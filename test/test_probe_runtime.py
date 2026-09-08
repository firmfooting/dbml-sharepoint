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
