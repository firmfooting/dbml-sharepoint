"""Execute form-header-parity-probe.js under node against a mock web.

The probe measures; these tests check its plumbing only. The mock computes its own calculated
columns and its own header text, so no test asserts how a site behaves, only that the probe
prints AGREE where the two match, DISAGREE where they differ, voids what rests on a fixture that
did not hold, and leaves each observed reliance open.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import textwrap
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest
from _json_view import Json
from _paths import MANUAL
from _probe_runs import ended_with_report, run_probe, voided

from dbml_sharepoint.testing.node import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "form-header-parity-probe.js"
GATES = ("CONFIRMED", "ALLOW_WRITES")
READ = {"  const MODE = 'build';": "  const MODE = 'read';"}
ID = "form.display-form."
FIXTURES = [ID + f"fixture-parity-{n}" for n in (
    "list", "columns", "formatter", "site-zone", "date-order", "items", "header-rendered")]
PARITY = ID + "header-agrees-with-columns"
OBSERVED = [ID + n for n in (
    "observed-apostrophe-literal", "observed-blank-calculated-date",
    "observed-tostring-of-integer", "observed-number-of-now")]


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_form_header_parity_generator", MANUAL / "generate_form_header_parity_probe.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GEN = _generator()
ITEMS = GEN._items()
TITLES = [str(item["title"]) for item in ITEMS]

# The shapes are this mock's own; the probe never compares what a site gives with them.
_MOCK = textwrap.dedent(r"""
    const CONFIG = __CONFIG__;
    globalThis.window = { _spPageContextInfo: {
      webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe' } };
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const answer = (status, payload) => {
      const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
      return { ok: status >= 200 && status < 300, status, headers: { get: () => null },
        text: async () => text, json: async () => JSON.parse(text) };
    };
    const LIST_ID = '00000000-0000-4000-8000-00000000000a';
    const OWNER = 'dbml-sharepoint form-header-parity probe scratch list. Safe to delete.';
    const TODAY = '2026-10-21';
    const BLOCKED = CONFIG.blocked;
    if (CONFIG.browserOffset !== undefined) {
      Date.prototype.getTimezoneOffset = () => CONFIG.browserOffset;
    }
    const addDays = (iso, n) => new Date(Date.parse(iso + 'T00:00:00Z') + n * 86400000)
      .toISOString().slice(0, 10);
    let list = null;
    let fields = [];
    let items = [];
    let formatter = null;
    if (CONFIG.prior || CONFIG.foreign) {
      list = { Description: CONFIG.foreign ? 'Not made by the probe.' : OWNER };
    }
    if (CONFIG.prior) {
      fields = CONFIG.columns.map((c) => ({ Title: c.name, InternalName: c.name, TypeAsString:
        { choice: 'Choice', date: 'DateTime', calc: 'Calculated' }[c.kind] }));
      formatter = CONFIG.formatter;
      items = CONFIG.items.map((it, i) => ({ Id: i + 1, Title: it.title, Impact: it.Impact,
        Risk: it.Risk, Status: it.Status,
        Start: it.dueOffset === undefined ? it.Start : addDays(TODAY, it.dueOffset - CONFIG.days[it.Impact]) }));
    }
    const days = (it) => CONFIG.days[it.Impact] || 28;
    const wait = (it) => (it.Impact === 'Critical' ? 28 : it.Impact === 'High' ? 30 : 14);
    const months = (it) => ({ Low: 3, Medium: 6 }[it.Risk] || 12);
    const monthsLater = (it) => {
      const [y, m, d] = it.Start.split('-').map(Number);
      return new Date(Date.UTC(y, m - 1 + months(it), d)).toISOString().slice(0, 10);
    };
    // Calculated columns as dates (a blank Start is blank), rating as text.
    const calc = (it) => (it.Start ? { Cutoff: addDays(it.Start, days(it)), Review: monthsLater(it),
      Chased: addDays(it.Start, wait(it)) } : { Cutoff: null, Review: null, Chased: null });
    const rating = (it) => it.Risk || 'High';
    const ORDER = CONFIG.order || 'dmy';
    const inOrder = (iso, fix) => {
      const [y, m, d] = iso.split('-').map(fix);
      return (ORDER === 'mdy' ? [m, d, y] : ORDER === 'ymd' ? [y, m, d] : [d, m, y]).join('/');
    };
    const padded = (iso) => inOrder(iso, String);
    const plain = (iso) => inOrder(iso, Number);
    // The site's own zone: a stored instant is read back as the site's local day, as a site does.
    const SITE = CONFIG.tz || 'Australia/Melbourne';
    const eastOf = (ms) => {
      const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: SITE, hourCycle: 'h23',
        year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' })
        .formatToParts(new Date(ms)).map((x) => [x.type, Number(x.value)]));
      return (Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - Math.floor(ms / 1000) * 1000) / 60000;
    };
    const dayOfInstant = (text) => new Date(Date.parse(text) + eastOf(Date.parse(text)) * 60000).toISOString().slice(0, 10);
    const instantOfDay = (iso) => {
      const local = Date.parse(iso + 'T00:00:00Z');
      const guess = local - eastOf(local) * 60000;
      return new Date(local - eastOf(guess) * 60000).toISOString();
    };
    const textRow = (it) => {
      const c = calc(it);
      const row = { Title: it.Title, Modified: padded(TODAY) + ' 6:00 AM', Rating: rating(it) };
      if (it.Start) row.Start = padded(it.Start);
      for (const k of Object.keys(c)) row[k] = c[k] ? padded(c[k]) : '';
      return row;
    };
    const headerOf = (it) => {
      const c = calc(it);
      let review = c.Review;
      if (CONFIG.wrong === it.Title && review) review = addDays(review, 1);
      let reviewText = review ? plain(review) : '';
      if (CONFIG.badDate === it.Title && review) reviewText = '29.5/3/2026';
      const sep = CONFIG.colon ? ': ' : ' '; // the built header prints "Label: value"
      const lines = [it.Title, it.Status, it.Impact ? 'Impact ' + it.Impact : ''];
      if (c.Cutoff) {
        lines.push('Due by' + sep + plain(c.Cutoff), 'Review on' + sep + reviewText, 'Chased on' + sep + plain(c.Chased));
      }
      lines.push('Rating now' + sep + (CONFIG.wrongRating === it.Title ? 'Low' : rating(it)));
      if (it.Status === 'Open') lines.push(CONFIG.apostrophe);
      return lines.filter(Boolean).join('\n');
    };
    globalThis.document = {
      body: { appendChild: () => {} },
      createElement: () => {
        const frame = { style: {}, remove: () => {}, onload: null };
        Object.defineProperty(frame, 'src', { set(url) {
          frame.id = Number(/ID=(\d+)/.exec(url)[1]);
          setTimeout(() => frame.onload && frame.onload(), 0);
        } });
        Object.defineProperty(frame, 'contentDocument', { get() {
          if (CONFIG.noHeader) return { querySelectorAll: () => [{ innerText: 'Form body only', className: '' }] };
          const it = items.find((x) => x.Id === frame.id);
          const c = calc(it);
          const over = c.Cutoff && TODAY > c.Cutoff;
          return { querySelectorAll: () => [
            { innerText: headerOf(it), className: '' },
            { innerText: c.Cutoff ? 'Due by ' + plain(c.Cutoff) : '', className: over ? BLOCKED : 'plain' }] };
        } });
        return frame;
      },
    };
    const fail = (message) => answer(500, { error: { message: { value: message } } });
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      const body = typeof init.body === 'string' ? init.body : '';
      SENT.push({ method, path, body, merge: !!(init.headers && init.headers['X-HTTP-Method']) });
      if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
        GetContextWebInformation: { FormDigestValue: 'digest' } } });
      if (path.includes('/regionalsettings/timezone')) {
        return answer(200, { Id: 1, Information: CONFIG.zone || { Bias: -600, StandardBias: 0, DaylightBias: -60 } });
      }
      if (path.endsWith('/_api/web/lists') && method === 'POST') {
        list = { Description: JSON.parse(body).Description };
        return answer(201, { d: { Id: LIST_ID } });
      }
      if (path.includes("getbytitle('FormHeaderParity')") || path.includes('lists(guid')) {
        if (!list) return answer(404, { error: { message: { value: 'List does not exist.' } } });
        const rest = path.replace(/^.*?(getbytitle\('FormHeaderParity'\)|lists\(guid'[^']+'\))/, '');
        if (rest.startsWith('/recycle')) { list = null; return answer(200, { d: {} }); }
        if (rest.startsWith('/fields/createfieldasxml')) {
          const xml = JSON.parse(body).parameters.SchemaXml;
          fields.push({ Title: /Name='([^']+)'/.exec(xml)[1], InternalName: /Name='([^']+)'/.exec(xml)[1],
            TypeAsString: /Type='([^']+)'/.exec(xml)[1] });
          return answer(201, { d: {} });
        }
        if (rest === '/fields' && method === 'POST') {
          const sent = JSON.parse(body);
          fields.push({ Title: sent.Title, InternalName: sent.Title, TypeAsString: 'Calculated' });
          return answer(201, { d: {} });
        }
        if (rest.startsWith('/fields?')) return answer(200, { value: fields });
        if (rest.startsWith('/contenttypes?')) return answer(200, { value: [
          { Name: 'Folder', StringId: '0x0120' }, { Name: 'Item', StringId: '0x01' }] });
        if (rest.startsWith("/contenttypes('0x01')")) {
          if (method === 'POST') {
            if (!CONFIG.dropFormatter) formatter = JSON.parse(body).ClientFormCustomFormatter;
            return answer(204, '');
          }
          return answer(200, { ClientFormCustomFormatter: formatter });
        }
        if (rest === '/items' && method === 'POST') {
          const sent = JSON.parse(body);
          const it = { Id: items.length + 1, Title: sent.Title, Impact: sent.Impact, Risk: sent.Risk,
            Status: sent.Status, Start: sent.Start ? dayOfInstant(sent.Start) : null };
          items.push(it);
          return answer(201, { d: { Id: it.Id } });
        }
        if (rest.startsWith('/items?')) return answer(200, { value: items.map((i) => ({ Id: i.Id, Title: i.Title })) });
        const one = /^\/items\((\d+)\)(.*)$/.exec(rest);
        if (one) {
          const it = items.find((x) => x.Id === Number(one[1]));
          if (one[2].startsWith('/FieldValuesAsText')) return answer(200, textRow(it));
          if (method === 'POST') {
            const sent = JSON.parse(body);
            if ('Start' in sent) it.Start = sent.Start ? dayOfInstant(sent.Start) : null;
            return answer(204, '');
          }
          const c = calc(it);
          return answer(200, { Id: it.Id, Title: it.Title, Status: it.Status, Impact: it.Impact, Risk: it.Risk,
            Start: it.Start ? instantOfDay(it.Start) : null, Cutoff: c.Cutoff, Review: c.Review,
            Chased: c.Chased, Rating: rating(it), Wait: wait(it) });
        }
        return answer(200, { Id: LIST_ID, Description: list.Description,
          RootFolder: { ServerRelativeUrl: '/sites/probe/Lists/FormHeaderParity' },
          ListItemEntityTypeFullName: 'SP.Data.FormHeaderParityListItem' });
      }
      return answer(404, 'mock has no ' + path);
    };
""")  # noqa: E501 -- JavaScript mock lines

_COLUMNS = [{"name": n, "kind": "choice"} for n in ("Status", "Impact", "Risk")] + [
    {"name": "Start", "kind": "date"}] + [{"name": n, "kind": "calc"} for n in (
        "Wait", "Cutoff", "Review", "Chased", "Rating")]
CONFIG: dict[str, object] = {
    "days": GEN.DAYS, "items": ITEMS, "columns": _COLUMNS,
    "apostrophe": GEN.APOSTROPHE, "blocked": "blocked-class",
}

def _run(config: Mapping[str, object] | None = None, swaps: dict[str, str] | None = None,
         gates: tuple[str, ...] = GATES) -> tuple[dict[str, Json], list[Json], str]:
    merged = {**CONFIG, **(config or {})}
    # The scratch list carries a fixed title, so there is no per-run token to pin.
    quick = {
        "  const POLL_MS = 500;": "  const POLL_MS = 0;",
        "  const WAIT_MS = 30000;": "  const WAIT_MS = 50;",
    }
    return run_probe(_MOCK, PROBE, gates, merged, swaps={**quick, **(swaps or {})}, pin=False)


def _probe_formatter() -> str:
    match = re.search(r'^  "formatter": (".*"),?$', PROBE.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    return str(json.loads(match.group(1)))


def _blocked_class() -> str:
    text = PROBE.read_text(encoding="utf-8")
    match = re.search(r'^  "blockedClass": "(.*)",?$', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


CONFIG["blocked"] = _blocked_class()
PRIOR = {**CONFIG, "prior": True, "formatter": _probe_formatter()}


def _lines(output: str, head: str) -> list[str]:
    return [ln for ln in output.splitlines() if ln.startswith(head + " ")]


def _writes(sent: list[Json]) -> list[Json]:
    return [s for s in sent if s["method"] == "POST" and not s["path"].endswith("/contextinfo")]


def test_an_unconfirmed_probe_prints_its_plan_and_sends_nothing() -> None:
    rows, sent, output = _run(gates=())

    assert sent == [] and "Set CONFIRMED = true" in output
    assert rows[PARITY]["state"] == "open"


def test_every_item_agrees_when_the_header_shows_what_the_columns_hold() -> None:
    rows, _sent, output = _run()

    assert _lines(output, "DISAGREE") == []
    assert [ln.removeprefix("AGREE ") for ln in _lines(output, "AGREE")] == TITLES
    for row_id in FIXTURES:
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    assert rows[PARITY]["outcome"] == "AGREE" and rows[PARITY]["state"] == "settled"
    assert ended_with_report(output)


@pytest.mark.parametrize("colon", [True, False])
def test_the_label_reader_takes_the_value_with_or_without_a_colon(colon: bool) -> None:
    _rows, _sent, output = _run({"colon": colon})

    assert _lines(output, "DISAGREE") == []
    assert [ln.removeprefix("AGREE ") for ln in _lines(output, "AGREE")] == TITLES


def test_a_header_differing_from_its_column_prints_disagree_for_that_row_only() -> None:
    rows, _sent, output = _run({"wrong": "Case 05"})

    [line] = _lines(output, "DISAGREE")
    assert line.startswith("DISAGREE Case 05: Review header ") and "column" in line
    assert len(_lines(output, "AGREE")) == len(TITLES) - 1
    assert rows[PARITY]["outcome"] == "DISAGREE" and rows[PARITY]["state"] == "open"


def test_a_text_column_differing_from_its_header_prints_disagree() -> None:
    _rows, _sent, output = _run({"wrongRating": "Case 01"})

    [line] = _lines(output, "DISAGREE")
    assert line.startswith("DISAGREE Case 01: Rating header Low column ")


def test_a_read_run_compares_again_and_refreshes_only_the_due_day_items() -> None:
    rows, sent, output = _run(PRIOR, READ)

    assert _lines(output, "DISAGREE") == []
    assert len(_lines(output, "AGREE")) == len(TITLES)
    writes = _writes(sent)
    relative = [i for i in ITEMS if "dueOffset" in i]
    assert len(writes) >= len(relative) and all(s["merge"] for s in writes)
    assert all(s["path"].text.endswith(")") for s in writes)
    assert rows[PARITY]["outcome"] == "AGREE"


def test_the_four_unmeasured_reliances_are_observed_and_stay_open() -> None:
    rows, _sent, _output = _run()

    for row_id in OBSERVED:
        assert rows[row_id]["outcome"] == "OBSERVED" and rows[row_id]["state"] == "open", row_id
    assert "Can't start" in rows[OBSERVED[0]]["evidence"].text
    assert "REST null" in rows[OBSERVED[1]]["evidence"].text
    assert "whole numbers" in rows[OBSERVED[2]]["evidence"].text
    now = rows[OBSERVED[3]]["evidence"].text
    assert "yesterday): overdue colour shown" in now and "today): overdue colour not shown" in now
    assert "tomorrow): overdue colour not shown" in now


def test_a_header_with_a_malformed_date_is_reported_by_the_integer_observation() -> None:
    rows, _sent, output = _run({"badDate": "Case 05"})

    assert "29.5/3/2026" in rows[OBSERVED[2]]["evidence"].text
    assert _lines(output, "DISAGREE")[0].startswith("DISAGREE Case 05: Review header 29.5/3/2026")


def test_a_site_zone_other_than_the_generated_one_voids_the_comparison() -> None:
    rows, _sent, output = _run({"zone": {"Bias": -540, "StandardBias": 0, "DaylightBias": 0}})

    assert rows[ID + "fixture-parity-site-zone"]["outcome"] == "FAIL"
    assert rows[PARITY]["state"] == "void" and rows[OBSERVED[3]]["state"] == "void"
    assert _lines(output, "AGREE") == [] and _lines(output, "DISAGREE") == []
    assert PARITY in voided(rows) and ended_with_report(output)


def test_a_form_that_shows_no_header_voids_the_comparison_and_prints_no_verdict() -> None:
    rows, _sent, output = _run({"noHeader": True})

    assert rows[ID + "fixture-parity-header-rendered"]["outcome"] == "FAIL"
    assert PARITY in voided(rows) and set(OBSERVED) <= voided(rows)
    assert _lines(output, "AGREE") == [] and _lines(output, "DISAGREE") == []


def test_a_header_that_did_not_save_voids_the_comparison() -> None:
    rows, _sent, _output = _run({"dropFormatter": True})

    assert rows[ID + "fixture-parity-formatter"]["outcome"] == "FAIL"
    assert PARITY in voided(rows)


def test_a_site_writing_dates_in_another_order_voids_the_comparison() -> None:
    rows, _sent, _output = _run(swaps={'"dateOrder": "dmy"': '"dateOrder": "mdy"'})

    assert rows[ID + "fixture-parity-date-order"]["outcome"] == "FAIL"
    assert PARITY in voided(rows) and ID + "fixture-parity-items" in voided(rows)


def test_a_same_title_list_without_the_marker_is_never_touched() -> None:
    rows, sent, _output = _run({"foreign": True})

    assert rows[ID + "fixture-parity-list"]["outcome"] == "FAIL" and not _writes(sent)


def test_an_earlier_list_is_recycled_only_with_cleanup() -> None:
    rows, sent, _output = _run({"prior": True})
    assert rows[ID + "fixture-parity-list"]["outcome"] == "FAIL" and not _writes(sent)

    _rows, sent, _output = _run({"prior": True}, swaps={
        "  const CLEANUP = false;": "  const CLEANUP = true;"})
    assert any(s["path"].endswith("/recycle") for s in _writes(sent))


@pytest.mark.parametrize(("offset", "outcome"), [(-600, "SAME AS SITE"), (-660, "SAME AS SITE"),
                                                  (480, "DIFFERS")])
def test_the_browser_zone_row_says_whether_the_run_differed_from_the_site(
    offset: int, outcome: str,
) -> None:
    rows, _sent, _output = _run({"browserOffset": offset})

    row = rows[ID + "browser-zone-differs"]
    assert row["outcome"] == outcome
    assert row["state"] == ("settled" if outcome == "DIFFERS" else "open")


def test_the_grid_covers_the_hard_cases() -> None:
    starts = {i["Start"] for i in ITEMS}
    assert {"2026-01-31", "2024-02-29", "2025-12-31", None} <= starts
    assert any(i["Impact"] is None for i in ITEMS) and any(i["Risk"] is None for i in ITEMS)
    assert any(i["Impact"] == GEN.UNLISTED for i in ITEMS)
    assert sorted(i["dueOffset"] for i in ITEMS if "dueOffset" in i) == [-1, 0, 1]
    assert len(TITLES) == len(set(TITLES))


def test_the_committed_probe_is_the_generator_output() -> None:
    assert PROBE.read_text(encoding="utf-8") == GEN.render()


def test_a_mistyped_mode_fails_closed_by_name_and_sends_nothing() -> None:
    rows, sent, output = _run(swaps={"  const MODE = 'build';": "  const MODE = 'bild';"})

    assert sent == [] and rows == {}
    assert "MODE is 'bild'" in output and "TypeError" not in output


def test_the_revision_is_derived_from_the_probe_text() -> None:
    js = PROBE.read_text(encoding="utf-8")
    stamped = re.search(r"REVISION: ([0-9a-f]{8})", js)
    assert stamped is not None
    neutral = js.replace(stamped.group(1), "00000000")
    assert stamped.group(1) == hashlib.sha256(neutral.encode()).hexdigest()[:8]
    assert f"probe revision {stamped.group(1)}." in js


def _generated_run(
    tmp_path: Path, zone: str, order: str,
) -> tuple[dict[str, Json], list[Json], str]:
    probe = tmp_path / "probe.js"
    text = GEN.render(zone, order)
    probe.write_text(text, encoding="utf-8", newline="\n")
    match = re.search(r'^  "formatter": (".*"),?$', text, re.MULTILINE)
    assert match is not None
    config = {
        **CONFIG, "tz": zone, "order": order, "zone": GEN._zone_biases(zone),
        "formatter": json.loads(match.group(1)),
    }
    quick = {
        "  const POLL_MS = 500;": "  const POLL_MS = 0;",
        "  const WAIT_MS = 30000;": "  const WAIT_MS = 50;",
    }
    return run_probe(_MOCK, probe, GATES, config, swaps=quick, pin=False)


# A daylight change day and the day after, per zone, among the dates the probe writes.
@pytest.mark.parametrize(("zone", "edge"), [
    ("America/Los_Angeles", ("2026-03-08", "2026-03-09")),
    ("Australia/Melbourne", ("2026-04-05", "2026-04-06")),
])
def test_every_written_date_is_the_site_local_midnight_of_the_intended_day(
    tmp_path: Path, zone: str, edge: tuple[str, str],
) -> None:
    _rows, sent, output = _generated_run(tmp_path, zone, "dmy")

    written: dict[str, str] = {}
    for request in _writes(sent):
        text = request["body"].text
        body = Json.loads(text) if text else Json({})
        if body.get("Start").value:
            written[body["Title"].text] = body["Start"].text
    items = {str(i["title"]): i for i in GEN._items()}
    assert set(written) == {t for t, i in items.items() if i["Start"] or "dueOffset" in i}
    for title, instant in written.items():
        item = items[title]
        # The mock's own day is 2026-10-21; a relative item starts its lead time before the due day.
        days = GEN.DAYS.get(str(item["Impact"]), 0)
        lead = timedelta(days=int(str(item.get("dueOffset", 0))) - days)
        want =str(item["Start"]) if item["Start"] else (date(2026, 10, 21) + lead).isoformat()
        local = datetime.fromisoformat(instant).astimezone(ZoneInfo(zone))
        assert (local.date().isoformat(), local.time()) == (want, time(0)), (title, instant)
    assert set(edge) <= {str(i["Start"]) for i in items.values()}
    assert _lines(output, "DISAGREE") == []


@pytest.mark.parametrize("order", ["dmy", "mdy", "ymd"])
def test_the_date_order_argument_sets_the_probe_and_the_site_text_it_reads(
    tmp_path: Path, order: str,
) -> None:
    assert GEN.render("America/Los_Angeles", order).count(f'"dateOrder": "{order}"') == 1

    rows, _sent, output = _generated_run(tmp_path, "America/Los_Angeles", order)

    assert rows[ID + "fixture-parity-date-order"]["outcome"] == "PASS"
    assert rows[PARITY]["outcome"] == "AGREE"
    assert _lines(output, "DISAGREE") == []


def test_a_date_order_the_form_does_not_know_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="'dmy ' is not one of dmy, mdy, ymd"):
        GEN.render("Australia/Melbourne", "dmy ")
