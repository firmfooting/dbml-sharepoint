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
