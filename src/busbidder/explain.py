GOOD = 75
WEAK = 40
PHRASES = {
    "price": ("a lower price than most options", "a higher price than most options"),
    "duration": ("a shorter journey than most options", "a longer journey than most options"),
    "departure": ("a departure near your preferred time", "a departure far from your preferred time"),
    "flexibility": ("a flexible ticket", "a ticket that cannot be changed or refunded"),
    "rating": ("a good customer rating", "a weak customer rating"),
    "emissions": ("lower emissions than most options", "higher emissions than most options"),
}


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def explain(ranked, weights):
    best = ranked[0]
    offer = best.offer
    by_weight = [name for name in sorted(weights, key=weights.get, reverse=True) if weights[name]]
    known = [name for name in by_weight if name not in best.estimated]
    strengths = [PHRASES[name][0] for name in known if best.scores[name] >= GOOD]
    drawbacks = [PHRASES[name][1] for name in known if best.scores[name] < WEAK]
    if offer.transfers:
        drawbacks.append(f"{offer.transfers} transfer(s)")
    else:
        strengths.insert(0, "a direct route")
    lines = [
        f"Why {offer.offer_id} ({offer.company.name}) ranks first:",
        f"  Strengths: {_join(strengths) if strengths else 'no single strong point'}.",
        f"  Drawbacks: {_join(drawbacks) if drawbacks else 'none of the weighted criteria is weak'}.",
    ]
    missing = [name for name in by_weight if name in best.estimated]
    if missing:
        lines.append(f"  No data for {_join(missing)}, so a neutral score was used.")
    if len(ranked) > 1:
        gap = best.total - ranked[1].total
        lines.append(f"  It scores {gap:.2f} points more than {ranked[1].offer.offer_id}.")
        if gap < 1:
            lines.append("  The gap is small, so slightly different weights could change the order.")
    lines.append("  This is the best match for the chosen constraints and weights, not an objective best.")
    return lines
