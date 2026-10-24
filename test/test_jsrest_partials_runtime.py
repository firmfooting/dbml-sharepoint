"""Execute the download, ensureUser and pathname site-guard partials under Node, one fact each."""

import json
from typing import TypedDict, cast

import pytest
from test_deploy_runtime import _reader_deploy_js
from test_transport_facts_runtime import Stub, _run_facts, contextinfo

from dbml_sharepoint.analysis.permissions import TENANT_WIDE_CLAIM_NEEDLES
from dbml_sharepoint.jsonvalue import JsonValue
from dbml_sharepoint.jsrest import strip_js_comments
from dbml_sharepoint.templating import script_env
from dbml_sharepoint.testing.node import NODE
from dbml_sharepoint.testing.node import run_node as _run

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


class GuardRun(TypedDict, total=False):
    """The web the guard resolved, or the error it threw."""

    web: str
    error: str


def run_guard(
    pathname: str, *, expected: str | None = None, origin: str = "https://t.example",
) -> GuardRun:
    """Run the pathname guard, stripped as the prelude ships it, on `origin` + `pathname`."""
    guard = strip_js_comments(script_env().get_template("_site_guard.js.j2").render(
        site_resolution="pathname", require_site_match=expected is not None))
    script = (
        f"globalThis.location = {{ origin: {json.dumps(origin)},"
        f" pathname: {json.dumps(pathname)} }};\n"
        f"const SITE_URL = {json.dumps(expected)};\n"
        "const log = () => {};\n"
        "(async () => {\n"
        f"{guard}\n"
        "return { web: WEB };\n"
        "})().catch((err) => ({ error: err.message }))"
        ".then((r) => console.log('__OUT__' + JSON.stringify(r)));\n"
    )
    line = next(x for x in _run(script).splitlines() if x.startswith("__OUT__"))
    return cast("GuardRun", json.loads(line.removeprefix("__OUT__")))


@pytest.mark.parametrize(("pathname", "web"), [
    ("/sites/T/SitePages/Home.aspx", "/sites/T"),
    ("/sites/T/_layouts/15/settings.aspx", "/sites/T"),
    ("/SitePages/Home.aspx", ""),
])
def test_the_pathname_guard_takes_the_site_prefix(pathname: str, web: str) -> None:
    assert run_guard(pathname) == {"web": web}


def test_the_pathname_guard_refuses_a_page_outside_site_pages() -> None:
    assert run_guard("/sites/T/Lists/X/AllItems.aspx")["error"] == (
        "Run this from a modern page under .../SitePages/ or from .../_layouts/15/settings.aspx")


@pytest.mark.parametrize("expected", [
    "https://t.example/sites/My Site", "https://t.example/sites/My%20Site/",
])
def test_an_encoded_or_slashed_expected_site_matches(expected: str) -> None:
    assert run_guard("/sites/My%20Site/SitePages/Home.aspx", expected=expected) == {
        "web": "/sites/My%20Site"}


@pytest.mark.parametrize("expected", [
    "https://t.example/sites/Other", "https://other.example/sites/My Site",
])
def test_another_site_or_origin_is_refused(expected: str) -> None:
    assert run_guard("/sites/My%20Site/SitePages/Home.aspx", expected=expected)["error"].startswith(
        "Site mismatch.")


def test_a_mismatch_names_both_sites() -> None:
    other = "https://t.example/sites/Other/"
    assert run_guard("/sites/T/SitePages/Home.aspx", expected=other)["error"] == (
        "Site mismatch. Expected https://t.example/sites/Other, found https://t.example/sites/T.")


ENSURE_PARTIALS = (
    "_http.js.j2", "_http_write.js.j2", "_digest_cached.js.j2", "_ensure_user.js.j2",
)
PRINCIPAL: dict[str, JsonValue] = {
    "Id": 7, "LoginName": "i:0#.f|membership|a@t.example", "Title": "A",
    "Email": "a@t.example", "PrincipalType": 1,
}


def run_ensure(name: str, *answer: Stub, login: str | None = None) -> dict[str, object]:
    """ensureUser(`name`) behind a digest, answered by `answer` or by PRINCIPAL with `login`."""
    if not answer:
        answer = (Stub(200, {"d": {**PRINCIPAL, "LoginName": login or PRINCIPAL["LoginName"]}}),)
    result = _run_facts(
        f"report.principal = await ensureUser({json.dumps(name)});",
        contextinfo("D1"), *answer, partials=ENSURE_PARTIALS)
    return cast("dict[str, object]", result)


def test_ensure_user_returns_the_principal() -> None:
    result = run_ensure("a@t.example")
    assert result["principal"] == PRINCIPAL
    post = cast("list[dict[str, str]]", result["calls"])[1]
    assert post["url"] == (
        "/sites/T/_api/web/ensureuser?$select=Id,LoginName,Title,Email,PrincipalType")
    assert (post["method"], post["digest"]) == ("POST", "D1")


def test_ensure_user_refuses_a_tenant_wide_claim_without_echoing_the_name() -> None:
    result = run_ensure("everyone@t.example", login="c:0-.f|rolemanager|spo-grid-all-users/x")
    assert result["error"] == "ensureuser resolved a tenant-wide claim; refused"
    assert "everyone@t.example" not in result["error"]


@pytest.mark.parametrize("needle", TENANT_WIDE_CLAIM_NEEDLES)
def test_every_needle_is_refused_in_any_case(needle: str) -> None:
    assert run_ensure("x@t.example", login=f"PRE{needle.upper()}POST")["error"] == (
        "ensureuser resolved a tenant-wide claim; refused")


def test_a_refusal_carries_the_reason_without_the_name() -> None:
    said = "The specified user Nobody@T.example could not be found."
    reason: JsonValue = {"error": {"message": {"value": said}}}
    assert run_ensure("nobody@t.example", Stub(400, reason))["error"] == (
        "ensureuser: HTTP 400 The specified user [logon name] could not be found.")


def test_a_claim_refused_with_only_its_address_quoted_carries_neither() -> None:
    claim = "i:0#.f|membership|nobody@t.example"
    said = "The specified user Nobody@T.example could not be found."
    error = run_ensure(claim, Stub(400, {"error": {"message": {"value": said}}}))["error"]
    assert error == "ensureuser: HTTP 400 The specified user [logon name] could not be found."
    assert "nobody@t.example" not in error.lower()
    assert claim not in error


@pytest.mark.parametrize("principal", [
    {**PRINCIPAL, "Id": "7"}, {**PRINCIPAL, "LoginName": ""}, {}, None,
])
def test_an_invalid_principal_is_refused(principal: JsonValue) -> None:
    assert run_ensure("a@t.example", Stub(200, {"d": principal}))["error"] == (
        "ensureuser returned an invalid principal response")


class DownloadRun(TypedDict, total=False):
    """What `download` returned, the warnings it logged, and the file it offered."""

    started: bool
    warnings: list[str]
    name: str
    text: str
    revokeAfter: int


def run_download(*, blob_fails: bool) -> DownloadRun:
    """download('out.json', {a: [1]}) against a stub DOM whose blob URL can be made to fail."""
    partial = script_env().get_template("_download.js.j2").render()
    script = (
        "const warnings = [];\n"
        "const log = (level, message) => { if (level === 'WARN') warnings.push(message); };\n"
        "const seen = {};\n"
        "globalThis.Blob = class { constructor(parts) { seen.text = parts.join(''); } };\n"
        "globalThis.URL.createObjectURL = () => {"
        f" if ({json.dumps(blob_fails)}) throw new Error('blocked by policy');"
        " return 'blob:x'; };\n"
        "globalThis.URL.revokeObjectURL = () => {};\n"
        "globalThis.setTimeout = (fn, ms) => { seen.revokeAfter = ms; };\n"
        "globalThis.document = { body: { appendChild: () => {} }, createElement: () => ({"
        " click() { seen.name = this.download; }, remove() {} }) };\n"
        f"{partial}\n"
        "const started = download('out.json', { a: [1] });\n"
        "console.log('__OUT__' + JSON.stringify({ started, warnings, ...seen }));\n"
    )
    line = next(x for x in _run(script).splitlines() if x.startswith("__OUT__"))
    return cast("DownloadRun", json.loads(line.removeprefix("__OUT__")))


def test_download_offers_indented_json_and_revokes_after_thirty_seconds() -> None:
    assert run_download(blob_fails=False) == {
        "started": True, "warnings": [], "name": "out.json", "text": '{\n  "a": [\n    1\n  ]\n}',
        "revokeAfter": 30000}


def test_download_reports_false_when_the_blob_cannot_start() -> None:
    result = run_download(blob_fails=True)
    assert result["started"] is False
    assert result["warnings"] == ["The download could not start (blocked by policy)."]


def test_the_tenant_wide_needles_have_one_home() -> None:
    # The deploy bundle's literal comes from the constant.
    literal = f"const TENANT_WIDE = {json.dumps(list(TENANT_WIDE_CLAIM_NEEDLES))};"
    assert literal in _reader_deploy_js()
