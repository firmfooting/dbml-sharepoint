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
K1, K2 and K3 depend on K8. Pass 2 leaves the rows K8 decides open and prints
a PASS2 line carrying them with the fixture it read; pass 3 confirms THAT
fixture (the bound list GUID, the fixture ids, the sentinels), then settles the
rows, voids them when K8 fails, or leaves them open when K8 is unanswered. A
404 is an absence only to a site collection administrator.
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
K3 = "access.lookup-acl.expand-reaches-other-columns"
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
      if (u.includes("LookupSource')/fields/getbyinternalnameortitle('ProbeLink')")) {
        return CONFIG.boundStatus === 200
          ? jsonResponse(200, { LookupList: CONFIG.lookupList, LookupField: CONFIG.lookupField })
          : jsonResponse(CONFIG.boundStatus, { error: 'field read failed' });
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
        // The $expand reads answer with the link and whatever `leak` exposes
        // ('none' is the withheld shape); the plain read carries the stored id.
        const row = { Title: 'dbmlsp-probe-source-row', ProbeLinkId: CONFIG.linkId };
        if (u.includes('$expand')) {
          row.ProbeLink = CONFIG.leak === 'none' ? {}
            : CONFIG.leak === 'title' ? { Title: CONFIG.rowTitle }
            : { Title: CONFIG.rowTitle, ProbeSide: CONFIG.rowSide };
        }
        return jsonResponse(200, { value: [row] });
      }
      // The target by GUID: only the list whose GUID is `targetListId` exists.
      const byGuid = /lists\\(guid'([^']+)'\\)/.exec(u);
      if (byGuid) {
        if (byGuid[1].toLowerCase() !== CONFIG.targetListId.toLowerCase()) {
          return jsonResponse(404, { error: 'list does not exist' });
        }
        const item = /\\/items\\((\\d+)\\)/.exec(u);
        if (item) {
          const id = Number(item[1]);
          return CONFIG.targetRowIds.includes(id)
            ? jsonResponse(200, { Id: id, Title: CONFIG.rowTitle, ProbeSide: CONFIG.rowSide })
            : jsonResponse(404, { error: 'item does not exist' });
        }
        if (u.includes('/items?')) {
          return CONFIG.targetStatus === 200
            ? jsonResponse(200, { value: [{ Title: 'secret' }] })
            : jsonResponse(CONFIG.targetStatus, { error: 'target read failed' });
        }
        return CONFIG.ownerTargetStatus === 200
          ? jsonResponse(200, { Id: CONFIG.targetListId, HasUniqueRoleAssignments: CONFIG.unique })
          : jsonResponse(CONFIG.ownerTargetStatus, { error: 'list read failed' });
      }
      // The same target by title, which the probe must not use: a rename answers it 404.
      if (u.includes("LookupTarget')")) {
        return jsonResponse(CONFIG.titleTargetStatus, { error: 'by title' });
      }
      return jsonResponse(404, { error: `unmocked ${u}` });
    };
""")

_TARGET_GUID = "5b0c3a9e-7d41-4f3a-9a52-1c2d3e4f5a6b"

#: The healthy three-pass run on a tenant that HIDES the target: the reader
#: gets 404, the source fixture is linked to target row 1, and the owner, not
#: a site collection administrator, finds afterwards the list the lookup is
#: bound to, with its own permissions and that row in it, sentinels intact. The
#: bound id is braced and the list id is not, so the comparison is on the
#: GUID rather than its spelling.
_HEALTHY: dict[str, Any] = {
    "admin": False,
    "sourceStatus": 200,
    "linkId": 1,
    "targetStatus": 404,
    "ownerTargetStatus": 200,
    "targetListId": _TARGET_GUID,
    "lookupList": "{" + _TARGET_GUID.upper() + "}",
    "unique": True,
    "boundStatus": 200,
    "lookupField": "Title",
    "titleTargetStatus": 404,
    "leak": "none",
    "targetRowIds": [1],
    "rowTitle": "dbmlsp-probe-target-title-should-not-leak",
    "rowSide": "dbmlsp-probe-target-second-column",
}


def _probe_js(mode: str, pass2: dict[str, Any] | None = None) -> str:
    """The committed probe, gates opened, MODE set, result table exposed.

    The file is edited rather than re-rendered, so what runs is what an
    operator pastes.
    """
    js = PROBE.read_text(encoding="utf-8")
    edits = (
        ("  const CONFIRMED = false;", "  const CONFIRMED = true;"),
        ("  const MODE = 'setup';", f"  const MODE = '{mode}';"),
        ("  const PASS2 = null;", f"  const PASS2 = {json.dumps(pass2)};"),
    )
    for old, new in edits:
        assert js.count(old) == 1, f"{old!r} is not spelled as this test expects"
        js = js.replace(old, new)
    dump = "\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n    report();\n"
    exposed = js.replace("\n    report();\n", dump)
    assert exposed != js, "the result table dump did not splice in before report()"
    return exposed


def _run_full(
    mode: str, pass2: dict[str, Any] | None = None, **changes: Any,
) -> tuple[dict[str, dict[str, str]], str]:
    """(rows by id, output) for one pass."""
    config = {**_HEALTHY, **changes}
    script = _HARNESS.replace("__CONFIG__", json.dumps(config)) + "\n" + _probe_js(mode, pass2)
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}, output


def _run_pass(mode: str, pass2: dict[str, Any] | None = None, **changes: Any) -> dict[str, str]:
    rows, _output = _run_full(mode, pass2, **changes)
    return {rid: row["outcome"] for rid, row in rows.items()}


def _printed_pass2(output: str) -> dict[str, Any]:
    """The PASS2 line pass 2 prints for the operator to carry into pass 3."""
    prefix = "const PASS2 = "
    line = next((ln for ln in output.splitlines() if ln.startswith(prefix)), None)
    assert line is not None, f"pass 2 printed no PASS2 line:\n{output[-3000:]}"
    carried: dict[str, Any] = json.loads(line.removeprefix(prefix).removesuffix(";"))
    return carried


#: What healthy pass 2 carries, built by hand so each confirm test can vary one
#: part; `test_pass_2_carries_its_fixture_into_pass_3` pins it to the real line.
_PASS2: dict[str, Any] = {
    "lookupList": _HEALTHY["lookupList"],
    "linkedId": 1,
    "rows": {
        K1: {"outcome": "PASS", "evidence": "hidden", "state": "open", "needs": ["target"]},
        K2: {
            "outcome": "LOOKUP VALUE IS WITHHELD", "evidence": "no sentinel", "state": "open",
            "needs": ["target", "row", "title"],
        },
        K3: {
            "outcome": "DISPLAY FIELD ONLY", "evidence": "title only", "state": "open",
            "needs": ["target", "row", "side"],
        },
    },
}


def _confirm(pass2: dict[str, Any] | None = None, **changes: Any) -> dict[str, str]:
    return _run_pass("confirm", _PASS2 if pass2 is None else pass2, **changes)


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
    rows = _confirm()
    assert rows[K8] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_deleted_between_the_passes_fails_k8() -> None:
    """The case the 404 reading cannot see from the reader's side.

    Read by a site collection administrator, whom the target's ACL does not
    bind, so the 404 is an absence.
    """
    rows = _confirm(admin=True, ownerTargetStatus=404)
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_404_to_an_account_that_is_not_an_administrator_is_not_an_absence() -> None:
    """The denied account running pass 3 by mistake gets exactly this 404.

    So does a Site Owners member whose grant from pass 1 did not take, so
    neither can tell a deleted target from a hidden one.
    """
    rows = _confirm(ownerTargetStatus=404)
    assert rows[K8] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_linked_row_deleted_between_the_passes_fails_k8() -> None:
    rows = _confirm(targetRowIds=[2])
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_rebuilt_under_the_same_title_fails_k8() -> None:
    """Same title and the same item id, but not the list pass 2 read."""
    rows = _confirm(admin=True, targetListId="0f0e0d0c-0b0a-4908-8706-050403020100")
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    "changed",
    [{"rowTitle": "renamed"}, {"rowSide": None}],
    ids=["title", "second-column"],
)
def test_a_linked_row_without_its_sentinels_fails_k8(changed: dict[str, Any]) -> None:
    """K2 and K3 read the absence of these values, so they must still be there."""
    rows = _confirm(**changed)
    assert rows[K8] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_inheritance_restored_after_pass_2_does_not_undo_its_measurement() -> None:
    """Pass 2's 403 or 404 measured the ACL it met; what it is now is reported."""
    rows, _output = _run_full("confirm", _PASS2, unique=False)
    assert rows[K8]["outcome"] == "PASS"
    assert "HasUniqueRoleAssignments=false" in rows[K8]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreadable_owner_read_is_not_recorded_as_either_answer() -> None:
    rows = _confirm(ownerTargetStatus=429)
    assert rows[K8] == "NOT ESTABLISHED"


_NEW_GUID = "0f0e0d0c-0b0a-4908-8706-050403020100"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_pass_2_leaves_what_k8_decides_open_and_pass_3_settles_it() -> None:
    """The whole relay, through the line an operator actually copies.

    `depends_on` voids a row only when its control FAILS, so a pass 3 that
    never ran would otherwise leave pass 2's hidden-target K1 and its K2 and
    K3 standing as settled answers.
    """
    read, output = _run_full("read")
    assert {rid: read[rid]["state"] for rid in (K1, K2, K3)} == {
        K1: "open", K2: "open", K3: "open",
    }
    carried = _printed_pass2(output)
    assert carried["lookupList"] == _HEALTHY["lookupList"]
    assert carried["linkedId"] == 1
    assert carried["rows"][K1]["outcome"] == "PASS"
    assert carried["rows"][K1]["needs"] == ["target"]
    assert carried["rows"][K2]["needs"] == ["target", "row", "title"]

    confirmed, _output = _run_full("confirm", carried)
    assert confirmed[K8]["outcome"] == "PASS"
    assert confirmed[K1]["outcome"] == "PASS"
    assert confirmed[K2]["outcome"] == "LOOKUP VALUE IS WITHHELD"
    assert (confirmed[K1]["state"], confirmed[K2]["state"]) == ("settled", "settled")
    # The mock withholds both fields, so K3 was never answered; confirming the
    # fixture does not turn that into an answer.
    assert confirmed[K3]["outcome"] == read[K3]["outcome"] == "NOT ESTABLISHED"
    assert confirmed[K3]["state"] == "open"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_target_is_settled_by_pass_2_alone() -> None:
    """A 403 needs no existence proof: a missing list answers 404."""
    read, _output = _run_full("read", targetStatus=403)
    assert read[K1]["state"] == "settled"
    assert read[K2]["state"] == "open"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_both_lists_rebuilt_after_pass_2_fail_k8_and_void_its_rows() -> None:
    """A fresh setup is consistent with itself: the lookup is bound to the new
    target and the new target holds the linked row with both sentinels. Only
    the GUID pass 2 saw tells it from the fixture pass 2 read."""
    rows, _output = _run_full(
        "confirm", _PASS2, admin=True, targetListId=_NEW_GUID, lookupList="{" + _NEW_GUID + "}",
    )
    assert rows[K8]["outcome"] == "FAIL"
    assert {rid: rows[rid]["state"] for rid in (K1, K2, K3)} == {
        K1: "void", K2: "void", K3: "void",
    }


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_target_renamed_during_pass_2_is_still_read_by_its_guid() -> None:
    """A title read of a renamed target answers 404 to anyone, which pass 2
    would have taken for a hidden list. The bound GUID reaches it."""
    rows = _run_pass("read", targetStatus=200, titleTargetStatus=404)
    assert rows[K1] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreadable_binding_leaves_k1_unestablished() -> None:
    rows = _run_pass("read", boundStatus=500)
    assert rows[K1] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_lookup_not_showing_title_answers_neither_k2_nor_k3() -> None:
    """The sentinels are Title values: shown through another column, their
    absence measures nothing. Checked in pass 2, while the reads are made."""
    rows = _run_pass("read", lookupField="ProbeSide", targetStatus=403, leak="both")
    assert rows[K1] == "PASS"
    assert (rows[K2], rows[K3]) == ("NOT ESTABLISHED", "NOT ESTABLISHED")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("changed", "voided"),
    [({"rowSide": "edited"}, K3), ({"rowTitle": "edited"}, K2)],
    ids=["probe-side", "title"],
)
def test_a_changed_sentinel_voids_only_the_row_read_against_it(
    changed: dict[str, Any], voided: str,
) -> None:
    """Each absence rested on one sentinel; K1 behind a 404 rests on neither."""
    rows, _output = _run_full("confirm", _PASS2, **changed)
    assert rows[K8]["outcome"] == "FAIL"
    assert {rid: rows[rid]["state"] for rid in (K1, K2, K3)} == {
        K1: "settled", K2: "void" if voided == K2 else "settled",
        K3: "void" if voided == K3 else "settled",
    }


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_confirm_pass_without_pass_2s_line_answers_nothing() -> None:
    rows, _output = _run_full("confirm", None)
    assert rows[K8]["outcome"] == "NOT ESTABLISHED"
    assert rows[K1]["evidence"] == "the run did not reach this question"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unanswered_k8_leaves_pass_2s_rows_open() -> None:
    rows, _output = _run_full("confirm", _PASS2, ownerTargetStatus=429)
    assert rows[K8]["outcome"] == "NOT ESTABLISHED"
    assert {rid: rows[rid]["state"] for rid in (K1, K2, K3)} == {
        K1: "open", K2: "open", K3: "open",
    }


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_leak_seen_after_a_refusal_is_settled_in_pass_2() -> None:
    """The sentinel came back to a reader the ACL provably refused: nothing
    pass 3 can find about the fixture afterwards changes what was seen."""
    read, _output = _run_full("read", targetStatus=403, leak="both")
    assert read[K2]["outcome"] == "LOOKUP VALUE IS VISIBLE"
    assert read[K3]["outcome"] == "OTHER COLUMNS ALSO VISIBLE"
    assert (read[K2]["state"], read[K3]["state"]) == ("settled", "settled")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_absence_after_a_refusal_waits_for_k8() -> None:
    """DISPLAY FIELD ONLY reads the second sentinel's absence."""
    read, _output = _run_full("read", targetStatus=403, leak="title")
    assert read[K3]["outcome"] == "DISPLAY FIELD ONLY"
    assert read[K3]["state"] == "open"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_leak_seen_behind_a_404_still_waits_for_k8() -> None:
    """Behind a 404 the denial itself is pending, so even a sighting is."""
    read, _output = _run_full("read", leak="both")
    assert read[K2]["outcome"] == "LOOKUP VALUE IS VISIBLE"
    assert read[K2]["state"] == "open"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_failed_k8_voids_only_what_pass_2_left_open() -> None:
    """Pass 2 through the printed line, then a fixture edited before pass 3."""
    _read, output = _run_full("read", targetStatus=403, leak="title")
    carried = _printed_pass2(output)
    rows, _output = _run_full("confirm", carried, rowSide="edited")
    assert rows[K8]["outcome"] == "FAIL"
    assert rows[K3]["state"] == "void"
    # K1 (a 403) and K2 (a sighting) were settled by pass 2 and are not re-recorded.
    assert rows[K1]["evidence"] == "the run did not reach this question"
    assert rows[K2]["evidence"] == "the run did not reach this question"


def test_k8_is_a_control_the_probe_applies_per_outcome() -> None:
    """K8 is registered as a control, and deliberately NOT a static dependency.

    `depends_on` voids every outcome of a finding when its control fails, and
    K8 decides only some of them: a 404-derived K1, and a K2 or K3 read from
    an ABSENCE. A leak pass 2 saw after a 403 must survive a fixture edited
    afterwards, so the probe carries each row's state through PASS2 and pass 3
    settles or voids only the rows pass 2 left open.
    """
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    probe = next(p for p in catalog["probes"] if p["file"] == PROBE.name)
    findings = {f["id"]: f["depends_on"] for f in probe["scenarios"][0]["findings"]}
    assert K8 in probe["scenarios"][0]["controls"]
    for finding in (K1, K2, K3):
        assert K8 not in findings[finding], finding
    for dependent in (K2, K3):
        assert K1 in findings[dependent], dependent
