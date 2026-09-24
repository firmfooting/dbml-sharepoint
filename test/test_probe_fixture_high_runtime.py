"""Execute the High-tier probes of #559 whose rows rested on an unread fixture.

Each probe runs against a mock SharePoint more than once: healthy, as the
control that shows it still measures, and once per fixture that does not hold,
which must void exactly the rows that rest on it and send none of their writes.
"""

import textwrap
from typing import Any

import pytest
from _node import NODE
from test_probe_fixture_runtime import _run_probe, _void_ids

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


# --------------------------------------------------------------------------
# Item 6: today-semantics reads both rules and the =TODAY() default back.
# --------------------------------------------------------------------------
#: A fresh scratch list. A stored rule reads back without brackets, as measured
#: on 2026-09-02, and refuses a value later than the save.
_TODAY_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    let listMade = false;
    const fields = new Map();
    const items = new Map();
    let nextItem = 1;
    const FIELD = /\\/fields\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)/;
    const ITEM = /\\/items\\((\\d+)\\)/;
    const refused = (status, value) => jsonResponse(status, { error: { message: { value } } });

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = raw ? JSON.parse(raw) : {};
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) return digestResponse();
      if (path.startsWith('web/regionalsettings/timezone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, DaylightBias: 0 } });
      }
      if (path === 'web/lists' && method === 'POST') {
        listMade = true;
        return jsonResponse(201, { d: { Id: 'list-1', Title: sent.Title } });
      }
      if (!listMade) return refused(404, 'List does not exist.');
      const named = FIELD.exec(path);
      if (named) {
        const held = fields.get(named[1]);
        if (!held) return refused(400, 'Column does not exist.');
        if (verb === 'MERGE') {
          if (!(CONFIG.dropRule || []).includes(named[1])) {
            held.ValidationFormula = sent.ValidationFormula.replace(/[[\\]]/g, '');
          }
          return jsonResponse(204, {});
        }
        if (CONFIG.ruleReadStatus) return jsonResponse(CONFIG.ruleReadStatus, { error: 'no' });
        return jsonResponse(200, { ValidationFormula: held.ValidationFormula });
      }
      if (path.endsWith('/fields')) {
        fields.set(sent.Title, { ValidationFormula: '' });
        return jsonResponse(201, { d: { Title: sent.Title } });
      }
      const item = ITEM.exec(path);
      if (item) return jsonResponse(200, items.get(Number(item[1])));
      if (path.endsWith('/items')) {
        const now = Date.now();
        for (const name of ['D', 'W']) {
          const ruled = fields.get(name).ValidationFormula && name in sent;
          if (ruled && Date.parse(sent[name]) > now) return refused(400, `${name} is after`);
        }
        const id = nextItem;
        nextItem += 1;
        const midnight = new Date();
        midnight.setHours(0, 0, 0, 0);
        items.set(id, { Id: id, Created: new Date(now).toISOString(),
          T: CONFIG.defaultFires ? midnight.toISOString() : null });
        return jsonResponse(201, { d: { Id: id } });
      }
      return jsonResponse(200, { ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' });
    };
""")

_TODAY = "today-semantics-probe.js"
_RULES = "formula.datetime.fixture-today-now-rules-stored"
_DEFAULT = "formula.datetime.today-function-default-value"
_SAVE_ROWS = {
    "formula.datetime.today-allows-two-days-ago",
    "formula.datetime.today-allows-yesterday",
    "formula.datetime.today-allows-site-midnight-today",
    "formula.datetime.today-allows-utc-midnight-today",
    "formula.datetime.today-rejects-tomorrow",
    "formula.datetime.now-function-minus-20h",
    "formula.datetime.now-function-minus-12h",
    "formula.datetime.now-function-minus-1h",
    "formula.datetime.now-function-plus-1h",
    "formula.datetime.now-function-plus-12h",
    "formula.datetime.now-function-plus-20h",
}
_TODAY_HEALTHY: dict[str, Any] = {"defaultFires": True}


def _saves(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "POST" and r["path"].endswith("/items")]


def test_today_semantics_measures_against_rules_it_read_back() -> None:
    rows, sent = _run_probe(_TODAY_MOCK, _TODAY_HEALTHY, _TODAY)

    assert rows[_RULES]["outcome"] == "PASS", rows[_RULES]
    assert rows[_DEFAULT]["outcome"] == "PASS", rows[_DEFAULT]
    assert rows["formula.datetime.today-allows-yesterday"]["outcome"] == "SAVED"
    assert rows["formula.datetime.today-rejects-tomorrow"]["outcome"] == "REFUSED"
    assert rows["formula.datetime.now-function-plus-1h"]["outcome"] == "REFUSED"
    assert not _void_ids(rows)
    assert len(_saves(sent)) == 1 + len(_SAVE_ROWS)


@pytest.mark.parametrize("dropped", ["D", "W"])
def test_today_semantics_voids_the_save_rows_when_a_rule_was_dropped(dropped: str) -> None:
    """A MERGE answered 204 for a rule never kept, and every save then read as allowed."""
    rows, sent = _run_probe(_TODAY_MOCK, {**_TODAY_HEALTHY, "dropRule": [dropped]}, _TODAY)

    assert rows[_RULES]["outcome"] == "FAIL", rows[_RULES]
    assert f"{dropped}.ValidationFormula differs" in rows[_RULES]["evidence"]
    assert _void_ids(rows) == _SAVE_ROWS
    assert all(_RULES in rows[row_id]["evidence"] for row_id in _SAVE_ROWS)
    assert len(_saves(sent)) == 1


def test_today_semantics_voids_the_save_rows_when_the_rules_do_not_read_back() -> None:
    rows, sent = _run_probe(_TODAY_MOCK, {**_TODAY_HEALTHY, "ruleReadStatus": 429}, _TODAY)

    assert rows[_RULES]["outcome"] == "FAIL", rows[_RULES]
    assert "the read was throttled (HTTP 429)" in rows[_RULES]["evidence"]
    assert _void_ids(rows) == _SAVE_ROWS
    assert len(_saves(sent)) == 1


def test_today_semantics_does_not_report_a_default_that_never_fired() -> None:
    """The row was a literal 'PASS' that printed T as null."""
    rows, _ = _run_probe(_TODAY_MOCK, {"defaultFires": False}, _TODAY)

    assert rows[_DEFAULT]["outcome"] == "NOT ESTABLISHED", rows[_DEFAULT]
    assert "T stored as null" in rows[_DEFAULT]["evidence"]
    assert rows[_RULES]["outcome"] == "PASS"
