# test/test_deploy_runtime.py
"""Execute the generated deploy.js against a mock SharePoint.

The golden-file test proves deploy.js does not CHANGE; it cannot prove it
RUNS. A whole class of defect lives in that gap — a caller that omits a
key another function requires, a comparison against `undefined`, a
sentinel that reads as a real value. One such bug shipped in the golden
fixture and was asserted as correct: the synthetic Title patch carried
none of the declared-formula keys, so every field reconcile treated it as
managed and aborted the phase on every list, on every run.

Node is required; the test skips without it rather than failing, since it
is not a dependency of the package.
"""

import json
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
NODE = shutil.which("node")


def _deploy_js() -> str:
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml
    from dbml_sharepoint.model.release import load_release

    return generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


# A SharePoint that answers every read as an EMPTY, healthy list: no fields
# exist, no formulas are set. That is the state of a brand-new site, and the
# state in which the shipped bug threw.
_HARNESS = textwrap.dedent("""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const body = (url) => {
      if (url.includes('contextinfo')) {
        return { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      }
      if (url.toLowerCase().includes('effectivebasepermissions')) {
        return { d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } };
      }
      if (url.includes('ClientValidationFormula') || url.includes('ValidationFormula')) {
        return { d: {
          ClientValidationFormula: null, ClientValidationMessage: null,
          ValidationFormula: null, ValidationMessage: null } };
      }
      return { d: { results: [] } };
    };
    globalThis.fetch = async (url, opts = {}) => {
      calls.push({ url: String(url), method: opts.method || 'GET', body: opts.body });
      return {
        ok: true, status: 200,
        headers: { get: () => null },
        json: async () => body(String(url)),
        text: async () => JSON.stringify(body(String(url))),
      };
    };
    globalThis.__calls = calls;
""")


def _run(script: str) -> str:
    """Via a file: deploy.js is far past the Windows command-line limit."""
    assert NODE is not None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "run.js"
        path.write_text(script, encoding="utf-8")
        proc = subprocess.run(  # noqa: S603
            [NODE, str(path)], capture_output=True, text=True, timeout=180, check=False,
        )
    return proc.stdout + proc.stderr


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_deploy_js_runs_without_throwing() -> None:
    """The generated script must reach a summary against a healthy site.

    It need not succeed at provisioning — the mock is too thin for that —
    but a thrown exception or an abort carrying schema errors means the
    script is broken for every operator on every site.
    """
    script = _HARNESS + "\n" + _deploy_js().replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))"
        ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(result_line.removeprefix("__RESULT__"))
    # The mock is deliberately thin, so shape probes legitimately complain.
    # What must never appear is a formula error: that is the phase-aborting
    # failure the synthetic Title patch produced on every list, every run,
    # and it is invisible to a golden-file comparison.
    formula_errors = [
        err for err in (summary.get("errors") or [])
        if "ValidationFormula" in str(err) or "ValidationMessage" in str(err)
    ]
    assert not formula_errors, f"deploy.js aborted on the declared formulas: {formula_errors}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_builtin_title_column_is_never_sent_a_formula() -> None:
    """Title is not a declared field, so the tool does not own its
    formulas. The shipped bug MERGEd an empty ClientValidationMessage onto
    it before aborting — an unrequested write to a built-in column."""
    script = _HARNESS + "\n" + _deploy_js().replace(
        "})();", "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
        ).replace("(async () => {", "((async () => {", 1)
    line = next(
        (ln for ln in _run(script).splitlines() if ln.startswith("__CALLS__")),
        None,
    )
    assert line is not None, "harness produced no call log"
    calls = json.loads(line.removeprefix("__CALLS__"))
    title_writes = [
        c for c in calls
        if c["method"] == "POST" and c["body"] and "ValidationMessage" in c["body"]
        and "'Title'" in c["url"]
    ]
    assert not title_writes, (
        f"wrote formula properties to the built-in Title column: {title_writes}"
    )
