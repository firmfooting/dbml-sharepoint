# test/test_complexity_ratchet.py
"""The complexity ratchet, asserted instead of described.

`pyproject.toml` sets `max-complexity` and a comment beside it says what that
number means. The comment was prose, so it rotted: measured on `main` at
2efa4f29, three of its four numbers were wrong. It claimed
`_formatting.py::check` was 49 when it was 57, `_retirement.py::check` was the
third worst at 40 when the third worst was `jsgen.py::build_schema_json`, and
that the ruff default of 10 flags 25 functions when it flags 33.

That is the failure `test_limit_authority.py` and `test_family_count_prose.py`
already exist to close, re-committed in a third place. A reader lowering the
ratchet trusts those numbers, and #308 is exactly a reader having done so: the
ceiling moved down by six rather than down to the new worst, which handed the
largest remaining offender free growth that nothing would report.

So the numbers live here now, measured by the same tool that enforces them.
Ruff is a pinned dev dependency rather than an optional one like Node, so a
missing binary fails rather than skips: a silently skipping gate is the thing
#172 is open about.
"""

import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from _paths import REPO_ROOT

SRC = REPO_ROOT / "src"

#: `check` is too complex (61 > 1). Ruff's concise line, whose numbers are the
#: measured complexity and the ceiling it was measured against.
_TOO_COMPLEX = re.compile(r"`(?P<name>[^`]+)` is too complex \((?P<score>\d+) > \d+\)")

#: What the comment in `pyproject.toml` says, and therefore what this module
#: holds it to. Both come out of `_complexities()` below, so a failure here
#: names the new value rather than leaving it to be looked up.
DEFAULT_CEILING = 10


def _ruff() -> str:
    """The ruff that measures, preferring the one beside this interpreter.

    `shutil.which` alone would take a ruff from the operator's PATH, which on
    a machine with a global install is a different version from the pinned
    one, and mccabe scores are a property of the version.
    """
    beside = Path(sys.executable).parent / ("ruff.exe" if sys.platform == "win32" else "ruff")
    if beside.is_file():
        return str(beside)
    found = shutil.which("ruff")
    assert found is not None, "ruff is a pinned dev dependency and was not found"
    return found


def _complexities(ceiling: int) -> dict[str, int]:
    """Every function over `ceiling`, mapped to its measured complexity.

    Measured by running ruff rather than by walking the AST here. A second
    implementation of mccabe would be a second opinion, and the number that
    matters is the one the gate will produce.
    """
    proc = subprocess.run(  # noqa: S603
        [
            _ruff(), "check", "--select", "C901",
            "--config", f"lint.mccabe.max-complexity={ceiling}",
            "--output-format", "concise", "--no-cache", str(SRC),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    found: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        match = _TOO_COMPLEX.search(line)
        if match is None:
            continue
        path, _, _ = line.partition(":")
        found[f"{Path(path).name}::{match['name']}"] = int(match["score"])
    assert found, f"ruff reported no function over {ceiling}, so this pins nothing"
    return found


def _declared_ceiling() -> int:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    return int(config["tool"]["ruff"]["lint"]["mccabe"]["max-complexity"])


def test_the_ratchet_sits_on_the_worst_function_not_above_it() -> None:
    """THE gate #308 asks for, and the reason it is a gate rather than a note.

    Ruff fires on `> max`, so a ceiling equal to the worst function allows
    zero growth and a ceiling above it allows exactly the difference, silently.
    Nothing else in the suite can see that slack: it is not a failure, it is
    an absence of one.

    Lowering the ceiling as functions shrink is the ratchet turning, and it is
    meant to need this test edited. Raising it needs the argument AGENTS.md
    asks for on any weakened guard, and that argument belongs in the pull
    request rather than in a comment nothing reads.
    """
    measured = _complexities(1)
    worst_name = max(measured, key=lambda name: measured[name])
    worst = measured[worst_name]
    assert _declared_ceiling() == worst, (
        f"max-complexity is {_declared_ceiling()} and the worst function is "
        f"{worst_name} at {worst}. A ceiling above the worst function is slack "
        f"that nothing reports; set max-complexity to {worst}."
    )


def test_the_ratchet_comment_states_the_measured_worst_functions() -> None:
    """The three functions the comment names, held to what they actually score.

    Named individually rather than counted, because the comment's job is to
    tell a reader WHICH functions the ceiling is holding. A count would stay
    true while every name in it went wrong, which is how it drifted before.
    """
    measured = _complexities(1)
    ranked = sorted(measured.items(), key=lambda item: (-item[1], item[0]))
    comment = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for name, score in ranked[:3]:
        module, _, function = name.partition("::")
        stated = re.search(
            rf"`{re.escape(module)}::{re.escape(function)}`[^\n]*?(\d+)", comment,
        )
        assert stated is not None, (
            f"the comment beside max-complexity does not name {name}, "
            f"currently one of the three worst at {score}"
        )
        assert int(stated.group(1)) == score, (
            f"the comment says {name} is {stated.group(1)}; it is {score}"
        )


def test_the_comment_states_how_many_functions_the_ruff_default_would_flag() -> None:
    """The argument for not using ruff's default of 10 rests on a count, so
    the count is measured rather than remembered. It read 25 when the true
    figure was 33, which overstates how close the default is to reachable."""
    flagged = len(_complexities(DEFAULT_CEILING))
    comment = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    stated = re.search(r"flags (\d+) functions at once", comment)
    assert stated is not None, (
        "the comment beside max-complexity no longer states how many functions "
        "ruff's default would flag, which is the whole argument for not using it"
    )
    assert int(stated.group(1)) == flagged, (
        f"the comment says the default flags {stated.group(1)} functions; "
        f"it flags {flagged}"
    )
