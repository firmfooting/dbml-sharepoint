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


# An ADOPTED site: the lists already exist and the built-in Title is
# SEALED. The harness above answers every field probe as absent, so the
# adoption path — the one where declared shapes are actually compared —
# has never executed in a test. That is the gap the synthetic-Title bug
# shipped through.
_ADOPTED_HARNESS = textwrap.dedent(r"""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    // Per-list Title state, mutated by MERGEs exactly as SharePoint would.
    const titles = {};
    const titleState = (listTitle) => (titles[listTitle] ||= {
      Sealed: true, Required: true, Description: '', DefaultValue: null,
    });
    const titleField = (listTitle) => ({
      Id: '11111111-1111-1111-1111-111111111111',
      InternalName: 'Title', Title: 'Title', TypeAsString: 'Text',
      EnforceUniqueValues: false, Indexed: false, ReadOnlyField: false,
      CustomFormatter: null, ...titleState(listTitle),
    });
    // Created fields persist, so the run converges instead of failing
    // "missing after creation" and aborting before PROTECTION. Without
    // this the mock could never execute a phase past list creation.
    const TYPE_BY_KIND = { 2: 'Text', 3: 'Note', 4: 'DateTime', 6: 'Choice',
      7: 'Lookup', 8: 'Boolean', 9: 'Number', 11: 'URL', 20: 'User',
      17: 'Calculated' };
    const created = {};   // `${list} ${title}` -> shape
    const listOf = (url) => (url.match(/getbytitle\('([^']+)'\)/) || [])[1];
    const fieldShape = (listTitle, name, b) => ({
      Id: '33333333-3333-3333-3333-333333333333',
      InternalName: name, Title: name,
      TypeAsString: TYPE_BY_KIND[b.FieldTypeKind] || 'Text',
      Description: b.Description == null ? '' : b.Description,
      Required: b.Required === true,
      EnforceUniqueValues: b.EnforceUniqueValues === true,
      Indexed: b.EnforceUniqueValues === true,
      ReadOnlyField: b.FieldTypeKind === 17,
      Sealed: false,
      DefaultValue: b.DefaultValue == null ? null : b.DefaultValue,
      CustomFormatter: b.CustomFormatter == null ? null : b.CustomFormatter,
      __body: b,
    });
    const body = (url, opts) => {
      if (url.includes('contextinfo')) {
        return { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      }
      if (url.toLowerCase().includes('effectivebasepermissions')) {
        return { d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } };
      }
      // A field probe or enumeration. Title exists from the start (it is
      // the adopted, sealed one); everything else appears once created.
      // Checked BEFORE the list probe, whose own $select also names
      // ValidationFormula.
      if (url.includes('/fields')) {
        const listTitle = listOf(url);
        if (url.includes('ClientValidationFormula')) {
          const probed = (url.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
          const f = created[`${listTitle} ${probed}`] || {};
          return { d: {
            ClientValidationFormula: f.__cvf == null ? null : f.__cvf,
            ClientValidationMessage: null,
            ValidationFormula: f.__vf == null ? null : f.__vf,
            ValidationMessage: f.__vm == null ? null : f.__vm } };
        }
        const named = (url.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
        if (named === 'Title') return { d: titleField(listTitle) };
        if (named) {
          const f = created[`${listTitle} ${named}`];
          if (!f) return { error: { code: '-2147024809, System.ArgumentException' } };
          // A derived-property probe (MaxLength, Choices, DisplayFormat...)
          // names none of the shape columns; echo what the field was
          // created with, which is what the declaration asked for.
          if (!url.includes('InternalName')) return { d: f.__body };
          return { d: f };
        }
        const own = Object.entries(created)
          .filter(([k]) => k.startsWith(`${listTitle} `))
          .map(([, v]) => v);
        return { d: { results: [titleField(listTitle), ...own] } };
      }
      // Principals: enough shape to get PREPARE past 1.2/1.3 and reach the
      // maintenance unseal at 1.4. Before this, the runtime test had never
      // executed a phase beyond the read-only preflight.
      if (url.includes('AssociatedOwnerGroup') || url.includes('AssociatedMemberGroup')
          || url.includes('AssociatedVisitorGroup') || url.includes('/owner')) {
        return { d: { Id: 3, Title: 'Site Owners', PrincipalType: 8 } };
      }
      if (url.includes('/users')) return { d: { results: [] } };
      if (url.includes('sitegroups/getbyname')) {
        return { d: {
          Id: 9, Title: 'List Maintainer', PrincipalType: 8,
          Description: 'Test group.', AllowMembersEditMembership: false,
          AllowRequestToJoinLeave: false, AutoAcceptRequestToJoinLeave: false,
          OnlyAllowMembersViewMembership: false } };
      }
      if (url.includes('roledefinitions')) return { d: { results: [{ Id: 1 }] } };
      // A list probe: the list exists, matching the declared shape.
      if (url.includes('getbytitle') && url.includes('BaseTemplate')) {
        return { d: {
          Id: '22222222-2222-2222-2222-222222222222',
          Title: 'adopted', BaseTemplate: 100, ContentTypesEnabled: false,
          EnableVersioning: true, EnableMinorVersions: false,
          MajorVersionLimit: 500, ValidationFormula: null, ValidationMessage: null } };
      }
      return { d: { results: [] } };
    };
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      calls.push({ url: u, method: opts.method || 'GET', body: opts.body });
      // Apply writes, exactly as SharePoint would, so readbacks converge.
      if ((opts.method || 'GET') === 'POST' && opts.body && u.includes('/fields')) {
        const parsed = JSON.parse(opts.body);
        const listTitle = listOf(u);
        const named = (u.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
        if (named === 'Title') {
          for (const k of ['Sealed', 'Required', 'Description', 'DefaultValue']) {
            if (parsed[k] !== undefined) titleState(listTitle)[k] = parsed[k];
          }
        } else if (named) {
          const key = `${listTitle} ${named}`;
          const f = created[key];
          if (f) {
            if (parsed.Sealed != null) f.Sealed = parsed.Sealed;
            if (parsed.ClientValidationFormula != null) f.__cvf = parsed.ClientValidationFormula;
            if (parsed.ValidationFormula != null) f.__vf = parsed.ValidationFormula;
            if (parsed.ValidationMessage != null) f.__vm = parsed.ValidationMessage;
            for (const k of ['Description', 'Required', 'DefaultValue', 'CustomFormatter']) {
              if (parsed[k] !== undefined) f[k] = parsed[k];
            }
          }
        } else if (parsed.Title) {
          created[`${listTitle} ${parsed.Title}`] = fieldShape(listTitle, parsed.Title, parsed);
        }
      }
      const payload = body(u, opts);
      const absent = payload && payload.error;
      return {
        ok: !absent, status: absent ? 400 : 200,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
    globalThis.__calls = calls;
""")


def _run_deploy(harness: str, tail: str) -> str:
    script = harness + "\n" + _deploy_js().replace("})();", tail).replace(
        "(async () => {", "((async () => {", 1,
    )
    return _run(script)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_sealed_builtin_title_does_not_abort_every_list() -> None:
    """`assertFieldImmutableShape` throws when a field is sealed and
    `field.seal` is falsy. Both synthetic Title objects omitted the key, so
    against a site whose Title is sealed EVERY list failed preflight — and
    the tool could not self-heal, because the maintenance unseal walks
    declared columns only and Title is not one. A site that ever sealed
    Title was permanently un-deployable."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    seal_errors = [
        err for err in (summary.get("errors") or []) if "sealed" in str(err)
    ]
    assert not seal_errors, f"a sealed built-in Title aborted the run: {seal_errors}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_sealed_title_is_unsealed_for_the_run() -> None:
    """Not aborting is not enough to make the site deployable: Phase 2.1
    writes list.title_patch to Title, and a sealed column discards writes.
    The maintenance unseal walked declared columns only, and Title is not
    one, so the run could never converge. It must open Title too."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert line is not None, f"harness produced no call log:\n{output[-3000:]}"
    calls = json.loads(line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Title')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert False in seal_writes, "a sealed Title was never unsealed for the run"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_adopted_run_reaches_the_write_phases() -> None:
    """Guards the reach of the harness itself.

    The original mock answered every field probe as absent and every list
    probe as malformed, so the run aborted in the read-only preflight: no
    phase past 1.1 had ever executed in a test, which is how a bug in the
    Phase 2.1 field reconcile shipped in a green suite. If a future change
    quietly shortens this run, the coverage disappears silently — so the
    reach is asserted rather than assumed."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    for phase in ("1.1", "1.2", "1.3", "1.4", "2.1"):
        assert phase in reached, f"phase {phase} not reached: {reached}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_protection_restores_only_the_titles_prepare_unsealed(tmp_path: Path) -> None:
    """The tool does not own Title's seal state, so a run that unseals one
    must hand back what it found: it must neither seal a Title it found
    unsealed nor leave open one it opened to write."""
    js = _declared_deploy_js(
        tmp_path,
        "form_visibility:\n  Escalation:\n    columns:\n      Note: hidden\n",
    )
    script = _ADOPTED_HARNESS + "\n" + js.replace(
        "})();", "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    ).replace("(async () => {", "((async () => {", 1)
    line = next(
        (ln for ln in _run(script).splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert line is not None, "harness produced no call log"
    calls = json.loads(line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Title')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert seal_writes[0] is False, f"PREPARE did not unseal Title: {seal_writes}"
    assert seal_writes[-1] is True, f"the run left Title unsealed: {seal_writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_declared_run_completes_every_phase_cleanly(tmp_path: Path) -> None:
    """The end-to-end guard, and the one that gives the others their value.

    The original mock aborted in the read-only preflight, so no phase past
    1.1 had ever executed in a test — which is how a bug in the Phase 2.1
    field reconcile shipped in a green suite. This run adopts an existing
    site, unseals, creates, reconciles declared formulas, seals and seeds,
    and must finish with no errors and no abort. If a future change
    shortens it, the coverage disappears silently unless this fails.
    """
    js = _declared_deploy_js(
        tmp_path,
        "form_visibility:\n  Escalation:\n    columns:\n      Note: hidden\n",
    )
    script = _ADOPTED_HARNESS + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    for phase in ("1.1", "1.4", "2.1", "3.1", "4.1", "5.1"):
        assert phase in reached, f"phase {phase} not reached: {reached}"


def test_generated_deploy_js_carries_no_control_characters() -> None:
    """deploy.js is pasted into a browser console by hand.

    A stray control character survives templating, the golden file and
    every text-mode diff — git reports the file as binary and shows
    nothing. Writing this fix, a literal NUL reached a template's
    executable code from an editing tool and rode into the generated
    script; the suite was green. Cheap to assert, invisible otherwise.
    """
    js = _deploy_js()
    stray = sorted({
        ch for ch in js
        if ord(ch) < 32 and ch not in "\n\r\t"
    })
    assert not stray, f"control characters in generated deploy.js: {[hex(ord(c)) for c in stray]}"


def _declared_deploy_js(tmp_path: Path, section: str) -> str:
    """deploy.js for an all-text schema that actually declares a formula.

    The shipped fixture declares none, so enforceDeclaredFormulas returns
    before doing anything and cannot be exercised through it. All-Text
    columns keep the run clear of the derived-property probes the mock does
    not answer.
    """
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml
    from dbml_sharepoint.model.release import load_release

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Escalation {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  Note nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Escalation: { kind: List, base_template: 100, site_role: default }\n" + section,
        encoding="utf-8",
    )
    return generate_deploy_js(
        schema=parse_dbml(tmp_path / "s.dbml"),
        bundle=load_mapping(tmp_path / "m.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_overwriting_a_declared_formula_logs_the_prior_value(tmp_path: Path) -> None:
    """`before` was read, compared and discarded; on success nothing was
    logged, so a deploy that removed or rewrote an existing formula left no
    record of what had been there. Under `reconcile: exact` an undeclared
    column's formula is cleared outright — exactly the case where the prior
    value is the only thing anyone would want back."""
    harness = _ADOPTED_HARNESS.replace(
        "ClientValidationFormula: f.__cvf == null ? null : f.__cvf,",
        "ClientValidationFormula: f.__cvf == null ? "
        "\"=if([$WasHere] != '', 'true', 'false')\" : f.__cvf,",
    )
    js = _declared_deploy_js(
        tmp_path,
        "form_visibility:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Note: hidden\n",
    )
    script = harness + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    replaced = [ln for ln in output.splitlines() if "declared formulas" in ln]
    assert replaced, f"no prior value logged:\n{output[-2500:]}"
    assert any("WasHere" in ln for ln in replaced), replaced
