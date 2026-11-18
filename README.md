# BusBidder Spain

Final project for ACIT4420. BusBidder reads simulated bus offers from Madrid to 15 Spanish cities and checks them before they are used. Filtering, ranking and booking come in later commits.

It needs Python 3.11 or newer. The program only uses the standard library, and pytest is needed for the tests.

## Setup

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Run

```bash
python -m busbidder validate
```

The input files are in `data/`. Rows that fail validation are not corrected. They are left out and saved to `output/rejected_offers.csv` so they can be reviewed, and the log is in `output/busbidder.log`.

The data is simulated. This command recreates the same files:

```bash
python scripts/generate_data.py
```

## Tests

```bash
python -m pytest
```
