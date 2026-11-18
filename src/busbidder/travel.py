from dataclasses import dataclass
from datetime import date

from busbidder.errors import RequestError

# Minutes after midnight. Night runs past midnight, so it ends after 1440.
PERIODS = {
    "morning": (360, 720),
    "afternoon": (720, 1080),
    "evening": (1080, 1320),
    "night": (1320, 1800),
}


@dataclass(frozen=True)
class TravelRequest:
    destination_code: str
    earliest: date
    latest: date
    passengers: int = 1
    max_price: float | None = None
    max_transfers: int | None = None
    max_duration: int | None = None
    min_luggage: int | None = None
    require_changeable: bool = False
    require_refundable: bool = False
    preferred_period: str = "morning"

    def __post_init__(self):
        if self.earliest > self.latest:
            raise RequestError("the travel window ends before it starts")
        if self.passengers < 1:
            raise RequestError("there must be at least one passenger")
        if self.preferred_period not in PERIODS:
            raise RequestError(f"unknown departure period: {self.preferred_period}")
        for name in ("max_price", "max_transfers", "max_duration", "min_luggage"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise RequestError(f"{name} cannot be negative")
