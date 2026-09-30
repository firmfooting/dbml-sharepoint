"""Execute the shared scratch-list partial on its own, behind the versions mock.

A probe that applies list settings certifies them by read-back. The settings MERGE's answer is
recorded beside that read-back, so a refused MERGE is shown with its reason in RESULTS and not
only on the console, but it never fails the fixture on its own account.
"""

import importlib.util
import json
import sys
from types import ModuleType
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL
from _versions_mock import VERSIONS_MOCK

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

FIXTURE = "test.scratch.fixture-list"
DEPENDENT = "test.scratch.dependent"
TITLE = "dbmlsp Probe Scratch"
REFUSAL = "The value is out of range at https://example.sharepoint.com/sites/probe."
REFUSED = {"contains": f"getbytitle('{TITLE}')", "verb": "MERGE", "status": 400, "text": REFUSAL}
SAID = "HTTP 400: The value is out of range at [TENANT]/sites/probe."
VERSIONING = "{ EnableVersioning: true }"


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes_scratch", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _claim(
    settings: dict[str, Any] | None, declared: str = "{}", **config: Any,
) -> dict[str, Any]:
    """Claim one scratch list with `settings`, and return what came back and the result rows."""
    env = _load_renderer()._env()
    body = "".join(env.get_template(name).render() for name in (
        "_probe_harness.js.j2", "_probe_raw_request_v1.js.j2", "_probe_identity_v1.js.j2",
        "_probe_scratch_list_v1.js.j2"))
    script = (
        VERSIONS_MOCK.replace("__CONFIG__", json.dumps(config))
        + "(async () => {\n" + body
        + f"  expect('{FIXTURE}', 'the scratch list');\n"
        + f"  expect('{DEPENDENT}', 'a question resting on it');\n"
        + f"  const got = await claimScratchList({{ id: '{FIXTURE}', question: 'the scratch list',"
        + f" title: '{TITLE}', description: 'owned', dependents: ['{DEPENDENT}'],"
        + f" settings: {json.dumps(settings)}, declared: {declared} }});\n"
        + "  console.log('__OUT__' + JSON.stringify({ held: got.held, body: got.body,"
        + " merge: got.merge && got.merge.status, rows: RESULTS }));\n"
        + "})();\n"
    )
    output = run_node(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__OUT__")), None)
    assert line is not None, output[-2000:]
    out: dict[str, Any] = json.loads(line.removeprefix("__OUT__"))
    out["rows"] = {row["id"]: row for row in out["rows"]}
    out["console"] = output.split("__SENT__")[0]
    return out


def test_an_accepted_settings_merge_is_read_back_with_its_status() -> None:
    out = _claim({"EnableVersioning": True}, declared=VERSIONING)

    assert out["held"] is True
    assert out["merge"] == 204
    assert out["rows"][FIXTURE]["outcome"] == "PASS"
    assert 'Settings="HTTP 204"' in out["rows"][FIXTURE]["evidence"]
    # The body handed on is the site's read-back; the MERGE's answer is evidence only.
    assert "Settings" not in out["body"]


def test_a_refused_merge_alone_is_recorded_and_the_fixture_still_holds() -> None:
    # Nothing is declared from the settings, so the MERGE's answer is the only thing that differs.
    out = _claim({"EnableVersioning": True}, rules=[REFUSED])

    evidence = out["rows"][FIXTURE]["evidence"]
    assert out["held"] is True
    assert out["merge"] == 400
    assert out["rows"][FIXTURE]["outcome"] == "PASS"
    assert SAID in evidence
    assert "example.sharepoint.com" not in evidence
    assert out["rows"][DEPENDENT]["state"] == "open"


def test_a_refused_merge_that_leaves_a_setting_unapplied_fails_on_that_setting() -> None:
    out = _claim({"EnableVersioning": True}, declared=VERSIONING, rules=[REFUSED])

    evidence = out["rows"][FIXTURE]["evidence"]
    assert out["held"] is False
    assert out["rows"][FIXTURE]["outcome"] == "FAIL"
    assert "EnableVersioning differs" in evidence
    assert "Settings differs" not in evidence
    assert SAID in evidence
    assert "example.sharepoint.com" not in evidence
    assert out["rows"][DEPENDENT]["state"] == "void"


def test_a_refused_merge_naming_an_account_is_masked() -> None:
    naming = {**REFUSED,
              "text": "Refused for i:0#.f|membership|ada@example.com by bob@example.com."}
    out = _claim({"EnableVersioning": True}, rules=[naming])

    evidence = out["rows"][FIXTURE]["evidence"]
    assert "HTTP 400: Refused for i:0#.f|membership|<account> by <account>" in evidence
    assert "ada@example.com" not in out["console"]
    assert "bob@example.com" not in out["console"]


def test_a_list_claimed_without_settings_declares_no_merge() -> None:
    out = _claim(None)

    assert out["held"] is True
    assert out["merge"] is None
    assert "Settings" not in out["rows"][FIXTURE]["evidence"]
