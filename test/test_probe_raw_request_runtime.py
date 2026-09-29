"""Execute the shared raw-request partial on its own, one case per way a request answers.

The probes built on it record a refusal's text as the finding, so the partial is run under
node against a fetch that answers healthy, refuses, throttles, denies, answers 2xx with no
JSON, and never answers, before any probe relies on it.
"""

import importlib.util
import json
import sys
import textwrap
from types import ModuleType
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WINDOW = (
    "globalThis.window = { _spPageContextInfo: "
    "{ webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' } };\n"
)

#: Answers every request with CONFIG.status and CONFIG.text, or rejects it when CONFIG.reject.
_FETCH = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    globalThis.fetch = async (url, opts = {}) => {
      if (CONFIG.reject) throw new TypeError('Failed to fetch');
      return {
        ok: CONFIG.status >= 200 && CONFIG.status < 300,
        status: CONFIG.status,
        headers: { get: (name) => (String(name).toLowerCase() === 'date' ? CONFIG.date : null) },
        text: async () => CONFIG.text,
        json: async () => JSON.parse(CONFIG.text),
      };
    };
""")


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes_raw", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(expression: str, **config: Any) -> Any:
    """Evaluate `expression` inside a probe body holding the harness and the partial."""
    env = _load_renderer()._env()
    harness = env.get_template("_probe_harness.js.j2").render()
    partial = env.get_template("_probe_raw_request_v1.js.j2").render()
    settings = {"status": 200, "text": "", "date": None, "reject": False, **config}
    script = (
        WINDOW
        + _FETCH.replace("__CONFIG__", json.dumps(settings))
        + "(async () => {\n" + harness + partial
        + f"  const out = await (async () => {expression})();\n"
        + "  console.log('__OUT__' + JSON.stringify(out));\n"
        + "})();\n"
    )
    output = run_node(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__OUT__")), None)
    assert line is not None, output[-2000:]
    return json.loads(line.removeprefix("__OUT__"))


def test_a_json_answer_keeps_the_text_the_parse_and_the_date_header() -> None:
    out = _run("sendRaw('web/x')", text='{"value": 3}', date="Tue, 29 Sep 2026 00:00:00 GMT")

    assert out == {"ok": True, "status": 200, "text": '{"value": 3}', "parsed": {"value": 3},
                   "date": "Tue, 29 Sep 2026 00:00:00 GMT"}


def test_a_text_answer_is_kept_with_no_parse() -> None:
    out = _run("sendRaw('web/x')", text="<html>sign in</html>")

    assert out["parsed"] is None
    assert out["text"] == "<html>sign in</html>"


def test_a_request_that_never_answered_is_a_result_not_a_throw() -> None:
    out = _run("sendRaw('web/x')", reject=True)

    assert out["status"] is None
    assert out["text"] == "no response: Failed to fetch"


def test_a_2xx_has_no_head_so_the_payload_decides() -> None:
    assert _run("rawHead(await sendRaw('web/x'))", text="{}") is None


def test_a_refusal_heads_refused_and_quotes_the_text_without_the_tenant() -> None:
    said = "The URL https://EXAMPLE.sharepoint.com/sites/test/_api/web/x is not valid"
    out = _run("rawHead(await sendRaw('web/x'))", status=500, text=said)

    assert out["outcome"] == "REFUSED"
    assert out["why"] == "HTTP 500: The URL [TENANT]/sites/test/_api/web/x is not valid"


#: A JSON-escaped origin as SharePoint can write it; the backslashes are literal in the text.
ESCAPED = "https:\\/\\/EXAMPLE.sharepoint.com/sites/test"


@pytest.mark.parametrize(
    ("text", "said"),
    [
        (f'{{"uri":"{ESCAPED}/_api/web"}}', '{"uri":"[TENANT]/sites/test/_api/web"}'),
        ("served by Example.SharePoint.com today", "served by [TENANT] today"),
        (f"both {ESCAPED} and example.sharepoint.com", "both [TENANT]/sites/test and [TENANT]"),
    ],
    ids=["json-escaped-origin", "bare-host", "both"],
)
def test_an_escaped_origin_and_a_bare_host_are_redacted(text: str, said: str) -> None:
    out = _run("rawHead(await sendRaw('web/x'))", status=500, text=text)

    assert out["why"] == f"HTTP 500: {said}"
    assert "example.sharepoint.com" not in json.dumps(out).lower()


@pytest.mark.parametrize(
    ("status", "named"),
    [
        (429, "was throttled (HTTP 429)"),
        (503, "was throttled (HTTP 503)"),
        (408, "timed out (HTTP 408)"),
        (403, "was not authorised (HTTP 403)"),
    ],
)
def test_a_throttle_or_a_denial_is_not_a_refusal(status: int, named: str) -> None:
    out = _run("rawHead(await sendRaw('web/x'))", status=status, text="slow down")

    assert out["outcome"] == "NOT ESTABLISHED"
    assert out["why"] == f"the request {named}: slow down"


def test_an_unanswered_request_heads_not_established() -> None:
    out = _run("rawHead(await sendRaw('web/x'))", reject=True)

    assert out == {"outcome": "NOT ESTABLISHED", "why": "no response: Failed to fetch"}


@pytest.mark.parametrize(
    "answer",
    [
        {"d": {"GetContextWebInformation": {"FormDigestValue": "digest"}}},
        {"FormDigestValue": "digest"},
    ],
    ids=["verbose", "nometadata"],
)
def test_the_digest_is_read_in_either_envelope(answer: dict[str, Any]) -> None:
    out = _run("(await issueDigest()).digest", text=json.dumps(answer))

    assert out == "digest"


@pytest.mark.parametrize(
    "config",
    [{"status": 403, "text": "denied"}, {"reject": True}, {"text": "{}"}],
    ids=["denied", "no-response", "no-digest"],
)
def test_no_digest_is_null_rather_than_a_throw(config: dict[str, Any]) -> None:
    assert _run("(await issueDigest()).digest", **config) is None
