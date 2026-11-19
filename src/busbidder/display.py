from busbidder.explain import explain

LABELS = {"price": "Price", "duration": "Time", "departure": "Dep",
          "flexibility": "Flex", "rating": "Rate", "emissions": "CO2"}


def _hard_constraints(request, destination):
    parts = [
        f"to {destination.name}",
        f"{request.earliest} to {request.latest}",
        f"{request.passengers} seat(s)",
    ]
    limits = (
        (request.max_price, "total price up to EUR {:g}"),
        (request.max_transfers, "at most {} transfer(s)"),
        (request.max_duration, "at most {} minutes"),
        (request.min_luggage, "at least {} kg luggage"),
    )
    parts += [text.format(value) for value, text in limits if value is not None]
    if request.require_changeable:
        parts.append("changeable ticket")
    if request.require_refundable:
        parts.append("refundable ticket")
    return ", ".join(parts)


def _row(position, item, names):
    offer = item.offer
    minutes = offer.duration_minutes
    scores = "".join(
        f"{item.scores[name]:6.1f}{'*' if name in item.estimated else ' '}" for name in names
    )
    return (
        f"{position:>2} {item.total:6.2f}  {offer.company.name:<15}"
        f"{offer.departure:%m-%d %H:%M}  {minutes // 60:>2}h{minutes % 60:02d}"
        f"{offer.price_eur:8.2f}{offer.transfers:>6}  {offer.fare.label:<8}{scores} {offer.offer_id}"
    )


def format_search(destination, request, profile, weights, result, ranked, top):
    checked = len(result.accepted) + sum(result.removed.values())
    weight_text = ", ".join(f"{name} {value:.0%}" for name, value in weights.items() if value)
    removed = ", ".join(f"{name} {count}" for name, count in result.removed.items() if count)
    lines = [
        f"Profile: {profile.name} ({profile.description})",
        f"Hard constraints, offers that fail are removed: {_hard_constraints(request, destination)}",
        f"Soft preferences, these only change the score: {request.preferred_period} departure; "
        f"{weight_text}",
        f"Offers: {checked} checked, {len(ranked)} acceptable",
        f"Removed by: {removed or 'nothing'}",
    ]
    if not ranked:
        lines.append("No offers meet the hard constraints.")
        return "\n".join(lines)
    names = list(weights)
    header = "".join(f"{LABELS[name]:>6} " for name in names)
    lines += [
        "",
        f" # {'Score':>6}  {'Company':<15}{'Departure':<11}  {'Trip':>5}"
        f"{'EUR':>8}{'Stops':>6}  {'Fare':<8}{header} Offer ID",
    ]
    lines += [_row(number, item, names) for number, item in enumerate(ranked[:top], 1)]
    if any(item.estimated for item in ranked[:top]):
        lines.append("* no data for this offer, so a neutral score of 50 is used")
    lines += ["", *explain(ranked, weights)]
    return "\n".join(lines)


def format_booking(booking, offer):
    change = "changeable" if booking.changeable else "not changeable"
    refund = "refundable" if booking.refundable else "not refundable"
    return "\n".join([
        f"Booking confirmed: {booking.reference}",
        f"  {offer.company.name}, Madrid to {offer.destination.name}, {offer.departure:%Y-%m-%d %H:%M}",
        f"  Traveller: {booking.traveller}, {booking.passengers} seat(s), EUR {booking.total_eur:.2f}",
        f"  Ticket: {offer.fare.label}, {change}, {refund}. Payment: {booking.payment}",
        f"  Seats left on this departure: {offer.seats_available}",
    ])
