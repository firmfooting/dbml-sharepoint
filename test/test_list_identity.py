from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _packs import pack

from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError


def _list(name: str, spec: str, role: str = "default") -> str:
    return f"  {name}: {{kind: List, base_template: 100, site_role: {role}, {spec}}}"


def test_a_list_may_declare_its_url(tmp_path: Path) -> None:
    _, bundle = pack(
        tmp_path, dbml=table("Task", ID_PK, TITLE),
        mapping="entities:\n" + _list("Task", "internal_name: Lists/MailLedger"),
    )
    assert bundle.mapping.entities["Task"].internal_name == "Lists/MailLedger"


@pytest.mark.parametrize("value", ["Lists/a|b", "Lists/../x", "/"])
def test_a_list_url_is_validated(tmp_path: Path, value: str) -> None:
    with pytest.raises(MappingValueError, match=r"entities\.Task\.internal_name"):
        pack(
            tmp_path, dbml=table("Task", ID_PK, TITLE),
            mapping="entities:\n" + _list("Task", f"internal_name: '{value}'"),
        )


def test_a_non_string_list_url_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MappingShapeError):
        pack(
            tmp_path, dbml=table("Task", ID_PK, TITLE),
            mapping="entities:\n" + _list("Task", "internal_name: 123"),
        )


def test_two_lists_may_not_share_a_url(tmp_path: Path) -> None:
    mapping = "entities:\n" + _list("Task", "internal_name: Lists/One") + "\n" + _list(
        "Job", "internal_name: lists/one/")
    with pytest.raises(MappingValueError, match="duplicate"):
        pack(tmp_path, dbml=table("Task", ID_PK, TITLE) + table("Job", ID_PK, TITLE),
             mapping=mapping)


def test_a_list_url_cannot_combine_with_renamed_from(tmp_path: Path) -> None:
    mapping = "entities:\n" + _list("Task", "internal_name: Lists/One, renamed_from: [Old]")
    with pytest.raises(MappingValueError, match="renamed_from"):
        pack(tmp_path, dbml=table("Task", ID_PK, TITLE), mapping=mapping)


def test_a_list_url_collides_with_a_library_root(tmp_path: Path) -> None:
    mapping = (
        "entities:\n" + _list("Task", "internal_name: PolicyDocuments") + "\n"
        "  Doc: {kind: DocumentLibrary, base_template: 101, site_role: default, "
        "title: Policy Documents, internal_name: policydocuments}"
    )
    with pytest.raises(MappingValueError, match="duplicate"):
        pack(tmp_path, dbml=table("Task", ID_PK, TITLE) + table("Doc", ID_PK, TITLE),
             mapping=mapping)
