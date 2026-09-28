"""`dbml-sharepoint blueprints`: every installed blueprint, its package and its licence."""

from pathlib import Path

import pytest
from _catalogue_fixtures import CORE_LICENSE, Provider, install, write_family
from typer.testing import CliRunner

from dbml_sharepoint import catalogue
from dbml_sharepoint.catalogue import CORE_DISTRIBUTION, available_solutions
from dbml_sharepoint.cli import app
from dbml_sharepoint.pipeline import execute_blueprints

runner = CliRunner()

_HEADER = ["Blueprint", "Title", "Package", "Licence"]


def test_core_alone_lists_every_template_with_core_s_package_and_licence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site")
    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0].split() == _HEADER
    assert len(lines) == 1 + len(available_solutions())
    row = next(line for line in lines if line.startswith("visitor-log "))
    assert row.split()[-2:] == [CORE_DISTRIBUTION, CORE_LICENSE]


def test_a_provider_s_templates_are_listed_after_core_s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[-1].split() == [
        "acme-thing", "Acme", "thing", "acme-packs", "BUSL-1.1",
    ]


def test_a_hidden_template_is_named_once_and_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expected while a provider and core both ship a pack, so it informs rather than fails."""
    packs = tmp_path / "packs"
    write_family(packs, "visitor-log", {"license": "BUSL-1.1"})
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 0, result.output
    assert result.stdout.count("Hidden:") == 1
    assert (
        "Hidden: 1 blueprint from acme-packs shares an id with one from dbml-sharepoint, "
        "which is offered instead: visitor-log"
    ) in result.stdout


def test_a_refused_pack_is_named_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_family(packs, "acme-thing")  # core's licence, inside a BUSL-1.1 distribution
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert "Not offered: acme-packs:" in result.stdout
    assert not any(line.startswith("acme-thing ") for line in result.stdout.splitlines())


def test_an_unreadable_provider_exits_1_with_its_name_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", tmp_path / "missing"))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert result.stderr.startswith("acme-packs: ")
    assert result.stdout == ""


def test_execute_solutions_reports_whether_every_pack_was_offered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site")
    text, every_pack_offered = execute_blueprints()
    assert every_pack_offered
    assert text.splitlines()[0].split() == _HEADER


def test_a_provider_that_fails_to_load_exits_1_with_its_name_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", ImportError("gone")))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert result.stderr.startswith("acme-packs: ")
    assert "failed to load: ImportError: gone" in result.stderr


def test_a_provider_journey_that_will_not_parse_exits_1_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    (packs / "journeys").mkdir(parents=True)
    (packs / "journeys" / "broken.md").write_text("no front matter\n", encoding="utf-8")
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert result.stderr.startswith("acme-packs: ")


def test_an_installation_offering_no_template_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wheel missing its packs lists nothing, which must not pass as a clean check."""
    install(monkeypatch, tmp_path / "site")
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path / "missing")

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert "No blueprint is offered" in result.stdout


def test_a_provider_error_naming_an_unprintable_path_is_printed_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / ("miss" + chr(0x1B) + "[2Jing")
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", missing))

    result = runner.invoke(app, ["blueprints"])

    assert result.exit_code == 1
    assert chr(0x1B) not in result.stderr
    assert "miss\\x1b[2Jing" in result.stderr
