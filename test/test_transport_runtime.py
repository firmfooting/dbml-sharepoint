# test/test_transport_runtime.py
"""Execute the shared HTTP transport against a mock SharePoint.

`fetchWithRetry` is the one place every request in every emitted script goes
through -- `test_emitted_practices.py` pins that -- so what it treats as a
throttle decides whether a run waits or dies.

MEASURED 2026-09-04 on a live nine-list deploy: the run aborted at Phase 4.2
with `GET /_layouts/15/Throttle.htm 406`. Microsoft Learn, "Avoid getting
throttled or blocked in SharePoint Online", says why:

    For requests that a user performs directly in the browser, SharePoint
    Online redirects you to the throttling information page, and the requests
    fail. For requests that an application makes, including Microsoft Graph,
    CSOM, or REST calls, SharePoint Online returns HTTP status code 429 ...
    or 503 ...

These scripts are pasted into a browser console, so SharePoint answers them
the first way. The transport was written for the second.

Node is required; the tests skip without it rather than failing.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.assessgen import generate_assess_js
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

THROTTLE_URL = "https://example.sharepoint.com/_layouts/15/Throttle.htm"
GOOD_URL = "https://example.sharepoint.com/sites/test/_api/web/lists"


def _transport() -> str:
    """The transport block lifted whole out of the emitted script.

    Lifted rather than copied: a copy keeps passing after the real one
    changes, which is the failure mode this whole file exists to catch.
    """
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="x.dbml",
        source_mtime="2026-09-04T00:00:00Z",
        generated_at="2026-09-04T00:00:00Z",
        resolved=resolve(schema, bundle.mapping),
    )
    start = js.index("  const DEBUG = false;")
    rest = js[start:]
    end = rest.index("async function fetchWithRetry")
    tail = rest[end:]
    return rest[: end + tail.index("\n  }") + len("\n  }")]


_HARNESS = textwrap.dedent("""
    const events = [];
    const log = (level, message) => events.push({ level, message });
    // Real timers, short: the ordering assertions below depend on the gate
    // actually suspending, not on a stub that resolves immediately.
    const RESPONSES = JSON.parse(RESPONSES_JSON);
    const calls = [];
    const inits = [];
    globalThis.fetch = async (url, init) => {
      calls.push(String(url));
      inits.push(init === undefined ? null : init);
      const queue = RESPONSES[String(url)];
      const next = queue.length > 1 ? queue.shift() : queue[0];
      return {
        ok: next.status < 400,
        status: next.status,
        // The post-redirect URL. SharePoint redirects a throttled browser to
        // its throttling page, so this is what names the throttle.
        url: next.url || String(url),
        redirected: Boolean(next.url && next.url !== String(url)),
        headers: { get: (name) => (next.headers || {})[name] ?? null },
        json: async () => ({}),
        text: async () => '',
      };
    };
""")


def _run_transport(
    responses: dict[str, list[dict[str, Any]]], body: str,
) -> dict[str, Any]:
    script = (
        f"const RESPONSES_JSON = {json.dumps(json.dumps(responses))};\n"
        "(async () => {\n"
        f"{_HARNESS}\n{_transport()}\n"
        f"{body}\n"
        "})().then((r) => console.log('__OUT__' + JSON.stringify(r)));\n"
    )
    output = _run(script)
    line = next((x for x in output.splitlines() if x.startswith("__OUT__")), None)
    assert line is not None, f"the transport never returned:\n{output[-3000:]}"
    result: dict[str, Any] = json.loads(line.removeprefix("__OUT__"))
    return result


def test_a_redirect_to_the_throttling_page_is_a_throttle() -> None:
    """The regression. Before this, the run aborted on a wait.

    The status is 406 only because the request asked for JSON and the
    throttling page is HTML, so the STATUS is a property of our own Accept
    header rather than of the throttle. The URL is what names it.
    """
    result = _run_transport(
        {GOOD_URL: [
            {"status": 406, "url": THROTTLE_URL},
            {"status": 200},
        ]},
        f"""
        const r = await fetchWithRetry({json.dumps(GOOD_URL)}, {{}}, 3);
        return {{ status: r.status, calls, throttleLogs:
          events.filter((e) => /throttl/i.test(e.message)).length }};
        """,
    )
    assert result["status"] == 200, (
        "the throttling-page redirect was returned to the caller as a failure "
        "instead of being waited out"
    )
    assert len(result["calls"]) == 2, "the request was not retried"
    assert result["throttleLogs"] >= 1, "the wait was not reported to the operator"


def test_a_406_that_is_not_the_throttling_page_is_returned_to_the_caller() -> None:
    """Only the throttling page earns a retry.

    A 406 from a real endpoint means the caller asked for something the
    server cannot produce, and retrying it changes nothing. Keying on the
    status rather than the URL would have turned every one of those into
    five pointless requests and a long wait.
    """
    result = _run_transport(
        {GOOD_URL: [{"status": 406}]},
        f"""
        const r = await fetchWithRetry({json.dumps(GOOD_URL)}, {{}}, 3);
        return {{ status: r.status, calls }};
        """,
    )
    assert result["status"] == 406
    assert len(result["calls"]) == 1, "a plain 406 was retried"


def test_a_throttle_pauses_every_lane_not_just_the_one_that_saw_it() -> None:
    """The deploy runs four lanes through this one helper.

    Microsoft Learn: "Throttled requests count towards usage limits, so
    failure to honor Retry-After may result in more throttling", and
    "reduce concurrency after throttling". Four lanes each backing off
    independently keep spending quota against a tenant that is already
    refusing, and then resume together.
    """
    other = GOOD_URL + "/other"
    result = _run_transport(
        {
            GOOD_URL: [{"status": 406, "url": THROTTLE_URL}, {"status": 200}],
            other: [{"status": 200}],
        },
        f"""
        // Lane A throttles first and opens the gate; lane B starts once it has.
        const a = fetchWithRetry({json.dumps(GOOD_URL)}, {{}}, 3);
        await new Promise((res) => setTimeout(res, 50));
        const b = fetchWithRetry({json.dumps(other)}, {{}}, 3);
        await Promise.all([a, b]);
        return {{ calls }};
        """,
    )
    calls = result["calls"]
    assert calls.count(GOOD_URL) == 2, "lane A did not retry"
    assert calls.index(other) > calls.index(GOOD_URL), "lane B never ran"
    assert calls[-1] == other, (
        f"lane B fired during lane A's backoff: {calls}. A throttle has to "
        "hold every lane, or the run keeps spending quota while refused."
    )
def test_every_request_defeats_the_browser_cache() -> None:
    """A by-title read can otherwise answer with a list that no longer exists.

    MEASURED 2026-09-13, revision c9c55b1f, `transport.cache.id-select-after-recreate`
    and `transport.cache.shape-select-after-recreate` in
    list-identity-cache-probe.js: after a list is hard-deleted and another
    created under the same title, which is what a rollback followed by a
    redeploy does, BOTH by-title reads answered with the dead list's Id, under
    `Cache-Control: private, max-age=0` and `ETag: "1"`. The enumeration and a
    unique-parameter read both answered the live one, and the same run with
    the browser's cache disabled answered fresh on every row, which is what
    puts it in the browser rather than in SharePoint.

    This is a safety defect rather than an inconvenience. Two reads that go
    stale together AGREE with each other, so the ownership guard passes while
    naming an object the run never saw, which is the one thing that guard
    exists to prevent. It reached us the loud way instead: the ownership
    survey and the filter-editor check ask by different URLs, so they are
    separate cache entries filled at different times, and Phase 3.1 reported
    the list changing identity mid-phase.

    `cache: 'no-store'` because it is the only one of the three that neither
    reads the cache nor writes it, so a read cannot be answered from an entry
    and cannot leave one for a later read either. All three were measured
    fresh (`transport.cache.remedy-no-store`, `remedy-no-cache-header`,
    `remedy-reload`), so this picks the strongest rather than the only one
    that works.
    """
    result = _run_transport(
        {GOOD_URL: [{"status": 200}]},
        f"""
        await fetchWithRetry({json.dumps(GOOD_URL)}, {{}});
        await fetchWithRetry({json.dumps(GOOD_URL)}, {{ method: 'POST', body: 'x' }});
        await fetchWithRetry({json.dumps(GOOD_URL)});
        return {{ inits }};
        """,
    )
    assert [init["cache"] for init in result["inits"]] == ["no-store"] * 3, (
        "a request went out able to be answered from the browser cache"
    )
    # The caller's own options survive it: no-store is added, never swapped in.
    assert result["inits"][1]["method"] == "POST"
    assert result["inits"][1]["body"] == "x"


def test_a_caller_cannot_opt_back_into_the_cache() -> None:
    """The directive is applied after the caller's options, not before.

    Spread the other way round, one caller passing `cache` for its own reason
    would silently re-enable the stale read for that request, and nothing
    downstream could see it.
    """
    result = _run_transport(
        {GOOD_URL: [{"status": 200}]},
        f"""
        await fetchWithRetry({json.dumps(GOOD_URL)}, {{ cache: 'force-cache' }});
        return {{ inits }};
        """,
    )
    assert result["inits"][0]["cache"] == "no-store"


# === The read-only script's own batch transport =============================
#
# assess.js includes `_http_batch_read.js.j2` where the write-capable scripts
# include `_http_batch.js.j2`, so the class below is the same text in a
# DIFFERENT scope: no `spHeaders`, no `_http_write.js.j2` at all. A name it
# resolved there and does not resolve here is exactly the #454 failure, a
# ReferenceError on the one branch whose job is to explain a refusal, and
# `node --check` cannot see it because the branch has to RUN. So these lift
# the transport out of the emitted assessment rather than out of the deploy.

ASSESS_ORIGIN = "https://example.sharepoint.com"
ASSESS_WEB = "/sites/test"
ASSESS_BATCH_URL = f"{ASSESS_WEB}/_api/$batch"


def _assess_transport() -> str:
    """The transport block lifted whole out of the emitted assess script.

    Sliced from the first line of `_http.js.j2` to the first line of
    `_assess_body.js.j2`, so it is what the read-only script actually carries:
    `_http` + `_digest_cached` + `_http_batch_read`, and nothing that writes.
    """
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    js = generate_assess_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url=f"{ASSESS_ORIGIN}{ASSESS_WEB}",
        site_role="default",
        source_dbml="x.dbml",
        generated_at="2026-09-14T00:00:00Z",
        resolved=resolve(schema, bundle.mapping),
    )
    start = js.index("  const DEBUG = false;")
    end = js.index("  // The whole assessment, taking its collaborators")
    block = js[start:end]
    assert "class BatchReader {" in block, (
        "the assessment no longer carries BatchReader between its transport "
        "and its body; this test is measuring the wrong text"
    )
    assert "class BatchWriter" not in block, (
        "the read-only assessment gained the write half of the batch transport"
    )
    return block


_ASSESS_HARNESS = textwrap.dedent("""
    const events = [];
    const log = (level, message) => events.push({ level, message });
    // The site guard is not in the lifted slice, so the origin it would have
    // proved is stubbed, and apiUrl is passed to the reader rather than read
    // off the scope the guard defines.
    globalThis.window = { location: { origin: ORIGIN } };
    const ANSWER = JSON.parse(ANSWER_JSON);
    const sent = [];
    globalThis.fetch = async (url, init) => {
      sent.push({
        url: String(url),
        method: (init || {}).method || 'GET',
        body: String((init || {}).body || ''),
      });
      return {
        ok: ANSWER.status < 400,
        status: ANSWER.status,
        url: String(url),
        headers: { get: () => null },
        json: async () => ({}),
        text: async () => ANSWER.text,
      };
    };
    const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
    // Its own name: the slice already declares getDigest, and the reader takes
    // one as a constructor argument precisely so a caller can supply this.
    const stubDigest = async () => 'digest-value';
""")


def _query_answer(parts: list[tuple[int, str]]) -> str:
    """A $batch response body carrying one query part's status and payload."""
    body = "".join(
        f"--batchresponse_1\r\nContent-Type: application/http\r\n\r\n"
        f"HTTP/1.1 {status} Whatever\r\n"
        f"Content-Type: application/json;odata=verbose\r\n\r\n"
        f"{payload}\r\n"
        for status, payload in parts
    )
    return body + "--batchresponse_1--\r\n"


def _run_assess_reader(answer: dict[str, Any], body: str) -> dict[str, Any]:
    """Run `body` against the assessment's own transport and one scripted answer."""
    script = (
        f"const ORIGIN = {json.dumps(ASSESS_ORIGIN)};\n"
        f"const WEB = {json.dumps(ASSESS_WEB)};\n"
        f"const ANSWER_JSON = {json.dumps(json.dumps(answer))};\n"
        "(async () => {\n"
        f"{_ASSESS_HARNESS}\n{_assess_transport()}\n"
        f"{body}\n"
        "})().then((r) => console.log('__OUT__' + JSON.stringify(r)));\n"
    )
    output = _run(script)
    line = next((x for x in output.splitlines() if x.startswith("__OUT__")), None)
    assert line is not None, f"the assessment reader never returned:\n{output[-3000:]}"
    result: dict[str, Any] = json.loads(line.removeprefix("__OUT__"))
    return result


#: Two reads queued, the refusal reported rather than thrown at the runner.
_TWO_READS = """
    const reader = new BatchReader({
      getDigest: stubDigest, fetchWithRetry, apiUrl, log,
    });
    await reader.add("web/lists/getbytitle('APP_Project')?$select=Title");
    await reader.add("web/lists/getbytitle('APP_Task')?$select=Title");
    try {
      return { threw: false, shapes: await reader.done(), sent };
    } catch (err) {
      return { threw: true, message: err.message, batchFailure: err.batchFailure === true,
               throttled: err.throttled, answered: err.answered, refused: err.refused,
               errors: events.filter((e) => e.level === 'ERROR').length, sent };
    }
"""


def test_a_refused_part_is_not_an_answer_for_the_assessment() -> None:
    """The outer request is 200 and `response.ok` is true.

    Measured 2026-09-04, 1000 operations came back HTTP 200 with 363 of them
    failed inside the body, so the envelope's status says nothing about the
    parts. A 404 on one part is a list that was NOT read, and an assessment
    that took the 200 for an answer would record findings about a list it
    never saw.
    """
    result = _run_assess_reader(
        {"status": 200, "text": _query_answer([
            (200, '{"d":{"Title":"APP_Project"}}'),
            (404, '{"error":{"message":"not found"}}'),
        ])},
        _TWO_READS,
    )
    assert result["threw"], "a 404 part answered as a clean read"
    assert result["batchFailure"] is True
    assert (result["answered"], result["refused"]) == (1, 1)
    assert result["throttled"] is False, "a 404 is a refusal, not a throttle"
    assert "200, 404" in result["message"], result["message"]
    assert result["errors"] >= 1, (
        "the refusal never reached the transcript the operator pastes back"
    )


def test_a_part_count_the_assessment_cannot_pair_is_refused() -> None:
    """Position is the only join between a part and the path that asked for it.

    A short answer is unpairable rather than partial: taking the first N would
    silently file the second list's answer against the first list's findings,
    which is worse than reporting neither.
    """
    result = _run_assess_reader(
        {"status": 200, "text": _query_answer([(200, '{"d":{"Title":"APP_Project"}}')])},
        _TWO_READS,
    )
    assert result["threw"], "an envelope one part short answered as a clean read"
    assert "cannot be accounted for" in result["message"], result["message"]
    assert result["refused"] == 2, (
        "a read the envelope could not account for was reported as partly done"
    )


def test_a_refused_batch_request_is_reported_with_its_status() -> None:
    """The branch that only runs when the request itself fails.

    Nothing else in the suite reaches it, and it is the branch that has to
    name the failure: an assessment that logged nothing here would leave the
    operator a degraded verdict with no reason in the transcript.
    """
    result = _run_assess_reader(
        {"status": 500, "text": '{"error":{"message":{"value":"Batch is broken"}}}'},
        _TWO_READS,
    )
    assert result["threw"], "a refused $batch request answered as a clean read"
    assert "HTTP 500" in result["message"], result["message"]
    assert "Batch is broken" in result["message"], (
        f"the refusal reached the operator without SharePoint's reason: "
        f"{result['message']}"
    )
    assert result["errors"] >= 1, "the refusal never reached the transcript"
    assert len(result["sent"]) == 1, (
        f"a refused $batch was retried: {result['sent']}. A 500 is not a "
        f"throttle and retrying it spends quota against a tenant already "
        f"refusing."
    )
