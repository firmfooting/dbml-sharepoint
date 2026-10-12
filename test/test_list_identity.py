from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _packs import pack
from _paths import FIXTURES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.release import load_release


def _list(name: str, spec: str, role: str = "default") -> str:
    return f"  {name}: {{kind: List, base_template: 100, site_role: {role}, {spec}}}"


def test_a_list_may_declare_its_url(tmp_path: Path) -> None:
    _, bundle = pack(
        tmp_path, dbml=table("Task", ID_PK, TITLE),
        mapping="entities:\n" + _list("Task", "internal_name: Lists/MailLedger"),
    )
    assert bundle.mapping.entities["Task"].internal_name == "Lists/MailLedger"


def _manifest_for(tmp_path: Path, url: str) -> str:
    schema, bundle = pack(
        tmp_path, dbml=table("Task", ID_PK, TITLE),
        mapping="entities:\n" + _list("Task", f"internal_name: '{url}'"),
    )
    return generate_manifest(
        resolved=resolve(schema, bundle.mapping),
        schema_json=build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        ),
        findings=[], bundle=bundle, release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test", site_role="default",
        source_dbml="schema.dbml", generated_at="2026-09-15T00:00:00Z",
        source_mtime="2026-09-15T00:00:00Z",
    )


def test_the_manifest_records_a_declared_list_url(tmp_path: Path) -> None:
    manifest = _manifest_for(tmp_path, "Lists/MailLedger")
    assert "Declared list URL: `Lists/MailLedger`" in manifest
    assert "Immutable library URL name" not in manifest


@pytest.mark.parametrize(("url", "span"), [
    ("Lists/a`b", "``Lists/a`b``"), ("Lists/a``b", "```Lists/a``b```"),
    ("Lists/a`", "`` Lists/a` ``"),
])
def test_a_backtick_in_a_list_url_cannot_close_the_manifest_code_span(
    tmp_path: Path, url: str, span: str,
) -> None:
    assert f"Declared list URL: {span}\n" in _manifest_for(tmp_path, url)


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


@pytest.mark.parametrize("spelling", [
    "/Lists/MailLedger/", "Lists\\\\MailLedger",
    "Lists//MailLedger",
])
def test_a_list_url_is_stored_normalised(tmp_path: Path, spelling: str) -> None:
    _, bundle = pack(
        tmp_path, dbml=table("Task", ID_PK, TITLE),
        mapping="entities:\n" + _list("Task", f"internal_name: '{spelling}'"),
    )
    assert bundle.mapping.entities["Task"].internal_name == "Lists/MailLedger"


@pytest.mark.parametrize("name", [
    "Policy Documents", "Policy-Docs", "Politiques d\u00e9taill\u00e9es",
])
def test_a_library_root_with_spaces_hyphens_or_unicode_still_loads(
    tmp_path: Path, name: str,
) -> None:
    mapping = (
        "entities:\n  Doc: {kind: DocumentLibrary, base_template: 101, "
        f"site_role: default, internal_name: '{name}'}}"
    )
    _, bundle = pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=mapping)
    assert bundle.mapping.entities["Doc"].internal_name == name
