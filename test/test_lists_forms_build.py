"""A lists-forms.yaml blueprint builds its deploy step and manifest end to end."""

import shutil
import subprocess
from pathlib import Path

import pytest
import typer
from _paths import FIXTURES

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.pipeline import execute_build
from dbml_sharepoint.testing.node import NODE

LISTS_FORMS = FIXTURES / "lists_forms"
EPOCH = 1759276800

# The refused example of the spec: a line break in the title, and no Title question.
_REFUSED = """\
Request:
  forms:
    - title: "Intake\\nform"
      thank_you: Track it at https://example.com/track
      questions:
        - column: Status
          required: true
        - column: Site
"""


def _build(out: Path, project: Path = LISTS_FORMS) -> Path:
    execute_build(
        schema=project / "schema.dbml", mapping=project / "mapping.yaml",
        release=FIXTURES / "release.yaml", site_url="https://example.sharepoint.com/sites/ci",
        time_zone="Australia/Melbourne", site_role="default", out=out,
        source_date_epoch=EPOCH,
    )
    return out


def _copy(tmp_path: Path) -> Path:
    project = tmp_path / "p"
    shutil.copytree(LISTS_FORMS, project)
    return project


def _manifest(out: Path) -> str:
    return (out / "deploy-manifest.md").read_text(encoding="utf-8")


def test_build_writes_the_lists_forms_step_and_payload(tmp_path: Path) -> None:
    deploy = (_build(tmp_path / "out") / "deploy.js.txt").read_text(encoding="utf-8")
    assert f"// === Phase {phase_number('lists_forms')}: Lists forms ===" in deploy
    assert '"lists_forms": [' in deploy
    assert '"title": "Facilities request"' in deploy


def test_manifest_lists_each_form_and_what_is_left_to_the_owner(tmp_path: Path) -> None:
    manifest = _manifest(_build(tmp_path / "out"))
    section = manifest.split(f"## Phase {phase_number('lists_forms')}: Lists forms", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "Facilities request" in section
    assert "Title (What needs fixing?)" in section
    assert "Details (Details)" in section
    left = next(line for line in section.splitlines() if "Left to the owner" in line)
    assert "`accepting_responses`" in left
    assert "`closed_message`" in left
    assert "`opens`" not in left
    assert "`_FormSourceId_0`" in section
    assert "Old intake" in section
    assert "seed" in section


def test_manifest_puts_a_declared_operational_key_in_force(tmp_path: Path) -> None:
    project = _copy(tmp_path)
    path = project / "lists-forms.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "      one_response_per_person: false\n",
            "      one_response_per_person: false\n      accepting_responses: false\n",
        ),
        encoding="utf-8",
    )
    manifest = _manifest(_build(tmp_path / "out", project))
    settings = next(line for line in manifest.splitlines() if "Settings in force" in line)
    assert "`accepting_responses`: no" in settings
    left = next(line for line in manifest.splitlines() if "Left to the owner" in line)
    assert "`accepting_responses`" not in left


def test_manifest_without_lists_forms_says_none(tmp_path: Path) -> None:
    project = _copy(tmp_path)
    (project / "lists-forms.yaml").unlink()
    manifest = _manifest(_build(tmp_path / "out", project))
    section = manifest.split(f"## Phase {phase_number('lists_forms')}: Lists forms", 1)[1]
    assert section.split("\n## ", 1)[0].strip() == "_(none; no list declares Lists forms)_"


def test_refused_declaration_fails_the_build_naming_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    project = _copy(tmp_path)
    (project / "lists-forms.yaml").write_text(_REFUSED, encoding="utf-8")
    with pytest.raises(typer.Exit):
        _build(tmp_path / "out", project)
    err = capsys.readouterr().err
    assert "lists_form_title_invalid" in err
    assert "lists_form_required_column_missing" in err
    assert not (tmp_path / "out" / "deploy.js.txt").exists()


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_emitted_scripts_parse(tmp_path: Path) -> None:
    deploy = _build(tmp_path / "out") / "deploy.js.txt"
    script = tmp_path / "deploy.js"
    shutil.copyfile(deploy, script)
    assert NODE is not None
    result = subprocess.run(  # noqa: S603
        [NODE, "--check", str(script)], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
