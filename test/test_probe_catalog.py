from __future__ import annotations

import json
import re
from typing import Any

from _paths import MANUAL

CATALOG = MANUAL / "probe-catalog.json"
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


def _catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _static_finding_ids(source: str) -> set[str]:
    ids = set(re.findall(r"^\s*expect\(\s*['\"]([^'\"]+)", source, re.MULTILINE))
    ids |= set(re.findall(r"^\s*record\(\s*['\"]([^'\"]+)", source, re.MULTILINE))
    ids -= {finding for finding in ids if finding.startswith("BOOT")}
    if "const CANDIDATES = [" in source:
        candidate_block = source.split("const CANDIDATES = [", 1)[1].split("];", 1)[0]
        ids |= set(re.findall(r"['\"](X[1-9][0-9]*)['\"]", candidate_block))
    return ids


def test_probe_catalog_covers_the_exact_manual_inventory() -> None:
    catalog = _catalog()
    descriptors = catalog["probes"]
    catalogued = {descriptor["file"] for descriptor in descriptors}
    actual = {path.name for path in MANUAL.glob("*.js")}

    assert catalog["schema_version"] == "1.0"
    assert len(descriptors) == 24
    assert catalogued == actual


def test_probe_catalog_declares_every_static_finding_once() -> None:
    for descriptor in _catalog()["probes"]:
        source = (MANUAL / descriptor["file"]).read_text(encoding="utf-8")
        declared = [
            finding
            for scenario in descriptor["scenarios"]
            for finding in scenario["findings"]
        ]
        assert len(declared) == len(set(declared)), descriptor["file"]
        assert set(declared) == _static_finding_ids(source), descriptor["file"]


def test_visible_scenarios_declare_typed_capture_states_and_controls() -> None:
    for descriptor in _catalog()["probes"]:
        for scenario in descriptor["scenarios"]:
            assert scenario["pattern"] in ALL_PATTERNS
            states = scenario["states"]
            if scenario["pattern"] in VISIBLE_PATTERNS:
                assert states, f"{descriptor['file']}:{scenario['id']}"
                roles = [state["role"] for state in states]
                assert len(roles) == len(set(roles))
                for state in states:
                    assert state["page"]
                    assert state["assertions"]
                assert scenario["controls"], (
                    f"{descriptor['file']}:{scenario['id']} has no control"
                )
            else:
                assert states == []


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
