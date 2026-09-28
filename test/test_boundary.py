"""Core names no package that plugs into it, and not the organisation whose material stays out.

A pack provider reaches core through an entry point, so core never has a reason to name one.
"""

import hashlib
import re
import subprocess
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest
from _paths import REPO_ROOT

#: Where a name sits in a word: (offset, length), or None.
type Finder = Callable[[str], tuple[int, int] | None]

#: SHA-256 of each forbidden name in lower case, by length; digests, so this public file names none.
_FORBIDDEN: dict[int, frozenset[str]] = {
    4: frozenset({"5a098c8778e8c8f5218b94eb26c7e94af8ca1b94bd0f43ffe766919d092c44e6"}),
    7: frozenset({"d0186b437fe49d65ba16ea4efbd42d12e6886b4c887aab253c03b2c8dca90391"}),
    16: frozenset({"1d1441ff1e726ef0e063e1fd7d8f21f7ddfddcd43e6e480bb8b3c774532b6309"}),
}

#: Every forbidden name is spelled from these characters, so a match lies inside one run of them.
_WORD = re.compile(r"[a-z0-9_]+")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _finder(forbidden: dict[int, frozenset[str]]) -> Finder:
    """Look for any forbidden name inside one lower-case word, every window of each length."""

    @cache
    def find(word: str) -> tuple[int, int] | None:
        for length, digests in forbidden.items():
            for start in range(len(word) - length + 1):
                if _digest(word[start : start + length]) in digests:
                    return start, length
        return None

    return find


_FIND = _finder(_FORBIDDEN)


def _first(line: str, find: Finder) -> str | None:
    """The first forbidden name in `line`, spelled as the line spells it."""
    for word in _WORD.finditer(line.lower()):
        if (hit := find(word.group(0))) is not None:
            start = word.start() + hit[0]
            return line[start : start + hit[1]]
    return None


def _tracked_under_src() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "src"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Skipping is honest; an empty list would pass without reading a file.
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


def _naming(path: Path, relative: str, find: Finder = _FIND) -> list[str]:
    """Where `path` names a forbidden word: its path, then each line."""
    found = [f"{relative}: in the path"] if _first(relative, find) else []
    text = path.read_bytes().decode("utf-8", errors="replace")
    found.extend(
        f"{relative}:{number}: {hit}"
        for number, line in enumerate(text.split("\n"), start=1)
        if (hit := _first(line, find)) is not None
    )
    return found


def test_nothing_under_src_names_a_dependent_package() -> None:
    tracked = _tracked_under_src()
    assert len(tracked) > 100, f"only {len(tracked)} files scanned, so this pins nothing"
    offenders = [
        hit
        for path in tracked
        for hit in _naming(path, path.relative_to(REPO_ROOT).as_posix())
    ]
    assert not offenders, (
        "Core must not name a package that plugs into it, or the organisation whose "
        "material stays out of it. Move the reference into that package:\n"
        + "\n".join(offenders)
    )


def test_three_names_are_forbidden() -> None:
    """An emptied table would pass every file, so pin its size and shape."""
    digests = [d for group in _FORBIDDEN.values() for d in group]
    assert len(digests) == 3
    assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in digests)


#: Stand-ins for the real names, which this file may not spell.
_SEEDED = _finder({10: frozenset({_digest("acme_packs")}), 4: frozenset({_digest("zork")})})


@pytest.mark.parametrize(
    ("written", "reported"),
    [
        ("acme_packs", "acme_packs"),
        ("ZORK", "ZORK"),
        ("from_acme_packs_import", "acme_packs"),
        ("Zork-packs", "Zork"),
    ],
)
def test_the_scan_reports_a_seeded_name(tmp_path: Path, written: str, reported: str) -> None:
    seeded = tmp_path / "catalogue.py"
    seeded.write_text(f"import os\n# from {written} import packs\n", encoding="utf-8", newline="\n")
    assert _naming(seeded, "catalogue.py", _SEEDED) == [f"catalogue.py:2: {reported}"]


def test_the_scan_reports_a_seeded_path(tmp_path: Path) -> None:
    seeded = tmp_path / "notes.md"
    seeded.write_text("nothing here\n", encoding="utf-8")
    assert _naming(seeded, "src/zork-notes.md", _SEEDED) == ["src/zork-notes.md: in the path"]
