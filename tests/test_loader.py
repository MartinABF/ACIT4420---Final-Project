import csv
import logging
from collections import Counter
from pathlib import Path

import pytest

from busbidder.cli import main
from busbidder.errors import DataFileError, RecordError
from busbidder.loader import (
    OFFER_COLUMNS,
    RejectedRecord,
    load_companies,
    load_marketplace,
    load_offers,
    parse_offer,
    write_rejected,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_valid_row_becomes_offer(row, companies, destinations):
    offer = parse_offer(row, companies, destinations)
    assert offer.price_eur == 39.90
    assert offer.company.name == "SolRuta"
    assert offer.destination.name == "Malaga"
    assert offer.duration_minutes == 360
    assert offer.fare.label == "basic"


@pytest.mark.parametrize(
    ("change", "category"),
    [
        ({"price_eur": "-1"}, "invalid_value"),
        ({"price_eur": "cheap"}, "invalid_value"),
        ({"price_eur": ""}, "missing_value"),
        ({"price_eur": "nan"}, "invalid_value"),
        ({"transfers": "1.5"}, "invalid_value"),
        ({"company_code": "XXX"}, "unknown_reference"),
        ({"destination_code": "XXX"}, "unknown_reference"),
        ({"departure": "2026-13-40T08:30"}, "invalid_value"),
        ({"departure": "12/07/2026 08:30"}, "invalid_value"),
        ({"arrival": "2026-07-12T08:00"}, "inconsistent"),
        ({"rating": "0.9"}, "invalid_value"),
        ({"rating": "5.1"}, "invalid_value"),
        ({"seats_available": "0"}, "no_seats"),
        ({"seats_available": "-3"}, "invalid_value"),
        ({"offer_id": "SOL-123"}, "invalid_value"),
        ({"offer_id": "SOL-AGP-20260713-0830-B"}, "inconsistent"),
        ({"changeable": "yes"}, "inconsistent"),
        ({"changeable": "maybe"}, "invalid_value"),
    ],
)
def test_bad_rows_get_the_right_category(row, companies, destinations, change, category):
    with pytest.raises(RecordError) as caught:
        parse_offer(row | change, companies, destinations)
    assert caught.value.category == category


@pytest.mark.parametrize(
    "change",
    [{"rating": "1"}, {"rating": "5"}, {"seats_available": "1"}, {"price_eur": "0.01"}],
)
def test_boundary_values_are_accepted(row, companies, destinations, change):
    parse_offer(row | change, companies, destinations)


def test_optional_values_can_be_missing(row, companies, destinations):
    offer = parse_offer(row | {"rating": "", "co2_kg": ""}, companies, destinations)
    assert offer.rating is None
    assert offer.co2_kg is None


def test_load_offers_keeps_good_rows_and_reports_bad_ones(
    row, companies, destinations, write_offers
):
    path = write_offers([row, row, row | {"price_eur": "-1"}])
    offers, rejected = load_offers(path, companies, destinations)
    assert len(offers) == 1
    assert [(r.line, r.category) for r in rejected] == [(3, "duplicate"), (4, "invalid_value")]


def test_row_with_extra_column_is_rejected(row, companies, destinations, write_offers):
    path = write_offers([row])
    with path.open("a", encoding="utf-8") as file:
        file.write(",".join(row.values()).replace("0830", "0845") + ",extra\n")
    offers, rejected = load_offers(path, companies, destinations)
    assert len(offers) == 1
    assert rejected[0].category == "inconsistent"


def test_missing_file_raises_data_file_error(tmp_path, companies, destinations):
    with pytest.raises(DataFileError, match="not found"):
        load_offers(tmp_path / "nothing.csv", companies, destinations)


def test_missing_column_raises_data_file_error(row, companies, destinations, write_offers):
    path = write_offers([row], [c for c in OFFER_COLUMNS if c != "price_eur"])
    with pytest.raises(DataFileError, match="price_eur"):
        load_offers(path, companies, destinations)


def test_duplicate_reference_code_stops_loading(tmp_path):
    path = tmp_path / "companies.csv"
    path.write_text("code,name,profile\nSOL,A,x\nSOL,B,y\n", encoding="utf-8")
    with pytest.raises(DataFileError, match="line 3"):
        load_companies(path)


def test_write_rejected_creates_review_file(tmp_path):
    target = tmp_path / "out" / "rejected.csv"
    write_rejected([RejectedRecord(4, "X", "duplicate", "seen before")], target)
    with target.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))[0]["category"] == "duplicate"


def test_project_dataset():
    market = load_marketplace(DATA_DIR)
    assert len(market.companies) == 5
    assert len(market.destinations) == 15
    assert len(market.offers) == 1500
    pairs = {(o.company.code, o.destination.code) for o in market.offers}
    assert len(pairs) == 75
    assert Counter(r.category for r in market.rejected) == {
        "invalid_value": 4,
        "inconsistent": 2,
        "missing_value": 1,
        "unknown_reference": 1,
        "no_seats": 1,
        "duplicate": 1,
    }


def test_cli_validate(tmp_path, capsys):
    code = main(["--data-dir", str(DATA_DIR), "--output-dir", str(tmp_path), "validate"])
    logging.shutdown()
    assert code == 0
    assert "Valid offers:    1500" in capsys.readouterr().out
    assert (tmp_path / "rejected_offers.csv").exists()
    assert "Rejected line" in (tmp_path / "busbidder.log").read_text(encoding="utf-8")


def test_cli_reports_missing_data(tmp_path, capsys):
    code = main(["--data-dir", str(tmp_path / "x"), "--output-dir", str(tmp_path), "validate"])
    logging.shutdown()
    assert code == 1
    assert "not found" in capsys.readouterr().err
