"""Execute the shared transport partials against stubbed responses, one fact per test.

The partials are rendered on their own rather than lifted from an emitted
script, so a case states its responses, its clock and its expected waits and
nothing else. `setTimeout` records each delay and fires at once, so a run that
waits five minutes takes milliseconds.

Node is required; the tests skip without it rather than failing.
"""

import email.utils
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, NotRequired, TypedDict, cast

import pytest
from _node import NODE
from _node import run_node as _run

from dbml_sharepoint.jsonvalue import JsonValue
from dbml_sharepoint.templating import script_env

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

NOW = datetime(2026, 1, 15, 9, 30, tzinfo=UTC)
PAST_DATE = email.utils.format_datetime(NOW - timedelta(seconds=30), usegmt=True)


@dataclass(frozen=True)
class Stub:
    """One scripted answer; `hold` keeps it back until the body calls `release()`."""

    status: int
    body: JsonValue = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""
    hold: bool = False


class FactsRun(TypedDict):
    """What one run saw: its log, its requests, each delay it waited, and the body's report."""

    events: list[dict[str, str]]
    calls: list[dict[str, str | None]]
    waits: list[int]
    status: NotRequired[int]
    statuses: NotRequired[list[int]]
    digest: NotRequired[str]
    error: NotRequired[str]


OK = Stub(200, {"d": {}})

#: One GET through the transport, its final status reported.
FETCH_ONCE = """
    const r = await fetchWithRetry(apiUrl('web'), {});
    report.status = r.status;
"""

_HARNESS = """
const STUBS = JSON.parse(STUBS_JSON);
const events = [];
const log = (level, message) => events.push({ level, message });
const apiUrl = (s) => '/sites/T/_api/' + s;
const calls = [];
const waits = [];
const report = {};
let clock = NOW_MS;
Date.now = () => clock;
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (fn, ms, ...args) => {
  waits.push(ms);
  return realSetTimeout(fn, 0, ...args);
};
let released = false;
const held = [];
const heldWatchers = [];
const noticeHeld = () => {
  for (const w of heldWatchers.filter((x) => held.length >= x.n)) {
    heldWatchers.splice(heldWatchers.indexOf(w), 1);
    w.resolve();
  }
};
const release = () => {
  released = true;
  held.splice(0).forEach((resolve) => resolve());
};
const heldCount = (n) => new Promise((resolve) => {
  heldWatchers.push({ n, resolve });
  noticeHeld();
});
const respond = (stub, url) => {
  const headers = Object.fromEntries(
    Object.entries(stub.headers).map(([k, v]) => [k.toLowerCase(), v]));
  const make = () => ({
    ok: stub.status >= 200 && stub.status < 300,
    status: stub.status,
    url: stub.url || url,
    headers: { get: (name) => headers[String(name).toLowerCase()] ?? null },
    json: async () => JSON.parse(JSON.stringify(stub.body)),
    text: async () => JSON.stringify(stub.body),
    clone: () => make(),
  });
  return make();
};
globalThis.fetch = async (url, init) => {
  const headers = (init && init.headers) || {};
  calls.push({
    url: String(url),
    method: (init && init.method) || 'GET',
    digest: headers['X-RequestDigest'] ?? null,
  });
  const stub = STUBS.length
    ? STUBS.shift() : { status: 200, body: { d: {} }, headers: {}, url: '', hold: false };
  if (stub.hold && !released) {
    await new Promise((resolve) => { held.push(resolve); noticeHeld(); });
  }
  return respond(stub, String(url));
};
"""


def _run_facts(
    body: str,
    *responses: Stub,
    now: datetime = NOW,
    source: Literal["partials", "prelude"] = "partials",
    partials: Sequence[str] = ("_http.js.j2", "_http_write.js.j2", "_digest_cached.js.j2"),
) -> FactsRun:
    """Run `body` behind the transport, answering its requests from `responses` in order."""
    if source == "prelude":
        raise NotImplementedError("the prelude source is not wired yet")
    env = script_env()
    transport = "\n".join(env.get_template(name).render() for name in partials)
    script = (
        f"const STUBS_JSON = {json.dumps(json.dumps([asdict(s) for s in responses]))};\n"
        f"const NOW_MS = {int(now.timestamp() * 1000)};\n"
        "(async () => {\n"
        f"{_HARNESS}\n{transport}\n"
        "try {\n"
        f"{body}\n"
        "} catch (err) { report.error = String((err && err.message) || err); }\n"
        "return { events, calls, waits, ...report };\n"
        "})().then((r) => console.log('__OUT__' + JSON.stringify(r)));\n"
    )
    output = _run(script)
    line = next((x for x in output.splitlines() if x.startswith("__OUT__")), None)
    assert line is not None, f"the run never returned:\n{output[-3000:]}"
    return cast("FactsRun", json.loads(line.removeprefix("__OUT__")))


def messages(result: FactsRun) -> list[str]:
    """Each logged message, without the prelude's identity line, so both sources compare equal."""
    return [e["message"] for e in result["events"] if not e["message"].startswith("Running as ")]


class TestRetryAfter:
    def test_a_numeric_retry_after_is_waited_then_the_request_repeats(self) -> None:
        result = _run_facts(FETCH_ONCE, Stub(429, headers={"Retry-After": "7"}), OK)
        assert result["status"] == 200
        assert len(result["calls"]) == 2
        assert result["waits"] == [7000]
        assert messages(result) == ["Throttled, HTTP 429; every lane waits 7s, retry 1/8."]

    def test_an_http_date_retry_after_is_waited_until(self) -> None:
        when = email.utils.format_datetime(NOW + timedelta(seconds=120), usegmt=True)
        assert _run_facts(
            FETCH_ONCE, Stub(503, headers={"Retry-After": when}), OK,
        )["waits"] == [120_000]

    def test_a_retry_after_over_the_ceiling_stops_rather_than_retrying_early(self) -> None:
        result = _run_facts(FETCH_ONCE, Stub(429, headers={"Retry-After": "86400"}), OK)
        assert result["status"] == 429
        assert len(result["calls"]) == 1
        assert result["waits"] == []
        assert messages(result) == ["Retry-After asks 86400s, over the 300s ceiling; stopping."]

    def test_a_retry_after_at_the_ceiling_is_waited(self) -> None:
        assert _run_facts(
            FETCH_ONCE, Stub(429, headers={"Retry-After": "300"}), OK,
        )["waits"] == [300_000]

    @pytest.mark.parametrize("header", ["0", "soon", "-5", PAST_DATE, ""],
                             ids=["zero", "unreadable", "negative", "past-date", "empty"])
    def test_a_retry_after_that_asks_for_nothing_falls_back_to_the_backoff(
        self, header: str,
    ) -> None:
        assert _run_facts(
            FETCH_ONCE, Stub(429, headers={"Retry-After": header}), OK,
        )["waits"] == [1000]

    def test_the_backoff_doubles_to_its_sixty_second_ceiling(self) -> None:
        result = _run_facts(FETCH_ONCE, *[Stub(429)] * 8, OK)
        assert result["waits"] == [1000, 2000, 4000, 8000, 16000, 32000, 60000, 60000]

    def test_an_exhausted_retry_hands_the_last_response_to_the_caller(self) -> None:
        result = _run_facts(FETCH_ONCE, *[Stub(429)] * 9)
        assert result["status"] == 429
        assert len(result["calls"]) == 9
        assert len(result["waits"]) == 8
