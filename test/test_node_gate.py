# test/test_node_gate.py
"""The gate that stops CI reporting green with the runtime tests skipped.

`test_*_runtime.py` executes every emitted script against a mock web, which
is the only thing that proves the scripts RUN rather than merely that they
have not changed. Each of those modules skips itself when node is absent.
That is right locally and wrong on a runner, because a skip is green: an
image that stopped shipping node would retire the whole executed-script
suite without turning anything red.

These tests make the refusal fire. Without one the guard is a comment.
"""

import conftest
import pytest


def test_a_ci_run_without_node_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression. 262 skip sites across 20 modules rest on this."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("_node.NODE", None)
    with pytest.raises(pytest.UsageError) as refusal:
        conftest.pytest_collection_modifyitems(None, None, [])  # type: ignore[arg-type]
    message = str(refusal.value)
    # The operator has to be told what to do about it, not just that it broke.
    assert "node is not on PATH" in message
    assert "actions/setup-node" in message


def test_a_ci_run_with_node_present_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must not fail a runner that has what it asked for."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("_node.NODE", "/usr/bin/node")
    conftest.pytest_collection_modifyitems(None, None, [])  # type: ignore[arg-type]


def test_a_local_run_without_node_still_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """The skip stays a local convenience.

    Node is not a dependency of the package, so a contributor without it gets
    a skip rather than a wall. Hard-failing everywhere would have closed the
    CI hole by breaking the machine of everybody who does not deploy.
    """
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("_node.NODE", None)
    conftest.pytest_collection_modifyitems(None, None, [])  # type: ignore[arg-type]


def test_the_requirement_is_keyed_on_ci_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keyed on CI, the way the hypothesis profile in conftest already is.

    Every CI provider sets it and a contributor never does, so no flag of our
    own has to be remembered by a workflow that does not exist yet.
    """
    monkeypatch.delenv("CI", raising=False)
    assert conftest.node_is_required() is False
    monkeypatch.setenv("CI", "true")
    assert conftest.node_is_required() is True


def test_the_workflow_pins_node_for_the_job_that_runs_them() -> None:
    """The other half: the gate refuses, and the workflow supplies.

    A refusal alone would turn the hole into a red run rather than a working
    one. The `test` job already ran `node --check` twice while declaring no
    node at all, so it depended on the runner image; `markdown` and `docs`
    both pinned one.
    """
    from _paths import REPO_ROOT

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    test_job = workflow[workflow.index("\n  test:"):workflow.index("\n  mutate-limits:")]
    assert "actions/setup-node" in test_job, (
        "the job that runs the runtime tests does not install node"
    )
    assert "node-version: 24" in test_job, "node is installed but not pinned"
