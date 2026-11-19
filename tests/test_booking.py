import json
import logging
import re
from pathlib import Path

import pytest
from test_models import make_offer

from busbidder.booking import REFERENCE, BookingStore
from busbidder.cli import main
from busbidder.errors import BookingError
from busbidder.models import FareConditions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store(tmp_path):
    return BookingStore(tmp_path / "bookings.json")


def seats_after_reload(path):
    offer = make_offer()
    BookingStore(path).apply_to([offer])
    return offer.seats_available


def test_booking_saves_fare_rules_and_reduces_seats(store, tmp_path):
    offer = make_offer()
    booking = store.book(offer, " Ola ", passengers=2)
    assert REFERENCE.fullmatch(booking.reference)
    assert (offer.seats_available, booking.total_eur, booking.traveller) == (2, 60, "Ola")
    saved = json.loads((tmp_path / "bookings.json").read_text(encoding="utf-8"))[0]
    assert (saved["changeable"], saved["refundable"], saved["payment"]) == (False, False, "paid (simulated)")
    assert seats_after_reload(tmp_path / "bookings.json") == 2


@pytest.mark.parametrize(("name", "passengers"), [("Ola", 5), ("  ", 1), ("Ola", 0)])
def test_invalid_bookings_are_refused(store, name, passengers):
    with pytest.raises(BookingError):
        store.book(make_offer(), name, passengers)


@pytest.mark.parametrize(("refundable", "refund"), [(True, 30), (False, 0)])
def test_cancelling_refunds_by_fare_and_releases_the_seat(store, tmp_path, refundable, refund):
    reference = store.book(make_offer(fare=FareConditions(True, refundable)), "Ola").reference
    assert store.cancel(reference.lower()).refund_eur == refund
    assert seats_after_reload(tmp_path / "bookings.json") == 4


@pytest.mark.parametrize("reference", ["BB-12", "BB-AAAAAA"])
def test_cancel_refuses_bad_or_unknown_references(store, reference):
    with pytest.raises(BookingError):
        store.cancel(reference)


def test_booking_cannot_be_cancelled_twice(store):
    reference = store.book(make_offer(), "Ola").reference
    store.cancel(reference)
    with pytest.raises(BookingError, match="already cancelled"):
        store.cancel(reference)


def test_broken_bookings_file_is_reported(tmp_path):
    path = tmp_path / "bookings.json"
    path.write_text('[{"reference": "XX-1"}]', encoding="utf-8")
    with pytest.raises(BookingError):
        BookingStore(path)


def test_book_and_cancel_from_the_command_line(tmp_path, capsys):
    base = ["--data-dir", str(ROOT / "data"), "--output-dir", str(tmp_path)]
    assert main(base + ["book", "--offer-id", "cos-agp-20260713-1500-p", "--name", "Ola"]) == 0
    reference = re.search(r"BB-[A-Z0-9]{6}", capsys.readouterr().out).group()
    assert main(base + ["cancel", "--reference", reference]) == 0
    assert "Refund: EUR 48.01" in capsys.readouterr().out
    assert main(base + ["book", "--offer-id", "NOPE", "--name", "Ola"]) == 1
    logging.shutdown()
