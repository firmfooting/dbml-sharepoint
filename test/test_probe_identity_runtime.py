"""Execute the shared identity-masking partial's scrub under node.

A display name is masked only as a whole token, so a short name does not rewrite the words
and identifiers it happens to be spelled inside. Logins and emails are masked wherever they
appear.
"""

import importlib.util
import json
import sys

import pytest
from _node import NODE, run_node
from _paths import MANUAL
from _versions_mock import VERSIONS_MOCK

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SAMPLES = {
    '"LookupValue":"It"': '"LookupValue":"<name>"',
    "Written by It.": "Written by <name>.",
    "Written=3, ProbeITem, it_1": "Written=3, ProbeITem, it_1",
    "mail it@example.com as i:0#.f|membership|it@example.com": (
        "mail <account> as i:0#.f|membership|<account>"),
    # An address the probe never learned, whose local part is the display name.
    "copied to it@elsewhere.org": "copied to <account>",
}


def _evaluated(expression: str) -> object:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes_identity", MANUAL / "render_probes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    env = module._env()
    body = "".join(env.get_template(name).render() for name in (
        "_probe_harness.js.j2", "_probe_raw_request_v1.js.j2", "_probe_identity_v1.js.j2"))
    output = run_node(
        VERSIONS_MOCK.replace("__CONFIG__", "{}") + "(async () => {\n" + body
        + "  knowIdentity('it@example.com', '<account>');\n"
        + "  knowIdentity('It', '<name>', true);\n"
        + f"  console.log('__OUT__' + JSON.stringify({expression}));\n"
        + "})();\n")
    line = next(ln for ln in output.splitlines() if ln.startswith("__OUT__"))
    return json.loads(line.removeprefix("__OUT__"))


def _scrubbed(samples: list[str]) -> list[str]:
    out = _evaluated(f"{json.dumps(samples)}.map(scrub)")
    assert isinstance(out, list)
    return out


def test_a_display_name_is_masked_as_a_whole_token_and_nowhere_else() -> None:
    assert _scrubbed(list(SAMPLES)) == list(SAMPLES.values())


def test_a_refusal_is_masked_before_it_is_cut_short() -> None:
    # The name straddles the 400-character cut, so masking after the cut would leave "I" showing.
    text = "x" * 398 + " It"
    head = _evaluated(f"maskedHead({{ ok: false, status: 500, text: {json.dumps(text)} }})")

    assert isinstance(head, dict)
    assert head["why"].endswith("x" * 10 + " <"), head["why"]
