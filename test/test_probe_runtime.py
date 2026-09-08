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
