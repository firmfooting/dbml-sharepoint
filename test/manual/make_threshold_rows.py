# test/manual/make_threshold_rows.py
"""Write the split CSVs the threshold index probe's fixture is loaded from.

Run me AFTER the probe's first paste, which prints the two ids needed here:

    .venv/Scripts/python.exe test/manual/make_threshold_rows.py \
        --owner-id 7 --parent-id 1

Row data lives in Python rather than in the probe because the experiment's
validity rests on knowing EXACTLY how many rows each filter matches. A query
that returns fewer rows than expected is a finding only if the expected number
is known, and known-ness comes from the tests in test/test_threshold_rows.py.
A browser-generated file cannot have any.

MATCHED SELECTIVITY IS THE WHOLE DESIGN. Every filtered column matches exactly
MATCHING_ROWS rows, on offsets chosen to be pairwise disjoint. So:

    Bucket eq 'Z'      indexed Text     60 rows
    Shadow eq 'Z'      UNindexed Text   60 rows, byte-identical data
    ClosedAt eq null   indexed DateTime 60 rows
    OwnerId eq <id>    indexed Person   60 rows
    ParentId eq <id>   indexed Lookup   60 rows

Each of those differs from the first in exactly one respect (the index, the
operator, or the field type), so a divergence has one candidate explanation
instead of three. An earlier draft had these at 60, 60, 1200, 1500 and 6000
rows, which would have made "comparison served, null test refused"
uninterpretable: the two queries differed in result size by twenty times as
well as in operator. The 6000-row Lookup case was worse still, matching the
entire list, so it would have breached the threshold on result size alone and
produced a false corroboration of Microsoft's documented Lookup rule.

Selecting only 60 of 6000 rows also tests the BEST case for an index, which is
the right way round for this question: if a highly selective indexed null test
still cannot be served, that is decisive, whereas a failure at low selectivity
would be ambiguous with selectivity itself.

BLANK CELLS AND TYPED COLUMNS. Three columns are blank on the rows outside
their population: ClosedAt on 60, OwnerId and ParentId on 5940 each. That is
the design. A filter matching every row would breach the threshold on
result-set size alone and prove nothing about indexing.

None of the three is a string column, and SharePoint refuses "" for a DateTime,
a Person id or a Lookup id alike. A CSV cannot express null, so a blank cell
arrives as the empty string and the item is rejected (silently, batch creation
being non-transactional). This cost a real load: ten rows vanished from a
thousand, exactly the ClosedAt population, because that column was left out of
a hand-written list of the ones needing conversion.

So the list is no longer hand-written. NULLABLE_COLUMNS below is the single
source of truth, main() prints the flow expression for each, and a test asserts
it holds exactly the columns that are ever blank, in both directions, so a
column added to one and not the other fails rather than silently loading short.

The JSON files written alongside the CSVs avoid the problem entirely: they carry
real nulls and real integers, so a flow can pass them straight to the batch body
with no conversion at all. Prefer them if your flow can read JSON.
"""

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

TOTAL = 6000

# One clean baseline below the ~2500 auto-index trigger, one past it, then
# tight either side of 5000 because Microsoft documents the effective
# threshold as variable ("not always 5,000").
CHECKPOINTS: tuple[int, ...] = (1000, 3000, 4900, 5100, 6000)

# SharePoint INTERNAL column names, in CSV column order. The Power Automate
# batch-create pattern maps headers straight through to the request body, so
# Person and Lookup columns must appear with the `Id` suffix the REST API
# expects. `Owner` and `Parent` would be silently ignored.
#
# Order matches the insertion order in build_rows() so the two can be read
# against each other without a diff.
HEADERS: tuple[str, ...] = (
    "Title", "Bucket", "Shadow", "ClosedAt", "SortBait", "OwnerId", "ParentId",
)

# Columns that are sometimes blank and are NOT strings, mapped to the SharePoint
# type that rejects "". The single source of truth for what a flow has to
# convert, and for what the JSON writer emits as null rather than "".
#
# `int` marks a column whose JSON value must be a NUMBER, not a quoted digit
# string: a Person or Lookup id. ClosedAt stays a string when present, because
# an ISO-8601 datetime is a string in JSON.
NULLABLE_COLUMNS: dict[str, str] = {
    "ClosedAt": "DateTime",
    "OwnerId": "int",
    "ParentId": "int",
}

_BUCKETS: tuple[str, ...] = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")

# The value every comparison filter asks for.
RARE_BUCKET = "Z"

# Every filtered population is one row in each hundred, so they are all this
# size and all equally selective. For the default TOTAL only; write_csvs
# refuses a row count that does not match the run plan.
MATCHING_ROWS = TOTAL // 100

# Distinct residues mod 100, which is what makes the five populations pairwise
# disjoint. No row is both a `Z` and a blank `ClosedAt`, so no result can be
# read as a consequence of another. Change one of these and the disjointness
# test in test_threshold_rows.py fails, which is the point of it.
_Z_OFFSET = 3
_NULL_OFFSET = 23
_OWNER_OFFSET = 43
_PARENT_OFFSET = 63

_EPOCH = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)

_DEFAULT_OUT = Path(__file__).parent / "rows"


def _one_in_a_hundred(row: int, offset: int) -> bool:
    """Whether this row is in the population at `offset`."""
    return row % 100 == offset


def bucket_for(row: int) -> str:
    """`Z` on one row in a hundred, else the B1-B7 cycle.

    The substitution OVERRIDES the cycle rather than extending it, so the
    seven common values are not evenly sized. Deliberate and harmless: the
    filters only ever ask for `Z`.
    """
    if _one_in_a_hundred(row, _Z_OFFSET):
        return RARE_BUCKET
    return _BUCKETS[(row - 1) % len(_BUCKETS)]


def closed_at_for(row: int) -> str:
    """Blank on one row in a hundred, the null-test population.

    Non-blank values repeat (`row % 1000`), so this column supports `eq null`
    and nothing else. Range filters over it have no expected count and are out
    of scope for this fixture.
    """
    if _one_in_a_hundred(row, _NULL_OFFSET):
        return ""
    stamp = _EPOCH + dt.timedelta(days=row % 1000)
    # SharePoint REST wants ISO-8601 UTC with a `Z`, not the `+00:00` that
    # isoformat() emits for an aware datetime. Pinned by a test, because a
    # rejected value would only surface as silent per-item batch failures.
    return stamp.isoformat().replace("+00:00", "Z")


def sort_bait_for(row: int) -> str:
    """High-cardinality and deliberately out of order, so sorting on it costs
    SharePoint real work.

    A multiplicative hash, NOT random and NOT `hash()`: the files must be
    byte-identical across separate interpreter runs, or regenerating mid-run
    leaves the list holding a mixture and the sort observation is void.
    435761 is coprime to 1e6, so the leading half alone is injective for every
    row below a million. The `-{row}` suffix is for readability, not
    uniqueness.
    """
    return f"{(row * 2654435761) % 1_000_000:06d}-{row:06d}"


def build_rows(
    total: int = TOTAL, owner_id: str = "", parent_id: str = "",
) -> list[dict[str, str]]:
    """One dict per row, keyed by the CSV headers."""
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
            "OwnerId": owner_id if _one_in_a_hundred(row, _OWNER_OFFSET) else "",
            "ParentId": parent_id if _one_in_a_hundred(row, _PARENT_OFFSET) else "",
        })
    return rows


def split_plan(
    checkpoints: tuple[int, ...] = CHECKPOINTS,
) -> list[tuple[int, int, int]]:
    """`(sequence, first row, last row)` per file, one file per checkpoint.

    Split to match the RUN PLAN rather than the batch size. SharePoint's batch
    API takes up to a thousand operations per request and the flow chunks
    internally, so file boundaries are free to mean something else (here,
    "load this and the list is at the next checkpoint").
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


def as_json_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """The same rows with real nulls and real integers.

    A blank cell becomes null, and an id becomes a number rather than a quoted
    digit string. This is the shape a batch-create body wants, so a flow reading
    these needs no per-column conversion, which is the whole point, the
    conversions having already eaten one load.
    """
    typed: list[dict[str, object]] = []
    for row in rows:
        item: dict[str, object] = {}
        for column, value in row.items():
            if value == "" and column in NULLABLE_COLUMNS:
                item[column] = None
            elif value != "" and NULLABLE_COLUMNS.get(column) == "int":
                item[column] = int(value)
            else:
                item[column] = value
        typed.append(item)
    return typed


def write_csvs(rows: list[dict[str, str]], out_dir: Path) -> list[Path]:
    """Write one CSV per checkpoint. Returns what was written, in load order."""
    plan = split_plan()
    expected = plan[-1][2]
    if len(rows) != expected:
        # Silently writing header-only tail files, or dropping the overflow,
        # would hand the operator a directory that looks like a complete run
        # plan and is not.
        raise ValueError(
            f"got {len(rows)} row(s) but the run plan needs exactly {expected}; "
            f"the split would be short or truncated.",
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    # A shortened run plan would otherwise leave the previous plan's tail files
    # sitting beside the new ones, loadable and indistinguishable.
    for pattern in ("threshold-rows-*.csv", "threshold-rows-*.json"):
        for stale in out_dir.glob(pattern):
            stale.unlink()
    written: list[Path] = []
    for sequence, first, last in plan:
        target = out_dir / file_name(sequence, last)
        # The JSON sibling, with real nulls, for a flow that can read it.
        json_target = target.with_suffix(".json")
        json_target.write_text(
            json.dumps(as_json_rows(rows[first - 1:last]), indent=1),
            encoding="utf-8", newline="\n",
        )
        # Write beside, then rename. An interrupted write would otherwise leave
        # a syntactically valid CSV with fewer rows than it claims, and the
        # only signal would be a missing line of output.
        staging = target.with_name(target.name + ".tmp")
        # newline="" stops the OS translating what csv writes, so a terminator
        # cannot be doubled into \r\r\n. It does NOT decide the terminator.
        # csv.writer defaults to \r\n on every platform, which is the part an
        # earlier version of this comment got wrong and paid for.
        #
        # lineterminator="\n" because Power Automate split rows on LF and got a
        # bare CR as the value of the LAST column. That was ParentId, a Lookup
        # id, so SharePoint received "\r" and refused the item (silently, batch
        # creation being non-transactional). A trailing CR is invisible in a
        # spreadsheet and fatal to a typed field.
        with staging.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(HEADERS),
                                    lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows[first - 1:last])
        staging.replace(target)
        written.append(target)
    return written


def _site_id(value: str, label: str) -> str:
    """A SharePoint item or user id, or "" for not-supplied.

    Validated because a login claim or a stray character pasted out of the
    console produces a well-formed CSV that SharePoint rejects per item, and
    batch creation is non-transactional, so those rejections are silent.
    """
    if not value:
        return ""
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{label} must be a whole number, got {value!r}") from None
    if number < 1:
        # 0 is truthy as a string and would sail past a plain falsiness check.
        return ""
    return str(number)


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

    owner_id = _site_id(args.owner_id, "--owner-id")
    parent_id = _site_id(args.parent_id, "--parent-id")

    rows = build_rows(owner_id=owner_id, parent_id=parent_id)
    for path in write_csvs(rows, args.out):
        with path.open(encoding="utf-8", newline="") as handle:
            written_rows = sum(1 for _ in csv.DictReader(handle))
        print(f"wrote {path} ({written_rows} rows)")
    if not owner_id or not parent_id:
        # Not an error: generating without a tenant is useful. But the two
        # columns will be empty, and the Person and Lookup questions then have
        # no data to answer from. Say so rather than let a run report them
        # NOT ESTABLISHED for a reason nobody remembers.
        print(
            "WARNING: --owner-id and/or --parent-id were not supplied (or were "
            "not positive), so the Person and Lookup columns are blank. PERSID "
            "and LOOKID cannot be answered from these files.",
        )
    # Derived, never hand-listed. A hand-written list of the columns needing
    # conversion omitted ClosedAt, and ten rows silently failed to load.
    print()
    print("The .json files carry real nulls — point your flow at those and no")
    print("conversion is needed. If you load the .csv files instead, every one")
    print("of these columns arrives as \"\" when blank and SharePoint rejects it:")
    for column, kind in NULLABLE_COLUMNS.items():
        cast = "int(" if kind == "int" else ""
        close = ")" if kind == "int" else ""
        print(f"    {column:9} ({kind:8})  "
              f"if(empty(item()?['{column}']), null, {cast}item()?['{column}']{close})")


if __name__ == "__main__":
    main()
