# test/test_seam_register_family.py
"""seam-register rules the build cannot see.

The confidence rule is a governance check, not a save rule, so nothing
stops the demonstration rows modelling a *Verified* service with no
evidence behind it. A "Provider not named" view is the only thing that
stands in for a save rule on each provider lookup. And fields that appear
with a status keep their value when hidden again, so no save rule may
forbid one. All of it was found in review of the family's first pull
request.
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
    needs two agreeing rows from different known sides about the same
    column, or one System data row, and no row that contradicts
    (50-govern/governance.md: a disagreement moves it back to Claimed)."""
    evidence = _evidence_by_service()
    problems: list[str] = []
    for row in _mapping()["demo_items"]["Service"]:
        key, confidence = row["key"], row["values"]["Confidence"]
        rows = evidence.get(key, [])
        if confidence != "Assumed" and not rows:
            problems.append(f"{key} is {confidence} with no evidence row")
        if confidence == "Verified":
            if any(e.get("Contradicts", False) for e in rows):
                problems.append(f"{key} is Verified with contradicting evidence")
            agreeing = [e for e in rows if not e.get("Contradicts", False)]
            system = any(e["EvidenceType"] == "System data" for e in agreeing)
            sides_by_field: dict[str, set[str]] = {}
            for e in agreeing:
                # Unknown names no source, so it corroborates nothing.
                if e.get("SupportsField") and e["SourceSide"] != "Unknown":
                    sides_by_field.setdefault(e["SupportsField"], set()).add(e["SourceSide"])
            if not system and not any(len(s) >= 2 for s in sides_by_field.values()):
                problems.append(
                    f"{key} is Verified without two sides agreeing on one column: {sides_by_field}"
                )
    assert not problems, problems


# Service has two, and DocumentRequest, Interview and Incident one each.
PROVIDER_LOOKUPS = {
    "Service": {"RunByProvider", "SupportProvider"},
    "DocumentRequest": {"HolderProvider"},
    "Interview": {"IntervieweeProvider"},
    "Incident": {"ResolverProvider"},
}


def _not_named_branches(view: dict[str, Any]) -> dict[str, set[str]]:
    """{provider column: sides} from a Provider not named view's filter."""
    where = view["where"]
    branches = where[0].get("any_of", [{"all_of": where}])
    found: dict[str, set[str]] = {}
    for branch in branches:
        side, provider = branch["all_of"]
        assert provider["op"] == "is_null", provider
        found[provider["field"]] = set(side["value"])
    return found


def test_every_provider_lookup_has_a_not_named_view_over_its_shown_sides() -> None:
    mapping = _mapping()
    for entity, columns in PROVIDER_LOOKUPS.items():
        rules = mapping["form_visibility"][entity]["columns"]
        shown = {column: set(rules[column]["when"][0]["value"]) for column in columns}
        views = [v for v in mapping["views"][entity] if v["title"] == "Provider not named"]
        assert len(views) == 1, f"{entity} has no Provider not named view"
        assert _not_named_branches(views[0]) == shown == dict.fromkeys(columns, PROVIDER_SIDES)


def _leaves(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        return [leaf for item in node for leaf in _leaves(item)]
    if isinstance(node, dict) and "field" in node:
        return [node]
    if isinstance(node, dict):
        return [leaf for group in node.values() for leaf in _leaves(group)]
    return []


def test_no_save_rule_requires_a_hidden_field_to_be_empty() -> None:
    """A field a status or side hides keeps its old value when the row moves
    back, by design: the form stays uncluttered and reporting filters by
    status. So no save rule may test such a field for blank, or that row
    could never be saved again."""
    mapping = _mapping()
    problems: list[str] = []
    for entity, rules in mapping["form_visibility"].items():
        hidden = {c for c, r in rules["columns"].items() if isinstance(r, dict) and "when" in r}
        rule = mapping.get("list_validation", {}).get(entity)
        for leaf in _leaves(rule["when"] if rule else []):
            if leaf["field"] in hidden and leaf["op"] == "is_null":
                problems.append(f"{entity}.{leaf['field']}")
    assert not problems, problems


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

