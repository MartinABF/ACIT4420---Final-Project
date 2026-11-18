from dataclasses import dataclass

from busbidder.registry import Registry

constraints = Registry("constraint")


@constraints.register("destination")
def goes_to_destination(offer, request):
    return offer.destination.code == request.destination_code


@constraints.register("travel_window")
def inside_travel_window(offer, request):
    return request.earliest <= offer.travel_date <= request.latest


@constraints.register("seats")
def has_enough_seats(offer, request):
    return offer.seats_available >= request.passengers


@constraints.register("budget")
def within_budget(offer, request):
    return request.max_price is None or offer.price_eur * request.passengers <= request.max_price


@constraints.register("transfers")
def within_transfers(offer, request):
    return request.max_transfers is None or offer.transfers <= request.max_transfers


@constraints.register("duration")
def within_duration(offer, request):
    return request.max_duration is None or offer.duration_minutes <= request.max_duration


@constraints.register("luggage")
def allows_luggage(offer, request):
    return request.min_luggage is None or offer.luggage_kg >= request.min_luggage


@constraints.register("changeable")
def meets_change_rule(offer, request):
    return offer.fare.changeable or not request.require_changeable


@constraints.register("refundable")
def meets_refund_rule(offer, request):
    return offer.fare.refundable or not request.require_refundable


@dataclass
class FilterResult:
    accepted: list
    removed: dict


def filter_offers(offers, request):
    accepted = []
    removed = {name: 0 for name in constraints}
    for offer in offers:
        failed = next((n for n, check in constraints.items() if not check(offer, request)), None)
        if failed is None:
            accepted.append(offer)
        else:
            removed[failed] += 1
    return FilterResult(accepted, removed)
