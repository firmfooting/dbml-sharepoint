import ast
import hashlib
import inspect
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from _builders import ID_PK, TITLE, table
from _packs import (
    blocks,
    entities,
    entity,
    replaced,
    with_tail,
    write_dbml,
    write_mapping,
)
from _paths import FIXTURES, PACKAGE, SOLUTION_TEMPLATES
from typer.testing import CliRunner, Result

from dbml_sharepoint import __version__
from dbml_sharepoint.catalogue import (
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.cli import (
    app,
    build,
    execute_build,
    execute_extraction,
    extract,
)
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.model.env_file import ENV_FILENAME, ENV_SETTINGS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _cwd_has_no_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module runs with an empty current directory.

    `build` reads a CWD-relative `dbml-sharepoint.env` by default
    (`_resolve_env_file`), so without this a contributor's own file sitting
    at the repository root changes what these tests observe -- 22 of them
    fail if one is there, because a build that expects no env file default
    silently gets one anyway. `tmp_path` is unique per test and guaranteed
    not to contain one; a test that wants the file present writes it there
    explicitly. Mirrors `test_wizard.py`'s `_cwd_has_no_env_file`.
    """
    monkeypatch.chdir(tmp_path)


#: Terminal styling, stripped before any assertion about a rendered message.
#: CI emits it and a developer terminal usually does not, which is enough on
#: its own to make an assertion pass locally and fail on both runners --
#: `test_help_still_renders_as_rich_panels` records the same lesson about
#: box-drawing corners.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _normalise_rendered_output(text: str) -> str:
    """Reduce rich's rendered output to the words it actually contains.

    Strips ANSI escapes, strips the panel-border character, and collapses
    whitespace. Rich decides wrap width from the environment, so a raw
    string can land on one line at a wide width and get split across two,
    border included, at a narrow one; normalising removes that dependency
    instead of pinning the width. A test using this does not care, and
    should not need to know, how many columns rich rendered at.

    Use this for a PHRASE, where every break rich can make falls between
    words. For a single token, use `_rendered_without_whitespace` instead,
    and read why there.
    """
    return " ".join(_ANSI.sub("", text).replace("│", " ").split())


def _rendered_without_whitespace(text: str) -> str:
    """The same, with whitespace REMOVED rather than collapsed.

    Rich breaks a long line wherever it must, including inside a filename.
    CI caught this: a temp path wrapped mid-token and `nowhere.env` arrived
    as `now here.env`, so collapsing to single spaces turned a break inside
    the token into a space that was never in it. The Windows path was short
    enough not to split there, which is why it passed locally.

    So an assertion about one unbroken token compares against this, and an
    assertion about a phrase compares against the collapsing helper above.
    Neither pins the terminal width.
    """
    return "".join(_ANSI.sub("", text).replace("│", " ").split())


def test_help_lists_build_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout


def test_a_bare_invocation_prints_help_when_not_a_terminal() -> None:
    """The wizard is the default, but only for a human at a terminal.

    A bare `dbml-sharepoint` in CI, a cron job or a Dockerfile must not
    block on a prompt nobody can answer. Printing help and exiting 0 is
    what a bare invocation did before the wizard existed, so nothing that
    already scripted this command changes behaviour.
    """
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "report" in result.stdout


def test_the_wizard_is_reachable_by_name() -> None:
    """`new` exists so the wizard can be asked for explicitly, and so it
    appears in --help rather than being an undocumented default."""
    result = runner.invoke(app, ["--help"])
    assert "new" in result.stdout


def test_every_documented_command_survived_the_wizard_default() -> None:
    """Adding a callback with `invoke_without_command=True` is exactly the
    change that can turn a subcommand into a no-op: the callback runs for
    every invocation, and an early `raise typer.Exit` in it would swallow
    them all while `--help` kept listing them."""
    for command in (
        "build", "validate", "report", "extract", "extract-script",
        "protection-script", "columns-script", "version",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"{command} --help failed"
        assert command in result.stdout


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
    #
    # The CORNERS are platform-dependent and must not be pinned. Rich's panel
    # box is ROUNDED ('╭'), but Box.substitute swaps in SQUARE ('┌') when the
    # console reports legacy_windows. So this assertion sees '╭' on the Linux
    # runner and '┌' on a Windows one. An earlier version of this test pinned
    # the square set, passed locally, and failed both CI runners.
    assert "─" in out and "│" in out, (
        "help output has no box edges: rich is not rendering panels"
    )
    assert any(c in out for c in "┌┐└┘╭╮╰╯"), (
        "help output has no box corners: rich is not rendering panels"
    )

    # Typer is still grouping into its two named panels.
    assert "Usage:" in out
    for heading in ("Options", "Commands"):
        assert heading in out, f"help output lost the {heading!r} panel heading"

    # Every registered command is listed. A command silently dropped from the
    # help screen is invisible to anyone who has not read the source.
    for command in (
        "build", "validate", "report", "extract", "extract-script",
        "protection-script", "columns-script", "version",
    ):
        assert command in out, f"{command!r} is missing from the help screen"


def test_help_text_is_ascii() -> None:
    """Every string the help screen prints must be ASCII.

    `--help` is the first command anybody runs, and a non-ASCII character in
    a help string turns it into a traceback rather than a help screen:

        UnicodeEncodeError: 'charmap' codec can't encode character
        '\\u2192' in position 13: character maps to <undefined>

    ASCII, and not "encodable in cp1252". An earlier version of this test
    used cp1252 on the reasoning that it stated the real constraint rather
    than a stricter invented one. That was wrong, and measurably so: cp1252
    is the ANSI code page, but a Windows CONSOLE defaults to an OEM one, and
    the three disagree about different characters.

        character        cp1252   cp850   cp437
        U+2192  ->        FAILS   FAILS   FAILS
        U+2014  --        ok      FAILS   FAILS
        U+2026  ...       ok      FAILS   FAILS
        U+2264  <=        FAILS   FAILS   ok

    So no single code page is the constraint, and cp1252 explicitly blessed
    the em-dash in `--seed`'s help -- which then still crashed
    `dbml-sharepoint build --help` under `chcp 437`. ASCII is the only rule
    that holds for all of them, and it is the rule that is easy to keep.

    Deliberately NOT asserted over the *rendered* output: rich substitutes
    ASCII box-drawing when it detects a legacy console, so the frame is
    already safe and only the strings we author are at risk. Those are what
    this walks.
    """
    import typer.main

    def texts(command: object, path: str) -> list[tuple[str, str]]:
        found = [
            (f"{path} {attr}", value)
            for attr in ("help", "short_help", "epilog")
            if isinstance(value := getattr(command, attr, None), str)
        ]
        for param in getattr(command, "params", ()):
            if isinstance(value := getattr(param, "help", None), str):
                found.append((f"{path} {param.name} help", value))
        for name, sub in getattr(command, "commands", {}).items():
            found.extend(texts(sub, f"{path} {name}"))
        return found

    offenders = [
        f"{where}: {sorted({c for c in text if ord(c) > 127})} in {text!r}"
        for where, text in texts(typer.main.get_command(app), "dbml-sharepoint")
        if not text.isascii()
    ]
    assert not offenders, "help text is not ASCII:\n" + "\n".join(offenders)


#: Modules whose string literals reach a console rather than a file.
#:
#: `analysis/` and `model/` are where finding messages and loader errors are
#: written; `cli`, the two wizards and `catalogue` are the terminal surface
#: itself.
#:
#: Deliberately EXCLUDES the generators and `bundle`. Those write artifacts
#: through `write_artifact`, which is UTF-8 by contract, so nothing about a
#: console makes a non-ASCII literal there unsafe. `test_shipped_text_is_ascii`
#: bans it anyway, across the whole package, for the reason given in that file.
#: The rule THIS list draws is about bytes that go to a console, not about
#: prose in general; comments and docstrings are excluded below for the same
#: reason.
#:
#: Matched against the whole relative path, not just its first part, so a
#: console-bound module inside a subpackage can be named on its own.
_CONSOLE_BOUND = (
    "analysis",
    "model",
    "cli.py",
    "wizard.py",
    "catalogue.py",
    "extract/wizard.py",
)


def _console_bound_modules() -> list[Path]:
    return [
        path
        for path in sorted(PACKAGE.rglob("*.py"))
        if (relative := path.relative_to(PACKAGE)).parts[0] in _CONSOLE_BOUND
        or relative.as_posix() in _CONSOLE_BOUND
    ]


def test_messages_bound_for_a_console_are_ascii() -> None:
    """Finding messages and loader errors must be ASCII too, not just help.

    These reach the terminal through `typer.echo`, which does not raise on an
    unencodable character -- click falls back and prints the escape, so
    `unique without not_null -- uniqueness ...` came out as
    `unique without not_null \\u2014 uniqueness ...` on an OEM console. Not a
    crash, but a finding is a sentence somebody reads while something is
    wrong, and a literal escape sequence in the middle of it is noise at
    exactly the wrong moment.

    Comments and docstrings are excluded here because they are read in an
    editor and never encoded to a console. The em-dash and shipped-text gates
    read whole files, and MEASURED 2026-08-16 `src/` holds neither an em dash
    nor any other non-ASCII character.
    """
    import ast

    offenders = []
    for path in _console_bound_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            doc
            for node in ast.walk(tree)
            if isinstance(
                node,
                ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
            )
            and (doc := ast.get_docstring(node, clean=False))
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value not in docstrings
                and not node.value.isascii()
            ):
                bad = sorted({c for c in node.value if ord(c) > 127})
                offenders.append(f"{path.name}:{node.lineno}: {bad} in {node.value[:60]!r}")
    assert not offenders, (
        "string literals bound for a console are not ASCII:\n" + "\n".join(offenders)
    )


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
    assert (out / "deploy.js.txt").exists()
    assert (out / "deploy-manifest.md").exists()


def test_build_writes_full_bundle(tmp_path: Path) -> None:
    """A plain build (no flags) emits the complete bundle: scripts, both
    manifests, index.md and checksums.txt."""
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
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt",
                 "deploy-manifest.md", "assess-manifest.md", "index.md", "checksums.txt"):
        assert (out / name).exists(), name
    # assess.js.txt stays read-only (no write verbs).
    assert "X-HTTP-Method" not in (out / "assess.js.txt").read_text(encoding="utf-8")
    # The always-generated scripts carry the provenance timestamp.
    assert "Generated at:" in (out / "rollback.js.txt").read_text(encoding="utf-8")
    assert "Generated at:" in (out / "assess.js.txt").read_text(encoding="utf-8")
    # Reporting ships with every build.
    assert (out / "reporting" / "guide.md").exists()
    assert (out / "reporting" / "data-dictionary.md").exists()
    assert (out / "reporting" / "sql" / "views.sql").exists()
    assert list((out / "reporting" / "powerquery").glob("*.pq"))
    assert "`reporting/`" in (out / "index.md").read_text(encoding="utf-8")


def test_a_built_reporting_pack_needs_no_parameter(tmp_path: Path) -> None:
    """`build` is given `--site-url`, so the queries it ships already know
    the site. The seam is `emit_bundle` -> `emit_reporting`, and it is
    threaded rather than reconstructed, so the only way to see it is from
    the artifact on disk.

    `report` has no site and still emits the parameter form; that shape is
    covered in `test_reportgen.py`.
    """
    site = "https://example.sharepoint.com/sites/test"
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", site,
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    checked = 0
    for path in sorted((out / "reporting" / "powerquery").glob("*.pq")):
        text = path.read_text(encoding="utf-8")
        if "SiteRoot" not in text:
            continue  # a static #table query, no site in it
        assert f'    SiteUrl = "{site}",' in text.splitlines(), path.name
        assert "// Requires" not in text, path.name
        checked += 1
    # Three lists plus the drift audit -- named as a count so a build that
    # emitted no site-reading query could not pass this vacuously.
    assert checked == 4
    sql = (out / "reporting" / "sql" / "views.sql").read_text(encoding="utf-8")
    assert f":setvar SiteUrl {site}" in sql.splitlines()
    assert "yourtenant" not in sql


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
        "deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt",
        "deploy-manifest.md", "assess-manifest.md", "index.md",
    }
    assert base <= set(listed)
    assert "reporting/sql/views.sql" in listed
    assert "reporting/guide.md" in listed
    assert "reporting/data-dictionary.md" in listed
    assert any(p.startswith("reporting/powerquery/") for p in listed)
    assert not any("\\" in p for p in listed)
    for relpath, digest in listed.items():
        assert digest == hashlib.sha256((out / relpath).read_bytes()).hexdigest(), (
            relpath
        )


def test_a_windows_built_bundle_verifies_with_raw_byte_hashing(
    tmp_path: Path,
) -> None:
    """`sha256sum -c` and `Get-FileHash` hash the bytes ON DISK.

    This is the property that makes the bundle verifiable with ordinary
    tools instead of a bespoke one-liner, and it is the one the suite could
    not see. `write_checksums` used to digest `sha256_lf(read_text(...))`
    and the coverage test asserted the same expression back -- normalising
    BOTH sides, so it passed however the file was actually written. The
    manifest now records the digest of the bytes, and both tests check it
    the way an external tool would.

    Kept as a separate test from the coverage one above because they fail
    for different reasons: that one catches a MISSING entry, this one
    catches a WRONG one.
    """
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

    mismatched = []
    for line in (out / "checksums.txt").read_text(encoding="utf-8").splitlines():
        digest, _, relpath = line.partition("  ")
        raw = hashlib.sha256((out / relpath).read_bytes()).hexdigest()
        if raw != digest:
            mismatched.append(relpath)
    assert not mismatched, f"digest does not describe the bytes on disk: {mismatched}"


def test_no_emitted_artifact_carries_a_carriage_return(tmp_path: Path) -> None:
    """One line-ending policy for the whole bundle: LF, everywhere.

    Asserted over the WHOLE bundle rather than the files someone remembered
    to list -- the CRLF got in through `reporting/`, which no checksum test
    was looking at, and a new writer would land the same way.
    """
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

    offenders = [
        str(p.relative_to(out))
        for p in sorted(out.rglob("*"))
        if p.is_file() and b"\r" in p.read_bytes()
    ]
    assert not offenders, f"CRLF in emitted artifacts: {offenders}"


def test_the_reader_flag_needs_a_group_to_enrol_into(tmp_path: Path) -> None:
    """Fail closed, loudly, at build time.

    `sharepoint-mapping.yaml` declares a group but none with
    `enroll_enterprise_reader: true`, so this is exactly the gap the
    refusal exists to close: accepting the address and emitting a bundle
    that enrols nobody would deploy green, and the operator would only
    find out when a report came back short, weeks later.
    """
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--enterprise-reader", "svc-reporting@example.org",
    ])
    assert result.exit_code != 0
    assert "enroll_enterprise_reader" in result.output
    assert not (out / "deploy.js.txt").exists()


@pytest.mark.parametrize(("bad", "guard_fragment"), [
    # No '@' at all: the one-'@' guard.
    ("not-an-address", "one '@'"),
    # Two '@': the same one-'@' guard, from the other side.
    ("two@at@signs.example", "one '@'"),
    # One '@', but whitespace: the whitespace/'|' guard.
    ("has space@example.org", "no whitespace"),
    # The one that matters: a claims login name contains exactly one '@'
    # and would sail past an '@'-only check, then hand `web/ensureuser` a
    # principal other than the user it appears to name. Same guard as the
    # whitespace case, fired for '|' instead.
    ("i:0#.f|membership|svc@example.org", "no '|'"),
])
def test_a_malformed_reader_address_is_refused(
    tmp_path: Path, bad: str, guard_fragment: str,
) -> None:
    """Pointed at a mapping that DOES declare an enroll_enterprise_reader
    group, so a refusal here can only come from `validate_enterprise_reader`
    itself -- against `sharepoint-mapping.yaml` (no such group), all four
    cases would refuse identically via the "no group to enrol into" check
    regardless of the address, and gutting the validator would leave every
    case here green. Asserting the guard-specific message fragment, not just
    a nonzero exit code, is what makes that failure mode visible: a message
    naming the wrong guard (or no message at all, from a deleted validator)
    fails this even when the exit code alone would not.
    """
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--enterprise-reader", bad,
    ])
    assert result.exit_code != 0
    assert "enroll_enterprise_reader" not in result.output, (
        "refused via the wrong guard (missing group, not a bad address)"
    )
    assert guard_fragment in result.output, result.output
    assert not (out / "deploy.js.txt").exists()


def test_no_reader_flag_emits_no_enrolment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opt-in means the code path does not exist unless asked for.

    Asserted primarily against what `execute_build` actually hands
    `emit_bundle` -- a text-only check against `deploy.js.txt` would pass
    whether or not `enterprise_reader` reached the render context at all,
    since Task 5 (not this one) is what makes the template consume it. The
    spy wraps the real `emit_bundle` rather than replacing it, so the build
    still runs for real and the text assertion stays meaningful too.
    """
    from dbml_sharepoint.bundle import emit_bundle as real_emit_bundle

    captured: dict[str, object] = {}

    def spy(out: Path, **kwargs: Any) -> str:
        captured.update(kwargs)
        return real_emit_bundle(out, **kwargs)

    # String target, matching
    # `test_build_rejects_extension_that_requires_project_cli`: `emit_bundle`
    # is imported into `cli`'s namespace rather than defined there, and mypy
    # (under `strict`) flags `setattr(cli, "emit_bundle", ...)` as patching a
    # name the module does not explicitly re-export.
    monkeypatch.setattr("dbml_sharepoint.cli.emit_bundle", spy)

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
    assert captured["enterprise_reader"] is None
    assert "enterprise-reader" not in (out / "deploy.js.txt").read_text(encoding="utf-8")


def test_a_valid_reader_flag_reaches_emit_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of `test_no_reader_flag_emits_no_enrolment`: proves the
    literal address, not just `None`, survives the trip through
    `execute_build` into `emit_bundle`.

    Every OTHER test with a well-formed address either hits the "no group"
    refusal (`sharepoint-mapping.yaml`) or replaces `execute_build` wholesale
    (the wizard's `_capture_build`), so nothing before this proved a
    non-None value ever reaches `emit_bundle` -- a build that hard-coded
    `enterprise_reader=None` at that call site would still pass every other
    test in this file.
    """
    from dbml_sharepoint.bundle import emit_bundle as real_emit_bundle

    captured: dict[str, object] = {}

    def spy(out: Path, **kwargs: Any) -> str:
        captured.update(kwargs)
        return real_emit_bundle(out, **kwargs)

    monkeypatch.setattr("dbml_sharepoint.cli.emit_bundle", spy)

    out = tmp_path / "build"
    address = "svc-reporting@example.org"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--enterprise-reader", address,
    ])
    assert result.exit_code == 0, result.output
    assert captured["enterprise_reader"] == address


def test_a_valid_reader_flag_reaches_the_written_manifest(tmp_path: Path) -> None:
    """`deploy-manifest.md` is written by `execute_build` itself, NOT by
    `emit_bundle` -- so the spy test above proves nothing about it.

    This is the artefact the operator reviews BEFORE pasting, and the reader
    enrolment is the one act in the run that `rollback.js.txt` does not
    undo. The manifest generator was never handed the address, so the whole
    warning was missing from the only document positioned to carry it.
    """
    out = tmp_path / "build"
    address = "svc-reporting@example.org"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--enterprise-reader", address,
    ])
    assert result.exit_code == 0, result.output

    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    assert address in manifest
    assert "PERMANENT" in manifest
    assert "does not delete the group" in manifest


def test_the_declined_sentinel_is_treated_as_nobody_not_as_a_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ENTERPRISE_READER_DECLINED` must survive `execute_build` as its own
    state, distinct from both `None` (unset) and a real address, rather than
    being collapsed into either at the first opportunity.

    Run against `sharepoint-mapping-with-reader.yaml`, which DOES declare an
    `enroll_enterprise_reader` group. That choice matters: the old gate was
    `if enterprise_reader is not None`, and the sentinel is not `None`, so a
    build that still used that gate would hand the sentinel to `validate_
    enterprise_reader`, which calls `.strip()` on it and raises an unhandled
    `AttributeError` rather than the clean refusal a bad address gets. This
    test would error, not merely fail, if that regressed -- succeeding here
    proves the sentinel is excluded from the gate on its own terms, not
    merely because it happens to behave like `None` would against a mapping
    with no group to enrol into (which is all `sharepoint-mapping.yaml`
    would prove).

    The spy then proves what `emit_bundle` actually receives: `None`. It and
    `generate_manifest` do not know a third state yet -- teaching them one is
    a later change -- so both must still see the same "nobody" `None` an
    omitted flag produces. `execute_build` narrows to that `str | None` only
    at each site that needs it, so this cannot pass merely because the
    sentinel happened to overwrite the `enterprise_reader` parameter itself
    early and lose the distinction before it reached here.
    """
    from dbml_sharepoint.bundle import emit_bundle as real_emit_bundle
    from dbml_sharepoint.cli import ENTERPRISE_READER_DECLINED, execute_build

    captured: dict[str, object] = {}

    def spy(out: Path, **kwargs: Any) -> str:
        captured.update(kwargs)
        return real_emit_bundle(out, **kwargs)

    monkeypatch.setattr("dbml_sharepoint.cli.emit_bundle", spy)

    out = tmp_path / "build"
    execute_build(
        schema=FIXTURES / "simple.dbml",
        mapping=FIXTURES / "sharepoint-mapping-with-reader.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        out=out,
        enterprise_reader=ENTERPRISE_READER_DECLINED,
    )

    assert captured["enterprise_reader"] is None
    # Not a bare `"enterprise-reader" not in ...` check: this fixture's own
    # group carries that substring in a static description ("Read-only
    # enrolment target for --enterprise-reader") that renders regardless of
    # whether anybody was actually enrolled. `READER_ADDRESS` is declared
    # only inside `_reader_enrolment.js.j2`'s `{% if enterprise_reader %}`
    # guard, so its absence is what actually proves no enrolment code emitted.
    assert "READER_ADDRESS" not in (out / "deploy.js.txt").read_text(encoding="utf-8")


def _write_env_file(path: Path, address: str = "svc-reporting@example.org") -> Path:
    path.write_text(f"DBMLSP_ENTERPRISE_READER={address}\n", encoding="utf-8", newline="\n")
    return path


def test_env_file_missing_at_an_explicit_path_is_an_error(tmp_path: Path) -> None:
    """`--env-file` names a specific file; a typo there must not silently
    build without the settings the operator asked for.

    Asserts on `_normalise_rendered_output(result.output)` rather than
    pinning the terminal width: rich wraps its error panel to whatever
    width the environment gives it, and at a narrow width the path can land
    split across two lines with the panel border in between. Normalising
    removes the coupling between this content assertion and rich's width
    choice, rather than choosing a width wide enough to avoid the wrap.
    """
    missing = tmp_path / "nowhere.env"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
        "--env-file", str(missing),
    ])
    assert result.exit_code == 2
    # The filename is one token and the temp path is long, so rich may break
    # it mid-word. Compare against the whitespace-free form.
    assert "nowhere.env" in _rendered_without_whitespace(result.output)


def test_an_unparsable_env_file_is_refused_with_a_clean_message(tmp_path: Path) -> None:
    """`_resolve_env_settings`'s `except EnvFileError: _config_error(...)`
    was untested: deleting it broke nothing, because `read_env_file`'s own
    `EnvFileSyntaxError` would otherwise propagate as an unhandled exception
    and this test would fail with an error rather than an assertion.

    Also pins the message staying free of the duplicate path `_config_error`
    used to produce: `EnvFileSyntaxError` already names the path itself (see
    `_refuse` in `model/env_file.py`), and `_config_error` used to prepend it
    again -- "[ERROR] env file X: X: line 1: ...".
    """
    env_path = tmp_path / "custom.env"
    env_path.write_text("not a key-value line\n", encoding="utf-8", newline="\n")
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
        "--env-file", str(env_path),
    ])
    assert result.exit_code == 1
    assert "expected KEY=value" in result.output
    assert result.output.count(str(env_path)) == 1
    assert not (out / "deploy.js.txt").exists()


def test_no_env_file_at_the_default_location_is_not_an_error(tmp_path: Path) -> None:
    """No `dbml-sharepoint.env` at all is the ordinary case, not a refusal.

    The module's `_cwd_has_no_env_file` fixture is what actually neutralises
    the default location here: `tmp_path` is guaranteed not to contain one.

    Also pins the "say so explicitly" requirement: an absent env file must
    be a printed line, not silence a later regression could not tell apart
    from a feature that never ran.
    """
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert "No dbml-sharepoint.env file was read." in result.output


def test_env_file_at_the_default_location_is_used(tmp_path: Path) -> None:
    """The other half of the default-location pair: present, it is read."""
    _write_env_file(tmp_path / ENV_FILENAME)
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert "svc-reporting@example.org" in (out / "deploy-manifest.md").read_text(encoding="utf-8")


def test_an_env_file_value_reaches_execute_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of `test_a_valid_reader_flag_reaches_emit_bundle`, sourced
    from `--env-file` at a temp path rather than the default location -- so
    this test is not itself CWD-dependent."""
    from dbml_sharepoint.bundle import emit_bundle as real_emit_bundle

    captured: dict[str, object] = {}

    def spy(out: Path, **kwargs: Any) -> str:
        captured.update(kwargs)
        return real_emit_bundle(out, **kwargs)

    monkeypatch.setattr("dbml_sharepoint.cli.emit_bundle", spy)

    env_path = _write_env_file(tmp_path / "custom.env")
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
        "--env-file", str(env_path),
    ])
    assert result.exit_code == 0, result.output
    assert captured["enterprise_reader"] == "svc-reporting@example.org"


def test_an_explicit_flag_beats_the_env_file(tmp_path: Path) -> None:
    """Precedence, and the provenance record it leaves behind -- in the
    terminal echo AND in the manifest's own env-file line. The manifest
    line used to say only that the file was read, never that the flag beat
    it: a reviewer reading the manifest alone could not tell this build
    apart from one where the file was never consulted.
    """
    file_address = "file-reader@example.org"
    flag_address = "flag-reader@example.org"
    env_path = _write_env_file(tmp_path / "custom.env", file_address)
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
        "--env-file", str(env_path),
        "--enterprise-reader", flag_address,
    ])
    assert result.exit_code == 0, result.output
    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    assert flag_address in manifest
    assert file_address not in manifest
    assert f"Overridden: DBMLSP_ENTERPRISE_READER (using {flag_address})." in manifest
    assert (
        f"DBMLSP_ENTERPRISE_READER = {file_address} (from the file; overridden, "
        f"using {flag_address})"
    ) in result.output


def test_the_declined_sentinel_beats_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """The sentinel is not reachable through a CLI flag -- there is no way to
    type "declined" on the command line -- so, like
    `test_the_declined_sentinel_is_treated_as_nobody_not_as_a_value`, this
    calls `execute_build` directly."""
    from dbml_sharepoint.bundle import emit_bundle as real_emit_bundle
    from dbml_sharepoint.cli import ENTERPRISE_READER_DECLINED, execute_build

    captured: dict[str, object] = {}

    def spy(out: Path, **kwargs: Any) -> str:
        captured.update(kwargs)
        return real_emit_bundle(out, **kwargs)

    monkeypatch.setattr("dbml_sharepoint.cli.emit_bundle", spy)

    file_address = "file-reader@example.org"
    env_path = _write_env_file(tmp_path / "custom.env", file_address)
    out = tmp_path / "build"

    execute_build(
        schema=FIXTURES / "simple.dbml",
        mapping=FIXTURES / "sharepoint-mapping-with-reader.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        out=out,
        enterprise_reader=ENTERPRISE_READER_DECLINED,
        env_file=env_path,
    )

    assert captured["enterprise_reader"] is None
    assert "READER_ADDRESS" not in (out / "deploy.js.txt").read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert (
        f"DBMLSP_ENTERPRISE_READER = {file_address} (from the file; overridden, "
        "using ENTERPRISE_READER_DECLINED)"
    ) in printed


def test_an_env_file_value_that_fails_validation_is_refused_like_a_bad_flag(
    tmp_path: Path,
) -> None:
    """A file value takes the same `validate_enterprise_reader` call a flag
    value does, so a bad UPN is refused with the same message either way."""
    env_path = _write_env_file(tmp_path / "custom.env", "not-an-address")
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
        "--env-file", str(env_path),
    ])
    assert result.exit_code != 0
    assert "one '@'" in result.output
    assert not (out / "deploy.js.txt").exists()


def test_env_file_reader_arms_the_no_group_guard(tmp_path: Path) -> None:
    """The guard in `execute_build` that refuses `--enterprise-reader`
    against a mapping with no `enroll_enterprise_reader` group already
    exists; this feature arms it for a build that used to succeed, because
    no flag was ever given. Deliberately pinned rather than left for a
    consumer to discover.
    """
    env_path = _write_env_file(tmp_path / "custom.env")
    base_args = [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),  # no such group
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
    ]

    out_without = tmp_path / "without-file"
    without_file = runner.invoke(app, [*base_args, "--out", str(out_without)])
    assert without_file.exit_code == 0, without_file.output
    assert (out_without / "deploy.js.txt").is_file()

    out_with = tmp_path / "with-file"
    with_file = runner.invoke(
        app, [*base_args, "--out", str(out_with), "--env-file", str(env_path)],
    )
    assert with_file.exit_code != 0
    assert "enroll_enterprise_reader" in with_file.output
    assert not (out_with / "deploy.js.txt").exists()


def test_an_unwired_env_setting_refuses_instead_of_discarding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_resolve_env_settings` used to `continue` past any `ENV_SETTINGS`
    entry whose `parameter` was not `"enterprise_reader"`, discarding the
    value silently: a file could ask for a second setting, `build --help`
    could advertise the key, and the build would still succeed as though the
    file had said nothing. The registry's whole premise -- "adding a key
    later is one entry" -- is false unless a second entry that is not wired
    in fails loudly the moment a file actually sets it. Registers a fake
    entry rather than a real second parameter, so this test does not need
    one to exist: `test_env_settings_has_exactly_the_registered_fields`
    already pins the registry's current shape and is not a substitute for
    this, because it asserts a count, not that an unwired parameter is
    refused.
    """
    from dbml_sharepoint import cli
    from dbml_sharepoint.model import env_file as env_file_module
    from dbml_sharepoint.model.env_file import EnvSetting

    fake_setting = EnvSetting(
        key="DBMLSP_FAKE_SETTING", parameter="fake_parameter", help="test only.",
    )
    fake_settings = (*env_file_module.ENV_SETTINGS, fake_setting)
    monkeypatch.setattr(env_file_module, "ENV_SETTINGS", fake_settings)
    monkeypatch.setattr(cli, "ENV_SETTINGS", fake_settings)

    env_path = tmp_path / "custom.env"
    env_path.write_text("DBMLSP_FAKE_SETTING=whatever\n", encoding="utf-8", newline="\n")

    with pytest.raises(cli.UnwiredEnvSettingError, match="DBMLSP_FAKE_SETTING"):
        cli.execute_build(
            schema=FIXTURES / "simple.dbml",
            mapping=FIXTURES / "sharepoint-mapping.yaml",
            release=FIXTURES / "release.yaml",
            site_url="https://example.sharepoint.com/sites/test",
            site_role="default",
            out=tmp_path / "build",
            env_file=env_path,
        )


def test_the_manifest_and_index_both_say_so_when_no_env_file_was_read(
    tmp_path: Path,
) -> None:
    """A bundle must never silently claim no file was read: an absent line
    is indistinguishable from a feature that did not run. Pinned at the CLI
    path -- not merely by `generate_manifest`'s and `write_index`'s default
    parameter -- because that default is what every other caller of those
    19-plus call sites relies on, and a signature test alone would not catch
    `execute_build` forgetting to pass the provenance it already built.
    """
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "**Env file:** No dbml-sharepoint.env file was read." in manifest
    assert "**Env file:** No dbml-sharepoint.env file was read." in index


def test_the_manifest_and_index_both_report_the_env_file_that_was_read(
    tmp_path: Path,
) -> None:
    env_path = _write_env_file(tmp_path / "custom.env")
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
        "--env-file", str(env_path),
    ])
    assert result.exit_code == 0, result.output
    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    index = (out / "index.md").read_text(encoding="utf-8")
    for artefact in (manifest, index):
        assert "custom.env" in artefact
        assert "DBMLSP_ENTERPRISE_READER" in artefact


@pytest.mark.skipif(sys.platform != "win32", reason="cross-drive paths are a Windows concept")
def test_a_cross_drive_env_path_falls_back_to_the_path_as_given(tmp_path: Path) -> None:
    """`_relative_env_path` switched from `os.path.relpath` to
    `Path.relative_to(..., walk_up=True)` -- the pathlib equivalent, per the
    plan's "pathlib always". Both raise `ValueError` for a path on a
    different Windows drive than the current directory (`tmp_path`, never
    `Z:`, is what the current directory is under pytest), and the fallback
    branch that catches it was otherwise unexercised by any test.
    """
    from dbml_sharepoint.cli import _relative_env_path

    assert not str(tmp_path).upper().startswith("Z:")
    env_file = Path("Z:/nowhere/dbml-sharepoint.env")
    assert _relative_env_path(env_file) == env_file.as_posix()


def test_build_help_lists_every_env_setting_and_its_help_line() -> None:
    """`EnvSetting.help` is otherwise dead weight: nothing else reads it.

    A key not rendered here is a key an operator can only discover by
    reading source, which defeats the point of a registry. Walking
    `ENV_SETTINGS` rather than pinning today's one entry means a second key
    added later is covered for free, with no second place to edit.

    Rich wraps the panel to the terminal width, so a multi-word help line
    can land across several output lines, each carrying its own panel-border
    character and its own re-wrapped whitespace, the same way
    `test_help_still_renders_as_rich_panels` treats layout as incidental and
    content as what is asserted. `_normalise_rendered_output` strips the
    ANSI escapes, the border, and the whitespace, which is what makes this
    test indifferent to the width rich chose. Pinning the width to avoid the
    wrap would have worked too, but it couples a content assertion to a
    presentation decision that has nothing to do with what is being tested.

    A KEY, though, is one unbroken token, and rich breaks long tokens
    mid-word: a key too long for the options-table name column arrives
    ELLIPSISED (`DBMLSP_DEPLOY_LOG_L…`), which no normalisation can
    recover. The registry key therefore has to FIT the panel, which is the
    constraint this test enforces: today's longest key fits at the same
    width `DBMLSP_ENTERPRISE_READER` always has. Assertions go through
    `_rendered_without_whitespace` so a wrap between words cannot split a
    token; the help PROSE stays on `_normalise_rendered_output`, since
    every break rich can make in prose falls between words.
    """
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0
    collapsed = _normalise_rendered_output(result.stdout)
    tokens = _rendered_without_whitespace(result.stdout)
    for setting in ENV_SETTINGS:
        assert setting.key in tokens, f"{setting.key} missing from build --help"
        help_collapsed = " ".join(setting.help.split())
        assert help_collapsed in collapsed, f"help for {setting.key} missing from build --help"


def test_validation_failure_clears_stale_artifacts(tmp_path: Path) -> None:
    """A failed build must leave only its error manifest. A stale
    script or stale INDEX/checksums beside it could send an operator to the
    wrong release."""
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt",
                 "assess-manifest.md", "index.md", "checksums.txt"):
        (out / name).write_text("stale", encoding="utf-8")
    (out / "reporting").mkdir()
    (out / "reporting" / "stale.pq").write_text("stale", encoding="utf-8")
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        replaced(
            (FIXTURES / "simple.dbml").read_text(encoding="utf-8"),
            "Status    status     [not null, default: 'Open']",
            "Status    choice",
        ),
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
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt",
                 "assess-manifest.md", "index.md", "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_build_never_clears_output_before_it_accepts_its_inputs(tmp_path: Path) -> None:
    """A usage error must not destroy the last good bundle.

    The twin of `test_report_never_clears_output_before_it_reads_the_schema`,
    and it exists because `build` used to disagree with `report` about this.
    Clearing on the way in meant a mistyped `--site-url`, which exits 2 for
    "usage error, before the pipeline runs at all" having read nothing and
    learnt nothing, deleted a bundle the operator may have been part-way
    through pasting.

    The three refusals asserted here are exactly the ones that happen before
    any input file has been believed: a malformed URL, an unreadable schema
    path, and a site role the mapping does not declare.
    """
    out = tmp_path / "build"
    good = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert good.exit_code == 0, good.output

    def snapshot() -> dict[str, bytes]:
        """Every file below `out`, by relative path, with its bytes.

        Names alone are not enough: a regression that rewrote an artifact in
        place -- same name, different content -- would satisfy a name
        comparison while having destroyed exactly what this protects. The
        bundle an operator is part-way through pasting has to be unchanged,
        not merely still present.
        """
        return {
            str(path.relative_to(out)): path.read_bytes()
            for path in sorted(out.rglob("*"))
            if path.is_file()
        }

    bundle = snapshot()
    assert "deploy.js.txt" in bundle

    def rebuild(**overrides: str) -> int:
        args = {
            "--schema": str(FIXTURES / "simple.dbml"),
            "--mapping": str(FIXTURES / "sharepoint-mapping.yaml"),
            "--release": str(FIXTURES / "release.yaml"),
            "--site-url": "https://example.sharepoint.com/sites/test",
            "--site-role": "default",
            "--out": str(out),
            **overrides,
        }
        flat = [part for pair in args.items() for part in pair]
        return runner.invoke(app, ["build", *flat]).exit_code

    assert rebuild(**{"--site-url": "http://example.sharepoint.com/sites/test"}) == 2
    assert snapshot() == bundle, "a bad --site-url changed the bundle"

    assert rebuild(**{"--schema": str(tmp_path / "nope.dbml")}) == 1
    assert snapshot() == bundle, "a bad --schema changed the bundle"

    assert rebuild(**{"--site-role": "nosuchrole"}) == 2
    assert snapshot() == bundle, "a bad --site-role changed the bundle"


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
    assert not (out / "deploy.js.txt").exists()


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
    # An EXISTING bundle, because that is the case with something to lose.
    # Asserting only that `out` was never created tests the empty-directory
    # case, which is the one where the old behaviour was harmless.
    existing = out / "deploy.js.txt"
    out.mkdir()
    existing.write_bytes(b"// the operator is part-way through pasting this")
    before = {
        str(path.relative_to(out)): path.read_bytes()
        for path in sorted(out.rglob("*"))
        if path.is_file()
    }

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
    after = {
        str(path.relative_to(out)): path.read_bytes()
        for path in sorted(out.rglob("*"))
        if path.is_file()
    }
    # This used to assert "clear_generated ran first (creating out), but
    # nothing was generated" -- which was true, and was the bug: the refusal
    # happens before a single input is read, so it has nothing to clear.
    assert after == before


def test_build_rejects_non_https_site_url(tmp_path: Path) -> None:
    """A5: a non-https / malformed --site-url is rejected at parse time (it is
    interpolated into deploy.js.txt and drives the site-match preflight)."""
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
    assert not (out / "deploy.js.txt").exists()


@pytest.mark.parametrize(
    ("given", "used"),
    [
        ("https://example.sharepoint.com/sites/test?web=1",
         "https://example.sharepoint.com/sites/test"),
        ("https://example.sharepoint.com/sites/test#Overview",
         "https://example.sharepoint.com/sites/test"),
        ("https://example.sharepoint.com/sites/test?web=1#Overview",
         "https://example.sharepoint.com/sites/test"),
    ],
)
def test_a_query_or_fragment_never_reaches_the_generated_bundle(
    tmp_path: Path, given: str, used: str,
) -> None:
    """SharePoint's own Copy link puts `?web=1` on the clipboard.

    Nothing downstream stripped it, and the site URL is baked into the
    reporting pack -- the Power Query `SiteRoot` and the SQLCMD `SiteUrl` --
    so the generated endpoints came out as
    `https://tenant/sites/X?web=1/_api/web`.

    Asserted against the EMITTED artefacts, not the validator, because the
    validator returning something clean proves nothing about what the build
    wrote. The operator is told, because a silent rewrite of what they typed
    is indistinguishable from one that went wrong.
    """
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", given,
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output

    emitted = [p for p in out.rglob("*") if p.is_file()]
    assert emitted, "the build produced nothing to check"
    offenders = [
        p.relative_to(out).as_posix() for p in emitted
        if "?web=1" in p.read_text(encoding="utf-8", errors="replace")
        or "#Overview" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not offenders, offenders
    # And the cleaned form really is what was baked in, so this cannot pass
    # by the URL being absent altogether.
    assert any(
        used in p.read_text(encoding="utf-8", errors="replace") for p in emitted
    )
    assert "Ignoring the query or fragment" in result.output


def test_a_clean_site_url_is_passed_through_and_not_announced(
    tmp_path: Path,
) -> None:
    """The complement: no rewrite, and nothing said about one."""
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
    assert "Ignoring the query or fragment" not in result.output


def test_build_reports_validation_errors_without_crashing(tmp_path: Path) -> None:
    """Regression: a schema with an unsupported column type must exit via the
    validation-error path (writing a findings manifest, exit 1), not crash
    inside ``build_schema_json`` when ``map_column`` raises ``ValueError``
    before the error-reporting branch runs.
    """
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        replaced(
            (FIXTURES / "simple.dbml").read_text(encoding="utf-8"),
            "Status    status     [not null, default: 'Open']",
            "Status    choice",
        ),
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
    assert not (out / "deploy.js.txt").exists()


def test_build_dry_run_writes_manifest_but_no_js(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt", "index.md",
                 "checksums.txt"):
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
    for name in ("deploy.js.txt", "rollback.js.txt", "assess.js.txt", "verify.js.txt", "index.md",
                 "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()


# --- Config errors are messages, not crashes --------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the real CLI in a subprocess.

    CliRunner CATCHES the exception and stores it on the result, so a
    traceback never reaches its stdout, so a test written against it passes
    whether or not the operator sees 20 lines of loader internals. Only a
    real process shows what the person running the tool actually gets.
    """
    return subprocess.run(  # noqa: S603 - args are literals from this module
        [sys.executable, "-m", "dbml_sharepoint.cli", *args],
        capture_output=True, text=True, check=False,
    )


def _bad_mapping(tmp_path: Path, section: str) -> Path:
    """The standard Project entity plus a deliberately broken section.

    `with_tail`, not `blocks`: callers pass a top-level section here today, but
    the parameter is a raw fragment and dedenting it would silently reparent
    anything indented. Keeping the caller's text verbatim means the helper does
    what its name says regardless of what is passed.
    """
    return write_mapping(tmp_path, with_tail(entities("Project"), section))


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
    schema = write_dbml(
        tmp_path,
        """
            Table Broken {
              invalid !!!
            }
        """,
        preamble=False,
        name="bad.dbml",
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
    assert result.returncode == 1
    assert "Traceback" not in output, output
    assert "schema" in output and "bad.dbml" in output


def test_unknown_dbml_index_column_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    schema = write_dbml(
        tmp_path,
        """
            Table Risk {
              Status nvarchar
              indexes { Staus }
            }
        """,
        preamble=False,
        name="bad-index.dbml",
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


@pytest.mark.parametrize("command", ["build", "validate"])
def test_an_unknown_extension_is_a_message_not_a_traceback(
    command: str, tmp_path: Path,
) -> None:
    """`resolve_extension` was called one line after `_load_config` returned,
    outside its boundary, so an unknown name reached the operator as a rich
    traceback while every other bad input printed one sentence. Both commands
    taking `--extension` are covered, and the exit code alone cannot see the
    defect because the traceback exited 1 as well.
    """
    args = [
        command,
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--extension", "nope",
    ]
    if command == "build":
        args += [
            "--release", str(FIXTURES / "release.yaml"),
            "--site-url", "https://example.sharepoint.com/sites/test",
            "--out", str(tmp_path / "build"),
        ]
    result = _cli(*args)
    output = result.stdout + result.stderr
    # 1, not merely non-zero: the documented table in cli.md gives 1 to
    # "the build refused" and reserves 2 for the usage errors typer raises
    # before the pipeline runs.
    assert result.returncode == 1, output
    assert "Traceback" not in output, output
    assert "ValueError" not in output, output
    # The sentence that already named the unknown extension survives.
    assert "Unknown extension 'nope'" in output, output
    assert "installed" in output, output
    # One line for the operator, not a stack.
    assert len([ln for ln in output.splitlines() if ln.strip()]) <= 2, output


def test_an_unknown_extension_in_the_mapping_names_the_file(tmp_path: Path) -> None:
    """A misspelled `extension:` key reaches the same call as the flag, and
    with no flag to blame the message has to point at the file to edit."""
    mapping = write_mapping(tmp_path, with_tail(entities("Project"), "extension: nope\n"))
    result = _cli(
        "validate",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(mapping),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "Traceback" not in output, output
    assert "ValueError" not in output, output
    assert mapping.name in output, output
    assert "Unknown extension 'nope'" in output, output


def test_report_renders_generator_refusals_as_messages(tmp_path: Path) -> None:
    """`report` does not validate, so the generators meet a bad schema first.

    They refuse by raising, and unhandled that printed a traceback for a
    hand-edited typo. Both refusals reachable from a parseable schema are
    covered: an unmapped column type (typemap) and a composite DBML index
    (the deploy projection).
    """
    mapping = write_mapping(tmp_path, entities("Risk"))
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
    mapping = write_mapping(tmp_path, entities("Risk", "Legacy"))
    schema = write_dbml(tmp_path, blocks(table("Risk", ID_PK), table("Legacy", ID_PK)))
    out = tmp_path / "reports"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    assert (out / "powerquery" / "APP_Legacy.pq").exists()
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")

    schema = write_dbml(tmp_path, table("Risk", ID_PK))
    second = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )

    assert second.returncode == 0, second.stderr
    assert (out / "powerquery" / "APP_Risk.pq").exists()
    assert not (out / "powerquery" / "APP_Legacy.pq").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_report_refuses_a_member_the_export_cannot_split_back(
    tmp_path: Path,
) -> None:
    """`report` does not validate, so the generator guard is its only one.

    The rule itself is a finding now
    (`MULTI_VALUE_MEMBER_CONTAINS_THE_EXPORT_SEPARATOR`), which `build` and
    `validate` both reach. `report` reaches neither -- it renders straight
    from the schema with no site URL and never calls `validate_all`.

    So when the generator guard was deleted on the reasoning that the
    validator had replaced it, `report` began exiting 0 while emitting a
    Power Query cell joined on "; " from a member that itself contains "; ",
    with the data dictionary beside it telling the reader to split on that
    string. Well-formed, green, and lossy -- and reproduced exactly that way
    before this test existed.

    Pinned at the CLI rather than on the generator because the generator
    tests were green throughout: what regressed was which entry points reach
    the guard, and only a command-level test can see that.
    """
    schema = write_dbml(tmp_path, blocks(
        'enum audit_event {\n  "View"\n  "Permission change; revoked"\n}\n',
        table("Platform", ID_PK, TITLE, "Events audit_event[]"),
    ))
    mapping = write_mapping(tmp_path, entities("Platform"))
    out = tmp_path / "reports"

    result = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )

    assert result.returncode == 1, result.stdout
    assert "Permission change; revoked" in result.stderr
    assert not (out / "powerquery").exists(), (
        "report wrote an export it had already been told it cannot describe"
    )


def test_report_success_message_names_only_files_it_wrote(tmp_path: Path) -> None:
    """The success line is an instruction, and it named a file that was
    never written.

    `report` writes `guide.md`; the message said `reporting.md`, as did the
    bundle INDEX row and -- worse -- a comment inside the emitted T-SQL,
    which is read by a warehouse engineer who does not have this repository
    open. Six references survived a rename that changed the byte on disk.

    `bundle.py` already prescribes the cure for exactly this ("Named
    constants rather than literals at each write site ... those four
    drifting apart is how a manifest comes to tell somebody to paste a file
    the build did not write"); the reporting artifacts had never adopted it.

    Parsed out of the message rather than asserted against a fixed list, so
    this keeps holding when the set of artifacts changes -- a list would
    just be a seventh place to update.
    """
    mapping = write_mapping(tmp_path, entities("Risk"))
    schema = write_dbml(tmp_path, table("Risk", ID_PK))
    out = tmp_path / "reports"

    result = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )
    assert result.returncode == 0, result.stderr

    named = re.findall(r"[\w./-]+\.(?:md|sql)", result.stdout)
    assert named, f"the message names no artifact at all: {result.stdout!r}"
    missing = [name for name in named if not (out / name).is_file()]
    assert not missing, (
        f"the success message names {missing}, which `report` did not "
        f"write. It said: {result.stdout.strip()!r}"
    )


def test_report_refusal_clears_previous_generated_outputs(tmp_path: Path) -> None:
    mapping = write_mapping(tmp_path, entities("Risk"))
    schema = write_dbml(tmp_path, table("Risk", ID_PK, "Status nvarchar"))
    out = tmp_path / "reports"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")

    schema = write_dbml(tmp_path, table("Risk", ID_PK, "Status blob"))
    failed = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(out),
    )

    assert failed.returncode == 1
    assert not (out / "powerquery").exists()
    assert not (out / "sql").exists()
    assert not (out / "guide.md").exists()
    assert not (out / "data-dictionary.md").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_report_never_clears_output_before_it_reads_the_schema(tmp_path: Path) -> None:
    """An input error must not destroy the last good report set.

    `--out` is routinely aimed at a directory holding the operator's own
    work, and `sql/`/`powerquery/` are generic enough names to collide with
    it. Clearing on the way in meant a mistyped --schema path (or an
    unknown --site-role, which exits 2 for "usage error, before the
    pipeline runs") deleted both trees whole before reading anything.
    """
    mapping = write_mapping(tmp_path, entities("Risk"))
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
    mapping = write_mapping(tmp_path, entities("Risk"))
    schema = write_dbml(tmp_path, table("Risk", ID_PK, "Status nvarchar"))
    out = tmp_path / "shared"
    first = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping), "--out", str(out),
    )
    assert first.returncode == 0, first.stderr
    (out / "sql" / "001_migration.sql").write_text("-- hand written", encoding="utf-8")
    (out / "powerquery" / "notes.md").write_text("mine", encoding="utf-8")

    # A refusal clears what this command wrote, and stops there.
    schema = write_dbml(tmp_path, table("Risk", ID_PK, "Status blob"))
    refused = _cli(
        "report", "--schema", str(schema), "--mapping", str(mapping), "--out", str(out),
    )

    assert refused.returncode == 1
    assert not (out / "sql" / "views.sql").exists()
    assert not (out / "data-dictionary.md").exists()
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


def _fixture_build(out: Path, schema: Path, mapping: Path | None = None) -> Result:
    return runner.invoke(app, [
        "build",
        "--schema", str(schema),
        "--mapping", str(mapping or FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])


def _minimal_pack(tmp_path: Path, columns: str = "") -> tuple[Path, Path]:
    """A schema and mapping raising exactly the warnings the caller declares.

    Deliberately not `FIXTURES/simple.dbml`: that pack already raises an
    `unindexed_filter_columns` warning, so a test asserting "one warning" or
    "no warnings" against it is really asserting something about a fixture
    it does not control. Building the pack here makes the warning count a
    property of the test.
    """
    schema = write_dbml(
        tmp_path,
        blocks(f"""
            Table Risk {{
              {ID_PK}
              Title nvarchar [not null]
            {columns}
            }}
        """),
    )
    return schema, write_mapping(tmp_path, entities("Risk"))


def test_a_successful_build_reports_the_warnings_it_raised(tmp_path: Path) -> None:
    """A build that raises warnings must not print only its success line.

    The manifest is not optional reading and the docs say so, but a build
    that prints one cheerful line trains the operator that success means
    there is nothing to look at. The one time it matters, the habit is
    already formed -- and `unique without not_null` is exactly the kind of
    thing discovered in production, by a duplicate.
    """
    schema, mapping = _minimal_pack(tmp_path, "  Code nvarchar [unique]")
    out = tmp_path / "build"
    result = _fixture_build(out, schema, mapping)

    assert result.exit_code == 0, result.output
    assert "1 validation warning" in result.output
    assert "unique_without_not_null" in result.output


def test_a_clean_build_says_nothing_about_warnings(tmp_path: Path) -> None:
    """Silence when clean is deliberate, not accidental.

    A "0 warnings" line on every build is noise that makes the non-zero
    case LESS visible, which is the opposite of the point.
    """
    schema, mapping = _minimal_pack(tmp_path)
    out = tmp_path / "build"
    result = _fixture_build(out, schema, mapping)

    assert result.exit_code == 0, result.output
    assert "warning" not in result.output.lower()


def test_a_refused_build_names_the_finding_code(tmp_path: Path) -> None:
    """The message is prose and is free to be reworded in any commit; the
    code is the identity, and the published catalogue is keyed by it. With
    only the message on screen there was nothing to carry the operator from
    the terminal to `reference/findings.md`."""
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        replaced(
            (FIXTURES / "simple.dbml").read_text(encoding="utf-8"),
            "Status    status     [not null, default: 'Open']",
            "Status    persson",
        ),
        encoding="utf-8",
    )
    result = _fixture_build(tmp_path / "build", bad)

    assert result.exit_code == 1
    assert "unknown_column_type" in result.output


def test_the_manifest_names_the_finding_code(tmp_path: Path) -> None:
    """Same argument, same reason, on the artifact the docs send people to."""
    schema, mapping = _minimal_pack(tmp_path, "  Code nvarchar [unique]")
    out = tmp_path / "build"
    assert _fixture_build(out, schema, mapping).exit_code == 0

    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    assert "unique_without_not_null" in manifest


def test_a_refused_build_still_reports_its_warnings(tmp_path: Path) -> None:
    """Errors and warnings are found in the same pass, so both are known.

    Printing only the errors means the operator fixes those, rebuilds, and
    meets a second list they could have seen the first time. On every other
    path suppressing a warning costs nothing; on this one it costs a round
    trip.
    """
    schema, mapping = _minimal_pack(
        tmp_path,
        "  Code nvarchar [unique]\n  Cost decimal",
    )
    result = _fixture_build(tmp_path / "build", schema, mapping)

    assert result.exit_code == 1
    assert "unknown_column_type" in result.output
    assert "unique_without_not_null" in result.output


def _project(tmp_path: Path) -> Path:
    """A directory laid out the way `dbml-sharepoint new` leaves one.

    A real shipped family, copied whole, rather than three fixture files
    posted into the standard paths. A template is not just its three
    inputs -- the mapping references sibling files like an enum source, and
    a hand-built stand-in that omits them tests a project shape nobody ever
    has. Copying one is also the closest thing to what the wizard does,
    which is the situation this default exists for.
    """
    root = tmp_path / "proj"
    shutil.copytree(SOLUTION_TEMPLATES / "risk-register", root)
    return root


def test_build_defaults_its_inputs_to_the_project_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inside a scaffolded project the three paths are already known.

    `catalogue` declares them and `test_template_standard` enforces them
    across every family, so making the operator retype them on every
    rebuild -- the most repeated action in the tool -- was asking for
    something we already had.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
    ])

    assert result.exit_code == 0, result.output
    assert (Path("build") / "deploy.js.txt").is_file()


def test_sidecar_lists_are_ensured_by_default_and_the_external_log_is_probed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain build keeps a run log and a change log, and names the
    external deployment log to probe.

    The run log is the whole point of the stamps: without a list the
    transcript is the only record, and a console that closes takes it with
    it. The external log is the opposite bargain -- probed, never created,
    because its absence means the site does not run one. The build bakes
    the NAME in either way, so the operator can see what will be looked
    for before pasting.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
    ])
    assert result.exit_code == 0, result.output

    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"dbml Local Log"' in js
    assert '"dbml_Logs"' in js
    assert '"dbml-deployment-log"' in js
    assert "finishRunLog" in js


def test_no_sidecars_emits_no_logging_phase_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--no-sidecars` is a full opt-out, not a quiet mode.

    No sidecar constants may reach the script, because a constant that is
    declared but never ensured is exactly how a script comes to stamp into
    a list it never created. The logging phase renders empty; the buffered
    change events from renames are dropped on the floor, which is what the
    operator asked for.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--no-sidecars",
    ])
    assert result.exit_code == 0, result.output

    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert "dbml Local Log" not in js
    assert "dbml_Logs" not in js
    assert "dbml-deployment-log" not in js

    # The manifest is the pre-paste contract: it must not advertise lists
    # the bundle will not create.
    manifest = (Path("build") / "deploy-manifest.md").read_text(encoding="utf-8")
    assert "Run and change logs" not in manifest
    assert "dbml Local Log" not in manifest


def test_an_empty_deployment_log_list_disables_the_external_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--deployment-log-list ''` turns the external stamps off while
    keeping the built-in sidecars.

    The empty string must survive as a MEANING, not die in validation:
    it is how an operator says "this site does not run a shared deployment
    log" without losing the run log's start and stop stamps. A padded
    variant is not the disable and is refused, so nothing invisible can
    turn the feature off.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-list", "",
    ])
    assert result.exit_code == 0, result.output

    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert 'EXTERNAL_LOG_TITLE = ""' in js
    assert '"dbml Local Log"' in js  # the built-in sidecars stay

    padded = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-list", " ",
    ])
    assert padded.exit_code == 2
    # Normalise, then assert: rich wraps the refusal inside the panel and
    # the break lands between words, which is exactly what the collapsing
    # helper exists to remove.
    assert "padded, or whitespace" in _normalise_rendered_output(padded.output)


def test_an_env_file_can_supply_both_log_lists_and_a_flag_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two list names resolve under the same precedence as the reader.

    File supplies, flag overrides, and the build transcript says which won
    -- the same provenance line the reader key has always had, because a
    setting whose source cannot be told from a setting whose source is
    guessed is a setting nobody can audit.
    """
    monkeypatch.chdir(_project(tmp_path))
    (Path("dbml-sharepoint.env").write_text(
        "DBMLSP_DEPLOY_LOG_LIST=Programme Board Log\n"
        "DBMLSP_CHANGE_LOG_LIST=Programme_Changes\n",
        encoding="utf-8", newline="\n",
    ))

    from_file = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
    ])
    assert from_file.exit_code == 0, from_file.output
    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"Programme Board Log"' in js
    assert '"Programme_Changes"' in js
    assert "DBMLSP_DEPLOY_LOG_LIST = Programme Board Log (from the file)" in from_file.output
    assert "DBMLSP_CHANGE_LOG_LIST = Programme_Changes (from the file)" in from_file.output

    by_flag = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-list", "dbml-deployment-log",
    ])
    assert by_flag.exit_code == 0, by_flag.output
    assert (
        "DBMLSP_DEPLOY_LOG_LIST = Programme Board Log"
        " (from the file; overridden, using dbml-deployment-log)"
        in by_flag.output
    )
    js2 = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"dbml-deployment-log"' in js2  # the flag's value is what ships


#: Every command that hands its whole option set to a shared executor, and
#: the executor it hands them to. Both pairs, not just the one that broke:
#: the defect is a property of the SHAPE, so a third pair added later is
#: covered the day it is written.
_DELEGATING_COMMANDS = ((build, execute_build), (extract, execute_extraction))


def _forwarded_arguments(
    command: Callable[..., Any], executor: Callable[..., Any],
) -> dict[str, set[str]]:
    """Read `command`'s call to `executor` out of `command`'s own source.

    Source, not a call recorded through a monkeypatch: a parameter that is
    never forwarded still has a DEFAULT on the other side, so a recorded
    call carries the key regardless and the defect is invisible. What
    distinguishes a forwarded parameter from a dropped one is whether the
    call site mentions it at all, and only the source says that.

    Returns one entry per argument, holding the names its value expression
    reads, so `schema=_project_input(schema, ...)` counts as forwarding
    `schema` while a keyword wired to the wrong variable does not. A
    POSITIONAL argument is named from the executor's own signature, which
    is how `extract` forwards its `source`.
    """
    def reads(value: ast.expr) -> set[str]:
        return {inner.id for inner in ast.walk(value) if isinstance(inner, ast.Name)}

    tree = ast.parse(textwrap.dedent(inspect.getsource(command)))
    positional = list(inspect.signature(executor).parameters)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == executor.__name__
        ):
            forwarded = {
                name: reads(value)
                for name, value in zip(positional, node.args, strict=False)
            }
            forwarded.update({
                keyword.arg: reads(keyword.value)
                for keyword in node.keywords
                if keyword.arg is not None
            })
            return forwarded
    raise AssertionError(
        f"{command.__name__}() no longer calls {executor.__name__}(...) by "
        f"name; this guard reads that call out of the source and cannot find it.",
    )


@pytest.mark.parametrize(
    ("command", "executor", "option"),
    [
        pytest.param(command, executor, option,
                     id=f"{command.__name__}-{option}")
        for command, executor in _DELEGATING_COMMANDS
        for option in sorted(inspect.signature(command).parameters)
    ],
)
def test_every_command_option_reaches_its_executor(
    command: Callable[..., Any], executor: Callable[..., Any], option: str,
) -> None:
    """Every option a delegating command accepts is forwarded to its executor.

    `--deployment-log-site` was declared, resolved, validated, echoed in
    the provenance line, and then not passed: the flag and its documented
    `''` disable were both silent no-ops, and a build naming a completely
    different central site still emitted the default one. Nothing failed,
    because `execute_build` has a default for that parameter and used it.

    Parametrised per option so a failure names the dropped one rather than
    reporting that a set comparison did not match. Structural on purpose:
    it holds for the NEXT option added as well, which an end-to-end
    assertion about one flag cannot do.
    """
    forwarded = _forwarded_arguments(command, executor)
    assert option in forwarded, (
        f"`{command.__name__}` accepts --{option.replace('_', '-')} but never "
        f"passes it to {executor.__name__}(), so the option is a no-op however "
        f"carefully it is validated. Add `{option}={option},` to the call."
    )
    assert option in forwarded[option], (
        f"`{command.__name__}` passes {option}= to {executor.__name__}(), but "
        f"the value it passes never reads the `{option}` parameter, so the "
        f"option is still a no-op."
    )


@pytest.mark.parametrize(
    ("command", "executor"), _DELEGATING_COMMANDS,
    ids=[command.__name__ for command, _ in _DELEGATING_COMMANDS],
)
def test_no_command_option_is_forwarded_that_its_executor_cannot_accept(
    command: Callable[..., Any], executor: Callable[..., Any],
) -> None:
    """The other half: nothing is forwarded under a name that is not a
    parameter.

    A keyword the executor does not declare is a TypeError at runtime
    rather than a silent no-op, so this is the cheaper failure of the two.
    It is here because the guard above only reads one direction, and a
    rename applied to one side is exactly the edit that breaks the other.
    """
    accepted = set(inspect.signature(executor).parameters)
    forwarded = set(_forwarded_arguments(command, executor))
    assert forwarded <= accepted, (
        f"{command.__name__}() forwards {sorted(forwarded - accepted)} to "
        f"{executor.__name__}(), which does not accept it."
    )


def test_the_deployment_log_site_flag_reaches_the_emitted_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--deployment-log-site` names the site the script actually stamps.

    The end-to-end half of the guard above. A build naming another org's
    logging site used to emit the DEFAULT site name, so the operator read
    a correct-looking flag in their build command and pasted a script that
    wrote somebody else's log. Asserted on the emitted constant, because
    that is the only thing the browser reads.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-site", "clientB-logging",
    ])
    assert result.exit_code == 0, result.output

    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert 'EXTERNAL_LOG_SITE = "clientB-logging"' in js
    # The CONSTANT, not the whole file: the default site name is also named
    # in a live-finding comment about cross-web digests, which no build
    # substitutes and no browser reads.
    assert 'EXTERNAL_LOG_SITE = "firmfooting-logging"' not in js


def test_an_empty_deployment_log_site_disables_the_external_stamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--deployment-log-site ''` is the disable, and disables both halves.

    The site and the list are one feature: a script that knows a list name
    and no site has nowhere to write it. Both constants have to come out
    empty, or the emitted probe reads a site the operator turned off.
    """
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-site", "",
    ])
    assert result.exit_code == 0, result.output

    js = (Path("build") / "deploy.js.txt").read_text(encoding="utf-8")
    assert 'EXTERNAL_LOG_SITE = ""' in js
    assert 'EXTERNAL_LOG_TITLE = ""' in js
    assert '"dbml Local Log"' in js  # the built-in sidecars stay

    padded = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-site", " ",
    ])
    assert padded.exit_code == 2
    assert "padded, or whitespace" in _normalise_rendered_output(padded.output)

    spaced = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
        "--deployment-log-site", "client B logging",
    ])
    assert spaced.exit_code == 2
    assert "contains no spaces" in _normalise_rendered_output(spaced.output)


def test_an_explicit_path_beats_the_project_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A default that cannot be overridden is a trap, not a convenience."""
    monkeypatch.chdir(_project(tmp_path))
    missing = tmp_path / "nowhere.dbml"

    result = runner.invoke(app, [
        "build", "--schema", str(missing),
        "--site-url", "https://example.sharepoint.com/sites/test",
    ])

    # A path that does not exist is the unambiguous probe: the project
    # default IS present and would have built cleanly, so failing on
    # `nowhere.dbml` can only mean the explicit value won. Asserting on a
    # successful build with a different schema would prove the same thing
    # far more weakly -- the two could agree by accident.
    assert result.exit_code == 1
    assert "nowhere.dbml" in result.output


def test_a_missing_input_names_the_standard_path_it_looked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside a project the error has to teach the layout.

    "Missing option '--schema'" is true and useless: it does not say that
    running from a project directory would have supplied it. The message
    IS the feature for anyone who is not in one.
    """
    monkeypatch.chdir(tmp_path)
    # Pin the rendering this assertion reads. rich lays the refusal out in a
    # panel whose width and colour it decides from the environment, and the
    # first version of this test asserted on that panel raw: green on a
    # developer machine, red on both CI runners, for reasons that are nothing
    # to do with the behaviour under test. Fixing the width and disabling
    # colour makes the message the only variable.
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")

    result = runner.invoke(app, [
        "build", "--site-url", "https://example.sharepoint.com/sites/test",
    ])

    assert result.exit_code == 2
    # Collapsed, because even at 200 columns a panel wraps somewhere and a
    # wrap inside the path would make this a test of the terminal.
    rendered = " ".join(_ANSI.sub("", result.output).split())
    assert "--schema" in rendered
    assert str(SCHEMA_RELPATH) in rendered


def test_report_defaults_its_inputs_to_the_project_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`report` is the other command driven from a project directory."""
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0, result.output
    assert (Path("reports") / "guide.md").is_file()


def test_report_does_not_borrow_a_release_from_the_working_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit inputs must not pick up the current project's provenance.

    `report --schema ../other/... --mapping ../other/...` run from inside a
    project would otherwise stamp THIS project's release tag and schema
    version onto a data dictionary describing somebody else's schema.
    Nothing links a release.yaml to the schema it describes, so the result
    is not missing provenance but wrong provenance -- and the output looks
    equally confident either way.
    """
    project = _project(tmp_path)
    release_tag = (project / RELEASE_RELPATH).read_text(encoding="utf-8")
    assert "release:" in release_tag
    monkeypatch.chdir(project)

    out = tmp_path / "reports"
    result = runner.invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--out", str(out),
    ])

    assert result.exit_code == 0, result.output
    dictionary = (out / "data-dictionary.md").read_text(encoding="utf-8")
    # With the project's release borrowed, the tag from its release.yaml is
    # stamped into this dictionary -- which describes a different schema.
    tag = next(
        line.split(":", 1)[1].strip().strip('"')
        for line in release_tag.splitlines()
        if line.startswith("release:")
    )
    assert tag not in dictionary, f"borrowed the working project's release {tag!r}"


def test_build_does_not_borrow_a_release_from_the_working_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard `report` already has, on the command that ships a bundle.

    `report` learned this in the commit before last: infer the project's
    release ONLY when the schema and mapping came from the project too.
    `build` kept defaulting unconditionally, so
    `build --schema ../other/... --mapping ../other/...` run from a project
    directory stamped THIS project's release tag into a deploy bundle
    describing somebody else's schema.

    Measured before the fix: a bundle built from `test/fixtures/simple.dbml`
    (release `0.1.0-test`) inside a copy of `risk-register` reported
    "Release tag: 1.0.0" -- the risk-register value. Nothing links a
    release.yaml to the schema it describes, so that is not missing
    provenance but wrong provenance, on the artifact that actually gets
    pasted into a tenant.

    Refuses rather than silently skipping the stamp: unlike `report`, a
    release is REQUIRED by `build`, so there is no unstamped mode to fall
    back to. Naming `--release` tells the operator exactly what to supply.
    """
    monkeypatch.chdir(_project(tmp_path))
    # Same pinning as `test_a_missing_input_names_the_standard_path_it_looked_for`
    # above, for the same reason and then one more. rich decides width and
    # colour from the environment, and with colour ON its option highlighter
    # emits the two dashes as SEPARATE styled spans -- `--release` renders as
    # `ESC[1;36m-ESC[0mESC[1;36m-release`, so the literal substring is not in
    # the output at all. CI sets GITHUB_ACTIONS, rich colours, this assertion
    # went red on both runners while staying green on an uncoloured developer
    # terminal. Reproduce the CI rendering with `GITHUB_ACTIONS=true`.
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")

    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    ])

    assert result.exit_code == 2, result.output
    rendered = " ".join(_ANSI.sub("", result.output).split())
    assert "--release" in rendered


def test_report_stamps_the_project_release_it_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery has to be observed by its EFFECT, not by exit 0.

    `test_report_defaults_its_inputs_to_the_project_layout` above proves the
    command succeeds inside a project, which it would do just as happily if
    the release were ignored -- an unstamped dictionary is a supported
    result, so nothing about a zero exit distinguishes "found and stamped it"
    from "never looked". The negative case
    (`..._does_not_borrow_a_release_...`) asserts the tag is ABSENT, so
    without this its assertion would also hold if the tag could never appear
    at all. This is the positive half that gives the pair meaning.
    """
    project = _project(tmp_path)
    release_text = (project / RELEASE_RELPATH).read_text(encoding="utf-8")
    tag = next(
        line.split(":", 1)[1].strip().strip('"')
        for line in release_text.splitlines()
        if line.startswith("release:")
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0, result.output
    dictionary = (Path("reports") / "data-dictionary.md").read_text(encoding="utf-8")
    assert tag in dictionary, f"discovered release {tag!r} was not stamped"


def test_report_succeeds_in_a_project_with_no_release_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing release.yaml is a supported mode, not a refusal.

    This is what separates `--release` from the other two inputs, and the
    reason it does not go through `_project_input`. Deleting the file from an
    otherwise complete project is the only way to prove the difference is
    real rather than incidental to every fixture happening to have one.
    """
    project = _project(tmp_path)
    (project / RELEASE_RELPATH).unlink()
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0, result.output
    assert (Path("reports") / "data-dictionary.md").is_file()


def test_validate_accepts_a_valid_schema_without_a_site_url(tmp_path: Path) -> None:
    """The whole point: `validate_all` takes a schema, a mapping bundle and
    an extension. Not a site URL, not a release. Requiring either to answer
    "is this correct?" made the tightest loop in the tool -- edit, check,
    edit -- cost an invented tenant URL."""
    result = runner.invoke(app, [
        "validate",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
    ])

    assert result.exit_code == 0, result.output


def test_validate_refuses_an_invalid_schema(tmp_path: Path) -> None:
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        replaced(
            (FIXTURES / "simple.dbml").read_text(encoding="utf-8"),
            "Status    status     [not null, default: 'Open']",
            "Status    persson",
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, [
        "validate",
        "--schema", str(bad),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
    ])

    assert result.exit_code == 1
    assert "unknown_column_type" in result.output


def test_validate_writes_nothing(tmp_path: Path) -> None:
    """It answers a question; it does not produce an artifact.

    `build --dry-run` deliberately still writes deploy-manifest.md, which is
    a run sheet for a named target. This command has no target and must not
    leave anything behind that looks like one.
    """
    monkeypatch_cwd = tmp_path / "empty"
    monkeypatch_cwd.mkdir()

    result = runner.invoke(app, [
        "validate",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--out", str(monkeypatch_cwd),
    ])

    # There is no --out to give: the flag must not exist at all.
    assert result.exit_code == 2
    assert list(monkeypatch_cwd.iterdir()) == []


def test_validate_needs_no_flags_inside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With #124's path defaults this is the whole command."""
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0, result.output
    assert not (Path("build")).exists()


def test_validate_rejects_an_unknown_site_role(tmp_path: Path) -> None:
    """Same data-driven vocabulary `build` and `report` use. A misspelled
    role would otherwise validate an empty entity set and report success."""
    result = runner.invoke(app, [
        "validate",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-role", "nosuchrole",
    ])

    assert result.exit_code == 2
    assert "nosuchrole" in result.output


def test_validate_checks_every_role_not_just_the_selected_one(tmp_path: Path) -> None:
    """`--site-role` does NOT narrow what gets validated, and must not.

    Raised by review on #135, which read the option as selecting which
    entities to check -- the CLI reference said exactly that -- and called
    the mismatch a bug. The behaviour is right and the documentation was
    wrong: `validate_all(schema, bundle, extension)` takes no role, and
    `build` calls it the same way, so validation has always been
    project-wide.

    Narrowing it would be the actual bug. A mapping is one document; an
    error under `admin` is an error whether or not this run happens to be
    deploying `admin`, and hiding it until somebody runs with that role
    means the mapping validates clean right up until the deploy that
    breaks. The flag's job here is to reject a role the mapping does not
    declare -- catching the typo before `build --site-role adnim` does.

    Pinned so that a future "scope validation to the role" change has to
    argue with a test rather than look like a tidy-up.
    """
    mapping = write_mapping(tmp_path, blocks(
        entities(entity("Project"), entity("AdminOnly", site_role="admin")),
        """
        views:
          AdminOnly:
            - title: Broken
              fields: [NoSuchColumn]
        """,
    ))
    schema = write_dbml(tmp_path, blocks(
        table("Project", ID_PK, TITLE),
        table("AdminOnly", ID_PK, TITLE),
    ))

    result = runner.invoke(app, [
        "validate", "--schema", str(schema), "--mapping", str(mapping),
        "--site-role", "default",
    ])

    # The finding belongs to an entity this role would never deploy.
    assert result.exit_code == 1, result.output
    assert "AdminOnly" in result.output, result.output


def test_a_wrong_section_shape_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    """The loader guard has to survive the trip to the terminal.

    `test_mapping_loader` proves the ValueError is raised and names the
    section; this proves the CLI renders it as one sentence. The two are
    genuinely separate: `cli._CONFIG_ERRORS` lists the exception types it
    turns into a message, and a guard that raised the wrong type would pass
    every loader test and still print a stack here.

    Deliberately not widening `_CONFIG_ERRORS` to AttributeError/TypeError,
    which is the other way to make this pass -- that would dress every
    genuine loader bug up as a bad mapping file. See #141.
    """
    mapping = _bad_mapping(tmp_path, "views:\n  - Project\n")
    result = _cli(
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(mapping),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(tmp_path / "build"),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in output, output
    assert "mapping_loader.py" not in output, output
    assert "AttributeError" not in output, output
    # Names the section, so the operator knows which line to look at.
    assert "views" in output
    assert len([ln for ln in output.splitlines() if ln.strip()]) <= 2, output


def test_a_directory_at_the_default_env_path_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`is_file()` is false for a directory, which used to make one named
    `dbml-sharepoint.env` indistinguishable from no file at all.

    The build then succeeded while printing "No dbml-sharepoint.env file was
    read.", and `read_env_file` never got the chance to raise the
    `EnvFileReadError` it defines for exactly this. Fail closed instead.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ENV_FILENAME).mkdir()
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert "is not a file" in _normalise_rendered_output(result.output)
