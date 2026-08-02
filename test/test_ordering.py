# test/test_ordering.py


from _paths import FIXTURES

from dbml_sharepoint.analysis.ordering import compute_phases
from dbml_sharepoint.model.parser import parse_dbml


def test_simple_orders_lookups_after_targets() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    plan = compute_phases(schema)
    # Project has no lookups; Task has one to Project.
    project_idx = plan.list_creation_order.index("Project")
    task_idx = plan.list_creation_order.index("Task")
    assert project_idx < task_idx
    # Task's Project lookup is in pass 1 (target already created).
    assert ("Task", "Project") not in plan.phase2_lookups


def test_self_reference_goes_to_phase2() -> None:
    schema = parse_dbml(FIXTURES / "self-ref.dbml")
    plan = compute_phases(schema)
    assert plan.list_creation_order == ["Node"]
    assert ("Node", "Parent") in plan.phase2_lookups


def test_circular_dependency_goes_to_phase2_for_one_side() -> None:
    schema = parse_dbml(FIXTURES / "circular.dbml")
    plan = compute_phases(schema)
    # Both lists must be created; one side's lookup deferred to phase 2.
    assert set(plan.list_creation_order) == {"A", "B"}
    deferred = {(t, c) for (t, c) in plan.phase2_lookups}
    assert deferred & {("A", "BRef"), ("B", "ARef")}


def test_circular_with_multiple_lookups_defers_all_matching_columns() -> None:
    """Regression: when an earlier-placed table has more than one lookup to
    a later-placed table inside a cycle, EVERY matching column must be
    deferred to phase 2 — not just the first one.

    Fixture circular-multi.dbml: A has BRef1 and BRef2 → B; B has ARef → A.
    Whichever side the topo sort places first, ALL its lookups to the other
    side must end up in phase2_lookups.
    """
    schema = parse_dbml(FIXTURES / "circular-multi.dbml")
    plan = compute_phases(schema)
    deferred = {(t, c) for (t, c) in plan.phase2_lookups}

    a_idx = plan.list_creation_order.index("A")
    b_idx = plan.list_creation_order.index("B")
    if a_idx < b_idx:
        # A placed first → both A→B lookups deferred.
        assert ("A", "BRef1") in deferred
        assert ("A", "BRef2") in deferred
    else:
        # B placed first → B→A lookup deferred.
        assert ("B", "ARef") in deferred
