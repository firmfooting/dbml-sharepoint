"""A build turns the help env keys and a rule's `help:` key into the footer link, or refuses."""

import shutil
from pathlib import Path

import pytest
import typer
from _paths import FIXTURES
from test_form_file_build import _formatter, _texts

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.pipeline import execute_build, execute_validation

BASE = "https://hub.fabrikam.net/sites/help/SitePages/"
GUIDES = "g-critical: Review a critical risk.aspx\ng-low: Low-impact.aspx\n"
RULES = (
    '        - { when: { field: Impact, op: eq, value: Critical }, text: "Critical impact" }\n'
)
WITH_HELP = (
    '        - { when: { field: Impact, op: eq, value: Critical }, text: "Critical impact",'
    " help: g-critical }\n"
    '        - { when: { field: Impact, op: eq, value: Low }, text: "Low impact",'
    " help: g-low }\n"
)


def _project(
    tmp_path: Path, env: str | None, guides: str = GUIDES, key: str = "g-critical",
) -> Path:
    project = tmp_path / "p"
    shutil.copytree(FIXTURES / "forms", project)
    form = project / "form.yaml"
    form.write_text(
        form.read_text(encoding="utf-8").replace(RULES, WITH_HELP.replace("g-critical", key)),
        encoding="utf-8", newline="\n",
    )
    (project / "guides.yaml").write_text(guides, encoding="utf-8", newline="\n")
    if env is not None:
        (project / "dbml-sharepoint.env").write_text(env, encoding="utf-8", newline="\n")
    return project


def _run(project: Path, out: Path) -> None:
    env = project / "dbml-sharepoint.env"
    execute_build(
        schema=project / "schema.dbml", mapping=project / "mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci", time_zone="Australia/Melbourne",
        site_role="default", out=out, source_date_epoch=1759276800,
        env_file=env if env.exists() else None,
    )


def test_build_with_the_env_keys_renders_the_absolute_url_in_the_header_json(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        f"DBMLSP_HELP_BASE_URL={BASE}\nDBMLSP_HELP_GUIDES=guides.yaml\n",
    )
    _run(project, tmp_path / "out")
    text = "\n".join(_texts(_formatter(tmp_path / "out")["footerJSONFormatter"]))
    assert BASE + "Review%20a%20critical%20risk.aspx" in text
    assert BASE + "Low-impact.aspx" in text
    assert "Help for this step" in text


def test_build_without_the_env_keys_succeeds_with_the_off_warning_and_no_url(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(tmp_path, None)
    _run(project, tmp_path / "out")
    captured = capsys.readouterr()
    assert "form_help_off" in captured.out + captured.err
    text = "\n".join(_texts(_formatter(tmp_path / "out")["footerJSONFormatter"]))
    assert "Help for this step" not in text
    assert "hub.fabrikam.net" not in text


def test_build_with_an_unmapped_key_exits_1_naming_the_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(
        tmp_path, f"DBMLSP_HELP_BASE_URL={BASE}\nDBMLSP_HELP_GUIDES=guides.yaml\n", key="missing",
    )
    with pytest.raises(typer.Exit) as exit_:
        _run(project, tmp_path / "out")
    assert exit_.value.exit_code == 1
    assert "'missing'" in capsys.readouterr().err
    assert not (tmp_path / "out" / "deploy.js.txt").exists()


def test_build_with_one_env_key_only_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(tmp_path, f"DBMLSP_HELP_BASE_URL={BASE}\n")
    with pytest.raises(typer.Exit) as exit_:
        _run(project, tmp_path / "out")
    assert exit_.value.exit_code == 1
    assert "DBMLSP_HELP_GUIDES" in capsys.readouterr().err



def test_validate_of_a_help_mapping_emits_no_off_warning(tmp_path: Path) -> None:
    project = _project(tmp_path, None)
    findings = execute_validation(schema=project / "schema.dbml", mapping=project / "mapping.yaml")
    assert FindingCode.FORM_HELP_OFF not in [f.code for f in findings]


def test_refused_help_settings_do_not_also_report_the_off_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(tmp_path, f"DBMLSP_HELP_BASE_URL={BASE}\n")
    with pytest.raises(typer.Exit):
        _run(project, tmp_path / "out")
    assert "form_help_off" not in capsys.readouterr().err
