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


def _evaluated(expression: str, known: str = (
        "  knowIdentity('it@example.com', '<account>');\n"
        "  knowIdentity('It', '<name>', true);\n")) -> object:
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
        + known
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


# Valid identities a narrower pattern stops part way through, leaving a prefix or a tail.
UNLEARNED = {
    "from o'brien@example.com today": "from <account> today",
    "to ada+probe@example.com": "to <account>",
    "to mary-jane.o'neil@sub.example.co.uk": "to <account>",
    '{"Email":"o\'brien@example.com"}': '{"Email":"<account>"}',
    "to renée.zoë@example.com": "to <account>",
    "to a!#$%&*=?^_`{}~b@example.com": "to <account>",
    "as i:0#.f|membership|o'brien@example.com": "as i:0#.f|membership|<account>",
    "as i:0#.w|contoso\\o'brien": "as i:0#.w|<account>",
    '{"LoginName":"i:0#.w|contoso\\\\ada"}': '{"LoginName":"i:0#.w|<account>"}',
    # A JSON escape after a login survives, so the text around it still parses.
    '{\\"x\\":\\"i:0#.f|membership|ada@example.com\\"}': (
        '{\\"x\\":\\"i:0#.f|membership|<account>\\"}'),
}


def test_every_valid_address_and_login_is_masked_whole() -> None:
    out = _evaluated(f"{json.dumps(list(UNLEARNED))}.map(scrub)", known="")

    assert out == list(UNLEARNED.values())


LEARNED = {
    "Written by Renée O'Brien-Smith.": "Written by <name>.",
    '"LookupValue":"Renée O\'Brien-Smith"': '"LookupValue":"<name>"',
    # The same name as an answer's JSON may spell it, with its non-ASCII letter escaped.
    "Written by Ren\\u00e9e O'Brien-Smith.": "Written by <name>.",
    "Written by Ren\\u00E9e O'Brien-Smith.": "Written by <name>.",
}


def test_a_learned_display_name_is_masked_however_an_answer_spells_it() -> None:
    out = _evaluated(f"{json.dumps(list(LEARNED))}.map(scrub)",
                     known="  knowIdentity(\"Renée O'Brien-Smith\", '<name>', true);\n")

    assert out == list(LEARNED.values())
