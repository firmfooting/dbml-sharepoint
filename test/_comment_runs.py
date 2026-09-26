"""Find paragraph-length comment runs, for the ratchet in `test_comment_runs.py`.

A run is `MIN_RUN` or more consecutive comment lines in one file: Python,
YAML and TOML `#` lines, JS, Power Query and DBML `//` lines, and every line of a
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
from dataclasses import dataclass, field
from pathlib import Path

import pytest

#: The threshold #610 measured at; six lines of why is already generous.
MIN_RUN = 7

#: Generated output, excluded for the reason markdownlint excludes it.
GENERATED = ("test/fixtures/expected/", "website/docs/api/")

#: Rendered probes live here; their templates sit under `templates/`.
PROBES = "test/manual/"

C_STYLE = frozenset({".js", ".pq", ".dbml"})

HASH_STYLE = frozenset({".yaml", ".yml"})

TOML = ".toml"

#: A `/` after one of these (or at a line's start) opens a regex, not a division.
REGEX_AFTER = frozenset("(,=:[!&|?{};+-*%<>~^") | {""}

#: A `/` after one of these words also opens a regex.
REGEX_KEYWORD = re.compile(
    r"\b(?:return|typeof|instanceof|in|of|new|delete|void|throw|case|do|else|yield|await)$",
)

#: A key or sequence entry whose value is a `|` or `>` block scalar.
BLOCK_SCALAR = re.compile(r"(?:^\s*-|:)\s+[|>][1-9+-]*\s*(?:#.*)?$")

#: Indentation plus any `- ` sequence dashes, which together place a mapping key.
SEQUENCE_LEAD = re.compile(r"^\s*(?:-\s+)*")

#: Stripped from each end of a comment line before it is fingerprinted.
MARKERS = re.compile(r"^(?:\{#|/\*+|//+|#+:?|\*+)|(?:#\}|\*+/)$")

#: A comment marker and an optional `---` banner lead, before an evidence marker.
_OPENING = r"^(?:\{#|/\*+|//+|#+:?|\*+)?\s*(?:-{3,}\s*)?"

#: Checked in order against a run's first line; the first match names it.
EXEMPTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("MEASURED", re.compile(_OPENING + r"MEASURED\b")),
    ("dated", re.compile(_OPENING + r"\d{4}-\d{2}-\d{2}\b")),
    ("attribute", re.compile(r"^#:")),
    ("banner", re.compile(r"^(?:\{#|/\*+|//+|#+:?|\*+)?\s*(?=.*-{4,})-{3,}")),
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


def _jinja_opens(text: str) -> bool:
    """Whether `text` leaves a Jinja comment open."""
    opener = text.rfind("{#")
    return opener >= 0 and "#}" not in text[opener + 2 :]


def _jinja_only_comments(text: str) -> bool:
    """Whether `text` holds nothing but Jinja comments, the last possibly left open."""
    while text:
        if not text.startswith("{#"):
            return False
        closer = text.find("#}", 2)
        if closer < 0:
            return True
        text = text[closer + 2 :].strip()
    return True


def _jinja_comment_lines(lines: list[str]) -> set[int]:
    """Lines holding only `{# #}` comment; a block opened after code counts on."""
    found: set[int] = set()
    inside = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if inside:
            closer = stripped.find("#}")
            if closer < 0 or _jinja_only_comments(stripped[closer + 2 :].strip()):
                found.add(number)
            inside = closer < 0 or _jinja_opens(stripped[closer + 2 :])
        else:
            if stripped.startswith("{#") and _jinja_only_comments(stripped):
                found.add(number)
            inside = _jinja_opens(stripped)
    return found


def _yaml_comment_lines(lines: list[str]) -> set[int]:
    """`#` lines, skipping block scalar content, where a `#` is text."""
    found: set[int] = set()
    floor: int | None = None
    content: int | None = None
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if floor is not None:
            if not stripped:
                continue
            if content is None and indent > floor:
                content = indent
            if content is not None and indent >= content:
                continue
            floor = content = None
        if stripped.startswith("#"):
            found.add(number)
        elif match := BLOCK_SCALAR.search(line):
            # Content must be deeper than its key, which sits after any `- ` item dashes.
            key = len(line) - len(SEQUENCE_LEAD.sub("", line, count=1))
            floor = key if match.group().startswith(":") else indent
            # An explicit indentation indicator fixes the content column relative to the parent.
            explicit = re.search(r"[|>][+-]?([1-9])", match.group().split("#", 1)[0])
            content = floor + int(explicit.group(1)) if explicit else None
    return found


def _toml_string_end(line: str, index: int, delimiter: str) -> int:
    """The index just past the `delimiter` closing a TOML string, or -1 if it stays open."""
    while index < len(line):
        if delimiter.startswith('"') and line[index] == "\\":
            index += 2
        elif line.startswith(delimiter, index):
            return index + len(delimiter)
        else:
            index += 1
    return -1


def _toml_comment_lines(lines: list[str]) -> set[int]:
    """`#` lines, skipping multi-line string content, where a `#` is text."""
    found: set[int] = set()
    open_multi: str = ""
    for number, line in enumerate(lines, start=1):
        index = 0
        if not open_multi and line.lstrip().startswith("#"):
            found.add(number)
            continue
        while index < len(line):
            if open_multi:
                index = _toml_string_end(line, index, open_multi)
                if index < 0:
                    break
                open_multi = ""
            elif line[index] == "#":
                break
            elif line.startswith(('"""', "'''"), index):
                open_multi = line[index : index + 3]
                index += 3
            elif line[index] in "\"'":
                end = _toml_string_end(line, index + 1, line[index])
                index = len(line) if end < 0 else end
            else:
                index += 1
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


def _starts_regex(before: str) -> bool:
    """Whether a `/` after `before` on its line opens a regex rather than divides."""
    before = before.rstrip()
    return before[-1:] in REGEX_AFTER or REGEX_KEYWORD.search(before) is not None


@dataclass
class _CState:
    """Lexer state carried across lines: an open block comment and template frames."""

    #: A flag, not a depth: neither JS nor M nests comments (Learn, m-spec-lexical-structure).
    block: bool = False
    #: -1 is a template literal, n >= 0 the brace depth of a `${` inside one.
    stack: list[int] = field(default_factory=list)


def _lex_c_line(line: str, state: _CState, quotes: str, js: bool) -> bool:
    """Advance `state` over one line; whether the line is a comment line."""
    # A regex after `)` or a name reads as division, so a quote or backtick in it misleads.
    comment = state.block
    code = False
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        step = 1
        if state.stack and state.stack[-1] < 0:
            if char == "\\":
                step = 2
            elif char == "`":
                state.stack.pop()
            elif line.startswith("${", index):
                state.stack.append(0)
                step = 2
        elif state.block:
            if line.startswith("*/", index):
                state.block = False
                step = 2
        elif char.isspace():
            pass
        elif quote:
            step = 2 if char == "\\" else 1
            quote = "" if char == quote else quote
        elif line.startswith("//", index):
            comment = comment or not code
            break
        elif line.startswith("/*", index):
            comment = comment or not code
            state.block = True
            step = 2
        else:
            code = True
            if char in quotes:
                quote = char
            elif js and char == "`":
                state.stack.append(-1)
            elif js and char == "/" and _starts_regex(line[:index]):
                step = _regex_end(line, index) - index + 1
            elif state.stack and char in "{}":
                state.stack[-1] += 1 if char == "{" else -1
                if state.stack[-1] < 0:
                    state.stack.pop()
        index += step
    return comment and not code


def _c_comment_lines(lines: list[str], skip: set[int], suffix: str) -> set[int]:
    """`//` lines and `/* */` blocks, not counting either inside a JS string."""
    found: set[int] = set()
    state = _CState()
    js = suffix == ".js"
    quotes = '"' if suffix == ".pq" else "'\""
    for number, line in enumerate(lines, start=1):
        in_literal = bool(state.stack) and state.stack[-1] < 0
        if number in skip and not in_literal:
            continue
        if _lex_c_line(line, state, quotes, js) and not in_literal:
            found.add(number)
    return found


def _comment_lines(text: str, name: str) -> set[int]:
    lines = text.splitlines()
    if name.endswith(".py"):
        return _python_comment_lines(text)
    found: set[int] = set()
    inner = name.removesuffix(".j2")
    suffix = Path(inner).suffix
    if inner != name:
        found |= _jinja_comment_lines(lines)
    if suffix in HASH_STYLE:
        found |= _yaml_comment_lines(lines)
    if suffix == TOML:
        found |= _toml_comment_lines(lines)
    if suffix in C_STYLE:
        found |= _c_comment_lines(lines, set(found), suffix)
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
    return name.endswith((".py", ".j2")) or Path(name).suffix in C_STYLE | HASH_STYLE | {TOML}


def scanned_files(root: Path) -> list[str]:
    """Every tracked file in a scanned syntax, so untracked scratch never counts."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
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
