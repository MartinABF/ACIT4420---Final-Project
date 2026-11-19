import json
import logging
import re
import secrets
import string
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from busbidder.errors import BookingError

logger = logging.getLogger(__name__)
REFERENCE = re.compile(r"BB-[A-Z0-9]{6}")
CHARACTERS = string.ascii_uppercase + string.digits


@dataclass
class Booking:
    reference: str
    offer_id: str
    traveller: str
    passengers: int
    total_eur: float
    changeable: bool
    refundable: bool
    created: str
    status: str = "confirmed"
    payment: str = "paid (simulated)"
    refund_eur: float = 0.0


class BookingStore:
    def __init__(self, path):
        self.path = Path(path)
        self.bookings = {booking.reference: booking for booking in self._read()}

    def _read(self):
        if not self.path.exists():
            return []
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            bookings = [Booking(**row) for row in rows]
        except (OSError, ValueError, TypeError) as error:
            raise BookingError(f"could not read {self.path}: {error}") from error
        for booking in bookings:
            if not REFERENCE.fullmatch(booking.reference):
                raise BookingError(f"invalid reference in {self.path.name}: {booking.reference!r}")
        return bookings

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(booking) for booking in self.bookings.values()]
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def apply_to(self, offers):
        taken = Counter()
        for booking in self.bookings.values():
            if booking.status == "confirmed":
                taken[booking.offer_id] += booking.passengers
        for offer in offers:
            if taken[offer.offer_id] > offer.seats_available:
                raise BookingError(f"more seats are booked than exist on {offer.offer_id}")
            offer.seats_available -= taken[offer.offer_id]

    def _new_reference(self):
        while True:
            reference = "BB-" + "".join(secrets.choice(CHARACTERS) for _ in range(6))
            if REFERENCE.fullmatch(reference) and reference not in self.bookings:
                return reference

    def book(self, offer, traveller, passengers=1):
        if not traveller.strip():
            raise BookingError("the traveller's name is required")
        if passengers < 1:
            raise BookingError("there must be at least one passenger")
        if offer.seats_available < passengers:
            raise BookingError(f"only {offer.seats_available} seat(s) left on {offer.offer_id}")
        booking = Booking(
            self._new_reference(), offer.offer_id, traveller.strip(), passengers,
            round(offer.price_eur * passengers, 2), offer.fare.changeable, offer.fare.refundable,
            datetime.now().isoformat(timespec="seconds"),
        )
        self.bookings[booking.reference] = booking
        self._save()
        offer.seats_available -= passengers
        logger.info("Booked %s on %s", booking.reference, offer.offer_id)
        return booking

    def cancel(self, reference):
        reference = reference.strip().upper()
        if not REFERENCE.fullmatch(reference):
            raise BookingError(f"{reference!r} is not a reference like BB-7K2M9Q")
        booking = self.bookings.get(reference)
        if booking is None:
            raise BookingError(f"no booking with reference {reference}")
        if booking.status == "cancelled":
            raise BookingError(f"{reference} is already cancelled")
        booking.status = "cancelled"
        booking.refund_eur = booking.total_eur if booking.refundable else 0.0
        self._save()
        logger.info("Cancelled %s with a refund of EUR %.2f", reference, booking.refund_eur)
        return booking
