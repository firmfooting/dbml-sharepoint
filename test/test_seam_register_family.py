# test/test_seam_register_family.py
"""seam-register rules the build cannot see.

The confidence rule is a governance check, not a save rule, so nothing
stops the demonstration rows modelling a *Verified* service with no
evidence behind it. And "Provider not named" is the only thing that stands
in for a save rule on the provider lookups, so its sides must be the sides
the form shows the lookup for, or a row that owes a provider drops out of
both. Both were found in review of the family's first pull request.
"""

from typing import Any

import yaml
from _paths import SOLUTION_TEMPLATES

MAPPING = SOLUTION_TEMPLATES / "seam-register" / "20-configure" / "mapping.yaml"


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
    needs two agreeing rows from different sides, or one System data row
    (50-govern/governance.md)."""
    evidence = _evidence_by_service()
    problems: list[str] = []
    for row in _mapping()["demo_items"]["Service"]:
        key, confidence = row["key"], row["values"]["Confidence"]
        rows = evidence.get(key, [])
        if confidence != "Assumed" and not rows:
            problems.append(f"{key} is {confidence} with no evidence row")
        if confidence == "Verified":
            agreeing = [e for e in rows if not e.get("Contradicts", False)]
            sides = {e["SourceSide"] for e in agreeing}
            system = any(e["EvidenceType"] == "System data" for e in agreeing)
            if len(sides) < 2 and not system:
                problems.append(f"{key} is Verified on evidence from {sorted(sides)} only")
    assert not problems, problems


def test_provider_not_named_covers_every_side_that_shows_the_lookup() -> None:
    mapping = _mapping()
    shown = {
        column: set(rule["when"][0]["value"])
        for column, rule in mapping["form_visibility"]["Service"]["columns"].items()
    }
    view = next(v for v in mapping["views"]["Service"] if v["title"] == "Provider not named")
    flagged = {
        branch["all_of"][1]["field"]: set(branch["all_of"][0]["value"])
        for branch in view["where"][0]["any_of"]
    }
    assert flagged == shown == {
        "RunByProvider": {"Provider", "Third party", "Shared"},
        "SupportProvider": {"Provider", "Third party", "Shared"},
    }
