"""The rows the deploy, manifest, assess and verify all read."""

from pathlib import Path

from _packs import blocks, entities, write_mapping

from dbml_sharepoint.analysis.enrolment import (
    GroupEnrolment,
    as_json,
    enrolment_plan,
)
from dbml_sharepoint.model.identities import describe_identity, parse_values
from dbml_sharepoint.model.mapping_loader import load_mapping

_BODY = """
    groups:
      - name: "XX Writers"
        description: "w"
        enroll: [automation]
      - name: "XX Readers"
        description: "r"
        enroll: [enterprise_reader]
        membership: exclusive
      - name: "dbml List Administrators"
        description: "a"
        enroll_during_run: [operator]
"""


def _plan(tmp_path: Path, **values: str) -> tuple[GroupEnrolment, ...]:
    write_mapping(tmp_path, blocks(entities("Project"), _BODY), name="mapping.yaml")
    mapping = load_mapping(tmp_path / "mapping.yaml").mapping
    return enrolment_plan(mapping, {k: parse_values(k, v) for k, v in values.items()})


def test_a_group_whose_identities_have_no_values_is_left_out(tmp_path: Path) -> None:
    plan = _plan(tmp_path, automation="user:flows@example.com")
    assert [g.group for g in plan] == ["XX Writers"]


def test_each_row_carries_its_ceiling_and_its_description(tmp_path: Path) -> None:
    plan = _plan(tmp_path, automation="user:flows@example.com",
                 enterprise_reader="user:reader@example.com")
    (writers, readers) = plan
    assert writers.rows[0].ceiling == "automation"
    assert readers.rows[0].ceiling == "reader"
    assert readers.membership == "exclusive"
    values = parse_values("automation", "user:flows@example.com")
    assert writers.rows[0].described == describe_identity("automation", values)


def test_the_json_shape_the_templates_read(tmp_path: Path) -> None:
    plan = _plan(tmp_path, automation="user:flows@example.com")
    assert as_json(plan) == [{
        "group": "XX Writers", "membership": "additive", "during_run": [],
        "rows": [{
            "identity": "automation", "ceiling": "automation",
            "described": plan[0].rows[0].described,
            "values": [{"kind": "user", "value": "flows@example.com", "owners": False}],
        }],
    }]
