# test/test_sp_mock.py
"""The prelude `run_node` loads ahead of every script (`_sp_mock.PRELUDE`).

Every runtime test now depends on it answering the way SharePoint does, so a
projection that kept too much would quietly return the suite to the mock
behaviour #574 replaced, and a tripwire that never fired would look the same
as a script with no defect.
"""

import json
from typing import Any

import pytest
from _node import NODE, run_node
from _sp_mock import UnselectedReadError

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_ROW = {"Id": 1, "Title": "t", "Hidden": False, "Fields": {"results": []},
        "__metadata": {"type": "SP.List"}}


def _mock(payload: Any, *, status: int = 200) -> str:
    """A harness answering every request with `payload`, the way the runtime
    harnesses do: a plain object with `ok`, `status`, `json()` and `text()`."""
    return (
        "globalThis.fetch = async () => ({\n"
        f"  ok: {json.dumps(status < 300)}, status: {status},\n"
        f"  json: async () => JSON.parse({json.dumps(json.dumps(payload))}),\n"
        f"  text: async () => {json.dumps(json.dumps(payload))},\n"
        "});\n"
    )


def _keys(payload: Any, url: str, pick: str, *, method: str = "GET",
          status: int = 200) -> list[str]:
    """The keys the script sees on the row `pick` selects from the answer."""
    out = run_node(
        _mock(payload, status=status)
        + "(async () => {\n"
        f"  const r = await fetch({json.dumps(url)}, {{ method: {json.dumps(method)} }});\n"
        "  const j = await r.json();\n"
        f"  console.log('KEYS' + JSON.stringify(Object.keys({pick}).sort()));\n"
        "})();\n"
    )
    line = next(ln for ln in out.splitlines() if ln.startswith("KEYS"))
    keys: list[str] = json.loads(line.removeprefix("KEYS"))
    return keys


def test_a_collection_row_keeps_only_what_was_selected() -> None:
    keys = _keys({"d": {"results": [_ROW]}}, "/_api/web/lists?$select=Id,Title", "j.d.results[0]")
    assert keys == ["Id", "Title", "__metadata"]


def test_a_verbose_entity_is_projected() -> None:
    keys = _keys({"d": _ROW}, "/_api/web/lists/getbytitle('X')?$select=Hidden", "j.d")
    assert keys == ["Hidden", "__metadata"]


def test_a_nometadata_collection_is_projected() -> None:
    keys = _keys({"value": [_ROW]}, "/_api/web/lists?$select=Title", "j.value[0]")
    assert keys == ["Title", "__metadata"]


def test_expanded_names_and_first_segments_are_kept() -> None:
    keys = _keys(
        {"d": {"results": [_ROW]}},
        "/_api/web/lists?$select=Id,Fields/InternalName&$expand=Fields", "j.d.results[0]",
    )
    assert keys == ["Fields", "Id", "__metadata"]


def test_selection_ignores_case_and_url_encoding() -> None:
    keys = _keys({"d": {"results": [_ROW]}}, "/_api/web/lists?%24select=id%2CTITLE",
                 "j.d.results[0]")
    assert keys == ["Id", "Title", "__metadata"]


@pytest.mark.parametrize("url", [
    "/_api/web/lists?$select=*", "/_api/web/lists", "/_api/web/lists?$top=5",
])
def test_a_star_or_absent_select_answers_in_full(url: str) -> None:
    keys = _keys({"d": {"results": [_ROW]}}, url, "j.d.results[0]")
    assert keys == sorted(_ROW)


def test_writes_and_error_answers_are_not_projected() -> None:
    url = "/_api/web/lists?$select=Id"
    assert _keys({"d": _ROW}, url, "j.d", method="POST") == sorted(_ROW)
    assert _keys({"d": _ROW}, url, "j.d", status=404) == sorted(_ROW)


def test_an_unselected_pascal_case_read_fails_the_run_even_when_caught() -> None:
    """Recorded rather than thrown, so the script's own try/catch cannot hide it."""
    with pytest.raises(UnselectedReadError) as caught:
        run_node(
            _mock({"d": {"results": [_ROW]}})
            + "(async () => {\n"
            "  try {\n"
            "    const j = await (await fetch('/_api/web/lists?$select=Id')).json();\n"
            "    if (j.d.results[0].Hidden === undefined) console.log('undefined, as live');\n"
            "  } catch (e) { console.log('swallowed'); }\n"
            "})();\n"
        )
    [read] = caught.value.reads
    assert read.prop == "Hidden"
    assert read.url == "/_api/web/lists?$select=Id"
    assert "results[0].Hidden" in read.source


def test_camel_case_and_script_assigned_reads_are_silent() -> None:
    out = run_node(
        _mock({"d": {"results": [_ROW]}})
        + "(async () => {\n"
        "  const j = await (await fetch('/_api/web/lists?$select=Id')).json();\n"
        "  const row = j.d.results[0];\n"
        "  row.Resolved = row.Id + 1;\n"
        "  console.log('OK', row.deleteBehavior, row.Resolved, row.id, row.__metadata.type);\n"
        "})();\n"
    )
    assert "OK undefined 2 undefined SP.List" in out


def test_a_wrapper_sees_the_full_row_and_the_script_the_projected_one() -> None:
    """A sabotage wrapper reads the fetch beneath it; only the script's own
    call is SharePoint answering the script."""
    out = run_node(
        _mock({"d": {"results": [_ROW]}})
        + "{\n"
        "  const under = globalThis.fetch;\n"
        "  globalThis.fetch = async (url, opts) => {\n"
        "    const r = await under(url, opts);\n"
        "    const rows = (await r.json()).d.results;\n"
        "    console.log('WRAPPER', Object.keys(rows[0]).length);\n"
        "    return { ...r, json: async () => ({ d: { results: rows } }) };\n"
        "  };\n"
        "}\n"
        "(async () => {\n"
        "  const j = await (await fetch('/_api/web/lists?$select=Title')).json();\n"
        "  console.log('SCRIPT', Object.keys(j.d.results[0]).join(','));\n"
        "})();\n"
    )
    assert f"WRAPPER {len(_ROW)}" in out
    assert "SCRIPT Title" in out


def test_a_nested_read_has_its_text_projected() -> None:
    """How a `$batch` part reaches the script: the batch mock redispatches it
    and reads its body as text, so text is where its projection has to be."""
    out = run_node(
        _mock({"d": {"results": [_ROW]}})
        + "{\n"
        "  const under = globalThis.fetch;\n"
        "  globalThis.fetch = async (url, opts) => {\n"
        "    if (!String(url).endsWith('$batch')) return under(url, opts);\n"
        "    const part = await globalThis.fetch('/_api/web/lists?$select=Title');\n"
        "    const text = await part.text();\n"
        "    return { ok: true, status: 200, text: async () => text };\n"
        "  };\n"
        "}\n"
        "(async () => {\n"
        "  const r = await fetch('/_api/$batch', { method: 'POST' });\n"
        "  console.log('PART', await r.text());\n"
        "})();\n"
    )
    assert 'PART {"d":{"results":[{"Title":"t","__metadata":{"type":"SP.List"}}]}}' in out
