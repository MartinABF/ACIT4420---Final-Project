from dataclasses import dataclass
from datetime import timedelta

from busbidder.errors import InconsistentRecordError, InvalidFieldError
from busbidder.fields import Bounded

MAX_JOURNEY = timedelta(hours=24)
FARE_TYPES = {
    (False, False): ("B", "basic"),
    (True, False): ("F", "flex"),
    (True, True): ("P", "premium"),
}


@dataclass(frozen=True)
class Company:
    code: str
    name: str
    profile: str


@dataclass(frozen=True)
class Destination:
    code: str
    name: str
    distance_km: int
    coastal: bool

    def __post_init__(self):
        if self.distance_km <= 0:
            raise InvalidFieldError("distance_km must be positive")


@dataclass(frozen=True)
class FareConditions:
    changeable: bool
    refundable: bool

    def __post_init__(self):
        if self.refundable and not self.changeable:
            raise InconsistentRecordError("a refundable fare must also be changeable")

    @property
    def code(self):
        return FARE_TYPES[self.changeable, self.refundable][0]

    @property
    def label(self):
        return FARE_TYPES[self.changeable, self.refundable][1]


class Offer:
    price_eur = Bounded(0.01, 500)
    transfers = Bounded(0, 3, kind=int)
    luggage_kg = Bounded(0, 50, kind=int)
    seats_available = Bounded(0, 80, kind=int)
    rating = Bounded(1, 5, optional=True)
    co2_kg = Bounded(0, 200, optional=True)

    def __init__(
        self,
        *,
        offer_id,
        company,
        destination,
        departure,
        arrival,
        fare,
        price_eur,
        transfers,
        luggage_kg,
        seats_available,
        rating=None,
        co2_kg=None,
    ):
        journey = arrival - departure
        if journey <= timedelta(0):
            raise InconsistentRecordError("arrival must be after departure")
        if journey > MAX_JOURNEY:
            raise InconsistentRecordError("journey cannot be longer than 24 hours")
        self.offer_id = offer_id
        self.company = company
        self.destination = destination
        self.departure = departure
        self.arrival = arrival
        self.fare = fare
        self.price_eur = price_eur
        self.transfers = transfers
        self.luggage_kg = luggage_kg
        self.seats_available = seats_available
        self.rating = rating
        self.co2_kg = co2_kg

    @property
    def duration_minutes(self):
        return int((self.arrival - self.departure).total_seconds() // 60)

    @property
    def travel_date(self):
        return self.departure.date()

    def __repr__(self):
        return f"Offer({self.offer_id!r}, {self.price_eur:.2f} EUR)"
