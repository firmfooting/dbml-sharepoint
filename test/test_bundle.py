# test/test_bundle.py
"""Bundle-level packaging: artifact clearing, LF-stable hashing, INDEX/checksums."""

from pathlib import Path

from dbml_sharepoint.bundle import (
    GENERATED_FILES,
    clear_generated,
    sha256_lf,
    write_checksums,
    write_index,
)


def test_generated_files_is_the_full_bundle() -> None:
    # demo-data.js is in the clear set even though it is emitted only with
    # --seed: a rebuild WITHOUT --seed must remove a stale demo script.
    assert set(GENERATED_FILES) == {
        "deploy.js", "rollback.js", "assess.js", "demo-data.js",
        "deploy-manifest.md", "assess-manifest.md",
        "INDEX.md", "checksums.txt",
    }


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


def test_write_checksums_round_trip_validates(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    (out / "x.js").write_text("line1\nline2\n", encoding="utf-8")

    write_checksums(out, ["x.js"])

    line = (out / "checksums.txt").read_text(encoding="utf-8").splitlines()[0]
    digest, _, relpath = line.partition("  ")
    assert relpath == "x.js"
    assert digest == sha256_lf((out / relpath).read_text(encoding="utf-8"))


def test_write_index_lists_base_artifacts_not_itself(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    write_index(out)
    md = (out / "INDEX.md").read_text(encoding="utf-8")
    for name in ("deploy-manifest.md", "assess.js", "assess-manifest.md",
                 "deploy.js", "rollback.js", "checksums.txt"):
        assert f"`{name}`" in md, name
    assert "`INDEX.md`" not in md
    assert "`reporting/`" not in md
    # Pointer to the manifest's run steps, and the LF-normalised verify story.
    assert "How to run this deployment" in md
    assert "LF-normalised" in md


def test_write_index_reporting_row(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    write_index(out, reporting=True)
    assert "`reporting/`" in (out / "INDEX.md").read_text(encoding="utf-8")
