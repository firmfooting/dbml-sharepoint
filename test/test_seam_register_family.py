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


def _not_named_branches(view: dict[str, Any]) -> dict[str, set[str]]:
    """{provider column: sides} from a Provider not named view's filter."""
    where = view["where"]
    branches = where[0].get("any_of", [{"all_of": where}])
    return {b["all_of"][1]["field"]: set(b["all_of"][0]["value"]) for b in branches}


def test_every_provider_lookup_has_a_not_named_view_over_its_shown_sides() -> None:
    mapping = _mapping()
    lookups = 0
    for entity, rules in mapping["form_visibility"].items():
        # A provider lookup is the column whose visibility reads a side.
        shown = {
            column: set(rule["when"][0]["value"])
            for column, rule in rules["columns"].items()
            if rule["when"][0]["field"].endswith("Side")
        }
        if not shown:
            continue
        lookups += len(shown)
        views = [v for v in mapping["views"][entity] if v["title"] == "Provider not named"]
        assert len(views) == 1, f"{entity} has no Provider not named view"
        assert _not_named_branches(views[0]) == shown, entity
        assert all(sides == PROVIDER_SIDES for sides in shown.values()), entity
    # Service has two, and DocumentRequest, Interview and Incident one each.
    assert lookups == 5
