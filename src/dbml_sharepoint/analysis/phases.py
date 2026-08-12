# src/dbml_sharepoint/analysis/phases.py
"""The deploy-phase manifest: THE single source of phase truth.

Group/step numbers derive from position here — add or move a step and
every consumer renumbers automatically: deploy.js banners/Starting
lines/[Phase X.Y] prefixes/error tags (templates receive
phases_context()), the manifest's phase references (phase_numbers()),
and test expectations (phase_number()). Reference steps by NAME or key
in prose and docs; numbers belong to generated artifacts.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PhaseStep:
    key: str        # stable id used by tests/tools
    name: str       # log noun: "Starting Phase X.Y: <name>."
    template: str   # template path relative to the templates root


DEPLOY_GROUPS: tuple[tuple[str, tuple[PhaseStep, ...]], ...] = (
    ("PREPARE", (
        PhaseStep("preflight", "read-only preflight", "deploy/_preflight.js.j2"),
        PhaseStep("security", "permission levels and site groups",
                  "deploy/_security_principals.js.j2"),
        PhaseStep("enrolment", "operator self-enrolment",
                  "deploy/_operator_enrolment.js.j2"),
        # After `security`, never before: that step proves
        # require_empty_at_deploy, and a reader added ahead of it would trip
        # the run's own empty-group gate. Before every write phase, because
        # the enrolment is part of PREPARE's security setup.
        PhaseStep("reader_enrolment", "enterprise reader enrolment",
                  "deploy/_reader_enrolment.js.j2"),
        PhaseStep("unseal", "maintenance unseal",
                  "deploy/_maintenance_unseal.js.j2"),
    )),
    ("STRUCTURE", (
        PhaseStep("lists", "list creation", "deploy/_lists.js.j2"),
        PhaseStep("lookups", "deferred lookups", "deploy/_lookups.js.j2"),
        PhaseStep("indexes", "indexed columns", "deploy/_indexes.js.j2"),
        PhaseStep("defaults", "field defaults", "deploy/_field_defaults.js.j2"),
    )),
    ("PRESENTATION", (
        PhaseStep("views", "views", "deploy/_views.js.j2"),
        PhaseStep("forms", "form formatting", "deploy/_forms.js.j2"),
    )),
    ("PROTECTION", (
        PhaseStep("seal", "seal declared columns", "deploy/_seal.js.j2"),
        PhaseStep("acls", "role inheritance and assignments",
                  "deploy/_acls.js.j2"),
    )),
    ("DATA", (
        PhaseStep("seeds", "seed items", "deploy/_seeds.js.j2"),
    )),
)


def phases_context() -> list[dict[str, Any]]:
    """Render-ready structure for deploy.js.j2 (numbers derived)."""
    groups: list[dict[str, Any]] = []
    for g_index, (group_name, steps) in enumerate(DEPLOY_GROUPS, start=1):
        step_dicts = [
            {
                "key": step.key,
                "name": step.name,
                "number": f"{g_index}.{s_index}",
                "template": step.template,
                "group_number": str(g_index),
                "group_name": group_name,
                "first_in_group": s_index == 1,
            }
            for s_index, step in enumerate(steps, start=1)
        ]
        groups.append({
            "number": str(g_index), "name": group_name, "steps": step_dicts,
        })
    return groups


def phase_numbers() -> dict[str, str]:
    """{step key: dotted number} — the manifest template's lookup."""
    return {
        step["key"]: step["number"]
        for group in phases_context()
        for step in group["steps"]
    }


def phase_number(key: str) -> str:
    numbers = phase_numbers()
    if key not in numbers:
        raise KeyError(f"unknown phase key {key!r} (known: {sorted(numbers)})")
    return numbers[key]
