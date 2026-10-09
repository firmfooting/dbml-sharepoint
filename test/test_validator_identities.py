"""Each identity rule, made to fire on a mapping with one fault."""

from pathlib import Path

from _findings import only
from _packs import blocks, entities, pack

from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping

_SCHEMA = "Table Project {\n  Title varchar [not null]\n}\n"


def _findings(tmp_path: Path, body: str) -> list[Finding]:
    schema, bundle = pack(tmp_path, _SCHEMA, blocks(entities("Project"), body))
    return validate_against_mapping(schema, bundle)


_GRANT = """
    list_permissions:
      default:
        break_inheritance: true
        reconcile: exact
        assignments:
          - principal: { kind: group, name: "XX Writers" }
            level: "Contribute"
"""


def _group(lines: str) -> str:
    return f"""
    groups:
      - name: "XX Writers"
        description: "Writers."
{lines}
""" + _GRANT


def test_an_enrolled_name_nobody_declared_is_refused(tmp_path: Path) -> None:
    finding = only(
        _findings(tmp_path, _group("        enroll: [records_clerk]")),
        FindingCode.IDENTITY_UNKNOWN,
    )
    assert "records_clerk" in finding.message


def test_redeclaring_a_built_in_is_refused(tmp_path: Path) -> None:
    body = _group("        enroll: [automation]") + """
    identities:
      automation:
        description: "Mine."
"""
    only(_findings(tmp_path, body), FindingCode.IDENTITY_REDECLARES_BUILTIN)


def test_a_name_the_env_key_cannot_spell_is_refused(tmp_path: Path) -> None:
    body = _group("        enroll: [Records-Clerk]") + """
    identities:
      Records-Clerk:
        description: "x"
"""
    only(_findings(tmp_path, body), FindingCode.IDENTITY_NAME_INVALID)


def test_an_unknown_or_empty_kind_list_is_refused(tmp_path: Path) -> None:
    body = _group("        enroll: [clerk, desk]") + """
    identities:
      clerk:
        description: "x"
        kinds: [mailbox]
      desk:
        description: "y"
        kinds: []
"""
    findings = [f for f in _findings(tmp_path, body) if f.code is FindingCode.IDENTITY_KIND_UNKNOWN]
    assert len(findings) == 2


def test_the_operator_in_enroll_is_refused(tmp_path: Path) -> None:
    only(
        _findings(tmp_path, _group("        enroll: [operator]")),
        FindingCode.OPERATOR_ENROLLED_PERSISTENTLY,
    )


def test_a_persistent_identity_in_enroll_during_run_is_refused(tmp_path: Path) -> None:
    only(
        _findings(tmp_path, _group("        enroll_during_run: [automation]")),
        FindingCode.OPERATOR_ENROLLED_PERSISTENTLY,
    )


def test_an_exclusive_group_enrolling_a_group_kind_is_refused(tmp_path: Path) -> None:
    body = _group("        enroll: [intake]\n        membership: exclusive") + """
    identities:
      intake:
        description: "x"
        kinds: [user, security_group]
"""
    only(_findings(tmp_path, body), FindingCode.EXCLUSIVE_GROUP_ENROLS_A_GROUP_KIND)


def test_a_declared_identity_no_group_enrols_is_warned_about(tmp_path: Path) -> None:
    body = _group("        enroll: [automation]") + """
    identities:
      clerk:
        description: "x"
"""
    finding = only(_findings(tmp_path, body), FindingCode.IDENTITY_DECLARED_NOT_ENROLLED)
    assert finding.severity == "warning"


def test_an_old_flag_is_warned_about(tmp_path: Path) -> None:
    body = _group("        enroll_operator_during_deploy: true")
    finding = only(_findings(tmp_path, body), FindingCode.DEPRECATED_ENROLMENT_FLAG)
    assert finding.severity == "warning"
    assert "enroll_during_run: [operator]" in finding.message


def test_an_old_flag_beside_the_new_key_is_refused(tmp_path: Path) -> None:
    body = _group(
        "        enroll_operator_during_deploy: true\n        enroll_during_run: [operator]"
    )
    codes = {f.code for f in _findings(tmp_path, body)}
    assert FindingCode.ENROLMENT_DECLARED_TWICE in codes


def test_a_sharepoint_group_in_enroll_is_refused_with_the_nesting_citation(
    tmp_path: Path,
) -> None:
    finding = only(
        _findings(tmp_path, _group('        enroll: ["Site Members"]')),
        FindingCode.SHAREPOINT_GROUP_ENROLLED,
    )
    assert "cannot be nested" in finding.message
    assert "associated_member_group" in finding.message
