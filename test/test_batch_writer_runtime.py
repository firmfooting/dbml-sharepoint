# test/test_batch_writer_runtime.py
"""Execute the emitted BatchWriter against a mock SharePoint.

`BatchWriter` is the transport primitive the write-capable scripts use to
collapse many single writes into one OData `$batch` request, and two of its
properties cannot be seen anywhere else in the stack:

- the outer `$batch` request answers HTTP 200 even when ChangeSet parts fail,
  so a plain `fetchWithRetry` on it reports success while dropping writes;
- the tenant's ceiling is body SIZE, not operation count. MEASURED by
  `test/manual/throttle-batch-probe.js` (#404): 750 operations landed clean
  and 1000 came back 200 with 637 parts at 201 and 363 at 500.

The class is LIFTED out of the emitted deploy script rather than copied, for
the reason `test_transport_runtime.py` gives: a copy keeps passing after the
real one changes.

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
    assert "class BatchWriter {" in block, (
        "the BatchWriter is no longer emitted between the transport partial "
        "and the cached digest; this test is measuring the wrong text"
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
        text: async () => (next.echo ? echoed(opts) : (next.text || '')),
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
