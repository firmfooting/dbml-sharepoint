# scripts/mutate_limits.py
"""Mutate every ceiling a pull request changes, and fail on a survivor.

A constant in `analysis/limits.py` can be read by nothing any test exercises,
so moving it changes nothing observable and the suite stays green. The #259
sweep measured that over the whole module: 8 of 28 mutants survived, five
ceilings among them. This script runs the same experiment automatically over
whichever ceilings a branch touches, so a new one arrives either enforced or
with a recorded reason it is not.

    uv run python scripts/mutate_limits.py --base-ref origin/main
    uv run python scripts/mutate_limits.py --constant MAX_DISPLAY_TITLE

`_DESELECTS` decides whether the result means anything, and it drops four
tests for two different reasons.

Three of them read the mutated source rather than any behaviour. Two generated
pages carry these values verbatim, so their currency tests regenerate from the
mutant and fail on it whether or not a rule enforces the ceiling, and
`test_limit_authority.py` scans the package for whatever number `limits.py`
currently holds. MEASURED 2026-08-16, both directions of each pair:

    MAX_FIELD_DESCRIPTION  survives, and reports killed with the API-docs
                           deselect removed
    MAX_VIEW_ROW_LIMIT     survives, and reports killed with the findings
                           deselect removed
    MAX_INTERNAL_NAME      at 31, the message gate matched the 31 inside
                           "Measured 2026-07-31" in a `_views.py` finding
    MAX_DISPLAY_TITLE      killed, with every deselect in place

A kill for the first three is the wrong answer, and leaving the API-docs test
in is how the first run of the #259 sweep reported 28 kills and established
nothing. The findings page is the same defect found here rather than in #259:
`finding_help.py` interpolates seven constants into its prose, so that sweep's
recorded kills for INDEX_WARN_AT, LIST_VIEW_THRESHOLD, MAX_LIST_INDEXES,
MAX_VALIDATION_FORMULA, MAX_VALIDATION_MESSAGE and MAX_VIEW_ROW_LIMIT are not
evidence of enforcement. MAX_DISPLAY_TITLE is the seventh and is killed by its
own boundary tests, so its result stands.

The fourth is dropped for its runtime alone. Dropping tests makes a mutant
harder to kill, so it can hide a kill but cannot manufacture one.
"""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIMITS = REPO_ROOT / "src" / "dbml_sharepoint" / "analysis" / "limits.py"
LIMITS_REL = "src/dbml_sharepoint/analysis/limits.py"

#: Tests dropped from the sweep. The first three read the mutated source, and
#: the fourth is dropped for its runtime; the module docstring holds the
#: measurement behind each.
_DESELECTS = (
    # Regenerates the API page from the mutated source, so it fails on every
    # mutant and reports a kill for a ceiling nothing enforces.
    "test/test_template_lint.py::test_generated_api_docs_are_current",
    # The same defect on a second generated page, because `finding_help.py`
    # interpolates seven of these constants into its prose.
    "test/test_finding_help.py::test_generated_findings_page_is_current",
    # Reads `limits.py` as it stands, so under a mutant it hunts the value the
    # sweep just wrote and its verdict is not evidence of enforcement.
    "test/test_limit_authority.py",
    # Dropped only for its 180-second runtime timeout.
    "test/test_deploy_runtime.py",
)

#: A ceiling declaration the sweep can rewrite, which is one name and one
#: integer on one line. `_integer_constants` fails the run on any other shape.
_DECLARATION = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)(?P<gap>\s*=\s*)(?P<value>[0-9_]+)\s*$")

#: pytest's exit code for "tests ran and something failed", which is the only
#: non-zero code that means the mutant was killed rather than the run broke.
_TESTS_FAILED = 1


def _ascii(text: str) -> str:
    """Text a cp1252 console can print, so a diagnostic cannot raise on its way out."""
    return text.encode("ascii", "replace").decode("ascii")


def _git(*args: str) -> str:
    """Run git in the repository and return its stdout.

    A base ref that does not resolve is the likeliest operator error here, so
    it exits with git's own message rather than a traceback.
    """
    try:
        done = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as failure:
        stderr = _ascii(failure.stderr or "").strip()
        raise SystemExit(
            f"git {' '.join(args)} exited {failure.returncode}: {stderr}"
        ) from failure
    return done.stdout


def _declarations(source: str) -> dict[str, int]:
    """Every constant `limits.py` declares, mapped to its 1-based line number."""
    found: dict[str, int] = {}
    for number, line in enumerate(source.splitlines(), start=1):
        match = _DECLARATION.match(line)
        if match is not None:
            found[match.group("name")] = number
    return found


def _integer_constants(source: str) -> set[str]:
    """Every uppercase integer constant `limits.py` really defines, read from its AST.

    The independent list `_declarations` is checked against, so a declaration
    the line regex cannot rewrite (`MAX_X: Final = 32`, or a trailing comment)
    fails the run instead of going unswept while the job reports success.
    """
    found: set[str] = set()
    for statement in ast.parse(source).body:
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(statement, ast.Assign):
            targets, value = statement.targets, statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets, value = [statement.target], statement.value
        else:
            continue
        if not isinstance(value, ast.Constant):
            continue
        if not isinstance(value.value, int) or isinstance(value.value, bool):
            continue
        found.update(
            target.id for target in targets
            if isinstance(target, ast.Name) and target.id.isupper()
        )
    return found


def _changed_lines(base_ref: str) -> set[int]:
    """Line numbers of `limits.py` the branch touches, against the merge base.

    The merge base rather than the ref itself, so a branch that is simply
    behind `main` does not report every ceiling somebody else moved.
    """
    base = _git("merge-base", base_ref, "HEAD").strip()
    diff = _git("diff", "--unified=0", base, "--", LIMITS_REL)
    changed: set[int] = set()
    for line in diff.splitlines():
        header = re.match(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if header is None:
            continue
        start = int(header.group(1))
        count = int(header.group(2) or "1")
        changed.update(range(start, start + count))
    return changed


def _mutate(source: str, name: str, line_number: int, delta: int) -> tuple[str, int, int]:
    """`source` with one ceiling moved by `delta`, plus the old and new values."""
    lines = source.splitlines(keepends=True)
    match = _DECLARATION.match(lines[line_number - 1].rstrip("\r\n"))
    if match is None or match.group("name") != name:
        raise SystemExit(f"{name} is not declared on line {line_number}; refusing to guess")

    old = int(match.group("value").replace("_", ""))
    new = old + delta
    lines[line_number - 1] = f"{name}{match.group('gap')}{new}\n"
    mutated = "".join(lines)
    if mutated == source:
        raise SystemExit(f"mutating {name} by {delta:+d} changed nothing")
    return mutated, old, new


def _restore(original: bytes) -> None:
    """Write the original bytes back, then read them again to prove it took.

    Bytes rather than text, so a checkout with any line ending is returned
    exactly as it was found. The `finally` that calls this covers a failing
    sweep and a Ctrl-C; SIGTERM is the one case it does not, and that leaves
    the last mutant on disk.
    """
    LIMITS.write_bytes(original)
    if LIMITS.read_bytes() != original:
        raise SystemExit(
            f"{LIMITS_REL} does not match what was read; restore it by hand before committing"
        )


def _suite_kills_it() -> bool:
    """Whether the suite fails against whatever is currently on disk."""
    # There is no `-x` because under xdist it aborts the session, so a killed
    # mutant exits 2 and so does a collection error. A whole run costs about 40
    # seconds and keeps the verdict to pytest's own exit codes.
    done = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            *[flag for name in _DESELECTS for flag in ("--deselect", name)],
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if done.returncode not in (0, _TESTS_FAILED):
        # A collection or usage error is non-zero and is not a kill, so the run
        # stops here rather than reporting a broken suite as an enforced ceiling.
        tail = "\n".join((done.stdout + done.stderr).splitlines()[-20:])
        raise SystemExit(
            f"pytest exited {done.returncode}, which is not a verdict:\n{_ascii(tail)}"
        )
    return done.returncode == _TESTS_FAILED


def _sweep(names: list[str], source: str, declarations: dict[str, int]) -> list[str]:
    """Mutate each name up and down, printing every verdict; return survivors."""
    survivors: list[str] = []
    for name in names:
        for delta in (+1, -1):
            mutated, old, new = _mutate(source, name, declarations[name], delta)
            LIMITS.write_bytes(mutated.encode("utf-8"))
            killed = _suite_kills_it()
            verdict = "killed" if killed else "SURVIVED"
            print(f"{name}: {old} -> {new} ({delta:+d}): {verdict}")
            if not killed:
                survivors.append(f"{name} {delta:+d} ({old} -> {new})")
    return survivors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref", default="origin/main",
        help="the ref this branch is measured against (default: origin/main)",
    )
    parser.add_argument(
        "--constant", action="append", dest="constants", metavar="NAME",
        help="sweep this constant instead of the ones the diff touches; repeatable",
    )
    args = parser.parse_args()

    original = LIMITS.read_bytes()
    source = original.decode("utf-8")
    declarations = _declarations(source)
    if not declarations:
        raise SystemExit(f"no ceilings found in {LIMITS_REL}, so this sweep proves nothing")
    unswept = sorted(_integer_constants(source) - set(declarations))
    if unswept:
        raise SystemExit(
            f"{LIMITS_REL} declares these in a shape this sweep cannot rewrite, so it "
            f"would skip them and still report success: {', '.join(unswept)}"
        )

    if args.constants:
        unknown = sorted(set(args.constants) - set(declarations))
        if unknown:
            raise SystemExit(f"not declared in {LIMITS_REL}: {', '.join(unknown)}")
        names = sorted(set(args.constants))
    else:
        touched = _changed_lines(args.base_ref)
        names = sorted(n for n, line in declarations.items() if line in touched)
        if not names:
            print(f"No ceiling declaration changed against {args.base_ref}; nothing to mutate.")
            return 0

    print(f"Mutating {len(names)} ceiling(s): {', '.join(names)}")
    try:
        survivors = _sweep(names, source, declarations)
    finally:
        # NEVER `git checkout --`, which has wiped uncommitted work in this repository.
        _restore(original)

    if survivors:
        print()
        print("Survivors, meaning the suite cannot see these ceilings move:")
        for survivor in survivors:
            print(f"  {survivor}")
        print("Give each one a test that exercises its boundary, or record why it has none.")
        return 1

    print(f"All {2 * len(names)} mutants killed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
