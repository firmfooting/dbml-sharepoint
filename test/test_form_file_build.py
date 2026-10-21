"""A form.yaml blueprint builds its header and footer end to end."""

import json
import re
import shutil
from hashlib import sha256
from pathlib import Path

import pytest
import typer
from _paths import FIXTURES
from test_jsgen_golden import _manifest, _script

from dbml_sharepoint.analysis.formula.functions import SUPPORTED
from dbml_sharepoint.pipeline import execute_build, execute_validation

FORMS = FIXTURES / "forms"
EPOCH = 1759276800
HEADER_JSON = '{"elmType": "div", "txtContent": "Hello"}'
BODY = "{ sections: [ { displayname: Core, fields: [Title, Status] } ] }"
VISIBILITY = "{ reconcile: declared, columns: { Wait: hidden } }"


def _build(out: Path, schema: Path, mapping: Path, zone: str = "Australia/Melbourne") -> None:
    execute_build(
        schema=schema, mapping=mapping, release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci", time_zone=zone,
        site_role="default", out=out, source_date_epoch=EPOCH,
    )


def _formatter(out: Path) -> dict[str, object]:
    """The form formatting entry of the Task list, as the deploy script carries it."""
    deploy = (out / "deploy.js.txt").read_text(encoding="utf-8")
    raw = re.search(r'"client_form_custom_formatter": (".*"),?\n', deploy)
    assert raw is not None
    return dict(json.loads(json.loads(raw.group(1))))


def _fixture_build(tmp_path: Path, zone: str = "Australia/Melbourne") -> Path:
    out = tmp_path / zone.replace("/", "-")
    _build(out, FORMS / "schema.dbml", FORMS / "mapping.yaml", zone)
    return out


def _texts(node: object) -> list[str]:
    """Every string anywhere in a JSON value."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [t for v in node.values() for t in _texts(v)]
    if isinstance(node, list):
        return [t for v in node for t in _texts(v)]
    return []


def test_build_of_a_form_yaml_blueprint_writes_the_header(tmp_path: Path) -> None:
    header = _formatter(_fixture_build(tmp_path))["headerJSONFormatter"]
    text = "\n".join(_texts(header))
    assert "Untitled task" in text
    assert "Open reference" in text
    assert "Rating" in text
    assert "[$Due" not in text  # a calculated column is re-derived, never read


def test_a_component_footer_is_written_too(tmp_path: Path) -> None:
    footer = _formatter(_fixture_build(tmp_path))["footerJSONFormatter"]
    text = "\n".join(_texts(footer))
    assert "Critical impact" in text
    assert "Notice" in text


def test_a_different_site_zone_changes_only_the_form_formatting(tmp_path: Path) -> None:
    melbourne = _fixture_build(tmp_path, "Australia/Melbourne")
    london = _fixture_build(tmp_path, "Europe/London")
    for name in ("deploy.js.txt", "rollback.js.txt"):
        a = (melbourne / name).read_text(encoding="utf-8").splitlines()
        b = (london / name).read_text(encoding="utf-8").splitlines()
        assert len(a) == len(b)
        moved = [x for x, y in zip(a, b, strict=True) if x != y]
        assert all("client_form_custom_formatter" in x or "time_zone" in x.lower() for x in moved)
    a_header = _formatter(melbourne)["headerJSONFormatter"]
    b_header = _formatter(london)["headerJSONFormatter"]
    assert a_header != b_header


def test_refused_formula_fails_the_build_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "p"
    shutil.copytree(FORMS, project)
    mapping = project / "mapping.yaml"
    mapping.write_text(
        mapping.read_text(encoding="utf-8").replace(
            "Chased: '=IF(ISBLANK([Start]),\"\",[Start]+[Wait])'", "Chased: '=[Start]+[Wait]'",
        ),
        encoding="utf-8",
    )
    with pytest.raises(typer.Exit):
        _build(tmp_path / "out", project / "schema.dbml", mapping)
    err = capsys.readouterr().err
    assert "Task.Chased" in err
    assert "[Start]+[Wait]" in err
    assert not (tmp_path / "out" / "deploy.js.txt").exists()


def test_validate_without_a_zone_still_reports_formula_refusals(tmp_path: Path) -> None:
    project = tmp_path / "p"
    shutil.copytree(FORMS, project)
    mapping = project / "mapping.yaml"
    mapping.write_text(
        mapping.read_text(encoding="utf-8").replace(
            "Chased: '=IF(ISBLANK([Start]),\"\",[Start]+[Wait])'", "Chased: '=[Start]+[Wait]'",
        ),
        encoding="utf-8",
    )
    findings = execute_validation(schema=project / "schema.dbml", mapping=mapping)
    errors = [f for f in findings if f.severity == "error"]
    assert [f.location.column for f in errors if f.location] == ["Chased"]
    assert execute_validation(schema=FORMS / "schema.dbml", mapping=FORMS / "mapping.yaml") == []


def _project(root: Path, mapping_extra: str, form_yaml: str | None) -> Path:
    root.mkdir()
    shutil.copy(FORMS / "schema.dbml", root / "schema.dbml")
    (root / "header.json").write_text(HEADER_JSON, encoding="utf-8")
    base = (FORMS / "mapping.yaml").read_text(encoding="utf-8")
    (root / "mapping.yaml").write_text(base + mapping_extra, encoding="utf-8")
    if form_yaml is not None:
        (root / "form.yaml").write_text(form_yaml, encoding="utf-8")
    return root


def test_header_file_escape_hatch_builds_byte_identically_to_mapping_yaml(tmp_path: Path) -> None:
    in_mapping = _project(
        tmp_path / "a",
        f"\nform_formatting:\n  Task:\n    header: header.json\n    body: {BODY}\n"
        f"\nform_visibility:\n  Task: {VISIBILITY}\n",
        None,
    )
    in_form = _project(
        tmp_path / "b",
        "",
        f"Task:\n  header: {{ file: header.json }}\n  body: {BODY}\n  visibility: {VISIBILITY}\n",
    )
    _build(tmp_path / "out-a", in_mapping / "schema.dbml", in_mapping / "mapping.yaml")
    _build(tmp_path / "out-b", in_form / "schema.dbml", in_form / "mapping.yaml")
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt"):
        a = (tmp_path / "out-a" / name).read_bytes()
        assert a == (tmp_path / "out-b" / name).read_bytes()
    assert "Hello" in (tmp_path / "out-a" / "deploy.js.txt").read_text(encoding="utf-8")


def test_the_golden_is_unchanged() -> None:
    manifest = _manifest()
    js = _script().encode("utf-8")
    assert (len(js), sha256(js).hexdigest()) == (manifest["bytes"], manifest["sha256"])


def test_the_documented_function_list_is_the_supported_set() -> None:
    page = (FIXTURES.parent.parent / "website/docs/reference/mapping.md").read_text("utf-8")
    start = page.index("A header can use these functions")
    listed = re.findall(r"`([A-Z]+)`", page[start : page.index("###", start)])
    assert set(listed) == set(SUPPORTED)
