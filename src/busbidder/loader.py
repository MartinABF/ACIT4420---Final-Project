import csv
import logging
import re
from dataclasses import astuple, dataclass, fields
from datetime import datetime
from pathlib import Path

from busbidder.errors import (
    DataFileError,
    DuplicateRecordError,
    InconsistentRecordError,
    InvalidFieldError,
    MissingFieldError,
    NoSeatsError,
    RecordError,
    UnknownReferenceError,
)
from busbidder.models import Company, Destination, FareConditions, Offer

logger = logging.getLogger(__name__)

CODE = re.compile(r"[A-Z]{3}")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
OFFER_ID = re.compile(
    r"(?P<company>[A-Z]{3})-(?P<destination>[A-Z]{3})-"
    r"(?P<date>\d{8})-(?P<time>\d{4})-(?P<fare>[BFP])"
)

COMPANY_COLUMNS = ("code", "name", "profile")
DESTINATION_COLUMNS = ("code", "name", "distance_km", "coastal")
OFFER_COLUMNS = (
    "offer_id", "company_code", "destination_code", "departure", "arrival",
    "price_eur", "transfers", "luggage_kg", "changeable", "refundable",
    "seats_available", "rating", "co2_kg",
)


@dataclass(frozen=True)
class RejectedRecord:
    line: int
    offer_id: str
    category: str
    reason: str


@dataclass
class Marketplace:
    companies: dict
    destinations: dict
    offers: list
    rejected: list


def read_rows(path, required_columns):
    path = Path(path)
    try:
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            missing = set(required_columns) - set(reader.fieldnames or ())
            if missing:
                raise DataFileError(f"{path.name} is missing columns: {sorted(missing)}")
            return [(reader.line_num, row) for row in reader]
    except FileNotFoundError as error:
        raise DataFileError(f"data file not found: {path}") from error
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise DataFileError(f"could not read {path}: {error}") from error


def _text(row, column):
    value = (row.get(column) or "").strip()
    if not value:
        raise MissingFieldError(f"{column} is missing")
    return value


def _number(row, column, kind=float):
    text = _text(row, column)
    try:
        return kind(text)
    except ValueError as error:
        raise InvalidFieldError(f"{column} is not a valid number: {text!r}") from error


def _optional_number(row, column):
    return _number(row, column) if (row.get(column) or "").strip() else None


def _yes_no(row, column):
    text = _text(row, column).lower()
    if text not in {"yes", "no"}:
        raise InvalidFieldError(f"{column} must be yes or no, got {text!r}")
    return text == "yes"


def _code(row, column):
    text = _text(row, column)
    if not CODE.fullmatch(text):
        raise InvalidFieldError(f"{column} must be three capital letters, got {text!r}")
    return text


def _timestamp(row, column):
    text = _text(row, column)
    if not TIMESTAMP.fullmatch(text):
        raise InvalidFieldError(f"{column} must look like 2026-07-12T08:30, got {text!r}")
    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise InvalidFieldError(f"{column} is not a real date and time: {text!r}") from error


def _lookup(items, code, kind):
    if code not in items:
        raise UnknownReferenceError(f"unknown {kind}: {code}")
    return items[code]


def _parse_company(row):
    return Company(_code(row, "code"), _text(row, "name"), _text(row, "profile"))


def _parse_destination(row):
    return Destination(
        _code(row, "code"),
        _text(row, "name"),
        _number(row, "distance_km", int),
        _yes_no(row, "coastal"),
    )


def _load_reference(path, columns, parse):
    items = {}
    for line, row in read_rows(path, columns):
        try:
            item = parse(row)
            if item.code in items:
                raise DuplicateRecordError(f"duplicate code {item.code}")
        except RecordError as error:
            raise DataFileError(f"{Path(path).name} line {line}: {error}") from error
        items[item.code] = item
    if not items:
        raise DataFileError(f"{Path(path).name} has no rows")
    return items


def load_companies(path):
    return _load_reference(path, COMPANY_COLUMNS, _parse_company)


def load_destinations(path):
    return _load_reference(path, DESTINATION_COLUMNS, _parse_destination)


def _check_id_matches(parts, offer):
    expected = {
        "company": offer.company.code,
        "destination": offer.destination.code,
        "date": offer.departure.strftime("%Y%m%d"),
        "time": offer.departure.strftime("%H%M"),
        "fare": offer.fare.code,
    }
    for name, value in expected.items():
        if parts[name] != value:
            raise InconsistentRecordError(f"offer_id {name} does not match the row")


def parse_offer(row, companies, destinations):
    offer_id = _text(row, "offer_id")
    match = OFFER_ID.fullmatch(offer_id)
    if not match:
        raise InvalidFieldError(f"malformed offer_id: {offer_id!r}")
    offer = Offer(
        offer_id=offer_id,
        company=_lookup(companies, _text(row, "company_code"), "company"),
        destination=_lookup(destinations, _text(row, "destination_code"), "destination"),
        departure=_timestamp(row, "departure"),
        arrival=_timestamp(row, "arrival"),
        fare=FareConditions(_yes_no(row, "changeable"), _yes_no(row, "refundable")),
        price_eur=_number(row, "price_eur"),
        transfers=_number(row, "transfers", int),
        luggage_kg=_number(row, "luggage_kg", int),
        seats_available=_number(row, "seats_available", int),
        rating=_optional_number(row, "rating"),
        co2_kg=_optional_number(row, "co2_kg"),
    )
    _check_id_matches(match.groupdict(), offer)
    if offer.seats_available == 0:
        raise NoSeatsError("offer has no available seats")
    return offer


def load_offers(path, companies, destinations):
    offers, rejected, seen = [], [], set()
    for line, row in read_rows(path, OFFER_COLUMNS):
        try:
            if None in row:
                raise InconsistentRecordError("row has too many columns")
            offer = parse_offer(row, companies, destinations)
            if offer.offer_id in seen:
                raise DuplicateRecordError(f"duplicate offer_id {offer.offer_id}")
        except RecordError as error:
            offer_id = (row.get("offer_id") or "").strip()
            rejected.append(RejectedRecord(line, offer_id, error.category, str(error)))
            logger.warning("Rejected line %d (%s): %s", line, error.category, error)
            continue
        seen.add(offer.offer_id)
        offers.append(offer)
    logger.info("Loaded %d offers and rejected %d", len(offers), len(rejected))
    return offers, rejected


def load_marketplace(data_dir):
    data_dir = Path(data_dir)
    companies = load_companies(data_dir / "companies.csv")
    destinations = load_destinations(data_dir / "destinations.csv")
    offers, rejected = load_offers(data_dir / "offers.csv", companies, destinations)
    if not offers:
        raise DataFileError("offers.csv has no valid offers")
    return Marketplace(companies, destinations, offers, rejected)


def write_rejected(rejected, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(field.name for field in fields(RejectedRecord))
        writer.writerows(astuple(record) for record in rejected)
