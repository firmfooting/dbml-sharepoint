# test/test_phases.py
from pathlib import Path

from dbml_sharepoint.analysis.phases import (
    DEPLOY_GROUPS,
    phase_number,
    phase_numbers,
    phases_context,
)

TEMPLATES = Path(__file__).parent.parent / "src" / "dbml_sharepoint" / "templates"


def test_todays_numbering_is_pinned() -> None:
    """THE canary: structure changes surface here first, loudly. Numbers
    derive from position; this pins today's derivation exactly."""
    assert phase_numbers() == {
        "preflight": "1.1", "security": "1.2", "enrolment": "1.3",
        "unseal": "1.4", "lists": "2.1", "lookups": "2.2",
        "indexes": "2.3", "defaults": "2.4", "views": "3.1",
        "forms": "3.2", "seal": "4.1", "acls": "4.2", "seeds": "5.1",
    }
    assert phase_number("seal") == "4.1"


def test_keys_unique_and_templates_exist() -> None:
    keys = [s.key for _, steps in DEPLOY_GROUPS for s in steps]
    assert len(keys) == len(set(keys))
    for _, steps in DEPLOY_GROUPS:
        for step in steps:
            assert (TEMPLATES / step.template).exists(), step.template


def test_context_shape_for_templates() -> None:
    ctx = phases_context()
    assert [g["name"] for g in ctx] == [
        "PREPARE", "STRUCTURE", "PRESENTATION", "PROTECTION", "DATA",
    ]
    first = ctx[0]["steps"][0]
    assert first == {
        "key": "preflight", "name": "read-only preflight",
        "number": "1.1", "template": "deploy/_preflight.js.j2",
        "group_number": "1", "group_name": "PREPARE",
        "first_in_group": True,
    }
    assert ctx[0]["steps"][1]["first_in_group"] is False
