import json
import shutil
import subprocess
from typing import Any

import pytest
from _paths import MANUAL


@pytest.mark.parametrize("scenario", [
    "normal", "library-denied", "throttled", "malformed", "administrator", "identity-denied",
    "owner", "groups-denied", "owners-denied", "groups-malformed", "owners-malformed",
    "groups-partial", "groups-partial-odata", "groups-partial-verbose", "groups-verbose",
    "group-id-malformed",
    "extra-administrator", "extra-division", "wrong-division", "no-groups",
    "division-missing", "division-malformed", "division-unsafe", "division-is-owners",
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
const prompts = ['Probe', 'division A before', '/sites/probe/Probe/A/test.txt', division];
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
    else body = { IsSiteAdmin: scenario === 'administrator' };
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
  else if (url.includes('RoleAssignments?')) {
    status = 403;
    body = { error: { message: 'ACL enumeration denied' } };
  } else if (url.includes('/EffectiveBasePermissions')) body = { High: '1073741824', Low: '5' };
  else if (url.includes('HasUniqueRoleAssignments')) body = { HasUniqueRoleAssignments: false };
  else if (url.includes('RootFolder/ServerRelativeUrl')) {
    if (scenario === 'library-denied') status = 403;
    else body = { BaseTemplate: 101, RootFolder: { ServerRelativeUrl: '/sites/probe/Probe' } };
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
    script = (
        f"const source = {json.dumps(source)}; const scenario = {json.dumps(scenario)};\n{harness}"
    )
    completed = subprocess.run(  # noqa: S603 - executes repository-owned probe with mocked reads
        [node, "-e", script],
        capture_output=True, text=True, check=True,
    )
    result: dict[str, Any] = json.loads(completed.stdout)
    report = result["report"]
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
    if scenario == "library-denied":
        assert report["libraryRootVerified"] is False
    if scenario == "throttled":
        assert target["fileRead"]["status"] == 429
    findings = {row["id"]: row for row in report["results"]}
    ordinary = scenario in {
        "normal", "library-denied", "throttled", "malformed", "groups-verbose",
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
