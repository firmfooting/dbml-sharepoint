# test/test_extract_runtime.py
"""Execute the generated extract.js against a mock SharePoint web.

`node --check` proves the script parses. It cannot reach a name that is only
resolved when a branch runs, so the abort path went out referring to a
variable that does not exist in its scope: the one path whose whole job is to
explain a failure was itself throwing.

Node is required; the tests skip without it rather than failing, since it is
not a dependency of the package.
"""

import json
import textwrap
from collections.abc import Mapping

import pytest
from _json_view import Json
from _node import NODE
from _node import run_node as _run

from dbml_sharepoint.generators.extractgen import generate_extract_js

GENERATED_AT = "2026-09-06T12:00:00+00:00"
SITE = "https://example.sharepoint.com/sites/risk"
WEB = "/sites/risk"

#: The fixture list is SERVED at /Lists/OldRisk and TITLED PT_Risk, which is
#: what a list that has been through a `renamed_from` migration looks like.
LIST_PATH = f"{WEB}/Lists/OldRisk"
LIST_TITLE = "PT_Risk"
MISSING_PATH = f"{WEB}/Lists/Gone"

_HARNESS = textwrap.dedent(r"""
    const CONFIG = {};
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: CONFIG.web,
      userLoginName: 'operator@example.com',
      userId: 1,
    };
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

    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      calls.push({ url: u, method: (opts && opts.method) || 'GET' });

      if (u.includes('web/lists?$select=Title,Hidden')) {
        return results(CONFIG.titles.map((t) => ({ Title: t, Hidden: false })));
      }
      if (u.includes('web/lists?$select=Id,Hidden,IsCatalog')) return results(CONFIG.siteLists);
      const byId = /web\/lists\(guid'([^']+)'\)\?\$select=/.exec(u);
      if (byId) {
        const found = (CONFIG.lists || [CONFIG.list]).find((l) => l.Id === byId[1]);
        if (found) return reply(200, { d: found });
        return reply(404, { error: { message: { value: 'List not found' } } });
      }
      const byPath = /GetList\(@listUrl\)\?@listUrl='([^']+)'/.exec(u);
      if (byPath && CONFIG.getListRefuses) {
        const refused = 'Cannot find resource for the request sites.';
        return reply(404, { error: { message: { value: refused } } });
      }
      if (byPath) {
        const found = (CONFIG.lists || [CONFIG.list]).find((l) => l.Path === byPath[1]);
        if (!found) {
          return reply(404, { error: { message: { value: 'List not found' } } });
        }
        return reply(200, { d: found });
      }
      if (u.includes('/fields?')) {
        const d = { results: CONFIG.fields, ...CONFIG.fieldPage };
        return reply(200, { d });
      }
      if (u.includes('__fields_page=2')) return results(CONFIG.laterFields);
      if (u.includes('/views?')) return results([]);
      if (u.includes('/contenttypes?')) return results([]);
      return reply(400, { error: { message: { value: `unmocked ${u}` } } });
    };
""")


def _config() -> dict[str, object]:
    return {
        "web": WEB,
        "titles": [LIST_TITLE, "PT_Project"],
        "list": {
            "Id": "aaaaaaaa-0000-0000-0000-000000000001",
            "Title": LIST_TITLE,
            "Path": LIST_PATH,
            "Description": "",
            "BaseTemplate": 100,
            "ItemCount": 3,
        },
        "fields": [
            {"InternalName": "Title", "SchemaXml": '<Field Name="Title" Type="Text" />'},
        ],
    }


Run = tuple[Json, str]


def _run_script(list_paths: list[str] | None) -> Run:
    """Run the emitted extract script against the mock and return its result."""
    body = generate_extract_js(
        site_url=SITE, list_paths=list_paths, generated_at=GENERATED_AT,
    ).rstrip()
    assert body.endswith("})();")
    harness = _HARNESS.replace(
        "const CONFIG = {};", f"const CONFIG = {json.dumps(_config())};", 1,
    )
    # Wrap the emitted IIFE rather than editing inside it, so what runs is the
    # artefact byte for byte. `process.exit` because a successful run schedules
    # a 30-second timer to revoke the download's object URL.
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  process.exit(0);\n"
        "}).catch((e) => {\n"
        "  console.log('__THREW__' + (e && e.message));\n"
        "  process.exit(0);\n"
        "});\n"
    )
    out = _run(script)
    payload = Json({})
    for line in out.splitlines():
        if line.startswith("__RESULT__"):
            payload = Json.loads(line.removeprefix("__RESULT__"))
    return payload, out


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def test_a_list_that_cannot_be_read_aborts_with_the_path_it_tried() -> None:
    """The abort has to name what it failed on and get back to the operator.

    It referred to `title`, which is declared inside `readList` and is not in
    scope where the failure is caught, so the diagnostic threw a ReferenceError
    and the operator saw an unhandled rejection instead of the reason.
    """
    result, out = _run_script([MISSING_PATH])
    assert "__THREW__" not in out, f"the abort path threw instead of reporting:\n{out}"
    assert result["aborted"] == "list-read-failed"
    assert result["list"] == MISSING_PATH


def test_the_abort_names_the_lists_that_do_exist() -> None:
    """A path naming no list is answered with the ones that do, because a bare
    404 is what the console paints red and an operator reads as a broken
    script."""
    _, out = _run_script([MISSING_PATH])
    assert MISSING_PATH in out
    # Sorted, so the titles are named in their own order rather than the
    # fixture's.
    assert "Lists on this web: PT_Project, PT_Risk" in out


def test_a_list_that_reads_cleanly_still_extracts() -> None:
    """The positive control: the abort path is not reached, and the payload
    carries the title read back from the site rather than the URL slug."""
    result, out = _run_script([LIST_PATH])
    assert "__THREW__" not in out, out
    assert result["lists"][0]["title"] == LIST_TITLE
    assert result["lists"][0]["fields"] == ['<Field Name="Title" Type="Text" />']
    # The id is what a lookup's List attribute names, so `extract` can resolve it.
    assert result["lists"][0]["id"] == "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.mark.parametrize("continuation", [False, 0, True, 1, [], {}])
def test_malformed_continuation_aborts_extraction(
    continuation: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config["fieldPage"] = {"__next": continuation}
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, output = _run_script([LIST_PATH])
    assert result["aborted"] == "list-read-failed"
    assert "malformed OData __next" in output
    assert "lists" not in result


@pytest.mark.parametrize("page", [{}, {"__next": None}, {"__next": ""}])
def test_valid_continuation_terminators_preserve_extraction(
    page: Mapping[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config["fieldPage"] = page
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, output = _run_script([LIST_PATH])
    assert "__THREW__" not in output
    assert result["lists"][0]["fields"] == ['<Field Name="Title" Type="Text" />']


def test_extraction_includes_fields_from_later_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    config["fieldPage"] = {"__next": SITE + "/_api/__fields_page=2"}
    schema = '<Field Name="Later" Type="Text" />'
    config["laterFields"] = [{"InternalName": "Later", "SchemaXml": schema}]
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, output = _run_script([LIST_PATH])
    assert "__THREW__" not in output
    assert result["lists"][0]["fields"] == [
        '<Field Name="Title" Type="Text" />', schema,
    ]


@pytest.mark.parametrize("results", [None, {}])
def test_a_field_page_without_results_aborts_extraction(
    results: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read as empty, the list extracted with none of its columns (#722)."""
    config = _config()
    config["fieldPage"] = {"results": results}
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, output = _run_script([LIST_PATH])
    assert result["aborted"] == "list-read-failed"
    assert "without a d.results array" in output
    assert "lists" not in result


def _site_entry(
    path: str, list_id: str = "", *, hidden: bool = False, catalog: bool = False,
) -> dict[str, object]:
    return {
        "Id": list_id, "Hidden": hidden, "IsCatalog": catalog,
        "RootFolder": {"ServerRelativeUrl": path},
    }


def test_a_site_read_extracts_every_visible_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hidden lists and catalogues are the platform's own, not the site's
    data, so a site read skips them and reads the rest by the id the
    enumeration returned. GetList refused a path holding a space live."""
    config = _config()
    other_path = f"{WEB}/Lists/Action Register"
    other_id = "aaaaaaaa-0000-0000-0000-000000000002"
    assert isinstance(config["list"], dict)
    first_id = config["list"]["Id"]
    assert isinstance(first_id, str)
    other = {**config["list"], "Id": other_id, "Title": "Action Register", "Path": other_path}
    config["lists"] = [config["list"], other]
    config["getListRefuses"] = True
    config["siteLists"] = [
        _site_entry(LIST_PATH, first_id),
        _site_entry(other_path, other_id),
        _site_entry(f"{WEB}/Lists/Workflow History", hidden=True),
        _site_entry(f"{WEB}/_catalogs/masterpage", catalog=True),
    ]
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, out = _run_script(None)
    assert "__THREW__" not in out, out
    assert [entry["title"] for entry in result["lists"]] == [LIST_TITLE, "Action Register"]
    assert result["siteRead"].value is True


def test_a_site_with_no_visible_lists_downloads_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config["siteLists"] = [_site_entry(f"{WEB}/_catalogs/masterpage", catalog=True)]
    monkeypatch.setattr(__name__ + "._config", lambda: config)
    result, out = _run_script(None)
    assert result["aborted"] == "no-lists"
    assert "Nothing was downloaded" in out
