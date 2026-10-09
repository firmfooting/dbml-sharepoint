"""Which value each identity gets, and every refusal on the way."""

from pathlib import Path

import pytest
import typer
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.model.env_file import describe_env_provenance
from dbml_sharepoint.model.identities import (
    IdentityGivenTwice,
    IdentityKindNotAllowed,
    IdentityKindNotYetSupported,
    IdentityNotDeclared,
    IdentityValue,
    IdentityValueCount,
    IdentityValueMissing,
    identity_hash,
    parse_values,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import Mapping
from dbml_sharepoint.project import (
    ENTERPRISE_READER_DECLINED,
    EnterpriseReaderDeclined,
    resolve_env_settings,
    resolve_identities,
)

_GROUPS = """
    identities:
      records_clerk:
        description: "Files correspondence."
      intake:
        description: "Intake."
        kinds: [user, security_group]
      board:
        description: "Board mailbox group."
        kinds: [user, m365_group]
    groups:
      - name: "XX Writers"
        description: "Writers."
        enroll: [automation, records_clerk, intake]
      - name: "XX Readers"
        description: "Readers."
        enroll: [enterprise_reader]
        membership: exclusive
"""
_ALL = ["automation=user:flows@example.com", "records_clerk=user:clerk@example.com",
        "intake=user:intake@example.com"]
_GUID = "0f8fad5b-d9cb-469f-a165-70867728950e"


def _mapping(tmp_path: Path, body: str = _GROUPS) -> Mapping:
    write_mapping(tmp_path, blocks(entities("Project"), body), name="mapping.yaml")
    return load_mapping(tmp_path / "mapping.yaml").mapping


def _resolve(tmp_path: Path, flags: list[str], file: dict[str, str] | None = None,
             reader: str | EnterpriseReaderDeclined | None = None,
             body: str = _GROUPS) -> dict[str, tuple[IdentityValue, ...]]:
    return resolve_identities(
        flags=flags, reader_flag=reader, file_identities=file or {},
        mapping=_mapping(tmp_path, body),
    )


def test_every_enrolled_identity_gets_its_values(tmp_path: Path) -> None:
    resolved = _resolve(tmp_path, _ALL)
    assert resolved["automation"] == (IdentityValue("user", "flows@example.com"),)
    assert "enterprise_reader" not in resolved  # optional, ruling A1


def test_a_flag_replaces_the_file_for_that_name_only(tmp_path: Path) -> None:
    resolved = _resolve(
        tmp_path, ["automation=user:new@example.com"],
        file={"automation": "user:old@example.com", "records_clerk": "user:clerk@example.com",
              "intake": "user:intake@example.com"},
    )
    assert resolved["automation"][0].value == "new@example.com"
    assert resolved["records_clerk"][0].value == "clerk@example.com"


def test_the_reader_alias_flag_is_the_reader_identity(tmp_path: Path) -> None:
    resolved = _resolve(tmp_path, _ALL, reader="reader@example.com")
    assert resolved["enterprise_reader"] == (IdentityValue("user", "reader@example.com"),)


def test_the_wizard_declining_the_reader_means_no_value(tmp_path: Path) -> None:
    resolved = _resolve(tmp_path, _ALL, file={"enterprise_reader": "user:r@example.com"},
                        reader=ENTERPRISE_READER_DECLINED)
    assert "enterprise_reader" not in resolved


def test_a_missing_required_value_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityValueMissing, match="automation"):
        _resolve(tmp_path, _ALL[1:])


def test_a_value_for_a_name_nobody_enrols_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityNotDeclared, match="mailroom"):
        _resolve(tmp_path, [*_ALL, "mailroom=user:m@example.com"])


def test_a_declared_identity_no_group_enrols_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityNotDeclared, match="board"):
        _resolve(tmp_path, [*_ALL, "board=user:b@example.com"])


def test_a_kind_the_identity_does_not_take_is_refused(tmp_path: Path) -> None:
    flags = [_ALL[0], f"records_clerk=security_group:{_GUID}", _ALL[2]]
    with pytest.raises(IdentityKindNotAllowed, match="records_clerk"):
        _resolve(tmp_path, flags)


def test_a_group_kind_is_refused_until_the_probe_passes(tmp_path: Path) -> None:
    flags = [*_ALL[:2], f"intake=security_group:{_GUID}"]
    with pytest.raises(IdentityKindNotYetSupported, match="probe"):
        _resolve(tmp_path, flags)


def test_the_m365_group_and_its_owners_form_are_refused_until_the_probe_passes(
    tmp_path: Path,
) -> None:
    body = _GROUPS.replace("enroll: [automation, records_clerk, intake]",
                           "enroll: [automation, records_clerk, intake, board]")
    for spelled in (f"m365_group:{_GUID}", f"m365_group:{_GUID}:owners"):
        with pytest.raises(IdentityKindNotYetSupported, match="board"):
            _resolve(tmp_path, [*_ALL, f"board={spelled}"], body=body)


def test_two_reader_values_are_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityValueCount, match="enterprise_reader"):
        _resolve(tmp_path, [*_ALL, "enterprise_reader=user:a@example.com,user:b@example.com"])


def test_the_operator_takes_no_value(tmp_path: Path) -> None:
    with pytest.raises(IdentityValueCount, match="operator"):
        _resolve(tmp_path, [*_ALL, "operator=user:me@example.com"])


def test_one_name_in_two_flags_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityGivenTwice, match="automation"):
        _resolve(tmp_path, [*_ALL, "automation=user:other@example.com"])


def test_the_alias_flag_and_its_canonical_flag_are_refused_together(tmp_path: Path) -> None:
    with pytest.raises(IdentityGivenTwice, match="enterprise_reader"):
        _resolve(tmp_path, [*_ALL, "enterprise_reader=user:a@example.com"],
                 reader="a@example.com")


def _env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "dbml-sharepoint.env"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_file_reader_alias_and_its_canonical_key_are_refused_together(
    tmp_path: Path,
) -> None:
    path = _env(tmp_path, "DBMLSP_ENTERPRISE_READER=a@example.com\n"
                          "DBMLSP_IDENTITY_ENTERPRISE_READER=user:a@example.com\n")
    # config_error prints the reason and raises typer.Exit(1), a refused build.
    with pytest.raises(typer.Exit):
        resolve_env_settings(path, None, None, None, None, None, None)


def test_the_file_reader_alias_is_folded_into_the_identities(tmp_path: Path) -> None:
    path = _env(tmp_path, "DBMLSP_ENTERPRISE_READER=reader@example.com\n")
    *_, file_identities, _provenance = resolve_env_settings(
        path, None, None, None, None, None, None,
    )
    assert file_identities == {"enterprise_reader": "user:reader@example.com"}


def test_an_overridden_identity_is_described_by_hash(tmp_path: Path) -> None:
    """Review focus 1: the provenance line reaches the central log."""
    path = _env(tmp_path, "DBMLSP_IDENTITY_AUTOMATION=user:old@example.com\n"
                          "DBMLSP_ENTERPRISE_READER=reader@example.com\n")
    *_, file_identities, provenance = resolve_env_settings(
        path, "flagged@example.com", None, None, None, None, None,
        identity_flags=("automation=user:new@example.com",),
    )
    line = describe_env_provenance(provenance)
    assert "example.com" not in line
    new = identity_hash(parse_values("automation", "user:new@example.com"))
    assert f"DBMLSP_IDENTITY_AUTOMATION (using automation (sha256:{new}))" in line
    assert "DBMLSP_ENTERPRISE_READER (using enterprise_reader (sha256:" in line
    assert file_identities["automation"] == "user:old@example.com"


def test_a_reader_flag_over_the_canonical_file_key_is_described_by_hash(
    tmp_path: Path,
) -> None:
    path = _env(tmp_path, "DBMLSP_IDENTITY_ENTERPRISE_READER=user:old@example.com\n")
    *_, provenance = resolve_env_settings(
        path, "flagged@example.com", None, None, None, None, None,
    )
    line = describe_env_provenance(provenance)
    assert "example.com" not in line
    assert "DBMLSP_IDENTITY_ENTERPRISE_READER (using enterprise_reader (sha256:" in line


def test_an_identity_flag_beats_the_file_reader_alias(tmp_path: Path) -> None:
    path = _env(tmp_path, "DBMLSP_ENTERPRISE_READER=old@example.com\n")
    reader, *_, file_identities, provenance = resolve_env_settings(
        path, None, None, None, None, None, None,
        identity_flags=("enterprise_reader=user:new@example.com",),
    )
    line = describe_env_provenance(provenance)
    assert "example.com" not in line
    assert "DBMLSP_ENTERPRISE_READER (using enterprise_reader (sha256:" in line
    # The alias must not reach resolve_identities as a second source.
    assert reader is None
    assert "enterprise_reader" not in file_identities
    resolved = resolve_identities(
        flags=(*_ALL, "enterprise_reader=user:new@example.com"), reader_flag=reader,
        file_identities=file_identities, mapping=_mapping(tmp_path),
    )
    assert resolved["enterprise_reader"] == (IdentityValue("user", "new@example.com"),)


def test_the_reader_flag_and_an_identity_flag_are_still_refused_over_a_file_alias(
    tmp_path: Path,
) -> None:
    path = _env(tmp_path, "DBMLSP_ENTERPRISE_READER=old@example.com\n")
    reader, *_, file_identities, _ = resolve_env_settings(
        path, "a@example.com", None, None, None, None, None,
        identity_flags=("enterprise_reader=user:b@example.com",),
    )
    with pytest.raises(IdentityGivenTwice, match="enterprise_reader"):
        resolve_identities(
            flags=("enterprise_reader=user:b@example.com",), reader_flag=reader,
            file_identities=file_identities, mapping=_mapping(tmp_path),
        )


def test_a_declined_reader_with_an_identity_flag_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IdentityGivenTwice, match="declined"):
        _resolve(tmp_path, [*_ALL, "enterprise_reader=user:a@example.com"],
                 reader=ENTERPRISE_READER_DECLINED)


@pytest.mark.parametrize("flags", [
    ("automation",),
    ("automation=user:a@example.com", "automation=user:b@example.com"),
])
def test_resolve_env_settings_leaves_a_bad_identity_flag_to_resolve_identities(
    tmp_path: Path, flags: tuple[str, ...], capsys: pytest.CaptureFixture[str],
) -> None:
    path = _env(tmp_path, "DBMLSP_IDENTITY_AUTOMATION=user:old@example.com\n")
    *_, provenance = resolve_env_settings(
        path, None, None, None, None, None, None, identity_flags=flags,
    )
    assert "example.com" not in describe_env_provenance(provenance)
    assert "example.com" not in capsys.readouterr().out
