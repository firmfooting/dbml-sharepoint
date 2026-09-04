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
    js = generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="x.dbml",
        source_mtime="2026-09-04T00:00:00Z",
        generated_at="2026-09-04T00:00:00Z",
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
    globalThis.fetch = async (url) => {
      calls.push(String(url));
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
