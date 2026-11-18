import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

from busbidder.errors import BusBidderError
from busbidder.loader import load_marketplace, write_rejected
from busbidder.logs import configure_logging

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


def build_parser():
    parser = argparse.ArgumentParser(prog="busbidder", description="BusBidder Spain")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="check the data files")
    validate.set_defaults(handler=run_validate)
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
