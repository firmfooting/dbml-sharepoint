import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from _paths import MANUAL


@pytest.mark.parametrize("scenario", [
    "normal", "encoded-web", "library-denied", "library-malformed",
    "library-wrong-kind", "library-outside-web",
    "throttled", "malformed", "administrator", "identity-denied",
    "owner", "groups-denied", "owners-denied", "groups-malformed", "owners-malformed",
    "groups-partial", "groups-partial-odata", "groups-partial-verbose", "groups-verbose",
    "group-id-malformed",
    "extra-administrator", "extra-division", "wrong-division", "no-groups",
    "division-missing", "division-malformed", "division-unsafe", "division-is-owners",
    "delegation", "delegation-control-owned-by-actor", "delegation-control-owned-by-leads",
])
def test_sharing_snapshot_preserves_observations_without_claiming_enforcement(
    scenario: str,
) -> None:
    source = (MANUAL / "library-sharing-probe.js").read_text(encoding="utf-8").replace(
        "const CONFIRMED = false;", "const CONFIRMED = true;",
    )
    node = shutil.which("node")
    assert node is not None
    harness = r"""
const vm = require('node:vm');
const division = { 'division-missing': '', 'division-malformed': '8junk',
  'division-unsafe': '9007199254740993', 'division-is-owners': '7' }[scenario] ?? '8';
const leads = scenario.startsWith('delegation') ? '11' : '';
const prompts = ['Probe', 'division A before', '/sites/probe/Probe/A/test.txt', division, leads];
const calls = [];
let captured;
const window = {
  _spPageContextInfo: {
    webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe',
    webServerRelativeUrl: '/sites/probe',
  },
  location: { origin: 'https://example.sharepoint.com' },
  prompt: () => prompts.shift(),
};
const fetch = async (url, options) => {
  calls.push({url, method: options.method});
  let status = 200;
  let body = {};
  if (url.includes('currentuser?')) {
    if (scenario === 'identity-denied') status = 403;
    else body = { Id: 5, IsSiteAdmin: scenario === 'administrator' };
  }
  else if (url.includes('currentuser/groups?')) {
    body = { value: [{ Id: scenario === 'owner' ? 7 : 8 }] };
    if (scenario === 'extra-administrator') {
      body.value.push({ Id: 9, Title: 'dbml List Administrators' });
    }
    if (scenario === 'extra-division') body.value.push({ Id: 10, Title: 'Division B' });
    if (scenario === 'wrong-division') body = { value: [{ Id: 10 }] };
    if (scenario === 'no-groups') body = { value: [] };
    if (scenario === 'division-is-owners') body = { value: [{ Id: 7 }] };
    // The delegation fixture: the actor is in its division group and in the
    // leads group that owns it, and in nothing else.
    if (scenario.startsWith('delegation')) body = { value: [{ Id: 8 }, { Id: 11 }] };
    if (scenario === 'groups-denied') status = 403;
    if (scenario === 'groups-malformed') body = {};
    if (scenario === 'group-id-malformed') body = { value: [{}] };
    if (scenario === 'groups-partial') body['@odata.nextLink'] = 'next-page';
    if (scenario === 'groups-partial-odata') body['odata.nextLink'] = 'next-page';
    if (scenario === 'groups-partial-verbose') body = { d: { results: [], __next: 'next-page' } };
    if (scenario === 'groups-verbose') body = { d: { results: [{ Id: 8 }] } };
  }
  else if (url.includes('AssociatedOwnerGroup?')) {
    body = { Id: 7 };
    if (scenario === 'owners-denied') status = 403;
    if (scenario === 'owners-malformed') body = {};
  }
  else if (url.includes('/sitegroups(')) {
    const id = Number(url.match(/sitegroups\((\d+)\)/)[1]);
    if (url.includes('/owner')) {
      // Group 8 is the division group the leads group 11 owns. Group 7 is the
      // control, owned by a third party unless the scenario says otherwise.
      let ownerId = 99;
      if (id === 8) ownerId = 11;
      else if (scenario === 'delegation-control-owned-by-actor') ownerId = 5;
      else if (scenario === 'delegation-control-owned-by-leads') ownerId = 11;
      body = { Id: ownerId, Title: 'Owner ' + ownerId, PrincipalType: ownerId === 5 ? 1 : 8 };
    } else {
      body = { AllowMembersEditMembership: false,
        CanCurrentUserEditMembership: id === 8, CanCurrentUserManageGroup: id === 8,
        CanCurrentUserViewMembership: true };
    }
  }
  else if (url.includes('RoleAssignments?')) {
    status = 403;
    body = { error: { message: 'ACL enumeration denied' } };
  } else if (url.includes('/EffectiveBasePermissions')) body = { High: '1073741824', Low: '5' };
  else if (url.includes('HasUniqueRoleAssignments')) body = { HasUniqueRoleAssignments: false };
  else if (url.includes('RootFolder/ServerRelativeUrl')) {
    if (scenario === 'library-denied') status = 403;
    else body = { BaseTemplate: 101, RootFolder: { ServerRelativeUrl: '/sites/probe/Probe' } };
    if (scenario === 'library-malformed') body.RootFolder = {};
    if (scenario === 'library-wrong-kind') body.BaseTemplate = 100;
    if (scenario === 'library-outside-web') {
      body.RootFolder.ServerRelativeUrl = '/sites/other/Probe';
    }
  } else if (url.includes('GetFolderByServerRelativeUrl')) status = 404;
  else if (url.includes('GetFileByServerRelativeUrl')) {
    if (scenario === 'throttled') status = 429;
    else body = { Name: 'test.txt', ServerRelativeUrl: '/sites/probe/Probe/A/test.txt' };
  }
  const malformed = scenario === 'malformed' && url.includes('GetFileByServerRelativeUrl');
  return { ok: status === 200, status,
    text: async () => malformed ? '<html>login</html>' : JSON.stringify(body) };
};
(async () => {
  await vm.runInNewContext(source, {
    window, _spPageContextInfo: window._spPageContextInfo, fetch, URL,
    console: { log: text => { captured = text; }, table: () => {} },
  });
  const report = JSON.parse(captured.split('\n').slice(1).join('\n'));
  console.log(JSON.stringify({report, calls}));
})();
"""
    if scenario == "encoded-web":
        harness = harness.replace("/sites/probe", "/sites/Legal Team").replace(
            "https://example.sharepoint.com/sites/Legal Team",
            "https://example.sharepoint.com/sites/Legal%20Team",
        )
    script = (
        f"const source = {json.dumps(source)}; const scenario = {json.dumps(scenario)};\n{harness}"
    )
    # Via a FILE, never `node -e`, for the reason `_node.run_node` gives:
    # Windows caps a command line and this probe is past it. MEASURED in CI
    # on 2026-09-21, every scenario here failed with WinError 206 once the
    # probe grew, while Ubuntu passed. `newline="\n"` so Node parses the
    # bytes the repository ships rather than a CRLF copy of them.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "probe.js"
        path.write_text(script, encoding="utf-8", newline="\n")
        completed = subprocess.run(  # noqa: S603 - executes repository-owned probe with mocked reads
            [node, str(path)],
            capture_output=True, text=True, check=True,
        )
    result: dict[str, Any] = json.loads(completed.stdout)
    report = result["report"]
    if scenario.startswith("library-"):
        assert "LIBRARY_ROOT_UNVERIFIED" in report["errors"][0]
        assert report["libraryRootVerified"] is False
        assert report["targets"] == []
        assert not any("GetFileBy" in call["url"] for call in result["calls"])
        findings = {row["id"]: row for row in report["results"]}
        for name in ("control-own-file-edit", "control-recipient-denied", "division-isolation",
                     "folder-resharing", "file-resharing"):
            assert findings[f"library.access.{name}"]["state"] == "void"
        return
    assert report["errors"] == []
    assert report["sharingVerdict"].startswith("NOT ESTABLISHED")
    assert {call["method"] for call in result["calls"]} == {"GET"}
    target = report["targets"][0]
    if scenario not in {"throttled", "malformed"}:
        assert target["kind"] == "file"
        assert target["scope"]["assignments"]["status"] == 403
        assert target["scope"]["inheritance"]["body"]["HasUniqueRoleAssignments"] is False
        assert target["scope"]["decoded"]["EditListItems"] is True
        assert target["scope"]["decoded"]["ManagePermissions"] is False
        assert target["scope"]["decoded"]["EnumeratePermissions"] is True
    else:
        assert "scope" not in target
        assert target["observation"].startswith("UNRESOLVED")
    if scenario == "throttled":
        assert target["fileRead"]["status"] == 429
    findings = {row["id"]: row for row in report["results"]}
    ordinary = scenario in {
        "encoded-web",
        "normal", "throttled", "malformed", "groups-verbose",
        "delegation", "delegation-control-owned-by-actor",
        "delegation-control-owned-by-leads",
    }
    sharing_state = "awaiting-capture" if ordinary else "void"
    for finding in (
        "control-own-file-edit", "control-recipient-denied", "division-isolation",
        "folder-resharing", "file-resharing",
    ):
        assert findings[f"library.access.{finding}"]["state"] == sharing_state
    if scenario == "identity-denied":
        assert findings["library.access.permission-snapshot"]["state"] == "void"
    else:
        assert findings["library.access.permission-snapshot"]["observed"] == "CAPTURED"
        assert findings["access.effective-perms.control-ordinary-actor"]["observed"] == (
            "PASS" if ordinary else "FAIL"
        )
    if scenario == "delegation":
        # The fixture the delegation question depends on: a control owned by
        # neither the actor nor a prepared group, reporting editing refused.
        assert findings["access.group.control-non-owner-cannot-edit"]["observed"] == (
            "EDIT REPORTED REFUSED"
        )
        assert findings["access.group.owner-edits-membership"]["observed"] == (
            "EDIT REPORTED ALLOWED"
        )
    if scenario.startswith("delegation-control-owned-by-"):
        # A control the actor owns is not a control. Without this the probe
        # would read its ALLOWED as the platform failing to discriminate,
        # which is indistinguishable from a real negative result.
        control = findings["access.group.control-non-owner-cannot-edit"]
        assert control["observed"].startswith("NOT ESTABLISHED")
        assert control["state"] == "open"
        delegation = findings["access.group.owner-edits-membership"]
        assert delegation["state"] == "void"
        assert "not a non-owner control" in delegation["detail"]
