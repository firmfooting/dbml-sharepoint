import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from dbml_sharepoint import __version__
from dbml_sharepoint.bundle import sha256_lf
from dbml_sharepoint.cli import app
from dbml_sharepoint.extension import BaseExtension

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_help_lists_build_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout


def test_help_still_renders_as_rich_panels() -> None:
    """The CLI's help screen is its user surface, and nothing else asserts it.

    `test_help_lists_build_command` above only looks for the substring "build",
    which survives rich rendering collapsing entirely -- to plain text, to a
    stack trace fragment, to anything containing those five letters. A rich or
    typer major that broke the panel layout would pass the whole suite.

    That is not hypothetical: the rich 13 -> 15 bump in #48 was green on 1292
    tests, and the only way to know the help screen still rendered was to run it
    by hand and diff the output. This test is that check, automated, so a
    dependency bump can be merged on CI alone.

    Asserted here are structural invariants, not exact output -- box-drawing
    characters prove rich is still drawing panels rather than falling back to
    plain text, and the section headings prove typer still groups them. Exact
    spacing and wrapping are deliberately not asserted; those change legitimately
    between versions and pinning them would make this test noise.
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout

    # Rich is still drawing boxes, not emitting a plain-text fallback.
    for corner in ("┌", "─", "│", "└"):
        assert corner in out, (
            f"help output lost the {corner!r} border: rich is not rendering panels"
        )

    # Typer is still grouping into its two named panels.
    assert "Usage:" in out
    for heading in ("Options", "Commands"):
        assert heading in out, f"help output lost the {heading!r} panel heading"

    # Every registered command is listed. A command silently dropped from the
    # help screen is invisible to anyone who has not read the source.
    for command in ("build", "report", "version"):
        assert command in out, f"{command!r} is missing from the help screen"


def test_version_command_available_on_direct_module_run() -> None:
    """Regression: the `version` command must be registered *before* the
    ``if __name__ == "__main__"`` guard. When the module is run directly
    (``python -m dbml_sharepoint.cli``), the guard executes ``app()`` inline, so
    any command defined after it is never registered in that execution mode.
    """
    result = subprocess.run(
        [sys.executable, "-m", "dbml_sharepoint.cli", "version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # Compare against the package version rather than a literal so
    # release-please version bumps cannot break this regression test.
    assert __version__ in result.stdout


def test_build_writes_deploy_js_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "deploy.js").exists()
    assert (out / "deploy-manifest.md").exists()


def test_build_writes_full_bundle(tmp_path: Path) -> None:
    """A plain build (no flags) emits the complete bundle: scripts, both
    manifests, INDEX.md and checksums.txt."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    for name in ("deploy.js", "rollback.js", "assess.js", "deploy-manifest.md",
                 "assess-manifest.md", "INDEX.md", "checksums.txt"):
        assert (out / name).exists(), name
    # assess.js stays read-only (no write verbs).
    assert "X-HTTP-Method" not in (out / "assess.js").read_text(encoding="utf-8")
    # The always-generated scripts carry the provenance timestamp.
    assert "Generated at:" in (out / "rollback.js").read_text(encoding="utf-8")
    assert "Generated at:" in (out / "assess.js").read_text(encoding="utf-8")
    # Reporting ships with every build.
    assert (out / "reporting" / "REPORTING.md").exists()
    assert (out / "reporting" / "data-dictionary.md").exists()
    assert (out / "reporting" / "sql" / "views.sql").exists()
    assert list((out / "reporting" / "powerquery").glob("*.pq"))
    assert "`reporting/`" in (out / "INDEX.md").read_text(encoding="utf-8")


def test_build_checksums_validate_and_cover_the_bundle(tmp_path: Path) -> None:
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    lines = (out / "checksums.txt").read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in lines:
        digest, _, relpath = line.partition("  ")
        listed[relpath] = digest
    base = {
        "deploy.js", "rollback.js", "assess.js",
        "deploy-manifest.md", "assess-manifest.md", "INDEX.md",
    }
    assert base <= set(listed)
    assert "reporting/sql/views.sql" in listed
    assert "reporting/REPORTING.md" in listed
    assert "reporting/data-dictionary.md" in listed
    assert any(p.startswith("reporting/powerquery/") for p in listed)
    assert not any("\\" in p for p in listed)
    for relpath, digest in listed.items():
        assert digest == sha256_lf((out / relpath).read_text(encoding="utf-8")), relpath


def test_validation_failure_clears_stale_artifacts(tmp_path: Path) -> None:
    """A failed build must leave only its error manifest — a stale script
    or stale INDEX/checksums beside it could send an operator to the wrong
    release."""
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js", "rollback.js", "assess.js", "assess-manifest.md",
                 "INDEX.md", "checksums.txt"):
        (out / name).write_text("stale", encoding="utf-8")
    (out / "reporting").mkdir()
    (out / "reporting" / "stale.pq").write_text("stale", encoding="utf-8")
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        (FIXTURES / "simple.dbml")
        .read_text(encoding="utf-8")
        .replace("Status    status     [not null, default: 'Open']", "Status    choice"),
        encoding="utf-8",
    )
    result = runner.invoke(app, [
        "build",
        "--schema", str(bad),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 1
    for name in ("deploy.js", "rollback.js", "assess.js", "assess-manifest.md",
                 "INDEX.md", "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_build_rejects_invalid_site_role(tmp_path: Path) -> None:
    """Regression: a misspelled --site-role must fail fast instead of being
    silently filtered to an empty deploy plan that still exits 0."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "commitee",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert not (out / "deploy.js").exists()


def test_build_rejects_extension_that_requires_project_cli(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """A project-only extension must fail before creating any artifact."""

    class ProjectOnlyExtension(BaseExtension):
        name = "project_only"
        requires_project_cli = True

    def resolve_project_only(_name: str | None) -> BaseExtension:
        return ProjectOnlyExtension()

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "dbml_sharepoint.cli.resolve_extension",
        resolve_project_only,
    )
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--extension", "project_only",
    ])

    assert result.exit_code == 2
    assert "requires its project-specific CLI" in result.output
    assert "Use the extension's project CLI instead" in result.output
    # clear_generated ran first (creating out), but nothing was generated.
    assert not any(out.iterdir())


def test_build_rejects_non_https_site_url(tmp_path: Path) -> None:
    """A5: a non-https / malformed --site-url is rejected at parse time (it is
    interpolated into deploy.js and drives the site-match preflight)."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "http://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert not (out / "deploy.js").exists()


def test_build_reports_validation_errors_without_crashing(tmp_path: Path) -> None:
    """Regression: a schema with an unsupported column type must exit via the
    validation-error path (writing a findings manifest, exit 1), not crash
    inside ``build_schema_json`` when ``map_column`` raises ``ValueError``
    before the error-reporting branch runs.
    """
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        (FIXTURES / "simple.dbml")
        .read_text(encoding="utf-8")
        .replace("Status    status     [not null, default: 'Open']", "Status    choice"),
        encoding="utf-8",
    )
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(bad),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 1
    # Must be the deliberate abort, not an unhandled crash in schema rendering.
    assert not isinstance(result.exception, ValueError), result.output
    # The findings manifest is still written before aborting.
    assert (out / "deploy-manifest.md").exists()
    assert not (out / "deploy.js").exists()


def test_build_dry_run_writes_manifest_but_no_js(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js", "rollback.js", "assess.js", "INDEX.md", "checksums.txt"):
        (out / name).write_text("stale", encoding="utf-8")
    (out / "reporting").mkdir()
    (out / "reporting" / "stale.pq").write_text("stale", encoding="utf-8")
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    for name in ("deploy.js", "rollback.js", "assess.js", "INDEX.md", "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()


# --- Config errors are messages, not crashes --------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the real CLI in a subprocess.

    CliRunner CATCHES the exception and stores it on the result, so a
    traceback never reaches its stdout — a test written against it passes
    whether or not the operator sees 20 lines of loader internals. Only a
    real process shows what the person running the tool actually gets.
    """
    return subprocess.run(  # noqa: S603 - args are literals from this module
        [sys.executable, "-m", "dbml_sharepoint.cli", *args],
        capture_output=True, text=True, check=False,
    )


def _bad_mapping(tmp_path: Path, section: str) -> Path:
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n" + section,
        encoding="utf-8",
    )
    return tmp_path / "m.yaml"


def test_a_wrong_mapping_key_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    """A wrong key printed ~20 lines of mapping_loader internals before the
    one useful sentence. The person who hits this is a SharePoint admin
    editing YAML; they cannot act on a single frame of it, and will paste
    the whole thing into a support channel. Semantic errors are already
    clean single lines, so the contrast made a config typo look like a
    crash in the tool."""
    mapping = _bad_mapping(
        tmp_path,
        "form_visibility:\n"
        "  Project:\n"
        "    columns:\n"
        "      Status: { new: false, edit: false }\n",
    )
    result = _cli(
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(mapping),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    # 1, not merely non-zero: the documented table in cli.md gives 1 to
    # "the build refused", which includes an unreadable or invalid input
    # file, and reserves 2 for usage errors typer raises before the
    # pipeline runs. A loose != 0 let a 2 regress past this test.
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in output, output
    assert "mapping_loader.py" not in output, output
    # The useful sentence survives, and names the offending key.
    assert "edit" in output
    assert "form_visibility.Project.columns.Status" in output
    # One line for the operator, not a stack.
    assert len([ln for ln in output.splitlines() if ln.strip()]) <= 2, output


def test_a_malformed_release_file_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    (tmp_path / "release.yaml").write_text('date: "2026-01-01"\n', encoding="utf-8")
    result = _cli(
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(tmp_path / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    # 1, not merely non-zero: the documented table in cli.md gives 1 to
    # "the build refused", which includes an unreadable or invalid input
    # file, and reserves 2 for usage errors typer raises before the
    # pipeline runs. A loose != 0 let a 2 regress past this test.
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in output, output
    assert "release" in output


def test_a_missing_mapping_file_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    result = _cli(
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(tmp_path / "nope.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    # 1, not merely non-zero: the documented table in cli.md gives 1 to
    # "the build refused", which includes an unreadable or invalid input
    # file, and reserves 2 for usage errors typer raises before the
    # pipeline runs. A loose != 0 let a 2 regress past this test.
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in output, output
    assert "nope.yaml" in output


def test_malformed_dbml_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    schema = tmp_path / "bad.dbml"
    schema.write_text("Table Broken {\n  invalid !!!\n}\n", encoding="utf-8")
    result = _cli(
        "build",
        "--schema", str(schema),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Traceback" not in output, output
    assert "schema" in output and "bad.dbml" in output


def test_unknown_dbml_index_column_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    schema = tmp_path / "bad-index.dbml"
    schema.write_text(
        "Table Risk {\n"
        "  Status nvarchar\n"
        "  indexes { Staus }\n"
        "}\n",
        encoding="utf-8",
    )
    result = _cli(
        "build",
        "--schema", str(schema),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "Traceback" not in output, output
    assert "bad-index.dbml" in output
    assert "Staus" in output
    # pydbml names the table with a literal, unformatted '{self.name}'. The
    # whole clause is dropped, so the sentence must not trail off mid-phrase.
    assert "{self.name}" not in output, output
    assert "not defined in." not in output, output


def test_report_renders_generator_refusals_as_messages(tmp_path: Path) -> None:
    """`report` does not validate — the generators meet a bad schema first.

    They refuse by raising, and unhandled that printed a traceback for a
    hand-edited typo. Both refusals reachable from a parseable schema are
    covered: an unmapped column type (typemap) and a composite DBML index
    (the deploy projection).
    """
    mapping = tmp_path / "m.yaml"
    mapping.write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    refusals = {
        "bad-type.dbml": ("  Status blob\n", "blob"),
        "composite.dbml": (
            ("  Status nvarchar\n  Category nvarchar\n"
             "  indexes { (Status, Category) }\n"),
            "composite",
        ),
    }
    for filename, (body, needle) in refusals.items():
        schema = tmp_path / filename
        schema.write_text(
            "Project t { database_type: 'SharePoint Online' }\n"
            f"Table Risk {{\n  Id int [pk, increment]\n{body}}}\n",
            encoding="utf-8",
        )
        out = tmp_path / f"reports-{filename}"
        result = _cli(
            "report",
            "--schema", str(schema),
            "--mapping", str(mapping),
            "--out", str(out),
        )
        output = result.stdout + result.stderr
        assert result.returncode == 1, output
        assert "Traceback" not in output, output
        assert needle in output, output
        assert "build --dry-run" in output, output
        # Nothing half-written survives the refusal.
        assert not out.exists(), sorted(p.name for p in out.iterdir())


def test_report_replaces_owned_outputs_and_preserves_operator_files(
    tmp_path: Path,
) -> None:
    mapping = tmp_path / "m.yaml"
    mapping.write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "  Legacy: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = tmp_path / "s.dbml"
    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n}\n"
        "Table Legacy {\n  Id int [pk, increment]\n}\n",
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    assert (out / "powerquery" / "APP_Legacy.pq").exists()
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")

    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n}\n",
        encoding="utf-8",
    )
    second = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )

    assert second.returncode == 0, second.stderr
    assert (out / "powerquery" / "APP_Risk.pq").exists()
    assert not (out / "powerquery" / "APP_Legacy.pq").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_report_refusal_clears_previous_generated_outputs(tmp_path: Path) -> None:
    mapping = tmp_path / "m.yaml"
    mapping.write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = tmp_path / "s.dbml"
    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Status nvarchar\n}\n",
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")

    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Status blob\n}\n",
        encoding="utf-8",
    )
    failed = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )

    assert failed.returncode == 1
    assert not (out / "powerquery").exists()
    assert not (out / "sql").exists()
    assert not (out / "REPORTING.md").exists()
    assert not (out / "DATA-DICTIONARY.md").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_report_never_clears_output_before_it_reads_the_schema(tmp_path: Path) -> None:
    """An input error must not destroy the last good report set.

    `--out` is routinely aimed at a directory holding the operator's own
    work, and `sql/`/`powerquery/` are generic enough names to collide with
    it. Clearing on the way in meant a mistyped --schema path — or an
    unknown --site-role, which exits 2 for "usage error, before the
    pipeline runs" — deleted both trees whole before reading anything.
    """
    mapping = tmp_path / "m.yaml"
    mapping.write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    out = tmp_path / "shared"
    (out / "sql").mkdir(parents=True)
    (out / "powerquery").mkdir(parents=True)
    (out / "sql" / "001_migration.sql").write_text("-- hand written", encoding="utf-8")
    (out / "powerquery" / "MyReport.pq").write_text("mine", encoding="utf-8")

    def surviving() -> set[str]:
        return {p.name for p in out.rglob("*") if p.is_file()}

    owned = {"001_migration.sql", "MyReport.pq"}

    missing = _cli(
        "report", "--schema", str(tmp_path / "nope.dbml"),
        "--mapping", str(mapping), "--out", str(out),
    )
    assert missing.returncode == 1, missing.stderr
    assert surviving() == owned

    bad_role = _cli(
        "report", "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(mapping), "--site-role", "nosuchrole", "--out", str(out),
    )
    assert bad_role.returncode == 2, bad_role.stderr
    assert surviving() == owned


def test_report_clearing_spares_operator_files_inside_owned_directories(
    tmp_path: Path,
) -> None:
    """Only the generated names go; a neighbour in sql/ is not ours to delete."""
    mapping = tmp_path / "m.yaml"
    mapping.write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = tmp_path / "s.dbml"
    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Status nvarchar\n}\n",
        encoding="utf-8",
    )
    out = tmp_path / "shared"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping), "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    (out / "sql" / "001_migration.sql").write_text("-- hand written", encoding="utf-8")
    (out / "powerquery" / "notes.md").write_text("mine", encoding="utf-8")

    # A refusal clears what this command wrote — and stops there.
    schema.write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Status blob\n}\n",
        encoding="utf-8",
    )
    refused = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping), "--out", str(out),
    )

    assert refused.returncode == 1
    assert not (out / "sql" / "views.sql").exists()
    assert not (out / "DATA-DICTIONARY.md").exists()
    assert (out / "sql" / "001_migration.sql").read_text(encoding="utf-8") == "-- hand written"
    assert (out / "powerquery" / "notes.md").read_text(encoding="utf-8") == "mine"
    # The directories survive precisely because the operator left something
    # in them; with nothing but generated files they go too.
    assert (out / "sql").is_dir()
    assert (out / "powerquery").is_dir()


def test_report_reports_config_errors_the_same_way(tmp_path: Path) -> None:
    """`report` loads the same three files and had the same behaviour."""
    mapping = _bad_mapping(tmp_path, "versioning:\n  default:\n    enable_versionin: false\n")
    out = tmp_path / "reports"
    (out / "powerquery").mkdir(parents=True)
    (out / "powerquery" / "stale.pq").write_text("stale", encoding="utf-8")
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")
    result = _cli(
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(mapping),
        "--out", str(out),
    )
    output = result.stdout + result.stderr
    # 1, not merely non-zero: the documented table in cli.md gives 1 to
    # "the build refused", which includes an unreadable or invalid input
    # file, and reserves 2 for usage errors typer raises before the
    # pipeline runs. A loose != 0 let a 2 regress past this test.
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in output, output
    assert "enable_versionin" in output
    # A config that never loaded says nothing about the report, so the last
    # good set survives. Clearing here destroyed output on a YAML typo.
    assert (out / "powerquery" / "stale.pq").read_text(encoding="utf-8") == "stale"
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"
