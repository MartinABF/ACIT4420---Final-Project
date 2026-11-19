# BusBidder Spain

Final project for ACIT4420. BusBidder reads simulated bus offers from Madrid to 15 Spanish cities, removes the ones that break the traveller's requirements and ranks the rest with a weighted score. You can then book a seat and cancel it again.

It needs Python 3.11 or newer. The program only uses the standard library, and pytest is needed for the tests.

## Setup

Run every command from the project folder. These are for PowerShell on Windows:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Run

Check the data files:

```bash
.venv\Scripts\python -m busbidder validate
```

Search for offers:

```bash
.venv\Scripts\python -m busbidder search --destination Malaga --from 2026-07-12 --to 2026-07-14 --max-price 50 --max-transfers 1 --changeable --profile budget
```

Destination, dates, seats, budget, transfers, duration, luggage and ticket rules are hard constraints, so an offer that breaks one is removed. Departure time and the weights are soft preferences and only change the score.

Each row shows the offer's values, its score for every criterion and the total. Below the table there is a short explanation of why the top offer won, which drawbacks it still has and how close the runner-up was.

The profiles `balanced`, `budget`, `business`, `flexible` and `eco` are in `config/profiles.json`. To use your own weights, add `--weights price=40,duration=25,departure=15,flexibility=20`. They have to add up to 100.

Book an offer by copying its ID from the search table:

```bash
.venv\Scripts\python -m busbidder book --offer-id COS-AGP-20260713-1500-P --name "Ola Nordmann"
```

The booking gets a reference like `BB-7K2M9Q` and is saved in `output/bookings.json` with the ticket rules and a simulated payment. No payment details are asked for. Searches count the booked seats, and `data/offers.csv` is never changed.

Cancel with the reference:

```bash
.venv\Scripts\python -m busbidder cancel --reference BB-7K2M9Q
```

A refundable (premium) ticket gets the full price back. Flex and basic tickets get nothing back, but the seat is released.

The input files are in `data/`. Rows that fail validation are not corrected. They are left out and saved to `output/rejected_offers.csv` so they can be reviewed, and the log is in `output/busbidder.log`.

The data is simulated. This command recreates the same files:

```bash
.venv\Scripts\python scripts\generate_data.py
```

## Tests

```bash
.venv\Scripts\python -m pytest
```
