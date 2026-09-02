# test/test_bundle.py
"""Bundle-level packaging: artifact clearing, LF-stable hashing, INDEX/checksums."""

import hashlib
from pathlib import Path

from _paths import FIXTURES, PACKAGE

from dbml_sharepoint.bundle import (
    ASSESS_SCRIPT,
    DEMO_SCRIPT,
    DEPLOY_SCRIPT,
    GENERATED_FILES,
    ROLLBACK_SCRIPT,
    clear_generated,
    emit_bundle,
    sha256_lf,
    write_artifact,
    write_checksums,
    write_index,
)


def test_generated_files_is_the_full_bundle() -> None:
    # The demo script is in the clear set even though it is emitted only
    # with --seed: a rebuild WITHOUT --seed must remove a stale one.
    #
    # Spelled out rather than built from the constants: this is the test
    # that would catch a rename, and asserting `DEPLOY_SCRIPT in
    # GENERATED_FILES` would pass no matter what either one said.
    assert set(GENERATED_FILES) == {
        "deploy.js.txt", "rollback.js.txt", "assess.js.txt",
        "demo-data.js.txt", "verify.js.txt",
        "deploy-manifest.md", "assess-manifest.md",
        "index.md", "checksums.txt",
    }


def test_the_pasteable_scripts_are_not_executable_by_extension() -> None:
    """`.js` on Windows is bound to Windows Script Host, so double-clicking
    the deliverable RUNS a provisioning script instead of opening it. These
    files exist to be opened and copied; the extension has to say so."""
    for name in (DEPLOY_SCRIPT, ROLLBACK_SCRIPT, ASSESS_SCRIPT, DEMO_SCRIPT):
        assert name.endswith(".js.txt"), name


def test_a_stale_script_from_an_older_build_is_cleared(tmp_path: Path) -> None:
    """A directory built before the rename still holds a pasteable
    `deploy.js`. Clearing only the current names would leave it beside the
    fresh bundle -- the exact "stale script an operator could paste"
    failure clear_generated exists to prevent."""
    out = tmp_path / "build"
    out.mkdir()
    legacy_names = (
        "deploy.js", "rollback.js", "assess.js", "demo-data.js",  # pre-.js.txt
        "INDEX.md",                                               # pre-lowercase
    )
    for legacy in legacy_names:
        (out / legacy).write_text("// last month's run", encoding="utf-8")

    clear_generated(out)

    assert sorted(p.name for p in out.iterdir()) == []


def test_clearing_leaves_files_this_build_never_wrote(tmp_path: Path) -> None:
    """The legacy sweep must not become a licence to delete.

    `--out` is routinely aimed at a directory an operator also keeps their
    own work in, and every name added to the legacy list is one more thing
    removed from it without being asked. Anything the bundle has never
    emitted stays.
    """
    out = tmp_path / "build"
    out.mkdir()
    (out / "notes.md").write_text("mine", encoding="utf-8")
    (out / "deploy.js.bak").write_text("mine", encoding="utf-8")

    clear_generated(out)

    assert sorted(p.name for p in out.iterdir()) == ["deploy.js.bak", "notes.md"]


def test_sha256_lf_is_newline_insensitive() -> None:
    """A bundle built on Windows (CRLF on disk) must hash identically to one
    built on POSIX (LF)."""
    assert sha256_lf("a\r\nb\r\n") == sha256_lf("a\nb\n")


def test_sha256_lf_distinguishes_content() -> None:
    assert sha256_lf("a\n") != sha256_lf("b\n")


def test_clear_generated_removes_set_and_preserves_operator_files(
    tmp_path: Path,
) -> None:
    out = tmp_path / "build"
    out.mkdir()
    for name in GENERATED_FILES:
        (out / name).write_text("stale", encoding="utf-8")
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")

    clear_generated(out)

    for name in GENERATED_FILES:
        assert not (out / name).exists(), name
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_clear_generated_creates_missing_out_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "build"
    clear_generated(out)
    assert out.is_dir()


def test_clear_generated_reporting_flag_removes_reporting_dir(tmp_path: Path) -> None:
    out = tmp_path / "build"
    (out / "reporting" / "powerquery").mkdir(parents=True)
    (out / "reporting" / "powerquery" / "Stale.pq").write_text("stale", encoding="utf-8")
    clear_generated(out, reporting=True)
    assert not (out / "reporting").exists()


def test_clear_generated_without_reporting_flag_leaves_reporting_dir(
    tmp_path: Path,
) -> None:
    out = tmp_path / "build"
    (out / "reporting").mkdir(parents=True)
    (out / "reporting" / "keep.pq").write_text("keep", encoding="utf-8")
    clear_generated(out)
    assert (out / "reporting" / "keep.pq").exists()


def test_write_checksums_sorted_sha256sum_lines_omitting_itself(
    tmp_path: Path,
) -> None:
    out = tmp_path / "build"
    out.mkdir()
    (out / "b.js").write_text("bee\n", encoding="utf-8")
    (out / "a.js").write_text("ay\n", encoding="utf-8")

    write_checksums(out, ["b.js", "a.js"])

    text = (out / "checksums.txt").read_text(encoding="utf-8")
    assert text.endswith("\n")
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("  a.js")
    assert lines[1].endswith("  b.js")
    assert all(len(line.split("  ")[0]) == 64 for line in lines)
    assert not any("checksums.txt" in line for line in lines)


def test_checksums_is_written_lf_even_on_windows(tmp_path: Path) -> None:
    """`sha256sum -c` takes a trailing CR as part of the FILENAME.

    `write_checksums` promises "plain sha256sum format ... keeps
    `sha256sum -c` clean". Written in text mode on Windows every line gained
    a CR, so sha256sum looked for a file named "a.js.txt\\r" and reported
    "FAILED open or read" for every entry -- the format claim was false for
    any bundle built on Windows.

    This pins the FILE being well-formed, not the bundle being
    sha256sum-verifiable: the digests are of LF-normalised bytes, so a
    Windows-built bundle still will not match bare `-c`. index.md documents
    that and advertises an LF-normalising Python one-liner instead.

    Asserted on BYTES deliberately. Every other checksum test here reads the
    file with `read_text`, which normalises CRLF to \\n on the way in --
    which is exactly why none of them ever saw this.
    """
    out = tmp_path / "build"
    out.mkdir()
    (out / "a.js.txt").write_text("ay\n", encoding="utf-8")

    write_checksums(out, ["a.js.txt"])

    raw = (out / "checksums.txt").read_bytes()
    assert b"\r" not in raw, raw


def test_write_checksums_round_trip_validates(tmp_path: Path) -> None:
    """The recorded digest is of the BYTES on disk.

    It used to be `sha256_lf(read_text(...))`, and this test asserted the
    same expression it was computed from -- so it held whatever the file
    actually contained. Hashing `read_bytes()` is what `sha256sum` does,
    and is the only form that can disagree when the manifest is wrong.
    """
    out = tmp_path / "build"
    out.mkdir()
    write_artifact(out / "x.js.txt", "line1\nline2\n")

    write_checksums(out, ["x.js.txt"])

    line = (out / "checksums.txt").read_text(encoding="utf-8").splitlines()[0]
    digest, _, relpath = line.partition("  ")
    assert relpath == "x.js.txt"
    assert digest == hashlib.sha256((out / relpath).read_bytes()).hexdigest()


def test_write_artifact_strips_carriage_returns_from_the_content(
    tmp_path: Path,
) -> None:
    """`newline="\\n"` only stops Python ADDING a CR; it does not remove one
    already in the string.

    A `.j2` checked out with CRLF, or a mapping value carrying one, would
    otherwise put CR bytes in the artifact while the digest hashed them
    away -- reopening the exact gap between the manifest and the bytes on
    disk that this writer exists to close.
    """
    out = tmp_path / "build"
    write_artifact(out / "crlf.js.txt", "a\r\nb\rc\nd\n")

    raw = (out / "crlf.js.txt").read_bytes()
    assert b"\r" not in raw
    assert raw == b"a\nb\nc\nd\n"


def test_write_index_lists_base_artifacts_not_itself(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    write_index(out)
    md = (out / "index.md").read_text(encoding="utf-8")
    for name in ("deploy-manifest.md", ASSESS_SCRIPT, "assess-manifest.md",
                 DEPLOY_SCRIPT, ROLLBACK_SCRIPT, "checksums.txt"):
        assert f"`{name}`" in md, name
    assert "`index.md`" not in md
    assert "`reporting/`" not in md
    # Pointer to the manifest's run steps, and a verify recipe for each of
    # the two shells an operator actually has. The bundle is LF everywhere,
    # so these are the STANDARD tools rather than a bespoke normalising
    # one-liner -- which is the whole point of the LF policy.
    assert "How to run this deployment" in md
    assert "sha256sum -c checksums.txt" in md
    assert "Get-FileHash" in md


def test_write_index_reporting_row(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    write_index(out, reporting=True)
    assert "`reporting/`" in (out / "index.md").read_text(encoding="utf-8")


def test_write_index_says_so_when_no_env_file_was_read(tmp_path: Path) -> None:
    """The default `env_provenance` must say explicitly that nothing was
    read -- an absent line is indistinguishable from a feature that never
    ran. Also pins that a caller passing no argument at all (the extension
    CLI composition point `emit_bundle` and `write_index` both document)
    still gets the honest line, not a crash from a missing parameter."""
    out = tmp_path / "build"
    out.mkdir()
    write_index(out)
    assert "No dbml-sharepoint.env file was read." in (out / "index.md").read_text(encoding="utf-8")


def test_write_index_reports_the_env_file_that_was_read(tmp_path: Path) -> None:
    from dbml_sharepoint.model.env_file import ENV_SETTINGS, EnvProvenance, EnvValue

    out = tmp_path / "build"
    out.mkdir()
    provenance = EnvProvenance(
        path="dbml-sharepoint.env",
        digest="abc123def456",
        values=(
            EnvValue(setting=ENV_SETTINGS[0], value="svc@example.org", used=True, override=None),
        ),
    )
    write_index(out, env_provenance=provenance)
    md = (out / "index.md").read_text(encoding="utf-8")
    assert "dbml-sharepoint.env" in md
    assert "abc123def456" in md
    assert "DBMLSP_ENTERPRISE_READER" in md


def test_the_package_has_exactly_one_writer() -> None:
    """`write_artifact` is the only thing in the package allowed to write.

    `Path.write_text` defaults to text mode, so on Windows it emits CRLF while
    `.gitattributes` declares `* text=auto eol=lf`. A writer that omits
    `newline="\\n"` therefore rewrites every file it touches, and the one real
    change hides among a hundred phantom ones. AGENTS.md records this; both
    committed-output generators and the bundle artifacts were fixed for it.

    The defect is PER-CALL-SITE, which is what makes it worth a test rather than
    a note: the fix does not generalise, so the next writer someone adds
    reintroduces it, and nothing in ruff, mypy or the suite would say so.

    Static, in the same way `test_every_finding_site_carries_a_location` is:
    a property of the source, not of any particular run. It is deliberately
    AST-based -- `grep` finds five more hits in this package, and all five are
    the word `write_text` inside a docstring or a comment explaining this very
    trap.
    """
    import ast

    def is_a_write_call(func: ast.expr) -> bool:
        """`path.write_text(...)`, however `path` was spelled."""
        return isinstance(func, ast.Attribute) and func.attr == "write_text"

    writers: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and is_a_write_call(node.func):
                keywords = {kw.arg for kw in node.keywords}
                writers.append(
                    f"{path.relative_to(PACKAGE)}:{node.lineno} "
                    f"(keywords: {sorted(k for k in keywords if k)})",
                )

    # Exactly one, not "at most one". Zero would mean `write_artifact` has been
    # renamed or moved out of the package, at which point this test would be
    # green while guarding nothing -- the same failure the `sites > 100` guard
    # in test_findings.py exists to prevent.
    assert len(writers) == 1, (
        "the package must write through `bundle.write_artifact` alone, which "
        'passes newline="\\n". Found:\n  ' + "\n  ".join(writers)
    )
    assert writers[0].startswith("bundle.py:"), writers[0]
    assert "'newline'" in writers[0], (
        f"the one writer must pass newline: {writers[0]}"
    )


def test_write_index_verify_row_only_when_asked(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    write_index(out)
    assert "`verify.js.txt`" not in (out / "index.md").read_text(encoding="utf-8")
    write_index(out, verify=True)
    md = (out / "index.md").read_text(encoding="utf-8")
    assert "`verify.js.txt`" in md
    assert "_dbml-verify" in md


def _emit(tmp_path: Path, schema: object, bundle: object) -> Path:
    from dbml_sharepoint.model.release import load_release

    out = tmp_path / "build"
    # The CLI writes the manifest before emitting; the checksums cover it.
    out.mkdir(exist_ok=True)
    (out / "deploy-manifest.md").write_text("manifest", encoding="utf-8")
    emit_bundle(
        out, schema=schema, mapping_bundle=bundle,  # type: ignore[arg-type]
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test", site_role="default",
        schema_name="s.dbml", mapping_name="m.yaml", source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", seed=False,
    )
    return out


def test_verify_is_emitted_only_for_a_pack_that_uses_a_clock_cell(tmp_path: Path) -> None:
    """The simple fixture's view window is a clock cell, so every ordinary
    build carries verify.js.txt; a pack with no clock use must not, and a
    stale one from an earlier build of it must go."""
    from _model import bundle as make_bundle
    from _model import column
    from _model import schema as make_schema
    from _model import table as make_table

    from dbml_sharepoint.model.conditions import Group, Leaf
    from dbml_sharepoint.model.mapping_types import ViewDef

    plain_schema = make_schema(make_table(
        "Task", column("Title", required=True), column("Due", "date"), note="Tasks.",
    ))
    clock = make_bundle(entities=["Task"], views={"Task": [ViewDef(
        title="Soon", fields=["Title"],
        where=Group("all_of", (Leaf(field="Due", op="leq", value="today+7"),)),
    )]})
    out = _emit(tmp_path, plain_schema, clock)
    assert (out / "verify.js.txt").is_file()
    assert "verify.js.txt" in (out / "checksums.txt").read_text(encoding="utf-8")
    assert "`verify.js.txt`" in (out / "index.md").read_text(encoding="utf-8")

    clear_generated(out, reporting=True)
    assert not (out / "verify.js.txt").exists()
    out = _emit(tmp_path, plain_schema, make_bundle(entities=["Task"]))
    assert not (out / "verify.js.txt").exists()
    assert "verify.js.txt" not in (out / "checksums.txt").read_text(encoding="utf-8")
    assert "`verify.js.txt`" not in (out / "index.md").read_text(encoding="utf-8")
