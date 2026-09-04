# test/test_batch_writer_runtime.py
"""Execute the emitted BatchWriter and BatchReader against a mock SharePoint.

`BatchWriter` is the transport primitive the write-capable scripts use to
collapse many single writes into one OData `$batch` request, and two of its
properties cannot be seen anywhere else in the stack:

- the outer `$batch` request answers HTTP 200 even when ChangeSet parts fail,
  so a plain `fetchWithRetry` on it reports success while dropping writes;
- the tenant's ceiling is body SIZE, not operation count. MEASURED by
  `test/manual/throttle-batch-probe.js` (#404): 750 operations landed clean
  and 1000 came back 200 with 637 parts at 201 and 363 at 500.

`BatchReader` is the read companion, and its one property that nothing else
in the stack can show is the same one inverted: an envelope of top-level query
parts answers HTTP 200 while individual parts 404, so a phase that verifies N
objects through it and does not read the part statuses reports verification it
never did. It is also the half that must NOT be trusted to a plausible
encoding: query parts sit outside any ChangeSet and the outer request still
needs `X-RequestDigest` even though every part is a read (measured live, 2026-
09-04: the identical envelope without one came back HTTP 403).

Both classes are LIFTED out of the emitted deploy script rather than copied,
for the reason `test_transport_runtime.py` gives: a copy keeps passing after
the real one changes.

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

ORIGIN = "https://example.sharepoint.com"
WEB = "/sites/test"
BATCH_URL = f"{WEB}/_api/$batch"
# Long on purpose. A real form digest is several hundred characters and it is
# repeated on every ChangeSet part, so it, not the payload, is what fills a
# batch. A short stub would make the budget test measure the wrong thing.
DIGEST = "0x" + "A1B2C3D4" * 48 + ",04 Sep 2026 00:00:00 -0000"

BUDGET = 200 * 1024
# The clean point the probe measured. Every emitted request must stay under it.
MEASURED_CLEAN_OPS = 750


def _transport() -> str:
    """The transport stack lifted whole out of the emitted deploy script.

    Sliced from the first line of `_http.js.j2` to the first line of
    `_digest_cached.js.j2`, so it is `_http` + `_http_write` + `_http_batch`
    verbatim and nothing else. `getDigest` is deliberately outside the slice:
    the BatchWriter takes it as a constructor argument, and the tests supply
    their own.
    """
    js = generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url=f"{ORIGIN}{WEB}",
        site_role="default",
        source_dbml="x.dbml",
        source_mtime="2026-09-04T00:00:00Z",
        generated_at="2026-09-04T00:00:00Z",
    )
    start = js.index("  const DEBUG = false;")
    end = js.index("  let cachedDigest = null;")
    block = js[start:end]
    for name in ("class BatchWriter {", "class BatchReader {"):
        assert name in block, (
            f"`{name}` is no longer emitted between the transport partial and "
            "the cached digest; this test is measuring the wrong text"
        )
    return block


_HARNESS = textwrap.dedent("""
    const events = [];
    const log = (level, message) => events.push({ level, message });
    // The site guard is not in the lifted slice, so the origin it would have
    // proved is stubbed. BatchWriter reads it to build absolute operation
    // URLs, which is what the $batch protocol requires in a request line.
    globalThis.window = { location: { origin: ORIGIN } };
    const RESPONSES = JSON.parse(RESPONSES_JSON);
    const requests = [];
    // `echo: true` answers with one 201 status line per operation the request
    // actually carried. Tests about how a body is SPLIT cannot pin the part
    // count in advance, and a fixed count would fail the writer's own
    // accounting check instead of measuring the split.
    const echoed = (opts) => {
      const ops = String((opts && opts.body) || '')
        .split('Content-Type: application/http').length - 1;
      return Array.from({ length: ops },
        () => '--r\\r\\nHTTP/1.1 201 Created\\r\\n\\r\\n{}\\r\\n').join('') + '--r--\\r\\n';
    };
    // `readEcho: true` is the same trick for query parts, except that a read's
    // PAYLOAD is what the caller wants back, so each answer names the field id
    // its own request line asked for. A test about how a read is SPLIT cannot
    // know the split in advance; answering from the request is what lets it
    // assert the reader kept its results in order ACROSS requests.
    const readEchoed = (opts) => {
      const asked = String((opts && opts.body) || '').split('\\r\\n')
        .filter((line) => line.startsWith('GET '))
        .map((line) => (line.match(/getbyid\\('([^']+)'\\)/) || [])[1]);
      return asked.map((id) =>
        '--r\\r\\nContent-Type: application/http\\r\\n\\r\\nHTTP/1.1 200 OK\\r\\n'
        + 'Content-Type: application/json;odata=verbose\\r\\n\\r\\n'
        + JSON.stringify({ d: { Id: id } }) + '\\r\\n').join('') + '--r--\\r\\n';
    };
    globalThis.fetch = async (url, opts) => {
      requests.push({ url: String(url), opts });
      const queue = RESPONSES[String(url)];
      const next = queue.length > 1 ? queue.shift() : queue[0];
      return {
        ok: next.status < 400,
        status: next.status,
        url: next.url || String(url),
        headers: { get: (name) => (next.headers || {})[name] ?? null },
        json: async () => ({}),
        text: async () => {
          if (next.echo) return echoed(opts);
          if (next.readEcho) return readEchoed(opts);
          return next.text || '';
        },
      };
    };
    // A digest is fetched by the caller in the real script and handed in, so
    // this stands in for _digest_cached.js.j2's cached getDigest.
    const getDigest = async () => DIGEST;
    const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
""")


def _run_batch(
    responses: dict[str, list[dict[str, Any]]], body: str,
) -> dict[str, Any]:
    script = (
        f"const RESPONSES_JSON = {json.dumps(json.dumps(responses))};\n"
        f"const ORIGIN = {json.dumps(ORIGIN)};\n"
        f"const WEB = {json.dumps(WEB)};\n"
        f"const DIGEST = {json.dumps(DIGEST)};\n"
        "(async () => {\n"
        f"{_HARNESS}\n{_transport()}\n"
        f"{body}\n"
        "})().then((r) => console.log('__OUT__' + JSON.stringify(r)));\n"
    )
    output = _run(script)
    line = next((x for x in output.splitlines() if x.startswith("__OUT__")), None)
    assert line is not None, f"the BatchWriter never returned:\n{output[-4000:]}"
    result: dict[str, Any] = json.loads(line.removeprefix("__OUT__"))
    return result


def _multipart_response(statuses: list[int]) -> str:
    """A $batch response body carrying one status line per operation."""
    parts = "".join(
        f"--batchresponse_1\r\nContent-Type: application/http\r\n\r\n"
        f"HTTP/1.1 {status} Whatever\r\nContent-Type: application/json\r\n\r\n"
        f'{{"d":{{"Id":{index + 1}}}}}\r\n'
        for index, status in enumerate(statuses)
    )
    return parts + "--batchresponse_1--\r\n"


def _writer(*, transport: str = "fetchWithRetry", options: str = "") -> str:
    return (
        "const writer = new BatchWriter({ getDigest, apiUrl, log, "
        f"fetchWithRetry: {transport}{options} }});"
    )


def test_a_batch_body_encodes_every_operation() -> None:
    """The envelope the probe proved, port for port.

    One outer boundary, one ChangeSet inside it, one application/http part per
    operation carrying a full request line with an ABSOLUTE url, the
    verbose-OData write headers, and the digest. The digest rides on the outer
    request as well; that double spelling is what landed on a live tenant and
    it is not up for tidying.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _multipart_response([201, 201, 201])}]},
        f"""
        {_writer()}
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'A' }});
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'B' }});
        await writer.add('POST', "web/lists/getbytitle('Risk')/items({{2}})", {{ Title: 'C' }},
                         {{ 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }});
        const outcome = await writer.done();
        return {{ outcome, sent: requests.length, url: requests[0].url,
                  opts: {{ method: requests[0].opts.method,
                           headers: requests[0].opts.headers }},
                  body: requests[0].opts.body }};
        """,
    )
    assert result["sent"] == 1, "three operations did not go out as one request"
    assert result["url"] == BATCH_URL
    assert result["outcome"] == {"requests": 1, "landed": 3, "statuses": [201, 201, 201]}

    headers = result["opts"]["headers"]
    assert result["opts"]["method"] == "POST"
    assert headers["X-RequestDigest"] == DIGEST, "the outer request carries no digest"
    outer = headers["Content-Type"].removeprefix("multipart/mixed; boundary=")
    assert outer.startswith("batch_") and outer != headers["Content-Type"]
    assert "Accept" not in headers, (
        "an Accept header turns the throttling-page redirect into a 406 that "
        "only its URL identifies (#401); the probe omits it deliberately"
    )

    body = result["body"]
    inner = body.split(f"--{outer}\r\nContent-Type: multipart/mixed; boundary=")[1]
    inner = inner.split("\r\n")[0]
    assert inner.startswith("changeset_")
    assert body.count("Content-Type: application/http\r\n") == 3
    assert body.count(f"X-RequestDigest: {DIGEST}\r\n") == 3, (
        "the digest is not on every ChangeSet part"
    )
    assert body.count("Accept: application/json;odata=verbose\r\n") == 3
    assert body.count("Content-Type: application/json;odata=verbose\r\n") == 3
    assert (
        f"POST {ORIGIN}{WEB}/_api/web/lists/getbytitle('Risk')/items HTTP/1.1\r\n" in body
    ), "an operation's request line is not an absolute url"
    assert '{"Title":"A"}\r\n' in body and '{"Title":"C"}\r\n' in body
    assert "IF-MATCH: *\r\n" in body, "extraHeaders did not reach the ChangeSet part"
    assert f"MERGE {ORIGIN}{WEB}/_api/web/lists/getbytitle('Risk')/items(" in body, (
        "a tunnelled MERGE did not become the part's request-line verb, so it would POST"
    )
    assert "X-HTTP-Method" not in body, (
        "X-HTTP-Method survived into the part; Learn's batch example and PnPjs "
        "both put the verb in the request line and send no override header"
    )
    assert body.endswith(f"--{inner}--\r\n--{outer}--\r\n")


def test_a_part_with_no_body_carries_no_payload() -> None:
    """A function invocation is a POST with no body, batched or not.

    `addroleassignment` and friends take their arguments in the URL. The
    single write sends no body at all, so neither does the part that replaces
    it: PnPjs writes a part's body only when the request has one.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _multipart_response([200])}]},
        f"""
        {_writer()}
        await writer.add(
          'POST',
          "web/lists/getbytitle('Risk')/roleassignments/addroleassignment(principalid=7,roleDefId=1073741826)",
        );
        await writer.done();
        return {{ body: requests[0].opts.body }};
        """,
    )
    body = result["body"]
    assert (
        f"POST {ORIGIN}{WEB}/_api/web/lists/getbytitle('Risk')"
        "/roleassignments/addroleassignment(principalid=7,roleDefId=1073741826)"
        " HTTP/1.1\r\n" in body
    )
    assert "{}" not in body, "a bodyless operation invented a payload"
    assert body.count(f"X-RequestDigest: {DIGEST}\r\n") == 1, (
        "the part carries no digest"
    )


def test_a_metadata_body_goes_out_under_a_verbose_part() -> None:
    """`__metadata` and the part's content type have to agree.

    Every field write the deploy batches carries a `__metadata` annotation,
    because that is what the single write it replaces carries. The annotation
    only exists in verbose OData, so a part declaring nometadata is refused
    HTTP 400: "The property '__metadata' does not exist on type
    'SP.FieldText'" (live finding 2026-09-04, measured one candidate spelling
    per $batch with each verdict read back off the field). A whole live deploy
    of Index, Default and seal writes was lost to that mismatch, and nothing
    between here and the tenant can see it, so the pairing is pinned.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _multipart_response([204])}]},
        f"""
        {_writer()}
        await writer.add(
          'POST',
          "web/lists(guid'11111111-1111-1111-1111-111111111111')"
          + "/fields(guid'22222222-2222-2222-2222-222222222222')",
          {{ __metadata: {{ type: 'SP.Field' }}, Indexed: true }},
          {{ 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }},
        );
        await writer.done();
        return {{ body: requests[0].opts.body }};
        """,
    )
    body = result["body"]
    assert '"__metadata":{"type":"SP.Field"}' in body, (
        "the caller's __metadata annotation did not survive into the part"
    )
    assert "Content-Type: application/json;odata=verbose\r\n" in body, (
        "a __metadata body went out under a part that does not declare verbose "
        "OData, which SharePoint refuses HTTP 400 for an unknown property"
    )
    assert "odata=nometadata" not in body


def test_the_body_budget_flushes_before_the_measured_ceiling() -> None:
    """The default budget, against a body the size of a real one.

    Budgeting operations rather than bytes is what this exists to refuse. The
    probe found 750 clean and 1000 partial, and 637 of that 1000 landing is
    what says the ceiling is size-shaped: a count-shaped ceiling would have
    refused the whole request.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "echo": True}]},
        f"""
        {_writer()}
        for (let i = 0; i < 900; i++) {{
          await writer.add('POST', "web/lists/getbytitle('Risk')/items",
                           {{ Title: `row ${{i}}`, Notes: 'x'.repeat(200) }});
        }}
        await writer.done();
        return {{ sizes: requests.map((r) => r.opts.body.length),
                  ops: requests.map((r) => (r.opts.body.match(
                    /Content-Type: application\\/http/g) || []).length) }};
        """,
    )
    assert len(result["sizes"]) > 1, "900 operations went out as one request"
    assert max(result["sizes"]) <= BUDGET, (
        f"a $batch body of {max(result['sizes'])} bytes passed the "
        f"{BUDGET}-byte budget"
    )
    assert max(result["ops"]) < MEASURED_CLEAN_OPS, (
        f"a request carried {max(result['ops'])} operations, at or past the "
        f"{MEASURED_CLEAN_OPS} the probe measured as the last clean point"
    )


def test_the_body_budget_is_a_constructor_option() -> None:
    """A caller with a smaller appetite gets a smaller batch.

    The same eight operations go out as one request on the default budget, so
    the split below is the option taking effect and not the size of the work.
    """
    def sweep(options: str) -> dict[str, Any]:
        return _run_batch(
            {BATCH_URL: [{"status": 200, "echo": True}]},
            f"""
            {_writer(options=options)}
            for (let i = 0; i < 8; i++) {{
              await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
            }}
            await writer.done();
            return {{ sent: requests.length,
                      sizes: requests.map((r) => r.opts.body.length) }};
            """,
        )

    assert sweep("")["sent"] == 1
    tight = sweep(", bodyBudgetBytes: 2000")
    assert tight["sent"] > 1, f"a 2000-byte budget did not split anything: {tight}"
    assert max(tight["sizes"]) <= 2000


def test_a_partly_refused_batch_is_an_error_naming_both_counts() -> None:
    """The whole reason this class exists.

    The outer request came back HTTP 200. `response.ok` is true, and every
    single one of the 500s below would have been dropped in silence.
    """
    result = _run_batch(
        {BATCH_URL: [
            {"status": 200, "text": _multipart_response([201, 500, 201, 500, 500])},
        ]},
        f"""
        {_writer()}
        for (let i = 0; i < 5; i++) {{
          await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
        }}
        try {{
          await writer.done();
          return {{ threw: false }};
        }} catch (err) {{
          return {{ threw: true, message: err.message, batchFailure: err.batchFailure,
                    throttled: err.throttled, sent: err.sent, landed: err.landed,
                    refused: err.refused, statuses: err.statuses,
                    logged: events.filter((e) => e.level === 'ERROR').length }};
        }}
        """,
    )
    assert result["threw"], "a batch with three failed parts reported success"
    assert result["batchFailure"] is True
    assert (result["landed"], result["refused"], result["sent"]) == (2, 3, 5)
    assert result["statuses"] == [201, 500, 201, 500, 500]
    assert result["throttled"] is False, "a 500 is a refusal, not a throttle"
    assert "2 landed, 3 refused" in result["message"], result["message"]
    assert "201, 500, 201, 500, 500" in result["message"], result["message"]
    assert result["logged"] >= 1, (
        "the refusal never reached the transcript the operator pastes back"
    )


def test_a_throttle_inside_the_envelope_is_reported_as_a_throttle() -> None:
    """429 on a part is the tenant pacing us, not refusing the content.

    The probe records this as its own response shape, distinct from an outer
    429/503/redirect, and a phase that cannot tell them apart either retries a
    refusal forever or gives up on a wait.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _multipart_response([201, 429, 503])}]},
        f"""
        {_writer()}
        for (let i = 0; i < 3; i++) {{
          await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
        }}
        try {{
          await writer.done();
          return {{ threw: false }};
        }} catch (err) {{
          return {{ threw: true, throttled: err.throttled, landed: err.landed,
                    refused: err.refused }};
        }}
        """,
    )
    assert result["threw"]
    assert result["throttled"] is True
    assert (result["landed"], result["refused"]) == (1, 2)


def test_a_throttled_outer_request_is_reported_as_a_throttle() -> None:
    """The browser gets a redirect to the throttling page, not a 429 (#401).

    `fetchWithRetry` waits it out; this asserts what the BatchWriter does when
    the wait ran out, so it is handed a transport with no attempts left.
    """
    throttle_url = f"{ORIGIN}/_layouts/15/Throttle.htm"
    result = _run_batch(
        {BATCH_URL: [{"status": 406, "url": throttle_url}]},
        f"""
        {_writer(transport="(url, opts) => fetchWithRetry(url, opts, 0)")}
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
        try {{
          await writer.done();
          return {{ threw: false }};
        }} catch (err) {{
          return {{ threw: true, throttled: err.throttled, landed: err.landed,
                    message: err.message }};
        }}
        """,
    )
    assert result["threw"], "a throttled $batch reported success"
    assert result["throttled"] is True, (
        "the throttling-page redirect was reported as a generic failure, so "
        "the surrounding phase cannot pace"
    )
    assert result["landed"] == 0


def test_a_response_with_no_part_statuses_is_refused() -> None:
    """An accepted envelope this cannot read is not a success.

    The probe credited the operations here and let its read-back control
    arbitrate. The BatchWriter has no control, so it fails closed.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": "nothing parseable here"}]},
        f"""
        {_writer()}
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'y' }});
        try {{
          await writer.done();
          return {{ threw: false }};
        }} catch (err) {{
          return {{ threw: true, message: err.message, landed: err.landed }};
        }}
        """,
    )
    assert result["threw"], "a $batch whose parts could not be counted passed"
    assert result["landed"] == 0
    assert "cannot be accounted for" in result["message"], result["message"]


def test_an_empty_done_sends_nothing() -> None:
    """Closing a writer nobody used must not POST an empty ChangeSet."""
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _multipart_response([])}]},
        f"""
        {_writer()}
        const first = await writer.done();
        const second = await writer.flush();
        return {{ first, second, sent: requests.length, requests: writer.requests }};
        """,
    )
    assert result["sent"] == 0, "an empty writer POSTed a $batch anyway"
    assert result["requests"] == 0
    assert result["first"] == {"requests": 0, "landed": 0, "statuses": []}
    assert result["second"] == result["first"]


def test_a_flushed_batch_is_not_sent_twice() -> None:
    """The queue is taken before the request, so a refusal cannot replay it.

    A retry the caller decides to make must resend nothing it did not queue
    again itself; duplicating an item write is not recoverable by re-running.
    """
    result = _run_batch(
        {BATCH_URL: [
            {"status": 200, "text": _multipart_response([500])},
            {"status": 200, "text": _multipart_response([201])},
        ]},
        f"""
        {_writer()}
        await writer.add('POST', "web/lists/getbytitle('Risk')/items", {{ Title: 'x' }});
        try {{ await writer.flush(); }} catch (err) {{ log('INFO', err.message); }}
        const after = await writer.done();
        return {{ after, sent: requests.length, pending: writer.pending.length }};
        """,
    )
    assert result["sent"] == 1, "the refused batch was sent a second time"
    assert result["pending"] == 0
    assert result["after"] == {"requests": 0, "landed": 0, "statuses": []}


def _query_response(parts: list[tuple[int, str]]) -> str:
    """A $batch response body carrying one query part's status AND payload.

    The payload is the difference. A ChangeSet response is read for its status
    lines alone; a query response is read for what it answered, so these parts
    carry a body and the reader has to get it back out from between the part
    headers and the next boundary.
    """
    body = "".join(
        f"--batchresponse_1\r\nContent-Type: application/http\r\n\r\n"
        f"HTTP/1.1 {status} Whatever\r\n"
        f"Content-Type: application/json;odata=verbose\r\n\r\n"
        f"{payload}\r\n"
        for status, payload in parts
    )
    return body + "--batchresponse_1--\r\n"


def _shapes(*ids: str) -> str:
    """A clean read of one `{ Id }` per part, in the order they were asked."""
    return _query_response(
        [(200, json.dumps({"d": {"Id": field_id}})) for field_id in ids],
    )


def _reader(*, transport: str = "fetchWithRetry", options: str = "") -> str:
    return (
        "const reader = new BatchReader({ getDigest, apiUrl, log, "
        f"fetchWithRetry: {transport}{options} }});"
    )


def test_a_read_batch_encodes_its_query_parts_outside_any_changeset() -> None:
    """The shape measured live: top-level GET parts, digest, no ChangeSet.

    A ChangeSet is the atomic-write grouping; a read has nothing to group and
    SharePoint refuses GETs inside one. What it does NOT let go of is the
    digest: the identical envelope without `X-RequestDigest` came back HTTP
    403, "The security validation for this page is invalid", even though every
    part is a read. That is the one line here a live tenant had to confirm.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _shapes("11", "22")}]},
        f"""
        {_reader()}
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('11')?$select=Id");
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('22')?$select=Id");
        await reader.done();
        return {{ sent: requests.length, url: requests[0].url,
                  method: requests[0].opts.method,
                  headers: requests[0].opts.headers, body: requests[0].opts.body }};
        """,
    )
    assert result["sent"] == 1, "two reads did not go out as one request"
    assert result["url"] == BATCH_URL
    assert result["method"] == "POST", "a $batch of reads is still POSTed"

    headers = result["headers"]
    assert headers["X-RequestDigest"] == DIGEST, (
        "the outer request carries no digest; measured live, that is a 403 "
        "even when every part inside it is a GET"
    )
    outer = headers["Content-Type"].removeprefix("multipart/mixed; boundary=")
    assert outer.startswith("batch_") and outer != headers["Content-Type"]
    assert "Accept" not in headers, (
        "an Accept header turns the throttling-page redirect into a 406 that "
        "only its URL identifies (#401); the write side omits it deliberately"
    )

    body = result["body"]
    assert "multipart/mixed; boundary=changeset_" not in body, (
        "the query parts were wrapped in a ChangeSet, which is the write "
        "grouping; SharePoint reads a GET there as a malformed write"
    )
    assert body.count("Content-Type: application/http\r\n") == 2
    assert body.count("Accept: application/json;odata=verbose\r\n") == 2
    assert (
        f"GET {ORIGIN}{WEB}/_api/web/lists/getbytitle('Risk')/fields/"
        "getbyid('11')?$select=Id HTTP/1.1\r\n" in body
    ), "a query part's request line is not an absolute url"
    assert "X-RequestDigest" not in body, (
        "a digest on a query part is a write-part header the read does not need"
    )
    assert body.endswith(f"--{outer}--\r\n")


def test_a_read_batch_answers_one_unwrapped_payload_per_part_in_order() -> None:
    """Position is the only join between a part and what it was asked for.

    A `$batch` response identifies its parts by order alone -- no request id,
    no echo of the url. The caller pairs `results[i]` with its own `i`th read,
    so the reader must never reorder, drop or coalesce one. `d` is the verbose
    envelope and is unwrapped here so the caller compares a shape, not a
    transport annotation.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _shapes("aa", "bb", "cc")}]},
        f"""
        {_reader()}
        for (const id of ['aa', 'bb', 'cc']) {{
          await reader.add(`web/lists/getbytitle('Risk')/fields/getbyid('${{id}}')?$select=Id`);
        }}
        const shapes = await reader.done();
        return {{ shapes, requests: reader.requests }};
        """,
    )
    assert result["shapes"] == [{"Id": "aa"}, {"Id": "bb"}, {"Id": "cc"}]
    assert result["requests"] == 1


def test_a_refused_query_part_fails_the_whole_read() -> None:
    """The read-side of the reason this class exists at all.

    The outer request is HTTP 200 and `response.ok` is true. A 404 on one part
    is a column that was NOT read back, and a phase that took the 200 for an
    answer would report verification it never performed. It fails closed, and
    it says `query part` so a refusal cannot be mistaken for a lost write.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _query_response([
            (200, '{"d":{"Id":"aa"}}'), (404, '{"error":{"message":"not found"}}'),
        ])}]},
        f"""
        {_reader()}
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('aa')?$select=Id");
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('gone')?$select=Id");
        try {{
          const shapes = await reader.done();
          return {{ threw: false, shapes }};
        }} catch (err) {{
          return {{ threw: true, message: err.message, batchFailure: err.batchFailure,
                    throttled: err.throttled, sent: err.sent, answered: err.answered,
                    refused: err.refused,
                    logged: events.filter((e) => e.level === 'ERROR').length }};
        }}
        """,
    )
    assert result["threw"], "a read batch with a 404 part answered as a clean read"
    assert result["batchFailure"] is True
    assert (result["sent"], result["answered"], result["refused"]) == (2, 1, 1)
    assert result["throttled"] is False, "a 404 is a refusal, not a throttle"
    assert "query part(s)" in result["message"], result["message"]
    assert "1 answered, 1 refused" in result["message"], result["message"]
    assert "200, 404" in result["message"], result["message"]
    assert result["logged"] >= 1, (
        "the refusal never reached the transcript the operator pastes back"
    )


def test_a_query_part_that_is_not_json_is_refused() -> None:
    """A part this cannot parse is not an answer, whatever its status says.

    SharePoint answers an HTML error or a throttling page with a 200 part more
    readily than it answers a malformed GET, and `JSON.parse` throwing inside
    a verification loop would be reported as that column's failure rather than
    as the read never having happened.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _query_response([
            (200, '{"d":{"Id":"aa"}}'), (200, "<html>Throttled</html>"),
        ])}]},
        f"""
        {_reader()}
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('aa')?$select=Id");
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('bb')?$select=Id");
        try {{
          return {{ threw: false, shapes: await reader.done() }};
        }} catch (err) {{
          return {{ threw: true, message: err.message, answered: err.answered }};
        }}
        """,
    )
    assert result["threw"], "an unparseable part passed as a read"
    assert result["answered"] == 0, (
        "a part that could not be parsed credited the parts before it, so the "
        "caller would pair its columns against a short list"
    )
    assert "is not JSON" in result["message"], result["message"]


def test_a_read_response_with_the_wrong_part_count_is_refused() -> None:
    """Position is the join, so a short answer is unpairable, not partial.

    Two reads answered by one part is not "the first one worked". Nothing in
    the response says WHICH read the part belongs to, so crediting it would
    pair a column against another column's shape.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _shapes("aa")}]},
        f"""
        {_reader()}
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('aa')?$select=Id");
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('bb')?$select=Id");
        try {{
          return {{ threw: false, shapes: await reader.done() }};
        }} catch (err) {{
          return {{ threw: true, message: err.message, answered: err.answered }};
        }}
        """,
    )
    assert result["threw"], "a $batch answering 1 of 2 reads passed"
    assert result["answered"] == 0
    assert "cannot be accounted for" in result["message"], result["message"]


def test_a_throttled_read_is_reported_as_a_throttle() -> None:
    """The browser gets a redirect to the throttling page, not a 429 (#401).

    Same shape as the write side, and it has to stay distinguishable from a
    refusal for the same reason: a caller that cannot tell them apart either
    retries a refusal forever or gives up on a wait.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 406, "url": f"{ORIGIN}/_layouts/15/Throttle.htm"}]},
        f"""
        {_reader(transport="(url, opts) => fetchWithRetry(url, opts, 0)")}
        await reader.add("web/lists/getbytitle('Risk')/fields/getbyid('aa')?$select=Id");
        try {{
          return {{ threw: false, shapes: await reader.done() }};
        }} catch (err) {{
          return {{ threw: true, throttled: err.throttled, answered: err.answered,
                    message: err.message }};
        }}
        """,
    )
    assert result["threw"], "a throttled read batch answered as a clean read"
    assert result["throttled"] is True
    assert result["answered"] == 0
    assert "query part(s)" in result["message"], result["message"]


def test_the_read_body_budget_splits_and_keeps_the_answers_in_order() -> None:
    """A split is invisible to the caller, which is the whole contract.

    The same body ceiling applies -- it is a property of the endpoint, not of
    the verb -- so a long verification splits. `results` accumulates across
    flushes, so the caller still pairs `results[i]` with its `i`th read and
    never learns how many requests that took.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "readEcho": True}]},
        f"""
        {_reader(options=", bodyBudgetBytes: 3000")}
        const asked = [];
        for (let i = 0; i < 40; i++) {{
          asked.push(String(i));
          await reader.add(`web/lists/getbytitle('Risk')/fields/getbyid('${{i}}')?$select=Id`);
        }}
        const shapes = await reader.done();
        return {{ asked, shapes, sent: requests.length,
                  sizes: requests.map((r) => r.opts.body.length) }};
        """,
    )
    assert result["sent"] > 1, f"a 3000-byte budget did not split anything: {result}"
    assert max(result["sizes"]) <= 3000
    assert result["shapes"] == [{"Id": asked} for asked in result["asked"]], (
        "the answers did not survive the split in the order they were asked"
    )


def test_an_empty_read_sends_nothing() -> None:
    """Closing a reader nobody used must not POST an empty envelope.

    The index phase builds one whether or not the schema declares an indexed
    column, and an empty multipart body is a 400 rather than a no-op.
    """
    result = _run_batch(
        {BATCH_URL: [{"status": 200, "text": _shapes()}]},
        f"""
        {_reader()}
        const shapes = await reader.done();
        return {{ shapes, sent: requests.length, requests: reader.requests }};
        """,
    )
    assert result["sent"] == 0, "an empty reader POSTed a $batch anyway"
    assert result["requests"] == 0
    assert result["shapes"] == []
