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

import datetime as dt

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
