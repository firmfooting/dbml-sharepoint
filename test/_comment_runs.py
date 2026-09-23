"""Find paragraph-length comment runs, for the ratchet in `test_comment_runs.py`.

A run is `MIN_RUN` or more consecutive comment lines in one file: Python
and YAML `#` lines, JS, Power Query and DBML `//` lines, and every line of a
`/* */` or Jinja `{# #}` block. Docstrings are out of scope, being where long
prose belongs. A run whose first line has one of the evidence forms
`AGENTS.md` asks for is exempt. Every other run is pinned by a fingerprint of
its text, so a grandfathered run may move but not change.
"""

from __future__ import annotations

import hashlib
import io
import re
import subprocess
import tokenize
from collections import Counter
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

C_STYLE = frozenset({".js", ".pq", ".dbml"})

HASH_STYLE = frozenset({".yaml", ".yml"})

#: A `/` after one of these (or at a line's start) opens a regex, not a division.
REGEX_AFTER = frozenset("(,=:[!&|?{};+-*%<>~^") | {""}

#: Stripped from each end of a comment line before it is fingerprinted.
MARKERS = re.compile(r"^(?:\{#|/\*+|//+|#+:?|\*+)|(?:#\}|\*+/)$")

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
    fingerprint: str = ""


def fingerprint(lines: list[str]) -> str:
    """A short hash of a run's words, blind to indentation and comment markers."""
    body = "\n".join(MARKERS.sub("", line.strip()).strip() for line in lines)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


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


def _regex_end(line: str, index: int) -> int:
    """The index of the `/` closing the regex literal opened at `index`."""
    in_class = False
    index += 1
    while index < len(line):
        char = line[index]
        if char == "\\":
            index += 1
        elif char in "[]":
            in_class = char == "["
        elif char == "/" and not in_class:
            return index
        index += 1
    return index


def _template_state(line: str, stack: list[int]) -> list[int]:
    """The template nesting after a JS line: -1 is a literal, n is `${` brace depth."""
    stack = list(stack)
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if stack and stack[-1] < 0:
            if char == "`":
                stack.pop()
            elif line.startswith("${", index):
                stack.append(0)
                index += 1
        elif quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "`":
            stack.append(-1)
        elif line.startswith("//", index):
            break
        elif char == "/" and line[:index].rstrip()[-1:] in REGEX_AFTER:
            index = _regex_end(line, index)
        elif stack and char in "{}":
            stack[-1] += 1 if char == "{" else -1
            if stack[-1] < 0:
                stack.pop()
        index += 1
    return stack


def _template_lines(lines: list[str], comments: set[int]) -> set[int]:
    """Lines that open inside a JS template literal, where `//` is string content."""
    # A regex after `)` or a name reads as division, so a quote or backtick in it misleads.
    found: set[int] = set()
    stack: list[int] = []
    for number, line in enumerate(lines, start=1):
        if stack:
            found.add(number)
        if stack or number not in comments:
            stack = _template_state(line, stack)
    return found


def _comment_lines(text: str, name: str) -> set[int]:
    lines = text.splitlines()
    if name.endswith(".py"):
        return _python_comment_lines(text)
    found: set[int] = set()
    inner = name.removesuffix(".j2")
    suffix = Path(inner).suffix
    if inner != name:
        found |= _block_comment_lines(lines, None, "{#", "#}")
    if suffix in HASH_STYLE:
        found |= {n for n, line in enumerate(lines, start=1) if line.lstrip().startswith("#")}
    if suffix in C_STYLE:
        c_style = _block_comment_lines(lines, "//", "/*", "*/")
        if suffix == ".js":
            c_style -= _template_lines(lines, found | c_style)
        found |= c_style
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
            body = lines[numbers[start] - 1 : numbers[start] - 1 + length]
            first = body[0].strip()
            runs.append(
                Run(numbers[start], length, first, _exemption(first), fingerprint(body)),
            )
        start = index
    return runs


def excluded(name: str, tracked: set[str]) -> bool:
    """Generated files are not scanned; the templates they come from are."""
    if name.startswith(GENERATED):
        return True
    rendered = name.startswith(PROBES) and "/" not in name.removeprefix(PROBES)
    return rendered and f"{PROBES}templates/{name.removeprefix(PROBES)}.j2" in tracked


def _scanned_syntax(name: str) -> bool:
    return name.endswith((".py", ".j2")) or Path(name).suffix in C_STYLE | HASH_STYLE


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


def pins(measured: dict[str, list[Run]]) -> dict[str, list[str]]:
    """The `PINNED` table that `measured` satisfies exactly."""
    table = {
        name: sorted(run.fingerprint for run in runs if run.exemption is None)
        for name, runs in sorted(measured.items())
    }
    return {name: prints for name, prints in table.items() if prints}


def problems(measured: dict[str, list[Run]], pinned: dict[str, list[str]]) -> list[str]:
    """Each unexempt run with no pin, and each pin with no run."""
    found: list[str] = []
    for name in sorted(set(measured) | set(pinned)):
        runs = [run for run in measured.get(name, []) if run.exemption is None]
        spare = Counter(pinned.get(name, []))
        unpinned: list[Run] = []
        for run in runs:
            if spare[run.fingerprint] > 0:
                spare[run.fingerprint] -= 1
            else:
                unpinned.append(run)
        if unpinned:
            listed = "\n  ".join(
                f"{name}:{run.first_line}  {run.text}  [{run.fingerprint}]" for run in unpinned
            )
            found.append(
                f"{name} has {len(unpinned)} unpinned comment runs of {MIN_RUN}+ lines. "
                f"AGENTS.md asks for one-line comments, so shorten each below {MIN_RUN} "
                "lines or open it with MEASURED, a date, `#:` or a ---- banner ----. "
                "An edited grandfathered run is a new run: fix the lines you are already "
                f"touching. The runs:\n  {listed}",
            )
        stale = sorted(spare.elements())
        if stale:
            found.append(
                f"{name} has PINNED fingerprints that match no comment run; remove them "
                f"so the ratchet holds: {stale}",
            )
    return found
