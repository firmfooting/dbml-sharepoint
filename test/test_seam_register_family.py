# test/test_seam_register_family.py
"""seam-register rules the build cannot see.

The confidence rule is a governance check, not a save rule, so nothing
stops the demonstration rows modelling a *Verified* service with no
evidence behind it. And a "Provider not named" view is the only thing that
stands in for a save rule on each provider lookup, so every lookup needs
one, over exactly the sides the form shows it for, or a row that owes a
provider drops out of sight. Both were found in review of the family's
first pull request.
"""

from typing import Any
from urllib.parse import unquote

import yaml
from _paths import SOLUTION_TEMPLATES

MAPPING = SOLUTION_TEMPLATES / "seam-register" / "20-configure" / "mapping.yaml"
PROVIDER_SIDES = {"Provider", "Third party", "Shared"}


def _mapping() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
    return loaded


def _evidence_by_service() -> dict[str, list[dict[str, Any]]]:
    by_service: dict[str, list[dict[str, Any]]] = {}
    for row in _mapping()["demo_items"]["Evidence"]:
        values = row["values"]
        by_service.setdefault(values["Service"]["demo_ref"], []).append(values)
    return by_service


def test_no_seeded_service_claims_more_confidence_than_its_evidence() -> None:
    """A service with no evidence rows is Assumed by definition; Verified
    needs two agreeing rows from different sides about the same column, or
    one System data row (50-govern/governance.md)."""
    evidence = _evidence_by_service()
    problems: list[str] = []
    for row in _mapping()["demo_items"]["Service"]:
        key, confidence = row["key"], row["values"]["Confidence"]
        rows = evidence.get(key, [])
        if confidence != "Assumed" and not rows:
            problems.append(f"{key} is {confidence} with no evidence row")
        if confidence == "Verified":
            agreeing = [e for e in rows if not e.get("Contradicts", False)]
            system = any(e["EvidenceType"] == "System data" for e in agreeing)
            sides_by_field: dict[str, set[str]] = {}
            for e in agreeing:
                if e.get("SupportsField"):
                    sides_by_field.setdefault(e["SupportsField"], set()).add(e["SourceSide"])
            if not system and not any(len(s) >= 2 for s in sides_by_field.values()):
                problems.append(
                    f"{key} is Verified without two sides agreeing on one column: {sides_by_field}"
                )
    assert not problems, problems


def _check_branches(view: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    """{provider column: {null test: sides}} from a provider-to-check filter."""
    found: dict[str, dict[str, set[str]]] = {}
    for branch in view["where"][0]["any_of"]:
        side, provider = branch["all_of"]
        found.setdefault(provider["field"], {})[provider["op"]] = set(side["value"])
    return found


# Service has two, and DocumentRequest, Interview and Incident one each.
PROVIDER_LOOKUPS = {
    "Service": {"RunByProvider", "SupportProvider"},
    "DocumentRequest": {"HolderProvider"},
    "Interview": {"IntervieweeProvider"},
    "Incident": {"ResolverProvider"},
}


def test_no_provider_lookup_is_ever_hidden_on_the_form() -> None:
    """A hidden lookup can keep a value nobody can see to clear, and whether
    a self-referencing show rule prevents that has never been measured."""
    visibility = _mapping()["form_visibility"]
    hidden = {
        (entity, column)
        for entity, columns in PROVIDER_LOOKUPS.items()
        for column in columns
        if column in visibility.get(entity, {}).get("columns", {})
    }
    assert not hidden, hidden


def test_every_provider_lookup_has_a_check_view_for_both_gaps() -> None:
    """Owed and none named, and named on a side that has none."""
    views = _mapping()["views"]
    for entity, columns in PROVIDER_LOOKUPS.items():
        checked: dict[str, dict[str, set[str]]] = {}
        for view in views[entity]:
            if view["title"].endswith("rovider to check"):
                checked.update(_check_branches(view))
        assert set(checked) == columns, entity
        expected = {"is_null": PROVIDER_SIDES, "is_not_null": {"Us", "Unknown"}}
        for column in columns:
            assert checked[column] == expected, column


def test_every_seeded_link_into_the_library_names_a_seeded_file() -> None:
    """A link to a file the seed never uploads made a row look Held."""
    demo = _mapping()["demo_items"]
    seeded = {
        f"{row['file']['folder']}/{row['file']['name']}" for row in demo["Artefact"]
    }
    marker = "/SEAM_Artefact/"
    links = [
        value["url"]
        for rows in demo.values()
        for row in rows
        for value in row["values"].values()
        if isinstance(value, dict) and marker in value.get("url", "")
    ]
    assert links, "no seeded row links into the library"
    missing = [u for u in links if unquote(u.split(marker, 1)[1]) not in seeded]
    assert not missing, missing
