"""Execute the probe rows #642 found settling a verdict their step did not establish.

Each row is run against a mock SharePoint twice or more: once healthy, as the
control that shows it still measures, and once per way the step can fail to
establish what the verdict claims. A sabotage wrapper is laid over an existing
mock so the mock itself keeps encoding only what a live run returns.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from test_probe_fixture_high_runtime import (
    _BY_FOLDER,
    _BY_METADATA,
    _GUARDS,
    _GUARDS_LIB,
    _LIBRARY_MOCK,
    _RULE_FIXTURES,
    _RULE_ROWS,
    _TODAY,
    _TODAY_HEALTHY,
    _TODAY_MOCK,
    _VIEW,
)
from test_probe_fixture_runtime import _catalogued_dependents, _run_probe, _void_ids
from test_probe_runtime import (
    _LIB_COLS_HARNESS,
    _LIB_COLS_HEALTHY,
    LIB_COLS_PROBE,
    _fixture_probe_js,
    _fixture_rows,
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _over(mock: str, wrapper: str) -> str:
    """`mock` with `wrapper` laid over its fetch; the wrapper calls `underneath`."""
    return mock + textwrap.dedent("""
        {
          const underneath = globalThis.fetch;
          globalThis.fetch = async (url, opts = {}) => {
            const where = decodeURIComponent(String(url).split('/_api/')[1] || '');
            const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
            let body = {};
            try { body = JSON.parse(String(opts.body || '{}')); } catch { body = {}; }
    """) + textwrap.indent(textwrap.dedent(wrapper), "        ") + textwrap.dedent("""
            return underneath(url, opts);
          };
        }
    """)


# --------------------------------------------------------------------------
# Items 1 and 5: today-semantics.
# --------------------------------------------------------------------------
_TOMORROW = "formula.datetime.today-rejects-tomorrow"
_PLUS_1H = "formula.datetime.now-function-plus-1h"


@pytest.mark.parametrize("column", ["D", "W"])
def test_today_semantics_catalogues_each_rule_fixture_over_its_own_rows(column: str) -> None:
    assert _catalogued_dependents(_TODAY, _RULE_FIXTURES[column]) == _RULE_ROWS[column]


@pytest.mark.parametrize(("unread", "measured"), [("D", "W"), ("W", "D")])
def test_today_semantics_voids_only_the_rows_of_the_rule_that_did_not_read_back(
    unread: str, measured: str,
) -> None:
    """One fixture covered both rules, so an unreadable W rule voided every D row too."""
    mock = _over(_TODAY_MOCK, f"""
        const rule = "getbyinternalnameortitle('{unread}')";
        if (verb === 'GET' && where.includes(rule)) return throttled();
    """)
    rows, _ = _run_probe(mock, _TODAY_HEALTHY, _TODAY)

    assert rows[_RULE_FIXTURES[unread]]["outcome"] == "FAIL"
    assert "the read was throttled (HTTP 429)" in rows[_RULE_FIXTURES[unread]]["evidence"]
    assert rows[_RULE_FIXTURES[measured]]["outcome"] == "PASS"
    assert _void_ids(rows) == _catalogued_dependents(_TODAY, _RULE_FIXTURES[unread])
    for row_id in _RULE_ROWS[measured]:
        assert rows[row_id]["outcome"] in {"SAVED", "REFUSED"}, rows[row_id]


def test_today_semantics_records_a_refused_save_as_refused() -> None:
    rows, _ = _run_probe(_TODAY_MOCK, _TODAY_HEALTHY, _TODAY)

    for row_id in (_TOMORROW, _PLUS_1H):
        assert rows[row_id]["outcome"] == "REFUSED", rows[row_id]
        assert "REFUSED HTTP 400" in rows[row_id]["evidence"]


@pytest.mark.parametrize("status", [401, 403, 408, 429])
@pytest.mark.parametrize("row_id", [_TOMORROW, _PLUS_1H])
def test_today_semantics_leaves_a_save_that_failed_without_a_refusal_open(
    row_id: str, status: int,
) -> None:
    """A throttled or unauthorised save was recorded as the rule refusing the value."""
    mock = _over(_TODAY_MOCK, f"""
        if (verb === 'POST' && where.endsWith('/items') && body.Title === '{row_id}') {{
          return jsonResponse({status}, {{ error: {{ message: {{ value: '' }} }} }});
        }}
    """)
    rows, _ = _run_probe(mock, _TODAY_HEALTHY, _TODAY)

    row = rows[row_id]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert row["state"] == "open", row
    assert f"FAILED HTTP {status}" in row["evidence"]


# --------------------------------------------------------------------------
# Item 2: library-guards, scope-on-merge-reads-back.
# --------------------------------------------------------------------------
_SCOPE_MERGE = "library.view.scope-on-merge-reads-back"
_SCOPE_MERGE_VIEW = "dbmlsp guards scope merge"


def _scope_merges(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "MERGE" and _SCOPE_MERGE_VIEW in r["path"]]


def _guards_reusing(scope: int) -> dict[str, Any]:
    views = {_SCOPE_MERGE_VIEW: {"Scope": scope}}
    return {"existing": {_GUARDS_LIB: {"template": 101, "views": views}}}


def test_guards_settles_a_merge_on_a_reused_view_that_read_another_scope() -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, _guards_reusing(0), _GUARDS)

    assert rows[_SCOPE_MERGE]["outcome"] == "STICKS", rows[_SCOPE_MERGE]
    assert "Scope read 0 before" in rows[_SCOPE_MERGE]["evidence"]
    assert len(_scope_merges(sent)) == 1


def test_guards_does_not_settle_a_merge_on_a_view_already_at_scope_one() -> None:
    """A reused view already reading Scope 1 reported STICKS for a MERGE that changed nothing."""
    rows, sent = _run_probe(_LIBRARY_MOCK, _guards_reusing(1), _GUARDS)

    row = rows[_SCOPE_MERGE]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert row["state"] == "void", row
    assert "Scope read 1 before, so no MERGE was sent" in row["evidence"]
    assert not _scope_merges(sent)


def test_guards_does_not_settle_a_merge_when_the_scope_before_did_not_read() -> None:
    mock = _over(_LIBRARY_MOCK, f"""
        if (verb === 'GET' && where.includes("views/getbytitle('{_SCOPE_MERGE_VIEW}')")
            && where.includes('Scope')) return throttled();
    """)
    rows, sent = _run_probe(mock, {}, _GUARDS)

    row = rows[_SCOPE_MERGE]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert row["state"] == "open", row
    assert "(read failed HTTP 429)" in row["evidence"]
    assert not _scope_merges(sent)


# --------------------------------------------------------------------------
# Items 3 and 4: library-columns.
# --------------------------------------------------------------------------
_CALC = "library.column.calculated-column-on-library"
_RULE = "library.validation.validation-formula-on-library"


def _run_lib_cols(wrapper: str = "", **changes: Any) -> dict[str, dict[str, str]]:
    config = json.loads(json.dumps(_LIB_COLS_HEALTHY))
    config.update(changes)
    harness = _LIB_COLS_HARNESS.replace("__CONFIG__", json.dumps(config))
    script = (_over(harness, wrapper) if wrapper else harness) + "\n" + _fixture_probe_js(
        LIB_COLS_PROBE)
    return _fixture_rows(run_node(script))


def _choice_write_lands_as(value: str) -> str:
    """The Beta write answers 204 and the item keeps `value`, as a write that did not land."""
    return f"""
        if (verb === 'MERGE' && body.ColChoice === 'Beta') {{
          opts = {{ ...opts, body: JSON.stringify({{ ...body, ColChoice: {value} }}) }};
        }}
    """


def test_calculated_column_is_judged_against_the_choice_it_was_read_beside() -> None:
    rows = _run_lib_cols()

    assert rows[_CALC]["outcome"] == "PASS", rows[_CALC]
    assert '[ColChoice]="Beta"' in rows[_CALC]["evidence"]


def test_calculated_column_is_not_failed_by_a_choice_write_that_did_not_land() -> None:
    """The row expected 'Beta - calc' whatever the item held, and FAILed a correct calculation."""
    rows = _run_lib_cols(_choice_write_lands_as("'Alpha'"))

    assert rows["library.column.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows[_CALC]["outcome"] == "PASS", rows[_CALC]
    assert '[ColChoice]="Alpha"' in rows[_CALC]["evidence"]


def test_calculated_column_with_a_blank_operand_is_not_established() -> None:
    rows = _run_lib_cols(_choice_write_lands_as("null"))

    assert rows[_CALC]["outcome"] == "NOT ESTABLISHED", rows[_CALC]
    assert "ColChoice read back null" in rows[_CALC]["evidence"]


def test_an_accepted_violating_write_that_stored_the_value_is_inert() -> None:
    rows = _run_lib_cols(ruleEnforces=False)

    assert rows[_RULE]["outcome"] == "INERT", rows[_RULE]
    assert 'ColChoice reads back "InvalidValue"' in rows[_RULE]["evidence"]


def test_an_accepted_violating_write_that_stored_nothing_is_not_inert() -> None:
    """INERT was recorded off the 204 alone, which a dropped write also answers."""
    rows = _run_lib_cols("""
        if (verb === 'MERGE' && body.ColChoice === 'InvalidValue') {
          return jsonResponse(204, {});
        }
    """, ruleEnforces=False)

    assert rows[_RULE]["outcome"] == "NOT ESTABLISHED", rows[_RULE]
    assert 'ColChoice reads back "Beta"' in rows[_RULE]["evidence"]


def test_an_accepted_violating_write_that_did_not_read_back_is_not_inert() -> None:
    rows = _run_lib_cols("""
        if (verb === 'MERGE' && body.ColChoice === 'InvalidValue') globalThis.violated = true;
        if (verb === 'GET' && globalThis.violated && /\\/items\\(\\d+\\)/.test(where)) {
          return jsonResponse(429, { error: 'throttled' });
        }
    """, ruleEnforces=False)

    assert rows[_RULE]["outcome"] == "NOT ESTABLISHED", rows[_RULE]
    assert "did not read back (HTTP 429)" in rows[_RULE]["evidence"]


# --------------------------------------------------------------------------
# Item 6: library-view matches each upload by its full path.
# --------------------------------------------------------------------------
_ROOT = "/sites/test/L1"
_DECOY = "Decoy"


def _with_decoys(names: list[str]) -> str:
    """A reused library holding each of `names` in another folder, where a name match finds it."""
    return _over(_LIBRARY_MOCK, f"""
        if (!globalThis.decoyed && verb === 'POST' && where.includes("/Files/add(url='")) {{
          globalThis.decoyed = true;
          const at = (folder) => `${{String(url).split('/_api/')[0]}}/_api/web/`
            + `GetFolderByServerRelativeUrl('${{folder}}')`;
          const post = (body) => ({{ method: 'POST', headers: {{}}, body }});
          await underneath(`${{at('{_ROOT}')}}/folders/add(url='{_DECOY}')`, post('{{}}'));
          for (const name of {json.dumps(names)}) {{
            const file = `Files/add(url='${{name}}',overwrite=true)`;
            await underneath(`${{at('{_ROOT}/{_DECOY}')}}/${{file}}`, post('decoy'));
          }}
        }}
    """)


def _item_merges(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "MERGE" and "/items(" in r["path"]]


def test_library_view_writes_each_file_at_the_path_it_uploaded_to() -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, {}, _VIEW)

    assert rows[_BY_METADATA]["outcome"] == "SAME AS LIST", rows[_BY_METADATA]
    assert rows[_BY_FOLDER]["outcome"] == "FOLDERS ARE NOT A REST GROUPING DIMENSION"
    assert not _void_ids(rows)
    assert len(_item_merges(sent)) == 4


def test_library_view_does_not_write_to_a_same_named_file_in_another_folder() -> None:
    """A name match picked the decoy, so the MERGE and its read-back landed on the wrong item."""
    names = ["doc-alpha-1.txt", "doc-beta-1.txt", "doc-alpha-2.txt", "subfolder-doc.txt"]
    rows, sent = _run_probe(_with_decoys(names), {}, _VIEW)

    assert rows[_BY_METADATA]["outcome"] == "SAME AS LIST", rows[_BY_METADATA]
    assert rows[_BY_FOLDER]["outcome"] == "FOLDERS ARE NOT A REST GROUPING DIMENSION"
    assert not _void_ids(rows)
    # The decoys are items 1 to 4; every write goes to an upload of this run.
    assert sorted(r["path"].split("/items(")[1].split(")")[0] for r in _item_merges(sent)) == [
        "5", "6", "7", "8"]


def test_library_view_voids_the_folder_row_when_only_a_decoy_carries_the_subfile() -> None:
    mock = _over(_with_decoys(["subfolder-doc.txt"]), """
        if (verb === 'POST' && where.includes("FolderAlpha')/Files/add(")) {
          return jsonResponse(200, { Name: 'subfolder-doc.txt' });
        }
    """)
    rows, _ = _run_probe(mock, {}, _VIEW)

    assert _void_ids(rows) == {_BY_FOLDER}
    assert f"no item was served at '{_ROOT}/FolderAlpha/subfolder-doc.txt'" in (
        rows[_BY_FOLDER]["evidence"])
