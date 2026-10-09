"""The rows the deploy, manifest, assess and verify all read."""

from pathlib import Path

from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack, write_mapping

from dbml_sharepoint.analysis.enrolment import (
    GroupEnrolment,
    as_json,
    enrolment_plan,
)
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.verifygen import verify_targets
from dbml_sharepoint.model.identities import describe_identity, parse_values
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

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
    bundle = load_mapping(tmp_path / "mapping.yaml")
    dbml = table("Project", ID_PK, TITLE)
    (tmp_path / "s.dbml").write_text(dbml, encoding="utf-8", newline="\n")
    schema = parse_dbml(tmp_path / "s.dbml")
    return enrolment_plan(
        bundle, resolve(schema, bundle.mapping),
        {k: parse_values(k, v) for k, v in values.items()},
    )


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
            "values": [{"kind": "user", "value": "flows@example.com", "owners": False,
                        "claim": "flows@example.com"}],
        }],
    }]


def test_a_single_member_enum_group_is_named_as_it_is_deployed(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml='Enum division {\n  "Field operations"\n}\n' + table("Docs", ID_PK, TITLE),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member} Editors"
                description: "Editors."
                owner_group: "Site Owners"
                enroll: [automation]
        """,
    )
    plan = enrolment_plan(
        bundle, resolve(schema, bundle.mapping),
        {"automation": parse_values("automation", "user:flows@example.com")},
    )
    assert [g.group for g in plan] == ["Field operations Editors"]


def test_deploy_assess_and_verify_name_a_single_member_group_alike(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml='Enum division {\n  "Field operations"\n}\n' + table("Docs", ID_PK, TITLE),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member} Editors"
                description: "Editors."
                owner_group: "Site Owners"
                enroll: [automation]
        """,
    )
    resolved = resolve(schema, bundle.mapping)
    identities = {"automation": parse_values("automation", "user:flows@example.com")}
    planned = as_json(enrolment_plan(bundle, resolved, identities))
    verify = verify_targets(schema, bundle, "default", resolved=resolved, identities=identities)
    assess = assess_targets(
        schema, bundle, "default", resolved=resolved, identities=identities,
    )
    assert [g["group"] for g in planned] == ["Field operations Editors"]
    assert verify["identity_groups"] == planned
    assert assess["identity_groups"] == planned
