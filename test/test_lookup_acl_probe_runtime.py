# test/test_lookup_acl_probe_runtime.py
"""Execute `lookup-acl-probe.js` against a mock SharePoint, per pass.

The probe's K1 control decides whether the denied reader's run means
anything. On 2026-09-19 a tenant hid the ACL-denied target behind HTTP 404
rather than refusing it with 403, and K1, which accepted only 401 and 403,
recorded NOT ESTABLISHED on a run where the ACL was working (#592).

A 404 is also what a DELETED target answers, and from the denied account the
two cannot be told apart. Accepting it therefore needs two things the tests
below hold the probe to: pass 2 takes it only with the linked source fixture
in hand, and pass 3, run by the owner afterwards, confirms the target was
still there (K8, `control-target-present-after-read`). The catalogue makes
K2 and K3 depend on K8, so a missing or failed pass 3 voids them.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run
from _paths import MANUAL

PROBE = MANUAL / "lookup-acl-probe.js"

K1 = "access.lookup-acl.control-target-denied"
K2 = "access.lookup-acl.display-value-to-denied-reader"
K4 = "access.lookup-acl.control-source-readable"
K8 = "access.lookup-acl.control-target-present-after-read"

_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      location: { origin: 'https://example.sharepoint.com' },
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
        webServerRelativeUrl: '/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    globalThis.fetch = async (url) => {
      const u = decodeURIComponent(String(url));
      if (u.includes('/contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.includes('web/currentuser')) {
        return jsonResponse(200, {
          Title: 'Reader', LoginName: 'i:0#.f|membership|reader@example.com',
          IsSiteAdmin: CONFIG.admin,
        });
      }
      if (u.includes("LookupSource')/items")) {
        if (CONFIG.sourceStatus !== 200) {
          return jsonResponse(CONFIG.sourceStatus, { error: 'source read failed' });
        }
        // The $expand reads answer with the link but no target values, which
        // is the withheld shape; the plain read carries the stored id.
        const row = { Title: 'dbmlsp-probe-source-row', ProbeLinkId: CONFIG.linkId };
        if (u.includes('$expand')) row.ProbeLink = {};
        return jsonResponse(200, { value: [row] });
      }
      if (u.includes("LookupTarget')/items(")) {
        const id = Number(/items\\((\\d+)\\)/.exec(u)[1]);
        return CONFIG.targetRowIds.includes(id)
          ? jsonResponse(200, { Id: id, Title: 'row' })
          : jsonResponse(404, { error: 'item does not exist' });
      }
      if (u.includes("LookupTarget')/items")) {
        return CONFIG.targetStatus === 200
          ? jsonResponse(200, { value: [{ Title: 'secret' }] })
          : jsonResponse(CONFIG.targetStatus, { error: 'target read failed' });
      }
      if (u.includes("LookupTarget')?")) {
        return CONFIG.ownerTargetStatus === 200
          ? jsonResponse(200, { Id: 'list-1', HasUniqueRoleAssignments: CONFIG.unique })
          : jsonResponse(CONFIG.ownerTargetStatus, { error: 'list does not exist' });
      }
      return jsonResponse(404, { error: `unmocked ${u}` });
    };
""")

#: The healthy three-pass run on a tenant that HIDES the target: the reader
#: gets 404, the source fixture is linked to target row 1, and the owner finds
#: the target afterwards with its own permissions and that row in it.
_HEALTHY: dict[str, Any] = {
    "admin": False,
    "sourceStatus": 200,
    "linkId": 1,
    "targetStatus": 404,
    "ownerTargetStatus": 200,
    "unique": True,
    "targetRowIds": [1],
}


def _probe_js(mode: str) -> str:
    """The committed probe, gates opened, MODE set, result table exposed.

    The file is edited rather than re-rendered, so what runs is what an
    operator pastes.
    """
    js = PROBE.read_text(encoding="utf-8")
    edits = (
        ("  const CONFIRMED = false;", "  const CONFIRMED = true;"),
        ("  const MODE = 'setup';", f"  const MODE = '{mode}';"),
    )
    for old, new in edits:
        assert js.count(old) == 1, f"{old!r} is not spelled as this test expects"
        js = js.replace(old, new)
    dump = "\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n    report();\n"
    exposed = js.replace("\n    report();\n", dump)
    assert exposed != js, "the result table dump did not splice in before report()"
    return exposed


def _run_pass(mode: str, **changes: Any) -> dict[str, str]:
    config = {**_HEALTHY, **changes}
    script = _HARNESS.replace("__CONFIG__", json.dumps(config)) + "\n" + _probe_js(mode)
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row["outcome"] for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_target_passes_k1_and_lets_k2_run() -> None:
    """The control for the tests below: the 403 shape K1 always accepted.

    Without it, a change that stopped K2 from ever running would pass every
    test in this file that expects K2 to stay unestablished.
    """
    rows = _run_pass("read", targetStatus=403)
    assert rows[K1] == "PASS"
    assert rows[K4] == "PASS"
    assert rows[K2] == "LOOKUP VALUE IS WITHHELD"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_hidden_target_with_the_linked_fixture_passes_k1() -> None:
    rows = _run_pass("read")
    assert rows[K1] == "PASS"
    assert rows[K2] == "LOOKUP VALUE IS WITHHELD"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_404_without_the_linked_fixture_is_not_read_as_a_denial() -> None:
    """Nothing the reader can see then shows the target ever existed."""
    rows = _run_pass("read", linkId=None)
    assert rows[K1] == "NOT ESTABLISHED"
    assert rows[K2] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_server_error_on_the_target_is_still_not_a_denial() -> None:
    rows = _run_pass("read", targetStatus=500)
    assert rows[K1] == "NOT ESTABLISHED"
    assert rows[K2] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_owner_confirms_a_target_that_is_still_there() -> None:
    rows = _run_pass("confirm")
    assert rows[K8] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_deleted_between_the_passes_fails_k8() -> None:
    """The case the 404 reading cannot see from the reader's side."""
    rows = _run_pass("confirm", ownerTargetStatus=404)
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_rebuilt_between_the_passes_fails_k8() -> None:
    """Same title, but not the row the source fixture links to."""
    rows = _run_pass("confirm", targetRowIds=[2])
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_whose_inheritance_was_restored_fails_k8() -> None:
    rows = _run_pass("confirm", unique=False)
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreadable_owner_read_is_not_recorded_as_either_answer() -> None:
    rows = _run_pass("confirm", ownerTargetStatus=429)
    assert rows[K8] == "NOT ESTABLISHED"


def test_k2_and_k3_depend_on_the_owner_confirmation() -> None:
    """The catalogue edge is what voids K2 and K3 when pass 3 is missing."""
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    probe = next(p for p in catalog["probes"] if p["file"] == PROBE.name)
    findings = {f["id"]: f["depends_on"] for f in probe["scenarios"][0]["findings"]}
    assert K8 in probe["scenarios"][0]["controls"]
    for dependent in (K2, "access.lookup-acl.expand-reaches-other-columns"):
        assert K8 in findings[dependent], dependent
