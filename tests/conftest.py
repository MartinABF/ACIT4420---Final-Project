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
    values = ["SOL-AGP-20260712-0830-B", "SOL", "AGP", "2026-07-12T08:30", "2026-07-12T14:30",
              "39.90", "1", "15", "no", "no", "12", "3.8", "14.8"]
    return dict(zip(OFFER_COLUMNS, values))


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
