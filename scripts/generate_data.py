import csv
import random
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from pathlib import Path

from busbidder.loader import OFFER_COLUMNS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEED = 4420
FIRST_DAY = date(2026, 7, 10)
DAYS = 5

COMPANIES = [
    ("SOL", "SolRuta", "Low-cost daytime services"),
    ("CAM", "Camino Express", "Fast direct connections between major cities"),
    ("COS", "CostaLink", "Strong coverage of coastal destinations"),
    ("VER", "VerdeBus", "Environment-focused services and modern vehicles"),
    ("NOC", "NocheVia", "Overnight and late-evening services"),
]

# code, name, road distance from Madrid in km, coastal, major city
DESTINATIONS = [
    ("BCN", "Barcelona", 620, True, True), ("VLC", "Valencia", 355, True, True),
    ("SVQ", "Seville", 530, False, True), ("AGP", "Malaga", 530, True, True),
    ("GRX", "Granada", 420, False, False), ("ODB", "Cordoba", 400, False, False),
    ("BIO", "Bilbao", 395, True, True), ("EAS", "San Sebastian", 450, True, False),
    ("ZAZ", "Zaragoza", 315, False, True), ("ALC", "Alicante", 420, True, False),
    ("MJV", "Murcia", 400, False, False), ("SLM", "Salamanca", 215, False, False),
    ("TOL", "Toledo", 75, False, False), ("SCQ", "Santiago de Compostela", 600, False, False),
    ("CDZ", "Cadiz", 650, True, False),
]

Style = namedtuple("Style", "price speed hours rating co2 transfer_risk")
STYLES = {
    "SOL": Style(0.82, 70, (7, 13), 3.6, 1.0, 0.50),
    "CAM": Style(1.18, 88, (8, 16), 4.4, 1.0, 0.05),
    "COS": Style(1.00, 78, (9, 15), 4.0, 1.0, 0.25),
    "VER": Style(1.10, 76, (10, 17), 4.3, 0.55, 0.20),
    "NOC": Style(0.92, 68, (22, 23), 3.9, 0.9, 0.30),
}

# changeable, refundable, price factor, luggage in kg
FARES = {
    "B": ("no", "no", 1.00, 15),
    "F": ("yes", "no", 1.15, 20),
    "P": ("yes", "yes", 1.30, 25),
}


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M")


def offer_id(company, destination, moment, fare):
    return f"{company}-{destination}-{moment:%Y%m%d}-{moment:%H%M}-{fare}"


def count_transfers(rng, company, style, km, coastal, major):
    if km < 150 or (company == "CAM" and major):
        return 0
    risk = style.transfer_risk + (0.2 if company == "COS" and not coastal else 0)
    if rng.random() >= risk:
        return 0
    return 2 if rng.random() < 0.15 else 1


def departure_rows(rng, company, destination, day, hour):
    style = STYLES[company]
    code, _, km, coastal, major = destination
    coastal_factor = 1.0
    speed = style.speed
    if company == "COS":
        coastal_factor = 0.90 if coastal else 1.08
        speed = style.speed * (1.08 if coastal else 1)
    transfers = count_transfers(rng, company, style, km, coastal, major)
    minutes = max(40, 5 * round((km / speed * 60 + transfers * 40) / 5))
    departure = datetime.combine(day, time(hour, rng.choice((0, 15, 30, 45))))
    arrival = departure + timedelta(minutes=minutes)
    base_price = (5 + km * 0.072) * style.price * coastal_factor
    rating = min(5.0, max(1.0, rng.gauss(style.rating, 0.15)))
    co2 = km * 0.028 * style.co2 * (1 + 0.08 * transfers)
    rating_text = "" if rng.random() < 0.04 else f"{rating:.1f}"
    co2_text = "" if rng.random() < 0.06 else f"{co2:.1f}"
    for fare in ("B", rng.choice("FP")):
        changeable, refundable, factor, luggage = FARES[fare]
        price = base_price * factor * rng.uniform(0.94, 1.08)
        yield {
            "offer_id": offer_id(company, code, departure, fare),
            "company_code": company,
            "destination_code": code,
            "departure": stamp(departure),
            "arrival": stamp(arrival),
            "price_eur": f"{price:.2f}",
            "transfers": transfers,
            "luggage_kg": luggage,
            "changeable": changeable,
            "refundable": refundable,
            "seats_available": rng.randint(1, 48),
            "rating": rating_text,
            "co2_kg": co2_text,
        }


def valid_rows(rng):
    days = [FIRST_DAY + timedelta(days=offset) for offset in range(DAYS)]
    for company, *_ in COMPANIES:
        for destination in DESTINATIONS:
            for day in days:
                for hour in STYLES[company].hours:
                    yield from departure_rows(rng, company, destination, day, hour)


def faulty_rows(base):
    def variant(minute, **changes):
        departure = datetime(2026, 7, 15, 5, minute)
        row = dict(
            base,
            offer_id=offer_id(base["company_code"], base["destination_code"], departure, "B"),
            departure=stamp(departure),
            arrival=stamp(departure + timedelta(hours=4)),
        )
        return row | changes

    return [
        variant(1, price_eur="-12.50"),
        variant(2, price_eur=""),
        variant(3, destination_code="XXX"),
        variant(4, departure="2026-13-40T08:00"),
        variant(5, arrival="2026-07-15T04:00"),
        variant(6, rating="7.0"),
        variant(7, seats_available=0),
        variant(8, changeable="yes"),
        variant(9, offer_id="SOL-123"),
        dict(base),
    ]


def write_csv(name, header, rows):
    DATA_DIR.mkdir(exist_ok=True)
    with (DATA_DIR / name).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    rng = random.Random(SEED)
    offers = list(valid_rows(rng))
    offers += faulty_rows(offers[0])
    write_csv("companies.csv", ("code", "name", "profile"), COMPANIES)
    write_csv(
        "destinations.csv",
        ("code", "name", "distance_km", "coastal"),
        ((c, n, km, "yes" if coast else "no") for c, n, km, coast, _ in DESTINATIONS),
    )
    write_csv("offers.csv", OFFER_COLUMNS, ([row[c] for c in OFFER_COLUMNS] for row in offers))
    print(f"Wrote {len(offers)} offer rows to {DATA_DIR}")


if __name__ == "__main__":
    main()
