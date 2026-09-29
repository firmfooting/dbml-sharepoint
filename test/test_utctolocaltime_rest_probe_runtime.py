"""Execute utctolocaltime-rest-form-probe.js under node against a mock web.

`node --check` proves the probe parses; only running it proves what it records. Each run
answers the way a live site can: healthy, refusing with a text body, throttling, denying,
answering 2xx with no JSON, and never answering.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "utctolocaltime-rest-form-probe.js"
ZONE = "field.date.control-site-time-zone"
DIGEST = "field.date.control-form-digest-issued"
FORMS = {
    "field.date.utctolocaltime-post-quoted-literal": "utcToLocalTime('",
    "field.date.utctolocaltime-post-alias-parameter": "utcToLocalTime(@d)",
    "field.date.utctolocaltime-post-body-date": '"date"',
    "field.date.utctolocaltime-post-body-utctime": '"utcTime"',
    "field.date.utctolocaltime-post-datetime-literal": "utcToLocalTime(datetime'",
    "field.date.localtimetoutc-post-quoted-literal": "localTimeToUTC('",
}

#: Rules are tried in order; a rule matches on the decoded path and, if given, the body.
_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    globalThis.window = { _spPageContextInfo: {
      webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe' } };
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const answer = (status, text) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: (name) => (String(name).toLowerCase() === 'date' ? CONFIG.date : null) },
      text: async () => text,
      json: async () => JSON.parse(text),
    });
    const healthy = (path, opts) => {
      if (path === 'contextinfo') {
        const info = { FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 };
        const verbose = String((opts.headers || {}).Accept || '').includes('verbose');
        const wrapped = verbose ? { d: { GetContextWebInformation: info } } : info;
        return answer(200, JSON.stringify(wrapped));
      }
      if (path.startsWith('web/RegionalSettings/TimeZone/')) {
        return answer(200, JSON.stringify({ value: '2026-09-29T10:00:00' }));
      }
      if (path === 'web/RegionalSettings/TimeZone') {
        return answer(200, JSON.stringify({ Description: '(UTC+10:00) Canberra, Melbourne, Sydney',
          Id: 76, Information: { Bias: -600, DaylightBias: -60, StandardBias: 0 } }));
      }
      return answer(404, 'no such endpoint in the mock: ' + path);
    };
    globalThis.fetch = async (url, opts = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const body = opts.body === undefined ? '' : String(opts.body);
      SENT.push({ method: opts.method || 'GET', path, body,
        digest: (opts.headers || {})['X-RequestDigest'] || null });
      for (const rule of CONFIG.rules) {
        if (!(path + ' ' + body).includes(rule.contains)) continue;
        if (rule.reject) throw new TypeError('Failed to fetch');
        return answer(rule.status, rule.text);
      }
      return healthy(path, opts);
    };
""")


def _probe_js(confirmed: bool) -> str:
    js = PROBE.read_text(encoding="utf-8")
    if confirmed:
        opened = js.replace("  const CONFIRMED = false;", "  const CONFIRMED = true;", 1)
        assert opened != js, "the CONFIRMED gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run(
    rules: list[dict[str, Any]] | None = None,
    *,
    date: str | None = "Tue, 29 Sep 2026 00:00:00 GMT",
    confirmed: bool = True,
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]], str]:
    config = json.dumps({"rules": rules or [], "date": date})
    output = run_node(_MOCK.replace("__CONFIG__", config) + "\n" + _probe_js(confirmed))
    sent_line = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    rows_line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    rows = {} if rows_line is None else {
        row["id"]: row for row in json.loads(rows_line.removeprefix("__ROWS__"))}
    return rows, json.loads(sent_line.removeprefix("__SENT__")), output


def test_an_unconfirmed_probe_prints_its_plan_and_sends_nothing() -> None:
    rows, sent, output = _run(confirmed=False)

    assert sent == []
    assert rows == {}
    assert "Set CONFIRMED = true" in output


def test_a_healthy_run_records_every_form_accepted_with_its_value() -> None:
    rows, sent, _ = _run()

    assert rows[ZONE]["outcome"] == "PASS"
    zone = rows[ZONE]["evidence"]
    assert 'site zone "(UTC+10:00) Canberra, Melbourne, Sydney" Id=76 bias=-600' in zone
    assert rows[DIGEST]["outcome"] == "PASS"
    for form in FORMS:
        assert rows[form]["outcome"] == "ACCEPTED", rows[form]
        assert rows[form]["state"] == "settled"
        assert 'value "2026-09-29T10:00:00"' in rows[form]["evidence"]
    posts = [r for r in sent if r["path"].startswith("web/RegionalSettings/TimeZone/")]
    assert len(posts) == 6
    assert all(r["method"] == "POST" and r["digest"] == "digest" for r in posts)
    assert len(sent) == 1 + 1 + 6


def test_every_form_is_asked_about_the_server_instant() -> None:
    rows, sent, _ = _run()

    zone = rows[ZONE]["evidence"]
    assert "asked about 2026-09-29T00:00:00.000Z, from the server Date header" in zone
    for form, marker in FORMS.items():
        [request] = [r for r in sent if marker in r["path"] + " " + r["body"]]
        assert "2026-09-29T00:00:00.000Z" in request["path"] + request["body"], form


def test_without_a_date_header_the_browser_clock_is_named() -> None:
    rows, _, _ = _run(date=None)

    assert "from this browser's clock" in rows[ZONE]["evidence"]
    quoted = rows["field.date.utctolocaltime-post-quoted-literal"]["evidence"]
    assert "(from this browser's clock)" in quoted


def test_a_refusal_is_recorded_with_its_status_and_text() -> None:
    refused = "The expression is not valid."
    rows, _, _ = _run([{"contains": "utcToLocalTime(datetime'", "status": 400, "text": refused}])

    row = rows["field.date.utctolocaltime-post-datetime-literal"]
    assert row["outcome"] == "REFUSED"
    assert row["state"] == "settled"
    assert "HTTP 400: The expression" in row["evidence"]
    assert rows["field.date.utctolocaltime-post-quoted-literal"]["outcome"] == "ACCEPTED"


@pytest.mark.parametrize("status", [429, 503, 408, 403, 401])
def test_a_throttle_or_a_denial_leaves_the_form_open(status: int) -> None:
    rows, _, _ = _run([{"contains": "localTimeToUTC('", "status": status, "text": "slow down"}])

    row = rows["field.date.localtimetoutc-post-quoted-literal"]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert row["state"] == "open"
    assert f"HTTP {status}" in row["evidence"]


def test_a_request_with_no_response_is_a_row_and_the_table_still_prints() -> None:
    rows, _, _ = _run([{"contains": '"utcTime"', "reject": True}])

    row = rows["field.date.utctolocaltime-post-body-utctime"]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert "no response: Failed to fetch" in row["evidence"]
    assert rows["field.date.utctolocaltime-post-body-date"]["outcome"] == "ACCEPTED"


def test_a_2xx_with_no_json_value_is_not_an_acceptance() -> None:
    rows, _, _ = _run([{"contains": "utcToLocalTime(@d)", "status": 200,
                        "text": "<html>sign in</html>"}])

    row = rows["field.date.utctolocaltime-post-alias-parameter"]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert "carried no JSON value: <html>sign in</html>" in row["evidence"]


@pytest.mark.parametrize(
    "rule",
    [
        {"contains": "contextinfo", "status": 403, "text": "denied"},
        {"contains": "contextinfo", "reject": True},
        {"contains": "contextinfo", "status": 200, "text": "{}"},
    ],
    ids=["denied", "no-response", "no-digest"],
)
def test_without_a_digest_every_form_is_void_and_none_is_sent(rule: dict[str, Any]) -> None:
    rows, sent, _ = _run([rule])

    assert rows[DIGEST]["outcome"] in {"FAIL", "NOT ESTABLISHED"}
    for form in FORMS:
        assert rows[form]["state"] == "void", rows[form]
    assert not [r for r in sent if r["path"].startswith("web/RegionalSettings/TimeZone/")]


def test_an_unread_zone_still_asks_every_form() -> None:
    rows, _, _ = _run([{"contains": "web/RegionalSettings/TimeZone ", "status": 429,
                        "text": "busy"}])

    assert rows[ZONE]["outcome"] == "NOT ESTABLISHED"
    assert all(rows[form]["outcome"] == "ACCEPTED" for form in FORMS)


def test_the_evidence_never_names_the_tenant() -> None:
    said = "Bad URL https://example.sharepoint.com/sites/probe/_api/web"
    rows, _, _ = _run([{"contains": "utcToLocalTime('", "status": 500, "text": said}])

    quoted = rows["field.date.utctolocaltime-post-quoted-literal"]["evidence"]
    assert "[TENANT]/sites/probe/_api/web" in quoted
    assert "example.sharepoint.com" not in json.dumps(rows)


def test_a_verbose_shaped_answer_is_read_as_the_value() -> None:
    rows, _, _ = _run([{"contains": "localTimeToUTC('", "status": 200,
                        "text": '{"d": {"LocalTimeToUTC": "2026-09-28T14:00:00Z"}}'}])

    row = rows["field.date.localtimetoutc-post-quoted-literal"]
    assert row["outcome"] == "ACCEPTED"
    assert 'value "2026-09-28T14:00:00Z"' in row["evidence"]
