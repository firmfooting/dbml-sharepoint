"""Execute the probe rows #642 found settling a verdict their step did not establish.

Each row is run against a mock SharePoint twice or more: once healthy, as the
control that shows it still measures, and once per way the step can fail to
establish what the verdict claims. A sabotage wrapper is laid over an existing
mock so the mock itself keeps encoding only what a live run returns.
"""

import textwrap

import pytest
from _node import NODE
from test_probe_fixture_high_runtime import (
    _RULE_FIXTURES,
    _RULE_ROWS,
    _TODAY,
    _TODAY_HEALTHY,
    _TODAY_MOCK,
)
from test_probe_fixture_runtime import _catalogued_dependents, _run_probe, _void_ids

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
