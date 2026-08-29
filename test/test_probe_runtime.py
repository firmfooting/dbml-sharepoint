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
