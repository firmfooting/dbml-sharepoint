# test/test_probe_runtime.py
"""Execute the rendered probes against a mock SharePoint.

`test_probes.py` proves a probe PARSES. It cannot prove what a probe
CONCLUDES, and a probe's conclusions are the whole product: nobody reads a
probe's source to learn what SharePoint does, they read the result table it
prints into a transcript.

The failure this closes is a row that answers a question the run did not
establish. An operator reads "UNCHANGED (both served)" as a measurement,
pastes it back, and the finding is recorded against a run whose controls had
already collapsed. Nothing in the probe, the render or `node --check` can see
that, because the script ran perfectly and printed a sentence.

So: run the real rendered file, on a SharePoint that behaves the way a live
run has actually misbehaved, and assert on the outcomes it records.

Node is required; the tests skip without it rather than failing, since it is
not a dependency of the package.
"""

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run
from _paths import MANUAL

PROBE = MANUAL / "threshold-index-probe.js"

# A SharePoint thin enough to describe in one screen and controllable in the
# four ways a live run has actually gone wrong: what ItemCount reads, which
# columns come back indexed, whether an index MERGE takes, and what a CAML
# query answers.
_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      location: { origin: 'https://example.sharepoint.com' },
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
        webServerRelativeUrl: '/sites/test',
        userLoginName: 'probe@example.com',
        userId: 11,
      },
    };

    // Field-read sabotage is armed by a LOG LINE, never by a read count. A
    // count pins the test to today's request pattern rather than to the call
    // it means, and it shifts the moment any question is added earlier in the
    // run, so the test then measures a different read while still passing.
    let armed = CONFIG.failReadsAfter === null;
    let sabotageLeft = CONFIG.failReadsAfter ? CONFIG.failReadsAfter.count : 0;
    const realLog = console.log;
    console.log = (...parts) => {
      if (!armed && String(parts[0] || '').includes(CONFIG.failReadsAfter.marker)) {
        armed = true;
      }
      realLog(...parts);
    };

    // The views SharePoint now holds, keyed by title, exactly as the creates
    // left them. Stored VERBATIM so a read-back mismatch is a defect in the
    // probe rather than a mock paraphrasing what it was handed.
    const views = new Map();

    const FIELD_RE = /getbyinternalnameortitle\\('([^']+)'\\)/;

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // First matching rule wins, so a test prepends the one shape it is about
    // and inherits the rest of a healthy run.
    const renderRows = (viewXml) => {
      for (const rule of CONFIG.render) {
        const hit = (rule.contains || []).every((s) => viewXml.includes(s))
          && !(rule.notContains || []).some((s) => viewXml.includes(s));
        if (!hit) continue;
        if (!rule.ok) return jsonResponse(rule.status || 500, { error: 'refused' });
        const rows = (rule.ids || []).map(
          (id) => (rule.noIds ? { Title: `Row ${id}` } : { ID: String(id) }),
        );
        return jsonResponse(200, {
          Row: rows, FirstRow: 1, LastRow: rows.length,
        });
      }
      return jsonResponse(200, { Row: [], FirstRow: 0, LastRow: 0 });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const body = opts.body === undefined ? null : String(opts.body);

      if (u.includes('/contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.includes('RenderListDataAsStream')) {
        const sent = JSON.parse(body || '{}');
        return renderRows(String((sent.parameters || {}).ViewXml || ''));
      }
      if (u.includes('web/currentuser')) return jsonResponse(200, { Id: 11 });

      const field = FIELD_RE.exec(u);
      if (field) {
        const name = field[1];
        if (method === 'GET') {
          if (armed && sabotageLeft > 0 && CONFIG.failReadsAfter
              && CONFIG.failReadsAfter.field === name) {
            sabotageLeft -= 1;
            return jsonResponse(500, { error: 'the field read failed' });
          }
          return jsonResponse(200, {
            InternalName: name,
            Indexed: CONFIG.indexed[name] === true,
            AutoIndexed: false,
          });
        }
        // A MERGE. Indexed only moves when the test says the write takes,
        // which is how a 200 that changed nothing is expressed here.
        const wanted = JSON.parse(body || '{}');
        if (typeof wanted.Indexed === 'boolean' && CONFIG.mergeSticks) {
          CONFIG.indexed[name] = wanted.Indexed;
        }
        return jsonResponse(204, {});
      }

      if (u.includes('/items')) return jsonResponse(200, { value: CONFIG.items });
      if (u.includes('/views')) {
        if (method === 'POST') {
          const sent = JSON.parse(body || '{}');
          if (views.has(sent.Title)) {
            return jsonResponse(400, { error: 'a view of that title exists' });
          }
          views.set(sent.Title, {
            Title: sent.Title, ViewQuery: sent.ViewQuery, RowLimit: sent.RowLimit,
            Paged: sent.Paged, PersonalView: sent.PersonalView,
            ServerRelativeUrl: `/sites/test/Lists/Probe/${views.size}.aspx`,
          });
          return jsonResponse(201, { Id: `view-${views.size}` });
        }
        return jsonResponse(200, { value: [...views.values()] });
      }
      if (/getbytitle\\('[^']*'\\)($|\\?)/.test(u)) {
        return jsonResponse(200, {
          Id: 'list-1',
          ItemCount: u.includes('Parent') ? CONFIG.parentCount : CONFIG.itemCount,
          ListItemEntityTypeFullName: 'SP.Data.ProbeListItem',
        });
      }
      return jsonResponse(200, { value: [] });
    };
""")

#: A run where nothing has gone wrong: the list is past the threshold and on a
#: declared checkpoint, every control holds its intended index state, and the
#: twins match the same rows. Each test changes one thing.
_HEALTHY: dict[str, Any] = {
    "itemCount": 6000,
    "parentCount": 6000,
    "indexed": {
        "Bucket": True, "ClosedAt": True, "Owner": True, "Parent": True,
        "NotNullIdx": True, "Shadow": False, "NotNullUni": False, "SortBait": False,
    },
    "mergeSticks": True,
    "failReadsAfter": None,
    "items": [{"Id": 1, "OwnerId": 11, "Title": "Row 000001"}],
    "render": [
        {"contains": ["Name='Bucket'"], "ok": True, "ids": list(range(1, 61))},
        {"contains": ["Name='Shadow'"], "ok": True, "ids": list(range(1, 61))},
        {"contains": ["Name='ClosedAt'"], "ok": True, "ids": list(range(61, 121))},
        # The guard alone matches every row, so it is refused like any
        # unfiltered query at this size.
        {"contains": ['<Where><Or><IsNotNull><FieldRef Name="ID"/>'],
         "ok": False, "status": 500},
    ],
}


def _probe_js() -> str:
    """The rendered probe with its gates opened and its result table exposed.

    The gates are flipped rather than the file being re-rendered with
    different values: what an operator pastes is what these tests must run,
    and a re-render could diverge from the committed artefact.
    """
    js = PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "\n  report();\n",
        "\n  console.log('__ROWS__' + JSON.stringify(RESULTS));\n  report();\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice in before report()"
    return exposed


def _run_probe(**changes: Any) -> dict[str, str]:
    """Run the probe against `_HEALTHY` plus `changes`, and return id -> outcome.

    `indexed` and `render` merge rather than replace: a test says the one
    thing it is about and inherits a healthy run for everything else.
    """
    config = json.loads(json.dumps(_HEALTHY))
    for key, value in changes.items():
        if key == "indexed":
            config["indexed"].update(value)
        elif key == "render":
            config["render"] = list(value) + config["render"]
        else:
            config[key] = value
    script = _HARNESS.replace("__CONFIG__", json.dumps(config)) + "\n" + _probe_js()
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {
        row["id"]: row["outcome"]
        for row in json.loads(line.removeprefix("__ROWS__"))
    }


#: Every row `measureGuard` gates behind its dependency check. Named here
#: rather than spelled into each test, because the gate is the thing under
#: test and a row quietly dropping out of it is the regression.
_GUARD_ROWS = (
    "scale.index.fixture-twins-match-same-rows",
    "scale.threshold.guarded-comparison-indexed-text",
    "scale.threshold.guarded-isnull-indexed-datetime",
    "scale.threshold.guarded-comparison-unindexed-text",
    "scale.threshold.guard-alone-every-row",
    "view.threshold-render.indexed-filter",
    "view.threshold-render.indexed-filter-guarded",
    "view.threshold-render.unindexed-filter",
    "view.threshold-render.unindexed-filter-guarded",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_healthy_run_answers_the_guard_questions() -> None:
    """The control for every test below.

    Without it, a change that made the probe record NOT ESTABLISHED for
    everything would pass all of them, and this file would be measuring a
    probe that had stopped measuring anything.
    """
    rows = _run_probe()
    assert rows["scale.index.fixture-indexes-set"] == "CONFIRMED"
    assert rows["scale.index.fixture-twins-match-same-rows"] == "AGREE"
    guarded = "UNCHANGED (both served)"
    assert rows["scale.threshold.guarded-comparison-indexed-text"] == guarded
    assert rows["scale.threshold.guarded-isnull-indexed-datetime"] == guarded
    assert rows["view.threshold-render.indexed-filter"] == "MANUAL (unobserved)"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_failed_index_control_leaves_every_guard_row_unestablished() -> None:
    """`fixture-indexes-set` voiding the table must void the guard rows with it.

    Run of 2026-08-17: SharePoint had indexed Shadow between runs, so the
    negative control had expired. `measureGuard` gated only on ItemCount, so
    the two guarded comparisons still answered "UNCHANGED (both served)" one
    screen below `fixture-indexes-set` reporting TABLE VOID, and the four
    rendered views were still handed to an operator labelled INDEXED and
    UNINDEXED.

    Nothing there is established. The labels those rows are ABOUT are the
    labels `fixture-indexes-set` just said are wrong.
    """
    rows = _run_probe(indexed={"Shadow": True}, mergeSticks=False)
    assert rows["scale.index.negative-control-clearable"] == "DID NOT STICK"
    assert rows["scale.index.fixture-indexes-set"] == "MISLABELLED, TABLE VOID"
    answered = [row for row in _GUARD_ROWS if not rows[row].startswith("NOT ESTABLISHED")]
    assert not answered, (
        f"the index control failed and {answered} still answered. Every one of "
        f"them is an indexed-versus-unindexed comparison, so the labels it "
        f"rests on are the ones `fixture-indexes-set` reported wrong."
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "shadow"),
    [
        ("the request was refused", {"ok": False, "status": 500}),
        ("no row carried a readable ID",
         {"ok": True, "ids": list(range(1, 61)), "noIds": True}),
    ],
)
def test_twins_that_could_not_be_read_are_not_recorded_as_disagreeing(
    why: str, shadow: dict[str, Any],
) -> None:
    """`fixture-twins-match-same-rows` asks whether the twins match the same
    rows, and an unreadable half does not answer it either way.

    DISAGREE is an answer: report() counts it, and the unindexed guarded
    comparison reads it as the seed having drifted, which sends an operator to
    reconcile a fixture that may be fine. A refused request and a response
    whose rows carry no ID say only that the comparison could not be made.
    """
    rows = _run_probe(render=[{"contains": ["Name='Shadow'"], **shadow}])
    twins = rows["scale.index.fixture-twins-match-same-rows"]
    assert twins.startswith("NOT ESTABLISHED"), (
        f"{why}, and the twin check recorded {twins!r}. Nothing was compared, "
        f"so nothing disagreed."
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreadable_negative_control_is_not_reported_as_needing_no_clear() -> None:
    """A read that failed says nothing about whether Shadow is indexed.

    `wasIndexed` folded the read failure into `false`, so a 500 on the field
    read recorded NOT NEEDED and the evidence line said "Shadow is already
    unindexed", which the probe had not established and could not have. The
    negative control is what every indexed-versus-unindexed row rests on, so
    an unverified one is the quietest way this table goes wrong.
    """
    rows = _run_probe(
        # Armed off the item-count log line rather than a read count:
        # clearControl makes the first read of Shadow after that row is
        # recorded.
        failReadsAfter={
            "marker": "scale.threshold.fixture-item-count:",
            "field": "Shadow",
            "count": 1,
        },
    )
    clear = rows["scale.index.negative-control-clearable"]
    assert clear.startswith("NOT ESTABLISHED"), (
        f"the Shadow read failed and the clear check recorded {clear!r}. A "
        f"failed read is not a reading of Indexed=false."
    )


# --------------------------------------------------------------------------
# list-settings-probe.js: the Description control, and the one re-read it is
# allowed before it voids the twenty-six settings rows behind it.
# --------------------------------------------------------------------------
SETTINGS_PROBE = MANUAL / "list-settings-probe.js"

#: The delay these tests substitute for the shipped 1500 ms. The re-read
#: DECISION is what they are about, not how long it waits, and three runs of
#: real sleeping buys nothing.
_TEST_REREAD_MS = 5

#: Thirteen settings on each of the two containers. Named as a number because
#: what a failed control has to do is void ALL of them.
_SETTINGS_ROW_COUNT = 26

_SETTINGS_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // What a container reads before the probe writes to it. Values chosen so
    // every candidate has a differing target: a row already at its target
    // records NOT ESTABLISHED and measures nothing.
    const DEFAULTS = {
      EnableAttachments: true, EnableVersioning: false, EnableMinorVersions: false,
      EnableModeration: false, EnableFolderCreation: false, NoCrawl: false,
      Direction: 'none', ContentTypesEnabled: false, ReadSecurity: 1,
      WriteSecurity: 1, IrmEnabled: false, IrmExpire: false, IrmReject: false,
    };

    // The scratch containers, keyed by title. `lag` is how many further reads
    // of Description still answer with the value the container held BEFORE the
    // MERGE, which is the shape run 20260906T061520 recorded: a 204 whose
    // readback had not caught up with it.
    const lists = new Map();

    const TITLE = /getbytitle\\('([^']+)'\\)/;
    const SELECT = /[?&]\\$select=([A-Za-z]+)/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body));

      if (u.includes('/contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u.endsWith('/web/lists') && method === 'POST') {
        lists.set(sent.Title, {
          props: {
            ...DEFAULTS,
            Title: sent.Title,
            Description: sent.Description,
            BaseTemplate: sent.BaseTemplate,
          },
          pending: null,
          lag: 0,
        });
        return jsonResponse(201, { Title: sent.Title });
      }

      const named = TITLE.exec(u);
      if (!named) return jsonResponse(404, { error: 'no such endpoint' });
      const held = lists.get(named[1]);
      if (!held) return jsonResponse(404, { error: 'list not found' });

      if (verb === 'MERGE') {
        for (const [name, value] of Object.entries(sent)) {
          if (name === '__metadata') continue;
          // A property SP.List does not have, refused 500, which is the
          // status every refusal this project has recorded came back as.
          if (!(name in held.props)) {
            return jsonResponse(500, { error: `no property named ${name}` });
          }
          if (name === 'Description') {
            held.pending = value;
            held.lag = CONFIG.descriptionLagReads;
            if (held.lag === 0) held.props.Description = value;
          } else if (CONFIG.settingsStick) {
            held.props[name] = value;
          }
        }
        return jsonResponse(204, {});
      }

      const selected = SELECT.exec(u);
      if (!selected) return jsonResponse(200, { ...held.props });
      const name = selected[1];
      if (!(name in held.props)) {
        return jsonResponse(400, { error: `no property named ${name}` });
      }
      if (name === 'Description' && held.lag > 0) {
        const stale = held.props.Description;
        held.lag -= 1;
        if (held.lag === 0) held.props.Description = held.pending;
        return jsonResponse(200, { Description: stale });
      }
      return jsonResponse(200, { [name]: held.props[name] });
    };
""")


def _settings_probe_js() -> str:
    """The rendered settings probe with its gates open and its table exposed.

    Edited by replacement rather than re-rendered, for the reason `_probe_js`
    gives. The re-read delay is replaced too, and that replacement doubles as
    the pin on the shipped value: change 1500 in the probe and this fails.
    """
    js = SETTINGS_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    shortened = js.replace(
        "  const CONTROL_REREAD_MS = 1500;",
        f"  const CONTROL_REREAD_MS = {_TEST_REREAD_MS};",
        1,
    )
    assert shortened != js, "the control re-read delay is not spelled as this test expects"
    exposed = shortened.replace(
        "\n  report();\n",
        "\n  console.log('__ROWS__' + JSON.stringify(RESULTS));\n  report();\n",
        1,
    )
    assert exposed != shortened, "the result table dump did not splice in before report()"
    return exposed


def _run_settings_probe(
    description_lag_reads: int = 0, settings_stick: bool = True,
) -> dict[str, dict[str, str]]:
    """Run the settings probe and return id -> the whole recorded row.

    The whole row, not the outcome alone: what a re-read has to leave behind
    is EVIDENCE naming it, and an outcome of PASS says nothing about that.
    """
    config = {
        "descriptionLagReads": description_lag_reads,
        "settingsStick": settings_stick,
    }
    script = (
        _SETTINGS_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _settings_probe_js()
    )
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_settings_run_whose_readback_keeps_up_needs_no_re_read() -> None:
    """The control for the two tests below, and the shape of a healthy run.

    Without it, a re-read that fired on every run would pass both of them
    while quietly halving the probe's ability to fail.
    """
    rows = _run_settings_probe()

    for control in ("field.list.control-description-sticks",
                    "library.doc-lib.control-description-sticks"):
        assert rows[control]["outcome"] == "PASS"
        assert "re-read" not in rows[control]["evidence"], (
            f"{control} re-read a Description that had already read back. The "
            f"re-read exists for a readback that lagged, and firing it here "
            f"would hide a method that answers late every time."
        )
    assert rows["field.list.attachments-sticks"]["outcome"] == "STICKS"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_readback_that_lags_the_merge_is_re_read_once() -> None:
    """Run 20260906T061520: both controls failed on a 204 whose readback was
    not yet showing the marker, and 26 settings rows were voided with them.

    The same file passed the same control three hours earlier
    (20260906T015302) and forty minutes later (20260906T062002), so the
    method was not broken and the rows should never have been voided. One
    re-read is what tells those two cases apart.
    """
    rows = _run_settings_probe(description_lag_reads=1)

    for control in ("field.list.control-description-sticks",
                    "library.doc-lib.control-description-sticks"):
        assert rows[control]["outcome"] == "PASS", (
            f"{control} recorded {rows[control]['outcome']!r} for a readback "
            f"that was one read behind the MERGE, which voids 26 measured rows."
        )
        assert f"after one re-read {_TEST_REREAD_MS} ms later" in rows[control]["evidence"]
        assert "204-to-read lag" in rows[control]["evidence"]
    assert rows["field.list.attachments-sticks"]["outcome"] == "STICKS"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_that_never_reads_back_still_voids_every_settings_row() -> None:
    """The re-read is bounded at one, so a method that is actually broken
    still voids what it always voided.

    A retry loop passes anything eventually, and a positive control that
    cannot fail is worse than none: every row below it would then be reported
    as measured on a container nothing had been written to.
    """
    rows = _run_settings_probe(description_lag_reads=99)

    control = rows["field.list.control-description-sticks"]
    assert control["outcome"] == "CONTROL FAILED, METHOD VOID"
    # Both strings, quoted, so a difference of length or trailing whitespace
    # is visible. The failed live run's evidence showed only one of them and
    # the two looked identical.
    assert '"dbml-sharepoint list-settings probe list. Safe to delete."' in control["evidence"]
    assert (
        'the marker written was "dbml-sharepoint list-settings probe list. '
        'Safe to delete. probe-control-'
    ) in control["evidence"]
    assert "still differing" in control["evidence"]

    voided = [row for row in rows.values() if row["state"] == "void"]
    assert len(voided) == _SETTINGS_ROW_COUNT


# --------------------------------------------------------------------------
# library-grouping-probe.js: the negative control that tells a group-by
# SharePoint HONOURED from one it IGNORED.
# --------------------------------------------------------------------------
GROUPING_PROBE = MANUAL / "library-grouping-probe.js"

#: The six measurements the two grouping controls gate. A failed control has
#: to void all of them, and run 20260908T015538 is what that looks like.
_GROUPING_MEASUREMENTS = (
    "library.view.group-by-multi-value-choice",
    "library.view.group-by-multi-value-lookup",
    "library.view.group-by-lookup-column",
    "library.view.group-by-name-column",
    "library.view.group-by-null-title",
    "library.view.multi-value-group-by-stored-on-view",
)

_GROUPING_CONTROL = "library.view.control-missing-group-column-ungrouped"

#: A SharePoint that answers a grouped RenderListDataAsStream the way run
#: 20260908T015538 recorded: a collapsed query returns one row per distinct
#: value carrying `<Field>.COUNT.group`, `.newgroup` and `.groupindex`, an
#: expanded one returns the files, and a lookup label is an array of
#: `{lookupId, lookupValue}`. What the CONFIG varies is the one thing that run
#: could not explain: what comes back for a <GroupBy> naming a column that does
#: not exist.
_GROUPING_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // Every container the probe makes, keyed by title. `fields` holds what a
    // field read answers, `items` the rows, in creation order.
    const lists = new Map();
    const views = new Map();
    let nextListId = 1;
    let nextItemId = 1;

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const FILE_NAME = /Files\\/add\\(url='([^']+)'/;
    const SCHEMA = {
      type: /Type="([^"]+)"/, name: /Name="([^"]+)"/,
      list: /List="\\{([^}]+)\\}"/, mult: /Mult="TRUE"/,
    };
    const GROUP_BY = /<GroupBy Collapse="(TRUE|FALSE)"><FieldRef Name="([^"]+)"\\/>/;

    const listById = (id) => [...lists.values()].find((held) => held.Id === id);

    // One rendered cell. A lookup answers with the shape the live run showed,
    // an array of {lookupId, lookupValue}, which is why the probe's label test
    // for a display field does not match one.
    const cellOf = (held, item, name) => {
      const field = held.fields.get(name);
      if (field && (field.TypeAsString === 'Lookup' || field.TypeAsString === 'LookupMulti')) {
        const target = listById(field.LookupList.replace(/[{}]/g, ''));
        const raw = item[`${name}Id`];
        const ids = raw === undefined ? [] : (Array.isArray(raw) ? raw : [raw]);
        return ids.map((id) => ({
          lookupId: id,
          lookupValue: (target.items.find((row) => row.Id === id) || {}).Title,
          isSecretFieldValue: false,
        }));
      }
      const held_value = item[name];
      return held_value === undefined || held_value === null ? '' : held_value;
    };

    const flatRows = (held, fields) => held.items.map((item) => {
      const row = {};
      for (const name of fields) row[name] = cellOf(held, item, name);
      return row;
    });

    // A group row, keyed the way the live run's collapsed query keyed one.
    const groupRow = (label, count) => (name) => ({
      [name]: label,
      [`${name}.urlencoded`]: '%3B%23%3B%23',
      [`${name}.singleurlencoded`]: '',
      [`${name}.COUNT.group`]: String(count),
      [`${name}.newgroup`]: '1',
      [`${name}.groupindex`]: '1_',
    });

    const groupedRows = (held, name) => {
      const groups = new Map();
      for (const item of held.items) {
        const label = cellOf(held, item, name);
        const key = JSON.stringify(label);
        groups.set(key, { label, count: (groups.get(key) || { count: 0 }).count + 1 });
      }
      return [...groups.values()].map((group) => groupRow(group.label, group.count)(name));
    };

    const extra = (when) => (CONFIG.extraRow === when || CONFIG.extraRow === 'always'
      ? [{ FileLeafRef: 'dbmlsp-not-a-probe-file.txt' }] : []);

    // The rows run 20260908T021507 got back for a <GroupBy> naming a column
    // that does not exist: one per file, and none of them carrying the
    // FileLeafRef the ViewFields asked for.
    const namelessRows = (held) => held.items.map(
      () => ({ PreviewThumbnailsQualitySets: '' }));

    const render = (held, viewXml) => {
      const asked = GROUP_BY.exec(viewXml);
      const fields = [...viewXml.matchAll(/<ViewFields>[\\s\\S]*<\\/ViewFields>/g)].length
        ? [...viewXml.split('<ViewFields>')[1].split('</ViewFields>')[0]
            .matchAll(/Name="([^"]+)"/g)].map((hit) => hit[1])
        : ['FileLeafRef'];
      if (asked && !held.fields.has(asked[2]) && asked[2] !== 'FileLeafRef'
          && asked[2] !== 'Title') {
        if (CONFIG.missingGroupBy === 'refused') {
          return jsonResponse(500, { error: `no column named ${asked[2]}` });
        }
        if (CONFIG.missingGroupBy === 'grouped') {
          return jsonResponse(200, { Row: [groupRow('', held.items.length)(asked[2])] });
        }
        return jsonResponse(200, {
          Row: namelessRows(held).concat(extra('grouped-only')),
        });
      }
      if (asked && asked[1] === 'TRUE') {
        return jsonResponse(200, { Row: groupedRows(held, asked[2]) });
      }
      return jsonResponse(200, { Row: flatRows(held, fields).concat(extra('ungrouped')) });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url).split('/_api/')[1] || '';
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? null : String(opts.body);
      const sent = () => JSON.parse(raw || '{}');

      if (u.includes('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u === 'web/lists' && method === 'POST') {
        const made = sent();
        lists.set(made.Title, {
          Id: `list-${nextListId}`, Title: made.Title,
          BaseTemplate: made.BaseTemplate,
          ServerRelativeUrl: `/sites/test/${nextListId}`,
          fields: new Map(), items: [],
        });
        nextListId += 1;
        return jsonResponse(201, { Id: lists.get(made.Title).Id });
      }
      const upload = FILE_NAME.exec(u);
      if (upload) {
        const folder = decodeURIComponent(u.split("'")[1]);
        const held = [...lists.values()].find((one) => one.ServerRelativeUrl === folder);
        if (!held) return jsonResponse(404, { error: 'no such folder' });
        held.items.push({ Id: nextItemId, FileLeafRef: upload[1] });
        nextItemId += 1;
        return jsonResponse(200, { Name: upload[1] });
      }

      const named = LIST.exec(u);
      if (!named) return jsonResponse(404, { error: `no such endpoint: ${u}` });
      const held = lists.get(decodeURIComponent(named[1]));
      const rest = named[2];
      if (!held) return jsonResponse(404, { error: 'list not found' });

      if (rest.startsWith('/RenderListDataAsStream')) {
        return render(held, String((sent().parameters || {}).ViewXml || ''));
      }
      if (rest.startsWith('/fields/createfieldasxml')) {
        const xml = sent().parameters.SchemaXml;
        const type = SCHEMA.type.exec(xml)[1];
        held.fields.set(SCHEMA.name.exec(xml)[1], {
          TypeAsString: type,
          LookupList: SCHEMA.list.test(xml) ? `{${SCHEMA.list.exec(xml)[1]}}` : undefined,
          AllowMultipleValues: type.startsWith('Lookup')
            ? SCHEMA.mult.test(xml) : undefined,
        });
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/fields/')) {
        const field = held.fields.get(FIELD.exec(rest)[1]);
        return field
          ? jsonResponse(200, { InternalName: FIELD.exec(rest)[1], ...field })
          : jsonResponse(404, { error: 'field not found' });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: held.ServerRelativeUrl });
      }
      if (rest.startsWith('/views')) {
        if (method === 'POST') {
          const made = sent();
          views.set(made.Title, {
            Title: made.Title,
            // Read back as SharePoint rewrote it in the live run: the
            // self-closing FieldRef gains a space before the slash.
            ViewQuery: made.ViewQuery.replace(/"\\/>/g, '" />'),
            ServerRelativeUrl: `${held.ServerRelativeUrl}/Forms/${made.Title}.aspx`,
          });
          return jsonResponse(201, { Id: `view-${views.size}` });
        }
        return jsonResponse(200, { value: [...views.values()] });
      }

      const one = ITEM.exec(rest);
      if (one) {
        const item = held.items.find((row) => row.Id === Number(one[1]));
        if (!item) return jsonResponse(404, { error: 'item not found' });
        if (verb === 'MERGE') {
          for (const [name, value] of Object.entries(sent())) {
            if (name === '__metadata') continue;
            const column = name.endsWith('Id') ? name.slice(0, -2) : name;
            if (name !== 'Title' && !held.fields.has(column)) {
              return jsonResponse(500, { error: `no column named ${name}` });
            }
            item[name] = Array.isArray(value) ? value
              : (value && Array.isArray(value.results) ? value.results : value);
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { ...item });
      }
      if (rest.startsWith('/items')) {
        if (method === 'POST') {
          const made = { Id: nextItemId, ...sent() };
          nextItemId += 1;
          held.items.push(made);
          return jsonResponse(201, { Id: made.Id });
        }
        return jsonResponse(200, { value: held.items.map((item) => ({ ...item })) });
      }
      return jsonResponse(200, {
        Id: held.Id, Title: held.Title,
        ListItemEntityTypeFullName: 'SP.Data.ProbeLibItem',
      });
    };
""")


def _grouping_probe_js() -> str:
    """The rendered grouping probe with its gates open and its table exposed.

    The dump goes inside report() rather than before one call of it: this
    probe returns report() from five places, and splicing at one of them
    would leave an aborted run invisible to these tests.
    """
    js = GROUPING_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_grouping_probe(
    missing_group_by: str = "flat", extra_row: str = "none",
) -> dict[str, dict[str, str]]:
    """Run the grouping probe and return id -> the whole recorded row."""
    config = {"missingGroupBy": missing_group_by, "extraRow": extra_row}
    script = (
        _GROUPING_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _grouping_probe_js()
    )
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_by_that_is_ignored_rather_than_refused_still_holds_the_control() -> None:
    """Run 20260908T015538: the negative control asked whether a group-by
    naming a column that does not exist was REFUSED, SharePoint answered HTTP
    200 with flat rows, and six measurements that had been made were voided.

    A group-by is never refused, so the control has to establish the IGNORED
    signature instead: rows carrying no group label, as many as the same query
    returns with no <GroupBy> at all.

    The rows here are the ones run 20260908T021507 came back with, which carry
    no FileLeafRef. Requiring one row per file over a count keyed by that name
    voided the same six measurements a second time.
    """
    rows = _run_grouping_probe()

    assert rows[_GROUPING_CONTROL]["outcome"] == "PASS", (
        f"the control recorded {rows[_GROUPING_CONTROL]['outcome']!r} against a "
        f"group-by that came back flat, which is the answer the live run got."
    )
    assert "Flat rows carrying no group label" in rows[_GROUPING_CONTROL]["evidence"]
    # The count is still reported, and is still the count the live run showed.
    assert "rows per file " in rows[_GROUPING_CONTROL]["evidence"]
    assert rows["library.view.control-group-by-single-value-column"]["outcome"] == "PASS"
    assert not [row for row in rows.values() if row["state"] == "void"]
    assert rows["library.view.group-by-multi-value-choice"]["outcome"] == "ONE GROUP PER SET"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_missing_column_group_by_that_comes_back_grouped_voids_the_measurements() -> None:
    """The failure the control exists for, and the one it must still catch.

    Group rows for a column that does not exist mean group rows are not
    evidence of a grouping, so nothing below them is a measurement.
    """
    rows = _run_grouping_probe(missing_group_by="grouped")

    assert rows[_GROUPING_CONTROL]["outcome"] == "FAIL"
    assert "cannot tell a group-by SharePoint honoured from one it ignored" in (
        rows[_GROUPING_CONTROL]["evidence"]
    )
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == set(_GROUPING_MEASUREMENTS)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_missing_column_group_by_is_not_the_ignored_signature() -> None:
    """A refusal is not the flat shape, so the row it would license is not
    answered. The control fails closed rather than reading a 500 as proof of
    something it never saw."""
    rows = _run_grouping_probe(missing_group_by="refused")

    assert rows[_GROUPING_CONTROL]["outcome"] == "NOT ESTABLISHED"
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == set(
        _GROUPING_MEASUREMENTS,
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_row_the_ungrouped_query_also_returns_does_not_fail_the_control() -> None:
    """The flat shape is measured, not assumed to be the file count.

    The live run's missing-column query returned five rows over four files.
    What makes a response flat is that the same query returns as many rows
    with no <GroupBy> at all, carrying no grouping marker.
    """
    rows = _run_grouping_probe(extra_row="always")

    assert rows[_GROUPING_CONTROL]["outcome"] == "PASS"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_row_only_the_grouped_query_returns_is_not_the_ignored_signature() -> None:
    """A response the ungrouped query does not match is not the flat shape,
    whether or not it carries a group label."""
    rows = _run_grouping_probe(extra_row="grouped-only")

    assert rows[_GROUPING_CONTROL]["outcome"] == "NOT ESTABLISHED"
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == set(
        _GROUPING_MEASUREMENTS,
    )


# --------------------------------------------------------------------------
# library-nesting-probe.js: what a view does when a folder holds a folder,
# and which rows a failed control is allowed to take with it.
# --------------------------------------------------------------------------
NESTING_PROBE = MANUAL / "library-nesting-probe.js"

#: The rows the two GROUPING controls gate, and only those. A probe whose
#: controls void more than they cover throws away measurements that were made.
_NESTING_GROUPED = (
    "library.folder.group-by-path-depth",
    "library.folder.nesting-with-metadata-group-by",
)

#: The rows the FOLDER control gates. Depth is a write question, so a folder
#: creation this probe cannot tell from a no-op voids these and nothing else.
_NESTING_FOLDER_ROWS = (
    "library.folder.nesting-depth",
    "library.folder.file-in-nested-folder",
)

#: Every question the probe asks after its fixture, which is what an abort has
#: to report as open rather than as answered.
_NESTING_MEASUREMENTS = (
    *_NESTING_FOLDER_ROWS,
    "library.folder.view-flattens-depth",
    "library.view.control-missing-group-column-ungrouped",
    "library.view.control-group-by-single-value-column",
    *_NESTING_GROUPED,
)

#: A SharePoint that holds a folder tree, and answers a view query the way
#: "View element (List)" documents Scope: absent shows the files and subfolders
#: of one folder, `FilesOnly` its files, `Recursive` every file, `RecursiveAll`
#: every file and every subfolder. What the CONFIG varies is each way a live
#: run could make the probe's classifiers wrong: a nested create that lands
#: somewhere else, a create under a parent that does not exist being accepted,
#: a scope that changes nothing, a group-by SharePoint ignores, a second
#: FieldRef it drops, a read that answers for a folder that is not there, a
#: folder an earlier run left behind, and a recycle that will not clear it.
_NESTING_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const ROOT = '/sites/test/lib';
    const lists = new Map();
    const folders = new Map();
    const files = [];
    let nextItemId = 1;

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FOLDER = /^web\\/GetFolderByServerRelativeUrl\\('([^']*)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const URL_ARG = /\\('([^']+)'\\)/;
    const NAMED_URL_ARG = /url='([^']+)'/;

    const addFolder = (path) => {
      const name = path.slice(path.lastIndexOf('/') + 1);
      folders.set(path, { Name: name, ServerRelativeUrl: path, Exists: true, ItemCount: 0 });
    };

    // Reading a folder that is NOT there. `exists-false` is the shape run
    // 20260908T032653 recorded on a library it had just created: the read
    // answered HTTP 200 unless it named Name or ItemCount, and 404 when it did.
    // `not-found` is the other tenant the probe has to be right on, refusing
    // the read whatever the select. A probe reading HTTP ok as presence passes
    // against `not-found` and skips its whole fixture against `exists-false`.
    const absentFolderRead = (path, rest) => {
      if (CONFIG.absentFolder === 'not-found') {
        return jsonResponse(404, { error: 'no such folder' });
      }
      if (/Name|ItemCount/.test(rest)) return jsonResponse(404, { error: 'not found' });
      return jsonResponse(200, { ServerRelativeUrl: path, Exists: false });
    };

    // Recycling a folder takes what is under it. The probe's reset clears the
    // deepest folder first and so does not rest on that, which makes this the
    // generous case rather than the behaviour the reset needs.
    const recycleFolder = (path) => {
      if (CONFIG.folderRecycle === 'refused') {
        return jsonResponse(500, { error: 'this folder cannot be recycled' });
      }
      for (const held of [...folders.keys()]) {
        if (held === path || held.startsWith(`${path}/`)) folders.delete(held);
      }
      for (let at = files.length - 1; at >= 0; at -= 1) {
        if (String(files[at].FileRef).startsWith(`${path}/`)) files.splice(at, 1);
      }
      return jsonResponse(200, { value: 'recycled' });
    };

    // A folder creation, addressed at a parent. The two ways a live run could
    // make the nesting rows a statement about this probe rather than about
    // SharePoint are both here: a create under a parent that does not exist
    // being ACCEPTED, and a nested create landing at the library root.
    const createFolder = (parentPath, name) => {
      if (!folders.has(parentPath)) {
        if (CONFIG.orphan !== 'accepted') {
          return jsonResponse(404, { error: `no folder at ${parentPath}` });
        }
        addFolder(parentPath);
      }
      const at = CONFIG.nesting === 'flat' && parentPath !== ROOT
        ? `${ROOT}/${name}` : `${parentPath}/${name}`;
      addFolder(at);
      return jsonResponse(200, { ServerRelativeUrl: at });
    };

    // Which rows a view returns at one Scope value.
    const rowsForScope = (scope) => {
      const all = CONFIG.scope === 'always-flat';
      const none = CONFIG.scope === 'never-flat';
      const deepFiles = all || (!none && (scope === 'Recursive' || scope === 'RecursiveAll'));
      const withFolders = all || (!none && (scope === null || scope === 'RecursiveAll'));
      const rows = files
        .filter((file) => deepFiles || file.FileDirRef === ROOT)
        .map((file) => ({ ...file, FSObjType: '0' }));
      if (!withFolders) return rows;
      return rows.concat([...folders.values()]
        .filter((folder) => folder.ServerRelativeUrl !== ROOT)
        .filter((folder) => all || scope === 'RecursiveAll'
          || folder.ServerRelativeUrl.lastIndexOf('/') === ROOT.length)
        .map((folder) => ({
          FileLeafRef: folder.Name, FileRef: folder.ServerRelativeUrl,
          FileDirRef: folder.ServerRelativeUrl.slice(0, folder.ServerRelativeUrl.lastIndexOf('/')),
          FSObjType: '1',
        })));
    };

    const pick = (row, fields) => {
      if (!fields.length) return { ...row };
      const out = {};
      for (const name of fields) out[name] = row[name] === undefined ? '' : row[name];
      return out;
    };

    const labelOf = (row, name) => {
      const held = row[name] === undefined ? '' : row[name];
      if (name !== 'FileDirRef' || CONFIG.pathLabel !== 'leaf') return held;
      return String(held).slice(String(held).lastIndexOf('/') + 1);
    };

    const groupedRows = (rows, names) => {
      const grouping = CONFIG.compose === 'first-only' ? names.slice(0, 1) : names;
      const groups = new Map();
      for (const row of rows) {
        const labels = grouping.map((name) => labelOf(row, name));
        const key = JSON.stringify(labels);
        const held = groups.get(key) || { labels, count: 0 };
        held.count += 1;
        groups.set(key, held);
      }
      return [...groups.values()].map((group) => {
        const out = {};
        grouping.forEach((name, at) => {
          out[name] = group.labels[at];
          out[`${name}.COUNT.group`] = String(group.count);
          out[`${name}.newgroup`] = '1';
          out[`${name}.groupindex`] = '1_';
        });
        return out;
      });
    };

    const render = (held, viewXml) => {
      const scoped = /<View Scope="([^"]+)"/.exec(viewXml);
      const scope = scoped === null ? null : scoped[1];
      const asked = (viewXml.split('<GroupBy')[1] || '').split('</GroupBy>')[0];
      const names = [...asked.matchAll(/Name="([^"]+)"/g)].map((hit) => hit[1]);
      const fields = [...(viewXml.split('<ViewFields>')[1] || '').split('</ViewFields>')[0]
        .matchAll(/Name="([^"]+)"/g)].map((hit) => hit[1]);
      const rows = rowsForScope(scope);
      const flat = () => jsonResponse(200, { Row: rows.map((row) => pick(row, fields)) });
      if (!names.length) return flat();
      if (names.some((name) => !held.fields.has(name))) {
        if (CONFIG.missingGroupBy === 'grouped') {
          return jsonResponse(200, { Row: groupedRows(rows, names) });
        }
        // The shape run 20260908T021507 recorded for a group-by naming a column
        // that does not exist: as many rows as the ungrouped query, none of
        // them carrying the ViewFields the query asked for.
        return jsonResponse(200, {
          Row: rows.map(() => ({ PreviewThumbnailsQualitySets: '' })),
        });
      }
      if (names.includes('FileDirRef') && CONFIG.pathGroupBy === 'ignored') return flat();
      if (!viewXml.includes('Collapse="TRUE"')) return flat();
      return jsonResponse(200, { Row: groupedRows(rows, names) });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url).split('/_api/')[1] || '';
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? null : String(opts.body);
      const sent = () => JSON.parse(raw || '{}');

      if (u.includes('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u === 'web/lists' && method === 'POST') {
        const made = sent();
        // The columns a library holds before anybody adds one. FileDirRef is
        // among them, which is what makes a group-by over it a measurement
        // rather than the negative control a second time.
        const fields = new Map();
        for (const name of ['Title', 'FileLeafRef', 'FileRef', 'FileDirRef']) {
          fields.set(name, { TypeAsString: name === 'Title' ? 'Text' : 'Lookup' });
        }
        lists.set(made.Title, {
          Id: 'list-1', Title: made.Title, BaseTemplate: made.BaseTemplate,
          ServerRelativeUrl: ROOT, fields,
        });
        addFolder(ROOT);
        // What an earlier run left behind, which the probe has to clear rather
        // than build on. `ladder` is the nested tree with a file in it;
        // `orphan-parent` is the folder the negative control addresses, whose
        // presence makes a refused create and a successful read-back
        // contradict each other.
        if (CONFIG.leftover === 'ladder' || CONFIG.leftover === 'both') {
          addFolder(`${ROOT}/nestlevel-alpha`);
          addFolder(`${ROOT}/nestlevel-alpha/nestlevel-bravo`);
          addFolder(`${ROOT}/nestlevel-alpha/nestlevel-bravo/nestlevel-charlie`);
          files.push({
            Id: nextItemId, FileLeafRef: 'left-over.txt',
            FileRef: `${ROOT}/nestlevel-alpha/left-over.txt`,
            FileDirRef: `${ROOT}/nestlevel-alpha`, FileSystemObjectType: 0,
          });
          nextItemId += 1;
        }
        if (CONFIG.leftover === 'orphan-parent' || CONFIG.leftover === 'both') {
          addFolder(`${ROOT}/nestlevel-never-created`);
          addFolder(`${ROOT}/nestlevel-never-created/nestlevel-alpha`);
        }
        return jsonResponse(201, { Id: 'list-1' });
      }

      const atFolder = FOLDER.exec(u);
      if (atFolder) {
        const path = atFolder[1];
        const rest = atFolder[2];
        if (rest.startsWith('/folders/add')) {
          return createFolder(path, NAMED_URL_ARG.exec(rest)[1]);
        }
        if (rest.startsWith('/Files/add')) {
          if (!folders.has(path)) return jsonResponse(404, { error: 'no such folder' });
          const name = NAMED_URL_ARG.exec(rest)[1];
          files.push({
            Id: nextItemId, FileLeafRef: name, FileRef: `${path}/${name}`,
            FileDirRef: path, FileSystemObjectType: 0,
          });
          nextItemId += 1;
          return jsonResponse(200, { Name: name });
        }
        if (rest.startsWith('/recycle')) {
          if (!folders.has(path)) return jsonResponse(404, { error: 'no such folder' });
          return recycleFolder(path);
        }
        if (!folders.has(path)) return absentFolderRead(path, rest);
        if (rest.startsWith('/Folders')) {
          return jsonResponse(200, { value: [...folders.values()].filter(
            (folder) => folder.ServerRelativeUrl.startsWith(`${path}/`)
              && !folder.ServerRelativeUrl.slice(path.length + 1).includes('/')) });
        }
        return jsonResponse(200, { ...folders.get(path) });
      }
      if (u.startsWith('web/folders/add')) {
        const path = URL_ARG.exec(u)[1];
        return createFolder(path.slice(0, path.lastIndexOf('/')),
                            path.slice(path.lastIndexOf('/') + 1));
      }
      if (u === 'web/folders' && method === 'POST') {
        const path = sent().ServerRelativeUrl;
        return createFolder(path.slice(0, path.lastIndexOf('/')),
                            path.slice(path.lastIndexOf('/') + 1));
      }

      const named = LIST.exec(u);
      if (!named) return jsonResponse(404, { error: `no such endpoint: ${u}` });
      const held = lists.get(decodeURIComponent(named[1]));
      const rest = named[2];
      if (!held) return jsonResponse(404, { error: 'list not found' });

      if (rest.startsWith('/RenderListDataAsStream')) {
        return render(held, String((sent().parameters || {}).ViewXml || ''));
      }
      if (rest.startsWith('/fields/createfieldasxml')) {
        const xml = sent().parameters.SchemaXml;
        held.fields.set(/Name="([^"]+)"/.exec(xml)[1],
                        { TypeAsString: /Type="([^"]+)"/.exec(xml)[1] });
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/fields/')) {
        const name = FIELD.exec(rest)[1];
        const field = held.fields.get(name);
        return field
          ? jsonResponse(200, { InternalName: name, ...field })
          : jsonResponse(404, { error: 'field not found' });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: held.ServerRelativeUrl });
      }

      const one = ITEM.exec(rest);
      if (one) {
        const item = files.find((row) => row.Id === Number(one[1]));
        if (!item) return jsonResponse(404, { error: 'item not found' });
        if (verb === 'MERGE') {
          for (const [name, value] of Object.entries(sent())) {
            if (!held.fields.has(name)) {
              return jsonResponse(500, { error: `no column named ${name}` });
            }
            item[name] = value;
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { ...item });
      }
      if (rest.startsWith('/items')) {
        // One unrecognised name errors the WHOLE request, which is why the
        // probe reads the path columns defensively.
        if (CONFIG.dirRef === 'unselectable' && rest.includes('FileDirRef')) {
          return jsonResponse(400, { error: 'FileDirRef cannot be selected' });
        }
        return jsonResponse(200, { value: files.map((file) => ({ ...file })) });
      }
      return jsonResponse(200, { Id: held.Id, Title: held.Title });
    };
""")


def _nesting_probe_js() -> str:
    """The rendered nesting probe with its gates open and its table exposed."""
    js = NESTING_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_nesting_probe(**config: str) -> dict[str, dict[str, str]]:
    """Run the nesting probe and return id -> the whole recorded row."""
    settings: dict[str, str] = {
        "nesting": "ok",
        "orphan": "refused",
        "scope": "honoured",
        "pathGroupBy": "honoured",
        "pathLabel": "full-path",
        "compose": "both",
        "missingGroupBy": "flat",
        "dirRef": "selectable",
        # The shape a live tenant answered a missing folder with, so every
        # nesting test runs against it and a probe reading HTTP ok as presence
        # cannot pass by default.
        "absentFolder": "exists-false",
        "folderRecycle": "ok",
        "leftover": "none",
        **config,
    }
    script = (
        _NESTING_HARNESS.replace("__CONFIG__", json.dumps(settings))
        + "\n"
        + _nesting_probe_js()
    )
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_library_that_nests_records_the_depth_and_the_scope_that_flattened_it() -> None:
    """A SharePoint behaving the way Learn documents. Every question is
    answered, nothing is void, and the two classifiers say what the mock did:
    the default scope shows one folder's children and `Recursive` shows every
    file.
    """
    rows = _run_nesting_probe()

    assert rows["library.folder.control-missing-parent-refused"]["outcome"] == "PASS"
    assert rows["library.folder.fixture-nested-folders-created"]["outcome"] == "PASS"
    assert rows["library.folder.fixture-files-placed"]["outcome"] == "PASS"
    assert rows["library.folder.nesting-depth"]["outcome"] == "NESTS THREE DEEP"
    assert rows["library.folder.file-in-nested-folder"]["outcome"] == (
        "UPLOADED, AND BOTH PATH COLUMNS CARRY THE NESTED PATH"
    )
    assert rows["library.folder.view-flattens-depth"]["outcome"] == (
        'DIRECT CHILDREN BY DEFAULT, FLATTENED BY Scope="Recursive"'
    )
    assert rows["library.folder.group-by-path-depth"]["outcome"] == (
        "GROUPED UNDER THE FULL PATH"
    )
    assert rows["library.folder.nesting-with-metadata-group-by"]["outcome"] == (
        "BOTH DIMENSIONS GROUP"
    )
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_view_that_shows_every_file_at_every_scope_is_not_read_as_a_scope_effect() -> None:
    """A library that flattens on its own. The row must say so rather than
    crediting whichever Scope value happened to be asked first."""
    rows = _run_nesting_probe(scope="always-flat")

    assert rows["library.folder.view-flattens-depth"]["outcome"] == "FLATTENS BY DEFAULT"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_scope_that_never_reaches_a_nested_file_is_not_reported_as_flattening() -> None:
    """The answer a layout generator most needs, and the one a probe that
    assumed `Recursive` works would never print."""
    rows = _run_nesting_probe(scope="never-flat")

    assert rows["library.folder.view-flattens-depth"]["outcome"] == (
        "DIRECT CHILDREN ONLY, NO SCOPE RETURNED EVERY FILE"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_by_on_the_path_that_is_ignored_is_not_read_as_a_folder_grouping() -> None:
    """A group-by is never refused. A library that accepts one over the path
    column and returns the ungrouped rows has answered the question, and the
    answer is not a grouping."""
    rows = _run_nesting_probe(pathGroupBy="ignored")

    assert rows["library.folder.group-by-path-depth"]["outcome"] == "ACCEPTED AND IGNORED"
    assert rows["library.folder.group-by-path-depth"]["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_dropped_second_field_ref_is_recorded_as_one_dimension_grouping() -> None:
    """GroupBy documents one FieldRef child. A library that groups by the
    first and drops the second has to read as that, not as composition."""
    rows = _run_nesting_probe(compose="first-only")

    assert rows["library.folder.nesting-with-metadata-group-by"]["outcome"] == (
        "ONLY THE FOLDER PATH GROUPS"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_label_naming_only_the_leaf_folder_is_not_read_as_a_path() -> None:
    """The three candidate labels are three different string tests, and the
    folder names share no substring, so a leaf label cannot pass the full-path
    test by accident."""
    rows = _run_nesting_probe(pathLabel="leaf")

    assert rows["library.folder.group-by-path-depth"]["outcome"] == (
        "GROUPED UNDER THE LEAF FOLDER"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_failed_grouping_control_voids_the_grouped_rows_and_nothing_else() -> None:
    """A control that voids more than it covers throws away measurements that
    were made. The depth and flattening rows do not rest on a group-by."""
    rows = _run_nesting_probe(missingGroupBy="grouped")

    assert rows["library.view.control-missing-group-column-ungrouped"]["outcome"] == "FAIL"
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == set(_NESTING_GROUPED)
    assert rows["library.folder.nesting-depth"]["outcome"] == "NESTS THREE DEEP"
    assert rows["library.folder.view-flattens-depth"]["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_folder_create_under_a_missing_parent_that_is_accepted_voids_the_write_rows() -> None:
    """If a creation addressed at a parent that does not exist is accepted,
    this probe cannot tell a folder it created from one it did not, so the two
    write rows are void however they came out. The grouping rows are not: they
    read a fixture that was verified by path."""
    rows = _run_nesting_probe(orphan="accepted")

    assert rows["library.folder.control-missing-parent-refused"]["outcome"] == "FAIL"
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == set(_NESTING_FOLDER_ROWS)
    assert rows["library.folder.group-by-path-depth"]["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_nested_create_that_lands_at_the_root_aborts_rather_than_measuring_depth() -> None:
    """A folder endpoint that accepts the create and puts the folder beside its
    parent leaves nothing below it about depth. ABORTED is open, not settled:
    the questions were never asked, and a re-run can clear them."""
    rows = _run_nesting_probe(nesting="flat")

    assert rows["library.folder.fixture-nested-folders-created"]["outcome"] == "FAIL"
    assert {
        row_id for row_id, row in rows.items() if row["outcome"] == "ABORTED"
    } == {*_NESTING_MEASUREMENTS, "library.folder.fixture-files-placed"}
    # Only the rows the ladder does not stand on survive as answered, and the
    # ladder row itself, which answered its own question with a FAIL.
    assert {row_id for row_id, row in rows.items() if row["state"] == "settled"} == {
        "library.doc-lib.fixture-library-created",
        "library.folder.control-missing-parent-refused",
        "library.folder.fixture-nested-folders-created",
    }
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_path_column_that_cannot_be_selected_still_leaves_the_fixture_readable() -> None:
    """One unrecognised name errors the whole request, so a defensive read is
    the difference between a library with no items and a column that cannot be
    selected. The nested-file row has to say which it saw."""
    rows = _run_nesting_probe(dirRef="unselectable")

    assert rows["library.folder.fixture-files-placed"]["outcome"] == "PASS"
    assert rows["library.folder.file-in-nested-folder"]["outcome"] == (
        "UPLOADED, FileRef CARRIES THE PATH, FileDirRef NOT SELECTABLE"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_tenant_that_refuses_a_read_of_a_missing_folder_answers_the_same() -> None:
    """The two ways a tenant can answer a read of a folder that is not there,
    and the probe has to be right on both. `exists-false` is the default every
    other nesting test runs against, because it is what the first live run
    recorded; a 404 must not change a single row."""
    rows = _run_nesting_probe(absentFolder="not-found")

    assert rows["library.folder.control-missing-parent-refused"]["outcome"] == "PASS"
    assert rows["library.folder.fixture-nested-folders-created"]["outcome"] == "PASS"
    assert rows["library.folder.nesting-depth"]["outcome"] == "NESTS THREE DEEP"
    assert not [row for row in rows.values() if row["state"] in {"open", "void"}]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_ladder_an_earlier_run_left_is_reset_rather_than_reused() -> None:
    """A fixture that builds on what it finds measures the previous run. The
    ladder has to be cleared and rebuilt, and the row has to say so: every
    folder named as created by an endpoint spelling rather than found."""
    rows = _run_nesting_probe(leftover="both")

    folders = rows["library.folder.fixture-nested-folders-created"]
    assert folders["outcome"] == "PASS"
    assert "was left by an earlier run" in folders["evidence"]
    assert "NOT CREATED" not in folders["evidence"]
    assert rows["library.folder.control-missing-parent-refused"]["outcome"] == "PASS"
    assert rows["library.folder.nesting-depth"]["outcome"] == "NESTS THREE DEEP"
    assert not [row for row in rows.values() if row["state"] in {"open", "void"}]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_leftover_the_reset_cannot_clear_fails_the_fixture_rather_than_reusing_it() -> None:
    """The failure the first live run hit, in the shape it can still take: a
    folder from an earlier run that this run did not create. Building on it
    would answer this run's question with somebody else's folder, so the
    fixture row fails and everything under it reports ABORTED, which is open."""
    rows = _run_nesting_probe(leftover="ladder", folderRecycle="refused")

    folders = rows["library.folder.fixture-nested-folders-created"]
    assert folders["outcome"] == "FAIL"
    assert "DIRTY FIXTURE" in folders["evidence"]
    assert {
        row_id for row_id, row in rows.items() if row["outcome"] == "ABORTED"
    } == {*_NESTING_MEASUREMENTS, "library.folder.fixture-files-placed"}
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_control_folder_left_by_an_earlier_run_voids_rather_than_contradicting() -> None:
    """A folder already sitting where the refused create would have put one
    makes the refusal and the read-back contradict each other. That is a
    leftover, not a SharePoint that refuses a create it performed, so the
    control records what it saw and voids the two rows it gates."""
    rows = _run_nesting_probe(leftover="orphan-parent", folderRecycle="refused")

    control = rows["library.folder.control-missing-parent-refused"]
    assert control["outcome"] == "DIRTY FIXTURE, THE FOLDER WAS THERE BEFORE THE CREATE"
    assert control["state"] == "void"
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == {
        "library.folder.control-missing-parent-refused",
        *_NESTING_FOLDER_ROWS,
    }
    # The ladder is a different set of folders, so it still builds and the rows
    # that do not rest on the folder control still answer.
    assert rows["library.folder.fixture-nested-folders-created"]["outcome"] == "PASS"
    assert rows["library.folder.view-flattens-depth"]["state"] == "settled"


# --------------------------------------------------------------------------
# library-view-interaction-probe.js: what a view's filter, group-by and folder
# scope do when they are sent together.
# --------------------------------------------------------------------------
INTERACTION_PROBE = MANUAL / "library-view-interaction-probe.js"

#: The three composition rows, and only those. They rest on the filter control
#: and the two grouping controls, so a control that did not hold voids these and
#: nothing else.
_INTERACTION_COMPOSED = (
    "library.view.filter-with-group-by",
    "library.view.filter-in-folder-scope",
    "library.view.filter-group-by-and-folder-scope",
)

#: Every question the probe asks after its fixture, which is what an abort has
#: to report as open rather than as answered.
_INTERACTION_MEASUREMENTS = (
    "library.view.control-missing-column-refused",
    "library.view.control-filter-single-value-column",
    "library.view.control-missing-group-column-ungrouped",
    "library.view.control-group-by-single-value-column",
    *_INTERACTION_COMPOSED,
)

#: A SharePoint that holds a folder tree and answers a view query built from a
#: `<Where>`, a `<GroupBy>`, a `Scope` and a `FolderServerRelativeUrl`. What the
#: CONFIG varies is each way a live run could make the probe's classifiers
#: wrong: a filter that changes nothing, a group built over rows the filter took
#: out, a folder parameter that scopes nothing, each of the three being dropped
#: when all three are sent at once, a group-by SharePoint ignores, a `<Where>`
#: naming a missing column that is accepted, a folder an earlier run left, and a
#: recycle that will not clear it.
_INTERACTION_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const ROOT = '/sites/test/lib';
    const lists = new Map();
    const folders = new Map();
    const files = [];
    let nextItemId = 1;

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FOLDER = /^web\\/GetFolderByServerRelativeUrl\\('([^']*)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const URL_ARG = /\\('([^']+)'\\)/;
    const NAMED_URL_ARG = /url='([^']+)'/;

    const addFolder = (path) => {
      const name = path.slice(path.lastIndexOf('/') + 1);
      folders.set(path, { Name: name, ServerRelativeUrl: path, Exists: true, ItemCount: 0 });
    };

    // The shape a live tenant answered a read of a folder that is not there
    // with: HTTP 200 unless the select names Name or ItemCount. A probe reading
    // HTTP ok as presence skips its whole fixture against this.
    const absentFolderRead = (path, rest) => {
      if (CONFIG.absentFolder === 'not-found') {
        return jsonResponse(404, { error: 'no such folder' });
      }
      if (/Name|ItemCount/.test(rest)) return jsonResponse(404, { error: 'not found' });
      return jsonResponse(200, { ServerRelativeUrl: path, Exists: false });
    };

    const recycleFolder = (path) => {
      if (CONFIG.folderRecycle === 'refused') {
        return jsonResponse(500, { error: 'this folder cannot be recycled' });
      }
      for (const held of [...folders.keys()]) {
        if (held === path || held.startsWith(`${path}/`)) folders.delete(held);
      }
      for (let at = files.length - 1; at >= 0; at -= 1) {
        if (String(files[at].FileRef).startsWith(`${path}/`)) files.splice(at, 1);
      }
      return jsonResponse(200, { value: 'recycled' });
    };

    const createFolder = (parentPath, name) => {
      if (!folders.has(parentPath)) {
        return jsonResponse(404, { error: `no folder at ${parentPath}` });
      }
      addFolder(`${parentPath}/${name}`);
      return jsonResponse(200, { ServerRelativeUrl: `${parentPath}/${name}` });
    };

    const pick = (row, fields) => {
      if (!fields.length) return { ...row };
      const out = {};
      for (const name of fields) out[name] = row[name] === undefined ? '' : row[name];
      return out;
    };

    const groupedRows = (rows, names) => {
      const groups = new Map();
      for (const row of rows) {
        const labels = names.map((name) => (row[name] === undefined ? '' : row[name]));
        const key = JSON.stringify(labels);
        const held = groups.get(key) || { labels, count: 0 };
        held.count += 1;
        groups.set(key, held);
      }
      return [...groups.values()].map((group) => {
        const out = {};
        names.forEach((name, at) => {
          out[name] = group.labels[at];
          out[`${name}.COUNT.group`] = String(group.count);
          out[`${name}.newgroup`] = '1';
          out[`${name}.groupindex`] = '1_';
        });
        return out;
      });
    };

    // One view query. The three mechanisms are applied independently so that a
    // CONFIG can drop exactly one of them, which is the case the probe's
    // three-way row exists to name.
    const render = (held, viewXml, folderParam) => {
      const scoped = /<View Scope="([^"]+)"/.exec(viewXml);
      const scope = scoped === null ? null : scoped[1];
      const where = /<Where><Eq><FieldRef Name="([^"]+)"\\/><Value Type="[^"]*">([^<]*)<\\/Value>/
        .exec(viewXml);
      const asked = (viewXml.split('<GroupBy')[1] || '').split('</GroupBy>')[0];
      const names = [...asked.matchAll(/Name="([^"]+)"/g)].map((hit) => hit[1]);
      const fields = [...(viewXml.split('<ViewFields>')[1] || '').split('</ViewFields>')[0]
        .matchAll(/Name="([^"]+)"/g)].map((hit) => hit[1]);

      const threeWay = where !== null && names.length > 0 && folderParam !== null;
      const dropFolder = threeWay && CONFIG.threeWay === 'drop-folder';
      const dropFilter = threeWay && CONFIG.threeWay === 'drop-filter';
      const dropGroup = threeWay && CONFIG.threeWay === 'drop-group';

      const base = (folderParam === null || dropFolder || CONFIG.folder === 'ignored')
        ? ROOT : folderParam;
      const deep = scope === 'Recursive' || scope === 'RecursiveAll';
      const all = files.filter((file) => (deep
        ? String(file.FileRef).startsWith(`${base}/`)
        : file.FileDirRef === base));
      let rows = all;
      if (where !== null) {
        if (!held.fields.has(where[1])) {
          if (CONFIG.missingWhere !== 'accepted') {
            return jsonResponse(500, { error: `no column named ${where[1]}` });
          }
        } else if (CONFIG.filter !== 'ignored' && !dropFilter) {
          rows = all.filter((file) => String(file[where[1]]) === where[2]);
        }
      }

      const flat = () => jsonResponse(200, {
        Row: rows.map((row) => pick({ ...row, FSObjType: '0' }, fields)),
      });
      if (!names.length || dropGroup) return flat();
      if (names.some((name) => !held.fields.has(name))) {
        if (CONFIG.missingGroupBy === 'grouped') {
          return jsonResponse(200, { Row: groupedRows(rows, names) });
        }
        // What a live run recorded for a group-by naming a column that does not
        // exist: as many rows as the ungrouped query, none of them carrying the
        // ViewFields the query asked for.
        return jsonResponse(200, {
          Row: rows.map(() => ({ PreviewThumbnailsQualitySets: '' })),
        });
      }
      if (!viewXml.includes('Collapse="TRUE"')) return flat();
      // The group headings. `over-every-row` builds them from the rows the
      // filter took out as well, which is the behaviour the order row names.
      const source = (CONFIG.groupOrder === 'over-every-row') ? all : rows;
      return jsonResponse(200, { Row: groupedRows(source, names) });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url).split('/_api/')[1] || '';
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? null : String(opts.body);
      const sent = () => JSON.parse(raw || '{}');

      if (u.includes('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u === 'web/lists' && method === 'POST') {
        const made = sent();
        const fields = new Map();
        for (const name of ['Title', 'FileLeafRef', 'FileRef', 'FileDirRef']) {
          fields.set(name, { TypeAsString: name === 'Title' ? 'Text' : 'Lookup' });
        }
        lists.set(made.Title, {
          Id: 'list-1', Title: made.Title, BaseTemplate: made.BaseTemplate,
          ServerRelativeUrl: ROOT, fields,
        });
        addFolder(ROOT);
        // What an earlier run left behind, which the probe has to clear rather
        // than build on.
        if (CONFIG.leftover === 'folders') {
          addFolder(`${ROOT}/intlevel-outer`);
          addFolder(`${ROOT}/intlevel-outer/intlevel-inner`);
        }
        return jsonResponse(201, { Id: 'list-1' });
      }

      const atFolder = FOLDER.exec(u);
      if (atFolder) {
        const path = atFolder[1];
        const rest = atFolder[2];
        if (rest.startsWith('/folders/add')) {
          return createFolder(path, NAMED_URL_ARG.exec(rest)[1]);
        }
        if (rest.startsWith('/Files/add')) {
          if (!folders.has(path)) return jsonResponse(404, { error: 'no such folder' });
          const name = NAMED_URL_ARG.exec(rest)[1];
          files.push({
            Id: nextItemId, FileLeafRef: name, FileRef: `${path}/${name}`,
            FileDirRef: path, FileSystemObjectType: 0,
          });
          nextItemId += 1;
          return jsonResponse(200, { Name: name });
        }
        if (rest.startsWith('/recycle')) {
          if (!folders.has(path)) return jsonResponse(404, { error: 'no such folder' });
          return recycleFolder(path);
        }
        if (!folders.has(path)) return absentFolderRead(path, rest);
        return jsonResponse(200, { ...folders.get(path) });
      }
      if (u.startsWith('web/folders/add')) {
        const path = URL_ARG.exec(u)[1];
        return createFolder(path.slice(0, path.lastIndexOf('/')),
                            path.slice(path.lastIndexOf('/') + 1));
      }
      if (u === 'web/folders' && method === 'POST') {
        const path = sent().ServerRelativeUrl;
        return createFolder(path.slice(0, path.lastIndexOf('/')),
                            path.slice(path.lastIndexOf('/') + 1));
      }

      const named = LIST.exec(u);
      if (!named) return jsonResponse(404, { error: `no such endpoint: ${u}` });
      const held = lists.get(decodeURIComponent(named[1]));
      const rest = named[2];
      if (!held) return jsonResponse(404, { error: 'list not found' });

      if (rest.startsWith('/RenderListDataAsStream')) {
        const parameters = sent().parameters || {};
        const folderParam = parameters.FolderServerRelativeUrl === undefined
          ? null : parameters.FolderServerRelativeUrl;
        return render(held, String(parameters.ViewXml || ''), folderParam);
      }
      if (rest.startsWith('/fields/createfieldasxml')) {
        const xml = sent().parameters.SchemaXml;
        held.fields.set(/ Name="([^"]+)"/.exec(xml)[1],
                        { TypeAsString: /Type="([^"]+)"/.exec(xml)[1] });
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/fields/')) {
        const name = FIELD.exec(rest)[1];
        const field = held.fields.get(name);
        return field
          ? jsonResponse(200, { InternalName: name, ...field })
          : jsonResponse(404, { error: 'field not found' });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: held.ServerRelativeUrl });
      }

      const one = ITEM.exec(rest);
      if (one) {
        const item = files.find((row) => row.Id === Number(one[1]));
        if (!item) return jsonResponse(404, { error: 'item not found' });
        if (verb === 'MERGE') {
          for (const [name, value] of Object.entries(sent())) {
            if (!held.fields.has(name)) {
              return jsonResponse(500, { error: `no column named ${name}` });
            }
            item[name] = value;
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { ...item });
      }
      if (rest.startsWith('/items')) {
        return jsonResponse(200, { value: files.map((file) => ({ ...file })) });
      }
      return jsonResponse(200, { Id: held.Id, Title: held.Title });
    };
""")


def _interaction_probe_js() -> str:
    """The rendered interaction probe with its gates open and its table exposed."""
    js = INTERACTION_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_interaction_probe(**config: str) -> dict[str, dict[str, str]]:
    """Run the interaction probe and return id -> the whole recorded row."""
    settings: dict[str, str] = {
        "filter": "honoured",
        "folder": "honoured",
        "groupOrder": "filter-first",
        "threeWay": "all",
        "missingGroupBy": "flat",
        "missingWhere": "refused",
        "absentFolder": "exists-false",
        "folderRecycle": "ok",
        "leftover": "none",
        **config,
    }
    script = (
        _INTERACTION_HARNESS.replace("__CONFIG__", json.dumps(settings))
        + "\n"
        + _interaction_probe_js()
    )
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_view_whose_filter_group_and_folder_all_apply_records_all_three() -> None:
    """A SharePoint that applies each mechanism. Every control holds, the order
    row reads the filter as running first, the folder row reads the filter as
    applying inside the folder, and the three-way composes.
    """
    rows = _run_interaction_probe()

    for check in _INTERACTION_MEASUREMENTS[:4]:
        assert rows[check]["outcome"] == "PASS", check
    assert rows["library.view.fixture-interaction-columns-created"]["outcome"] == "PASS"
    assert rows["library.view.fixture-interaction-folders-created"]["outcome"] == "PASS"
    assert rows["library.view.fixture-interaction-files-placed"]["outcome"] == "PASS"
    assert rows["library.view.filter-with-group-by"]["outcome"] == (
        "THE FILTER RUNS BEFORE THE GROUP"
    )
    assert rows["library.view.filter-in-folder-scope"]["outcome"] == (
        "THE FILTER APPLIES INSIDE THE FOLDER"
    )
    assert rows["library.view.filter-group-by-and-folder-scope"]["outcome"] == (
        "ALL THREE COMPOSE"
    )
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_group_headings_built_over_rows_the_filter_removed_are_read_as_that() -> None:
    """The whole point of the fixture: one group value is carried only by files
    the filter removes, so a heading for it can only come from a group built
    before the filter ran. The rows still come back filtered, which is what
    makes this different from a filter that was dropped.
    """
    rows = _run_interaction_probe(groupOrder="over-every-row")

    assert rows["library.view.filter-with-group-by"]["outcome"] == (
        "THE GROUP IS BUILT OVER EVERY ROW"
    )
    assert rows["library.view.filter-with-group-by"]["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_folder_parameter_that_scopes_nothing_is_not_read_as_a_filter_answer() -> None:
    """A tenant that ignores FolderServerRelativeUrl answers the folder read
    with the whole library. The row has to say the parameter changed nothing
    rather than reporting whatever the filter did.
    """
    rows = _run_interaction_probe(folder="ignored")

    assert rows["library.view.filter-in-folder-scope"]["outcome"] == (
        "THE FOLDER PARAMETER CHANGED NOTHING, THE READ IS LIBRARY-WIDE"
    )
    # The three-way then has no folder scope to hold either, and the row says
    # which mechanism went rather than calling the composition a success.
    assert rows["library.view.filter-group-by-and-folder-scope"]["outcome"] == (
        "THE FOLDER SCOPE IS DROPPED"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_each_mechanism_dropped_from_the_three_way_is_named_by_the_row() -> None:
    """Three runs, one per mechanism the tenant drops when all three are sent
    together. A row that answered ALL THREE COMPOSE here would be the failure
    this probe exists to catch.
    """
    dropped = {
        "drop-folder": "THE FOLDER SCOPE IS DROPPED",
        "drop-filter": "THE FILTER IS DROPPED",
        "drop-group": "THE GROUP IS DROPPED",
    }
    for setting, outcome in dropped.items():
        rows = _run_interaction_probe(threeWay=setting)
        assert rows["library.view.filter-group-by-and-folder-scope"]["outcome"] == outcome
        # The pairwise rows are unaffected, because the tenant only drops one
        # when all three arrive at once.
        assert rows["library.view.filter-with-group-by"]["outcome"] == (
            "THE FILTER RUNS BEFORE THE GROUP"
        )
        assert rows["library.view.filter-in-folder-scope"]["outcome"] == (
            "THE FILTER APPLIES INSIDE THE FOLDER"
        )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_filter_that_changes_nothing_voids_every_composition_row() -> None:
    """A filter that is accepted and applied to nothing is the one failure that
    makes every composition row a statement about this probe. The control has to
    catch it, and the three rows have to be void rather than answered.
    """
    rows = _run_interaction_probe(filter="ignored")

    assert rows["library.view.control-filter-single-value-column"]["outcome"] == (
        "FAIL, THE FILTER CHANGED NOTHING"
    )
    for check in _INTERACTION_COMPOSED:
        assert rows[check]["state"] == "void", check
        assert rows[check]["outcome"] == "NOT ESTABLISHED", check
    # The observation survives the void: the reader loses the verdict, not the
    # data.
    assert "expanded HTTP" in rows["library.view.filter-with-group-by"]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_by_the_tenant_ignores_voids_the_grouped_rows_only() -> None:
    """A tenant that answers a group-by naming a missing column WITH group rows
    leaves the probe unable to tell an honoured group-by from an ignored one.
    """
    rows = _run_interaction_probe(missingGroupBy="grouped")

    assert rows["library.view.control-missing-group-column-ungrouped"]["outcome"] == "FAIL"
    for check in _INTERACTION_COMPOSED:
        assert rows[check]["state"] == "void", check


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_folder_an_earlier_run_left_aborts_rather_than_answering() -> None:
    """A fixture built on leftovers measures the previous run. The folders row
    has to fail and everything under it has to be open, not void: a re-run on a
    site somebody has cleaned can still answer.
    """
    rows = _run_interaction_probe(leftover="folders", folderRecycle="refused")

    assert rows["library.view.fixture-interaction-folders-created"]["outcome"] == "FAIL"
    assert "survived the pre-run reset" in (
        rows["library.view.fixture-interaction-folders-created"]["evidence"]
    )
    for check in _INTERACTION_MEASUREMENTS:
        assert rows[check]["outcome"] == "ABORTED", check
        assert rows[check]["state"] == "open", check


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refusal_nobody_can_observe_voids_a_refused_row() -> None:
    """A tenant that accepts a <Where> naming a column that does not exist makes
    a refusal unreadable. A composition row that comes back refused is then
    recorded rather than answered, and the rows that were not refused still
    answer.
    """
    rows = _run_interaction_probe(missingWhere="accepted")

    assert rows["library.view.control-missing-column-refused"]["outcome"] == "FAIL"
    # Nothing here was refused, so the three rows still answer: the refusal
    # control gates a REFUSED verdict and nothing else.
    assert rows["library.view.filter-with-group-by"]["outcome"] == (
        "THE FILTER RUNS BEFORE THE GROUP"
    )
    assert not [row for row in rows.values() if row["state"] == "void"]


LARGE_LIST_PROBE = MANUAL / "library-large-list-fixture-probe.js"

#: A SharePoint that holds the fixture library, and answers a DateTime read the
#: way run 20260908T050038 recorded: the instant the write carried, rendered in
#: the SITE's zone and naming no zone at all. What CONFIG varies is each way a
#: live run could make the fixture's verification wrong: which form a date comes
#: back in, which multi-value payload shape the tenant accepts, whether the site
#: zone reads at all, and whether an unrelated column write takes.
_LARGE_LIST_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const ROOT = '/sites/test/largelib';
    const LIB = 'dbmlsp Probe LargeLib';
    const TGT = 'dbmlsp Probe LargeLib Target';
    const FIELD_TYPES = {
      LVText: 'Text', LVChoice: 'Choice', LVNumber: 'Number', LVDate: 'DateTime',
      LVMultiChoice: 'MultiChoice', LVCalc: 'Calculated', LVLookup: 'Lookup',
    };

    const lists = new Map();
    const madeFields = new Set();
    const targetRows = [];
    const files = new Map();
    const itemsById = new Map();
    let nextItemId = 1;
    let nextTargetId = 1;

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FILE_URL = /^web\\/GetFileByServerRelativeUrl\\('([^']*)'\\)(.*)$/;
    const FOLDER_URL = /^web\\/GetFolderByServerRelativeUrl\\('([^']*)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const ADD_URL = /url='([^']+)'/;

    // How this SharePoint hands a DateTime back. 'bare-site-local' is the shape
    // the live run recorded: the right instant, rendered eight hours behind UTC
    // and carrying neither a Z nor an offset, so a reader who parses it in the
    // BROWSER's zone gets a third answer again.
    const renderDate = (iso) => {
      if (CONFIG.dateReadBack === 'missing') return null;
      const ms = Date.parse(iso);
      if (CONFIG.dateReadBack === 'utc-z') return new Date(ms).toISOString();
      const shift = CONFIG.dateReadBack === 'wrong-day' ? 86400000 : 0;
      const offsetMin = CONFIG.dateReadBack === 'bare-utc' ? 0 : -480;
      return new Date(ms + shift + offsetMin * 60000)
        .toISOString().replace(/\\.000Z$/, '');
    };

    // Which payload shape the multi-value column arrived in. The probe tries
    // three and this tenant accepts exactly one, so a run that keeps the wrong
    // one writes nothing and a run that keeps none stops.
    const shapeOf = (value) => {
      if (Array.isArray(value)) return 'bare-array';
      if (value && Array.isArray(value.results)) {
        return value.__metadata ? 'collection-metadata' : 'bare-results';
      }
      return 'unknown';
    };

    const readItem = (item, select) => {
      const out = { Id: item.Id, FileLeafRef: item.FileLeafRef };
      if (/LVCalc/.test(select)) {
        // Serialised the way the live run reported it, as decimal text.
        out.LVCalc = item.LVNumber === null || item.LVNumber === undefined
          ? null : `${(item.LVNumber * 2).toFixed(14)}`;
        return out;
      }
      out.LVText = item.LVText;
      out.LVChoice = item.LVChoice;
      out.LVNumber = item.LVNumber;
      out.LVDate = item.LVDate === null ? null : renderDate(item.LVDate);
      out.LVMultiChoice = item.LVMultiChoice;
      out.LVLookupId = item.LVLookupId;
      return out;
    };

    globalThis.fetch = async (url, init = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const method = init.method || 'GET';
      const headers = init.headers || {};
      const verb = headers['X-HTTP-Method'] || method;
      let payload = null;
      if (typeof init.body === 'string') {
        try { payload = JSON.parse(init.body); } catch { payload = null; }
      }

      if (path === 'contextinfo') {
        return jsonResponse(200, {
          d: { GetContextWebInformation: { FormDigestValue: 'digest' } },
        });
      }

      if (path.startsWith('web/RegionalSettings/TimeZone')) {
        if (CONFIG.zone === 'unreadable') {
          return jsonResponse(500, { error: 'the regional settings are unavailable' });
        }
        if (CONFIG.zone === 'no-information') {
          return jsonResponse(200, { Description: '(UTC-08:00) Pacific Time' });
        }
        return jsonResponse(200, {
          Description: '(UTC-08:00) Pacific Time',
          Information: { Bias: 480, StandardBias: 0, DaylightBias: -60 },
        });
      }

      if (path === 'web/lists' && method === 'POST') {
        const id = `{list-${lists.size + 1}}`;
        lists.set(payload.Title, { Id: id, Title: payload.Title });
        return jsonResponse(200, { Id: id, Title: payload.Title });
      }

      // A file upload. The body is the file's bytes, so it never parses as JSON.
      const folder = path.match(FOLDER_URL);
      if (folder && method === 'POST') {
        const named = folder[2].match(ADD_URL);
        const name = named ? named[1] : null;
        if (name === null) return jsonResponse(400, { error: 'no url argument' });
        if (!files.has(name)) {
          const item = {
            Id: nextItemId, FileLeafRef: name, LVText: null, LVChoice: null,
            LVNumber: null, LVDate: null, LVMultiChoice: null, LVLookupId: null,
          };
          nextItemId += 1;
          files.set(name, item);
          itemsById.set(item.Id, item);
        }
        return jsonResponse(200, { ServerRelativeUrl: `${ROOT}/${name}` });
      }

      const fileRead = path.match(FILE_URL);
      if (fileRead) {
        const name = fileRead[1].slice(fileRead[1].lastIndexOf('/') + 1);
        const item = files.get(name);
        if (!item) return jsonResponse(404, { error: `no file named ${name}` });
        const select = fileRead[2];
        if (/\\$select=Id$/.test(select)) return jsonResponse(200, { Id: item.Id });
        return jsonResponse(200, readItem(item, select));
      }

      const list = path.match(LIST);
      if (list) {
        const title = list[1].replace(/''/g, "'");
        const rest = list[2];
        const held = lists.get(title);
        if (!held) return jsonResponse(404, { error: `no list named ${title}` });

        if (rest.startsWith('/fields/createfieldasxml')) {
          const named = String(payload.parameters.SchemaXml).match(/Name="([^"]+)"/);
          madeFields.add(named[1]);
          return jsonResponse(200, { InternalName: named[1] });
        }
        const field = rest.match(FIELD);
        if (field) {
          const name = field[1];
          if (!madeFields.has(name)) {
            return jsonResponse(404, { error: `no field named ${name}` });
          }
          return jsonResponse(200, {
            InternalName: name,
            TypeAsString: FIELD_TYPES[name],
            LookupList: name === 'LVLookup' ? lists.get(TGT).Id : undefined,
            OutputType: name === 'LVCalc' ? 9 : undefined,
          });
        }
        if (rest.startsWith('/RootFolder')) {
          return jsonResponse(200, { ServerRelativeUrl: ROOT });
        }
        if (rest.includes('ListItemEntityTypeFullName')) {
          return jsonResponse(200, {
            ListItemEntityTypeFullName: 'SP.Data.LargeLibItem',
          });
        }

        // A MERGE onto one library item: the column write the whole fixture
        // rests on.
        const item = rest.match(ITEM);
        if (item && verb === 'MERGE') {
          const held2 = itemsById.get(Number(item[1]));
          if (!held2) return jsonResponse(404, { error: 'no such item' });
          // __metadata is a verbose construct and a nometadata Content-Type
          // rejects it rather than ignoring it. The probe pairs the two, and a
          // mock that accepted the mismatch would let that pairing rot.
          const contentType = headers['Content-Type'] || '';
          if (payload.__metadata && !/verbose/.test(contentType)) {
            return jsonResponse(400, {
              'odata.error': { message: { value: 'metadata sent without verbose odata' } },
            });
          }
          const sent = shapeOf(payload.LVMultiChoice);
          if (sent !== CONFIG.multiShape) {
            return jsonResponse(400, {
              'odata.error': {
                code: '-1, Microsoft.SharePoint.Client.InvalidClientQueryException',
                message: { value: `the ${sent} payload is not accepted here` },
              },
            });
          }
          held2.LVText = CONFIG.textWrite === 'dropped' ? null : payload.LVText;
          held2.LVChoice = payload.LVChoice;
          held2.LVNumber = payload.LVNumber;
          held2.LVDate = payload.LVDate;
          held2.LVMultiChoice = payload.LVMultiChoice.results
            || payload.LVMultiChoice;
          held2.LVLookupId = payload.LVLookupId;
          return jsonResponse(204, {});
        }

        if (rest.startsWith('/items') && method === 'POST') {
          const row = { Id: nextTargetId, Title: payload.Title };
          nextTargetId += 1;
          targetRows.push(row);
          return jsonResponse(200, row);
        }
        if (rest.startsWith('/items')) {
          if (title === TGT) {
            return jsonResponse(200, { value: targetRows.map((row) => ({ ...row })) });
          }
          // The resume read: the newest file by Id, and nothing else.
          const all = [...files.values()].sort((a, b) => b.Id - a.Id);
          const top = all.slice(0, 1)
            .map((held3) => ({ Id: held3.Id, FileLeafRef: held3.FileLeafRef }));
          return jsonResponse(200, { value: top });
        }
        return jsonResponse(200, { Id: held.Id, Title: held.Title });
      }

      return jsonResponse(404, { error: `unrouted ${method} ${path}` });
    };
""")


#: The build is shrunk so a test run is a few hundred requests rather than
#: sixteen thousand. Every value is still a pure function of the file number, so
#: a twelve-file fixture exercises the same comparisons as a 5,500-file one.
_LARGE_LIST_SHRINK = {
    "TARGET_FILES": ("5500", "12"),
    "UPLOAD_CAP": ("1000", "12"),
    "VERIFY_EVERY": ("250", "4"),
}


def _large_list_probe_js() -> str:
    """The rendered fixture probe with its gates open, its build on, its size
    shrunk and its result table exposed."""
    js = LARGE_LIST_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES", "BUILD_FIXTURE"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    for name, (shipped, small) in _LARGE_LIST_SHRINK.items():
        shrunk = js.replace(f"  const {name} = {shipped};", f"  const {name} = {small};", 1)
        assert shrunk != js, f"{name} does not ship as {shipped}"
        js = shrunk
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_large_list_probe(**config: str) -> dict[str, dict[str, str]]:
    """Run the fixture probe and return id -> the whole recorded row."""
    settings: dict[str, str] = {
        # The shape the live run recorded, so every test here runs against it
        # and a probe that parses a bare stamp in the browser's zone cannot
        # pass by default.
        "dateReadBack": "bare-site-local",
        "multiShape": "bare-array",
        "zone": "pacific",
        "textWrite": "ok",
        **config,
    }
    script = (
        _LARGE_LIST_HARNESS.replace("__CONFIG__", json.dumps(settings))
        + "\n"
        + _large_list_probe_js()
    )
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_read_back_in_the_site_zone_is_not_read_as_a_lost_write() -> None:
    """The 2026-09-08 regression, as a gate. The tenant returns LVDate as the
    right instant rendered in the site's zone and naming no zone, which is the
    same instant the write carried. The build must complete rather than declare
    file one incomplete and redo it on every paste.
    """
    rows = _run_large_list_probe()

    assert rows["library.large-list.fixture-file-count"]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-values-written"]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-calculated-column-computes"]["outcome"] == "PASS"
    # The form is OBSERVED, so the row has to print which one came back rather
    # than leave a reader to assume it was UTC.
    evidence = rows["library.large-list.fixture-values-written"]["evidence"]
    assert "a wall clock naming no zone, -480min" in evidence, evidence
    assert "the site's candidate offsets are +0min / -480min / -420min" in evidence, evidence


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("shape", ["utc-z", "bare-utc"])
def test_a_date_read_back_as_utc_is_the_same_instant(shape: str) -> None:
    """The other two forms the same instant can arrive in. A tenant that answers
    with a Z, and one that answers a bare stamp that is already UTC, are both
    the instant that was written and neither is a lost write."""
    rows = _run_large_list_probe(dateReadBack=shape)

    assert rows["library.large-list.fixture-file-count"]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-values-written"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_a_day_out_is_still_read_as_a_lost_write() -> None:
    """The tolerance must not swallow the thing it was widened for. Resolving a
    zone-less stamp against the site's offsets moves it by at most eight hours
    here, and consecutive files are a day apart, so a date off by a day has to
    stay a mismatch.
    """
    rows = _run_large_list_probe(dateReadBack="wrong-day")

    assert rows["library.large-list.fixture-file-count"]["outcome"] == "SHORT"
    assert "LVDate=" in rows["library.large-list.fixture-file-count"]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_that_never_arrives_is_read_as_a_lost_write() -> None:
    """A MERGE that took for every column but this one. The instant comparison
    must not read a missing value as a formatting difference."""
    rows = _run_large_list_probe(dateReadBack="missing")

    assert rows["library.large-list.fixture-file-count"]["outcome"] == "SHORT"
    assert "LVDate=null" in rows["library.large-list.fixture-file-count"]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("shape", ["bare-array", "bare-results", "collection-metadata"])
def test_the_first_payload_shape_that_writes_and_reads_back_wins(shape: str) -> None:
    """The shape experiment, against a tenant accepting each candidate in turn.
    Whichever one this tenant takes, the build completes and the row names it,
    because the winner is observed rather than assumed."""
    rows = _run_large_list_probe(multiShape=shape)

    assert rows["library.large-list.fixture-file-count"]["outcome"] == "PASS"
    written = rows["library.large-list.fixture-values-written"]
    assert written["outcome"] == "PASS"
    assert f"the shape that took is '{shape}'" in written["evidence"], written["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_shape_that_took_is_not_discarded_for_another_columns_mismatch() -> None:
    """The depends-on / observes split, as a gate. LVText does not write, and
    the multi-value shape has nothing to do with that. The run must stop naming
    LVText, and must not report that no payload shape worked: bare-array wrote
    LVMultiChoice and read it back, which is the whole question a shape answers.
    """
    rows = _run_large_list_probe(textWrite="dropped")

    count = rows["library.large-list.fixture-file-count"]
    assert count["outcome"] == "SHORT"
    assert "LVText=null" in count["evidence"], count["evidence"]
    assert "no multi-value item payload shape" not in count["evidence"], count["evidence"]
    assert "the multi-value payload shape in use is 'bare-array'" in count["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_tenant_that_takes_no_payload_shape_stops_the_build() -> None:
    """Every candidate refused. That is a real answer about this tenant and the
    row has to say so, rather than upload files with an empty column."""
    rows = _run_large_list_probe(multiShape="none")

    count = rows["library.large-list.fixture-file-count"]
    assert count["outcome"] == "SHORT"
    assert "no multi-value item payload shape wrote LVMultiChoice" in count["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("zone", ["unreadable", "no-information"])
def test_a_site_zone_that_does_not_read_stops_the_build_rather_than_guessing(
    zone: str,
) -> None:
    """Fail closed. Without the site's offsets a zone-less stamp cannot be
    resolved, and a comparison that guessed would either redo a correct fixture
    from file one or certify a broken one. Nothing is uploaded and every row
    from the file count down stays open.
    """
    rows = _run_large_list_probe(zone=zone)

    # The library, the target list and the columns were all built before the
    # zone is needed, so they still answer.
    assert rows["library.large-list.fixture-columns-created"]["outcome"] == "PASS"
    for check in (
        "library.large-list.fixture-file-count",
        "library.large-list.fixture-values-written",
        "library.large-list.fixture-calculated-column-computes",
        "library.large-list.fixture-distribution",
    ):
        assert rows[check]["outcome"] == "ABORTED", check
        assert rows[check]["state"] == "open", check
    assert "RegionalSettings" in rows["library.large-list.fixture-file-count"]["evidence"]


LARGE_LIST_INDEX_PROBE = MANUAL / "library-large-list-index-probe.js"

#: A SharePoint holding the built large-library fixture, controllable in the
#: ways this measurement can go wrong: whether the threshold is enforced at
#: all, what a filter on a column that does not exist comes back as, whether an
#: index MERGE takes, is silently dropped or is refused, and how many queries
#: pass before the index behind an accepted flag actually serves.
_LARGE_LIST_INDEX_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const LIB = 'dbmlsp Probe LargeLib';
    const COUNT = CONFIG.count;
    const PAGE = 100;
    const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
    const TYPES = {
      LVText: 'Text', LVNumber: 'Number', LVChoice: 'Choice', LVDate: 'DateTime',
      LVMultiChoice: 'MultiChoice', LVLookup: 'Lookup', LVCalc: 'Calculated',
    };
    const ENTITY_TYPES = {
      LVText: 'SP.FieldText', LVNumber: 'SP.FieldNumber', LVChoice: 'SP.FieldChoice',
      LVDate: 'SP.FieldDateTime', LVMultiChoice: 'SP.FieldMultiChoice',
      LVLookup: 'SP.FieldLookup', LVCalc: 'SP.FieldCalculated',
    };

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;

    // One entry per contract column: the flag, the description, and how many
    // more queries have to arrive before the index behind an accepted flag
    // serves anything. The last one is what makes the asynchronous build
    // testable rather than a comment.
    const fields = new Map();
    for (const name of Object.keys(TYPES)) {
      fields.set(name, {
        Indexed: CONFIG.preIndexed.indexOf(name) !== -1,
        AutoIndexed: false,
        Description: '',
        pending: 0,
      });
    }

    const fileName = (n) => `dbmlsp-lv-${String(n).padStart(5, '0')}.txt`;
    // The fixture's own value formulas. A mock answering with a fixed row
    // count would let the probe's count comparison pass on the wrong query.
    const valueFor = (n) => ({
      LVText: `text-${n % 100}`,
      LVChoice: CHOICES[n % 4],
      LVNumber: n % 1000,
    });
    const rowsMatching = (column, literal) => {
      const out = [];
      for (let n = 1; n <= COUNT; n += 1) {
        const held = valueFor(n)[column];
        if (held !== undefined && String(held) === String(literal)) out.push(n);
      }
      return out;
    };

    const throttled = () => jsonResponse(500, {
      'odata.error': {
        code: '-2147024860, Microsoft.SharePoint.SPQueryThrottledException',
        message: {
          value: 'The attempted operation is prohibited because it exceeds the '
            + 'list view threshold enforced by the administrator.',
        },
      },
    });
    const noSuchColumn = (column) => (CONFIG.absentColumn === 'throttled'
      ? throttled()
      : jsonResponse(400, {
        'odata.error': {
          message: { value: `Field or property "${column}" does not exist.` },
        },
      }));

    const canServe = (state) => {
      if (CONFIG.throttle === 'off') return true;
      if (!state.Indexed) return false;
      if (state.pending > 0) { state.pending -= 1; return false; }
      return true;
    };
    const page = () => {
      const out = [];
      for (let n = 1; n <= Math.min(PAGE, COUNT); n += 1) out.push({ Id: n });
      return out;
    };
    const writeMode = (name) => CONFIG.indexWrite[name] || CONFIG.indexWrite.default;

    globalThis.fetch = async (url, init = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const method = init.method || 'GET';
      const headers = init.headers || {};
      const verb = headers['X-HTTP-Method'] || method;
      let payload = null;
      if (typeof init.body === 'string') {
        try { payload = JSON.parse(init.body); } catch { payload = null; }
      }

      if (path === 'contextinfo') {
        return jsonResponse(200, {
          d: { GetContextWebInformation: { FormDigestValue: 'digest' } },
        });
      }

      const list = path.match(LIST);
      if (!list) return jsonResponse(404, { error: `unrouted ${method} ${path}` });
      if (list[1] !== LIB || CONFIG.library === 'missing') {
        return jsonResponse(404, { error: `no list named ${list[1]}` });
      }
      const rest = list[2];

      const field = rest.match(FIELD);
      if (field) {
        const name = field[1];
        const state = fields.get(name);
        if (!state) return jsonResponse(404, { error: `no field named ${name}` });

        if (verb === 'MERGE') {
          // __metadata is a verbose construct and a nometadata Content-Type
          // rejects it rather than ignoring it. The probe pairs the two, and a
          // mock that accepted the mismatch would let that pairing rot.
          const contentType = headers['Content-Type'] || '';
          if (payload.__metadata && !/verbose/.test(contentType)) {
            return jsonResponse(400, {
              'odata.error': { message: { value: 'metadata sent without verbose odata' } },
            });
          }
          const sentType = payload.__metadata ? payload.__metadata.type : null;
          const keys = Object.keys(payload).filter((key) => key !== '__metadata');
          const unknown = keys.filter(
            (key) => key !== 'Indexed' && key !== 'Description');
          if (unknown.length && CONFIG.unknownProperty !== 'accepted') {
            return jsonResponse(400, {
              'odata.error': {
                message: {
                  value: `The property '${unknown[0]}' does not exist on type 'SP.Field'.`,
                },
              },
            });
          }
          if (Object.prototype.hasOwnProperty.call(payload, 'Description')
              && CONFIG.descriptionWrite !== 'dropped') {
            state.Description = payload.Description;
          }
          if (Object.prototype.hasOwnProperty.call(payload, 'Indexed')) {
            const mode = writeMode(name);
            if (mode === 'refused') {
              return jsonResponse(500, {
                'odata.error': {
                  message: { value: 'This field type does not support indexing.' },
                },
              });
            }
            if (mode === 'type-hint' && sentType === 'SP.Field') {
              return jsonResponse(500, {
                'odata.error': {
                  message: { value: `Cannot convert SP.Field to ${ENTITY_TYPES[name]}.` },
                },
              });
            }
            if (mode !== 'ignored') {
              state.Indexed = payload.Indexed === true;
              state.pending = payload.Indexed === true ? CONFIG.buildAttempts : 0;
            }
          }
          console.log(`__MERGE__ ${name} ${JSON.stringify(keys)}`);
          return jsonResponse(204, {});
        }

        const body = {
          InternalName: name,
          TypeAsString: CONFIG.columnTypes[name] || TYPES[name],
          Indexed: state.Indexed,
          AutoIndexed: state.AutoIndexed,
          Description: state.Description,
        };
        if (/verbose/.test(headers.Accept || '')) {
          return jsonResponse(200, {
            d: { ...body, __metadata: { type: ENTITY_TYPES[name] } },
          });
        }
        return jsonResponse(200, body);
      }

      if (rest.startsWith('/items')) {
        const orderby = rest.match(/\\$orderby=([^&]+)/);
        // The count read: the newest file by Id, which Id's native index
        // serves past the threshold.
        if (orderby && /^Id desc/.test(orderby[1])) {
          return jsonResponse(200, {
            value: [{ Id: COUNT, FileLeafRef: fileName(COUNT) }],
          });
        }

        const filter = rest.match(/\\$filter=(.+)$/);
        if (filter) {
          const parsed = String(filter[1]).match(
            /^(\\w+) eq (?:'([^']*)'|([0-9]+))$/);
          if (!parsed) {
            return jsonResponse(400, {
              'odata.error': { message: { value: `unparsed filter ${filter[1]}` } },
            });
          }
          const column = parsed[1];
          const literal = parsed[2] === undefined ? Number(parsed[3]) : parsed[2];
          if (column === 'Id') {
            return jsonResponse(200, {
              value: literal <= COUNT ? [{ Id: literal }] : [],
            });
          }
          const state = fields.get(column);
          if (!state) return noSuchColumn(column);
          if (!canServe(state)) return throttled();
          return jsonResponse(200, {
            value: rowsMatching(column, literal).slice(0, PAGE).map((n) => ({ Id: n })),
          });
        }

        if (orderby) {
          const column = String(orderby[1]).split(' ')[0];
          if (column === 'Id') return jsonResponse(200, { value: page() });
          const state = fields.get(column);
          if (!state) return noSuchColumn(column);
          if (!canServe(state)) return throttled();
          return jsonResponse(200, { value: page() });
        }
        return jsonResponse(400, { error: `unrouted items query ${rest}` });
      }

      return jsonResponse(200, { Title: LIB, BaseTemplate: 101, ItemCount: COUNT });
    };
""")


#: The two waits, shrunk so the whole suite runs in milliseconds. Neither
#: figure changes what is measured: the wait is bounded by attempts, and the
#: attempts are what the row reports.
_LARGE_LIST_INDEX_SHRINK = {
    "REREAD_MS": ("1500", "1"),
    "INDEX_WAIT_MS": ("6000", "1"),
}


def _large_list_index_probe_js(remove_indexes: bool = False) -> str:
    """The rendered index probe with its gates open, its waits shrunk and its
    result table exposed.

    ``remove_indexes`` opens the teardown flag the operator sets on the paste
    that restores the fixture, so the restore runs here rather than only in a
    live console.
    """
    js = LARGE_LIST_INDEX_PROBE.read_text(encoding="utf-8")
    gates = ["CONFIRMED", "ALLOW_WRITES"]
    if remove_indexes:
        gates.append("REMOVE_INDEXES_AT_END")
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    for name, (shipped, small) in _LARGE_LIST_INDEX_SHRINK.items():
        shrunk = js.replace(
            f"  const {name} = {shipped};", f"  const {name} = {small};", 1
        )
        assert shrunk != js, f"{name} does not ship as {shipped}"
        js = shrunk
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _large_list_index_output(remove_indexes: bool = False, **config: Any) -> str:
    settings: dict[str, Any] = {
        "count": 5500,
        "library": "present",
        "throttle": "enforced",
        "absentColumn": "rejected",
        "descriptionWrite": "sticks",
        "unknownProperty": "refused",
        "indexWrite": {"default": "takes"},
        "buildAttempts": 0,
        "preIndexed": [],
        "columnTypes": {},
        **config,
    }
    return _run(
        _LARGE_LIST_INDEX_HARNESS.replace("__CONFIG__", json.dumps(settings))
        + "\n"
        + _large_list_index_probe_js(remove_indexes=remove_indexes)
    )


def _run_large_list_index_probe(**config: Any) -> dict[str, dict[str, str]]:
    """Run the index probe and return id -> the whole recorded row."""
    output = _large_list_index_output(**config)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_index_that_takes_and_serves_is_read_as_the_index_serving() -> None:
    """The tenant this probe hopes for: every column accepts the flag and the
    index serves immediately. Every control holds, every column answers, and
    the two before/after rows and the per-column row all settle.
    """
    rows = _run_large_list_index_probe()

    assert rows["library.large-list.fixture-library-present"]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-index-flags-clear"]["outcome"] == "PASS"
    assert rows["library.large-list.control-id-query-served"]["outcome"] == (
        "SERVED (filter and sort)"
    )
    for column in ("text", "number", "choice", "date", "multichoice", "lookup",
                   "calculated"):
        check = f"library.large-list.index-{column}-column"
        assert rows[check]["outcome"] == "INDEXED", check
    assert rows["library.large-list.index-removes-filter-throttle"]["outcome"] == (
        "INDEX SERVES THE FILTER"
    )
    assert rows["library.large-list.index-removes-sort-throttle"]["outcome"] == (
        "INDEX SERVES THE SORT"
    )
    assert rows["library.large-list.index-is-per-column"]["outcome"] == "PER COLUMN"
    assert [row["id"] for row in rows.values() if row["state"] != "settled"] == []


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_flag_that_is_accepted_and_dropped_is_not_reported_as_an_index() -> None:
    """The failure class this repository exists to find: HTTP 204 and nothing
    changed. Both method controls hold, so the verdict is the column's.
    """
    rows = _run_large_list_index_probe(indexWrite={"default": "ignored"})

    assert rows["library.large-list.index-number-column"]["outcome"] == (
        "SILENTLY IGNORED"
    )
    assert rows["library.large-list.control-description-sticks"]["outcome"] == (
        "DESCRIPTION STUCK"
    )
    # No column carries an index, so neither before/after pair has an after
    # half, and neither row may claim one.
    for check in ("library.large-list.index-removes-filter-throttle",
                  "library.large-list.index-removes-sort-throttle"):
        assert rows[check]["outcome"] == "NOT ESTABLISHED", check
        assert "took an index" in rows[check]["evidence"], check


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_dropped_write_is_void_when_the_method_control_collapses() -> None:
    """A write that changed nothing and a write that never arrived are the same
    observation. With the Description control down, SILENTLY IGNORED is a
    verdict this run cannot support, so it is void rather than recorded.
    """
    rows = _run_large_list_index_probe(
        indexWrite={"default": "ignored"}, descriptionWrite="dropped",
    )

    assert rows["library.large-list.control-description-sticks"]["outcome"] == (
        "CONTROL FAILED, METHOD VOID"
    )
    row = rows["library.large-list.index-number-column"]
    assert row["outcome"] == "VOID"
    assert row["state"] == "void"
    assert "never arrived" in row["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_after_half_waits_for_an_index_that_is_still_building() -> None:
    """SharePoint builds the index behind the flag. Three refusals then an
    answer is an index that works, and the row has to reach it rather than
    conclude on the first refusal.
    """
    rows = _run_large_list_index_probe(buildAttempts=3)

    row = rows["library.large-list.index-removes-filter-throttle"]
    assert row["outcome"] == "INDEX SERVES THE FILTER"
    assert "over 4 attempt(s)" in row["evidence"], row["evidence"]
    assert rows["library.large-list.index-removes-sort-throttle"]["outcome"] == (
        "INDEX SERVES THE SORT"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_index_that_never_serves_is_not_reported_as_the_index_failing() -> None:
    """The wait runs out. That is not evidence that the index does not lift the
    throttle, and the row must stay open and say why.
    """
    rows = _run_large_list_index_probe(buildAttempts=999)

    row = rows["library.large-list.index-removes-filter-throttle"]
    assert row["outcome"] == "NOT ESTABLISHED (still refused after 10 attempt(s))"
    assert row["state"] == "open"
    assert "builds the index behind the flag" in row["evidence"]
    # The flag itself still took, and that is a separate question with its own
    # answer.
    assert rows["library.large-list.index-number-column"]["outcome"] == "INDEXED"
    assert rows["library.large-list.index-is-per-column"]["outcome"] == (
        "NOT ESTABLISHED"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throttled_refusal_on_a_column_that_does_not_exist_voids_the_pairs() -> None:
    """If a filter naming a column the library does not hold comes back
    carrying the throttle signature, no refusal in this run can be attributed
    to the threshold. The three measurements are void, not open.
    """
    rows = _run_large_list_index_probe(absentColumn="throttled")

    assert rows["library.large-list.control-absent-column-refused"]["outcome"] == (
        "CONTROL FAILED, METHOD VOID"
    )
    for check in ("library.large-list.index-removes-filter-throttle",
                  "library.large-list.index-removes-sort-throttle",
                  "library.large-list.index-is-per-column"):
        assert rows[check]["outcome"] == "VOID", check
        assert rows[check]["state"] == "void", check
    # The index writes are a different question and still answer.
    assert rows["library.large-list.index-lookup-column"]["outcome"] == "INDEXED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_library_short_of_the_threshold_is_not_written_to_at_all() -> None:
    """The fixture is somebody else's expensive object. A run that cannot
    verify it writes nothing to it, and every question says so.
    """
    output = _large_list_index_output(count=400)
    line = next(ln for ln in output.splitlines() if ln.startswith("__ROWS__"))
    rows = {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}

    assert rows["library.large-list.fixture-library-present"]["outcome"] == "SHORT"
    assert rows["library.large-list.index-number-column"]["outcome"] == "ABORTED"
    assert rows["library.large-list.index-number-column"]["state"] == "open"
    assert "__MERGE__" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_that_arrives_indexed_cannot_supply_the_unindexed_half() -> None:
    """SharePoint has been measured indexing a column on its own between two
    runs. A column already carrying an index has no before half, and the rows
    that need one must say that rather than report the after half alone.
    """
    rows = _run_large_list_index_probe(preIndexed=["LVNumber", "LVText"])

    flags = rows["library.large-list.fixture-index-flags-clear"]
    assert flags["outcome"] == "ALREADY INDEXED"
    assert flags["state"] == "open"
    assert rows["library.large-list.index-number-column"]["outcome"] == (
        "NOT ESTABLISHED"
    )
    for check in ("library.large-list.index-removes-filter-throttle",
                  "library.large-list.index-removes-sort-throttle"):
        assert rows[check]["outcome"] == "NOT ESTABLISHED", check
        assert "started unindexed" in rows[check]["evidence"], check


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_type_hint_is_not_reported_as_a_refused_column() -> None:
    """The retry that separates the two. SP.Field is refused, the type
    SharePoint reports for the field is accepted, and the column is indexed:
    reporting REFUSED there would retire a column that works.
    """
    rows = _run_large_list_index_probe(indexWrite={"default": "type-hint"})

    row = rows["library.large-list.index-calculated-column"]
    assert row["outcome"] == "INDEXED"
    assert "The refusal was the TYPE HINT" in row["evidence"]


#: What the live run of 2026-09-08 left on the fixture: the five plain
#: single-value columns took an index, MultiChoice and Calculated refused one.
#: That state is what the REMOVE_INDEXES_AT_END re-paste has to find and clear.
_LEFT_INDEXED = ["LVText", "LVNumber", "LVChoice", "LVDate", "LVLookup"]
_REFUSES_AN_INDEX = {"LVMultiChoice": "refused", "LVCalc": "refused"}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_teardown_clears_the_indexes_an_earlier_run_left() -> None:
    """The paste that restores the fixture is, by construction, a run that
    finds the columns already indexed: the run before it indexed them.

    Measured on 2026-09-08: a teardown scoped to the columns THIS run indexed
    from unindexed matched nothing on that paste and reverted nothing, while
    the header promised the fixture back. So the columns that arrive indexed
    are cleared too.
    """
    output = _large_list_index_output(
        remove_indexes=True,
        preIndexed=_LEFT_INDEXED,
        indexWrite={"default": "takes", **_REFUSES_AN_INDEX},
    )

    for column in _LEFT_INDEXED:
        assert f"[OK] {column}: Indexed is back to false." in output, column
    # Neither of these ever carried an index, so there is nothing on them to
    # put back and the teardown must not report clearing one.
    for column in ("LVMultiChoice", "LVCalc"):
        assert f"{column}: Indexed is back to false." not in output, column
    assert (
        "[OK] Teardown: 5 of 5 column(s) read Indexed=false on the readback"
    ) in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_teardown_clears_what_this_run_indexed() -> None:
    """The other half of the union, unchanged: a run that indexes seven columns
    from unindexed and is told to tidy up puts all seven back."""
    output = _large_list_index_output(remove_indexes=True)

    for column in ("LVText", "LVNumber", "LVChoice", "LVDate", "LVMultiChoice",
                   "LVLookup", "LVCalc"):
        assert f"[OK] {column}: Indexed is back to false." in output, column
    assert (
        "[OK] Teardown: 7 of 7 column(s) read Indexed=false on the readback"
    ) in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_teardown_write_that_changes_nothing_is_not_reported_as_restored() -> None:
    """The teardown writes, so it reads back. A MERGE accepted and dropped
    leaves the fixture indexed, and a run that said otherwise would send the
    next operator to measure a before half that is not there.
    """
    output = _large_list_index_output(
        remove_indexes=True,
        preIndexed=_LEFT_INDEXED,
        indexWrite={"default": "ignored"},
    )

    for column in _LEFT_INDEXED:
        assert f"[FAIL] {column}: Indexed is still true" in output, column
    assert "[FAIL] Teardown: 0 of 5 column(s) read Indexed=false" in output
    assert "STILL INDEXED: LVText, LVNumber, LVChoice, LVDate, LVLookup" in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_measurement_run_reverts_nothing_and_names_both_sets() -> None:
    """Without the flag nothing is undone, which is what a run still waiting on
    an index build needs. The two sets are reported apart: what this run
    indexed, and what it found already indexed.
    """
    output = _large_list_index_output(preIndexed=["LVChoice"])

    assert "Indexed is back to false" not in output
    assert (
        "The fixture's columns are LEFT INDEXED: LVText, LVNumber, LVDate, "
        "LVMultiChoice, LVLookup, LVCalc."
    ) in output
    assert "Still indexed from a previous run: LVChoice." in output


# --------------------------------------------------------------------------
# library-builtin-view-probe.js: which view each row is about, and what it
# records when the step that row depends on did not answer.
# --------------------------------------------------------------------------
BUILTIN_VIEW_PROBE = MANUAL / "library-builtin-view-probe.js"

#: What the harness does when nothing is asked of it: a library whose built-in
#: view sits on AllItems.aspx under a title of its own, every write taking and
#: every read answering. Two of those are the live run of 2026-09-13 rather
#: than a convenience, and the rest of this file varies one knob at a time:
#: the built-in view reads 'All Documents' on AllItems.aspx, and a second view
#: created under the slug is minted AllItems1.aspx.
_BUILTIN_VIEW_DEFAULTS: dict[str, Any] = {
    # Where the library's built-in view sits. 'AllDocuments.aspx' leaves
    # AllItems.aspx free while a default view still exists.
    "builtinBasename": "AllItems.aspx",
    # 'normal', 'missing' (the created view never appears in the collection),
    # 'unreadable' (the collection read after the create fails).
    "collisionReadback": "normal",
    # 'takes', 'ignored' (the MERGE answers OK and the Title does not move),
    # 'refused'.
    "rename": "takes",
    # 'replaced', or 'survivor': removeallviewfields leaves one field behind
    # and addviewfield answers OK without applying anything.
    "viewFields": "replaced",
    # Does hiding the default view move DefaultView to another view?
    "hideMovesDefault": False,
    # Restoring Hidden to false: 'takes', 'ignored', 'refused'.
    "restore": "takes",
    # How a read of a view that is no longer there answers: 'absent' (404) or
    # 'transient' (500, which proves nothing either way).
    "missingViewRead": "absent",
    # Whether the view collection still reads back after the DELETE.
    "viewsAfterDelete": "readable",
}

#: A SharePoint holding lists of views, controllable in the eight ways a run
#: of this probe can go wrong without any request failing outright. It also
#: keeps every view write, so a test can ask WHICH view was renamed or
#: deleted rather than only what the run recorded about it.
_BUILTIN_VIEW_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const writes = [];
    globalThis.__writes = writes;

    const lists = new Map();
    let nextList = 1;
    let nextView = 1;
    // Armed by the call it belongs to rather than by a request count, which
    // would shift the moment a question is added earlier in the run.
    let failNextLibraryViewList = false;

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const BY_ID = /^\\/views\\('([^']+)'\\)(.*)$/;
    const BY_TITLE = /^\\/views\\/getbytitle\\('(.*?)'\\)/;
    const ADD_FIELD = /^\\/ViewFields\\/addviewfield\\('([^']+)'\\)$/;

    const baseOf = (view) => view.ServerRelativeUrl.split('/').pop();
    const publicShape = (view) => ({
      Id: view.Id, Title: view.Title, ServerRelativeUrl: view.ServerRelativeUrl,
      DefaultView: view.DefaultView, Hidden: view.Hidden, Scope: view.Scope,
      PersonalView: view.PersonalView,
    });

    const makeView = (held, title, basename, extra = {}) => {
      const view = {
        Id: `view-${nextView}`,
        Title: title,
        ServerRelativeUrl: `${held.ServerRelativeUrl}/Forms/${basename}`,
        DefaultView: false, Hidden: false, Scope: 0, PersonalView: false,
        fields: ['DocIcon', 'LinkFilename', 'Modified'],
        ...extra,
      };
      nextView += 1;
      held.views.push(view);
      return view;
    };

    // The basename SharePoint mints for a new view: the title, suffixed until
    // it names a page nothing else holds.
    const mint = (held, title) => {
      const taken = (name) => held.views.some(
        (v) => baseOf(v).toLowerCase() === name.toLowerCase());
      if (!taken(`${title}.aspx`)) return `${title}.aspx`;
      let n = 1;
      while (taken(`${title}${n}.aspx`)) n += 1;
      return `${title}${n}.aspx`;
    };

    const createList = (title, template) => {
      const held = {
        Id: `list-${nextList}`, Title: title, BaseTemplate: template,
        ServerRelativeUrl: `/sites/test/${nextList}`, views: [],
      };
      nextList += 1;
      lists.set(title, held);
      makeView(held,
               template === 101 ? 'All Documents' : 'All Items',
               template === 101 ? CONFIG.builtinBasename : 'AllItems.aspx',
               { DefaultView: true });
      return held;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url).split('/_api/')[1] || '';
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = () => JSON.parse(opts.body === undefined ? '{}' : String(opts.body));

      if (u.startsWith('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u === 'web/lists' && method === 'POST') {
        const made = sent();
        return jsonResponse(201, { Id: createList(made.Title, made.BaseTemplate).Id });
      }

      const named = LIST.exec(u);
      if (!named) return jsonResponse(404, { error: `no such endpoint: ${u}` });
      const held = lists.get(named[1]);
      if (!held) return jsonResponse(404, { error: 'list not found' });
      const rest = named[2].split('?')[0];

      if (rest === '') return jsonResponse(200, { Id: held.Id, Title: held.Title });

      if (rest === '/views' && method === 'POST') {
        const made = sent();
        const view = makeView(held, made.Title, mint(held, made.Title));
        writes.push({ op: 'create', view: view.Id, title: made.Title });
        if (made.Title === 'AllItems' && CONFIG.collisionReadback === 'missing') {
          view.invisible = true;
        }
        if (made.Title === 'AllItems' && CONFIG.collisionReadback === 'unreadable') {
          failNextLibraryViewList = true;
        }
        return jsonResponse(201, { Id: view.Id });
      }
      if (rest === '/views') {
        if (held.BaseTemplate === 101 && failNextLibraryViewList) {
          failNextLibraryViewList = false;
          return jsonResponse(500, { error: 'the view collection could not be read' });
        }
        return jsonResponse(200, {
          value: held.views.filter((v) => !v.invisible).map(publicShape),
        });
      }

      const byTitle = BY_TITLE.exec(rest);
      if (byTitle) {
        const wanted = byTitle[1].replace(/''/g, "'");
        const found = held.views.find((v) => v.Title === wanted);
        return found ? jsonResponse(200, publicShape(found))
                     : jsonResponse(404, { error: 'view not found' });
      }

      const byId = BY_ID.exec(rest);
      if (!byId) return jsonResponse(404, { error: `no such endpoint: ${rest}` });
      const view = held.views.find((v) => v.Id === byId[1]);
      if (!view) {
        return jsonResponse(CONFIG.missingViewRead === 'transient' ? 500 : 404,
                            { error: 'view not found' });
      }
      const tail = byId[2];

      if (tail === '' && verb === 'MERGE') {
        const body = sent();
        writes.push({ op: 'merge', view: view.Id, title: view.Title, body });
        for (const [name, value] of Object.entries(body)) {
          if (name === '__metadata') continue;
          if (name === 'Title' && CONFIG.rename === 'refused') {
            return jsonResponse(500, { error: 'the Title could not be set' });
          }
          if (name === 'Title' && CONFIG.rename === 'ignored') continue;
          if (name === 'Hidden' && value === false && CONFIG.restore === 'refused') {
            return jsonResponse(500, { error: 'Hidden could not be cleared' });
          }
          if (name === 'Hidden' && value === false && CONFIG.restore === 'ignored') continue;
          view[name] = value;
          if (name === 'DefaultView' && value === true) {
            for (const other of held.views) {
              if (other !== view) other.DefaultView = false;
            }
          }
          if (name === 'Hidden' && value === true
              && CONFIG.hideMovesDefault && view.DefaultView) {
            view.DefaultView = false;
            const next = held.views.find((o) => o !== view && !o.Hidden);
            if (next) next.DefaultView = true;
          }
        }
        return jsonResponse(204, {});
      }
      if (tail === '' && verb === 'DELETE') {
        writes.push({ op: 'delete', view: view.Id, title: view.Title });
        held.views = held.views.filter((v) => v !== view);
        if (CONFIG.viewsAfterDelete === 'unreadable') failNextLibraryViewList = true;
        return jsonResponse(200, {});
      }
      if (tail === '' && method === 'GET') return jsonResponse(200, publicShape(view));

      if (tail === '/ViewFields' && method === 'GET') {
        return jsonResponse(200, { Items: { results: view.fields.slice() } });
      }
      if (tail === '/ViewFields/removeallviewfields' && method === 'POST') {
        view.fields = CONFIG.viewFields === 'survivor' ? ['DocIcon'] : [];
        return jsonResponse(200, {});
      }
      const add = ADD_FIELD.exec(tail);
      if (add && method === 'POST') {
        if (CONFIG.viewFields !== 'survivor') view.fields.push(add[1]);
        return jsonResponse(200, {});
      }
      return jsonResponse(404, { error: `no such endpoint: ${rest}` });
    };
""")


def _builtin_view_probe_js() -> str:
    """The rendered built-in view probe with its gates open and its table
    exposed, alongside the view writes the run aimed at the mock.

    The dump goes inside report() rather than before one call of it: this
    probe returns report() from five places, and splicing at one of them
    would leave an aborted run invisible to these tests.
    """
    js = BUILTIN_VIEW_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n"
        "    console.log('__ROWS__' + JSON.stringify(RESULTS));\n"
        "    console.log('__WRITES__' + JSON.stringify(globalThis.__writes));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_builtin_view_probe(
    **overrides: Any,
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    """Run the probe and return id -> the whole recorded row, and the writes."""
    config = _BUILTIN_VIEW_DEFAULTS | overrides
    script = (
        _BUILTIN_VIEW_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _builtin_view_probe_js()
    )
    output = _run(script)
    rows = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert rows is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    writes = next(ln for ln in output.splitlines() if ln.startswith("__WRITES__"))
    return (
        {row["id"]: row for row in json.loads(rows.removeprefix("__ROWS__"))},
        json.loads(writes.removeprefix("__WRITES__")),
    )


#: Every row that only exists because a view was found on AllItems.aspx.
_BUILTIN_VIEW_ADOPTION = (
    "library.view.builtin-title-rename",
    "library.view.builtin-getbytitle-after-rename",
    "library.view.builtin-scope-merge",
    "library.view.builtin-viewfields-replace",
    "library.view.builtin-hidden-while-default",
    "library.view.builtin-hidden-once-not-default",
    "library.view.builtin-delete-once-not-default",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_library_answering_the_way_the_live_run_did_settles_every_row() -> None:
    """The baseline the failure cases are varied from, and the two values the
    live run of 2026-09-13 actually measured: the view on AllItems.aspx reads
    'All Documents', and a view created under the slug beside it is minted
    AllItems1.aspx.
    """
    rows, _writes = _run_builtin_view_probe()

    assert rows["library.view.builtin-occupies-allitems"]["outcome"] == "OCCUPIED"
    assert "'All Documents' at AllItems.aspx" in (
        rows["library.view.builtin-occupies-allitems"]["evidence"]
    )
    assert rows["library.view.create-allitems-title-on-library"]["outcome"] == "SUFFIXED"
    assert "AllItems1.aspx" in (
        rows["library.view.create-allitems-title-on-library"]["evidence"]
    )
    for check in _BUILTIN_VIEW_ADOPTION:
        assert rows[check]["outcome"] == "PASS", (check, rows[check])
    assert not [row for row in rows.values() if row["state"] != "settled"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_free_allitems_url_is_not_answered_by_renaming_the_default_view() -> None:
    """A library whose built-in view sits somewhere else leaves AllItems.aspx
    free, and FREE is the whole answer.

    Selecting the default view instead produced adoption evidence for a view
    that was never on the URL: the run renamed, refielded, hid and finally
    deleted a page nobody had asked about, and recorded FREE while doing it.
    """
    rows, writes = _run_builtin_view_probe(builtinBasename="AllDocuments.aspx")

    occupies = rows["library.view.builtin-occupies-allitems"]
    assert occupies["outcome"] == "FREE"
    assert "no public view on a bare library reports AllItems.aspx" in occupies["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == set(_BUILTIN_VIEW_ADOPTION)
    touched = [
        write for write in writes
        if write["op"] in {"merge", "delete"} and write["title"] == "All Documents"
    ]
    assert not touched, (
        f"the run wrote to the library's default view {touched}, which never held "
        f"AllItems.aspx, so every adoption row would be evidence about another page"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("readback", "evidence"),
    [
        ("missing", "no view titled 'AllItems' read back"),
        ("unreadable", "the view collection did not read back"),
    ],
)
def test_a_collision_nothing_read_back_is_not_evidence_of_a_suffix(
    readback: str, evidence: str,
) -> None:
    """SUFFIXED is a basename this run saw. The production adoption rule cites
    this row as live proof that SharePoint mints a suffixed page, so a create
    whose readback never found the view must not supply it.
    """
    rows, _writes = _run_builtin_view_probe(collisionReadback=readback)

    collide = rows["library.view.create-allitems-title-on-library"]
    assert collide["outcome"] == "NOT ESTABLISHED"
    assert evidence in collide["evidence"]
    assert "no basename was observed" in collide["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("rename", ["ignored", "refused"])
def test_a_getbytitle_lookup_after_a_failed_rename_is_not_a_lookup_result(
    rename: str,
) -> None:
    """The row asks whether getbytitle resolves a renamed view. A rename that
    never took leaves the lookup measuring the unmet prerequisite, and FAIL
    there reads as the surface refusing something it was never asked.
    """
    rows, _writes = _run_builtin_view_probe(rename=rename)

    assert rows["library.view.builtin-title-rename"]["outcome"] == "FAIL"
    lookup = rows["library.view.builtin-getbytitle-after-rename"]
    assert lookup["outcome"] == "NOT ESTABLISHED"
    assert lookup["state"] == "void"
    assert "did not read back under \"All Items\"" in lookup["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_field_set_of_the_right_length_is_not_the_field_that_was_asked_for() -> None:
    """removeallviewfields leaving one field behind, and an addviewfield that
    answers OK without applying anything, give a view holding exactly one
    field that is not the one requested.
    """
    rows, _writes = _run_builtin_view_probe(viewFields="survivor")

    fields = rows["library.view.builtin-viewfields-replace"]
    assert fields["outcome"] == "FAIL"
    assert '["DocIcon"], not the requested ["FileLeafRef"]' in fields["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_view_that_stops_being_the_default_when_hidden_answers_another_question() -> None:
    """The question is whether the built-in view can be hidden WHILE it holds
    DefaultView. A MERGE that hides it and moves the default elsewhere is the
    next row's experiment, not this one's.
    """
    rows, _writes = _run_builtin_view_probe(hideMovesDefault=True)

    hidden = rows["library.view.builtin-hidden-while-default"]
    assert hidden["outcome"] == "NOT ESTABLISHED"
    assert "DefaultView moved off it" in hidden["evidence"]
    # The row below asks about a view that is not the default, and still does.
    assert rows["library.view.builtin-hidden-once-not-default"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("restore", ["ignored", "refused"])
def test_a_hidden_flag_that_was_never_cleared_voids_the_second_hidden_row(
    restore: str,
) -> None:
    """The second hidden measurement needs a visible view to start from. Left
    hidden by the row above, its MERGE can do nothing and still read back
    true, which reports that hiding works once the default has moved.
    """
    rows, _writes = _run_builtin_view_probe(restore=restore)

    second = rows["library.view.builtin-hidden-once-not-default"]
    assert second["outcome"] == "NOT ESTABLISHED"
    assert second["state"] == "void"
    assert "Hidden did not read back false" in second["evidence"]
    # Only the row that depends on the restore. The delete is unaffected.
    assert rows["library.view.builtin-delete-once-not-default"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_verification_read_that_merely_failed_is_not_a_deleted_view() -> None:
    """Absence is what proves a delete. A 500 on the read afterwards says
    nothing, and reading it as the view being gone reports a deletion and a
    freed URL that nobody observed.
    """
    rows, _writes = _run_builtin_view_probe(missingViewRead="transient")

    deleted = rows["library.view.builtin-delete-once-not-default"]
    assert deleted["outcome"] == "NOT ESTABLISHED"
    assert "neither read back nor read as absent (HTTP 500)" in deleted["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_freed_url_is_not_reported_from_a_view_collection_that_never_read() -> None:
    """The row's evidence says AllItems.aspx is free. That is a reading of the
    view collection, so a collection that did not read back cannot supply it.
    """
    rows, _writes = _run_builtin_view_probe(viewsAfterDelete="unreadable")

    deleted = rows["library.view.builtin-delete-once-not-default"]
    assert deleted["outcome"] == "NOT ESTABLISHED"
    assert "whether AllItems.aspx is free was not observed" in deleted["evidence"]


# --------------------------------------------------------------------------
# library-header-token-probe.js: the fixture the rendered header is read
# against, and what happens when a piece of it was never established.
# --------------------------------------------------------------------------
HEADER_TOKEN_PROBE = MANUAL / "library-header-token-probe.js"

#: The two scratch containers this probe owns. Both are its fixture: the
#: lookup target holds the row the lookup points at, so one left behind is a
#: previous run's fixture answering this run's question.
_HEADER_LIB = "dbmlsp Probe Header Tokens"
_HEADER_TARGET = "dbmlsp Probe Header Lookup Target"
_HEADER_FILE = "dbmlsp-header-probe.txt"

#: The three rows only a person can answer, off the rendered form.
_HEADER_MANUAL_ROWS = (
    "library.form.header-token-battery-renders",
    "library.form.header-typed-column-battery-renders",
    "library.form.header-expression-battery-renders",
)

#: A SharePoint that serves a library the way one behaves when this probe is
#: re-run: `/items` in creation order rather than the order the probe wants,
#: a Folder content type ahead of the Document one, and a MERGE that answers
#: 2xx whether or not it kept the value. What the CONFIG varies is each thing
#: a live run could leave unestablished under a green transcript.
_HEADER_TOKEN_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const LIB = 'dbmlsp Probe Header Tokens';
    const TARGET = 'dbmlsp Probe Header Lookup Target';

    // What this site holds, keyed by title, plus the two ledgers the tests
    // read: which lists were recycled, and which items were written to.
    const lists = new Map();
    const recycled = [];
    const merged = [];
    let nextListId = 1;
    let nextItemId = 1;

    const makeList = (title, template) => {
      const held = {
        Id: `list-${nextListId}`, Title: title, BaseTemplate: template,
        ServerRelativeUrl: `/sites/test/${nextListId}`,
        fields: new Map(), items: [], formatter: null,
      };
      nextListId += 1;
      lists.set(title, held);
      return held;
    };

    // What an earlier run left behind, built before the probe starts so the
    // run has to deal with it rather than being handed a clean site.
    if (CONFIG.existingLibrary) {
      const held = makeList(LIB, 101);
      for (const name of CONFIG.leftoverItems) {
        held.items.push({ Id: nextItemId, FileLeafRef: name });
        nextItemId += 1;
      }
    }
    if (CONFIG.existingTarget) {
      const held = makeList(TARGET, 100);
      for (const row of CONFIG.targetRows) {
        held.items.push({ Id: row.Id, Title: row.Title });
        nextItemId = Math.max(nextItemId, row.Id + 1);
      }
    }

    // A library carries a Folder content type as well as a Document one, and
    // the Folder is served first here: the probe's own rule for picking the
    // document type is then doing work rather than reading the only entry.
    const contentTypesOf = (held) => (held.BaseTemplate === 101
      ? [{ Id: { StringValue: '0x0120001A' }, Name: 'Folder' },
         { Id: { StringValue: '0x0101002B' }, Name: 'Document' }]
      : [{ Id: { StringValue: '0x0100003C' }, Name: 'Item' }]);

    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FIELD = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const UPLOAD = /GetFolderByServerRelativeUrl\\('([^']+)'\\)\\/Files\\/add\\(url='([^']+)'/;
    const FILE_ITEM = /GetFileByServerRelativeUrl\\('([^']+)'\\)\\/ListItemAllFields/;
    const XML_NAME = /Name="([^"]+)"/;

    const selected = (u) => {
      const asked = /\\$select=([^&]+)/.exec(u);
      return asked ? decodeURIComponent(asked[1]).split(',') : [];
    };

    // What a read of one item answers. A column the MERGE discarded reads
    // back null, which is what SharePoint serves for an empty column and
    // what the form would then render as a blank.
    const itemView = (item, names) => {
      if (!names.length) return { ...item };
      const view = {};
      for (const name of names) {
        const held = item[name];
        view[name] = held === undefined ? null
          : (name === 'dbmlspDate' && CONFIG.dateReadBack ? CONFIG.dateReadBack : held);
      }
      return view;
    };

    // What the content type answers when its formatter is read back.
    const storedFormatter = (held) => {
      if (CONFIG.storage === 'changed') {
        // A server that kept the header and dropped a style property it did
        // not recognise. Accepted, readable, and not the battery submitted.
        return String(held.formatter).split(',"width":"100%"').join('');
      }
      return held.formatter;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url).split('/_api/')[1] || '';
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? null : String(opts.body);
      const sent = () => JSON.parse(raw || '{}');

      if (u.includes('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u.startsWith('web/currentuser')) return jsonResponse(200, { Id: 11 });
      if (u === 'web/lists' && method === 'POST') {
        const made = sent();
        const held = makeList(made.Title, made.BaseTemplate);
        return jsonResponse(201, { Id: held.Id, Title: held.Title });
      }

      const upload = UPLOAD.exec(u);
      if (upload) {
        const held = [...lists.values()].find(
          (one) => one.ServerRelativeUrl === upload[1]);
        if (!held) return jsonResponse(404, { error: 'no such folder' });
        const already = held.items.find((item) => item.FileLeafRef === upload[2]);
        if (!already) {
          held.items.push({ Id: nextItemId, FileLeafRef: upload[2] });
          nextItemId += 1;
        }
        return jsonResponse(200, { Name: upload[2] });
      }
      const fileItem = FILE_ITEM.exec(u);
      if (fileItem) {
        const leaf = fileItem[1].split('/').pop();
        const folder = fileItem[1].slice(0, -(leaf.length + 1));
        const held = [...lists.values()].find(
          (one) => one.ServerRelativeUrl === folder);
        const item = held && held.items.find((row) => row.FileLeafRef === leaf);
        if (!item) return jsonResponse(404, { error: 'no such file' });
        return jsonResponse(200, itemView(item, selected(u)));
      }

      const named = LIST.exec(u);
      if (!named) return jsonResponse(404, { error: `no such endpoint: ${u}` });
      const held = lists.get(named[1]);
      const rest = named[2];
      if (!held) return jsonResponse(404, { error: 'list not found' });

      if (rest.startsWith('/recycle')) {
        recycled.push(held.Title);
        lists.delete(held.Title);
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: held.ServerRelativeUrl });
      }
      if (rest.startsWith("/contenttypes('")) {
        const id = rest.split("'")[1];
        const ct = contentTypesOf(held).find((one) => one.Id.StringValue === id);
        if (!ct) return jsonResponse(404, { error: 'no such content type' });
        if (verb === 'MERGE') {
          if (CONFIG.storage === 'refused') {
            return jsonResponse(500, { error: 'the formatter was refused' });
          }
          held.formatter = sent().ClientFormCustomFormatter;
          return jsonResponse(204, {});
        }
        if (CONFIG.storage === 'unreadable') {
          return jsonResponse(500, { error: 'the content type did not read back' });
        }
        return jsonResponse(200, { ClientFormCustomFormatter: storedFormatter(held) });
      }
      if (rest.startsWith('/contenttypes')) {
        return jsonResponse(200, { value: contentTypesOf(held) });
      }
      if (rest.startsWith('/fields/createfieldasxml')) {
        const xml = sent().parameters.SchemaXml;
        held.fields.set(XML_NAME.exec(xml)[1], { readOnly: true });
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/fields/addfield')) {
        const made = sent().parameters;
        held.fields.set(made.Title, { lookup: made.LookupListId });
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/fields/getbyinternalnameortitle')) {
        const name = FIELD.exec(rest)[1];
        return held.fields.has(name)
          ? jsonResponse(200, { Id: `field-${name}` })
          : jsonResponse(404, { error: 'field not found' });
      }
      if (rest.startsWith('/fields') && method === 'POST') {
        const made = sent();
        held.fields.set(made.Title, { kind: made.FieldTypeKind });
        return jsonResponse(201, { Id: `field-${made.Title}` });
      }

      const one = ITEM.exec(rest);
      if (one) {
        const item = held.items.find((row) => row.Id === Number(one[1]));
        if (!item) return jsonResponse(404, { error: 'item not found' });
        if (verb === 'DELETE') {
          held.items = held.items.filter((row) => row.Id !== item.Id);
          return jsonResponse(200, {});
        }
        if (verb === 'MERGE') {
          merged.push(item.Id);
          for (const [name, value] of Object.entries(sent())) {
            if (name === '__metadata') continue;
            // Accepted and discarded, which is what a 2xx cannot tell you.
            if (CONFIG.dropOnMerge.includes(name)) continue;
            item[name] = value;
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, itemView(item, selected(rest)));
      }
      if (rest.startsWith('/items')) {
        if (method === 'POST') {
          const made = { Id: nextItemId, ...sent() };
          nextItemId += 1;
          held.items.push(made);
          return jsonResponse(201, { Id: made.Id });
        }
        return jsonResponse(200, { value: held.items.map((item) => ({ ...item })) });
      }
      return jsonResponse(200, {
        Id: held.Id, Title: held.Title,
        ListItemEntityTypeFullName: 'SP.Data.ProbeLibItem',
      });
    };

    // The site as the run left it, so a test can ask what was written to
    // rather than only what the probe said about it.
    globalThis.__dump = () => ({
      recycled,
      merged,
      lists: [...lists.values()].map((held) => ({
        Title: held.Title, items: held.items.map((item) => ({ ...item })),
      })),
    });
""")


def _header_token_probe_js(cleanup: bool = False) -> str:
    """The rendered header probe with its gates open and its table exposed.

    ``cleanup`` opens the destructive flag an operator sets for a clean
    fixture, which is the only state in which the pre-run reset runs at all.

    The dump goes inside report() rather than before one call of it: this
    probe returns report() from seven places, and splicing at one of them
    would leave an aborted run invisible to these tests.
    """
    js = HEADER_TOKEN_PROBE.read_text(encoding="utf-8")
    gates = ["CONFIRMED", "ALLOW_WRITES"]
    if cleanup:
        gates.append("CLEANUP")
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n"
        "    console.log('__ROWS__' + JSON.stringify(RESULTS));\n"
        "    console.log('__SITE__' + JSON.stringify(__dump()));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _header_token_output(cleanup: bool = False, **config: Any) -> str:
    settings: dict[str, Any] = {
        "existingLibrary": False,
        "existingTarget": False,
        "leftoverItems": [],
        "targetRows": [],
        "dropOnMerge": [],
        "dateReadBack": None,
        "storage": "verbatim",
        **config,
    }
    return _run(
        _HEADER_TOKEN_HARNESS.replace("__CONFIG__", json.dumps(settings))
        + "\n"
        + _header_token_probe_js(cleanup=cleanup)
    )


def _marked(output: str, marker: str) -> Any:
    line = next((ln for ln in output.splitlines() if ln.startswith(marker)), None)
    assert line is not None, f"the probe printed no {marker} line:\n{output[-3000:]}"
    return json.loads(line.removeprefix(marker))


def _run_header_token_probe(
    cleanup: bool = False, **config: Any,
) -> tuple[dict[str, dict[str, str]], dict[str, Any], str]:
    """Run the header probe and return its rows, the site it left, and stdout."""
    output = _header_token_output(cleanup=cleanup, **config)
    rows = {row["id"]: row for row in _marked(output, "__ROWS__")}
    return rows, _marked(output, "__SITE__"), output


def _library_items(site: dict[str, Any]) -> list[dict[str, Any]]:
    held = next(one for one in site["lists"] if one["Title"] == _HEADER_LIB)
    items: list[dict[str, Any]] = held["items"]
    return items


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_header_run_that_builds_its_whole_fixture_asks_for_the_look() -> None:
    """The control for every test below.

    Without it a probe that voided everything would satisfy all of them, and
    this section would be measuring a probe that had stopped measuring.
    """
    rows, site, output = _run_header_token_probe()

    assert rows["library.doc-lib.fixture-library-created"]["outcome"] == "PASS"
    assert rows["library.form.header-token-battery-stored"]["outcome"] == "PASS"
    for row_id in _HEADER_MANUAL_ROWS:
        assert rows[row_id]["outcome"] == "MANUAL", row_id
        assert rows[row_id]["state"] == "awaiting-capture", row_id
    assert not [row for row in rows.values() if row["state"] in {"open", "void"}]
    # The typed values are on the uploaded file, which is the item the
    # operator is about to open.
    file_item = next(
        item for item in _library_items(site)
        if item["FileLeafRef"] == _HEADER_FILE
    )
    assert site["merged"] == [file_item["Id"]]
    assert file_item["dbmlspChoice"] == "Q3"
    assert "============ EYES-ON ============" in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_cleanup_resets_the_lookup_target_as_well_as_the_library() -> None:
    """CLEANUP promises a clean fixture, and the lookup target is half of it.

    A run that recycles only the library reuses whatever row an earlier run
    left in the target, so the lookup the header reads points at fixture
    nobody in this run created. The operator is told to delete both as well,
    since a manual tidy-up that names one leaves the other behind for the
    next run to find.
    """
    rows, site, output = _run_header_token_probe(
        cleanup=True,
        existingLibrary=True,
        existingTarget=True,
        targetRows=[{"Id": 91, "Title": "Privacy and health records"}],
    )

    assert site["recycled"] == [_HEADER_LIB, _HEADER_TARGET]
    # The row the lookup points at is one THIS run created, not the one the
    # previous run left under the same title.
    file_item = next(
        item for item in _library_items(site)
        if item["FileLeafRef"] == _HEADER_FILE
    )
    assert file_item["dbmlspLookupId"] != 91
    assert rows["library.doc-lib.fixture-library-created"]["outcome"] == "PASS"
    assert (
        f"When finished, delete '{_HEADER_LIB}', then '{_HEADER_TARGET}'." in output
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_typed_values_land_on_the_uploaded_file_and_not_a_row_it_found() -> None:
    """`/items?$top=5` is unordered, and a reused library holds a row per
    folder as well as per file.

    Writing to whatever came back first modifies content this probe does not
    own, and leaves the file the operator is asked to open carrying none of
    the values whose blanks they are about to report as unresolved tokens.
    """
    rows, site, _ = _run_header_token_probe(
        existingLibrary=True, leftoverItems=["an-earlier-file.txt"],
    )

    items = _library_items(site)
    stale = next(item for item in items if item["FileLeafRef"] == "an-earlier-file.txt")
    file_item = next(item for item in items if item["FileLeafRef"] == _HEADER_FILE)
    assert site["merged"] == [file_item["Id"]]
    assert stale["Id"] < file_item["Id"], "the leftover must be served first"
    assert "dbmlspChoice" not in stale
    assert file_item["dbmlspChoice"] == "Q3"
    assert rows["library.form.header-typed-column-battery-renders"]["outcome"] == "MANUAL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_value_the_merge_accepted_and_dropped_is_reported_as_an_incomplete_fixture() -> None:
    """A 2xx says the request was taken, not that the value is on the item.

    A column that reads back empty renders an empty line in the header, which
    is indistinguishable on the page from a token the header cannot resolve.
    That is the one confusion this probe exists to prevent, so the two rows
    resting on those values say the fixture is incomplete and name the
    column.
    """
    rows, site, _ = _run_header_token_probe(dropOnMerge=["dbmlspChoice"])

    file_item = next(
        item for item in _library_items(site)
        if item["FileLeafRef"] == _HEADER_FILE
    )
    assert "dbmlspChoice" not in file_item
    for row_id in (
        "library.form.header-typed-column-battery-renders",
        "library.form.header-expression-battery-renders",
    ):
        assert rows[row_id]["outcome"] == "MANUAL (fixture incomplete)", row_id
        assert "dbmlspChoice" in rows[row_id]["evidence"], row_id
        assert '"Q3"' in rows[row_id]["evidence"], row_id


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_read_back_in_another_spelling_is_not_reported_as_a_lost_write() -> None:
    """The readback must not kill the experiment the moment it works.

    SharePoint answers a DateTime in its own ISO spelling, so the value is
    compared as an instant. A string compare would report a fixture that did
    not build on every run that built one.
    """
    rows, _, _ = _run_header_token_probe(dateReadBack="2026-10-13T00:00:00.000Z")

    for row_id in _HEADER_MANUAL_ROWS:
        assert rows[row_id]["outcome"] == "MANUAL", row_id


@pytest.mark.parametrize(
    ("storage", "outcome"),
    [("changed", "CHANGED"), ("unreadable", "NOT ESTABLISHED"), ("refused", "REFUSED")],
)
@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_header_that_is_not_the_battery_voids_every_row_a_person_answers(
    storage: str, outcome: str,
) -> None:
    """Every manual row is an observation of THIS battery on a form.

    A formatter that was refused, never read back, or read back changed
    leaves the form carrying something else, so asking somebody to interpret
    the lines on it collects evidence for a different experiment. The run
    stops instead, and says why on all three rows.
    """
    rows, _, output = _run_header_token_probe(storage=storage)

    assert rows["library.form.header-token-battery-stored"]["outcome"] == outcome
    for row_id in _HEADER_MANUAL_ROWS:
        assert rows[row_id]["state"] == "void", row_id
    assert "============ EYES-ON ============" not in output


# --------------------------------------------------------------------------
# item-text-roundtrip-probe.js: the column shapes every encoding row is
# attributed to, and what happens when the list only carries their names.
# --------------------------------------------------------------------------
TEXT_PROBE = MANUAL / "item-text-roundtrip-probe.js"

#: The seven rows the fixture gates. Each one reads an encoding off a column
#: type, so a fixture that was never established has to void all of them
#: rather than let a reading be attributed to a shape nobody confirmed.
_TEXT_MEASUREMENTS = (
    "text.item-value.single-line-roundtrip",
    "text.item-value.plain-note-roundtrip",
    "text.item-value.rich-note-roundtrip",
    "text.item-value.rich-note-colon",
    "text.item-value.control-plain-note-colon",
    "text.item-value.rich-note-decode-recovers",
    "text.item-value.rich-note-encoding-idempotent",
)

_TEXT_FIXTURE = "text.item-value.fixture-columns-created"

#: A list an earlier run left behind, with all three names present and the
#: right shapes under them.
_HEALTHY_FIELDS = [
    {"InternalName": "dbmlspLine", "FieldTypeKind": 2},
    {"InternalName": "dbmlspPlain", "FieldTypeKind": 3,
     "RichText": False, "NumberOfLines": 6},
    {"InternalName": "dbmlspRich", "FieldTypeKind": 3,
     "RichText": True, "NumberOfLines": 6},
]

# A SharePoint that holds columns as SHAPES rather than as names, because the
# defect this covers is a name accepted for a shape. What a column does to a
# value it stores is decided by the shape it actually holds, so a fixture the
# probe got wrong shows up in the measurement rather than being invisible.
_TEXT_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const fields = new Map(CONFIG.fields.map((f) => [f.InternalName, { ...f }]));
    const items = new Map();
    let nextId = 1;
    let listExists = CONFIG.listExists;

    // Per-list, and guessed wrong by the probe's first attempt, which is the
    // shape a live create has: the entity type name has to be read back.
    const ENTITY = 'SP.Data.DbmlspxProbexItemxTextListItem';

    const FIELD_RE = /getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM_RE = /items\\((\\d+)\\)/;
    const SELECT_RE = /\\$select=([^&]+)/;

    // What a rich text column did to a value on the live run of 2026-09-13: a
    // colon came back as a numeric character reference. Keyed off the shape
    // the column ACTUALLY holds, never off its name, so a plain column under
    // the rich name returns the bytes it was given.
    const store = (name, value) => {
      const held = fields.get(name);
      if (held && held.RichText === true) return String(value).replace(/:/g, '&#58;');
      return value;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body));

      if (u.includes('/contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u.endsWith('/web/lists') && method === 'POST') {
        listExists = true;
        return jsonResponse(201, { Title: sent.Title });
      }
      if (!listExists) return jsonResponse(404, { error: 'list not found' });

      const named = FIELD_RE.exec(u);
      if (named) {
        if (CONFIG.unreadableFields.includes(named[1])) {
          return jsonResponse(500, { error: 'the field read failed' });
        }
        const held = fields.get(named[1]);
        if (!held) return jsonResponse(404, { error: 'field not found' });
        return jsonResponse(200, { ...held });
      }

      if (u.endsWith('/fields') && method === 'POST') {
        const kept = {
          InternalName: sent.Title,
          FieldTypeKind: sent.FieldTypeKind,
          NumberOfLines: sent.NumberOfLines,
        };
        if (sent.RichText !== undefined) kept.RichText = sent.RichText;
        // A tenant that takes a property and does not keep it. A null drops
        // the property from the field entirely, which is the other way a
        // shape can be unavailable to the run that depends on it.
        for (const [prop, value] of Object.entries(CONFIG.dropsOnCreate[sent.Title] || {})) {
          if (value === null) delete kept[prop]; else kept[prop] = value;
        }
        fields.set(sent.Title, kept);
        return jsonResponse(201, { d: { InternalName: sent.Title } });
      }

      if (u.includes('/items')) {
        if (method === 'POST') {
          if (sent.__metadata.type !== ENTITY) {
            return jsonResponse(500, { error: 'the entity type name is wrong' });
          }
          const id = nextId;
          nextId += 1;
          const stored = {};
          for (const [name, value] of Object.entries(sent)) {
            if (name === '__metadata') continue;
            stored[name] = store(name, value);
          }
          items.set(id, stored);
          return jsonResponse(201, { d: { Id: id } });
        }
        const held = items.get(Number(ITEM_RE.exec(u)[1]));
        if (!held) return jsonResponse(404, { error: 'item not found' });
        const out = {};
        for (const name of SELECT_RE.exec(u)[1].split(',')) out[name] = held[name];
        return jsonResponse(200, out);
      }

      if (u.includes('ListItemEntityTypeFullName')) {
        return jsonResponse(200, { ListItemEntityTypeFullName: ENTITY });
      }
      return jsonResponse(200, { Title: 'dbmlsp Probe Item Text' });
    };
""")


def _text_probe_js() -> str:
    """The rendered probe with its gates open and its result table exposed.

    CLEANUP is left false on purpose. The review this covers is about the run
    that reuses whatever an earlier run left, and turning CLEANUP on would
    hide exactly that case.
    """
    js = TEXT_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_text_probe(**changes: Any) -> dict[str, dict[str, str]]:
    """Run the probe against an empty site plus `changes`, id -> whole row.

    The whole row, because what a refused fixture has to leave behind is
    EVIDENCE naming the shape it could not establish. An outcome of FAIL on
    its own would pass for a list that failed to build at all.
    """
    config: dict[str, Any] = {
        "listExists": False,
        "fields": [],
        "dropsOnCreate": {},
        "unreadableFields": [],
    }
    config.update(changes)
    script = (
        _TEXT_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _text_probe_js()
    )
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_fixture_read_back_with_the_declared_shapes_measures_all_three() -> None:
    """The control for the four tests below, and the shape of a healthy run.

    Without it, a shape check that refused every fixture would pass all of
    them while retiring the probe.
    """
    rows = _run_text_probe()

    assert rows[_TEXT_FIXTURE]["outcome"] == "PASS"
    evidence = rows[_TEXT_FIXTURE]["evidence"]
    assert "dbmlspLine (FieldTypeKind 2)" in evidence
    assert "dbmlspPlain (FieldTypeKind 3, RichText false)" in evidence
    assert "dbmlspRich (FieldTypeKind 3, RichText true)" in evidence
    assert "read back from the field itself" in evidence

    assert rows["text.item-value.single-line-roundtrip"]["outcome"] == "IDENTICAL"
    assert rows["text.item-value.plain-note-roundtrip"]["outcome"] == "IDENTICAL"
    assert rows["text.item-value.rich-note-roundtrip"]["outcome"] == "CHANGED"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_plain_column_left_under_the_rich_name_is_not_measured_as_rich() -> None:
    """CLEANUP off and a scratch list an earlier run left: `dbmlspRich` is
    present, and it is a plain Note.

    Every column here returns the bytes it was given, so the run reads as a
    tenant that encodes nothing, and the rich text finding this probe exists
    to record is contradicted by a column that was never rich text.
    """
    seeded = [dict(field) for field in _HEALTHY_FIELDS]
    seeded[2]["RichText"] = False
    rows = _run_text_probe(listExists=True, fields=seeded)

    assert rows[_TEXT_FIXTURE]["outcome"] == "FAIL", (
        "a Note with RichText false was accepted under the rich name, so "
        "every encoding row below it is attributed to a shape the run never "
        "established."
    )
    assert "dbmlspRich: RichText is false, not true" in rows[_TEXT_FIXTURE]["evidence"]
    voided = [row_id for row_id, row in rows.items() if row["state"] == "void"]
    assert sorted(voided) == sorted(_TEXT_MEASUREMENTS)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_rich_text_flag_the_tenant_dropped_on_create_fails_the_fixture() -> None:
    """A create that answers 201 is the server's word that it took the body,
    not a reading of the field it made.

    A dropped RichText is the same corruption as the reused column above, and
    it reaches a run that started from an empty site.
    """
    rows = _run_text_probe(dropsOnCreate={"dbmlspRich": {"RichText": False}})

    assert rows[_TEXT_FIXTURE]["outcome"] == "FAIL"
    assert "dbmlspRich: RichText is false, not true" in rows[_TEXT_FIXTURE]["evidence"]
    voided = [row_id for row_id, row in rows.items() if row["state"] == "void"]
    assert sorted(voided) == sorted(_TEXT_MEASUREMENTS)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_field_that_does_not_carry_rich_text_at_all_fails_closed() -> None:
    """A property missing from the payload is not a match.

    Read as one, a tenant that does not report RichText would certify every
    rich text row on a field whose shape nothing here can see.
    """
    rows = _run_text_probe(dropsOnCreate={"dbmlspRich": {"RichText": None}})

    assert rows[_TEXT_FIXTURE]["outcome"] == "FAIL"
    assert "dbmlspRich: RichText is absent from the field" in rows[_TEXT_FIXTURE]["evidence"]
    voided = [row_id for row_id, row in rows.items() if row["state"] == "void"]
    assert sorted(voided) == sorted(_TEXT_MEASUREMENTS)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_shape_that_never_reads_back_voids_rather_than_measuring() -> None:
    """The create is accepted and the field will not read. Nothing is known
    about the column, so nothing may be attributed to it."""
    rows = _run_text_probe(unreadableFields=["dbmlspPlain"])

    assert rows[_TEXT_FIXTURE]["outcome"] == "FAIL"
    assert (
        "dbmlspPlain: its shape did not read back: HTTP 500"
        in rows[_TEXT_FIXTURE]["evidence"]
    )
    voided = [row_id for row_id, row in rows.items() if row["state"] == "void"]
    assert sorted(voided) == sorted(_TEXT_MEASUREMENTS)


# --------------------------------------------------------------------------
# list-identity-cache-probe.js: what the probe is allowed to delete, and
# which rows survive a control that did not hold.
# --------------------------------------------------------------------------
IDENTITY_PROBE = MANUAL / "list-identity-cache-probe.js"

#: The two scratch titles, and the URL fragments that pick one read out of the
#: run. Spelled from the probe's own constants, because a title that drifts
#: would leave every fault below matching nothing and every test still green.
_IDENTITY_LIST = "dbmlsp Probe Cache Identity"
_IDENTITY_LIB = "dbmlsp Probe Cache Identity Library"
#: The closing quote matters: the library title has the list title as a prefix.
_LIST_PATH = f"getbytitle('{_IDENTITY_LIST}')"
_LIB_PATH = f"getbytitle('{_IDENTITY_LIB}')"
_OWNERSHIP = "dbml-sharepoint list identity cache probe. Safe to delete."
#: The ownership question this probe asks before it creates anything.
_EXISTS_READ = "$select=Id,Description&dbmlsp="
#: The filter-editor spelling. Excluded from the two reads that also start
#: `?$select=Id`: the ownership question above and the cache-busted control.
_PLAIN_READ = "?$select=Id"
_PLAIN_NOT = ["Description", "dbmlsp="]
#: The ownership survey's spelling, picked out by a column only it selects.
_SHAPE_READ = "ValidationMessage"
_BUSTED_READ = "$select=Id&dbmlsp="

# A SharePoint that holds lists by title AND a browser cache that holds
# answers by URL, because the second is what this probe measures: a by-title
# read served from an entry filled before a delete-and-recreate answers with
# the list that no longer exists.
#
# Every request is printed as a __CALL__ line. What the probe must NOT send
# (a hard DELETE against a list it did not create) cannot be read off the
# result table, only off the traffic.
_IDENTITY_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const lists = new Map(CONFIG.seeded.map((row) => [row.Title, { ...row }]));
    let nextId = 1;

    // url -> the answer a later read of that same url can be served. A
    // directive in `bypassing` skips it; no-store never fills it.
    const entries = new Map();

    // Per-title DELETE counters, so a test can let the run's own recreate
    // through and refuse only the delete that tears the fixture down.
    const deletes = new Map();
    const nth = (title) => {
      const seen = (deletes.get(title) || 0) + 1;
      deletes.set(title, seen);
      return seen;
    };
    const ruleFor = (rules, title) => rules.find((rule) => rule.title === title) || null;

    const TITLE = /getbytitle\\('([^']*)'\\)/;

    const respond = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: {
        get: (name) => (CONFIG.responseHeaders[name] === undefined
          ? null : CONFIG.responseHeaders[name]),
      },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // A read fault is armed by what the URL SAYS, never by a call count
    // alone: a count pins the test to today's request order, and `skip`
    // counts only the reads that already match the shape under test.
    const faults = CONFIG.readFaults.map((fault) => ({ ...fault, seen: 0 }));
    const faultFor = (u) => {
      const rule = faults.find((fault) => fault.contains.every((s) => u.includes(s))
        && !fault.notContains.some((s) => u.includes(s)));
      if (!rule) return null;
      rule.seen += 1;
      if (rule.seen <= rule.skip) return null;
      if (rule.seen > rule.skip + rule.times) return null;
      return rule;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      console.log(`__CALL__${verb} ${u}`);

      if (u.includes('/contextinfo')) {
        return respond(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u.includes('/_api/web/lists?')) {
        return respond(200, { d: { results: [...lists.values()].map(
          (row) => ({ Id: row.Id, Title: row.Title })) } });
      }
      if (u.endsWith('/_api/web/lists') && method === 'POST') {
        const sent = JSON.parse(String(opts.body));
        if (lists.has(sent.Title)) {
          return respond(400, { error: 'a list of that title already exists' });
        }
        nextId += 1;
        const made = {
          Id: `list-${nextId - 1}`, Title: sent.Title,
          Description: sent.Description, BaseTemplate: sent.BaseTemplate,
        };
        lists.set(sent.Title, made);
        return respond(201, { Id: made.Id });
      }

      const named = TITLE.exec(u);
      if (!named) return respond(404, { error: 'no such endpoint' });
      const title = named[1];

      if (u.endsWith('/recycle')) {
        if (CONFIG.refuseRecycle.includes(title)) {
          return respond(500, { error: 'the recycle was refused' });
        }
        lists.delete(title);
        return respond(200, { value: 'recycle-bin-id' });
      }
      if (u.includes('/items')) return respond(200, { value: [] });

      if (verb === 'DELETE') {
        const seen = nth(title);
        const refused = ruleFor(CONFIG.refuseDelete, title);
        if (refused && seen > refused.skip) {
          return respond(500, { error: 'the delete was refused' });
        }
        const pretend = ruleFor(CONFIG.pretendDeleted, title);
        if (pretend && seen > pretend.skip) return respond(200, {});
        if (!lists.has(title)) return respond(404, { error: 'no such list' });
        lists.delete(title);
        return respond(200, {});
      }

      const directive = opts.cache
        || (((opts.headers || {})['Cache-Control'] === 'no-cache')
          ? 'no-cache-header' : 'default');
      const bypass = !CONFIG.cacheStale || CONFIG.bypassing.includes(directive);
      if (!bypass && entries.has(u)) return entries.get(u)();

      const fault = faultFor(u);
      // A read that never answered leaves no entry behind either.
      if (fault && fault.status) {
        return respond(fault.status, { error: 'the read did not answer' });
      }
      const held = lists.get(title);
      const answer = held === undefined
        ? () => respond(404, { error: { message: `List '${title}' does not exist` } })
        : () => respond(200, { d: { ...held, Id: (fault && fault.id) || held.Id } });
      if (directive !== 'no-store') entries.set(u, answer);
      return answer();
    };
""")

#: A run where nothing has gone wrong: both scratch titles are free, the
#: browser holds a stale entry per URL, and only `no-store` and `reload`
#: defeat it. Each test changes one thing.
_IDENTITY_HEALTHY: dict[str, Any] = {
    "seeded": [],
    "cacheStale": True,
    # The no-cache REQUEST header is left cacheable, which is what the probe's
    # own prose expects of it, so `remedy-reload` and `plain-read-after-reload`
    # still have an entry to defeat and to repair.
    "bypassing": ["no-store", "reload"],
    "responseHeaders": {"Cache-Control": "private, max-age=0", "ETag": '"1"'},
    "readFaults": [],
    "refuseDelete": [],
    "pretendDeleted": [],
    "refuseRecycle": [],
}


def _fault(
    contains: list[str],
    *,
    not_contains: list[str] | None = None,
    skip: int = 0,
    times: int = 1,
    status: int | None = None,
    answers: str | None = None,
) -> dict[str, Any]:
    """One read fault: the shape it matches, how many to let past, what it does."""
    return {
        "contains": contains,
        "notContains": not_contains or [],
        "skip": skip,
        "times": times,
        "status": status,
        "id": answers,
    }


def _identity_probe_js(cleanup: bool = False) -> str:
    """The rendered probe with its gates opened and its result table exposed.

    The dump is spliced into report() rather than beside a call to it: every
    exit now reports through finish(), so there is no single call site.
    """
    js = IDENTITY_PROBE.read_text(encoding="utf-8")
    gates = ["CONFIRMED", "ALLOW_WRITES"] + (["CLEANUP"] if cleanup else [])
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n"
        "    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _identity_run(cleanup: bool = False, **changes: Any) -> tuple[dict[str, Any], str]:
    """Run the probe against `_IDENTITY_HEALTHY` plus `changes`.

    Returns the whole recorded row per id, and the raw output. Both, because
    the teardown reports through the log rather than through a row, and what
    the probe refuses to DELETE is only visible in the traffic.
    """
    config = json.loads(json.dumps(_IDENTITY_HEALTHY))
    config.update(changes)
    script = (
        _IDENTITY_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _identity_probe_js(cleanup)
    )
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    rows = {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}
    return rows, output


def _calls(output: str) -> list[str]:
    """Every request the probe sent, as "<verb> <url>"."""
    return [
        ln.removeprefix("__CALL__")
        for ln in output.splitlines()
        if ln.startswith("__CALL__")
    ]


def _deletes(output: str, path: str) -> list[str]:
    """The hard DELETEs sent against one by-title path."""
    return [call for call in _calls(output) if call.startswith("DELETE ") and path in call]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_stale_by_title_entry_is_measured_and_the_remedies_separated() -> None:
    """The healthy run, and the control that gives every test below meaning.

    Without it a probe that voided everything would pass them all: each one
    asserts that a row is NOT settled, and a row that never settles under any
    conditions measures nothing at all.
    """
    rows, output = _identity_run()

    assert rows["transport.cache.fixture-list-created"]["outcome"] == "PASS"
    assert rows["transport.cache.control-repeat-read-unchanged"]["outcome"] == "PASS"
    assert rows["transport.cache.control-enumeration-after-recreate"]["outcome"] == "NEW"
    assert rows["transport.cache.id-select-after-recreate"]["outcome"] == "STALE"
    assert rows["transport.cache.shape-select-after-recreate"]["outcome"] == "STALE"
    assert rows["transport.cache.control-busted-after-recreate"]["outcome"] == "FRESH"
    assert rows["transport.cache.remedy-no-store"]["outcome"] == "FRESH"
    assert rows["transport.cache.remedy-no-cache-header"]["outcome"] == "STALE"
    assert rows["transport.cache.remedy-reload"]["outcome"] == "FRESH"
    assert rows["transport.cache.plain-read-after-reload"]["outcome"] == "FRESH"
    assert rows["transport.cache.id-select-after-recreate-library"]["outcome"] == "STALE"
    assert not [row for row in rows.values() if row["state"] != "settled"]
    assert "deleted and confirmed absent" in output


# --- P1: a scratch title this run did not create is not deleted ------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_foreign_list_under_the_scratch_title_is_never_deleted() -> None:
    """The destructive branch has to fail closed, and a title is not ownership.

    An unconditional hard DELETE at the top of the run destroys whatever the
    site keeps under that title, permanently and before the probe has created
    anything at all. Nothing downstream can see that it happened: the run then
    proceeds exactly as it would on an empty site.
    """
    rows, output = _identity_run(seeded=[{
        "Id": "someone-elses-1",
        "Title": _IDENTITY_LIST,
        "Description": "A list this site actually uses",
    }])

    fixture = rows["transport.cache.fixture-list-created"]
    assert fixture["outcome"] == "ABORTED"
    assert fixture["state"] == "open"
    assert "without this probe's" in fixture["evidence"]
    assert _deletes(output, _LIST_PATH) == []
    assert not [call for call in _calls(output) if call.endswith("/_api/web/lists")]
    assert all(row["state"] in {"open", "void"} for row in rows.values())


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_foreign_library_under_the_scratch_title_is_never_deleted() -> None:
    """The same unconditional delete was written twice, once for each title.

    The list half can be fixed on its own and leave the library half exactly
    as it was, so the library is asserted separately rather than assumed to
    follow.
    """
    rows, output = _identity_run(seeded=[{
        "Id": "someone-elses-2",
        "Title": _IDENTITY_LIB,
        "Description": "A library this site actually uses",
    }])

    library = rows["transport.cache.id-select-after-recreate-library"]
    assert library["outcome"] == "NOT ESTABLISHED"
    assert library["state"] == "void"
    assert "without this probe's" in library["evidence"]
    assert _deletes(output, _LIB_PATH) == []
    # The list half still answered, and its own scratch list was still removed.
    assert rows["transport.cache.id-select-after-recreate"]["outcome"] == "STALE"
    assert "deleted and confirmed absent" in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_leftover_from_this_probe_stops_a_run_that_has_not_opted_into_cleanup() -> None:
    """Even the probe's own leftover goes through the recoverable path.

    CLEANUP is the opt-in, and recycling is what makes it recoverable. A run
    that hard-deletes the leftover for itself takes that choice away from the
    operator and puts the object beyond the recycle bin.
    """
    rows, output = _identity_run(seeded=[{
        "Id": "leftover-1",
        "Title": _IDENTITY_LIST,
        "Description": _OWNERSHIP,
    }])

    fixture = rows["transport.cache.fixture-list-created"]
    assert fixture["outcome"] == "ABORTED"
    assert "CLEANUP = true" in fixture["evidence"]
    assert _deletes(output, _LIST_PATH) == []


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_leftover_is_recycled_before_the_first_hard_delete() -> None:
    """With CLEANUP on the run proceeds, and the leftover goes to the bin.

    The probe hard-deletes its own fixture mid-run, which is the experiment.
    What this pins is the order: nothing is hard-deleted until the probe has
    created the object it is deleting.
    """
    rows, output = _identity_run(cleanup=True, seeded=[{
        "Id": "leftover-1",
        "Title": _IDENTITY_LIST,
        "Description": _OWNERSHIP,
    }])

    assert rows["transport.cache.fixture-list-created"]["outcome"] == "PASS"
    calls = _calls(output)
    recycled = next(i for i, call in enumerate(calls) if call.endswith("/recycle"))
    created = next(i for i, call in enumerate(calls) if call.endswith("/_api/web/lists"))
    deleted = next(i for i, call in enumerate(calls) if call.startswith("DELETE "))
    assert recycled < created < deleted


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_title_whose_existence_cannot_be_read_is_treated_as_occupied() -> None:
    """A throttle is not an empty site, and the branch it gates is destructive.

    `readFailed` in the shared harness exists because a refusal comes back as
    a parsed JSON body, so "the response arrived" says nothing about whether
    the question was answered.
    """
    rows, output = _identity_run(readFaults=[
        _fault([_LIST_PATH, _EXISTS_READ], status=429),
    ])

    fixture = rows["transport.cache.fixture-list-created"]
    assert fixture["outcome"] == "ABORTED"
    assert "could not tell whether" in fixture["evidence"]
    assert "429" in fixture["evidence"]
    assert _deletes(output, _LIST_PATH) == []
    assert not [call for call in _calls(output) if call.endswith("/_api/web/lists")]


# --- The survey URL has to be primed before the recreate -------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_survey_url_that_was_never_primed_voids_only_its_own_row() -> None:
    """A URL's FIRST read cannot be answered from an entry, so it reads fresh.

    Recording that as FRESH is the failure this whole probe exists to catch in
    the deploy: a row that settles on a read which never asked the question.
    The `?$select=Id` row was primed and is unaffected, so the void is scoped
    to the one measurement that lost its control.
    """
    rows, _ = _identity_run(readFaults=[
        _fault([_LIST_PATH, _SHAPE_READ], status=500),
    ])

    shape = rows["transport.cache.shape-select-after-recreate"]
    assert shape["outcome"] == "NOT ESTABLISHED"
    assert shape["state"] == "void"
    assert "that URL's first" in shape["evidence"]
    assert rows["transport.cache.id-select-after-recreate"]["outcome"] == "STALE"
    assert rows["transport.cache.control-busted-after-recreate"]["outcome"] == "FRESH"


# --- A failed repeat-read control stops the run ----------------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_repeat_control_that_disagrees_stops_before_the_recreate() -> None:
    """The probe's own contract: a later disagreement is then unattributable.

    Two identical reads that already disagree with nothing written between
    them mean this run cannot tell a stale entry from whatever else is moving.
    Every row after it would still print a verdict, and `remedy-no-store` is
    the one a fix would be built on.
    """
    rows, output = _identity_run(
        cacheStale=False,
        readFaults=[_fault(
            [_LIST_PATH, _PLAIN_READ], not_contains=_PLAIN_NOT, skip=1,
            answers="list-somewhere-else",
        )],
    )

    repeat = rows["transport.cache.control-repeat-read-unchanged"]
    assert repeat["outcome"] == "FAIL"
    voided = [
        identity for identity, row in rows.items()
        if row["state"] == "void" and "disagreed" in row["evidence"]
    ]
    assert "transport.cache.remedy-no-store" in voided
    assert "transport.cache.id-select-after-recreate" in voided
    assert "transport.cache.id-select-after-recreate-library" in voided
    assert len(voided) == 9
    # It stopped rather than recreating, and still took its fixture away.
    assert len(_deletes(output, _LIST_PATH)) == 1
    assert "deleted and confirmed absent" in output


# --- A read that never answered is not a third identity --------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("identity", "fault"),
    [
        (
            "transport.cache.id-select-after-recreate",
            _fault([_LIST_PATH, _PLAIN_READ], not_contains=_PLAIN_NOT, skip=2, status=500),
        ),
        (
            "transport.cache.control-busted-after-recreate",
            _fault([_LIST_PATH, _BUSTED_READ], status=500),
        ),
        (
            "transport.cache.remedy-no-store",
            _fault([_LIST_PATH, _PLAIN_READ], not_contains=_PLAIN_NOT, skip=3, status=503),
        ),
        (
            "transport.cache.id-select-after-recreate-library",
            _fault([_LIB_PATH, _PLAIN_READ], not_contains=_PLAIN_NOT, skip=1, status=500),
        ),
    ],
)
def test_a_cache_probe_read_that_never_answered_voids_its_row(
    identity: str, fault: dict[str, Any],
) -> None:
    """UNEXPECTED settles, and says a third list answered. Nothing did.

    A transient 500 and a genuinely unrecognised Id are the same null here,
    and only one of them is a finding. `remedy-no-store` is in the list
    because a directive reported as not working is what would send the fix
    towards a unique parameter on every URL instead.
    """
    rows, _ = _identity_run(cacheStale=False, readFaults=[fault])

    row = rows[identity]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert row["state"] == "void"
    assert "did not answer" in row["evidence"]


# --- The teardown is confirmed, not announced ------------------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("how", ["refuseDelete", "pretendDeleted"])
def test_a_final_delete_that_left_the_container_behind_is_reported(how: str) -> None:
    """Cleanup policy "after" is a promise to the operator, so it is read back.

    Both shapes leave the same scratch list on the site: one where the DELETE
    is refused outright, and one where it answers 200 and changes nothing.
    Only a read-back separates either from a clean teardown.
    """
    # skip 1: the run's own mid-experiment recreate still goes through, so
    # what is under test is the teardown rather than the fixture.
    config: dict[str, Any] = {how: [{"title": _IDENTITY_LIST, "skip": 1}]}
    _, output = _identity_run(**config)

    assert "cleanup did not finish" in output
    assert _IDENTITY_LIST in output.split("cleanup did not finish", 1)[1]
    assert "deleted and confirmed absent" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_teardown_read_that_cannot_answer_is_not_read_as_gone() -> None:
    """The confirming read fails closed too, or it only moves the assumption."""
    _, output = _identity_run(readFaults=[
        _fault([_LIST_PATH, _EXISTS_READ], skip=1, status=429),
    ])

    assert "could not confirm" in output
    assert "deleted and confirmed absent" not in output


# --------------------------------------------------------------------------
# projected-lookup-probe.js: the cross-web arm. What the arm CONCLUDES is
# the product, and a create that answers 200 and then reads back pointing
# at this web is the failure class AGENTS.md names: it saves, it reads
# back, and it did nothing the caller asked for.
# --------------------------------------------------------------------------
CROSS_WEB_PROBE = MANUAL / "projected-lookup-probe.js"

#: The other web the arm looks for, and the list it would target. Opaque
#: values only: the probe prints GUIDs and never a site name, and this mock
#: holds it to that by giving it nothing else to print.
CROSS_WEB_OTHER_WEB_ID = "11111111-1111-1111-1111-111111111111"
CROSS_WEB_OTHER_WEB_URL = "https://example.sharepoint.com/sites/test/sub"
CROSS_WEB_OTHER_LIST_ID = "22222222-2222-2222-2222-222222222222"
CROSS_WEB_THIS_WEB_ID = "33333333-3333-3333-3333-333333333333"
#: The site collection both webs sit in by default, which is the topology a
#: subweb found through `web/webs` gives, and the one a distant pair would not.
CROSS_WEB_THIS_SITE_ID = "55555555-5555-5555-5555-555555555555"
CROSS_WEB_FAR_SITE_ID = "66666666-6666-6666-6666-666666666666"
#: The row in the other web's list that an accepted cross-web column is set to.
CROSS_WEB_OTHER_ITEM_ID = 41
#: The two Titles the comparison has to tell apart, and that the transcript may
#: not carry: a lookup id is list-local, so a column that quietly repointed at
#: this web stores 41 and expands the row of this web that happens to be 41.
CROSS_WEB_REMOTE_TITLE = "title-of-the-row-in-the-other-web"
CROSS_WEB_LOCAL_TITLE = "title-of-the-row-in-this-web"

_CROSS_WEB_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      location: { origin: 'https://example.sharepoint.com' },
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
        webServerRelativeUrl: '/sites/test',
        userLoginName: 'probe@example.com',
        userId: 11,
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // Fields SharePoint now holds, by internal name. Seeded empty so the
    // probe's own existence checks drive the creates, which is what a first
    // run against a clean site looks like.
    const fields = new Map();
    for (const name of CONFIG.preexistingFields) {
      fields.set(name, { InternalName: name, schema: '' });
    }
    const items = new Map();
    let nextItemId = 1;
    let primaryReads = 0;

    // The id the probe settles on: the highest the target list holds plus its
    // margin. Derived here so a test can answer for that one row.
    const ABSENT_ID = CONFIG.targetHighestId === null
      ? null : CONFIG.targetHighestId + 1000;

    // The leading space matters: `DisplayName="..."` ends in `Name="..."`, so
    // an unanchored pattern reads every field's display name as its internal
    // one and every existence check then misses.
    const NAME_IN_SCHEMA = / Name="([^"]+)"/;
    const LIST_IN_SCHEMA = / List="\\{?([^"}]+)\\}?"/;
    const WEBID_IN_SCHEMA = / WebId="\\{?([^"}]+)\\}?"/;
    const FIELD_RE = /getbyinternalnameortitle\\('([^']+)'\\)/;

    // The list a column actually points at, which is what its readback says
    // and otherwise what its schema asked for.
    const targetListOf = (name) => {
      const override = CONFIG.readback[name] || {};
      const fromSchema = LIST_IN_SCHEMA.exec((fields.get(name) || {}).schema || '');
      const raw = override.LookupList !== undefined
        ? override.LookupList : (fromSchema ? fromSchema[1] : '');
      return String(raw).replace(/[{}]/g, '').toLowerCase();
    };

    // A lookup id is list-local, so an expansion is a row of the list the
    // column points at: 'target' follows it, 'this-web' is the misdirected
    // column that resolves a row of this web carrying the same number, and
    // 'nothing' is the column whose properties persisted and resolve no row.
    const expandedRow = (name, storedId) => {
      if (CONFIG.expandResolvesAs === 'nothing') return null;
      const local = CONFIG.expandResolvesAs === 'this-web'
        || targetListOf(name) !== String(CONFIG.otherListId).toLowerCase();
      const rows = local ? CONFIG.localItems : CONFIG.otherItems;
      return rows.find((row) => row.Id === storedId) || null;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const body = opts.body === undefined ? null : String(opts.body);

      if (u.includes('/contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }

      // Everything the probe sends to the OTHER web goes through its own
      // absolute URL, so one prefix test separates the two sides.
      if (u.startsWith(CONFIG.otherWebUrl)) {
        // The other web's own identity, which an operator-supplied URL is
        // resolved through, and the site collection it sits in.
        if (/\\/_api\\/web\\?\\$select=Id$/.test(u)) {
          if (CONFIG.otherWebStatus !== 200) {
            return jsonResponse(CONFIG.otherWebStatus, { error: 'refused' });
          }
          return jsonResponse(200, { Id: CONFIG.otherWebId });
        }
        if (/\\/_api\\/site\\?\\$select=Id$/.test(u)) {
          if (CONFIG.otherSiteStatus !== 200) {
            return jsonResponse(CONFIG.otherSiteStatus, { error: 'refused' });
          }
          return jsonResponse(200, { Id: CONFIG.otherSiteId });
        }
        if (u.includes('web/lists?')) return jsonResponse(200, { value: CONFIG.otherLists });
        if (u.includes('/items')) {
          if (CONFIG.otherItemsStatus !== 200) {
            return jsonResponse(CONFIG.otherItemsStatus, { error: 'refused' });
          }
          return jsonResponse(200, { value: CONFIG.otherItems });
        }
        return jsonResponse(200, { value: [] });
      }

      if (/\\/_api\\/web\\?\\$select=Id$/.test(u)) {
        if (CONFIG.thisWebStatus !== 200) {
          return jsonResponse(CONFIG.thisWebStatus, { error: 'refused' });
        }
        return jsonResponse(200, { Id: CONFIG.thisWebId });
      }

      if (/\\/_api\\/site\\?\\$select=Id$/.test(u)) {
        if (CONFIG.thisSiteStatus !== 200) {
          return jsonResponse(CONFIG.thisSiteStatus, { error: 'refused' });
        }
        return jsonResponse(200, { Id: CONFIG.thisSiteId });
      }

      if (u.includes('/createfieldasxml')) {
        const sent = JSON.parse(body || '{}');
        const schema = String((sent.parameters || {}).SchemaXml || '');
        const name = (NAME_IN_SCHEMA.exec(schema) || [null, '?'])[1];
        const rule = CONFIG.creates[name];
        if (rule && rule.ok === false) {
          return jsonResponse(rule.status || 400, { error: rule.error || 'refused' });
        }
        // `vanish` is the create that answers 200 and leaves no column, which
        // is the shape a status alone cannot tell from a real acceptance.
        if (!(rule && rule.vanish)) fields.set(name, { InternalName: name, schema });
        return jsonResponse(200, { Id: `field-${name}` });
      }

      const field = FIELD_RE.exec(u);
      if (field) {
        const name = field[1];
        if (name === 'RelatedRisk') {
          primaryReads += 1;
          if (CONFIG.primaryReadFailsAt && primaryReads >= CONFIG.primaryReadFailsAt) {
            return jsonResponse(500, { error: 'refused' });
          }
        }
        if (!fields.has(name)) return jsonResponse(404, { error: 'not found' });
        // LookupList and LookupWebId are derived from the schema that was
        // sent, which is what SharePoint does when it honours the attributes;
        // a test that wants a repoint overrides them through CONFIG.readback.
        const schema = fields.get(name).schema || '';
        const listAttr = LIST_IN_SCHEMA.exec(schema);
        const webAttr = WEBID_IN_SCHEMA.exec(schema);
        const payload = {
          Id: `field-${name}`,
          InternalName: name,
          TypeAsString: 'Lookup',
          IsDependentLookup: name === 'RelatedRiskTitle',
          PrimaryFieldId: name === 'RelatedRiskTitle' ? 'field-RelatedRisk' : null,
          DependentLookupInternalNames:
            name === 'RelatedRisk' ? ['RelatedRiskTitle'] : [],
          LookupField: 'Title',
          LookupList: listAttr ? `{${listAttr[1]}}` : undefined,
          LookupWebId: webAttr ? webAttr[1] : CONFIG.thisWebId,
          ...(CONFIG.readback[name] || {}),
        };
        for (const absent of CONFIG.absentProperties) delete payload[absent];
        return jsonResponse(200, payload);
      }

      if (u.includes('web/webs')) return jsonResponse(200, { value: CONFIG.webs });

      if (method === 'POST' && u.endsWith('/web/lists')) {
        const sent = JSON.parse(body || '{}');
        return jsonResponse(201, { Id: `list-${sent.Title}` });
      }

      if (u.includes('/items')) {
        if (method === 'POST') {
          if (u.includes('ProjSource') && CONFIG.sourceRowStatus !== 201) {
            return jsonResponse(CONFIG.sourceRowStatus, { error: 'refused' });
          }
          const sent = JSON.parse(body || '{}');
          // SharePoint refuses a write naming a column that is not there, and
          // a mock that took it would hide a row set through a field the
          // create reported and never left behind.
          const unknown = Object.keys(sent)
            .filter((key) => key.endsWith('Id') && !fields.has(key.slice(0, -2)));
          if (unknown.length) {
            return jsonResponse(400, {
              error: `The field or property '${unknown[0]}' does not exist.`,
            });
          }
          const label = String(sent.Title || '');
          if (label.startsWith('present-') && CONFIG.presentWriteStatus !== 201) {
            return jsonResponse(CONFIG.presentWriteStatus, { error: 'refused' });
          }
          if (label.startsWith('absent-') && CONFIG.absentWriteStatus !== 201) {
            return jsonResponse(CONFIG.absentWriteStatus, { error: CONFIG.absentWriteError });
          }
          const id = nextItemId;
          nextItemId += 1;
          // What the server STORES for an accepted absent-id write, which is a
          // separate question from whether it took the write at all.
          items.set(id, label.startsWith('absent-') && CONFIG.absentStoredId !== 'as-written'
            ? { ...sent, RelatedRiskId: CONFIG.absentStoredId } : sent);
          return jsonResponse(201, { Id: id });
        }
        if (u.includes('$select=Id&$orderby=Id desc')) {
          if (CONFIG.targetIdsStatus !== 200) {
            return jsonResponse(CONFIG.targetIdsStatus, { error: 'refused' });
          }
          return jsonResponse(200, {
            value: ABSENT_ID === null ? [] : [{ Id: CONFIG.targetHighestId }],
          });
        }
        if (ABSENT_ID !== null && u.includes(`/items(${ABSENT_ID})`)) {
          if (CONFIG.absentIdReadStatus !== 200) {
            return jsonResponse(CONFIG.absentIdReadStatus, { error: 'not found' });
          }
          return jsonResponse(200, { Id: ABSENT_ID });
        }
        if (u.includes('$select=RelatedRiskId') && CONFIG.absentRowReadStatus !== 200) {
          return jsonResponse(CONFIG.absentRowReadStatus, { error: 'refused' });
        }
        if (u.includes('$select=RelatedRiskTitle&') || u.endsWith('$select=RelatedRiskTitle')) {
          return jsonResponse(400, {
            error: "The field or property 'RelatedRiskTitle' does not exist",
          });
        }
        if (u.endsWith('$select=RelatedRiskTitleId') && CONFIG.projectedIdStatus !== 200) {
          return jsonResponse(CONFIG.projectedIdStatus, { error: 'refused' });
        }
        // The rows of THIS web, served to a read of the local target list the
        // same way an expansion of a repointed column resolves them.
        const wanted = /\\$filter=Id eq (\\d+)/.exec(u);
        if (wanted) {
          if (CONFIG.localItemsStatus !== 200) {
            return jsonResponse(CONFIG.localItemsStatus, { error: 'refused' });
          }
          return jsonResponse(200, {
            value: CONFIG.localItems.filter((row) => row.Id === Number(wanted[1])),
          });
        }
        const holder = /\\/items\\((\\d+)\\)/.exec(u);
        if (holder) {
          const stored = items.get(Number(holder[1])) || {};
          const expand = /\\$expand=([A-Za-z0-9_]+)/.exec(u);
          if (expand) {
            // Per column as well as globally: one spelling's expansion failing
            // while the other answers is what a combined row has to rule on.
            const only = CONFIG.expandFailsFor[expand[1]];
            if (only) return jsonResponse(only, { error: 'refused' });
            if (CONFIG.expandStatus !== 200) {
              return jsonResponse(CONFIG.expandStatus, { error: 'refused' });
            }
            const row = expandedRow(expand[1], stored[`${expand[1]}Id`]);
            return jsonResponse(200, { [expand[1]]: row ? { Title: row.Title } : null });
          }
          return jsonResponse(200, {
            ...stored,
            RelatedRiskTitleId: stored.RelatedRiskId,
          });
        }
        return jsonResponse(200, { value: [] });
      }

      if (/getbytitle\\('[^']*'\\)$/.test(u)) {
        if (CONFIG.listsExist) return jsonResponse(200, { Id: 'list-existing' });
        return jsonResponse(404, { error: 'not found' });
      }

      return jsonResponse(200, { value: [] });
    };
""")

#: A run where the other web is there with a row in it, all three same-web
#: controls are accepted, and SharePoint refuses both cross-web spellings.
#: Each test changes one thing.
_CROSS_WEB_HEALTHY: dict[str, Any] = {
    "listsExist": False,
    "preexistingFields": [],
    "absentProperties": [],
    "thisWebId": CROSS_WEB_THIS_WEB_ID,
    "thisWebStatus": 200,
    "thisSiteId": CROSS_WEB_THIS_SITE_ID,
    "thisSiteStatus": 200,
    "webs": [{"Id": CROSS_WEB_OTHER_WEB_ID, "Url": CROSS_WEB_OTHER_WEB_URL}],
    "otherWebUrl": CROSS_WEB_OTHER_WEB_URL,
    "otherWebId": CROSS_WEB_OTHER_WEB_ID,
    "otherWebStatus": 200,
    # A subweb found through web/webs sits in the same site collection, which
    # is the topology the arm measures unless an operator supplies another.
    "otherSiteId": CROSS_WEB_THIS_SITE_ID,
    "otherSiteStatus": 200,
    "otherLists": [{"Id": CROSS_WEB_OTHER_LIST_ID, "BaseTemplate": 100, "Hidden": False}],
    "otherListId": CROSS_WEB_OTHER_LIST_ID,
    "otherItems": [{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_REMOTE_TITLE}],
    # The row of THIS web that shares the remote row's number.
    "localItems": [{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_LOCAL_TITLE}],
    "localItemsStatus": 200,
    "otherItemsStatus": 200,
    "sourceRowStatus": 201,
    # The absent-id arm: the target list's highest row, whether the id the
    # probe derives from it reads back absent, and what the two writes answer.
    "targetHighestId": 2,
    "targetIdsStatus": 200,
    "absentIdReadStatus": 404,
    "presentWriteStatus": 201,
    "absentWriteStatus": 201,
    "absentWriteError": "refused",
    "absentStoredId": "as-written",
    "absentRowReadStatus": 200,
    "projectedIdStatus": 200,
    "primaryReadFailsAt": 0,
    "expandStatus": 200,
    "expandFailsFor": {},
    "expandResolvesAs": "target",
    "creates": {
        "XwebList": {"ok": False, "status": 400, "error": "The lookup list is in another web."},
        "XwebListAndWeb": {
            "ok": False, "status": 400, "error": "The lookup list is in another web.",
        },
    },
    "readback": {},
}


def _cross_web_probe_js(other_web_url: str = "") -> str:
    """The rendered probe with its gates opened and its result table exposed.

    The gates are flipped rather than the file being re-rendered with
    different values: what an operator pastes is what this must run.
    `other_web_url` is set the way an operator sets it, by editing the
    constant, so the supplied-web path is exercised as it ships.
    """
    js = CROSS_WEB_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    if other_web_url:
        supplied = js.replace(
            "  const OTHER_WEB_URL = '';",
            f"  const OTHER_WEB_URL = '{other_web_url}';", 1,
        )
        assert supplied != js, "OTHER_WEB_URL is not spelled as this test expects"
        js = supplied
    exposed = js.replace(
        "\n  report();\n",
        "\n  console.log('__ROWS__' + JSON.stringify(RESULTS));\n  report();\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice in before report()"
    return exposed


def _cross_web_transcript(
    other_web_url: str = "", **changes: Any,
) -> tuple[dict[str, dict[str, str]], str]:
    """Run the probe against `_CROSS_WEB_HEALTHY` plus `changes`.

    Returns the rows by id, and what the run printed with this test's own dump
    of the table removed, because what an operator copies back is the whole
    console rather than the row objects.
    """
    config = json.loads(json.dumps(_CROSS_WEB_HEALTHY))
    for key, value in changes.items():
        if key in {"creates", "readback", "expandFailsFor"}:
            config[key].update(value)
        else:
            config[key] = value
    script = (
        _CROSS_WEB_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n" + _cross_web_probe_js(other_web_url)
    )
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    rows = {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}
    return rows, output.replace(line, "")


def _run_cross_web_probe(
    other_web_url: str = "", **changes: Any,
) -> dict[str, dict[str, str]]:
    """The rows alone, for the tests that rule on a verdict rather than a leak."""
    return _cross_web_transcript(other_web_url, **changes)[0]


#: The readback and resolution rows of one spelling, which are recorded per
#: spelling because the two are separate requests that may answer differently.
_LIST_SPELLING_ROWS = (
    "field.cross-web.list-spelling-targets-other-web",
    "field.cross-web.list-spelling-resolves-remote-item",
)
_WEBID_SPELLING_ROWS = (
    "field.cross-web.webid-spelling-targets-other-web",
    "field.cross-web.webid-spelling-resolves-remote-item",
)
_CROSS_WEB_OBSERVATION_ROWS = (
    "field.cross-web.createfieldasxml-other-web-refused",
    "field.cross-web.webid-attribute-refused",
    *_LIST_SPELLING_ROWS,
    *_WEBID_SPELLING_ROWS,
)
#: The two same-web controls, which a cross-web row is only readable beside.
_CROSS_WEB_CONTROL_ROWS = (
    "field.cross-web.control-same-web-lookup-created",
    "field.cross-web.control-same-web-webid-accepted",
)
#: The dependent-lookup arm's fill rows, which share the same fixture.
_FILL_ROWS = (
    "field.lookup.dependent-fill-live-label",
    "field.lookup.dependent-fill-blank-label",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_healthy_run_records_both_controls_and_both_refusals() -> None:
    """The control for every test below.

    Without it, a change that made the arm record NOT ESTABLISHED for
    everything would pass all of them, and this file would be measuring an
    arm that had stopped measuring anything. It covers the dependent-lookup
    arm as well, because those rows share this fixture and the guards below
    can void them too.
    """
    rows = _run_cross_web_probe()

    assert rows["field.cross-web.control-other-web-has-a-list"]["outcome"] == "PASS"
    assert rows["field.cross-web.control-other-web-list-has-an-item"]["outcome"] == "PASS"
    for control in _CROSS_WEB_CONTROL_ROWS:
        assert rows[control]["outcome"] == "ACCEPTED", control
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "REFUSED"
    assert rows["field.cross-web.webid-attribute-refused"]["outcome"] == "REFUSED"
    # Nothing was created, so there is no field to read back and the question
    # does not arise. That is not the same as unanswered.
    for row in _LIST_SPELLING_ROWS + _WEBID_SPELLING_ROWS:
        assert rows[row]["outcome"] == "NOT APPLICABLE", row
    assert "The lookup list is in another web." in (
        rows["field.cross-web.createfieldasxml-other-web-refused"]["evidence"]
    )
    # Every cross-web row names the pair of webs it was measured at, because a
    # row quoted alone otherwise reads as a result about any two webs.
    assert f"other web {CROSS_WEB_OTHER_WEB_ID}" in (
        rows["field.cross-web.createfieldasxml-other-web-refused"]["evidence"]
    )
    assert rows["field.lookup.dependent-fieldref-accepted"]["outcome"] == "ACCEPTED"
    assert rows["field.lookup.isdependentlookup-readback"]["outcome"] == "PASS"
    assert rows["field.lookup.primary-lists-dependent"]["outcome"] == "PASS"
    for row in _FILL_ROWS:
        assert rows[row]["outcome"] == "PASS", row


#: The absent-id arm's two observation rows, void together or not at all.
_ABSENT_ID_OBSERVATION_ROWS = (
    "field.lookup.absent-target-id-write",
    "field.lookup.absent-target-id-readback",
)
_ABSENT_ID_PRESENT_CONTROL = "field.lookup.control-present-target-id-write-accepted"
_ABSENT_ID_ABSENCE_CONTROL = "field.lookup.control-absent-target-id-names-no-row"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_absent_id_arm_records_both_controls_and_both_observations() -> None:
    """The control for the absent-id tests below.

    Without it, a change that voided the arm for every run would pass all of
    them and this file would be measuring an arm that measures nothing.
    """
    rows = _run_cross_web_probe()

    assert rows[_ABSENT_ID_PRESENT_CONTROL]["outcome"] == "PASS"
    assert rows[_ABSENT_ID_ABSENCE_CONTROL]["outcome"] == "PASS"
    assert "1002" in rows[_ABSENT_ID_ABSENCE_CONTROL]["evidence"]
    write = rows["field.lookup.absent-target-id-write"]
    assert write["outcome"] == "ACCEPTED"
    assert write["state"] == "settled"
    readback = rows["field.lookup.absent-target-id-readback"]
    assert readback["outcome"] == "OBSERVED"
    # The two halves the row exists to separate: what the cell kept, and what
    # the lookup resolves to with no row on the other end.
    assert "stored id reads back 1002" in readback["evidence"]
    assert "$expand gives null" in readback["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_absent_id_write_is_recorded_as_a_refusal() -> None:
    """The other answer the arm exists to take.

    A refusal is the result that would let the page say SharePoint checks a
    lookup id at write time, so it has to read as a measurement and not as a
    failed step, and the readback question then does not arise.
    """
    rows = _run_cross_web_probe(
        absentWriteStatus=400,
        absentWriteError="Invalid look up value. A lookup ID was not valid.",
    )

    write = rows["field.lookup.absent-target-id-write"]
    assert write["outcome"] == "REFUSED"
    assert write["state"] == "settled"
    assert "A lookup ID was not valid." in write["evidence"]
    assert rows["field.lookup.absent-target-id-readback"]["outcome"] == "NOT APPLICABLE"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_write_the_server_emptied_reads_back_as_emptied() -> None:
    """Accepting the write and storing nothing is a third answer.

    A report reading a stored id treats it as a live reference, so a run that
    recorded ACCEPTED alone would leave the two apart-facts as one.
    """
    rows = _run_cross_web_probe(absentStoredId=None)

    assert rows["field.lookup.absent-target-id-write"]["outcome"] == "ACCEPTED"
    readback = rows["field.lookup.absent-target-id-readback"]
    assert readback["outcome"] == "OBSERVED"
    assert "stored id reads back null" in readback["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_write_of_a_real_target_id_voids_the_absent_id_rows() -> None:
    """Without that control, a refusal is about creating items on this site."""
    rows = _run_cross_web_probe(presentWriteStatus=403)

    assert rows[_ABSENT_ID_PRESENT_CONTROL]["outcome"] == "FAIL"
    for row in _ABSENT_ID_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row


#: The whole arm, controls included. A primary pointing at some other list
#: leaves the controls exactly as meaningless as the observations, so the
#: guard that catches it has to void all four.
_ABSENT_ID_ARM_ROWS = (
    _ABSENT_ID_PRESENT_CONTROL,
    _ABSENT_ID_ABSENCE_CONTROL,
    *_ABSENT_ID_OBSERVATION_ROWS,
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_reused_primary_pointing_at_another_list_voids_the_whole_arm() -> None:
    """CLEANUP ships false, so a RelatedRisk left by an earlier run is normal.

    Every row of this arm reads the probe's own target list. A primary that
    points somewhere else makes the 404 a fact about a list the lookup never
    consults, and the present-id control passes on any number that other list
    happens to hold, so the arm would settle the wrong condition twice over.
    """
    rows = _run_cross_web_probe(readback={"RelatedRisk": {"LookupList": "{list-elsewhere}"}})

    for row in _ABSENT_ID_ARM_ROWS:
        assert rows[row]["state"] == "void", row
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
    evidence = rows[_ABSENT_ID_PRESENT_CONTROL]["evidence"]
    assert "LookupList=list-elsewhere" in evidence
    assert "CLEANUP = true" in evidence


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_primary_whose_target_never_read_back_voids_the_whole_arm() -> None:
    """A column this run cannot place is not a column it can measure through.

    The reused field is the case: it is there, so nothing is created, and an
    unreadable LookupList leaves the run unable to say which list the write
    below would be about.
    """
    rows = _run_cross_web_probe(listsExist=True, preexistingFields=["RelatedRisk"])

    for row in _ABSENT_ID_ARM_ROWS:
        assert rows[row]["state"] == "void", row
    assert "LookupList=(absent)" in rows[_ABSENT_ID_ABSENCE_CONTROL]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_id_the_target_list_does_hold_voids_the_absent_id_rows() -> None:
    """A write to an id that resolves is an ordinary write.

    Recorded as a measurement it would say SharePoint accepts a dangling
    reference, off a write that was never dangling.
    """
    rows = _run_cross_web_probe(absentIdReadStatus=200)

    control = rows[_ABSENT_ID_ABSENCE_CONTROL]
    assert control["outcome"] == "FAIL"
    assert "the target list holds the row" in control["evidence"]
    for row in _ABSENT_ID_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_read_that_cannot_say_whether_the_row_is_there_is_not_a_present_row() -> None:
    """A refused read is a failed instrument, not a target list that holds it.

    Both void the rows below, and they are recorded apart so a transcript says
    which one happened.
    """
    rows = _run_cross_web_probe(absentIdReadStatus=503)

    control = rows[_ABSENT_ID_ABSENCE_CONTROL]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "HTTP 503" in control["evidence"]
    for row in _ABSENT_ID_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_target_ids_that_do_not_read_back_leave_the_arm_with_no_id_to_use() -> None:
    """No id is known absent, so there is no write to make."""
    rows = _run_cross_web_probe(targetIdsStatus=500, targetHighestId=None)

    assert rows[_ABSENT_ID_ABSENCE_CONTROL]["outcome"] == "NOT ESTABLISHED"
    for row in _ABSENT_ID_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_row_that_does_not_read_back_is_not_an_observation() -> None:
    """The write is still recorded; the readback row has nothing to report."""
    rows = _run_cross_web_probe(absentRowReadStatus=500)

    assert rows["field.lookup.absent-target-id-write"]["outcome"] == "ACCEPTED"
    readback = rows["field.lookup.absent-target-id-readback"]
    assert readback["state"] == "void"
    assert readback["outcome"] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_site_with_no_subweb_voids_the_arm_rather_than_answering_it() -> None:
    """A site with no subweb is one where the question cannot be asked.

    Recording a refusal there would be the arm answering from the absence of
    a fixture, which is the shape AGENTS.md warns about: the experiment
    reporting a result it never measured.
    """
    rows = _run_cross_web_probe(webs=[])

    control = rows["field.cross-web.control-other-web-has-a-list"]
    assert control["outcome"] == "NOT ESTABLISHED"
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_same_web_control_voids_the_cross_web_rows() -> None:
    """Without the control, a refusal says the method did not work here."""
    rows = _run_cross_web_probe(creates={
        "XwebControl": {"ok": False, "status": 500},
        "XwebWebIdControl": {"ok": False, "status": 500},
    })

    assert rows["field.cross-web.control-same-web-lookup-created"]["outcome"] == "REFUSED"
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_same_web_control_left_by_an_earlier_run_is_not_this_run_s_control() -> None:
    """CLEANUP ships false, so the second run finds its own control in place.

    That run sent no create, so it has shown nothing about whether creates
    work now. A run whose creates are all failing (a permission change,
    throttling, an edited fixture) would otherwise read the leftover column
    as an acceptance and file the cross-web refusals as findings.
    """
    rows = _run_cross_web_probe(
        preexistingFields=["XwebControl", "XwebWebIdControl"],
        creates={
            "XwebList": {"ok": False, "status": 403, "error": "Access denied."},
            "XwebListAndWeb": {"ok": False, "status": 403, "error": "Access denied."},
        },
    )

    for control in _CROSS_WEB_CONTROL_ROWS:
        assert rows[control]["outcome"] == "NOT ESTABLISHED", control
        assert "sent no create" in rows[control]["evidence"], control
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row
        assert rows[row]["outcome"] != "REFUSED", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_same_web_control_that_does_not_read_back_is_not_an_acceptance() -> None:
    """HTTP 200 and no column is the failure class, on the control itself."""
    rows = _run_cross_web_probe(creates={
        "XwebControl": {"ok": True, "vanish": True},
        "XwebWebIdControl": {"ok": True, "vanish": True},
    })

    for control in _CROSS_WEB_CONTROL_ROWS:
        assert rows[control]["outcome"] == "NOT ESTABLISHED", control
        assert "did not read back" in rows[control]["evidence"], control
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_same_web_control_pointing_somewhere_else_is_not_an_acceptance() -> None:
    """A column that landed at another list is not the control that was asked
    for, and a refusal beside it would be about some other column."""
    rows = _run_cross_web_probe(readback={
        "XwebControl": {"LookupList": "{99999999-9999-9999-9999-999999999999}"},
        "XwebWebIdControl": {"LookupList": "{99999999-9999-9999-9999-999999999999}"},
    })

    for control in _CROSS_WEB_CONTROL_ROWS:
        assert rows[control]["outcome"] == "NOT ESTABLISHED", control
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_local_webid_voids_only_the_webid_observation() -> None:
    """The WebId row asks about the web boundary, not about the attribute.

    If createfieldasxml will not take `WebId` even when it names THIS web,
    a cross-web refusal carrying `WebId` is a result about the spelling. The
    bare-lookup control still passes there, which is why the WebId row needs
    a control of its own; the List-only row is untouched and still answers.
    """
    rows = _run_cross_web_probe(creates={
        "XwebWebIdControl": {"ok": False, "status": 400, "error": "Invalid attribute WebId."},
    })

    assert rows["field.cross-web.control-same-web-lookup-created"]["outcome"] == "ACCEPTED"
    assert rows["field.cross-web.control-same-web-webid-accepted"]["outcome"] == "REFUSED"
    assert rows["field.cross-web.webid-attribute-refused"]["state"] == "void"
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "REFUSED"
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_create_that_repoints_at_this_web_is_not_a_cross_web_lookup() -> None:
    """The whole reason the readback row exists.

    HTTP 200 and a field that points at the local target list are exactly
    what a silent repoint looks like. Reporting ACCEPTED alone would record
    "SharePoint Online takes cross-web lookups" off a column that takes
    values from this web.
    """
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{44444444-4444-4444-4444-444444444444}",
            "LookupWebId": CROSS_WEB_THIS_WEB_ID,
        }},
    )

    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "ACCEPTED"
    readback = rows["field.cross-web.list-spelling-targets-other-web"]
    assert readback["outcome"] == "FAIL", (
        "the create was accepted and the field points somewhere else, which is "
        "the silent repoint this row exists to catch"
    )
    assert CROSS_WEB_OTHER_LIST_ID in readback["evidence"]
    # The resolution row is asked anyway, and answers on values rather than on
    # metadata: the column stores 41 and expands the row of THIS web numbered
    # 41, which is not the row the id was read out of.
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "FAIL"
    assert "not the Title on that row" in resolved["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_create_that_really_targets_the_other_web_passes() -> None:
    """The opposite result, which no Microsoft page rules out.

    Braces and case are normalised before the comparison, because SharePoint
    returns `LookupList` wrapped in braces and `LookupWebId` bare.
    """
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}, "XwebListAndWeb": {"ok": True}},
        readback={
            "XwebList": {
                "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID.upper() + "}",
                "LookupWebId": CROSS_WEB_OTHER_WEB_ID.upper(),
            },
            "XwebListAndWeb": {
                "LookupList": CROSS_WEB_OTHER_LIST_ID,
                "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
            },
        },
    )

    assert rows["field.cross-web.webid-attribute-refused"]["outcome"] == "ACCEPTED"
    # Both spellings were accepted, so both were exercised and each answers in
    # a row of its own rather than through one verdict over the pair.
    for row in _LIST_SPELLING_ROWS + _WEBID_SPELLING_ROWS:
        assert rows[row]["outcome"] == "PASS", row
    for row, name in (
        (_LIST_SPELLING_ROWS[1], "XwebList"),
        (_WEBID_SPELLING_ROWS[1], "XwebListAndWeb"),
    ):
        assert name in rows[row]["evidence"], row
        assert str(CROSS_WEB_OTHER_ITEM_ID) in rows[row]["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_metadata_nobody_expected_does_not_stop_the_arm_asking_for_a_value() -> None:
    """Metadata and resolution are two observations, not a control and a test.

    A create that is accepted and reads back a LookupWebId nobody expected is
    the case a value is most wanted for. Gating the stronger question on the
    weaker one leaves the run unable to report that the lookup works, which is
    the AGENTS.md corollary about a measurement asserting over its own
    observations.
    """
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {"LookupWebId": ""}},
    )

    assert rows["field.cross-web.list-spelling-targets-other-web"]["outcome"] == "FAIL"
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "PASS", (
        "the column reads back a web id nobody expected and still carries the "
        "row from over there, which is the answer this arm exists to find"
    )
    assert resolved["state"] == "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_expansion_of_a_row_of_this_web_is_not_a_remote_row_resolving() -> None:
    """A lookup id is list-local, so a number alone proves nothing.

    A column that reads back pointing at the other web and quietly resolves
    against this one expands the row of this web carrying the same number. Any
    nonempty title passes that, so the expansion is compared with the Title
    read from the row the id came from.
    """
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
        expandResolvesAs="this-web",
    )

    assert rows["field.cross-web.list-spelling-targets-other-web"]["outcome"] == "PASS"
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "FAIL", (
        "the expansion carries a row of this web, which a test for any "
        "nonempty title reports as a working cross-web lookup"
    )
    assert "not the Title on that row" in resolved["evidence"]


def _fnv1a32(value: str) -> str:
    """What the removed fingerprint would have published for a Title.

    An exact length beside an unsalted 32-bit digest of a short human-written
    string is recoverable by dictionary search, so the transcript may not carry
    either, and this is the derivative the test looks for by name.
    """
    digest = 0x811C9DC5
    for character in value:
        digest = ((digest ^ ord(character)) * 0x01000193) & 0xFFFFFFFF
    return f"{digest:08x}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_no_title_from_either_web_reaches_the_transcript() -> None:
    """The transcript is pasted back into a public issue.

    The arm's GUID-only guarantee covers the row it resolves as well, and it
    covers derivatives of a Title as well as the Title: only the comparison
    goes in the evidence, which is what the row rests on and carries none of
    the value.
    """
    pointing_out = {"XwebList": {
        "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
        "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
    }}
    resolving, resolving_output = _cross_web_transcript(
        creates={"XwebList": {"ok": True}}, readback=pointing_out,
    )
    misdirected, misdirected_output = _cross_web_transcript(
        creates={"XwebList": {"ok": True}}, readback=pointing_out,
        expandResolvesAs="this-web",
    )

    resolve_row = "field.cross-web.list-spelling-resolves-remote-item"
    assert resolving[resolve_row]["outcome"] == "PASS"
    assert misdirected[resolve_row]["outcome"] == "FAIL"
    leaks = (
        CROSS_WEB_REMOTE_TITLE,
        CROSS_WEB_LOCAL_TITLE,
        f"len={len(CROSS_WEB_REMOTE_TITLE)}",
        f"len={len(CROSS_WEB_LOCAL_TITLE)}",
        _fnv1a32(CROSS_WEB_REMOTE_TITLE),
        _fnv1a32(CROSS_WEB_LOCAL_TITLE),
        "fnv=",
    )
    for rows, output in ((resolving, resolving_output), (misdirected, misdirected_output)):
        for leak in leaks:
            assert leak not in output, leak
            for row in rows.values():
                assert leak not in row["evidence"], (row["id"], leak)
    # The comparison is what is left, and it is the evidence the row rests on.
    assert "the same as the Title on that row" in resolving[resolve_row]["evidence"]
    assert "not the Title on that row" in misdirected[resolve_row]["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("only_row", [{"Id": CROSS_WEB_OTHER_ITEM_ID}, {
    "Id": CROSS_WEB_OTHER_ITEM_ID, "Title": "",
}])
def test_a_remote_row_with_no_title_leaves_the_comparison_no_baseline(
    only_row: dict[str, Any],
) -> None:
    """Nothing to compare an expansion with is not a column that resolved one.

    An absent Title and a blank one are the same missing baseline. The list is
    there, so the acceptance rows still answer; the rows resting on the
    comparison are voided, and so is the control that supplies it.
    """
    rows = _run_cross_web_probe(
        otherItems=[only_row],
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    control = rows["field.cross-web.control-other-web-list-has-an-item"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "nonempty Title" in control["evidence"]
    assert rows["field.cross-web.list-spelling-targets-other-web"]["outcome"] == "PASS"
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["state"] == "void"
    assert "nonempty Title" in resolved["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_two_blank_titles_are_not_a_baseline_that_can_tell_the_webs_apart() -> None:
    """The collision a fallback to the first row reintroduces.

    Every row in the other web's list is blank-titled, and so is the row of
    THIS web carrying the same list-local id. A column that quietly repointed
    resolves that local row, its blank expansion compares equal to the blank
    baseline, and the run reports a working cross-web lookup. There is no
    discriminating baseline here, so the row stays unestablished.
    """
    rows = _run_cross_web_probe(
        otherItems=[{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": ""}],
        localItems=[{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": ""}],
        expandResolvesAs="this-web",
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "NOT ESTABLISHED", (
        "the lookup resolved a row of this web and the two blank titles compare "
        "equal, which a fallback baseline reports as PASS"
    )
    assert resolved["state"] == "void"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_row_carrying_a_title_is_preferred_as_the_comparison_baseline() -> None:
    """Two blank titles compare equal, so a blank baseline is the weaker one."""
    rows = _run_cross_web_probe(
        otherItems=[
            {"Id": 7, "Title": ""},
            {"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_REMOTE_TITLE},
        ],
        creates={"XwebList": {"ok": True}},
    )

    control = rows["field.cross-web.control-other-web-list-has-an-item"]
    assert f"row {CROSS_WEB_OTHER_ITEM_ID} " in control["evidence"]
    assert "differs from the Title on row" in control["evidence"]
    assert rows["field.cross-web.list-spelling-resolves-remote-item"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_remote_title_equal_to_the_local_row_at_that_id_is_not_a_baseline() -> None:
    """Nonempty is not discriminating, which is what the baseline has to be.

    The chosen remote row and the row of THIS web carrying the same list-local
    id have the same Title. A column that quietly repointed expands that local
    row, the comparison finds them equal, and the run records a working
    cross-web lookup off a column that never left this web.
    """
    rows = _run_cross_web_probe(
        otherItems=[{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_REMOTE_TITLE}],
        localItems=[{"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_REMOTE_TITLE}],
        expandResolvesAs="this-web",
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    control = rows["field.cross-web.control-other-web-list-has-an-item"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "the same Title as row" in control["evidence"]
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "NOT ESTABLISHED", (
        "the lookup resolved the local row and the two Titles compare equal, "
        "which a nonempty baseline reports as PASS"
    )
    assert resolved["state"] == "void"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_search_moves_on_to_a_row_that_can_tell_the_two_webs_apart() -> None:
    """A colliding row is passed over rather than ending the search.

    Row 41 carries the Title the local row at that id carries. Row 42 has no
    local row at all, so a column that repointed there expands nothing, and it
    is the baseline the arm takes.
    """
    rows = _run_cross_web_probe(
        otherItems=[
            {"Id": CROSS_WEB_OTHER_ITEM_ID, "Title": CROSS_WEB_LOCAL_TITLE},
            {"Id": CROSS_WEB_OTHER_ITEM_ID + 1, "Title": CROSS_WEB_REMOTE_TITLE},
        ],
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    control = rows["field.cross-web.control-other-web-list-has-an-item"]
    assert control["outcome"] == "PASS"
    assert f"row {CROSS_WEB_OTHER_ITEM_ID + 1} " in control["evidence"]
    assert f"holds no row {CROSS_WEB_OTHER_ITEM_ID + 1}" in control["evidence"]
    assert rows["field.cross-web.list-spelling-resolves-remote-item"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_local_row_that_did_not_read_back_leaves_the_baseline_unproven() -> None:
    """A comparison this run cannot make is not a comparison it passed.

    Without the local row the remote Title is only nonempty, which is the
    baseline that cannot tell a repointed column from a working one.
    """
    rows = _run_cross_web_probe(
        localItemsStatus=500,
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    control = rows["field.cross-web.control-other-web-list-has-an-item"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "did not read back (HTTP 500)" in control["evidence"]
    # The list is there, so the acceptance rows still answer.
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "ACCEPTED"
    assert rows["field.cross-web.list-spelling-resolves-remote-item"]["state"] == "void"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_metadata_that_persisted_is_not_a_column_that_resolves() -> None:
    """The readback row's PASS is about properties, not about values.

    A lookup that saves LookupList and LookupWebId, reads them back
    byte-identical and then resolves nothing is exactly the failure this
    repository exists to close, and status plus metadata cannot see it.
    """
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
        expandResolvesAs="nothing",
    )

    assert rows["field.cross-web.list-spelling-targets-other-web"]["outcome"] == "PASS"
    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "FAIL", (
        "the properties persisted and the column resolved nothing, which the "
        "metadata readback alone reports as a cross-web lookup that works"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_remote_row_the_column_refuses_to_store_is_a_resolve_failure() -> None:
    """A column that will not take the id it points at does not resolve."""
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
        sourceRowStatus=400,
    )

    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "FAIL"
    # The refused write is what the row rests on, so it has to be in the
    # evidence: reaching FAIL through a read of a row that was never created
    # reports the same verdict off nothing.
    assert "answered HTTP 400" in resolved["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_expand_that_did_not_answer_leaves_the_resolve_row_open() -> None:
    """A read that failed cannot tell a value that does not resolve from a
    value this spelling cannot read, which is what run 1 found for the
    dependent field's projected text."""
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
        expandStatus=400,
    )

    resolved = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert resolved["outcome"] == "NOT ESTABLISHED"
    assert resolved["state"] != "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_empty_list_in_the_other_web_voids_the_resolve_row() -> None:
    """With no row on the far side there is nothing to resolve to, and a
    column that carries nothing is not a column that resolves nothing."""
    rows = _run_cross_web_probe(
        otherItems=[],
        creates={"XwebList": {"ok": True}},
        readback={"XwebList": {
            "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
            "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
        }},
    )

    assert rows["field.cross-web.control-other-web-list-has-an-item"]["outcome"] == (
        "NOT ESTABLISHED"
    )
    # The acceptance rows are still real: they need a list, not a row in it.
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "ACCEPTED"
    assert rows["field.cross-web.list-spelling-targets-other-web"]["outcome"] == "PASS"
    assert rows["field.cross-web.list-spelling-resolves-remote-item"]["state"] == "void"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_field_left_by_an_earlier_run_is_not_reported_as_this_run_s_answer() -> None:
    """CLEANUP ships false, so a second run finds its own columns in place.

    The create is then never sent, and ACCEPTED would report a request this
    run did not make. The refusal in `_CROSS_WEB_HEALTHY` proves the row can say
    REFUSED at all, so this is a real distinction rather than a row that
    never answers.
    """
    rows = _run_cross_web_probe(listsExist=True, preexistingFields=["XwebList", "XwebListAndWeb"])

    for row in ("field.cross-web.createfieldasxml-other-web-refused",
                "field.cross-web.webid-attribute-refused"):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert "already exists from an earlier run" in rows[row]["evidence"], row
    # No create was sent, so nothing was accepted and there is nothing to
    # read back or to set a value on either, for either spelling.
    for row in _LIST_SPELLING_ROWS + _WEBID_SPELLING_ROWS:
        assert rows[row]["outcome"] == "NOT APPLICABLE", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_create_that_left_no_column_is_not_a_resolution_failure() -> None:
    """A column that is not there cannot be set to a value.

    The create answered 200 and left nothing, so the write below it names a
    lookup property no column carries. SharePoint refuses that for the name,
    and reading the refusal as a cross-web verdict settles FAIL off a field
    that never existed.
    """
    rows = _run_cross_web_probe(creates={"XwebList": {"ok": True, "vanish": True}})

    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "ACCEPTED"
    for row in _LIST_SPELLING_ROWS:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert rows[row]["state"] == "void", row
        assert "did not read back" in rows[row]["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_repoint_one_spelling_shows_is_not_erased_by_the_other_being_unread() -> None:
    """A conclusive negative is not a void.

    One accepted column reads back pointing at this web, which disproves the
    claim on its own; the other answered 200 and left no column to read. A row
    covering both spellings reports NOT ESTABLISHED and discards the
    observation that settled it.
    """
    rows = _run_cross_web_probe(
        creates={
            "XwebList": {"ok": True},
            "XwebListAndWeb": {"ok": True, "vanish": True},
        },
        readback={"XwebList": {
            "LookupList": "{44444444-4444-4444-4444-444444444444}",
            "LookupWebId": CROSS_WEB_THIS_WEB_ID,
        }},
    )

    repointed = rows["field.cross-web.list-spelling-targets-other-web"]
    assert repointed["outcome"] == "FAIL"
    assert repointed["state"] == "settled"
    for row in _WEBID_SPELLING_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_resolution_failure_one_spelling_shows_is_not_erased_by_an_unread_expansion(
) -> None:
    """The same rule on the stronger question.

    One accepted column stores the remote id and expands the row of THIS web
    carrying that number, which disproves the claim; the other column's
    expansion never answered, which settles nothing either way.
    """
    pointing_out = {
        "LookupList": "{" + CROSS_WEB_OTHER_LIST_ID + "}",
        "LookupWebId": CROSS_WEB_OTHER_WEB_ID,
    }
    rows = _run_cross_web_probe(
        creates={"XwebList": {"ok": True}, "XwebListAndWeb": {"ok": True}},
        readback={"XwebList": pointing_out, "XwebListAndWeb": pointing_out},
        expandResolvesAs="this-web",
        expandFailsFor={"XwebListAndWeb": 500},
    )

    misdirected = rows["field.cross-web.list-spelling-resolves-remote-item"]
    assert misdirected["outcome"] == "FAIL"
    assert misdirected["state"] == "settled"
    unread = rows["field.cross-web.webid-spelling-resolves-remote-item"]
    assert unread["outcome"] == "NOT ESTABLISHED"
    assert unread["state"] == "void"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_arm_reports_which_pair_of_webs_it_measured() -> None:
    """The rule this is parked against is broader than any one run.

    It compares two `site_role` labels, which can be deployed to unrelated
    site collections, while the arm measures one pair of webs. A row that did
    not say which pair reads as a result about all of them.
    """
    rows = _run_cross_web_probe()

    control = rows["field.cross-web.control-other-web-has-a-list"]
    assert "found through web/webs" in control["evidence"]
    assert f"THIS site collection {CROSS_WEB_THIS_SITE_ID}" in control["evidence"]
    for row in ("field.cross-web.createfieldasxml-other-web-refused",
                "field.cross-web.webid-attribute-refused"):
        assert f"other web {CROSS_WEB_OTHER_WEB_ID}" in rows[row]["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_supplied_web_measures_that_pair_and_still_names_no_site() -> None:
    """An operator can point the arm at another site collection.

    `web/webs` answers with nothing here, so a run that still finds its target
    found it through OTHER_WEB_URL. The two site ids differ and the row says
    so, and the URL itself stays out of the transcript like every other site
    identifier the arm handles.
    """
    rows, output = _cross_web_transcript(
        CROSS_WEB_OTHER_WEB_URL, webs=[], otherSiteId=CROSS_WEB_FAR_SITE_ID,
    )

    control = rows["field.cross-web.control-other-web-has-a-list"]
    assert control["outcome"] == "PASS"
    assert "supplied through OTHER_WEB_URL" in control["evidence"]
    assert f"ANOTHER site collection {CROSS_WEB_FAR_SITE_ID}" in control["evidence"]
    assert rows["field.cross-web.createfieldasxml-other-web-refused"]["outcome"] == "REFUSED"
    assert CROSS_WEB_OTHER_WEB_URL not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_supplied_url_that_resolves_to_this_web_voids_the_arm() -> None:
    """The worst outcome this arm can produce, off its own operator knob.

    A URL that names the web the page is on, or redirects to it, answers with
    this web's Id. Every column below is then an ordinary same-web lookup:
    both spellings are accepted, both read back where the arm expects, and
    both resolve, so the run reports cross-web lookups working and the rule
    the arm is parked against could be relaxed on the strength of it.
    """
    rows = _run_cross_web_probe(
        CROSS_WEB_OTHER_WEB_URL,
        webs=[],
        otherWebId=CROSS_WEB_THIS_WEB_ID,
        creates={"XwebList": {"ok": True}, "XwebListAndWeb": {"ok": True}},
    )

    control = rows["field.cross-web.control-other-web-has-a-list"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert f"THIS web ({CROSS_WEB_THIS_WEB_ID})" in control["evidence"]
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_this_web_id_that_did_not_read_back_voids_the_arm() -> None:
    """Both ids are a dependency, so one of them missing settles nothing.

    Without this web's Id no candidate can be shown to be a different web,
    and a row that cannot say which two webs it measured is a row about
    neither.
    """
    rows = _run_cross_web_probe(
        thisWebStatus=500,
        creates={"XwebList": {"ok": True}, "XwebListAndWeb": {"ok": True}},
    )

    control = rows["field.cross-web.control-other-web-has-a-list"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "did not read back (HTTP 500)" in control["evidence"]
    for row in _CROSS_WEB_OBSERVATION_ROWS:
        assert rows[row]["state"] == "void", row


# --------------------------------------------------------------------------
# The same probe's dependent-lookup arm, which shares the fixture and had the
# same defect: rows recorded from a step that never answered.
# --------------------------------------------------------------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_dependent_field_left_by_an_earlier_run_is_not_an_acceptance() -> None:
    """The acceptance row is about a request createfieldasxml answered.

    With CLEANUP false the column is already there on every run after the
    first, and that run asked createfieldasxml nothing.
    """
    rows = _run_cross_web_probe(listsExist=True, preexistingFields=["RelatedRiskTitle"])

    accepted = rows["field.lookup.dependent-fieldref-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert "sent no create" in accepted["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_dependent_create_that_leaves_no_column_is_not_an_acceptance() -> None:
    """A status is not a column. The fill rows void with it, because an empty
    projection off a column that is not there says nothing about auto-fill."""
    rows = _run_cross_web_probe(creates={
        "RelatedRiskTitle": {"ok": True, "vanish": True},
    })

    accepted = rows["field.lookup.dependent-fieldref-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert "did not read back" in accepted["evidence"]
    for row in _FILL_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_primary_that_did_not_read_back_cannot_report_the_linkage() -> None:
    """FAIL there would say SharePoint did not link the dependent, off a read
    that never answered. The existence check and the fixture readback are the
    first two reads of the primary, so the linkage read is the third."""
    rows = _run_cross_web_probe(primaryReadFailsAt=3)

    linkage = rows["field.lookup.primary-lists-dependent"]
    assert linkage["outcome"] == "NOT ESTABLISHED"
    assert "did not read back" in linkage["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_primary_served_without_the_linkage_property_is_not_an_empty_linkage() -> None:
    """An absent property and an empty one are different answers."""
    rows = _run_cross_web_probe(absentProperties=["DependentLookupInternalNames"])

    linkage = rows["field.lookup.primary-lists-dependent"]
    assert linkage["outcome"] == "NOT ESTABLISHED"
    assert "no DependentLookupInternalNames property" in linkage["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_source_row_that_was_never_created_is_not_a_projection_that_did_not_fill() -> None:
    """Nothing was set, so nothing can be read back as unset."""
    rows = _run_cross_web_probe(sourceRowStatus=403)

    for row in _FILL_ROWS:
        assert rows[row]["state"] == "void", row
        assert "never created" in rows[row]["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_projected_id_read_that_did_not_answer_is_not_a_fill_failure() -> None:
    """The read is the measurement. Recording FAIL from its HTTP status is the
    probe reporting the failed read as SharePoint's answer."""
    rows = _run_cross_web_probe(projectedIdStatus=500)

    for row in _FILL_ROWS:
        assert rows[row]["state"] == "void", row
        assert "did not read back" in rows[row]["evidence"], row


# --------------------------------------------------------------------------
# unique-transition-probe.js: the transition nothing has measured, and what
# the probe must refuse to conclude when one of its controls did not hold.
#
# The mock below answers the way the SQL Server analogy suggests SharePoint
# might. That is a SCENARIO, not a measurement: what these tests pin is what
# the probe CONCLUDES from an answer, never what SharePoint actually does
# with the write. Only a live run settles that.
# --------------------------------------------------------------------------
TRANSITION_PROBE = MANUAL / "unique-transition-probe.js"

#: The probe's own column names. Spelled here because every fault below is
#: addressed to one of them, and a rename in the probe must fail these tests
#: rather than leave them matching nothing and still passing.
_TRANSITION_COLUMNS = ("DupRef", "UniqRef", "IdxRef", "NoteRef")
#: The two rows that are void the moment a control does not hold.
_TRANSITION_MEASUREMENTS = (
    "field.unique.transition-on-duplicate-values",
    "field.unique.transition-without-index",
)

# A SharePoint with four columns, two items and one knob per thing a live run
# could do to this probe: refuse a MERGE, accept one and change nothing, drop
# a property out of a readback, or hand back rows an earlier run left.
_TRANSITION_HARNESS = textwrap.dedent(r"""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    let listExists = CONFIG.listExists;
    const fields = new Map();
    const items = [];
    for (let n = 0; n < CONFIG.seededItems; n += 1) {
      items.push({
        Id: n + 1, Title: `left behind ${n + 1}`,
        DupRef: 'old', UniqRef: `old-${n}`, IdxRef: `old-${n}`,
      });
    }

    const respond = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const FIELD = /getbyinternalnameortitle\('([^']*)'\)/;

    // A read fault is armed by the COLUMN it is about plus how many reads of
    // that column to let past, never by a global call count: a count pins the
    // test to today's request order and moves the moment a question is added
    // earlier in the run.
    const readFaults = CONFIG.readFaults.map((fault) => ({ ...fault, seen: 0 }));
    const faultFor = (column) => {
      const rule = readFaults.find((fault) => fault.column === column);
      if (!rule) return null;
      rule.seen += 1;
      if (rule.seen <= rule.skip) return null;
      if (rule.seen > rule.skip + rule.times) return null;
      return rule;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const body = opts.body ? JSON.parse(opts.body) : null;
      console.log(`__CALL__${verb} ${u}`);

      if (u.includes('/contextinfo')) {
        return respond(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (u.endsWith('/_api/web/lists') && method === 'POST') {
        listExists = true;
        return respond(201, { Id: 'list-1' });
      }

      const named = FIELD.exec(u);
      if (named) {
        const column = named[1];
        if (verb === 'MERGE') {
          const refused = CONFIG.refuseMerge[column];
          if (refused) {
            return respond(refused, { error: { message: {
              value: 'the write was refused' } } });
          }
          const held = fields.get(column);
          if (held && CONFIG.mergeApplies[column] !== false) {
            for (const [key, value] of Object.entries(body)) {
              if (key !== '__metadata') held[key] = value;
            }
          }
          return respond(204, {});
        }
        const fault = faultFor(column);
        if (fault && fault.status) {
          return respond(fault.status, { error: 'the read did not answer' });
        }
        const held = fields.get(column);
        if (!held) return respond(404, { error: `no column '${column}'` });
        const shape = { ...held };
        if (fault && fault.drop) delete shape[fault.drop];
        return respond(200, shape);
      }

      if (u.includes('/fields') && method === 'POST') {
        fields.set(body.Title, {
          Title: body.Title,
          TypeAsString: body.FieldTypeKind === 3 ? 'Note' : 'Text',
          EnforceUniqueValues: false,
          Indexed: false,
          ...(CONFIG.fieldSeeds[body.Title] || {}),
        });
        return respond(201, { Title: body.Title });
      }
      if (u.includes('/items') && method === 'POST') {
        items.push({ Id: items.length + 1, ...body });
        return respond(201, { Id: items.length });
      }
      if (u.includes('/items')) {
        if (CONFIG.itemsReadStatus) {
          return respond(CONFIG.itemsReadStatus, { error: 'the read did not answer' });
        }
        const rows = items.map((row) => {
          const copy = { ...row, ...(CONFIG.itemOverrides[row.Id] || {}) };
          if (CONFIG.dropItemColumn) delete copy[CONFIG.dropItemColumn];
          return copy;
        });
        return respond(200, { value: rows });
      }
      if (u.includes("getbytitle('")) {
        return listExists
          ? respond(200, { Id: 'list-1', Title: 'dbmlsp Probe Unique Transition' })
          : respond(404, { error: { message: 'the list does not exist' } });
      }
      return respond(404, { error: 'no such endpoint' });
    };
""")

#: A run on a site that answers the way the SQL Server analogy suggests: the
#: unsupported column type and the duplicate column are refused, and the two
#: columns whose values are distinct are not. Each test changes one thing.
_TRANSITION_HEALTHY: dict[str, Any] = {
    "listExists": False,
    "seededItems": 0,
    "fieldSeeds": {},
    "refuseMerge": {"NoteRef": 500, "DupRef": 500},
    "mergeApplies": {},
    "readFaults": [],
    "itemsReadStatus": None,
    "dropItemColumn": None,
    "itemOverrides": {},
}


def _transition_read_fault(
    column: str,
    *,
    skip: int = 0,
    times: int = 1,
    status: int | None = None,
    drop: str | None = None,
) -> dict[str, Any]:
    """One field-read fault: which column, how many reads to let past, what it does."""
    return {
        "column": column, "skip": skip, "times": times, "status": status, "drop": drop,
    }


def _transition_probe_js() -> str:
    """The rendered probe with its gates opened and its result table exposed.

    The gates are flipped rather than the file being re-rendered with other
    values: what an operator pastes is what these tests must run.
    """
    js = TRANSITION_PROBE.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    for column in _TRANSITION_COLUMNS:
        assert f"'{column}'" in js, f"the probe no longer names the column {column!r}"
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n"
        "    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run_transition_probe(**changes: Any) -> dict[str, dict[str, str]]:
    """Run the probe against `_TRANSITION_HEALTHY` plus `changes`.

    `refuseMerge` replaces rather than merges: a test that lifts the refusal
    on one column is saying exactly that, and a merge would leave it in place
    and measure a run nobody asked for.
    """
    config = json.loads(json.dumps(_TRANSITION_HEALTHY))
    config.update(changes)
    script = (
        _TRANSITION_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _transition_probe_js()
    )
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None,
    )
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_transition_run_whose_controls_hold_answers_both_measurements() -> None:
    """The control for every test below.

    Without it a probe that voided everything would pass them all: each one
    asserts that a row is not a settled verdict, and a row that never settles
    under any conditions measures nothing at all.

    The outcomes here are the mock's behaviour, not SharePoint's. What is
    pinned is that the probe reads a refusal as REFUSED, reads an accepted
    write that reads back enforced as ACCEPTED, and reaches both
    measurements.
    """
    rows = _run_transition_probe()

    assert rows["field.unique.fixture-transition-list"]["outcome"] == "PASS"
    assert rows["field.unique.fixture-unconstrained-columns"]["outcome"] == "PASS"
    assert rows["field.unique.fixture-duplicate-items"]["outcome"] == "PASS"
    assert rows["field.unique.control-note-column-refused"]["outcome"] == "REFUSED"
    control = rows["field.unique.control-transition-on-unique-values"]
    assert control["outcome"] == "ACCEPTED", control
    assert rows["field.unique.transition-on-duplicate-values"]["outcome"] == "REFUSED"
    assert rows["field.unique.transition-without-index"]["outcome"] == "ACCEPTED"
    assert not [row for row in rows.values() if row["state"] != "settled"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_endpoint_that_accepts_the_unsupported_type_voids_every_measurement() -> None:
    """Microsoft documents Multiple lines of text as an unsupported column
    type for unique columns, so an endpoint that takes the write there is not
    refusing on content at all.

    Under that endpoint a refusal below could be anything and an acceptance
    could be a server saying yes to whatever it is sent, so neither
    measurement is a measurement.
    """
    rows = _run_transition_probe(refuseMerge={"DupRef": 500})

    assert rows["field.unique.control-note-column-refused"]["outcome"] == "ACCEPTED"
    voided = ("field.unique.control-transition-on-unique-values", *_TRANSITION_MEASUREMENTS)
    for name in voided:
        assert rows[name]["state"] == "void", name
        assert "rather than a refusal" in rows[name]["evidence"], name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_transition_refused_on_distinct_values_voids_the_duplicate_row() -> None:
    """A tenant that refuses the write wherever it is sent has said nothing
    about duplicates.

    This is what the positive control exists for: without it the duplicate
    row would record REFUSED and be read back as the answer to the question
    the probe was written to ask.
    """
    rows = _run_transition_probe(
        refuseMerge={"NoteRef": 500, "UniqRef": 500, "DupRef": 500},
    )

    control = rows["field.unique.control-transition-on-unique-values"]
    assert control["outcome"] == "REFUSED", control
    for name in _TRANSITION_MEASUREMENTS:
        assert rows[name]["state"] == "void", name
        assert "say nothing about the duplicates" in rows[name]["evidence"], name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_write_that_is_accepted_and_changes_nothing_is_not_recorded_as_accepted() -> None:
    """HTTP 204 with the constraint still off is the silent failure this
    project exists to catch, and ACCEPTED would report it as the constraint
    having been applied."""
    rows = _run_transition_probe(
        refuseMerge={"NoteRef": 500}, mergeApplies={"DupRef": False},
    )

    row = rows["field.unique.transition-on-duplicate-values"]
    assert row["outcome"] == "ACCEPTED, NOT APPLIED", row
    assert "EnforceUniqueValues=false" in row["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_accepted_write_whose_column_will_not_read_back_answers_neither_way() -> None:
    """The write was accepted and nothing was read after it, so whether the
    constraint is on is exactly what this run does not know.

    The fault is armed on the THIRD read of the column, which is the one the
    transition makes: the create check and the fixture verification come
    first and both have to answer for the run to get this far.
    """
    rows = _run_transition_probe(
        refuseMerge={"NoteRef": 500},
        readFaults=[_transition_read_fault("DupRef", skip=2, status=500)],
    )

    row = rows["field.unique.transition-on-duplicate-values"]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert row["state"] == "open", row
    assert "did not read back" in row["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_readback_payload_without_the_property_is_not_read_as_unconstrained() -> None:
    """A body that omits `EnforceUniqueValues` reads as undefined, which
    compares unequal to true and looks identical to the constraint not having
    been applied. It is a read that did not answer."""
    rows = _run_transition_probe(
        refuseMerge={"NoteRef": 500},
        readFaults=[
            _transition_read_fault("DupRef", skip=2, drop="EnforceUniqueValues"),
        ],
    )

    row = rows["field.unique.transition-on-duplicate-values"]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert "carries no EnforceUniqueValues" in row["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throttled_write_is_not_recorded_as_a_refusal() -> None:
    """429 is about the moment, not about the content. Recorded as a refusal
    it would answer the probe's one question with a throttle."""
    rows = _run_transition_probe(refuseMerge={"NoteRef": 500, "DupRef": 429})

    row = rows["field.unique.transition-on-duplicate-values"]
    assert row["outcome"] == "NOT ESTABLISHED", row
    assert "HTTP 429" in row["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_that_already_carries_the_constraint_voids_the_run() -> None:
    """CLEANUP ships false, so a second run finds the columns its first run
    left. The transition out of the unconstrained state cannot be asked of a
    column that has already made it."""
    rows = _run_transition_probe(
        fieldSeeds={"DupRef": {"EnforceUniqueValues": True, "Indexed": True}},
    )

    fixture = rows["field.unique.fixture-unconstrained-columns"]
    assert fixture["outcome"] == "FAIL", fixture
    assert "EnforceUniqueValues reads back true" in fixture["evidence"], fixture
    for name in _TRANSITION_MEASUREMENTS:
        assert rows[name]["state"] == "void", name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_fixture_readback_missing_indexed_fails_rather_than_assuming_false() -> None:
    """The starting state is a dependency, and a payload that does not carry
    `Indexed` has not established that it is false."""
    rows = _run_transition_probe(
        readFaults=[_transition_read_fault("IdxRef", skip=1, drop="Indexed")],
    )

    fixture = rows["field.unique.fixture-unconstrained-columns"]
    assert fixture["outcome"] == "FAIL", fixture
    assert "carries no Indexed" in fixture["evidence"], fixture


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_items_an_earlier_run_left_are_not_measured_as_this_run_s_values() -> None:
    """The duplicate is the independent variable. Rows this run did not write
    are not known to hold it, and a run that reads them is measuring somebody
    else's data."""
    rows = _run_transition_probe(listExists=True, seededItems=2)

    items = rows["field.unique.fixture-duplicate-items"]
    assert items["outcome"] == "FAIL", items
    assert "already holds 2 item(s)" in items["evidence"], items
    voided = (
        "field.unique.control-note-column-refused",
        "field.unique.control-transition-on-unique-values",
        *_TRANSITION_MEASUREMENTS,
    )
    for name in voided:
        assert rows[name]["state"] == "void", name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_duplicate_column_that_reads_back_two_values_fails_the_fixture() -> None:
    """A site that rewrote, trimmed or dropped one of the two writes leaves a
    column with no duplicate in it, and every row below would then be about a
    column whose values are distinct."""
    rows = _run_transition_probe(itemOverrides={"2": {"DupRef": "something-else"}})

    items = rows["field.unique.fixture-duplicate-items"]
    assert items["outcome"] == "FAIL", items
    assert "which is not 1 distinct value(s)" in items["evidence"], items
    for name in _TRANSITION_MEASUREMENTS:
        assert rows[name]["state"] == "void", name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_item_payload_without_the_column_is_not_read_as_a_value() -> None:
    """A row that does not carry `DupRef` reads as undefined, and a set of
    undefined values is one distinct value, which is exactly the shape the
    duplicate fixture is looking for."""
    rows = _run_transition_probe(dropItemColumn="DupRef")

    items = rows["field.unique.fixture-duplicate-items"]
    assert items["outcome"] == "FAIL", items
    assert "carries no DupRef" in items["evidence"], items


# --------------------------------------------------------------------------
# save-instant-paths-probe.js and form-validation-probe.js: the scratch-list
# fixtures both write, and the rows that may not answer when one of them was
# accepted and then dropped.
# --------------------------------------------------------------------------
SCRATCH_SAVE_PATHS_PROBE = MANUAL / "save-instant-paths-probe.js"
SCRATCH_FORM_PROBE = MANUAL / "form-validation-probe.js"


def _fixture_probe_js(path: Path) -> str:
    """A rendered probe with its gates open and its result table exposed.

    The gates are flipped rather than the file being re-rendered, for the
    reason `_probe_js` gives: what an operator pastes is what these tests
    must run. The dump is spliced into report() itself rather than into one
    call site, because these probes return through report() from several
    places and those early exits are exactly what a failed fixture takes.
    """
    js = path.read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _fixture_rows(output: str) -> dict[str, dict[str, str]]:
    """id -> the whole recorded row. The whole row, because what a voided row
    has to carry is a REASON, and an outcome alone says nothing about that."""
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"the probe recorded no result table:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


#: A SharePoint holding the scratch list both probes write to, controllable
#: in the five ways a run can go wrong with every request still answering:
#: the field create refused, the dynamic default dropped, either rule
#: accepted and not stored, and the =TODAY() default never filled.
_SCRATCH_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'Mon, 14 Sep 2026 09:00:00 GMT' },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // A 2xx carrying an empty or non-JSON body. `res.json()` rejects, which
    // spGet catches, so the probe is handed { ok: true, body: null }.
    const emptyResponse = (status) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'Mon, 14 Sep 2026 09:00:00 GMT' },
      json: async () => { throw new Error('the response carried no JSON'); },
      text: async () => '',
    });

    // The columns the scratch list holds, by name, and the list's own rule.
    // Both are stored VERBATIM as the writes leave them, so a probe reading
    // one back sees what it sent rather than a mock paraphrasing it.
    const fields = new Map(Object.entries(CONFIG.fields));
    let listFormula = CONFIG.initialListFormula;
    let nextItem = 1;

    const FIELD = /\\/fields\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)/;
    const ITEM = /\\/items\\((\\d+)\\)/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body));
      const path = u.split('/_api/')[1] || '';

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (path.startsWith('web/regionalsettings/timezone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time' });
      }

      const named = FIELD.exec(path);
      if (named) {
        const held = fields.get(named[1]);
        if (!held) return jsonResponse(404, { error: 'no such field' });
        if (verb === 'MERGE') {
          if (CONFIG.columnRuleLands && 'ValidationFormula' in sent) {
            held.ValidationFormula = sent.ValidationFormula;
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { InternalName: named[1], Title: named[1], ...held });
      }

      if (path.includes('/fields')) {
        if (method === 'POST') {
          if (!CONFIG.createLands) {
            return jsonResponse(500, { error: 'the field create was refused' });
          }
          fields.set(sent.Title, {
            TypeAsString: 'DateTime',
            DisplayFormat: sent.DisplayFormat,
            // A default the server took and did not keep is the knob this
            // exists for: the create still answers 201.
            DefaultValue: CONFIG.defaultLands ? (sent.DefaultValue || null) : null,
            ValidationFormula: null,
            // Served explicitly, because SharePoint serves the whole entity
            // and a probe reading a property it withheld must not read that
            // as the column carrying nothing.
            Required: false,
          });
          return jsonResponse(201, { d: { Id: `field-${sent.Title}` } });
        }
        return jsonResponse(200, {
          value: [...fields.keys()].map((title) => ({ Title: title })),
        });
      }

      if (path.includes('AddValidateUpdateItemUsingPath')) {
        if (CONFIG.formEndpointStatus) {
          return jsonResponse(CONFIG.formEndpointStatus, { error: 'the form endpoint failed' });
        }
        // This endpoint answers 200 for a refusal too, so a 200 nobody can
        // read is the one shape that says nothing either way.
        if (CONFIG.emptyFormEndpoint) return emptyResponse(200);
        const id = nextItem;
        nextItem += 1;
        return jsonResponse(200, { d: { AddValidateUpdateItemUsingPath: { results: [
          { FieldName: 'Id', FieldValue: String(id), HasException: false },
        ] } } });
      }

      // The optional hidden list, which is read back by title. Its own branch,
      // so the readback can answer the three ways that matter: served hidden,
      // served without the property, and 2xx with nothing in it.
      if (path.includes(CONFIG.hiddenTitle)) {
        if (CONFIG.hiddenRead === 'empty') return emptyResponse(200);
        if (CONFIG.hiddenRead === 'withheld') return jsonResponse(200, { NoCrawl: true });
        return jsonResponse(200, { Hidden: true, NoCrawl: true });
      }

      const item = ITEM.exec(path);
      if (item) {
        if (CONFIG.emptyItemRead) return emptyResponse(200);
        return jsonResponse(200, {
          Id: Number(item[1]),
          Title: `row ${item[1]}`,
          DM: null,
          TR: '2026-09-14T00:00:00Z',
          WR: '2026-09-14T09:00:00Z',
          T: CONFIG.tValue,
          Created: '2026-09-14T09:00:00Z',
          Modified: '2026-09-14T09:00:00Z',
        });
      }
      if (path.includes('/items')) {
        if (method === 'POST') {
          if (CONFIG.itemCreateStatus) {
            return jsonResponse(CONFIG.itemCreateStatus, { error: 'the item create failed' });
          }
          if (CONFIG.emptyItemCreate) return emptyResponse(201);
          const id = nextItem;
          nextItem += 1;
          return jsonResponse(201, { d: { Id: id } });
        }
        // The bare 'today-now' row an earlier setup run left behind, which
        // form-validation reuses rather than accumulating one per run.
        if (CONFIG.bareItemLeft && path.includes('today-now')) {
          return jsonResponse(200, {
            value: [{ Id: CONFIG.bareItemLeft, Title: 'today-now' }],
          });
        }
        return jsonResponse(200, { value: [] });
      }

      if (verb === 'MERGE') {
        if (CONFIG.listMergeStatus) {
          return jsonResponse(CONFIG.listMergeStatus, { error: 'the list MERGE failed' });
        }
        if (CONFIG.listRuleLands) listFormula = sent.ValidationFormula;
        return jsonResponse(204, {});
      }
      const list = {
        Id: 'list-1',
        ListItemEntityTypeFullName: 'SP.Data.ScratchListItem',
        ValidationFormula: listFormula,
        RootFolder: { ServerRelativeUrl: '/sites/test/Lists/Scratch' },
      };
      // An $expand can answer 2xx without the expansion in it.
      if (!CONFIG.rootFolderServed) delete list.RootFolder;
      return jsonResponse(200, list);
    };
""")

#: A date column as the today-semantics probe leaves it, and the one carrying
#: the =TODAY() default that form-validation reads rather than creates.
_SCRATCH_DATE = {
    "TypeAsString": "DateTime", "DisplayFormat": 0,
    "DefaultValue": None, "ValidationFormula": None, "Required": False,
}
_SCRATCH_TODAY = {**_SCRATCH_DATE, "DefaultValue": "=TODAY()"}

#: Nothing has gone wrong: the scratch list is there with DM and T, every
#: create lands, every default is kept and both rules store.
_SCRATCH_HEALTHY: dict[str, Any] = {
    "fields": {"DM": dict(_SCRATCH_DATE), "T": dict(_SCRATCH_TODAY)},
    "createLands": True,
    "defaultLands": True,
    "columnRuleLands": True,
    "listRuleLands": True,
    "tValue": "2026-09-14T00:00:00Z",
    # What the list already holds before this run writes anything, and the
    # three ways a request can fail for a reason that is not a refusal.
    "initialListFormula": "",
    "itemCreateStatus": None,
    "formEndpointStatus": None,
    "listMergeStatus": None,
    "bareItemLeft": None,
    # A request can answer 2xx and carry nothing a probe can read: an empty
    # body on an item create, on an item read or on the hidden list's
    # readback, and a payload that withheld what was asked for.
    "emptyItemCreate": False,
    "emptyItemRead": False,
    "emptyFormEndpoint": False,
    "rootFolderServed": True,
    "hiddenTitle": "dbml-probe-hidden-verify",
    "hiddenRead": "served",
}


def _run_scratch_probe(
    probe: Path, hidden_list: bool = False, **changes: Any,
) -> dict[str, dict[str, str]]:
    """Run one scratch-list probe against `_SCRATCH_HEALTHY` plus `changes`.

    `hidden_list` opens the one gate beyond CONFIRMED and ALLOW_WRITES that a
    probe here ships closed, because the row behind it is the only one that
    reports on a list this probe creates rather than on the scratch list.
    """
    config = json.loads(json.dumps(_SCRATCH_HEALTHY))
    config.update(changes)
    js = _fixture_probe_js(probe)
    if hidden_list:
        opened = js.replace(
            "  const CREATE_HIDDEN_LIST = false;", "  const CREATE_HIDDEN_LIST = true;", 1)
        assert opened != js, "the CREATE_HIDDEN_LIST gate is not spelled as this test expects"
        js = opened
    script = _SCRATCH_HARNESS.replace("__CONFIG__", json.dumps(config)) + "\n" + js
    return _fixture_rows(_run(script))


#: What save-instant-paths records about the [today] default racing the save,
#: and the six steps it sends a person away to perform by hand.
_SAVE_PATHS_RACE_ROWS = (
    "formula.validation.today-default-races-modified-rule-rest",
    "formula.validation.today-default-races-modified-rule-form-endpoint",
    "formula.validation.form-new-prefilled-default-under-modified-rule",
)
_SAVE_PATHS_HUMAN_ROWS = (
    "formula.validation.form-edit-today-under-three-column-rule",
    "formula.validation.form-edit-tomorrow-under-three-column-rule",
    "formula.validation.grid-edit-today-under-modified-rule",
    "formula.validation.grid-edit-tomorrow-under-modified-rule",
    "formula.validation.bulk-edit-today-under-modified-rule",
    "formula.validation.form-new-prefilled-default-under-modified-rule",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_save_paths_run_with_the_defaults_in_place_answers_the_race() -> None:
    """The control for the two below.

    Without it, a probe that had stopped measuring the race at all would pass
    both of them.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE)

    assert rows["formula.validation.fixture-default-columns"]["outcome"] == "PASS"
    assert "[today]" in rows["formula.validation.fixture-default-columns"]["evidence"]
    assert rows["formula.validation.fixture-three-column-modified-rule-stored"]["outcome"] == "PASS"
    assert rows["formula.validation.today-default-races-modified-rule-rest"]["outcome"] == (
        "ALL SAVED"
    )
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes"),
    [
        ("two columns of the right Title were left by an earlier run with no default",
         {"fields": {"DM": dict(_SCRATCH_DATE), "T": dict(_SCRATCH_TODAY),
                     "TR": dict(_SCRATCH_DATE),
                     "WR": {**_SCRATCH_DATE, "DisplayFormat": 1}}}),
        ("the create was accepted and the dynamic default was not kept",
         {"defaultLands": False}),
    ],
)
def test_columns_without_the_today_default_do_not_answer_the_race(
    why: str, changes: dict[str, Any],
) -> None:
    """`fixture-default-columns` was a literal 'PASS' over a reuse by Title.

    With no dynamic default a bare create races nothing, all five land, and
    the probe reports that the default does not race the rule. That is the
    reassuring answer three shipped solutions are gated on, recorded off a
    column that has no default at all.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, **changes)

    fixture = rows["formula.validation.fixture-default-columns"]
    assert fixture["outcome"] == "FAIL", why
    assert "DefaultValue" in fixture["evidence"]
    for row in _SAVE_PATHS_RACE_ROWS:
        assert rows[row]["state"] == "void", f"{row} answered when {why}"
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
    # The rule is still stored, so the rows that are only about [DM] under it
    # are still a person's to perform.
    assert rows["formula.validation.grid-edit-today-under-modified-rule"]["outcome"] == "MANUAL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_rule_that_never_stored_voids_every_save_path_row_under_it() -> None:
    """The MERGE answers 204 whether or not the store kept the formula.

    A save accepted with no rule in place is not a save accepted under the
    rule, and six of these rows are steps a person is sent to perform by hand
    before anyone looks at the fixture row above them.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, listRuleLands=False)

    stored = rows["formula.validation.fixture-three-column-modified-rule-stored"]
    assert stored["outcome"] == "FAIL"
    assert 'stored: ""' in stored["evidence"]
    for row in (*_SAVE_PATHS_RACE_ROWS, *_SAVE_PATHS_HUMAN_ROWS):
        assert rows[row]["state"] == "void", row


#: The two form steps that are only about the DT column rule, and the four
#: that are only about the list rule over [DM] and [Modified].
_FORM_DT_ROWS = (
    "formula.validation.form-new-today-under-today-rule",
    "formula.validation.form-new-tomorrow-under-today-rule",
)
_FORM_DM_ROWS = (
    "formula.validation.form-new-today-under-modified-rule",
    "formula.validation.form-new-tomorrow-under-modified-rule",
    "formula.validation.form-edit-today-under-modified-rule",
    "formula.validation.form-edit-tomorrow-under-modified-rule",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_form_validation_run_with_both_rules_stored_sends_the_person_out() -> None:
    """The control for the three below."""
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE)

    assert rows["formula.validation.fixture-dt-column"]["outcome"] == "PASS"
    assert rows["formula.validation.fixture-today-column-rule-stored"]["outcome"] == "PASS"
    assert rows["formula.validation.fixture-modified-list-rule-stored"]["outcome"] == "PASS"
    assert rows["formula.datetime.today-function-default-value"]["outcome"] == "PASS"
    for row in (*_FORM_DT_ROWS, *_FORM_DM_ROWS):
        assert rows[row]["outcome"] == "MANUAL", row
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_rule_accepted_and_dropped_voids_only_the_dt_form_steps() -> None:
    """Six MANUAL form findings hang off these two fixture rows.

    Recorded from the MERGE status alone, a rule that never landed is written
    up as a form-versus-REST divergence: the form accepts tomorrow because
    there is no rule, and the transcript reads as the modern form evaluating
    TODAY() differently from REST.
    """
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, columnRuleLands=False)

    stored = rows["formula.validation.fixture-today-column-rule-stored"]
    assert stored["outcome"] == "FAIL"
    assert "stored null" in stored["evidence"]
    for row in _FORM_DT_ROWS:
        assert rows[row]["state"] == "void", row
    for row in _FORM_DM_ROWS:
        assert rows[row]["outcome"] == "MANUAL", f"{row} is not about the DT column rule"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_rule_accepted_and_dropped_voids_only_the_modified_form_steps() -> None:
    """The other half of the same fixture, and the other four steps."""
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, listRuleLands=False)

    assert rows["formula.validation.fixture-modified-list-rule-stored"]["outcome"] == "FAIL"
    for row in _FORM_DM_ROWS:
        assert rows[row]["state"] == "void", row
    for row in _FORM_DT_ROWS:
        assert rows[row]["outcome"] == "MANUAL", f"{row} is not about the list rule"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_bare_item_whose_today_default_never_filled_resolves_nothing() -> None:
    """T and its =TODAY() default come from the today-semantics probe.

    The row was a literal 'PASS' over whatever the read returned, so a run
    against a list without that column printed "T = undefined" beside the word
    PASS and the site's resolved TODAY() was recorded as observed.
    """
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, tValue=None)

    resolved = rows["formula.datetime.today-function-default-value"]
    assert resolved["outcome"] == "NOT ESTABLISHED"
    assert "today-semantics" in resolved["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_bare_item_create_that_served_no_id_leaves_the_row_open() -> None:
    """`bare.body.d.Id` was read off a response that only had to be 2xx, so an
    empty body threw before the six form steps were printed."""
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, emptyItemCreate=True)

    resolved = rows["formula.datetime.today-function-default-value"]
    assert resolved["outcome"] == "NOT ESTABLISHED"
    assert "served no id" in resolved["evidence"]
    # The fixture rows and the steps a person performs are still reported.
    assert rows["formula.validation.fixture-today-column-rule-stored"]["outcome"] == "PASS"
    for row in (*_FORM_DT_ROWS, *_FORM_DM_ROWS):
        assert rows[row]["outcome"] == "MANUAL", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes", "marker"),
    [
        ("the create served no id", {"emptyItemCreate": True}, "served no id"),
        ("the row did not read back", {"emptyItemRead": True}, "did not read back"),
    ],
)
def test_five_creates_that_answered_still_count_when_the_rows_do_not_read(
    why: str, changes: dict[str, Any], marker: str,
) -> None:
    """The race row counts what each CREATE answered, so a readback that never
    answered costs the evidence line its values and nothing else.

    `r.body.d.Id` and `row.body.Id` were both dereferenced unguarded, and
    either one threw away all fourteen rows, including the six a person is
    sent to perform.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, **changes)

    race = rows["formula.validation.today-default-races-modified-rule-rest"]
    assert race["outcome"] == "ALL SAVED", why
    assert marker in race["evidence"]
    for row in _SAVE_PATHS_HUMAN_ROWS:
        assert rows[row]["outcome"] == "MANUAL", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_form_endpoint_answer_nobody_could_read_is_not_a_save() -> None:
    """AddValidateUpdateItemUsingPath reports a refusal INSIDE a 200, so the
    payload is the answer rather than the status.

    The row read the results out of `r2.ok && r2.body && ...`, which is an
    empty list both for a payload nobody could read and for a save that went
    through, and recorded SAVED for the first.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, emptyFormEndpoint=True)

    endpoint = rows["formula.validation.today-default-races-modified-rule-form-endpoint"]
    assert endpoint["outcome"] == "NOT ESTABLISHED"
    assert "no form-endpoint results" in endpoint["evidence"]
    assert rows["formula.validation.today-default-races-modified-rule-rest"]["outcome"] == (
        "ALL SAVED"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_that_served_no_root_folder_leaves_the_form_endpoint_open() -> None:
    """`list.body.RootFolder.ServerRelativeUrl` assumed the $expand came back.

    A 2xx without the expansion threw, so the run lost the race row it had
    already measured as well as the row this one is about.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, rootFolderServed=False)

    endpoint = rows["formula.validation.today-default-races-modified-rule-form-endpoint"]
    assert endpoint["outcome"] == "NOT ESTABLISHED"
    assert "no RootFolder path" in endpoint["evidence"]
    assert rows["formula.validation.today-default-races-modified-rule-rest"]["outcome"] == (
        "ALL SAVED"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("hidden_read", "outcome", "marker"),
    [
        ("served", "PASS", "Hidden=true"),
        ("empty", "NOT ESTABLISHED", "did not read back"),
        ("withheld", "NOT ESTABLISHED", "carried no Hidden property"),
    ],
)
def test_a_hidden_list_nobody_read_is_not_a_list_that_came_back_visible(
    hidden_read: str, outcome: str, marker: str,
) -> None:
    """FAIL on this row says the tenant would not keep a list hidden, which
    decides where the verification artifact may write.

    It was recorded off `hb.body && hb.body.Hidden`, so a readback that
    answered 2xx with nothing, and one whose payload withheld the property,
    both produced it. The first case here is the control: without it a probe
    that had stopped reading the list at all would pass the other two.
    """
    rows = _run_scratch_probe(
        SCRATCH_SAVE_PATHS_PROBE, hidden_list=True, hiddenRead=hidden_read)

    hidden = rows["field.list.hidden-list-readback"]
    assert hidden["outcome"] == outcome
    assert marker in hidden["evidence"]


# --------------------------------------------------------------------------
# folder-under-schema-probe.js: the state each row NAMES, read back off the
# library rather than taken from the 2xx of the write meant to enter it.
# --------------------------------------------------------------------------
FOLDER_SCHEMA_PROBE = MANUAL / "folder-under-schema-probe.js"

#: Every row the bare-library control gates, which is all of them.
_FOLDER_SCHEMA_GATED_ROWS = (
    "library.folder.add-with-broken-inheritance",
    "library.folder.add-with-required-column",
    "library.folder.add-with-column-validation",
    "library.folder.add-with-list-validation",
    "library.folder.add-using-path-under-validation",
    "library.folder.add-as-list-item-under-validation",
    "library.folder.clear-list-validation-to-create",
    "library.folder.restore-list-validation-after-folders",
    "library.folder.folder-survives-restored-validation",
    "library.folder.control-restored-validation-refuses-a-folder",
)

#: The four rows that measure the only shape a fix can take: clear the list
#: formula, create the folder, put the formula back.
_FOLDER_SCHEMA_RESTORE_ROWS = _FOLDER_SCHEMA_GATED_ROWS[-4:]

_FOLDER_SCHEMA_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    const ROOT = '/sites/test/ProbeLib';
    // The folders that exist under the library root, by name. A create that
    // answers 200 and adds nothing here is the silent no-op every row would
    // otherwise report as the state accepting a folder, and one seeded here is
    // the folder an earlier run of this probe left under that state's name.
    const folders = new Set(CONFIG.preexistingFolders);
    let listExists = false;
    let unique = false;
    // A guard column an earlier run left behind. CLEANUP ships false, so this
    // is the reuse path rather than an exotic one.
    let guard = CONFIG.preexistingGuard;
    let listFormula = '';
    let clearedOnce = false;

    const ADD = /folders\\/add\\(url='([^']*)'\\)/;
    const USING_PATH = /AddUsingPath\\(decodedurl='([^']*)'\\)/;
    const BY_URL = /GetFolderByServerRelativeUrl\\('([^']*)'\\)/;

    // The live finding this probe is chasing: a library carrying a list
    // ValidationFormula refuses the create. 500 is the status every
    // SharePoint refusal this project has recorded came back as.
    const refusedByRule = () => CONFIG.refuseUnderRule && listFormula !== '';

    const createFolder = (name) => {
      // Named rather than counted, so a test says WHICH create failed and
      // stays pinned to that one when a question is added before it.
      if (CONFIG.addFailsFor[name]) {
        return jsonResponse(CONFIG.addFailsFor[name], { error: 'the folder create failed' });
      }
      if (refusedByRule()) {
        return jsonResponse(500, { error: { message: { value: 'Cannot create folder' } } });
      }
      if (CONFIG.folderLands) folders.add(name);
      return jsonResponse(200, { d: { Exists: true } });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body) || '{}');
      const path = u.split('/_api/')[1] || '';

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }

      const added = ADD.exec(path);
      if (added) return createFolder(added[1]);
      const usingPath = USING_PATH.exec(path);
      if (usingPath) return createFolder(usingPath[1].slice(ROOT.length + 1));

      const byUrl = BY_URL.exec(path);
      if (byUrl && method === 'GET') {
        const name = byUrl[1].slice(ROOT.length + 1);
        if (!folders.has(name)) return jsonResponse(404, { error: 'not found' });
        return jsonResponse(200, { Exists: true, ServerRelativeUrl: byUrl[1] });
      }

      if (path === 'web/lists' && method === 'POST') {
        listExists = true;
        return jsonResponse(201, { Id: 'list-1' });
      }
      if (!path.startsWith('web/lists/getbytitle')) {
        return jsonResponse(404, { error: 'no such endpoint' });
      }
      if (!listExists) return jsonResponse(404, { error: 'list not found' });

      if (path.includes('/breakroleinheritance')) {
        if (CONFIG.roleBreakLands) unique = true;
        return jsonResponse(200, {});
      }
      if (path.includes('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: ROOT });
      }
      if (path.includes('/fields/getbyinternalnameortitle')) {
        if (!guard) return jsonResponse(404, { error: 'no such field' });
        if (verb === 'MERGE') {
          if (CONFIG.columnRuleLands) guard.ValidationFormula = sent.ValidationFormula;
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { ...guard });
      }
      if (path.includes('/fields') && method === 'POST') {
        if (!CONFIG.guardCreateOk) return jsonResponse(500, { error: 'refused' });
        // SharePoint refuses a second column of the same name, so a reused
        // library answers the create rather than rebuilding the column.
        if (guard) {
          return jsonResponse(500, { error: { message: { value:
            'A field or property with the name dbmlspGuard already exists.' } } });
        }
        guard = {
          Title: sent.Title, TypeAsString: 'Text',
          // Required arriving true and reading back false is the case this
          // knob is for: the create still answers 201.
          Required: CONFIG.guardRequired, ValidationFormula: null,
          // The probe sends no DefaultValue, so a created column has none.
          DefaultValue: null,
        };
        return jsonResponse(201, { d: { Id: 'field-guard' } });
      }
      if (path.includes('/items')) {
        if (method === 'POST') {
          if (sent.FileSystemObjectType === 1) return createFolder(sent.FileLeafRef);
          return jsonResponse(201, { d: { Id: 1 } });
        }
        const wanted = /FileLeafRef%20eq%20'([^']*)'/.exec(path);
        const name = wanted ? decodeURIComponent(wanted[1]) : '';
        if (!folders.has(name)) return jsonResponse(200, { value: [] });
        return jsonResponse(200, { value: [
          { Id: 7, FileSystemObjectType: 1, FileLeafRef: name, dbmlspGuard: null },
        ] });
      }

      if (verb === 'MERGE') {
        const wanted = String(sent.ValidationFormula);
        const clearing = wanted === '';
        // The restore is the first non-clearing list MERGE AFTER a clear, so
        // it is recognised by the call it follows rather than by a request
        // count, which would shift the moment a question is added earlier.
        if (!clearing && clearedOnce && CONFIG.restoreMergeStatus) {
          return jsonResponse(CONFIG.restoreMergeStatus, { error: 'the restore failed' });
        }
        if (clearing) clearedOnce = true;
        if (clearing ? CONFIG.clearLands : CONFIG.listRuleLands) listFormula = wanted;
        return jsonResponse(204, {});
      }
      return jsonResponse(200, {
        Id: 'list-1',
        HasUniqueRoleAssignments: unique,
        ValidationFormula: listFormula,
        ListItemEntityTypeFullName: 'SP.Data.ProbeLibItem',
      });
    };
""")

#: A run that reproduces what the live deploy hit: the bare library takes a
#: folder, so do the first three states, and the list ValidationFormula is
#: what refuses one. Each test changes one knob.
_FOLDER_SCHEMA_HEALTHY: dict[str, Any] = {
    "folderLands": True,
    "refuseUnderRule": True,
    "roleBreakLands": True,
    "guardCreateOk": True,
    "guardRequired": True,
    "columnRuleLands": True,
    "listRuleLands": True,
    "clearLands": True,
    # A column an earlier run left on the library, and the two ways a write can
    # fail for a reason that is not the server rejecting it.
    "preexistingGuard": None,
    "preexistingFolders": [],
    "addFailsFor": {},
    "restoreMergeStatus": None,
}


def _run_folder_schema_probe(**changes: Any) -> dict[str, dict[str, str]]:
    config = json.loads(json.dumps(_FOLDER_SCHEMA_HEALTHY))
    config.update(changes)
    script = (
        _FOLDER_SCHEMA_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _fixture_probe_js(FOLDER_SCHEMA_PROBE)
    )
    return _fixture_rows(_run(script))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_folder_schema_run_attributes_the_refusal_to_the_list_formula() -> None:
    """The control for every test below, and the answer the probe was written
    to get: three states take a folder and the list formula is the one that
    does not, so the clear-create-restore shape is worth measuring."""
    rows = _run_folder_schema_probe()

    assert rows["library.folder.control-add-on-bare-library"]["outcome"] == "PASS"
    for row in ("library.folder.add-with-broken-inheritance",
                "library.folder.add-with-required-column",
                "library.folder.add-with-column-validation"):
        assert rows[row]["outcome"] == "PASS", row
    assert rows["library.folder.add-with-list-validation"]["outcome"] == "REFUSED"
    assert rows["library.folder.clear-list-validation-to-create"]["outcome"] == "PASS"
    assert rows["library.folder.restore-list-validation-after-folders"]["outcome"] == "PASS"
    assert rows["library.folder.folder-survives-restored-validation"]["outcome"] == "PASS"
    assert rows["library.folder.control-restored-validation-refuses-a-folder"]["outcome"] == "PASS"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_create_that_answers_2xx_and_leaves_no_folder_attributes_nothing() -> None:
    """Eight rows recorded PASS on the status alone while the evidence beside
    them read "no list item was served for that name".

    On the bare-library control that is the whole run: every later refusal
    would be attributed to a setting, on a library where the create never
    made a folder in any state.
    """
    rows = _run_folder_schema_probe(folderLands=False)

    control = rows["library.folder.control-add-on-bare-library"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "left no folder" in control["evidence"]
    for row in _FOLDER_SCHEMA_GATED_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_inheritance_that_was_not_broken_is_not_a_state_the_run_entered() -> None:
    """breakroleinheritance was gated on a bare `ok`.

    A 200 that left the library inheriting means the folder that follows was
    created on an inheriting library, and the row says it was not.
    """
    rows = _run_folder_schema_probe(roleBreakLands=False)

    acl = rows["library.folder.add-with-broken-inheritance"]
    assert acl["outcome"] == "NOT ESTABLISHED"
    assert "HasUniqueRoleAssignments reads back false" in acl["evidence"]
    # The states after it are still entered, so they still answer.
    assert rows["library.folder.add-with-required-column"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_that_is_not_required_is_not_the_required_state() -> None:
    """`Required: true` was gated on the create's status.

    Everything downstream names that column, so a column that came back
    optional leaves three further states measuring something else.
    """
    rows = _run_folder_schema_probe(guardRequired=False)

    required = rows["library.folder.add-with-required-column"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert "Required=false" in required["evidence"]
    assert rows["library.folder.add-with-column-validation"]["outcome"] == "NOT ESTABLISHED"
    assert rows["library.folder.add-with-list-validation"]["outcome"] == "NOT ESTABLISHED"
    for row in _FOLDER_SCHEMA_RESTORE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_formula_that_did_not_store_is_not_the_final_state() -> None:
    """The MERGE answers 204 either way, and the four rows about the fix are
    all about a library the formula is supposed to be on."""
    rows = _run_folder_schema_probe(listRuleLands=False)

    validated = rows["library.folder.add-with-list-validation"]
    assert validated["outcome"] == "NOT ESTABLISHED"
    assert 'it reads back ""' in validated["evidence"]
    for row in _FOLDER_SCHEMA_RESTORE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_formula_that_did_not_clear_is_not_the_window_the_fix_needs() -> None:
    """The clear was gated on a bare `ok` too.

    A create accepted while the formula was still there would be recorded as
    the cleared library accepting it, which is the one claim the whole
    clear-create-restore shape rests on.
    """
    rows = _run_folder_schema_probe(clearLands=False)

    for row in _FOLDER_SCHEMA_RESTORE_ROWS:
        assert rows[row]["state"] == "void", row
        assert "was not cleared" in rows[row]["evidence"], row


# --------------------------------------------------------------------------
# calculated-choice-operand.js: the acceptance rows, which say what SharePoint
# ALLOWS. A column left by an earlier run is not this run accepting anything,
# and neither is a 200 that added no column.
# --------------------------------------------------------------------------
CALC_CHOICE_PROBE = MANUAL / "calculated-choice-operand.js"

#: Every row that reports whether a createfieldasxml was accepted. These are
#: what the Person-operand negative control is FOR: an acceptance means
#: nothing from a probe that could not have seen a refusal.
_CALC_CHOICE_ACCEPTANCE_ROWS = (
    "formula.choice.calc-column-accepted",
    "formula.choice.spaced-display-name-accepted",
    "formula.choice.number-result-accepted",
    "formula.choice.datetime-result-accepted",
    "formula.calc.lookup-operand-accepted",
    "formula.choice.retitled-operand-referenced-anew",
)

#: The columns those rows create, in the same order, so a reuse run can be
#: expressed as "an earlier run left all six behind".
_CALC_CHOICE_ACCEPTANCE_FIELDS = [
    "ProbeRoute", "SpacedRoute", "ProbeScore", "ProbeDue", "LookupCalc", "RetiredRef",
]

_CALC_CHOICE_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // A 2xx carrying an empty or non-JSON body. `res.json()` rejects, which
    // spGet catches, so the probe is handed { ok: true, body: null }.
    const emptyResponse = (status) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => { throw new Error('the response carried no JSON'); },
      text: async () => '',
    });

    // Lists by title, each holding its own columns by internal name. Columns
    // are stored as the SchemaXml left them, so a probe reading Formula back
    // sees what it sent.
    const lists = new Map();
    // The items each create left, by id. A calculated column is evaluated on
    // READ, as SharePoint does: it is never written and never stored.
    const rows = new Map();
    let nextItem = 1;
    for (const title of CONFIG.existingLists) lists.set(title, new Map());
    for (const name of CONFIG.preexistingFields) {
      lists.get(CONFIG.existingLists[0])
        .set(name, { InternalName: name, Formula: '=sent by an earlier run' });
    }

    // The leading space matters: DisplayName="..." ends in Name="...", so an
    // unanchored pattern reads every display name as an internal one.
    const NAME_IN_SCHEMA = / Name="([^"]+)"/;
    const TYPE_IN_SCHEMA = /Type="([^"]+)"/;
    const DISPLAY_IN_SCHEMA = /DisplayName="([^"]+)"/;
    const FORMULA_IN_SCHEMA = /<Formula>([^<]*)<\\/Formula>/;
    const LIST = /web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)/;
    const FIELD = /\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;

    // The four calculated columns this probe creates, evaluated over the row
    // the create sent. Each is served only while its column is on the list.
    const evaluate = (fields, row) => {
      const due = new Date(new Date(row.ProbeRaised || 0).getTime()
        + (row.ProbePriority === 'High' ? 1 : 7) * 86400000);
      const served = { ...row };
      if (fields.has('ProbeRoute')) {
        served.ProbeRoute = row.RaisedAtTier === undefined
          ? null : `${row.RaisedAtTier} -> ${row.TargetTier || ''}`;
      }
      if (fields.has('SpacedRoute')) {
        served.SpacedRoute = row.SpacedFrom === undefined
          ? null : `${row.SpacedFrom} -> ${row.SpacedTo || ''}`;
      }
      if (fields.has('ProbeScore')) {
        served.ProbeScore = row.ProbePriority === undefined ? null
          : row.ProbePriority === 'High' ? 3 : row.ProbePriority === 'Medium' ? 2 : 1;
      }
      if (fields.has('ProbeDue')) {
        served.ProbeDue = row.ProbeRaised === undefined ? null : due.toISOString();
      }
      if (fields.has('RetireRoute')) {
        served.RetireRoute = row.RetireMe === undefined ? null : `${row.RetireMe} fixed`;
      }
      for (const prop of CONFIG.withholdItemProps) delete served[prop];
      return served;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body) || '{}');
      const path = u.split('/_api/')[1] || '';

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (path === 'web/lists' && method === 'POST') {
        lists.set(sent.Title, new Map());
        return jsonResponse(201, { Id: `list-${sent.Title}` });
      }

      const named = LIST.exec(path);
      if (!named) return jsonResponse(404, { error: 'no such endpoint' });
      const fields = lists.get(named[1]);
      if (!fields) return jsonResponse(404, { error: 'list not found' });
      const rest = named[2];

      const field = FIELD.exec(rest);
      if (field) {
        const held = fields.get(field[1]);
        if (!held) return jsonResponse(404, { error: 'no such field' });
        if (verb === 'MERGE') {
          if (CONFIG.fieldMergeStatus) {
            return jsonResponse(CONFIG.fieldMergeStatus, { error: 'the field MERGE failed' });
          }
          Object.assign(held, sent);
          return jsonResponse(204, {});
        }
        // The whole-entity read and the $select read are separate knobs: the
        // probe asks the first about a column's shape and the second about
        // what one validation store holds.
        const selected = rest.includes('$select=');
        const empty = selected ? CONFIG.emptySelectRead : CONFIG.emptyFieldRead;
        if (empty.includes(field[1])) return emptyResponse(200);
        if (selected && CONFIG.withholdSelected.includes(field[1])) {
          return jsonResponse(200, { InternalName: field[1] });
        }
        return jsonResponse(200, { ...held });
      }
      if (rest.includes('/createfieldasxml')) {
        const schema = String((sent.parameters || {}).SchemaXml || '');
        const name = (NAME_IN_SCHEMA.exec(schema) || [null, '?'])[1];
        const type = (TYPE_IN_SCHEMA.exec(schema) || [null, '?'])[1];
        // The documented refusal this probe's negative control rests on: a
        // Person operand inside a calculated formula.
        if (CONFIG.personOperandRefused && type === 'Calculated' && schema.includes('ProbeOwner')) {
          // The status is a knob because 500 is a refusal and 429 is not, and
          // the control may only conclude from the first.
          return jsonResponse(CONFIG.personControlStatus, { error: { message: { value:
            'One or more column references are not allowed' } } });
        }
        if (CONFIG.refuse.includes(name)) {
          return jsonResponse(CONFIG.refuseStatus, { error: { message: { value: 'refused' } } });
        }
        // An accepted create that adds no column: the readback is what tells
        // this from an acceptance.
        if (!CONFIG.noReadbackFor.includes(name)) {
          fields.set(name, {
            InternalName: name,
            TypeAsString: type,
            Title: (DISPLAY_IN_SCHEMA.exec(schema) || [null, name])[1],
            Formula: (FORMULA_IN_SCHEMA.exec(schema) || [null, ''])[1],
            // What an earlier run left this column as. CLEANUP ships false, so
            // a create is skipped and the probe reads whatever is there.
            ...(CONFIG.leftoverShape[name] || {}),
          });
        }
        return jsonResponse(200, { Id: `field-${name}` });
      }
      const item = ITEM.exec(rest);
      if (item) {
        const row = rows.get(Number(item[1]));
        if (!row) return jsonResponse(404, { error: 'no such item' });
        if (CONFIG.emptyItemRead) return emptyResponse(200);
        return jsonResponse(200, evaluate(fields, row));
      }
      if (rest.includes('/items')) {
        if (method === 'POST') {
          if (CONFIG.emptyItemCreate) return emptyResponse(201);
          const id = nextItem;
          nextItem += 1;
          rows.set(id, { Id: id, ...sent });
          return jsonResponse(201, { Id: id });
        }
        return jsonResponse(200, { value: [] });
      }
      // The lookup target, read for the GUID the lookup column points at.
      if (CONFIG.emptyTargetRead && named[1].endsWith('Target')) return emptyResponse(200);
      return jsonResponse(200, { Id: `list-${named[1]}`, Title: named[1] });
    };
""")

#: A clean site: no leftover columns, every create landing, and a Person
#: operand refused so the probe can tell acceptance from refusal.
_CALC_CHOICE_HEALTHY: dict[str, Any] = {
    "existingLists": [],
    "preexistingFields": [],
    "refuse": [],
    "noReadbackFor": [],
    "personOperandRefused": True,
    # 500 is the status every SharePoint refusal this project has recorded came
    # back as; the knobs exist so a test can send one that is not a refusal.
    "personControlStatus": 500,
    "refuseStatus": 500,
    "fieldMergeStatus": None,
    "leftoverShape": {},
    # A request can answer 2xx and carry nothing a probe can read: an empty
    # body on a field read, on a $select read, on an item read or on an item
    # create, and a payload that simply withholds the property asked for.
    "emptyFieldRead": [],
    "emptySelectRead": [],
    "withholdSelected": [],
    "emptyItemRead": False,
    "emptyItemCreate": False,
    "emptyTargetRead": False,
    "withholdItemProps": [],
}


def _run_calc_choice_probe(**changes: Any) -> dict[str, dict[str, str]]:
    config = json.loads(json.dumps(_CALC_CHOICE_HEALTHY))
    config.update(changes)
    script = (
        _CALC_CHOICE_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _fixture_probe_js(CALC_CHOICE_PROBE)
    )
    return _fixture_rows(_run(script))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_clean_calc_choice_run_answers_what_sharepoint_accepts() -> None:
    """The control for the three below. Without it, a probe that recorded NOT
    ESTABLISHED for every acceptance would pass all of them."""
    rows = _run_calc_choice_probe()

    assert rows["formula.choice.calc-column-accepted"]["outcome"] == "PASS"
    assert "reads back with Formula" in rows["formula.choice.calc-column-accepted"]["evidence"]
    assert rows["formula.calc.lookup-operand-accepted"]["outcome"] == "ACCEPTED"
    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "PASS"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_left_by_an_earlier_run_is_not_this_run_accepting_it() -> None:
    """CLEANUP ships false, so finding the column already there is the normal
    path, and it was recorded as PASS.

    `formula.calc.lookup-operand-accepted` contradicts this project's own
    denylist, so "SharePoint ALLOWS this" is the sentence that gets quoted,
    and off a reuse this run sent no create at all.
    """
    rows = _run_calc_choice_probe(
        existingLists=["dbmlsp Probe CalcChoice"],
        preexistingFields=_CALC_CHOICE_ACCEPTANCE_FIELDS,
    )

    for row in _CALC_CHOICE_ACCEPTANCE_ROWS:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert "already exists from an earlier run" in rows[row]["evidence"], row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_create_that_answers_200_and_adds_no_column_is_not_an_acceptance() -> None:
    """The other half of the same row: a status is not a column."""
    rows = _run_calc_choice_probe(noReadbackFor=["ProbeRoute"])

    accepted = rows["formula.choice.calc-column-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert "did not read back" in accepted["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_insensitive_calc_choice_run_voids_every_acceptance_it_recorded() -> None:
    """The header says to read the negative control first and treat the rest
    as worthless if it did not hold, and nothing enforced that.

    A Person operand accepted means this run cannot tell an accepted
    createfieldasxml from a refused one, so every acceptance above is a
    restatement of the probe's own insensitivity.
    """
    rows = _run_calc_choice_probe(personOperandRefused=False)

    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "FAIL"
    for row in _CALC_CHOICE_ACCEPTANCE_ROWS:
        assert rows[row]["state"] == "void", row
        assert "negative control did not hold" in rows[row]["evidence"], row


#: The rows that report a value a saved item rendered, rather than whether a
#: create was accepted. Each one is read off an item this run created.
_CALC_CHOICE_RENDER_ROWS = (
    "formula.choice.calc-column-renders",
    "formula.choice.metachar-value-renders",
    "formula.choice.blank-operand-renders",
)
_CALC_CHOICE_COMBO_ROWS = (
    "formula.choice.spaced-display-name-renders",
    "formula.choice.number-result-computes",
    "formula.choice.datetime-result-computes",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_field_read_that_carried_no_payload_is_not_an_acceptance() -> None:
    """`ok: true` is not `I read this`: a 2xx with an empty or non-JSON body
    leaves `body` null.

    The row settled on `!back.ok`, so an empty 2xx fell through to the
    acceptance line, which dereferenced the payload and threw. One odd
    response then cost the run every result it had already gathered.
    """
    rows = _run_calc_choice_probe(emptyFieldRead=["ProbeRoute"])

    accepted = rows["formula.choice.calc-column-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert "did not read back" in accepted["evidence"]
    stored = rows["formula.choice.formula-as-stored"]
    assert stored["outcome"] == "NOT ESTABLISHED"
    assert "did not read back" in stored["evidence"]
    for row in _CALC_CHOICE_RENDER_ROWS:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
    # The run carried on and answered everything the unreadable column does
    # not bear on, which is what an aborted run cannot do.
    assert rows["formula.choice.number-result-accepted"]["outcome"] == "PASS"
    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes"),
    [
        ("the column's shape read answered 2xx with no payload",
         {"emptyFieldRead": ["ProbeLookup"]}),
        ("the target list read answered 2xx with no payload", {"emptyTargetRead": True}),
    ],
)
def test_a_lookup_shape_read_that_carried_no_payload_is_not_a_lookup_column(
    why: str, changes: dict[str, Any],
) -> None:
    """The same shape one property further on: `lookupBack.ok` was tested and
    `lookupBack.body.TypeAsString` read, so an empty 2xx threw. The target
    list's own GUID was read the same way, one call earlier.

    The three rows they gate are about a Lookup operand, so a column whose
    type this run never read cannot answer any of them.
    """
    rows = _run_calc_choice_probe(**changes)

    for row in (
        "formula.calc.lookup-operand-accepted",
        "formula.validation.lookup-operand",
        "expression.client-validation.lookup-operand",
    ):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", f"{row} when {why}"
    assert rows["formula.validation.person-operand"]["outcome"] == "ACCEPTED"
    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes"),
    [
        ("the readback answered 2xx with no payload", {"emptySelectRead": ["ProbeOwner"]}),
        ("the payload withheld the property", {"withholdSelected": ["ProbeOwner"]}),
    ],
)
def test_a_validation_store_nobody_read_is_not_a_store_that_discarded(
    why: str, changes: dict[str, Any],
) -> None:
    """ACCEPTED THEN DISCARDED is a claim about what the store kept.

    `readBackOf` answered null for a read that never happened, and null is
    also what a store that dropped the formula reads back as. Only the second
    is evidence.
    """
    rows = _run_calc_choice_probe(**changes)

    for row in ("formula.validation.person-operand",
                "expression.client-validation.person-operand"):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", f"{row} when {why}"
        assert "did not see whether the store kept" in rows[row]["evidence"], row
    # The lookup stores were read, so they still answer.
    assert rows["formula.validation.lookup-operand"]["outcome"] == "ACCEPTED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes", "marker"),
    [
        ("the item read answered 2xx with no payload", {"emptyItemRead": True},
         "did not read back"),
        ("the item create served no id", {"emptyItemCreate": True}, "served no id"),
    ],
)
def test_a_computed_value_nobody_read_is_not_a_column_rendering_nothing(
    why: str, changes: dict[str, Any], marker: str,
) -> None:
    """Seven rows report a value a saved item rendered, and each of them read
    `made.body.Id` or `back.body.<column>` off a response that only had to be
    2xx. Both threw, which lost the whole run.
    """
    rows = _run_calc_choice_probe(**changes)

    for row in (*_CALC_CHOICE_RENDER_ROWS, *_CALC_CHOICE_COMBO_ROWS,
                "formula.choice.retitled-operand-survives"):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", f"{row} when {why}"
        assert marker in rows[row]["evidence"], row
    assert rows["formula.choice.calc-column-accepted"]["outcome"] == "PASS"
    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_item_served_without_the_column_is_not_a_blank_computed_value() -> None:
    """The blank-operand row reports the stored value as the finding, so a
    payload that never carried the column would be written up as SharePoint
    rendering nothing for it."""
    rows = _run_calc_choice_probe(withholdItemProps=["ProbeRoute"])

    for row in _CALC_CHOICE_RENDER_ROWS:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert "without a ProbeRoute property" in rows[row]["evidence"], row
    # The combo item carries its own columns, so those rows still measure.
    for row in _CALC_CHOICE_COMBO_ROWS:
        assert rows[row]["outcome"] == "PASS", row


# --------------------------------------------------------------------------
# library-columns-probe.js: the required column and the list ValidationFormula
# the two headline rows are ABOUT, read back off the library rather than taken
# from the status of the write that was meant to put them there.
# --------------------------------------------------------------------------
LIB_COLS_PROBE = MANUAL / "library-columns-probe.js"

_LIB_COLS_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.window = {
      _spPageContextInfo: {
        webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
      },
    };

    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });

    // A 2xx carrying an empty or non-JSON body. `res.json()` rejects, which
    // spGet catches, so the probe is handed { ok: true, body: null }.
    const emptyResponse = (status) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => { throw new Error('the response carried no JSON'); },
      text: async () => '',
    });

    const lists = new Map();
    const items = new Map();
    let nextItem = 1;
    let listFormula = '';

    // Only these reach a column. Anything else is the server refusing a
    // property it does not have, which is the negative control's whole job.
    const WRITABLE = ['Title', 'ColChoice', 'ColLookupId', 'ColRequired'];

    const NAME_IN_SCHEMA = / Name="([^"]+)"/;
    const TYPE_IN_SCHEMA = /Type="([^"]+)"/;
    const REQUIRED_IN_SCHEMA = /Required="TRUE"/;
    const LIST = /web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)/;
    const FIELD = /\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)/;
    const ITEM = /^\\/items\\((\\d+)\\)/;
    const FILTERED = /FileLeafRef eq '([^']+)'/;
    const UPLOAD = /Files\\/add\\(url='([^']+)'/;

    const shapeOf = (row) => ({
      ...row,
      // The calculated column is evaluated on read, as SharePoint does: it is
      // never written and never stored.
      ColCalc: row.ColChoice === undefined || row.ColChoice === null
        ? null : `${row.ColChoice} - calc`,
    });

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      let sent = {};
      try { sent = JSON.parse(raw || '{}'); } catch { sent = {}; }
      const path = u.split('/_api/')[1] || '';

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest' } } });
      }
      if (path === 'web/lists' && method === 'POST') {
        lists.set(sent.Title, new Map());
        return jsonResponse(201, { Id: `list-${sent.Title}` });
      }

      const named = LIST.exec(path);
      if (!named) return jsonResponse(404, { error: 'no such endpoint' });
      const fields = lists.get(named[1]);
      if (!fields) return jsonResponse(404, { error: 'list not found' });
      const rest = named[2];

      const uploaded = UPLOAD.exec(rest);
      if (uploaded) {
        if (CONFIG.uploadStatus) {
          return jsonResponse(CONFIG.uploadStatus, { error: 'the upload failed' });
        }
        const id = nextItem;
        nextItem += 1;
        items.set(id, { Id: id, FileLeafRef: uploaded[1], Title: uploaded[1] });
        return jsonResponse(200, { d: { Name: uploaded[1] } });
      }
      if (rest.includes('/RootFolder/Files(')) {
        // 2 is 'none': the upload left the file checked in. The other two
        // readings are a 2xx with nothing in it and a payload that served the
        // file without the property the row is about.
        if (CONFIG.filePropsRead === 'empty') return emptyResponse(200);
        if (CONFIG.filePropsRead === 'withheld') return jsonResponse(200, { MajorVersion: 1 });
        return jsonResponse(200, { CheckOutType: 2, MajorVersion: 1 });
      }

      const field = FIELD.exec(rest);
      if (field) {
        const held = fields.get(field[1]);
        if (!held) return jsonResponse(404, { error: 'no such field' });
        return jsonResponse(200, { ...held });
      }
      if (rest.includes('/createfieldasxml')) {
        const schema = String((sent.parameters || {}).SchemaXml || '');
        const name = (NAME_IN_SCHEMA.exec(schema) || [null, '?'])[1];
        fields.set(name, {
          InternalName: name,
          TypeAsString: (TYPE_IN_SCHEMA.exec(schema) || [null, '?'])[1],
          // Required sent true and reading back false is what this knob is
          // for: the create still answers 200.
          Required: REQUIRED_IN_SCHEMA.test(schema) && CONFIG.requiredReadsBack,
          // Served explicitly, because SharePoint serves the whole entity and
          // a property it withheld must not read as the column carrying none.
          DefaultValue: null,
          ValidationFormula: null,
          // What an earlier run left this column as. CLEANUP ships false, so
          // the probe reuses whatever carries that name.
          ...(CONFIG.leftoverShape[name] || {}),
        });
        return jsonResponse(200, { Id: `field-${name}` });
      }

      const one = ITEM.exec(rest);
      if (one) {
        const row = items.get(Number(one[1]));
        if (!row) return jsonResponse(404, { error: 'no such item' });
        if (verb !== 'MERGE' && CONFIG.emptyItemRead) return emptyResponse(200);
        if (verb !== 'MERGE') return jsonResponse(200, shapeOf(row));
        for (const key of Object.keys(sent)) {
          if (key === '__metadata') continue;
          if (!WRITABLE.includes(key)) {
            return jsonResponse(500, { error: { message: { value:
              `The field or property '${key}' does not exist.` } } });
          }
        }
        // Keyed on the value written, so a test can fail the one write it is
        // about without touching the negative control's own MERGE.
        if (CONFIG.writeFailsFor[String(sent.ColChoice ?? sent.ColLookupId)]) {
          return jsonResponse(
            CONFIG.writeFailsFor[String(sent.ColChoice ?? sent.ColLookupId)],
            { error: 'the metadata write failed' });
        }
        if (CONFIG.ruleEnforces && listFormula !== '' && sent.ColChoice === 'InvalidValue') {
          return jsonResponse(500, { error: { message: { value:
            'ColChoice cannot be InvalidValue' } } });
        }
        Object.assign(row, sent);
        return jsonResponse(204, {});
      }
      if (rest.startsWith('/items')) {
        if (method === 'POST') {
          const id = nextItem;
          nextItem += 1;
          items.set(id, { Id: id, ...sent });
          return jsonResponse(201, { Id: id });
        }
        const wanted = FILTERED.exec(rest);
        const rows = [...items.values()].filter(
          (row) => !wanted || row.FileLeafRef === wanted[1]);
        return jsonResponse(200, { value: rows.map(shapeOf) });
      }

      if (verb === 'MERGE') {
        if (CONFIG.ruleLands) listFormula = String(sent.ValidationFormula);
        return jsonResponse(204, {});
      }
      return jsonResponse(200, {
        Id: `list-${named[1]}`, Title: named[1], ValidationFormula: listFormula,
      });
    };
""")

#: Nothing has gone wrong: the required column comes back required, the list
#: rule stores, and it refuses a violating metadata write.
_LIB_COLS_HEALTHY: dict[str, Any] = {
    "requiredReadsBack": True,
    "ruleLands": True,
    "ruleEnforces": True,
    # The two ways a write can fail for a reason that is not the server
    # rejecting what was sent.
    "uploadStatus": None,
    "writeFailsFor": {},
    "leftoverShape": {},
    # A request can answer 2xx and carry nothing a probe can read: an empty
    # body on an item read, and a file served without the property asked for.
    "emptyItemRead": False,
    "filePropsRead": "served",
}


def _run_lib_cols_probe(**changes: Any) -> dict[str, dict[str, str]]:
    config = json.loads(json.dumps(_LIB_COLS_HEALTHY))
    config.update(changes)
    script = (
        _LIB_COLS_HARNESS.replace("__CONFIG__", json.dumps(config))
        + "\n"
        + _fixture_probe_js(LIB_COLS_PROBE)
    )
    return _fixture_rows(_run(script))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_library_columns_run_measures_the_required_column_and_the_rule() -> None:
    """The control for the two below."""
    rows = _run_lib_cols_probe()

    assert rows["library.column.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows["library.column.choice-column-on-library"]["outcome"] == "PASS"
    assert rows["library.column.calculated-column-on-library"]["outcome"] == "PASS"
    assert rows["library.column.required-column-enforced-on-upload"]["outcome"] == (
        "UPLOAD ACCEPTED WITHOUT CHECKOUT"
    )
    assert rows["library.validation.validation-formula-on-library"]["outcome"] == "ENFORCED"
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_upload_past_a_column_that_is_not_required_enforces_nothing() -> None:
    """`Required` was never read back off the column.

    An accepted upload then reports how a required column behaves during
    upload, measured on a library that has no required column.
    """
    rows = _run_lib_cols_probe(requiredReadsBack=False)

    required = rows["library.column.required-column-enforced-on-upload"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert required["state"] == "void"
    assert "Required=false" in required["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_rule_that_never_stored_is_not_a_rule_that_is_inert() -> None:
    """The headline of this file, and the exact finding a dropped formula
    manufactures.

    With no rule on the library the violating write is accepted, which the row
    recorded as INERT: a list ValidationFormula does not enforce against
    library item updates. That is a claim about SharePoint, published off a
    MERGE whose result was never read back.
    """
    rows = _run_lib_cols_probe(ruleLands=False)

    validation = rows["library.validation.validation-formula-on-library"]
    assert validation["outcome"] == "NOT ESTABLISHED", (
        "the formula was accepted and dropped, and an accepted violating write "
        "on a library carrying no rule says nothing about whether a rule enforces"
    )
    assert validation["state"] == "void"
    assert "no such rule" in validation["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_item_that_did_not_read_back_is_not_a_column_behaving_differently() -> None:
    """FAIL on these three rows says a column does NOT behave the same on a
    library, which is the sentence this file is read for.

    Each was recorded off `(read.ok && read.body) ? read.body.X : null`, so a
    2xx with nothing in it produced null and the row settled on a value this
    run never saw.
    """
    rows = _run_lib_cols_probe(emptyItemRead=True)

    for row in ("library.column.choice-column-on-library",
                "library.column.lookup-column-on-library",
                "library.column.calculated-column-on-library"):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert "did not read back" in rows[row]["evidence"], row
    # The rows that turn on a write rather than a read still answer.
    assert rows["library.column.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows["library.validation.validation-formula-on-library"]["outcome"] == "ENFORCED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "changes", "marker"),
    [
        ("the read answered 2xx with no payload", {"filePropsRead": "empty"},
         "did not read back"),
        ("the payload withheld the property", {"filePropsRead": "withheld"},
         "no CheckOutType property"),
    ],
)
def test_a_file_whose_properties_were_not_read_left_nothing_behind_to_report(
    why: str, changes: dict[str, Any], marker: str,
) -> None:
    """Both outcome heads name what the upload left behind, and CheckOutType
    is the only thing that separates them.

    A read that did not answer produced null, `null === 0` is false, and the
    row settled as UPLOAD ACCEPTED WITHOUT CHECKOUT off a property nobody had.
    """
    rows = _run_lib_cols_probe(**changes)

    required = rows["library.column.required-column-enforced-on-upload"]
    assert required["outcome"] == "NOT ESTABLISHED", why
    assert marker in required["evidence"]


# --------------------------------------------------------------------------
# The refusal boundary, across all five probes: a request that failed for a
# reason `isRefusal` excludes settles nothing.
#
# `_probe_harness.js.j2` defines that boundary and says why: 401 and 403 are
# about who is asking and 408 and 429 about the moment, so a row that reads
# either as the server rejecting what was sent certifies a surface on the
# strength of a throttle, and everything it gates is then read as evidence.
# --------------------------------------------------------------------------

#: Statuses the harness excludes from `isRefusal`, exercised as a pair: one
#: about the caller and one about the moment.
_NOT_A_REFUSAL = (403, 429)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("status", _NOT_A_REFUSAL)
def test_a_person_operand_control_that_was_not_refused_holds_nothing(status: int) -> None:
    """The control decided on `!negative.ok`, so a throttled create read as
    SharePoint rejecting a Person operand.

    That is the one row saying this probe can tell acceptance from refusal.
    Held on a 429, every accepted create below it stays settled while nothing
    established that a refusal is visible to the run at all.
    """
    rows = _run_calc_choice_probe(personControlStatus=status)

    control = rows["formula.calc.control-person-operand-refused"]
    assert control["outcome"] == "NOT ESTABLISHED", (
        f"HTTP {status} is not the server rejecting the formula"
    )
    assert control["state"] != "settled"
    for row in _CALC_CHOICE_ACCEPTANCE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("status", _NOT_A_REFUSAL)
def test_a_create_that_was_not_refused_is_not_recorded_as_refused(status: int) -> None:
    """`recordCreate` published its caller's refusal head on any non-2xx.

    For `formula.choice.calc-column-accepted` that reads FAIL, and for
    `formula.calc.lookup-operand-accepted` it reads REFUSED, which is a claim
    about what SharePoint rejects.
    """
    rows = _run_calc_choice_probe(refuse=["ProbeRoute"], refuseStatus=status)

    accepted = rows["formula.choice.calc-column-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert str(status) in accepted["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("status", _NOT_A_REFUSAL)
def test_a_validation_store_write_that_failed_is_not_a_store_that_refuses(
    status: int,
) -> None:
    """The four person-and-lookup store rows recorded REFUSED on any non-2xx.

    Those rows are what `analysis/conditions.py` would be corrected against: a
    REFUSED read off a throttle would tighten a rule SharePoint never rejected.
    """
    rows = _run_calc_choice_probe(fieldMergeStatus=status)

    for row in ("formula.validation.person-operand",
                "formula.validation.lookup-operand",
                "expression.client-validation.person-operand",
                "expression.client-validation.lookup-operand"):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert rows[row]["state"] != "settled", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("status", _NOT_A_REFUSAL)
def test_a_folder_create_that_was_not_refused_settles_no_state(status: int) -> None:
    """`addFolder` recorded FAIL for any non-refusal, which settles the row.

    On the bare-library control that is the whole run: the operator reads that
    a bare library did not take a folder, from a request the server never
    considered.
    """
    rows = _run_folder_schema_probe(addFailsFor={"dbmlsp bare state": status})

    control = rows["library.folder.control-add-on-bare-library"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert control["state"] != "settled"
    for row in _FOLDER_SCHEMA_GATED_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_restore_that_was_not_refused_is_not_a_restore_that_failed() -> None:
    """The restore row is half of the only shape a fix for this can take."""
    rows = _run_folder_schema_probe(restoreMergeStatus=429)

    restored = rows["library.folder.restore-list-validation-after-folders"]
    assert restored["outcome"] == "NOT ESTABLISHED"
    assert restored["state"] != "settled"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throttled_create_does_not_report_a_restored_guard_as_absent() -> None:
    """The last control asks whether the restored formula refuses a NEW folder.

    Recorded FAIL on a throttle, it reads "the restored formula is not in
    force and the three rows above are about an unguarded library", which is
    the loudest wrong sentence this probe can print.
    """
    rows = _run_folder_schema_probe(addFailsFor={"dbmlsp after restore state": 429})

    control = rows["library.folder.control-restored-validation-refuses-a-folder"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "not in force" not in control["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_five_creates_that_were_never_answered_do_not_read_as_all_refused() -> None:
    """The race row counted saves and called everything else a refusal.

    ALL REFUSED is the finding that the [today] default DOES race the rule and
    loses, which is what three shipped solutions would be changed over.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, itemCreateStatus=429)

    race = rows["formula.validation.today-default-races-modified-rule-rest"]
    assert race["outcome"] == "NOT ESTABLISHED"
    assert "neither saved nor were refused" in race["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("status", _NOT_A_REFUSAL)
def test_a_form_endpoint_that_failed_is_not_a_form_endpoint_that_refused(
    status: int,
) -> None:
    """The same question through the endpoint the form itself posts to."""
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, formEndpointStatus=status)

    endpoint = rows["formula.validation.today-default-races-modified-rule-form-endpoint"]
    assert endpoint["outcome"] == "NOT ESTABLISHED"
    assert endpoint["state"] != "settled"


#: The list rule form-validation writes, as the store reads it back: bracket
#: stripping is what SharePoint did to it, measured 2026-09-02.
_STORED_LIST_RULE = "=OR(ISBLANK(DM),DM<=Modified)"

#: The same, for the three-column rule save-instant-paths writes.
_STORED_THREE_COLUMN_RULE = (
    "=AND(OR(ISBLANK(DM),DM<=Modified),OR(ISBLANK(TR),TR<=Modified),"
    "OR(ISBLANK(WR),WR<=Modified))"
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throttled_merge_does_not_void_a_three_column_rule_already_stored() -> None:
    """The same boundary on the probe whose rule gates eight rows.

    Deciding on the MERGE's status, a 429 over a list that already carries the
    rule voided every row measured under it, including the six a person is
    sent away to perform by hand.
    """
    rows = _run_scratch_probe(
        SCRATCH_SAVE_PATHS_PROBE, listMergeStatus=429,
        initialListFormula=_STORED_THREE_COLUMN_RULE,
    )

    stored = rows["formula.validation.fixture-three-column-modified-rule-stored"]
    assert stored["outcome"] == "PASS"
    assert "429" in stored["evidence"]
    assert not [row for row in rows.values() if row["state"] == "void"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throttled_merge_over_a_rule_already_stored_is_not_a_missing_rule() -> None:
    """The row asks whether the rule IS stored, so the readback decides it.

    Short-circuited on the write's status, a 429 over a list that already
    carries the rule voided four form steps a person could have performed.
    """
    rows = _run_scratch_probe(
        SCRATCH_FORM_PROBE, listMergeStatus=429, initialListFormula=_STORED_LIST_RULE,
    )

    stored = rows["formula.validation.fixture-modified-list-rule-stored"]
    assert stored["outcome"] == "PASS"
    assert "429" in stored["evidence"]
    for row in _FORM_DM_ROWS:
        assert rows[row]["outcome"] == "MANUAL", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_upload_that_failed_is_not_an_upload_a_required_column_refused() -> None:
    """UPLOAD REFUSED is the finding that a required column blocks a file."""
    rows = _run_lib_cols_probe(uploadStatus=429)

    required = rows["library.column.required-column-enforced-on-upload"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert "was refused" not in required["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("row", "value"),
    [
        ("library.column.choice-column-on-library", "Beta"),
        ("library.column.lookup-column-on-library", "1"),
    ],
)
def test_a_metadata_write_that_failed_does_not_settle_the_column_row(
    row: str, value: str,
) -> None:
    """FAIL here reads as the column behaving differently on a library, which
    is the whole question the file exists to answer."""
    rows = _run_lib_cols_probe(writeFailsFor={value: 429})

    assert rows[row]["outcome"] == "NOT ESTABLISHED"
    assert rows[row]["state"] != "settled"


# --------------------------------------------------------------------------
# The reused fixture's full shape: a property the measurement depends on that
# a name match does not check.
# --------------------------------------------------------------------------


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_guard_column_carrying_a_default_is_not_the_blank_required_state() -> None:
    """The state is "REQUIRED with NO default", which is what the shipped
    family declares for two of its five library columns.

    CLEANUP ships false, so a column an earlier run left behind is the normal
    path. Carrying a default, it may be handing that default to every folder
    created under it, and the row then reports on a required column that is
    never blank.
    """
    rows = _run_folder_schema_probe(preexistingGuard={
        "Title": "dbmlspGuard", "TypeAsString": "Text",
        "Required": True, "ValidationFormula": None, "DefaultValue": "ok",
    })

    required = rows["library.folder.add-with-required-column"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert 'DefaultValue="ok"' in required["evidence"]
    # The two states built on that column are not entered either, and the four
    # rows about the fix are about a library that never reached the state.
    assert rows["library.folder.add-with-column-validation"]["outcome"] == "NOT ESTABLISHED"
    assert rows["library.folder.add-with-list-validation"]["outcome"] == "NOT ESTABLISHED"
    for row in _FOLDER_SCHEMA_RESTORE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_column_carrying_its_own_rule_does_not_answer_the_race() -> None:
    """The race rows read a refusal as the LIST rule firing.

    A column rule an earlier run left on TR refuses the same create for a
    reason this probe never asked about, so ALL REFUSED would be a finding
    about the wrong rule.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, fields={
        "DM": dict(_SCRATCH_DATE),
        "T": dict(_SCRATCH_TODAY),
        "TR": {**_SCRATCH_DATE, "DefaultValue": "[today]",
               "ValidationFormula": "=TR<=Modified"},
        "WR": {**_SCRATCH_DATE, "DisplayFormat": 1, "DefaultValue": "[today]"},
    })

    fixture = rows["formula.validation.fixture-default-columns"]
    assert fixture["outcome"] == "FAIL"
    assert "ValidationFormula" in fixture["evidence"]
    for row in _SAVE_PATHS_RACE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_guard_column_carrying_a_rule_is_the_next_states_state() -> None:
    """The same predicate, one property short again.

    State 3 puts a ValidationFormula on that column, and CLEANUP ships false,
    so the second run meets the formula the first one left. The state-2 create
    then runs in the state the NEXT row names, and a refusal under it is
    recorded against requiredness.
    """
    rows = _run_folder_schema_probe(preexistingGuard={
        "Title": "dbmlspGuard", "TypeAsString": "Text", "Required": True,
        "DefaultValue": None, "ValidationFormula": '=[dbmlspGuard]="ok"',
    })

    required = rows["library.folder.add-with-required-column"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert 'ValidationFormula="=[dbmlspGuard]=\\"ok\\""' in required["evidence"]
    assert rows["library.folder.add-with-column-validation"]["outcome"] == "NOT ESTABLISHED"
    assert rows["library.folder.add-with-list-validation"]["outcome"] == "NOT ESTABLISHED"
    for row in _FOLDER_SCHEMA_RESTORE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("withheld", ["DefaultValue", "ValidationFormula"])
def test_a_guard_property_the_site_withheld_is_not_a_column_carrying_none(
    withheld: str,
) -> None:
    """`!back.body.X` is true for a property that is unset AND for one the
    payload never carried, and only the first says the column is blank.

    Read as a false value, a payload that stopped serving either property
    would put every state back to being taken from the create's status.
    """
    guard = {
        "Title": "dbmlspGuard", "TypeAsString": "Text", "Required": True,
        "DefaultValue": None, "ValidationFormula": None,
    }
    del guard[withheld]
    rows = _run_folder_schema_probe(preexistingGuard=guard)

    required = rows["library.folder.add-with-required-column"]
    assert required["outcome"] == "NOT ESTABLISHED"
    assert f"{withheld}=undefined" in required["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_folder_an_earlier_run_left_is_not_this_state_taking_one() -> None:
    """MEASURED 2026-09-13, `library.folder.add-under-existing-folder-name`: a
    create on a name a folder already holds answers HTTP 200 and returns that
    folder.

    CLEANUP ships false and the names are one per state, so on the second run
    every state meets its own folder, the create is a no-op, the read back
    finds the old folder and each row reads PASS. The states this probe exists
    to tell apart would all accept a folder, including the one the live deploy
    was refused in.
    """
    rows = _run_folder_schema_probe(preexistingFolders=["dbmlsp bare state"])

    control = rows["library.folder.control-add-on-bare-library"]
    assert control["outcome"] == "NOT ESTABLISHED"
    assert "was not read as free" in control["evidence"]
    for row in _FOLDER_SCHEMA_GATED_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("row", "leftover"),
    [
        ("library.folder.add-using-path-under-validation", "dbmlsp using path state"),
        ("library.folder.add-as-list-item-under-validation", "dbmlsp list item state"),
        ("library.folder.control-restored-validation-refuses-a-folder",
         "dbmlsp after restore state"),
    ],
)
def test_a_leftover_name_answers_none_of_the_other_folder_spellings(
    row: str, leftover: str,
) -> None:
    """The same no-op reaches the two other spellings and the restore control.

    On the control it is the worse direction: a create that is really a no-op
    over last run's folder is ACCEPTED, and the row then reports that the
    restored formula is not in force and the three rows above it are about an
    unguarded library.
    """
    rows = _run_folder_schema_probe(preexistingFolders=[leftover])

    assert rows[row]["outcome"] == "NOT ESTABLISHED"
    assert "was not read as free" in rows[row]["evidence"]
    # Only that one row. The states before it were still measured.
    assert rows["library.folder.control-add-on-bare-library"]["outcome"] == "PASS"
    assert rows["library.folder.add-with-list-validation"]["outcome"] == "REFUSED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_date_column_left_required_does_not_answer_the_race_either() -> None:
    """Requiredness refuses the same bare create the column rule would.

    The race rows count five creates and read a refusal as the LIST rule
    firing, so a TR an earlier run left required makes ALL REFUSED a finding
    about the wrong constraint.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, fields={
        "DM": dict(_SCRATCH_DATE),
        "T": dict(_SCRATCH_TODAY),
        "TR": {**_SCRATCH_DATE, "DefaultValue": "[today]", "Required": True},
        "WR": {**_SCRATCH_DATE, "DisplayFormat": 1, "DefaultValue": "[today]"},
    })

    fixture = rows["formula.validation.fixture-default-columns"]
    assert fixture["outcome"] == "FAIL"
    assert "Required=true" in fixture["evidence"]
    for row in _SAVE_PATHS_RACE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_race_column_property_the_site_withheld_is_not_one_it_carries_none_of() -> None:
    """The same absent-is-not-false boundary on the shared scratch list.

    A payload that stops serving Required reads, under a bare falsy test, as a
    column carrying no requiredness, which is the reading the guard exists to
    refuse.
    """
    carried = {**_SCRATCH_DATE, "DefaultValue": "[today]"}
    del carried["Required"]
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, fields={
        "DM": dict(_SCRATCH_DATE),
        "T": dict(_SCRATCH_TODAY),
        "TR": carried,
        "WR": {**_SCRATCH_DATE, "DisplayFormat": 1, "DefaultValue": "[today]"},
    })

    fixture = rows["formula.validation.fixture-default-columns"]
    assert fixture["outcome"] == "FAIL"
    assert "Required=undefined" in fixture["evidence"]
    for row in _SAVE_PATHS_RACE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_of_another_type_under_the_race_name_answers_nothing() -> None:
    """The race is about a DATE column's dynamic default.

    A Text column of that name can hold the literal string "[today]", and the
    row would read as the fixture being in place.
    """
    rows = _run_scratch_probe(SCRATCH_SAVE_PATHS_PROBE, fields={
        "DM": dict(_SCRATCH_DATE),
        "T": dict(_SCRATCH_TODAY),
        "TR": {**_SCRATCH_DATE, "TypeAsString": "Text", "DefaultValue": "[today]"},
        "WR": {**_SCRATCH_DATE, "DisplayFormat": 1, "DefaultValue": "[today]"},
    })

    fixture = rows["formula.validation.fixture-default-columns"]
    assert fixture["outcome"] == "FAIL"
    assert "TypeAsString=Text" in fixture["evidence"]
    for row in _SAVE_PATHS_RACE_ROWS:
        assert rows[row]["state"] == "void", row


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "shape"),
    [
        ("required", {"Required": True}),
        ("carrying a default", {"DefaultValue": "2026-01-01T00:00:00Z"}),
    ],
)
def test_a_dt_column_of_another_shape_voids_the_new_form_steps(
    why: str, shape: dict[str, Any],
) -> None:
    """Every New step goes through a form that shows DT, and four of the six
    leave it blank.

    A DT an earlier run left required refuses those saves, and a DT carrying a
    default fills them, both for a reason no step asked about. The refusal is
    then written up against the rule the step names.
    """
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, fields={
        "DM": dict(_SCRATCH_DATE), "T": dict(_SCRATCH_TODAY),
        "DT": {**_SCRATCH_DATE, **shape},
    })

    assert rows["formula.validation.fixture-dt-column"]["outcome"] == "FAIL", why
    for row in (*_FORM_DT_ROWS, "formula.validation.form-new-today-under-modified-rule",
                "formula.validation.form-new-tomorrow-under-modified-rule"):
        assert rows[row]["state"] == "void", row
    # The two Edit steps open an item that already carries a DT.
    assert rows["formula.validation.form-edit-today-under-modified-rule"]["outcome"] == "MANUAL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_bare_item_an_earlier_run_left_is_not_what_today_resolves_to_now() -> None:
    """The =TODAY() default fires once, at create.

    The row is reused so repeated setup runs do not accumulate rows, and its T
    then holds what TODAY() resolved to on the day that run made it. Recorded
    as PASS beside a site-local midnight computed from now, a row a day old is
    the transcript that says TODAY() resolves to yesterday.
    """
    rows = _run_scratch_probe(SCRATCH_FORM_PROBE, bareItemLeft=4)

    resolved = rows["formula.datetime.today-function-default-value"]
    assert resolved["outcome"] == "NOT ESTABLISHED"
    assert "left by an earlier setup run" in resolved["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("why", "shape"),
    [
        ("a default fills the column the upload leaves out", {"DefaultValue": "draft"}),
        ("a column rule refuses the upload for its own reason",
         {"ValidationFormula": "=[ColRequired]<>\"\""}),
    ],
)
def test_an_upload_past_a_column_that_is_never_blank_enforces_nothing(
    why: str, shape: dict[str, Any],
) -> None:
    """The upload sends no metadata, so the question is whether a column that
    would be BLANK on the file that lands blocks it.

    A ColRequired an earlier run left carrying a default is never blank, and
    UPLOAD ACCEPTED then reports that a required column does not block a file.
    """
    rows = _run_lib_cols_probe(leftoverShape={"ColRequired": shape})

    required = rows["library.column.required-column-enforced-on-upload"]
    assert required["outcome"] == "NOT ESTABLISHED", why
    assert required["state"] == "void"
    assert "no blank required column" in required["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_text_column_under_the_choice_name_is_not_a_choice_column() -> None:
    """Each row is about a column of a PARTICULAR type.

    A ColChoice an earlier run left as Text takes the string "Beta" and reads
    it back, so the row records that a choice column behaves the same on a
    document library, measured on a column that is not one.
    """
    rows = _run_lib_cols_probe(leftoverShape={"ColChoice": {"TypeAsString": "Text"}})

    choice = rows["library.column.choice-column-on-library"]
    assert choice["state"] == "void"
    assert "TypeAsString=Text" in choice["evidence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_person_column_left_as_text_is_not_the_negative_control_s_operand() -> None:
    """N1 is the row that says this probe can tell acceptance from refusal.

    A ProbeOwner an earlier run left as Text takes a calculated formula, and
    the control then records that a Person operand was ACCEPTED: the probe
    declares itself insensitive, voids every acceptance, and the sentence
    quoted against this project's own denylist is about a Text column.
    """
    rows = _run_calc_choice_probe(
        leftoverShape={"ProbeOwner": {"TypeAsString": "Text"}})

    for row in _CALC_CHOICE_ACCEPTANCE_ROWS:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
        assert rows[row]["evidence"] == "the run did not reach this question", row
    assert rows["formula.calc.control-person-operand-refused"]["outcome"] == "NOT ESTABLISHED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_operand_under_another_display_title_stops_the_calc_choice_run() -> None:
    """D1 references its operands by DISPLAY title, which is the shape the
    build actually emits.

    A column re-titled since the run that made it answers "the formula refers
    to a column that does not exist", and the row records that SharePoint
    refuses a spaced display name.
    """
    rows = _run_calc_choice_probe(
        leftoverShape={"SpacedFrom": {"Title": "Spaced From Tier (retired)"}})

    accepted = rows["formula.choice.spaced-display-name-accepted"]
    assert accepted["outcome"] == "NOT ESTABLISHED"
    assert accepted["evidence"] == "the run did not reach this question"
