from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, cast

from _paths import MANUAL

CATALOG = MANUAL / "probe-catalog.json"
SURFACES = MANUAL / "SURFACES.md"
#: A numbered surface heading in SURFACES.md, e.g. "### 1. `formula`: ...".
SURFACE_HEADING = re.compile(r"^### \d+\. `([a-z]+)`:", re.MULTILINE)
#: A quoted `<surface>.<scope>.<question>` id, for the probes that build their
#: checks from a table rather than writing each expect() out. Matching the
#: grammar rather than a mnemonic shape keeps a table entry that is not an id
#: (a column name, a human label) out of the set.
CHECK_ID_LITERAL = r"['\"]([a-z][a-z0-9]*\.[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*)['\"]"
VISIBLE_PATTERNS = {
    "single-visible-state",
    "state-matrix",
    "before-action-after",
    "identity-pair",
    "phased-threshold",
}
ALL_PATTERNS = VISIBLE_PATTERNS | {
    "machine-only",
    "delayed-reconciliation",
    "helper",
}
#: The five states in SURFACES.md, emitted beside the prose by every registry.
STATES = {"settled", "open", "awaiting-capture", "void", "needs-human"}
#: Visible scenarios with no control check to name. A ratchet, like
#: _reachability.NOT_YET_REACHED: entries come out as controls arrive, and one
#: going in needs a reason in the pull request. The three form-visibility
#: helpers register no checks at all, so they have no id to point at; A5 reads
#: a site collection feature state that nothing in its probe sets up.
VISIBLE_SCENARIOS_WITHOUT_A_CONTROL = {
    ("enterprise-reader-probe.js", "visible-findings"),
    ("form-visibility-evidence-probe.js", "ui-storage-sequence"),
    ("form-visibility-interactive.js", "ui-storage-sequence"),
    ("form-visibility-storage-probe.js", "ui-storage-sequence"),
}
#: Every result registry, and the table each one publishes.
REGISTRIES = [
    ("templates/_probe_harness.js.j2", "RESULTS"),
    ("templates/_probe_results_v1.js.j2", "results"),
    ("projected-lookup-probe.js", "RESULTS"),
]


def _catalog() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CATALOG.read_text(encoding="utf-8")))


def _surface_registry() -> dict[str, set[str]]:
    """The surface list and its probe membership, read from the authority file.

    SURFACES.md is the sole authority for the eleven surfaces, so the catalogue
    is checked against what that file says rather than against a second copy of
    the list kept here.
    """
    text = SURFACES.read_text(encoding="utf-8")
    headings = list(SURFACE_HEADING.finditer(text))
    registry: dict[str, set[str]] = {}
    for position, heading in enumerate(headings):
        following = headings[position + 1].start() if position + 1 < len(headings) else len(text)
        section = text[heading.start():following]
        listed = re.search(r"^Probes: (.+?)\n\n", section, re.MULTILINE | re.DOTALL)
        assert listed is not None, f"{heading.group(1)} lists no probes"
        registry[heading.group(1)] = set(re.findall(r"`([^`]+\.js)`", listed.group(1)))
    return registry


def _static_finding_ids(source: str) -> set[str]:
    ids = set(re.findall(r"^\s*expect\(\s*['\"]([^'\"]+)", source, re.MULTILINE))
    ids |= set(re.findall(r"^\s*record\(\s*['\"]([^'\"]+)", source, re.MULTILINE))
    ids -= {finding for finding in ids if finding.startswith("BOOT")}
    if "const CANDIDATES = [" in source:
        candidate_block = source.split("const CANDIDATES = [", 1)[1].split("];", 1)[0]
        ids |= set(re.findall(CHECK_ID_LITERAL, candidate_block))
    return ids


def _registry_module(relative: str) -> str:
    """A result registry as standalone JavaScript, with logging stubbed out.

    The registries are fragments of an IIFE and two of the three are Jinja, so
    the state block is sliced out rather than the file being executed whole.
    """
    source = (MANUAL / relative).read_text(encoding="utf-8")
    block = re.search(
        r"const OPEN_HEADS.*?(?=\n\s*const report = |\Z)", source, re.DOTALL
    )
    assert block is not None, relative
    return f"const log = () => {{}};\n{block.group(0)}"


def _run_javascript(source: str, expression: str) -> Any:
    node = shutil.which("node")
    assert node is not None
    completed = subprocess.run(  # noqa: S603 - executes repository-owned test code
        [node, "-e", f"{source}\nconsole.log(JSON.stringify({expression}));"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_probe_catalog_covers_the_exact_manual_inventory() -> None:
    catalog = _catalog()
    descriptors = catalog["probes"]
    catalogued = {descriptor["file"] for descriptor in descriptors}
    actual = {path.name for path in MANUAL.glob("*.js")}

    assert catalog["schema_version"] == "1.2"
    assert len(descriptors) == 38
    assert catalogued == actual


def test_probe_catalog_declares_the_surface_the_registry_files_each_probe_under() -> None:
    registry = _surface_registry()
    descriptors = _catalog()["probes"]

    assert len(registry) == 11
    assert set().union(*registry.values()) == {
        descriptor["file"] for descriptor in descriptors
    }
    for descriptor in descriptors:
        surface = descriptor.get("surface")
        assert surface in registry, f"{descriptor['file']} declares surface {surface!r}"
        assert descriptor["file"] in registry[surface], descriptor["file"]
        for scenario in descriptor["scenarios"]:
            assert scenario.get("surface") == surface, (
                f"{descriptor['file']}:{scenario['id']}"
            )


def test_probe_catalog_declares_every_static_finding_once() -> None:
    for descriptor in _catalog()["probes"]:
        source = (MANUAL / descriptor["file"]).read_text(encoding="utf-8")
        declared = [
            finding["id"]
            for scenario in descriptor["scenarios"]
            for finding in scenario["findings"]
        ]
        assert len(declared) == len(set(declared)), descriptor["file"]
        assert set(declared) == _static_finding_ids(source), descriptor["file"]


def test_control_and_dependency_references_name_checks_the_probe_registers() -> None:
    """A control is a check id, so a control that is not a check is a typo.

    Prose could not be wrong in this way and could not be followed either. The
    reference is the point of the id.
    """
    for descriptor in _catalog()["probes"]:
        source = (MANUAL / descriptor["file"]).read_text(encoding="utf-8")
        registered = _static_finding_ids(source)
        for scenario in descriptor["scenarios"]:
            where = f"{descriptor['file']}:{scenario['id']}"
            controls = scenario["controls"]
            assert len(controls) == len(set(controls)), where
            for control in controls:
                assert control in registered, f"{where} names control {control!r}"
            for finding in scenario["findings"]:
                depends_on = finding["depends_on"]
                assert len(depends_on) == len(set(depends_on)), f"{where}:{finding['id']}"
                for control in depends_on:
                    assert control != finding["id"], f"{where}:{finding['id']} on itself"
                    assert control in registered, (
                        f"{where}:{finding['id']} depends on {control!r}"
                    )


def test_visible_scenarios_declare_typed_capture_states_and_controls() -> None:
    without_a_control = set()
    for descriptor in _catalog()["probes"]:
        for scenario in descriptor["scenarios"]:
            assert scenario["pattern"] in ALL_PATTERNS
            states = scenario["states"]
            if scenario["pattern"] not in VISIBLE_PATTERNS:
                assert states == []
                continue
            assert states, f"{descriptor['file']}:{scenario['id']}"
            roles = [state["role"] for state in states]
            assert len(roles) == len(set(roles))
            for state in states:
                assert state["page"]
                assert state["assertions"]
            if not scenario["controls"]:
                without_a_control.add((descriptor["file"], scenario["id"]))

    assert without_a_control == VISIBLE_SCENARIOS_WITHOUT_A_CONTROL


def test_native_index_voids_the_rows_a_failed_control_would_orphan() -> None:
    """The case SURFACES.md names: a failed control voids its dependants.

    `control-index-readable` reading false means a property read cannot answer
    for any column, so the four system-column rows are not open questions, and
    `odata-null-found-list` is not a null-test result when the comparison
    control was refused.
    """
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "native-index-probe.js"
    )
    depends_on = {
        finding["id"]: finding["depends_on"]
        for scenario in descriptor["scenarios"]
        for finding in scenario["findings"]
    }
    source = (MANUAL / "native-index-probe.js").read_text(encoding="utf-8")

    control = "scale.native-idx.control-index-readable"
    comparison = "scale.index.odata-comparison-found-list"
    assert depends_on == {
        comparison: [],
        control: [],
        "scale.native-idx.author-property": [control],
        "scale.native-idx.created-property": [control],
        "scale.native-idx.editor-property": [control],
        "scale.native-idx.modified-property": [control],
        "scale.index.odata-null-found-list": [comparison],
    }
    assert set(next(
        scenario["controls"] for scenario in descriptor["scenarios"]
    )) == {control, comparison}
    # The states this probe PASSES, not every mention of the word: report()'s
    # tally reads `r.state === 'void'` in every probe the harness renders.
    voided = [
        line for line in source.splitlines()
        if "'void'" in line and "r.state" not in line
    ]
    assert len(voided) == 2, voided


def test_every_registry_emits_a_state_from_the_shared_vocabulary() -> None:
    heads = [
        "NOT ESTABLISHED",
        "SHORT: 3 of 12 disjuncts",
        "MANUAL",
        "NOT REACHED",
        "PASS",
        "FAIL",
        "VOID",
    ]
    for relative, _ in REGISTRIES:
        module = f"{_registry_module(relative)}\nconst heads = {json.dumps(heads)};"

        classified = _run_javascript(module, "heads.map(stateFor)")

        # VOID classifying as settled is why record() takes an explicit state:
        # a probe that voids a row passes it rather than spelling it in prose.
        assert classified == [
            "open",
            "open",
            "awaiting-capture",
            "awaiting-capture",
            "settled",
            "settled",
            "settled",
        ], relative
        assert set(classified) <= STATES


def test_every_registry_seeds_open_and_lets_a_probe_override_the_state() -> None:
    for relative, table in REGISTRIES:
        module = (
            f"{_registry_module(relative)}\n"
            "expect('A', 'never reached');\n"
            # Empty evidence: two of the three registries echo it to stdout,
            # which would land in the JSON this reads back.
            "record('B', 'voided', 'NOT ESTABLISHED', '', 'void');\n"
            "record('C', 'answered', 'PASS', '');\n"
        )

        rows = _run_javascript(module, f"{table}.map((r) => [r.id, r.state])")

        assert rows == [["A", "open"], ["B", "void"], ["C", "settled"]], relative


def test_probe_catalog_makes_side_effects_and_cleanup_explicit() -> None:
    for descriptor in _catalog()["probes"]:
        assert descriptor["harness"] in {"shared-v1", "shared-v2", "legacy", "helper"}
        assert descriptor["authority"] in {
            "read-only",
            "allow-writes",
            "allow-legacy-writes",
            "interactive",
        }
        assert descriptor["cleanup"]["policy"] in {
            "none",
            "before",
            "after",
            "manual",
            "delayed",
        }
        assert isinstance(descriptor["writes"], list)
        assert isinstance(descriptor["prerequisites"], list)


def test_hyperlink_probe_uses_versioned_shared_transport_and_results() -> None:
    template = (
        MANUAL / "templates" / "hyperlink-validation-operand-probe.js.j2"
    ).read_text(encoding="utf-8")

    assert '{% include "_probe_core_v2.js.j2" %}' in template
    assert '{% include "_probe_results_v1.js.j2" %}' in template
    assert "async function fetchWithRetry" not in template
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "hyperlink-validation-operand-probe.js"
    )
    assert descriptor["harness"] == "shared-v2"


def test_hyperlink_probe_refuses_to_reset_a_foreign_same_title_list() -> None:
    template = (
        MANUAL / "templates" / "hyperlink-validation-operand-probe.js.j2"
    ).read_text(encoding="utf-8")

    fixture = (
        MANUAL / "templates" / "_probe_list_fixture_v1.js.j2"
    ).read_text(encoding="utf-8")
    assert "OWNERSHIP_DESCRIPTION" in template
    assert "refusing to modify it" in fixture
    assert '{% include "_probe_list_fixture_v1.js.j2" %}' in template
    assert "prepareOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION, CLEANUP_AT_END)" in template


def test_hyperlink_probe_marks_refused_downstream_questions_not_applicable() -> None:
    template = (
        MANUAL / "templates" / "hyperlink-validation-operand-probe.js.j2"
    ).read_text(encoding="utf-8")

    refusal_branch = template.split("if (set1.ok)", 1)[1]
    assert "'NOT APPLICABLE'" in refusal_branch
    assert "'NOT REACHED'" not in refusal_branch


def test_hyperlink_results_require_explicit_sharepoint_behavioral_refusal() -> None:
    decisions = (
        MANUAL / "templates" / "_hyperlink_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    statuses = [400, 404, 401, 403, 408, 429, 500, 502, 503, 504]
    decisions += f"\nconst statuses = {json.dumps(statuses)};"

    observed = _run_javascript(
        decisions,
        "statuses.map((status) => classifyAttempt("
        "{ ok: false, status, error: 'failure' }, 'ACCEPTED', 'FIRED'))",
    )

    assert observed == ["FIRED"] + ["NOT ESTABLISHED"] * 9


def test_hyperlink_non_behavioral_failures_never_claim_refusal_semantics() -> None:
    decisions = (
        MANUAL / "templates" / "_hyperlink_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    statuses = [404, 401, 403, 408, 429, 500, 502, 503, 504]
    decisions += f"\nconst statuses = {json.dumps(statuses)};"

    details = _run_javascript(
        decisions,
        "statuses.map((status) => describeAttempt("
        "{ ok: false, status, error: 'failure' }, 'accepted', 'formula refused row'))",
    )

    assert all(detail.startswith("NOT ESTABLISHED:") for detail in details)
    assert all("formula refused row" not in detail for detail in details)


def test_hyperlink_final_reduction_is_tri_state_and_neutral_when_unestablished() -> None:
    decisions = (
        MANUAL / "templates" / "_hyperlink_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    cases = [
        ["ACCEPTED", "FIRED", "PASSED"],
        ["REFUSED", "NOT APPLICABLE", "NOT APPLICABLE"],
        ["ACCEPTED", "DID NOT FIRE", "PASSED"],
        ["NOT ESTABLISHED", "NOT APPLICABLE", "NOT APPLICABLE"],
        ["ACCEPTED", "NOT ESTABLISHED", "PASSED"],
        ["ACCEPTED", "FIRED", "NOT ESTABLISHED"],
        ["ACCEPTED", "NOT ESTABLISHED", "REFUSED EVERYTHING"],
        ["ACCEPTED", "DID NOT FIRE", "NOT ESTABLISHED"],
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    verdicts = _run_javascript(
        decisions,
        "cases.map(([q1, q2, q3]) => hyperlinkOperandVerdict({ Q1: q1, Q2: q2, Q3: q3 }))",
    )

    assert [verdict["operandUsable"] for verdict in verdicts] == [
        "YES",
        "NO",
        "NO",
        "NOT ESTABLISHED",
        "NOT ESTABLISHED",
        "NOT ESTABLISHED",
        "NOT ESTABLISHED",
        "NOT ESTABLISHED",
    ]
    assert all(
        verdict["guidance"].startswith("Evidence is inconclusive.")
        for verdict in verdicts[3:]
    )
    assert all("Leave the build refusal" not in verdict["guidance"] for verdict in verdicts[3:])


def test_shared_v2_transport_preserves_success_bodies_and_accept_override() -> None:
    core = (
        MANUAL / "templates" / "_probe_core_v2.js.j2"
    ).read_text(encoding="utf-8")

    assert "async function get(suffix, accept)" in core
    assert "d: parsed.d !== undefined ? parsed.d : parsed" in core
    assert "return { ok: true, status: response.status, error: null, d };" in core


def test_multi_value_probe_uses_versioned_shared_transport_and_results() -> None:
    template = (
        MANUAL / "templates" / "multi-value-probe.js.j2"
    ).read_text(encoding="utf-8")

    assert '{% include "_probe_core_v2.js.j2" %}' in template
    assert '{% include "_probe_results_v1.js.j2" %}' in template
    assert "async function fetchWithRetry" not in template
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "multi-value-probe.js"
    )
    assert descriptor["harness"] == "shared-v2"


def test_view_aggregations_probe_uses_versioned_shared_transport_and_results() -> None:
    template = (
        MANUAL / "templates" / "view-aggregations-probe.js.j2"
    ).read_text(encoding="utf-8")

    assert '{% include "_probe_core_v2.js.j2" %}' in template
    assert '{% include "_probe_results_v1.js.j2" %}' in template
    assert "async function fetchWithRetry" not in template
    assert "OWNERSHIP_DESCRIPTION" in template
    assert '{% include "_probe_list_fixture_v1.js.j2" %}' in template
    assert "prepareOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION, CLEANUP_AT_END)" in template
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "view-aggregations-probe.js"
    )
    assert descriptor["harness"] == "shared-v2"


def test_view_aggregation_manual_result_requires_final_on_status() -> None:
    decisions = (
        MANUAL / "templates" / "_view_aggregation_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    base = {
        "setupReady": True,
        "writeOk": True,
        "aggregationXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "expectedXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "seedValues": [1, 3],
        "viewFieldNames": ["Amount", "SecondAmount"],
        "expectedViewFields": ["Amount", "SecondAmount"],
        "fieldTitle": "Second Amount Display",
        "expectedFieldTitle": "Second Amount Display",
    }
    cases = [
        base,
        {**base, "aggregationStatus": None},
        {**base, "aggregationStatus": "Off"},
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    observed = _run_javascript(
        decisions,
        "cases.map((controls) => aggregationManualOutcome(controls))",
    )

    assert observed == ["NOT ESTABLISHED", "NOT ESTABLISHED", "NOT ESTABLISHED"]


def test_view_aggregation_manual_result_requires_exact_seed_readback() -> None:
    decisions = (
        MANUAL / "templates" / "_view_aggregation_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    base = {
        "setupReady": True,
        "writeOk": True,
        "aggregationXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "expectedXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "aggregationStatus": "On",
        "viewFieldNames": ["Amount", "SecondAmount"],
        "expectedViewFields": ["Amount", "SecondAmount"],
        "fieldTitle": "Second Amount Display",
        "expectedFieldTitle": "Second Amount Display",
    }
    cases = [
        {**base, "seedValues": [1, 3]},
        {**base, "seedValues": None},
        {**base, "seedValues": [1, 4]},
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    observed = _run_javascript(
        decisions,
        "cases.map((controls) => aggregationManualOutcome(controls))",
    )

    assert observed == ["MANUAL", "NOT ESTABLISHED", "NOT ESTABLISHED"]


def test_view_aggregation_manual_result_requires_final_view_membership() -> None:
    decisions = (
        MANUAL / "templates" / "_view_aggregation_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    base = {
        "setupReady": True,
        "writeOk": True,
        "aggregationXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "expectedXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "aggregationStatus": "On",
        "seedValues": [1, 3],
        "expectedViewFields": ["Amount", "SecondAmount"],
        "fieldTitle": "Second Amount Display",
        "expectedFieldTitle": "Second Amount Display",
    }
    cases = [
        {**base, "viewFieldNames": ["Title", "Amount", "SecondAmount"]},
        {**base, "viewFieldNames": ["Title", "Amount"]},
        {**base, "viewFieldNames": None},
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    observed = _run_javascript(
        decisions,
        "cases.map((controls) => aggregationManualOutcome(controls))",
    )

    assert observed == ["MANUAL", "NOT ESTABLISHED", "NOT ESTABLISHED"]


def test_view_aggregation_manual_result_requires_persisted_renamed_title() -> None:
    decisions = (
        MANUAL / "templates" / "_view_aggregation_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    base = {
        "setupReady": True,
        "writeOk": True,
        "aggregationXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "expectedXml": '<FieldRef Name="Amount" Type="SUM"/>',
        "aggregationStatus": "On",
        "seedValues": [1, 3],
        "viewFieldNames": ["Title", "Amount", "SecondAmount"],
        "expectedViewFields": ["Amount", "SecondAmount"],
        "expectedFieldTitle": "Second Amount Display",
    }
    cases = [
        {**base, "fieldTitle": "Second Amount Display"},
        {**base, "fieldTitle": "SecondAmount"},
        {**base, "fieldTitle": None},
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    observed = _run_javascript(
        decisions,
        "cases.map((controls) => aggregationManualOutcome(controls))",
    )

    assert observed == ["MANUAL", "NOT ESTABLISHED", "NOT ESTABLISHED"]


def test_view_aggregation_probe_wires_authoritative_final_readbacks() -> None:
    template = (
        MANUAL / "templates" / "view-aggregations-probe.js.j2"
    ).read_text(encoding="utf-8")

    assert "const initialViewFields = await get(" in template
    assert "const finalViewFields = await get(" in template
    assert "/viewfields`" in template
    assert "?$select=InternalName,Title`" in template
    assert "viewFieldNames: finalViewFieldNames" in template
    assert "fieldTitle: renamedField.d?.Title" in template
    assert "expectedFieldTitle: SECOND_DISPLAY" in template


def test_form_visibility_probe_uses_shared_v2_and_safe_setup_default() -> None:
    template = (
        MANUAL / "templates" / "form-visibility-probe.js.j2"
    ).read_text(encoding="utf-8")

    assert '{% include "_probe_core_v2.js.j2" %}' in template
    assert '{% include "_probe_results_v1.js.j2" %}' in template
    assert "const RECHECK_ONLY = false;" in template
    assert "OWNERSHIP_DESCRIPTION" in template
    assert "refusing to modify it" in template
    assert "const PROBE_WRITES = !RECHECK_ONLY || CLEANUP_AT_END;" in template
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "form-visibility-probe.js"
    )
    assert descriptor["harness"] == "shared-v2"


def test_form_visibility_q6_recheck_and_catalogue_define_complete_visible_evidence() -> None:
    template = (
        MANUAL / "templates" / "form-visibility-probe.js.j2"
    ).read_text(encoding="utf-8")
    recheck = template.split("if (RECHECK_ONLY)", 1)[1].split("// === Setup ===", 1)[0]

    assert re.search(r"record\(\s*'form\.panel\.edit-columns-writes-attributes'", recheck)
    assert "record(`RECHECK." not in recheck
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "form-visibility-probe.js"
    )
    visible = next(
        scenario for scenario in descriptor["scenarios"]
        if scenario["id"] == "visible-findings"
    )
    assert visible["findings"] == [
        {"id": "form.panel.edit-columns-writes-attributes", "depends_on": []}
    ]
    assert [state["role"] for state in visible["states"]] == [
        "panel-before",
        "panel-action",
        "new-after",
        "edit-after",
        "display-after",
    ]


def test_multi_value_c14_exposes_a_capturable_view_and_retains_machine_replay() -> None:
    template = (
        MANUAL / "templates" / "multi-value-probe.js.j2"
    ).read_text(encoding="utf-8")
    c14 = template.split("// === multichoice-chain-selects (C14):", 1)[1].split(
        "// === multichoice-operand (V1):", 1
    )[0]

    assert "$select=Title,ViewQuery,ServerRelativeUrl" in c14
    assert "const chainColumnOnView = chainStored" in c14
    assert "const chainViewUrl = chainStored?.ServerRelativeUrl || null;" in c14
    assert "const c14Outcome = chainedViewOutcome({" in c14
    assert "columnOnViewOk: chainColumnOnView.ok" in c14
    assert "OPEN ${window.location.origin}${chainViewUrl}" in c14
    assert "chainReplay" in c14
    assert (
        "return { results, winningShape: winningShape?.name || null, viewUrl, "
        "chainViewUrl };" in template
    )


def test_multi_value_c14_failed_controls_produce_neutral_unestablished_detail() -> None:
    decisions = (
        MANUAL / "templates" / "_multi_value_results_v1.js.j2"
    ).read_text(encoding="utf-8")
    base = {
        "fixtureUsable": True,
        "viewCreateOk": True,
        "viewReadOk": True,
        "storedViewQuery": "<Where><Or>...</Or></Where>",
        "sentOk": True,
        "sentTitles": ["R1", "R2"],
        "replayOk": True,
        "replayTitles": ["R1", "R2"],
        "columnOnViewOk": True,
        "viewUrl": "/Lists/probe/view.aspx",
    }
    cases = [
        base,
        {**base, "replayTitles": ["R1"]},
        {**base, "fixtureUsable": False},
        {**base, "viewCreateOk": False},
        {**base, "viewReadOk": False},
        {**base, "storedViewQuery": None},
        {**base, "sentOk": False},
        {**base, "replayOk": False},
        {**base, "columnOnViewOk": False},
        {**base, "viewUrl": None},
    ]
    decisions += f"\nconst cases = {json.dumps(cases)};"

    outcomes = _run_javascript(
        decisions,
        "cases.map((controls) => chainedViewOutcome(controls))",
    )

    assert [outcome["observed"] for outcome in outcomes[:2]] == ["MANUAL", "CHANGED"]
    assert all(outcome["observed"] == "NOT ESTABLISHED" for outcome in outcomes[2:])
    assert all(
        outcome["detail"].startswith("NOT ESTABLISHED:") for outcome in outcomes[2:]
    )
    assert all("Storage changed" not in outcome["detail"] for outcome in outcomes[2:])


def test_owned_form_and_multi_value_fixture_cleanup_recycles_with_exact_ownership() -> None:
    for name, marker in [
        ("form-visibility-probe.js.j2", "OWNERSHIP_DESCRIPTION"),
        ("multi-value-probe.js.j2", "PROBE_DESCRIPTION"),
    ]:
        template = (MANUAL / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "_probe_list_fixture_v1.js.j2" %}' in template
        assert f"recycleOwnedList(PROBE_LIST, {marker})" in template
        assert "deleteProbeList" not in template


def test_calculated_operand_probe_uses_shared_v2_and_exact_fixture_ownership() -> None:
    template = (
        MANUAL / "templates" / "calculated-operand-probe.js.j2"
    ).read_text(encoding="utf-8")

    fixture = (
        MANUAL / "templates" / "_probe_list_fixture_v1.js.j2"
    ).read_text(encoding="utf-8")
    assert '{% include "_probe_core_v2.js.j2" %}' in template
    assert '{% include "_probe_results_v1.js.j2" %}' in template
    assert '{% include "_probe_list_fixture_v1.js.j2" %}' in template
    assert '{% include "_probe_harness.js.j2" %}' not in template
    assert "OWNERSHIP_DESCRIPTION" in template
    assert "refusing to modify it" in fixture
    descriptor = next(
        probe for probe in _catalog()["probes"]
        if probe["file"] == "calculated-operand-probe.js"
    )
    assert descriptor["harness"] == "shared-v2"
