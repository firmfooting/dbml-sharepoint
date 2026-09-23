"""Count paragraph-length comment runs, for the ratchet in `test_comment_runs.py`.

A run is `MIN_RUN` or more consecutive comment lines in one file: Python `#`
lines, JS and Power Query `//` lines, and every line of a `/* */` or Jinja
`{# #}` block. Docstrings are out of scope, being where long prose belongs.
A run whose first line has one of the evidence forms `AGENTS.md` asks for is
exempt, and so is never counted against a pin.
"""

from __future__ import annotations

import io
import re
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path

import pytest

#: The threshold #610 measured at; six lines of why is already generous.
MIN_RUN = 7

#: The trees whose tracked files are scanned.
ROOTS = ("src", "test", "scripts", "website/scripts")

#: Generated output, excluded for the reason markdownlint excludes it.
GENERATED = ("test/fixtures/expected/", "website/docs/api/")

#: Rendered probes live here; their templates sit under `templates/`.
PROBES = "test/manual/"

C_STYLE = frozenset({".js", ".pq"})

#: Checked in order against a run's first line; the first match names it.
EXEMPTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("MEASURED", re.compile(r"MEASURED")),
    ("dated", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("attribute", re.compile(r"^#:")),
    ("banner", re.compile(r"-{4,}")),
)


@dataclass(frozen=True)
class Run:
    """One run of comment lines, located by its first line."""

    first_line: int
    length: int
    text: str
    exemption: str | None


def _python_comment_lines(text: str) -> set[int]:
    """Lines holding only a comment; tokenize keeps a `#` in a string out."""
    found: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and not token.line[: token.start[1]].strip():
            found.add(token.start[0])
    return found


def _block_comment_lines(
    lines: list[str], line_marker: str | None, opener: str, closer: str,
) -> set[int]:
    """Lines inside `opener`...`closer` blocks or led by `line_marker`."""
    found: set[int] = set()
    inside = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if inside:
            found.add(number)
            inside = closer not in stripped
        elif line_marker is not None and stripped.startswith(line_marker):
            found.add(number)
        elif stripped.startswith(opener):
            found.add(number)
            inside = closer not in stripped[len(opener):]
    return found


def _comment_lines(text: str, name: str) -> set[int]:
    lines = text.splitlines()
    if name.endswith(".py"):
        return _python_comment_lines(text)
    found: set[int] = set()
    inner = name.removesuffix(".j2")
    if inner != name:
        found |= _block_comment_lines(lines, None, "{#", "#}")
    if Path(inner).suffix in C_STYLE:
        found |= _block_comment_lines(lines, "//", "/*", "*/")
    return found


def _exemption(first: str) -> str | None:
    for label, pattern in EXEMPTIONS:
        if pattern.search(first):
            return label
    return None


def comment_runs(text: str, name: str) -> list[Run]:
    """Every run of `MIN_RUN` or more comment lines in `text`, exempt or not."""
    lines = text.splitlines()
    numbers = sorted(_comment_lines(text, name))
    runs: list[Run] = []
    start = 0
    for index in range(1, len(numbers) + 1):
        if index < len(numbers) and numbers[index] == numbers[index - 1] + 1:
            continue
        length = index - start
        if length >= MIN_RUN:
            first = lines[numbers[start] - 1].strip()
            runs.append(Run(numbers[start], length, first, _exemption(first)))
        start = index
    return runs


def excluded(name: str, tracked: set[str]) -> bool:
    """Generated files are not scanned; the templates they come from are."""
    if name.startswith(GENERATED):
        return True
    rendered = name.startswith(PROBES) and "/" not in name.removeprefix(PROBES)
    return rendered and f"{PROBES}templates/{name.removeprefix(PROBES)}.j2" in tracked


def _scanned_syntax(name: str) -> bool:
    return name.endswith((".py", ".j2")) or Path(name).suffix in C_STYLE


def scanned_files(root: Path) -> list[str]:
    """Tracked files in scope, so untracked scratch can never move a count."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *ROOTS],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    tracked = {name for name in result.stdout.split("\0") if name}
    return sorted(
        name for name in tracked if _scanned_syntax(name) and not excluded(name, tracked)
    )


def measure(root: Path) -> dict[str, list[Run]]:
    """Every scanned file with at least one run, exempt runs included."""
    found: dict[str, list[Run]] = {}
    for name in scanned_files(root):
        runs = comment_runs((root / name).read_text(encoding="utf-8"), name)
        if runs:
            found[name] = runs
    return found


def problems(measured: dict[str, list[Run]], pinned: dict[str, int]) -> list[str]:
    """Each file whose count of unexempt runs differs from its pin."""
    found: list[str] = []
    for name in sorted(set(measured) | set(pinned)):
        runs = [run for run in measured.get(name, []) if run.exemption is None]
        pin = pinned.get(name, 0)
        if len(runs) > pin:
            listed = "\n  ".join(f"{name}:{run.first_line}  {run.text}" for run in runs)
            found.append(
                f"{name} has {len(runs)} comment runs of {MIN_RUN}+ lines and "
                f"PINNED allows {pin}. AGENTS.md asks for one-line comments, so "
                "shorten the new run or open it with MEASURED, a date, `#:` or "
                f"a ---- banner ----. The runs:\n  {listed}",
            )
        elif len(runs) < pin:
            fix = f"{name!r}: {len(runs)}," if runs else "delete its entry"
            found.append(
                f"{name} has {len(runs)} comment runs and PINNED holds {pin}; "
                f"lower the pin so the ratchet holds: {fix}",
            )
    return found
