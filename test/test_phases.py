# test/test_phases.py

from _paths import JINJA_TEMPLATES

from dbml_sharepoint.analysis.phases import (
    DEPLOY_GROUPS,
    phase_number,
    phase_numbers,
    phases_context,
)


def test_todays_numbering_is_pinned() -> None:
    """THE canary: structure changes surface here first, loudly. Numbers
    derive from position; this pins today's derivation exactly."""
    assert phase_numbers() == {
        "preflight": "1.1", "security": "1.2", "enrolment": "1.3",
        "reader_enrolment": "1.4", "unseal": "1.5", "lists": "2.1",
        "lookups": "2.2", "indexes": "2.3", "defaults": "2.4",
        "views": "3.1", "forms": "3.2", "seal": "4.1", "acls": "4.2",
        "seeds": "5.1",
    }
    assert phase_number("seal") == "4.1"


def test_reader_enrolment_follows_operator_enrolment() -> None:
    """Order matters and is not cosmetic.

    `require_empty_at_deploy` is proved in `security` (1.2). The reader must
    be added AFTER that gate has run in this same deploy, never before, or
    the run would trip its own gate. It must also precede every write phase,
    since the enrolment is part of PREPARE's security setup.
    """
    numbers = phase_numbers()
    assert numbers["reader_enrolment"] == "1.4"
    assert numbers["unseal"] == "1.5"
    keys = [step.key for _, steps in DEPLOY_GROUPS for step in steps]
    assert keys.index("security") < keys.index("reader_enrolment")
    assert keys.index("reader_enrolment") < keys.index("lists")


def test_keys_unique_and_templates_exist() -> None:
    keys = [s.key for _, steps in DEPLOY_GROUPS for s in steps]
    assert len(keys) == len(set(keys))
    for _, steps in DEPLOY_GROUPS:
        for step in steps:
            assert (JINJA_TEMPLATES / step.template).exists(), step.template


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
