import argparse
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from busbidder.booking import BookingStore
from busbidder.display import format_booking, format_comparison, format_search
from busbidder.errors import BusBidderError, ConfigError, RequestError
from busbidder.filtering import filter_offers
from busbidder.loader import load_marketplace, write_rejected
from busbidder.logs import configure_logging
from busbidder.profiles import load_profiles, parse_weights
from busbidder.scoring import rank_offers, validate_weights
from busbidder.travel import PERIODS, TravelRequest

logger = logging.getLogger(__name__)


def run_validate(args):
    market = load_marketplace(args.data_dir)
    target = args.output_dir / "rejected_offers.csv"
    write_rejected(market.rejected, target)
    print(f"Companies:       {len(market.companies)}")
    print(f"Destinations:    {len(market.destinations)}")
    print(f"Valid offers:    {len(market.offers)}")
    print(f"Rejected offers: {len(market.rejected)}")
    for category, count in sorted(Counter(r.category for r in market.rejected).items()):
        print(f"  {category}: {count}")
    print(f"Rejected rows saved to {target}")
    return 0


def find_destination(destinations, text):
    wanted = text.strip().casefold()
    for destination in destinations.values():
        if wanted in (destination.code.casefold(), destination.name.casefold()):
            return destination
    names = ", ".join(sorted(d.name for d in destinations.values()))
    raise RequestError(f"unknown destination {text!r}. Choose one of: {names}")


def load_for_request(args):
    market = load_marketplace(args.data_dir)
    BookingStore(args.output_dir / "bookings.json").apply_to(market.offers)
    destination = find_destination(market.destinations, args.destination)
    request = TravelRequest(
        destination_code=destination.code,
        earliest=args.earliest,
        latest=args.latest,
        passengers=args.passengers,
        max_price=args.max_price,
        max_transfers=args.max_transfers,
        max_duration=args.max_duration,
        min_luggage=args.min_luggage,
        require_changeable=args.changeable,
        require_refundable=args.refundable,
    )
    return market, destination, request, load_profiles(args.profiles)


def run_search(args):
    if args.top < 1:
        raise RequestError("--top must be at least 1")
    market, destination, request, profiles = load_for_request(args)
    if args.profile not in profiles:
        raise ConfigError(f"unknown profile {args.profile!r}. Choose one of: {sorted(profiles)}")
    profile = profiles[args.profile]
    request = profile.apply(request, args.departure)
    weights = validate_weights(parse_weights(args.weights)) if args.weights else profile.weights
    result = filter_offers(market.offers, request)
    ranked = rank_offers(result.accepted, request, weights)
    logger.info("Search for %s: %d acceptable offers", destination.name, len(ranked))
    print(format_search(destination, request, profile, weights, result, ranked, args.top))
    return 0


def run_compare(args):
    market, destination, request, profiles = load_for_request(args)
    results = []
    for name, profile in profiles.items():
        profiled = profile.apply(request, args.departure)
        accepted = filter_offers(market.offers, profiled).accepted
        results.append((name, rank_offers(accepted, profiled, profile.weights)))
    print(format_comparison(destination, request, results))
    return 0


def run_book(args):
    market = load_marketplace(args.data_dir)
    store = BookingStore(args.output_dir / "bookings.json")
    store.apply_to(market.offers)
    wanted = args.offer_id.strip().upper()
    offer = next((o for o in market.offers if o.offer_id == wanted), None)
    if offer is None:
        raise RequestError(f"no valid offer with ID {args.offer_id}")
    print(format_booking(store.book(offer, args.name, args.passengers), offer))
    return 0


def run_cancel(args):
    booking = BookingStore(args.output_dir / "bookings.json").cancel(args.reference)
    print(f"Booking {booking.reference} is cancelled and the seat is released.")
    print(f"Refund: EUR {booking.refund_eur:.2f} (simulated)")
    return 0


def iso_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date like 2026-07-12") from error


def add_request_arguments(command):
    command.add_argument("--destination", required=True)
    command.add_argument("--from", dest="earliest", type=iso_date, required=True)
    command.add_argument("--to", dest="latest", type=iso_date, required=True)
    command.add_argument("--departure", choices=PERIODS)
    command.add_argument("--passengers", type=int, default=1)
    command.add_argument("--max-price", type=float)
    command.add_argument("--max-transfers", type=int)
    command.add_argument("--max-duration", type=int, help="minutes")
    command.add_argument("--min-luggage", type=int, help="kg")
    command.add_argument("--changeable", action="store_true")
    command.add_argument("--refundable", action="store_true")


def add_search_commands(commands):
    search = commands.add_parser("search", help="filter and rank offers")
    add_request_arguments(search)
    search.add_argument("--profile", default="balanced")
    search.add_argument("--weights", help="percentages, e.g. price=40,duration=25,...")
    search.add_argument("--top", type=int, default=5)
    search.set_defaults(handler=run_search)
    compare = commands.add_parser("compare", help="show the winner for every profile")
    add_request_arguments(compare)
    compare.set_defaults(handler=run_compare)


def build_parser():
    parser = argparse.ArgumentParser(prog="busbidder", description="BusBidder Spain")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--profiles", type=Path, default=Path("config/profiles.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="check the data files")
    validate.set_defaults(handler=run_validate)
    add_search_commands(commands)
    book = commands.add_parser("book", help="book seats on an offer from the search table")
    book.add_argument("--offer-id", required=True)
    book.add_argument("--name", required=True)
    book.add_argument("--passengers", type=int, default=1)
    book.set_defaults(handler=run_book)
    cancel = commands.add_parser("cancel", help="cancel a booking")
    cancel.add_argument("--reference", required=True)
    cancel.set_defaults(handler=run_cancel)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        configure_logging(args.output_dir / "busbidder.log")
        return args.handler(args)
    except (BusBidderError, OSError) as error:
        logger.error("%s", error)
        print(f"Error: {error}", file=sys.stderr)
        return 1
