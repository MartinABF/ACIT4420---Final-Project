import csv

import pytest

from busbidder.loader import OFFER_COLUMNS
from busbidder.models import Company, Destination


@pytest.fixture
def companies():
    return {"SOL": Company("SOL", "SolRuta", "Low-cost daytime services")}


@pytest.fixture
def destinations():
    return {"AGP": Destination("AGP", "Malaga", 530, True)}


@pytest.fixture
def row():
    return {
        "offer_id": "SOL-AGP-20260712-0830-B",
        "company_code": "SOL",
        "destination_code": "AGP",
        "departure": "2026-07-12T08:30",
        "arrival": "2026-07-12T14:30",
        "price_eur": "39.90",
        "transfers": "1",
        "luggage_kg": "15",
        "changeable": "no",
        "refundable": "no",
        "seats_available": "12",
        "rating": "3.8",
        "co2_kg": "14.8",
    }


@pytest.fixture
def write_offers(tmp_path):
    def write(rows, columns=OFFER_COLUMNS):
        path = tmp_path / "offers.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    return write
