"""Execute the shared `establishFixture` helper and the probes built on it (#559).

A fixture row recorded from a status, a name match or a literal `'PASS'` lets
a measurement run against a fixture that is not the one declared, and the
finding it produces is confident and wrong. The helper reads the declared
properties back and voids every dependent row when one does not hold.

The helper is run on its own first, once per way it fails closed and once
healthy, then each probe fixed on it is run against a mock SharePoint with a
wrong-shaped fixture and with a healthy one.
"""

import importlib.util
import json
import sys
import textwrap
from types import ModuleType

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WINDOW = (
    "globalThis.window = { _spPageContextInfo: "
    "{ webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' } };\n"
)

#: Shared by every mock below: a fetch response, and a record of what was sent.
_RESPONSES = textwrap.dedent("""
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'Thu, 24 Sep 2026 09:00:00 GMT' },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const digestResponse = () => jsonResponse(200, {
      d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
    // A field absent by name answers 400 on a live site, not 404.
    const noSuchField = () => jsonResponse(400, {
      'odata.error': { message: { value: 'Column does not exist.' } } });
    // Only the status is asserted on, so the body claims nothing about its shape.
    const throttled = () => jsonResponse(429, { 'odata.error': { message: { value: '' } } });
    // Waits are skipped, so a probe's ten-second pause costs the suite nothing.
    const realSetTimeout = setTimeout;
    globalThis.setTimeout = (fn, ms, ...rest) => realSetTimeout(fn, 0, ...rest);
""")


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes_fixture", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(output: str) -> dict[str, dict[str, str]]:
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"no result table was printed:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


def _sent(output: str) -> list[dict[str, str]]:
    line = next((ln for ln in output.splitlines() if ln.startswith("__SENT__")), None)
    assert line is not None, f"no request log was printed:\n{output[-3000:]}"
    return list(json.loads(line.removeprefix("__SENT__")))


# --------------------------------------------------------------------------
# The helper on its own.
# --------------------------------------------------------------------------
FIXTURE = "field.probe.fixture-thing"
DEPENDENTS = ["field.probe.dependent-one", "field.probe.dependent-two"]
BYSTANDER = "field.probe.bystander"


DATE_TIME_DECLARED = "{ TypeAsString: 'DateTime', DisplayFormat: 1 }"


def _run_helper(
    read: str, declared: str = DATE_TIME_DECLARED,
) -> tuple[bool, dict[str, dict[str, str]]]:
    """Call establishFixture once, with `read` as the body of its read function."""
    harness = _load_renderer()._env().get_template("_probe_harness.js.j2").render()
    script = (
        WINDOW
        + "(async () => {\n"
        + harness
        + f"  expect('{FIXTURE}', 'the thing holds');\n"
        + f"  expect('{DEPENDENTS[0]}', 'question one');\n"
        + f"  expect('{DEPENDENTS[1]}', 'question two');\n"
        + f"  expect('{BYSTANDER}', 'a question that does not rest on the thing');\n"
        + f"  const held = await establishFixture('{FIXTURE}', async () => {{ {read} }},\n"
        + f"    {declared}, {json.dumps(DEPENDENTS)});\n"
        + "  console.log('__HELD__' + JSON.stringify(held));\n"
        + "  console.log('__ROWS__' + JSON.stringify(RESULTS));\n"
        + "})();\n"
    )
    output = run_node(script)
    held_line = next(ln for ln in output.splitlines() if ln.startswith("__HELD__"))
    return json.loads(held_line.removeprefix("__HELD__")), _rows(output)


def _assert_voided(rows: dict[str, dict[str, str]], named: str) -> None:
    fixture = rows[FIXTURE]
    assert fixture["outcome"] == "FAIL", fixture
    assert named in fixture["evidence"], fixture
    for dependent in DEPENDENTS:
        row = rows[dependent]
        assert row["state"] == "void", row
        assert FIXTURE in row["evidence"], row
        assert named in row["evidence"], row
        assert row["question"].startswith("question"), row
    assert rows[BYSTANDER]["state"] == "open", rows[BYSTANDER]


def test_a_fixture_that_reads_back_as_declared_passes_and_voids_nothing() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is True
    assert rows[FIXTURE]["outcome"] == "PASS"
    assert "DisplayFormat=1" in rows[FIXTURE]["evidence"]
    assert [row["state"] for row in rows.values()] == ["settled", "open", "open", "open"]


def test_a_predicate_decides_a_declared_property() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { ValidationFormula: 'DM<=Modified' } };",
        "{ ValidationFormula: (v) => String(v).replace(/[[\\]]/g, '') === 'DM<=Modified' }",
    )

    assert held is True
    assert rows[FIXTURE]["outcome"] == "PASS"


def test_a_property_that_differs_voids_the_dependents() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime', DisplayFormat: 0 } };")

    assert held is False
    _assert_voided(rows, "DisplayFormat differs: read 0, declared 1")


def test_a_predicate_that_fails_is_a_difference() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { ItemCount: 4000 } };",
        "{ ItemCount: (n) => n >= 5001 }",
    )

    assert held is False
    _assert_voided(rows, "ItemCount differs: read 4000, declared by a predicate it fails")


def test_a_property_absent_from_the_payload_voids_the_dependents() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime' } };")

    assert held is False
    _assert_voided(rows, "DisplayFormat is absent from the payload")


@pytest.mark.parametrize(
    ("status", "named"),
    [
        (404, "the read was refused (HTTP 404)"),
        (500, "the read was refused (HTTP 500)"),
        (403, "the read was not authorised (HTTP 403)"),
        (408, "the read timed out (HTTP 408)"),
    ],
)
def test_a_read_that_did_not_answer_voids_the_dependents(status: int, named: str) -> None:
    # The error payload carries both declared names, so only the status can refuse it.
    held, rows = _run_helper(
        f"return {{ ok: false, status: {status}, "
        "body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is False
    _assert_voided(rows, named)


@pytest.mark.parametrize("status", [429, 503])
def test_a_throttled_read_voids_the_dependents(status: int) -> None:
    held, rows = _run_helper(
        f"return {{ ok: false, status: {status}, "
        "body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is False
    _assert_voided(rows, f"the read was throttled (HTTP {status})")


def test_a_read_that_throws_voids_the_dependents() -> None:
    held, rows = _run_helper("throw new Error('Failed to fetch');")

    assert held is False
    _assert_voided(rows, "the read threw: Failed to fetch")


def test_a_2xx_with_no_payload_voids_the_dependents() -> None:
    held, rows = _run_helper("return { ok: true, status: 200, body: null };")

    assert held is False
    _assert_voided(rows, "the read answered HTTP 200 with no payload")
