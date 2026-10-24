"""Execute the shared transport against stubbed responses, one fact per test.

Each fact runs twice: behind the partials rendered on their own, so a case
states its responses, its clock and its expected waits and nothing else, and
behind the whole write prelude a downstream paste-in script wraps its body
in. `setTimeout` records each delay and fires at once, so a run that waits
five minutes takes milliseconds.

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
from dbml_sharepoint.jsrest import wrap
from dbml_sharepoint.templating import script_env

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

type Source = Literal["partials", "prelude"]
#: Every fact in the classes below holds behind both sources.
BOTH_SOURCES = pytest.mark.parametrize("source", ["partials", "prelude"])

NOW = datetime(2026, 1, 15, 9, 30, tzinfo=UTC)
PAST_DATE = email.utils.format_datetime(NOW - timedelta(seconds=30), usegmt=True)


@dataclass(frozen=True)
class Stub:
    """One scripted answer; `hold` keeps it back until the body calls `release()`.

    `body_fails` answers the status and then fails reading the body, as a dropped stream does.
    """

    status: int
    body: JsonValue = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""
    hold: bool = False
    body_fails: bool = False


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


def contextinfo(digest: str, **lifetime: JsonValue) -> Stub:
    """A contextinfo answer issuing `digest`, with any lifetime fields beside it."""
    return Stub(200, {"d": {"GetContextWebInformation": {"FormDigestValue": digest, **lifetime}}})

#: One GET through the transport, its final status reported.
FETCH_ONCE = """
    const r = await fetchWithRetry(apiUrl('web'), {});
    report.status = r.status;
"""

_HARNESS = """
const STUBS = JSON.parse(STUBS_JSON);
const events = [];
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
    text: async () => {
      if (stub.body_fails) throw new TypeError('Failed to fetch');
      return JSON.stringify(stub.body);
    },
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

#: What the prelude defines itself, so only the partials source needs it.
_PARTIALS_SHIMS = """
const log = (level, message) => events.push({ level, message });
const apiUrl = (s) => '/sites/T/_api/' + s;
"""

#: The prelude logs through console.log; its `[LEVEL] message` lines become events.
_PRELUDE_SHIMS = """
const realLog = console.log;
console.log = (line) => {
  const m = /^\\[(\\w+)\\] ([\\s\\S]*)$/.exec(String(line));
  if (m) events.push({ level: m[1], message: m[2] }); else realLog(line);
};
globalThis.window = {
  location: { origin: 'https://t.example', pathname: '/sites/T/SitePages/Home.aspx' },
};
globalThis.location = window.location;
globalThis._spPageContextInfo = { webServerRelativeUrl: '/sites/T', userLoginName: 'u' };
"""

#: One POST carrying digest `d`, resolving to its status; declared in the transport's scope.
_WRITE = """
const write = async (d) => (await fetchWithRetry(
  apiUrl('web/lists'), { method: 'POST', headers: spHeaders(d), body: '{}' })).status;
"""


def _run_facts(
    body: str,
    *responses: Stub,
    now: datetime = NOW,
    source: Source = "partials",
    partials: Sequence[str] = ("_http.js.j2", "_http_write.js.j2", "_digest_cached.js.j2"),
) -> FactsRun:
    """Run `body` behind the transport, answering its requests from `responses` in order."""
    stubs = (
        f"const STUBS_JSON = {json.dumps(json.dumps([asdict(s) for s in responses]))};\n"
        f"const NOW_MS = {int(now.timestamp() * 1000)};\n"
    )
    guarded = (
        f"{_WRITE}\ntry {{\n{body}\n}} "
        "catch (err) { report.error = String((err && err.message) || err); }\n"
    )
    if source == "prelude":
        out = "realLog('__OUT__' + JSON.stringify({ events, calls, waits, ...report }));\n"
        script = f"{stubs}{_HARNESS}\n{_PRELUDE_SHIMS}\n{wrap(guarded + out, writes=True)}"
    else:
        env = script_env()
        transport = "\n".join(env.get_template(name).render() for name in partials)
        script = (
            f"{stubs}(async () => {{\n{_HARNESS}\n{_PARTIALS_SHIMS}\n{transport}\n{guarded}"
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


@BOTH_SOURCES
class TestRetryAfter:
    def test_a_numeric_retry_after_is_waited_then_the_request_repeats(self, source: Source) -> None:
        result = _run_facts(FETCH_ONCE, Stub(429, headers={"Retry-After": "7"}), OK, source=source)
        assert result["status"] == 200
        assert len(result["calls"]) == 2
        assert result["waits"] == [7000]
        assert messages(result) == ["Throttled, HTTP 429; every lane waits 7s, retry 1/8."]

    def test_an_http_date_retry_after_is_waited_until(self, source: Source) -> None:
        when = email.utils.format_datetime(NOW + timedelta(seconds=120), usegmt=True)
        assert _run_facts(
            FETCH_ONCE, Stub(503, headers={"Retry-After": when}), OK, source=source,
        )["waits"] == [120_000]

    def test_a_retry_after_over_the_ceiling_stops_rather_than_retrying_early(
        self, source: Source,
    ) -> None:
        result = _run_facts(
            FETCH_ONCE, Stub(429, headers={"Retry-After": "86400"}), OK, source=source,
        )
        assert result["status"] == 429
        assert len(result["calls"]) == 1
        assert result["waits"] == []
        assert messages(result) == ["Retry-After asks 86400s, over the 300s ceiling; stopping."]

    def test_a_retry_after_at_the_ceiling_is_waited(self, source: Source) -> None:
        assert _run_facts(
            FETCH_ONCE, Stub(429, headers={"Retry-After": "300"}), OK, source=source,
        )["waits"] == [300_000]

    @pytest.mark.parametrize("header", ["0", "soon", "-5", PAST_DATE, ""],
                             ids=["zero", "unreadable", "negative", "past-date", "empty"])
    def test_a_retry_after_that_asks_for_nothing_falls_back_to_the_backoff(
        self, source: Source, header: str,
    ) -> None:
        assert _run_facts(
            FETCH_ONCE, Stub(429, headers={"Retry-After": header}), OK, source=source,
        )["waits"] == [1000]

    def test_the_backoff_doubles_to_its_sixty_second_ceiling(self, source: Source) -> None:
        result = _run_facts(FETCH_ONCE, *[Stub(429)] * 8, OK, source=source)
        assert result["waits"] == [1000, 2000, 4000, 8000, 16000, 32000, 60000, 60000]

    def test_an_exhausted_retry_hands_the_last_response_to_the_caller(self, source: Source) -> None:
        result = _run_facts(FETCH_ONCE, *[Stub(429)] * 9, source=source)
        assert result["status"] == 429
        assert len(result["calls"]) == 9
        assert len(result["waits"]) == 8


NO_INFO = "HTTP 200 carried no GetContextWebInformation"
FAILED = "contextinfo (request digest) failed: "


@BOTH_SOURCES
class TestDigest:
    def test_the_digest_is_posted_and_read_from_the_guarded_chain(self, source: Source) -> None:
        result = _run_facts("report.digest = await getDigest();", contextinfo("abc"), source=source)
        assert result["digest"] == "abc"
        assert result["calls"] == [
            {"url": "/sites/T/_api/contextinfo", "method": "POST", "digest": None},
        ]

    @pytest.mark.parametrize(("answer", "detail"), [
        (Stub(200, {"d": {}}), NO_INFO),
        (Stub(200, {"d": {"GetContextWebInformation": []}}), NO_INFO),
        (Stub(200, {"d": {"GetContextWebInformation": {"FormDigestValue": " "}}}),
         "HTTP 200 carried no usable FormDigestValue"),
        (Stub(403, {"error": {"message": {"value": "Access denied"}}}), "HTTP 403 Access denied"),
    ])
    def test_a_contextinfo_answer_without_a_digest_names_what_is_missing(
        self, source: Source, answer: Stub, detail: str,
    ) -> None:
        assert _run_facts("await getDigest();", answer, source=source)["error"] == FAILED + detail

    def test_a_cross_web_contextinfo_goes_through_the_same_parse(self, source: Source) -> None:
        body = "await getContextWebInformation('https://t.example/sites/C/_api/contextinfo');"
        result = _run_facts(body, Stub(200, {"d": {}}), source=source)
        assert result["calls"][0]["url"] == "https://t.example/sites/C/_api/contextinfo"
        assert result["error"] == FAILED + NO_INFO


SECURITY: JsonValue = {
    "error": {"message": {"value": "The security validation for this page is invalid."}},
}
DENIED: JsonValue = {"error": {"message": {"value": "Access denied."}}}
LIFETIME: dict[str, JsonValue] = {"FormDigestTimeoutSeconds": 1800}


def WRITE_WITH(digest: str) -> str:  # noqa: N802 - reads as the constant it extends
    """One write carrying the digest expression `digest`, its status reported."""
    return f"report.status = await write({digest});\n"


#: One write carrying this web's cached digest.
WRITE = WRITE_WITH("await getDigest()")


def contextinfo_calls(result: FactsRun) -> int:
    """How many contextinfo requests the run made."""
    return sum(c["url"].endswith("/contextinfo") for c in result["calls"] if c["url"])


def write_digests(result: FactsRun) -> list[str | None]:
    """The digest each write carried, in the order sent."""
    return [c["digest"] for c in result["calls"] if not (c["url"] or "").endswith("/contextinfo")]


@BOTH_SOURCES
class TestDigestCache:
    def test_writes_within_the_lifetime_share_one_digest(self, source: Source) -> None:
        result = _run_facts(WRITE * 3, contextinfo("d1", **LIFETIME), OK, OK, OK, source=source)
        assert contextinfo_calls(result) == 1

    @pytest.mark.parametrize(("elapsed", "fetches"), [(1739, 1), (1740, 2), (1800, 2)])
    def test_the_digest_is_refetched_a_minute_before_it_expires(
        self, source: Source, elapsed: int, fetches: int,
    ) -> None:
        body = f"await getDigest();\nclock += {elapsed * 1000};\nawait getDigest();"
        result = _run_facts(
            body, contextinfo("d1", **LIFETIME), contextinfo("d2", **LIFETIME), source=source,
        )
        assert contextinfo_calls(result) == fetches

    def test_a_security_validation_403_retries_once_with_a_fresh_digest(
        self, source: Source,
    ) -> None:
        result = _run_facts(
            WRITE, contextinfo("d1", **LIFETIME), Stub(403, SECURITY),
            contextinfo("d2", **LIFETIME), OK, source=source,
        )
        assert result["status"] == 200
        assert write_digests(result) == ["d1", "d2"]
        assert messages(result) == [
            "HTTP 403 security validation on a write; retrying once with a fresh request digest.",
        ]

    def test_a_second_403_is_the_callers_to_report(self, source: Source) -> None:
        result = _run_facts(
            WRITE, contextinfo("d1", **LIFETIME), Stub(403, SECURITY),
            contextinfo("d2", **LIFETIME), Stub(403, SECURITY), source=source,
        )
        assert result["status"] == 403
        assert contextinfo_calls(result) == 2

    def test_a_403_that_is_not_a_digest_refusal_is_handed_back(self, source: Source) -> None:
        result = _run_facts(WRITE, contextinfo("d1", **LIFETIME), Stub(403, DENIED), source=source)
        assert result["status"] == 403
        assert contextinfo_calls(result) == 1

    def test_a_403_on_a_write_carrying_another_webs_digest_is_not_retried(
        self, source: Source,
    ) -> None:
        result = _run_facts(
            "await getDigest();" + WRITE_WITH("'central-digest'"),
            contextinfo("d1", **LIFETIME), Stub(403, SECURITY), source=source,
        )
        assert result["status"] == 403
        assert len(result["calls"]) == 2

    def test_a_403_on_a_read_is_not_retried(self, source: Source) -> None:
        result = _run_facts(
            "await getDigest();" + FETCH_ONCE, contextinfo("d1", **LIFETIME), Stub(403, SECURITY),
            source=source,
        )
        assert result["status"] == 403
        assert len(result["calls"]) == 2

    def test_a_403_whose_body_cannot_be_read_is_handed_back(self, source: Source) -> None:
        result = _run_facts(
            WRITE, contextinfo("d1", **LIFETIME), Stub(403, body_fails=True), source=source,
        )
        assert result["status"] == 403
        assert write_digests(result) == ["d1"]

    @pytest.mark.parametrize(("refresh", "detail"), [
        (Stub(403, DENIED), "HTTP 403 Access denied."),
        (Stub(200, {"d": {}}), NO_INFO),
    ], ids=["refused", "no-digest"])
    def test_a_failed_refresh_hands_back_the_original_403(
        self, source: Source, refresh: Stub, detail: str,
    ) -> None:
        result = _run_facts(
            WRITE, contextinfo("d1", **LIFETIME), Stub(403, SECURITY), refresh, source=source,
        )
        assert "error" not in result
        assert result["status"] == 403
        assert write_digests(result) == ["d1"]
        assert messages(result) == [
            f"Request digest refresh failed ({FAILED}{detail}); handing back the HTTP 403.",
        ]

    def test_four_lanes_refused_together_share_one_refresh(self, source: Source) -> None:
        body = """
  const d = await getDigest();
  const lanes = [0, 1, 2, 3].map(() => write(d));
  await heldCount(4);
  release();
  report.statuses = await Promise.all(lanes);
"""
        result = _run_facts(
            body, contextinfo("d1", **LIFETIME), *[Stub(403, SECURITY, hold=True)] * 4,
            contextinfo("d2", **LIFETIME), OK, OK, OK, OK, source=source,
        )
        assert result["statuses"] == [200, 200, 200, 200]
        assert contextinfo_calls(result) == 2
        assert write_digests(result) == ["d1"] * 4 + ["d2"] * 4


def test_the_parse_needs_only_sp_error_beside_it() -> None:
    body = "report.digest = (await readContextWebInformation(await fetch('x'))).FormDigestValue"
    result = _run_facts(
        body, contextinfo("abc"), partials=("_sp_error.js.j2", "_contextinfo.js.j2"),
    )
    assert result["digest"] == "abc"


def test_a_script_without_the_digest_partial_hands_a_403_back() -> None:
    result = _run_facts(FETCH_ONCE, Stub(403, SECURITY), partials=("_http.js.j2",))
    assert result["status"] == 403
    assert len(result["calls"]) == 1
