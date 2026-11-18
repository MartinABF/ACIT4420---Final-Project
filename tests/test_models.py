from datetime import datetime

import pytest

from busbidder.errors import InconsistentRecordError, InvalidFieldError, MissingFieldError
from busbidder.fields import Bounded
from busbidder.models import Company, Destination, FareConditions, Offer


class Sample:
    level = Bounded(0, 100, kind=int)
    score = Bounded(1, 5, optional=True)

    def __init__(self, level=50, score=None):
        self.level = level
        self.score = score


def make_offer(**changes):
    values = {
        "offer_id": "SOL-AGP-20260712-2230-B",
        "company": Company("SOL", "SolRuta", "Low-cost"),
        "destination": Destination("AGP", "Malaga", 530, True),
        "departure": datetime(2026, 7, 12, 22, 30),
        "arrival": datetime(2026, 7, 13, 5, 0),
        "fare": FareConditions(False, False),
        "price_eur": 30,
        "transfers": 0,
        "luggage_kg": 15,
        "seats_available": 4,
    }
    return Offer(**values | changes)


@pytest.mark.parametrize("level", [0, 100])
def test_bounded_accepts_boundaries(level):
    assert Sample(level=level).level == level


@pytest.mark.parametrize("level", [-1, 101])
def test_bounded_rejects_values_outside_range(level):
    with pytest.raises(InvalidFieldError):
        Sample(level=level)


@pytest.mark.parametrize("level", ["10", 1.5, True])
def test_bounded_rejects_wrong_types(level):
    with pytest.raises(InvalidFieldError):
        Sample(level=level)


def test_bounded_rejects_nan():
    with pytest.raises(InvalidFieldError):
        Sample(score=float("nan"))


def test_bounded_handles_missing_values():
    assert Sample(score=None).score is None
    with pytest.raises(MissingFieldError):
        Sample(level=None)


def test_assignment_after_creation_is_validated():
    offer = make_offer()
    with pytest.raises(InvalidFieldError):
        offer.price_eur = -1
    assert offer.price_eur == 30


def test_overnight_journey_duration_and_date():
    offer = make_offer()
    assert offer.duration_minutes == 390
    assert offer.travel_date.isoformat() == "2026-07-12"


@pytest.mark.parametrize(
    "arrival",
    [datetime(2026, 7, 12, 22, 30), datetime(2026, 7, 12, 21, 0), datetime(2026, 7, 13, 22, 31)],
)
def test_impossible_journeys_are_rejected(arrival):
    with pytest.raises(InconsistentRecordError):
        make_offer(arrival=arrival)


def test_journey_of_exactly_24_hours_is_allowed():
    assert make_offer(arrival=datetime(2026, 7, 13, 22, 30)).duration_minutes == 1440


@pytest.mark.parametrize(
    ("changeable", "refundable", "code", "label"),
    [(False, False, "B", "basic"), (True, False, "F", "flex"), (True, True, "P", "premium")],
)
def test_fare_types(changeable, refundable, code, label):
    fare = FareConditions(changeable, refundable)
    assert (fare.code, fare.label) == (code, label)


def test_refundable_fare_must_be_changeable():
    with pytest.raises(InconsistentRecordError):
        FareConditions(False, True)
