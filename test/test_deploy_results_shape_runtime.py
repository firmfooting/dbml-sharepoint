"""An answer without a results array, or without a boolean
HasUniqueRoleAssignments, must stop the read that decides on it (#722)."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
from _node import NODE
from test_deploy_runtime import (
    _ADOPTED_HARNESS,
    _GUARDED_VIEWS,
    _declared_deploy_js,
    _deploy_js,
    _ownership_deploy_js,
    _ownership_harness,
    _run_capturing_calls,
    _summary_of,
    _view_guard_harness,
)

from dbml_sharepoint.analysis.phases import phase_number

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_NO_RESULTS = "delete payload.d.results;"
_NO_FLAG = "delete payload.d.HasUniqueRoleAssignments;"
_NAMED = "answered without a d.results array"


def malformed(
    parts: tuple[str, ...], mutate: str, *, phase: str | None = None, nth: int | None = None,
) -> str:
    """An overlay that rewrites the `nth` GET (every one, if None) whose URL
    holds every part, during `phase` if given, with `mutate` applied to its
    parsed `payload`."""
    phase_check = (
        f"mockPhase !== {json.dumps(phase_number(phase))} ||" if phase else ""
    )
    return f"""
{{
  const shapeFetch = globalThis.fetch;
  let shapeReads = 0;
  globalThis.fetch = async (url, opts = {{}}) => {{
    const response = await shapeFetch(url, opts);
    const u = decodeURIComponent(String(url));
    if ({phase_check} (opts.method || 'GET') !== 'GET'
        || !{json.dumps(list(parts))}.every((p) => u.includes(p))) return response;
    shapeReads += 1;
    if ({json.dumps(nth)} !== null && shapeReads !== {json.dumps(nth)}) return response;
    let payload = await response.json();
    {mutate}
    console.log('SHAPE_INJECTED');
    return {{ ...response, ok: true, status: 200,
      json: async () => payload, text: async () => JSON.stringify(payload) }};
  }};
}}
"""


def _errors(summary: dict[str, Any]) -> list[str]:
    return [str(e.get("error")) for e in summary.get("errors", [])]


def test_a_field_enumeration_without_results_writes_no_field() -> None:
    summary, calls, output = _run_capturing_calls(
        _ADOPTED_HARNESS + malformed(("/fields?",), _NO_RESULTS, phase="preflight"),
        _deploy_js(),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("Field enumeration for" in e and _NAMED in e for e in _errors(summary)), (
        summary.get("errors")
    )
    assert summary.get("aborted"), summary
    assert not [c for c in calls if c["method"] == "POST" and "/fields" in c["url"]]


def test_a_view_enumeration_without_results_creates_no_view(tmp_path: Path) -> None:
    summary, calls, output = _run_capturing_calls(
        _view_guard_harness({"All Items": "editable"})
        + malformed(("/views?",), _NO_RESULTS, phase="views"),
        _declared_deploy_js(tmp_path, _GUARDED_VIEWS),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("View enumeration of" in e and _NAMED in e for e in _errors(summary)), (
        summary.get("errors")
    )
    assert not [
        c for c in calls
        if c["method"] == "POST" and "/views" in c["url"]
        and c.get("phase") == phase_number("views")
    ]


def test_a_view_fields_read_without_results_rewrites_no_view_fields(tmp_path: Path) -> None:
    """The enumeration answers without the expanded fields, so the live read
    decides; read as empty it rewrote every declared column."""
    summary, calls, output = _run_capturing_calls(
        _view_guard_harness({"All Items": "editable"})
        + malformed(
            ("/views?",), "for (const v of payload.d.results) delete v.ViewFields;",
            phase="views",
        )
        + malformed(("/viewfields",), "payload.d = {};", phase="views"),
        _declared_deploy_js(tmp_path, _GUARDED_VIEWS),
    )
    assert output.count("SHAPE_INJECTED") >= 2, output[-4000:]
    assert any("View fields of" in e and _NAMED in e for e in _errors(summary)), (
        summary.get("errors")
    )
    assert not [
        c for c in calls
        if c["method"] == "POST" and "viewfields/" in c["url"].lower()
    ]


def test_an_operator_membership_read_without_results_enrols_nobody() -> None:
    """Read as empty, the operator was added to a group it may already be in,
    and the end of the run then removed a membership it did not grant."""
    js = _deploy_js()
    flag = '"enroll_operator_during_deploy": false'
    assert flag in js
    harness = _ADOPTED_HARNESS.replace(
        "const KNOWN_GROUP_NAMES = [];", 'const KNOWN_GROUP_NAMES = ["List Maintainer"];',
    )
    summary, calls, output = _run_capturing_calls(
        # The mock does not model this read, so the whole answer is supplied.
        harness + malformed(("/users?$filter=Id eq",), "payload = { d: {} };"),
        js.replace(flag, '"enroll_operator_during_deploy": true', 1),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("Membership probe for" in e and _NAMED in e for e in _errors(summary)), (
        summary.get("errors")
    )
    assert summary.get("aborted") == "operator-enrolment-errors", summary
    assert not [
        c for c in calls if c["method"] == "POST" and c["url"].endswith("/users")
    ]


def _ownership_run(
    tmp_path: Path, overlay: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    return _run_capturing_calls(
        _ownership_harness(tmp_path, ("Escalation",)) + overlay,
        _ownership_deploy_js(tmp_path, ("Escalation",)),
    )


@pytest.mark.parametrize("phase", ["lists", "acls"])
@pytest.mark.parametrize("mutate", [_NO_FLAG, "payload.d.HasUniqueRoleAssignments = 'false';"])
def test_an_inheritance_flag_that_is_not_a_boolean_breaks_nothing(
    tmp_path: Path, phase: str, mutate: str,
) -> None:
    """Read as false, a missing flag sent breakroleinheritance to a scope
    whose permissions may already be its own."""
    summary, calls, output = _ownership_run(
        tmp_path, malformed(("?$select=HasUniqueRoleAssignments",), mutate, phase=phase),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("not a boolean" in e for e in _errors(summary)), summary.get("errors")
    assert not [
        c for c in calls
        if "breakroleinheritance" in c["url"] and c.get("phase") == phase_number(phase)
    ]
    assert not [c for c in calls if "removeroleassignment" in c["url"]]


def test_a_descendant_row_without_its_flag_is_not_read_as_inheriting(tmp_path: Path) -> None:
    """Read as false, a row whose flag is missing passed the undeclared-scope guard."""
    row = "{ Id: 41, FileSystemObjectType: 0, FileRef: '/sites/test/stray.docx' }"
    summary, calls, output = _ownership_run(
        tmp_path,
        malformed(
            ("/items?$select=Id,HasUniqueRoleAssignments",),
            f"payload.d.results = [{row}];", phase="acls",
        ),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("Item 41 of" in e and "not a boolean" in e for e in _errors(summary)), (
        summary.get("errors")
    )
    assert not [
        c for c in calls
        if "roleassignment(" in c["url"]
        or ("breakroleinheritance" in c["url"] and c.get("phase") == phase_number("acls"))
    ]


def test_a_library_flag_re_read_that_is_not_a_boolean_writes_no_allowlist(
    tmp_path: Path,
) -> None:
    """The re-read after the break, which a library needs before it settles."""
    from test_deploy_library_runtime import (
        _BROKEN_INHERITANCE,
        _library_deploy_js,
        _library_harness,
        _run_output,
    )
    from test_deploy_library_runtime import _calls_of as library_calls

    output = _run_output(
        # Read 1 is early isolation, 2 the ACL check, 3 the re-read after the ACL break.
        _library_harness(unique_after=3)
        + malformed(("?$select=HasUniqueRoleAssignments",), _NO_FLAG, nth=3),
        _library_deploy_js(tmp_path, _BROKEN_INHERITANCE),
    )
    assert "SHAPE_INJECTED" in output, output[-4000:]
    assert any("not a boolean" in e for e in _errors(_summary_of(output))), output[-4000:]
    calls = library_calls(output)
    assert not [c for c in calls if "addroleassignment" in c["url"]
                or "removeroleassignment" in c["url"]]


def _logging_failures(run: dict[str, Any]) -> list[str]:
    return [json.dumps(f) for f in run["summary"]["loggingFailures"]]


@pytest.mark.parametrize("central", [True, False])
@pytest.mark.parametrize("which", ["deployments", "changes"])
def test_a_logging_field_read_without_results_is_a_recorded_failure(
    central: bool, which: str,
) -> None:
    """Read as empty, the sidecar probe created every stamp column again, and
    the central probe degraded the run as if the columns were missing, with
    nothing recorded."""
    from test_deploy_logging_runtime import (
        _CENTRAL_FIELDS_READ,
        _SIDECAR_FIELDS_READ,
        _run_deploy,
    )

    from dbml_sharepoint.analysis.sidecars import (
        CHANGE_LOG_TITLE,
        EXTERNAL_CHANGE_LOG_DEFAULT,
        EXTERNAL_LOG_DEFAULT,
        RUN_LOG_TITLE,
    )

    if central:
        title = EXTERNAL_LOG_DEFAULT if which == "deployments" else EXTERNAL_CHANGE_LOG_DEFAULT
        read, what = _CENTRAL_FIELDS_READ, "Central field read for"
    else:
        title = RUN_LOG_TITLE if which == "deployments" else CHANGE_LOG_TITLE
        read, what = _SIDECAR_FIELDS_READ, "Field read for"
    run = _run_deploy(
        central_absent=not central,
        overlay=malformed((f"getbytitle('{title}')/fields?", read), _NO_RESULTS),
    )
    assert "SHAPE_INJECTED" in run["output"]
    assert run["unhandled"] == [], "\n".join(run["unhandled"])
    assert any(what in f and _NAMED in f for f in _logging_failures(run)), (
        run["summary"]["loggingFailures"]
    )
    assert not [
        c for c in run["calls"]
        if c["method"] == "POST" and unquote(c["url"]).endswith(f"getbytitle('{title}')/fields")
    ]
    if central and which == "deployments":
        # Unproved columns are not written to: the stamps fall back to Title alone.
        assert not [row for row in run["state"]["central"] if row.get("StampKind")]
    if central and which == "changes":
        assert run["state"]["centralChanges"] == []


@pytest.mark.parametrize("central", [True, False])
def test_a_current_row_read_without_results_writes_no_change_row(central: bool) -> None:
    """Read as empty, the run inserted a second current row beside the one it
    should have closed."""
    from test_deploy_logging_runtime import _run_deploy

    from dbml_sharepoint.analysis.sidecars import CHANGE_LOG_TITLE, EXTERNAL_CHANGE_LOG_DEFAULT

    title = EXTERNAL_CHANGE_LOG_DEFAULT if central else CHANGE_LOG_TITLE
    overlay = malformed((f"getbytitle('{title}')/items", "IsCurrent eq true"), _NO_RESULTS)
    run = (
        _run_deploy(central_can_close=True, seeded_central_rows=True, overlay=overlay)
        if central else
        _run_deploy(seeded_change_rows=True, central_absent=True, overlay=overlay)
    )
    assert "SHAPE_INJECTED" in run["output"]
    assert run["unhandled"] == [], "\n".join(run["unhandled"])
    what = "Central current-row read for" if central else "Current-row read for"
    assert any(what in f and _NAMED in f for f in _logging_failures(run)), (
        run["summary"]["loggingFailures"]
    )
    assert not [
        c for c in run["calls"]
        if c["method"] == "POST" and f"getbytitle('{title}')/items" in unquote(c["url"])
    ]
