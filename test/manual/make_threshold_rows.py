# test/manual/make_threshold_rows.py
"""Write the split CSVs the threshold index probe's fixture is loaded from.

Run me AFTER the probe's first paste, which prints the two ids needed here:

    .venv/Scripts/python.exe test/manual/make_threshold_rows.py \
        --owner-id 7 --parent-id 1

Row data lives in Python rather than in the probe because the experiment's
validity rests on knowing EXACTLY how many rows carry a blank in the
null-test column. A query that returns fewer rows than expected is a finding
only if the expected number is known, and known-ness comes from the tests in
test/test_threshold_rows.py. A browser-generated file cannot have any.
"""

import argparse
import csv
import datetime as dt
from pathlib import Path

TOTAL = 6000

# One clean baseline below the ~2500 auto-index trigger, one past it, then
# tight either side of 5000 because Microsoft documents the effective
# threshold as variable ("not always 5,000").
CHECKPOINTS: tuple[int, ...] = (1000, 3000, 4900, 5100, 6000)

# SharePoint INTERNAL column names, in CSV column order. The Power Automate
# batch-create pattern maps headers straight through to the request body, so
# Person and Lookup columns must appear with the `Id` suffix the REST API
# expects — `Owner` and `Parent` would be silently ignored.
HEADERS: tuple[str, ...] = (
    "Title", "Bucket", "ClosedAt", "Shadow", "SortBait", "OwnerId", "ParentId",
)

_BUCKETS: tuple[str, ...] = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")

# The value every comparison filter asks for. Rare enough to be selective,
# and its count is exactly known, which is the point.
RARE_BUCKET = "Z"

_EPOCH = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)

_DEFAULT_OUT = Path(__file__).parent / "rows"


def bucket_for(row: int) -> str:
    """`Z` on every 100th row, else the B1-B7 cycle.

    The substitution OVERRIDES the cycle rather than extending it, so the
    seven common values are not evenly sized. Deliberate and harmless: the
    filters only ever ask for `Z`.
    """
    if row % 100 == 0:
        return RARE_BUCKET
    return _BUCKETS[(row - 1) % len(_BUCKETS)]


def closed_at_for(row: int) -> str:
    """Blank on every 5th row — the null-test population, 1200 of 6000."""
    if row % 5 == 0:
        return ""
    stamp = _EPOCH + dt.timedelta(days=row % 1000)
    return stamp.isoformat().replace("+00:00", "Z")


def sort_bait_for(row: int) -> str:
    """High-cardinality and deliberately out of order, so sorting on it costs
    SharePoint real work. A multiplicative hash, NOT random: the files must be
    byte-identical on every run or the tests cannot pin anything."""
    return f"{(row * 2654435761) % 1_000_000:06d}-{row:06d}"


def build_rows(
    total: int = TOTAL, owner_id: str = "", parent_id: str = "",
) -> list[dict[str, str]]:
    """One dict per row, keyed by the CSV headers.

    `OwnerId` lands on every 4th row and `ClosedAt` blanks on every 5th, so
    the two populations overlap on only every 20th row. Offsetting them keeps
    the Person result from being read as a consequence of the null result.
    """
    rows: list[dict[str, str]] = []
    for row in range(1, total + 1):
        bucket = bucket_for(row)
        rows.append({
            "Title": f"Row {row:06d}",
            "Bucket": bucket,
            # Byte-identical to Bucket on purpose: only the index differs.
            "Shadow": bucket,
            "ClosedAt": closed_at_for(row),
            "SortBait": sort_bait_for(row),
            "OwnerId": owner_id if row % 4 == 0 else "",
            "ParentId": parent_id,
        })
    return rows


def split_plan(
    checkpoints: tuple[int, ...] = CHECKPOINTS,
) -> list[tuple[int, int, int]]:
    """`(sequence, first row, last row)` per file, one file per checkpoint.

    Split to match the RUN PLAN rather than the batch size. SharePoint's batch
    API takes up to a thousand operations per request and the flow chunks
    internally, so file boundaries are free to mean something else — here,
    "load this and the list is at the next checkpoint".
    """
    plan: list[tuple[int, int, int]] = []
    previous = 0
    for sequence, checkpoint in enumerate(checkpoints, start=1):
        plan.append((sequence, previous + 1, checkpoint))
        previous = checkpoint
    return plan


def file_name(sequence: int, checkpoint: int) -> str:
    """`to-<n>` is the list total AFTER loading this file, not its row count.
    The operator reads the run plan off the file names."""
    return f"threshold-rows-{sequence:02d}-to-{checkpoint}.csv"


def write_csvs(rows: list[dict[str, str]], out_dir: Path) -> list[Path]:
    """Write one CSV per checkpoint. Returns what was written, in load order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for sequence, first, last in split_plan():
        target = out_dir / file_name(sequence, last)
        # newline="" is required: csv writes its own line terminators, and
        # without this Windows turns each into CRLF and every row gains a
        # blank line.
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(HEADERS))
            writer.writeheader()
            writer.writerows(rows[first - 1:last])
        written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the threshold probe's split CSVs.",
    )
    parser.add_argument(
        "--owner-id", default="",
        help="Site user id for the Person column. The probe prints it on run 1.",
    )
    parser.add_argument(
        "--parent-id", default="",
        help="Item id in the parent list. The probe prints it on run 1.",
    )
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    rows = build_rows(owner_id=args.owner_id, parent_id=args.parent_id)
    for path in write_csvs(rows, args.out):
        print(f"wrote {path}")
    if not args.owner_id or not args.parent_id:
        # Not an error: generating without a tenant is useful. But the two
        # columns will be empty, and the Person and Lookup questions then have
        # no data to answer from — say so rather than let a run report them
        # NOT ESTABLISHED for a reason nobody remembers.
        print(
            "WARNING: --owner-id and/or --parent-id were not supplied, so the "
            "Person and Lookup columns are blank. PERSID and LOOKID cannot be "
            "answered from these files.",
        )


if __name__ == "__main__":
    main()
