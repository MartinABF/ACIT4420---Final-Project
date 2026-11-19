import logging
import statistics
from collections import Counter, defaultdict
from datetime import date

from busbidder.filtering import filter_offers
from busbidder.loader import load_marketplace
from busbidder.profiles import load_profiles
from busbidder.scoring import rank_offers
from busbidder.travel import TravelRequest

logging.disable(logging.WARNING)
market = load_marketplace("data")
profiles = load_profiles("config/profiles.json")


def rank(profile, destination, earliest=date(2026, 7, 10), latest=date(2026, 7, 14), **limits):
    request = profile.apply(TravelRequest(destination, earliest, latest, **limits))
    accepted = filter_offers(market.offers, request).accepted
    return request, accepted, rank_offers(accepted, request, profile.weights)


def weight_sensitivity():
    print("Balanced profile, Malaga 12-14 July, max EUR 50, max one transfer, changeable:")
    balanced = profiles["balanced"]
    request, accepted, _ = rank(balanced, "AGP", date(2026, 7, 12), date(2026, 7, 14), max_price=50,
                                max_transfers=1, require_changeable=True)
    for price in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
        weights = balanced.weights | {"price": price, "duration": round(0.65 - price, 2)}
        best = rank_offers(accepted, request, weights)[0].offer
        print(f"  price {price:.0%}, duration {0.65 - price:.0%}: {best.offer_id} ({best.company.name})")


def winners_by_company():
    print("\nWinners over all 15 destinations, 10-14 July, no other limits:")
    for name, profile in profiles.items():
        rankings = [rank(profile, code)[2] for code in market.destinations]
        wins = Counter(ranked[0].offer.company.name for ranked in rankings)
        night = min(i for r in rankings for i, item in enumerate(r, 1) if item.offer.company.code == "NOC")
        print(f"  {name:<9} {dict(wins)}, best NocheVia position {night}")


def missing_emissions():
    known = defaultdict(list)
    for offer in market.offers:
        if offer.co2_kg is not None:
            known[offer.company.code, offer.destination.code].append(offer.co2_kg)
    eco, changed = profiles["eco"], 0
    for code in market.destinations:
        request, accepted, before = rank(eco, code)
        missing = [offer for offer in accepted if offer.co2_kg is None]
        for offer in missing:
            offer.co2_kg = round(statistics.mean(known[offer.company.code, code]), 1)
        after = rank_offers(accepted, request, eco.weights)
        for offer in missing:
            offer.co2_kg = None
        changed += [i.offer for i in before[:3]] != [i.offer for i in after[:3]]
    print(f"\nEco top three changes after filling in missing CO2: {changed} of {len(market.destinations)}")


def irrelevant_offers():
    searches = removals = changes = 0
    for code in market.destinations:
        for profile in profiles.values():
            request, accepted, ranked = rank(profile, code)
            hits = sum(
                rank_offers([o for o in accepted if o is not item.offer], request, profile.weights)[0].offer
                is not ranked[0].offer
                for item in ranked[2:]
            )
            removals, changes, searches = removals + len(ranked) - 2, changes + hits, searches + (hits > 0)
    print(f"Removing one offer outside the top two changed the winner in {searches} of 75 searches "
          f"({changes} of {removals} removals)")


if __name__ == "__main__":
    weight_sensitivity()
    winners_by_company()
    missing_emissions()
    irrelevant_offers()
