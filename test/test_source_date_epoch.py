"""`SOURCE_DATE_EPOCH` makes two builds of the same inputs byte-identical."""

from pathlib import Path

import pytest
import typer
from _paths import FIXTURES

from dbml_sharepoint.pipeline import execute_build

EPOCH = 1759276800  # 2025-10-01T00:00:00Z


def _build_simple(out: Path, source_date_epoch: int | None = None) -> dict[str, bytes]:
    execute_build(
        schema=FIXTURES / "simple.dbml",
        mapping=FIXTURES / "sharepoint-mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/test",
        time_zone="UTC",
        site_role="default",
        out=out,
        source_date_epoch=source_date_epoch,
    )
    return {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def test_source_date_epoch_fixes_both_stamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    first = _build_simple(tmp_path / "a")
    second = _build_simple(tmp_path / "a2")
    deploy = (tmp_path / "a" / "deploy.js.txt").read_text(encoding="utf-8")
    assert "2025-10-01T00:00:00+00:00" in deploy
    assert first == second


def test_the_epoch_clamps_a_newer_schema_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1")
    _build_simple(tmp_path / "a")
    deploy = (tmp_path / "a" / "deploy.js.txt").read_text(encoding="utf-8")
    assert "(mtime: 1970-01-01T00:00:01+00:00)" in deploy


def test_the_keyword_beats_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1")
    _build_simple(tmp_path / "a", source_date_epoch=EPOCH)
    deploy = (tmp_path / "a" / "deploy.js.txt").read_text(encoding="utf-8")
    assert "2025-10-01T00:00:00+00:00" in deploy


def test_the_zero_epoch_is_a_valid_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    _build_simple(tmp_path / "a", source_date_epoch=0)
    deploy = (tmp_path / "a" / "deploy.js.txt").read_text(encoding="utf-8")
    assert "1970-01-01T00:00:00+00:00" in deploy


@pytest.mark.parametrize("keyword", [-1, 10**20])
def test_a_refused_keyword_epoch_is_a_refused_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    keyword: int,
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    with pytest.raises(typer.Exit) as raised:
        _build_simple(tmp_path / "a", source_date_epoch=keyword)
    assert raised.value.exit_code == 1
    assert "SOURCE_DATE_EPOCH" in capsys.readouterr().err


@pytest.mark.parametrize("raw", ["yesterday", "-5", "1.5", "", "99999999999999999"])
def test_a_malformed_epoch_is_a_refused_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], raw: str,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", raw)
    with pytest.raises(typer.Exit) as raised:
        _build_simple(tmp_path / "a")
    assert raised.value.exit_code == 1
    assert "SOURCE_DATE_EPOCH" in capsys.readouterr().err
