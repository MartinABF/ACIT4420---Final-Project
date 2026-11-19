# Examples

Saved output from the program, made with the data in this repository. Each file starts with the command that produced it, run from the project folder with `.venv\Scripts\python`.

- `validate.txt`: the data check, with the ten rejected rows grouped by category.
- `search_budget_malaga.txt`: the example request from the assignment (Malaga, 12 to 14 July, at most EUR 50, at most one transfer, changeable ticket) with the budget profile, including the explanation of the winner.
- `compare_malaga_limits.txt`: the same request for all five profiles (scenario A).
- `compare_malaga_open.txt`: Malaga on 12 to 14 July with no other limits (scenario B).
- `compare_barcelona_open.txt`: Barcelona on 10 to 14 July with no other limits.
- `booking_and_cancel.txt`: booking a premium ticket, cancelling it with a full refund, and a second cancellation being refused. It was run with a separate output folder, so the booking is not stored in this repository, and the reference is different every time.
- `evaluation.txt`: the output of `scripts/evaluate.py`.
