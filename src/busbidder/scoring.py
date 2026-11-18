import math
from dataclasses import dataclass
from statistics import quantiles

from busbidder.errors import ConfigError
from busbidder.registry import Registry
from busbidder.travel import PERIODS

NEUTRAL = 50.0
DAY_MINUTES = 1440
DEPARTURE_TOLERANCE = 360
CORE_CRITERIA = ("price", "duration", "departure", "flexibility")

criteria = Registry("criterion")


def lower_is_better(values):
    known = [value for value in values if value is not None]
    if len(known) < 2:
        return [None if value is None else NEUTRAL for value in values]
    # Clipping to the 5th-95th percentile stops one extreme offer from
    # squeezing every other offer into a narrow part of the scale.
    cuts = quantiles(known, n=20, method="inclusive")
    low, high = cuts[0], cuts[-1]
    if low == high:
        return [None if value is None else NEUTRAL for value in values]
    return [
        None if value is None else 100 * (high - min(max(value, low), high)) / (high - low)
        for value in values
    ]


class Criterion:
    def raw(self, offer, request):
        raise NotImplementedError

    def normalise(self, values):
        return values

    def scores(self, offers, request):
        return self.normalise([self.raw(offer, request) for offer in offers])


class LowerIsBetter(Criterion):
    def normalise(self, values):
        return lower_is_better(values)


@criteria.register("price")
class Price(LowerIsBetter):
    def raw(self, offer, request):
        return offer.price_eur


@criteria.register("duration")
class Duration(LowerIsBetter):
    def raw(self, offer, request):
        return offer.duration_minutes


@criteria.register("emissions")
class Emissions(LowerIsBetter):
    def raw(self, offer, request):
        return offer.co2_kg


def _clock_gap(first, second):
    gap = abs(first - second) % DAY_MINUTES
    return min(gap, DAY_MINUTES - gap)


@criteria.register("departure")
class Departure(Criterion):
    def raw(self, offer, request):
        start, end = PERIODS[request.preferred_period]
        minute = offer.departure.hour * 60 + offer.departure.minute
        if start <= minute < end or start <= minute + DAY_MINUTES < end:
            return 100.0
        gap = min(_clock_gap(minute, start), _clock_gap(minute, end))
        return max(0.0, 100 * (1 - gap / DEPARTURE_TOLERANCE))


@criteria.register("flexibility")
class Flexibility(Criterion):
    def raw(self, offer, request):
        return 60.0 * offer.fare.changeable + 40.0 * offer.fare.refundable


@criteria.register("rating")
class Rating(Criterion):
    def raw(self, offer, request):
        return None if offer.rating is None else (offer.rating - 1) * 25


def validate_weights(weights):
    if not isinstance(weights, dict) or not weights:
        raise ConfigError("weights must be a non-empty mapping")
    unknown = set(weights) - set(criteria)
    if unknown:
        raise ConfigError(f"unknown criteria: {sorted(unknown)}")
    for name, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ConfigError(f"weight for {name} must be between 0 and 100%")
    missing = [name for name in CORE_CRITERIA if weights.get(name, 0) <= 0]
    if missing:
        raise ConfigError(f"these criteria need a weight above zero: {missing}")
    if not math.isclose(sum(weights.values()), 1, abs_tol=1e-9):
        raise ConfigError("weights must add up to 100%")
    return {name: float(value) for name, value in weights.items()}


@dataclass(frozen=True)
class RankedOffer:
    offer: object
    total: float
    scores: dict
    estimated: frozenset


def _sort_key(item):
    offer = item.offer
    return (-item.total, offer.price_eur, offer.duration_minutes, offer.departure, offer.offer_id)


def rank_offers(offers, request, weights):
    weights = validate_weights(weights)
    columns = {name: criteria[name]().scores(offers, request) for name in weights}
    ranked = []
    for index, offer in enumerate(offers):
        values = {name: column[index] for name, column in columns.items()}
        scores = {name: NEUTRAL if value is None else value for name, value in values.items()}
        total = round(sum(weights[name] * scores[name] for name in weights), 6)
        estimated = frozenset(name for name, value in values.items() if value is None)
        ranked.append(RankedOffer(offer, total, scores, estimated))
    return sorted(ranked, key=_sort_key)
