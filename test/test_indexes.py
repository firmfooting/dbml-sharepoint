"""The shared index projection, tested where it is declared.

`generators/_indexes.py` exists so `jsgen` and `report_md` cannot disagree
about which DBML indexes become SharePoint indexed columns, which is the
shape AGENTS.md asks for whenever both sides need the same fact. It had no
test module of its own (#172): it was reached only through whichever
generator happened to call it, so its refusal branch was covered by a CLI
test about something else and its ordering contract by nothing at all.

Ordering is a real contract rather than an incidental one. The deploy sets
indexes in the order this list gives, and SharePoint caps how many a list may
carry, so a projection that reordered silently would change which index is
dropped when a schema goes over the ceiling.
"""

import pytest
from _model import column, table

from dbml_sharepoint.generators._indexes import deployable_index_columns
from dbml_sharepoint.model.parser import TableIndex


def test_a_table_with_no_indexes_projects_nothing() -> None:
    """The common case. Most declared entities carry no DBML index at all."""
    assert deployable_index_columns(table("Risk", "Title")) == []


def test_a_single_column_index_projects_its_column() -> None:
    """The only shape SharePoint accepts, and the only one that survives."""
    assert deployable_index_columns(
        table("Risk", "Title", "Status", indexes=["Status"]),
    ) == ["Status"]


def test_several_indexes_keep_their_declared_order() -> None:
    """The deploy sets them in this order and the platform caps how many a
    list may hold, so reordering here would change which one is lost."""
    assert deployable_index_columns(
        table("Risk", "Status", "Owner", "Due", indexes=["Due", "Status", "Owner"]),
    ) == ["Due", "Status", "Owner"]


def test_the_same_column_indexed_twice_is_projected_twice() -> None:
    """Deduplication is not this function's job, and doing it here would hide
    a duplicate declaration from whatever downstream check should report it."""
    assert deployable_index_columns(
        table("Risk", "Status", indexes=["Status", "Status"]),
    ) == ["Status", "Status"]


def test_a_composite_index_is_refused() -> None:
    """SharePoint has no composite index, so there is no correct projection.
    Failing closed is the alternative to silently indexing the first column
    and deploying something the author did not declare."""
    composite = table(
        "Risk", "Status", "Category",
        indexes=[TableIndex(columns=("Status", "Category"))],
    )
    with pytest.raises(ValueError, match="composite DBML indexes cannot be deployed"):
        deployable_index_columns(composite)


def test_the_composite_refusal_names_the_table() -> None:
    """A build over thirty entities reports one message, so it has to say
    which table to go and fix."""
    composite = table(
        "Assessment", "Status", "Category",
        indexes=[TableIndex(columns=("Status", "Category"))],
    )
    with pytest.raises(ValueError, match=r"^Assessment:"):
        deployable_index_columns(composite)


def test_a_composite_index_is_refused_even_behind_valid_ones() -> None:
    """The loop must not return early with the columns it has already
    collected: a partial projection deploys a subset of what was declared and
    reports success."""
    mixed = table(
        "Risk", "Status", "Category", "Owner",
        indexes=["Owner", TableIndex(columns=("Status", "Category"))],
    )
    with pytest.raises(ValueError, match="composite DBML indexes cannot be deployed"):
        deployable_index_columns(mixed)


def test_a_zero_column_index_is_refused_as_a_composite() -> None:
    """`len(index.columns) != 1` rather than `> 1`, so an index carrying no
    column is refused with the rest instead of projecting nothing."""
    empty = table("Risk", "Status", indexes=[TableIndex(columns=())])
    with pytest.raises(ValueError, match="composite DBML indexes cannot be deployed"):
        deployable_index_columns(empty)


def test_the_projection_reads_names_and_not_column_objects() -> None:
    """Callers compare the result against declared column names, so a
    projection returning anything else would compare false everywhere and
    quietly index nothing."""
    projected = deployable_index_columns(
        table("Risk", column("Status", "varchar"), indexes=["Status"]),
    )
    assert projected == ["Status"]
    assert all(isinstance(name, str) for name in projected)
