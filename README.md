# BusBidder Spain

Final project for ACIT4420. BusBidder reads simulated bus offers from Madrid to 15 Spanish cities, removes the ones that break the traveller's requirements and ranks the rest with a weighted score. Booking comes in a later commit.

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

The profiles `balanced`, `budget`, `business`, `flexible` and `eco` are in `config/profiles.json`. To use your own weights, add `--weights price=40,duration=25,departure=15,flexibility=20`. They have to add up to 100.

The input files are in `data/`. Rows that fail validation are not corrected. They are left out and saved to `output/rejected_offers.csv` so they can be reviewed, and the log is in `output/busbidder.log`.

The data is simulated. This command recreates the same files:

```bash
.venv\Scripts\python scripts\generate_data.py
```

## Tests

```bash
.venv\Scripts\python -m pytest
```
