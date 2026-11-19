import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from test_models import make_offer

from busbidder.cli import main
from busbidder.errors import ConfigError, RequestError
from busbidder.explain import explain
from busbidder.filtering import filter_offers
from busbidder.loader import load_marketplace
from busbidder.models import FareConditions
from busbidder.profiles import load_profiles, parse_weights
from busbidder.scoring import criteria, lower_is_better, rank_offers, validate_weights
from busbidder.travel import TravelRequest

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {"price": 0.4, "duration": 0.25, "departure": 0.15, "flexibility": 0.2}
SEARCH = ["search", "--destination", "malaga", "--from", "2026-07-12", "--to", "2026-07-14"]


def make_request(**changes):
    values = {"destination_code": "AGP", "earliest": date(2026, 7, 12), "latest": date(2026, 7, 14)}
    return TravelRequest(**values | changes)


def leaving_at(hour, minute=0):
    departure = datetime(2026, 7, 12, hour, minute)
    return make_offer(departure=departure, arrival=departure + timedelta(hours=2))


def run_cli(tmp_path, *arguments):
    base = ["--data-dir", str(ROOT / "data"), "--output-dir", str(tmp_path)]
    code = main(base + ["--profiles", str(ROOT / "config" / "profiles.json"), *arguments])
    logging.shutdown()
    return code


@pytest.mark.parametrize(
    ("constraint", "allowed", "refused"),
    [
        ("destination", {"destination_code": "AGP"}, {"destination_code": "BCN"}),
        ("travel_window", {"latest": date(2026, 7, 12)}, {"earliest": date(2026, 7, 13)}),
        ("seats", {"passengers": 4}, {"passengers": 5}),
        ("budget", {"max_price": 30}, {"max_price": 29.99}),
        ("transfers", {"max_transfers": 1}, {"max_transfers": 0}),
        ("duration", {"max_duration": 390}, {"max_duration": 389}),
        ("luggage", {"min_luggage": 15}, {"min_luggage": 16}),
        ("changeable", {}, {"require_changeable": True}),
        ("refundable", {}, {"require_refundable": True}),
    ],
)
def test_hard_constraints_at_their_limits(constraint, allowed, refused):
    offer = make_offer(transfers=1)
    assert filter_offers([offer], make_request(**allowed)).accepted == [offer]
    result = filter_offers([offer], make_request(**refused))
    assert result.accepted == []
    assert result.removed[constraint] == 1


def test_budget_covers_all_passengers():
    assert not filter_offers([make_offer()], make_request(passengers=2, max_price=59)).accepted


def test_impossible_request_is_refused():
    with pytest.raises(RequestError):
        make_request(earliest=date(2026, 7, 15))


def test_lower_values_score_higher():
    assert lower_is_better([10, 20, 30]) == [100, 50, 0]


def test_extreme_value_does_not_flatten_the_scale():
    values = list(range(10, 30)) + [500]
    assert lower_is_better(values)[10] == pytest.approx(50)


def test_equal_and_missing_values():
    assert lower_is_better([7, 7]) == [50, 50]
    assert lower_is_better([7, None]) == [50, None]


@pytest.mark.parametrize(
    ("period", "hour", "score"),
    [
        ("morning", 8, 100),
        ("morning", 12, 100),
        ("morning", 15, 50),
        ("morning", 20, 0),
        ("night", 23, 100),
        ("night", 2, 100),
    ],
)
def test_departure_score(period, hour, score):
    request = make_request(preferred_period=period)
    assert criteria["departure"]().raw(leaving_at(hour), request) == pytest.approx(score)


@pytest.mark.parametrize(
    ("changeable", "refundable", "score"),
    [(False, False, 0), (True, False, 60), (True, True, 100)],
)
def test_flexibility_score(changeable, refundable, score):
    offer = make_offer(fare=FareConditions(changeable, refundable))
    assert criteria["flexibility"]().raw(offer, make_request()) == score


def test_cheaper_offer_ranks_first_when_all_else_is_equal():
    cheap, dear = make_offer(price_eur=20), make_offer(price_eur=40)
    ranked = rank_offers([dear, cheap], make_request(), WEIGHTS)
    assert [item.offer for item in ranked] == [cheap, dear]
    assert ranked[0].total > ranked[1].total


def test_ties_are_broken_the_same_way_every_time():
    first, second = make_offer(offer_id="A"), make_offer(offer_id="B")
    for offers in ([first, second], [second, first]):
        assert rank_offers(offers, make_request(), WEIGHTS)[0].offer is first


def test_missing_rating_gets_neutral_score():
    weights = WEIGHTS | {"price": 0.3, "rating": 0.1}
    item = rank_offers([make_offer()], make_request(), weights)[0]
    assert item.scores["rating"] == 50
    assert item.estimated == {"rating"}


@pytest.mark.parametrize(
    "change",
    [{"price": 0.5}, {"speed": 0.0}, {"price": -0.4}, {"price": True}, {"departure": 0}],
)
def test_invalid_weights_are_refused(change):
    with pytest.raises(ConfigError):
        validate_weights(WEIGHTS | change)


def test_parse_weights_reads_percentages():
    assert parse_weights("price=40, duration=60") == {"price": 0.4, "duration": 0.6}
    with pytest.raises(ConfigError):
        parse_weights("price:40")


def test_profile_never_weakens_a_hard_constraint():
    business = load_profiles(ROOT / "config" / "profiles.json")["business"]
    request = business.apply(make_request(max_transfers=2), "evening")
    assert (request.max_transfers, request.require_changeable) == (0, True)
    assert request.preferred_period == "evening"


def test_broken_profile_file_is_reported(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_profiles(path)


def test_explanation_gives_strengths_drawbacks_and_limits():
    cheap, dear = make_offer(price_eur=20, offer_id="A"), make_offer(price_eur=40, offer_id="B")
    text = "\n".join(explain(rank_offers([dear, cheap], make_request(), WEIGHTS), WEIGHTS))
    assert "A (SolRuta) ranks first" in text
    assert "Strengths: a direct route and a lower price than most options." in text
    assert "cannot be changed or refunded and a departure far from" in text
    assert "points more than B" in text
    assert "not an objective best" in text


def test_explanation_for_one_offer_and_for_a_close_race():
    alone = explain(rank_offers([make_offer()], make_request(), WEIGHTS), WEIGHTS)
    assert not any("points more" in line for line in alone)
    twins = rank_offers([make_offer(offer_id="A"), make_offer(offer_id="B")], make_request(), WEIGHTS)
    assert any("gap is small" in line for line in explain(twins, WEIGHTS))


def test_profiles_recommend_different_offers():
    market = load_marketplace(ROOT / "data")
    winners = set()
    for profile in load_profiles(ROOT / "config" / "profiles.json").values():
        request = profile.apply(make_request())
        accepted = filter_offers(market.offers, request).accepted
        winners.add(rank_offers(accepted, request, profile.weights)[0].offer.offer_id)
    assert len(winners) >= 3


def test_search_shows_constraints_and_ranking(tmp_path, capsys):
    assert run_cli(tmp_path, *SEARCH, "--max-price", "50", "--changeable", "--top", "3") == 0
    output = capsys.readouterr().out
    assert "Hard constraints" in output and "Soft preferences" in output
    assert "total price up to EUR 50" in output
    assert "\n 3 " in output and "\n 4 " not in output
    assert "ranks first" in output


def test_search_without_matches(tmp_path, capsys):
    assert run_cli(tmp_path, *SEARCH, "--max-price", "1") == 0
    assert "No offers meet" in capsys.readouterr().out


@pytest.mark.parametrize(
    "extra", [["--profile", "nobody"], ["--weights", "price=100"], ["--top", "0"]]
)
def test_search_reports_bad_input(tmp_path, capsys, extra):
    assert run_cli(tmp_path, *SEARCH, *extra) == 1
    assert "Error:" in capsys.readouterr().err
