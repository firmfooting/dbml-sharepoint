# test/test_identify_runtime.py
"""Execute the generated identify.js against a mock SharePoint web.

A static read of the script proves only what it says. Running it proves what
it asks the site for and what it makes of the answers: which objects it calls
this tool's, which family it files them under, and that it spends one column
read per owned list rather than one per list on the web.

Every marker in the fixture is built by `provenance.marker_for_object`, the
same function the deploy writes them with. A grammar change therefore breaks
these tests rather than quietly producing a script that recognises nothing.

Node is required; the tests skip without it rather than failing, since it is
not a dependency of the package.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run

from dbml_sharepoint.analysis import sidecars
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX, SCRATCH_KIND, marker_for_object
from dbml_sharepoint.generators.identifygen import (
    PAYLOAD_FORMAT,
    PAYLOAD_VERSION,
    generate_identify_js,
)

GENERATED_AT = "2026-09-06T12:00:00+00:00"
WEB = "/sites/test"

FAMILY = "programme-governance"
OTHER_FAMILY = "risk-register"

RISK_ID = "aaaaaaaa-0000-0000-0000-000000000001"
ACTION_ID = "aaaaaaaa-0000-0000-0000-000000000002"
PROJECT_ID = "aaaaaaaa-0000-0000-0000-000000000003"
RUN_LOG_ID = "aaaaaaaa-0000-0000-0000-000000000004"
CHANGE_LOG_ID = "aaaaaaaa-0000-0000-0000-000000000005"
DOCS_ID = "aaaaaaaa-0000-0000-0000-000000000006"
DECOY_ID = "aaaaaaaa-0000-0000-0000-000000000007"
OLD_RUN_LOG_ID = "aaaaaaaa-0000-0000-0000-000000000008"
OLD_CHANGE_LOG_ID = "aaaaaaaa-0000-0000-0000-000000000009"

_HARNESS = textwrap.dedent(r"""
    const CONFIG = {};
    const FLAGS = {};
    const calls = [];
    const tables = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: CONFIG.web,
      userLoginName: 'operator@example.com',
      userId: 1,
    };
    console.table = (rows) => { tables.push(rows); };
    globalThis.Blob = globalThis.Blob || function Blob() {};
    URL.createObjectURL = () => 'blob:mock';
    URL.revokeObjectURL = () => {};
    globalThis.document = {
      createElement: () => ({ click() {}, remove() {} }),
      body: { appendChild() {} },
    };

    const reply = (status, payload) => ({
      ok: status < 400,
      status,
      url: '',
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const results = (rows) => reply(200, { d: { results: rows } });
    const refused = (what) => reply(403, { error: { message: { value: `${what} refused` } } });

    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      calls.push({ url: u, method: (opts && opts.method) || 'GET' });

      if (/web\?\$select=/.test(u)) return reply(200, { d: CONFIG.web_facts });

      if (u.includes('web/lists?$select=')) {
        if (FLAGS.listsRefused) return refused('lists');
        return results(CONFIG.lists);
      }
      if (u.includes('web/sitegroups')) {
        if (FLAGS.groupsRefused) return refused('groups');
        return results(CONFIG.groups);
      }
      if (u.includes('web/roledefinitions')) return results(CONFIG.levels);

      const byGuid = /web\/lists\(guid'([^']+)'\)/.exec(u);
      if (byGuid) {
        const guid = byGuid[1].toLowerCase();
        if (u.includes('/fields')) return results(CONFIG.fields[guid] || []);
        if (u.includes('/items')) return results(CONFIG.items[guid] || []);
      }
      return reply(400, { error: { message: { value: `unmocked ${u}` } } });
    };
""")


def _list(
    title: str,
    list_id: str,
    *,
    description: str = "",
    items: int = 0,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "Title": title,
        "Id": list_id,
        "Description": description,
        "ItemCount": items,
        "Hidden": hidden,
        "BaseTemplate": 100,
        "Created": "2026-09-01T00:00:00Z",
        "LastItemUserModifiedDate": "2026-09-04T00:00:00Z",
        "RootFolder": {"ServerRelativeUrl": f"{WEB}/Lists/{title.replace(' ', '')}"},
    }


def _field(
    internal: str,
    kind: str = "Text",
    *,
    built_in: bool = False,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "InternalName": internal,
        "Title": internal,
        "TypeAsString": kind,
        "Required": False,
        "Indexed": False,
        "Hidden": hidden,
        "ReadOnlyField": False,
        "FromBaseType": built_in,
        "Sealed": False,
    }


def _config() -> dict[str, Any]:
    """A site carrying two families, both log sidecars, and three lists this
    tool does not own.

    The decoy's description mentions the tool by name without completing the
    grammar. It is the case an anchored or prefix-only match gets wrong, and
    the reason the marker is prefix-free.
    """
    return {
        "web": WEB,
        "web_facts": {
            "Title": "Programme Site",
            "Id": "eeeeeeee-0000-0000-0000-00000000000f",
            "Created": "2026-01-01T00:00:00Z",
            "Language": 1033,
            "WebTemplate": "STS",
            "ServerRelativeUrl": WEB,
        },
        "lists": [
            _list("GOV_Risk", RISK_ID, items=42, description=marker_for_object(
                kind="list", name="GOV_Risk", family=FAMILY)),
            _list("GOV_Action", ACTION_ID, items=7, description=(
                "The actions register. "
                + marker_for_object(kind="list", name="GOV_Action", family=FAMILY)
                + " Do not delete."
            )),
            _list("RG_Project", PROJECT_ID, items=3, description=marker_for_object(
                kind="list", name="RG_Project", family=OTHER_FAMILY)),
            _list(sidecars.RUN_LOG_TITLE, RUN_LOG_ID, items=2, hidden=True,
                  description=sidecars.run_log_marker()),
            _list(sidecars.CHANGE_LOG_TITLE, CHANGE_LOG_ID, items=19, hidden=True,
                  description=sidecars.change_log_marker()),
            _list("Documents", DOCS_ID, items=5),
            _list("Notes", DECOY_ID, items=1, description=(
                f"Hand-made. Looks like something {MARKER_PREFIX} would leave behind."
            )),
        ],
        "fields": {
            RISK_ID: [
                _field("Title", built_in=True),
                _field("ResidualRating", "Choice"),
                _field("LastReviewedDate", "DateTime"),
                _field("_Internal", hidden=True),
            ],
            ACTION_ID: [_field("DueDate", "DateTime")],
            PROJECT_ID: [_field("ProjectCode")],
            RUN_LOG_ID: [_field("StampKind")],
            CHANGE_LOG_ID: [_field("ChangeKey")],
        },
        "items": {
            RUN_LOG_ID: [
                {
                    "Id": 2, "Title": "deployment stop",
                    "StampKind": "stop", "StampUtc": "2026-09-04T02:10:00Z",
                    "SourceSite": WEB, "ReleaseTag": "2.1.0",
                    "SchemaVersion": "2.1.0", "Operator": "operator@example.com",
                    "Details": "",
                },
                {"Id": 1, "Title": "deployment start", "StampKind": "start"},
            ],
        },
        "groups": [
            {"Id": 11, "Title": "GOV Programme Leads", "Description": marker_for_object(
                kind="group", name="GOV Programme Leads", family=FAMILY)},
            {"Id": 12, "Title": "dbml Enterprise Readers", "Description": marker_for_object(
                kind="group", name="dbml Enterprise Readers", family=None)},
            {"Id": 13, "Title": "Site Owners", "Description": "Built in."},
        ],
        "levels": [
            {"Id": 21, "Name": "GOV Submit Only", "Description": marker_for_object(
                kind="level", name="GOV Submit Only", family=FAMILY)},
            {"Id": 22, "Name": "Full Control", "Description": "Has full control."},
        ],
    }


Run = tuple[dict[str, Any], list[dict[str, Any]], list[Any], str]


def _run_script(
    config: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
) -> Run:
    """Run the emitted script against the mock and return what came back."""
    body = generate_identify_js(generated_at=GENERATED_AT).rstrip()
    assert body.endswith("})();")
    harness = _HARNESS.replace(
        "const CONFIG = {};", f"const CONFIG = {json.dumps(config or _config())};", 1,
    ).replace(
        "const FLAGS = {};", f"const FLAGS = {json.dumps(flags or {})};", 1,
    )
    # Wrap the emitted IIFE rather than editing inside it, so what runs is the
    # artefact byte for byte.
    #
    # `process.exit` because the script schedules a 30-second timer to revoke
    # the download's object URL, and that timer holds Node's event loop open
    # long after the run has finished. Exiting is the harness's business, not
    # a reason to change what the browser gets.
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__TABLES__' + JSON.stringify(tables));\n"
        "  process.exit(0);\n"
        "});\n"
    )
    out = _run(script)
    payload: dict[str, Any] = {}
    calls: list[dict[str, Any]] = []
    tables: list[Any] = []
    for line in out.splitlines():
        if line.startswith("__RESULT__"):
            payload = json.loads(line.removeprefix("__RESULT__"))
        elif line.startswith("__CALLS__"):
            calls = json.loads(line.removeprefix("__CALLS__"))
        elif line.startswith("__TABLES__"):
            tables = json.loads(line.removeprefix("__TABLES__"))
    assert payload, f"the script returned nothing. Output:\n{out}"
    return payload, calls, tables, out


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _by_title(payload: dict[str, Any], title: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [
        row for row in payload["lists"] if row["title"] == title
    ]
    assert found, f"{title!r} is not in the inventory"
    return found[0]


def test_it_files_every_owned_object_under_its_family() -> None:
    payload, _, _, _ = _run_script()
    families = {row["family"]: row for row in payload["families"]}
    assert families[FAMILY]["lists"] == 2
    assert families[FAMILY]["groups"] == 1
    assert families[FAMILY]["levels"] == 1
    assert families[OTHER_FAMILY]["lists"] == 1
    # The tool's own objects file under a null family, which is the grammar's
    # ` for` form against ` from <family> for`.
    assert families[None]["lists"] == 2
    assert families[None]["groups"] == 1


def test_a_marker_surrounded_by_prose_is_still_a_marker() -> None:
    """The deploy tests ownership with `indexOf`, so a description may carry
    text either side of its marker."""
    payload, _, _, _ = _run_script()
    action = _by_title(payload, "GOV_Action")
    assert action["owned"] is True
    assert action["family"] == FAMILY
    assert action["declaredName"] == "GOV_Action"


def test_a_description_that_only_mentions_the_tool_is_not_owned() -> None:
    """This is the near miss the prefix-free grammar exists to refuse."""
    payload, _, _, _ = _run_script()
    decoy = _by_title(payload, "Notes")
    assert decoy["owned"] is False
    assert decoy["family"] is None
    assert decoy["columns"] is None


def test_columns_are_read_once_per_owned_list_and_never_for_the_others() -> None:
    """The request budget is measured here rather than asserted."""
    payload, calls, _, _ = _run_script()
    field_reads = [c for c in calls if "/fields" in c["url"]]
    owned = [row for row in payload["lists"] if row["owned"]]
    assert len(owned) == 5
    assert len(field_reads) == len(owned)
    assert not [c for c in field_reads if DOCS_ID in c["url"] or DECOY_ID in c["url"]]


def test_built_in_and_hidden_columns_are_left_out() -> None:
    """Every list carries the same built-ins, so they identify nothing."""
    payload, _, _, _ = _run_script()
    risk = _by_title(payload, "GOV_Risk")
    names = [column["internalName"] for column in risk["columns"]]
    assert names == ["ResidualRating", "LastReviewedDate"]


def test_every_request_is_a_get() -> None:
    _, calls, _, _ = _run_script()
    assert {c["method"] for c in calls} == {"GET"}


def test_it_reports_the_last_deployment_from_the_run_log() -> None:
    payload, _, _, _ = _run_script()
    assert payload["lastDeployment"]["ReleaseTag"] == "2.1.0"
    assert payload["lastDeployment"]["StampUtc"] == "2026-09-04T02:10:00Z"
    assert payload["changeLog"]["rows"] == 19


def test_the_run_log_is_found_by_its_marker_not_its_title() -> None:
    """`--change-log-list` renames a sidecar and its marker follows, so a
    by-title search would report a renamed log's site as never deployed."""
    config = _config()
    for row in config["lists"]:
        if row["Title"] == sidecars.RUN_LOG_TITLE:
            row["Title"] = "Renamed By Somebody"
    payload, _, _, _ = _run_script(config)
    assert payload["lastDeployment"]["ReleaseTag"] == "2.1.0"


def test_a_site_carrying_only_the_old_run_log_still_reports_its_history() -> None:
    """A site deployed before the `dbml_Deployments` rename still carries its
    run log under the pre-rename title, marker and all. `sidecarFor` has to
    recognise that declared name too, or a site with years of history prints
    the same "no deployment record" line as one that was never deployed."""
    old_title = sidecars.RUN_LOG_PREVIOUS_TITLES[0]
    config = _config()
    for row in config["lists"]:
        if row["Title"] == sidecars.RUN_LOG_TITLE:
            row["Title"] = old_title
            row["Description"] = marker_for_object(kind=SCRATCH_KIND, name=old_title, family=None)
    payload, _, _, out = _run_script(config)
    assert payload["lastDeployment"]["ReleaseTag"] == "2.1.0"
    run_log_row = _by_title(payload, old_title)
    assert run_log_row["owned"] is True
    assert run_log_row["declaredName"] == old_title
    assert "No deployment record" not in out


def test_the_current_run_log_title_is_preferred_over_an_old_one() -> None:
    """A site redeployed since the rename can carry both titles. The current
    one is the list this tool keeps writing to, so its history is what gets
    reported rather than the older, now-frozen list."""
    old_title = sidecars.RUN_LOG_PREVIOUS_TITLES[0]
    config = _config()
    config["lists"].append(_list(
        old_title, OLD_RUN_LOG_ID, items=1, hidden=True,
        description=marker_for_object(kind=SCRATCH_KIND, name=old_title, family=None),
    ))
    config["items"][OLD_RUN_LOG_ID] = [
        {"Id": 1, "Title": "deployment stop", "StampKind": "stop", "ReleaseTag": "1.0.0"},
    ]
    payload, _, _, _ = _run_script(config)
    assert payload["lastDeployment"]["ReleaseTag"] == "2.1.0"


def test_a_site_carrying_only_the_old_change_log_still_reports_it() -> None:
    """`CHANGE_LOG_TITLE` was `dbml_Logs` before this rename too, and a site
    deployed under that build still carries its change log under that title.
    `changeLog` in the payload must not read as null on a site with real
    change history simply because the title changed."""
    old_title = sidecars.CHANGE_LOG_PREVIOUS_TITLES[0]
    config = _config()
    for row in config["lists"]:
        if row["Title"] == sidecars.CHANGE_LOG_TITLE:
            row["Title"] = old_title
            row["Description"] = marker_for_object(kind=SCRATCH_KIND, name=old_title, family=None)
    payload, _, _, _ = _run_script(config)
    assert payload["changeLog"] == {"title": old_title, "rows": 19}
    change_log_row = _by_title(payload, old_title)
    assert change_log_row["owned"] is True
    assert change_log_row["declaredName"] == old_title


def test_the_current_change_log_title_is_preferred_over_an_old_one() -> None:
    """A site redeployed since the rename can carry both change logs; the
    current one is reported, the same preference as the run log."""
    old_title = sidecars.CHANGE_LOG_PREVIOUS_TITLES[0]
    config = _config()
    config["lists"].append(_list(
        old_title, OLD_CHANGE_LOG_ID, items=3, hidden=True,
        description=marker_for_object(kind=SCRATCH_KIND, name=old_title, family=None),
    ))
    payload, _, _, _ = _run_script(config)
    assert payload["changeLog"] == {"title": sidecars.CHANGE_LOG_TITLE, "rows": 19}


def test_a_site_with_no_markers_reports_nothing_owned_and_reads_no_columns() -> None:
    config = _config()
    config["lists"] = [_list("Documents", DOCS_ID, items=5)]
    config["groups"] = [{"Id": 13, "Title": "Site Owners", "Description": "Built in."}]
    config["levels"] = [{"Id": 22, "Name": "Full Control", "Description": "Has full control."}]
    payload, calls, _, _ = _run_script(config)
    assert payload["families"] == []
    assert payload["lastDeployment"] is None
    assert not [c for c in calls if "/fields" in c["url"]]
    assert payload["problems"] == []


def test_a_refused_collection_is_recorded_and_the_rest_still_comes_back() -> None:
    """A partial inventory an operator can read beats an abort that says
    nothing about the site they were trying to identify."""
    payload, _, _, _ = _run_script(flags={"groupsRefused": True})
    assert payload["groups"] == []
    assert [p["section"] for p in payload["problems"]] == ["Groups"]
    assert len(payload["lists"]) == 7
    assert payload["levels"]


def test_the_payload_says_what_shape_it_is() -> None:
    payload, _, _, _ = _run_script()
    assert payload["format"] == PAYLOAD_FORMAT
    assert payload["payload_version"] == PAYLOAD_VERSION
    assert payload["site"]["serverRelativeUrl"] == WEB
    assert payload["site"]["title"] == "Programme Site"
    assert payload["operator"] == "operator@example.com"
    assert payload["requestCount"] == len(_run_script()[1])
