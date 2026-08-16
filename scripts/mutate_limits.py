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

MEASURED 2026-08-16, and the reason `_DESELECTS` deselects two currency tests.
A page generated from `limits.py` carries the values verbatim, so its currency
test regenerates the page from the mutated source and fails on every mutant
whether or not a behavioural consumer exists. Both directions of each pair
below were run:

    MAX_FIELD_DESCRIPTION  survives, and reports killed with the API-docs
                           deselect removed
    MAX_VIEW_ROW_LIMIT     survives, and reports killed with the findings
                           deselect removed
    MAX_DISPLAY_TITLE      killed, with every deselect in place

A kill for the first two is the wrong answer, and leaving the API-docs test in
is how the first run of the #259 sweep reported 28 kills and established
nothing. The findings page is the same defect found here rather than in #259:
`finding_help.py` interpolates seven constants into its prose, so that sweep's
recorded kills for INDEX_WARN_AT, LIST_VIEW_THRESHOLD, MAX_LIST_INDEXES,
MAX_VALIDATION_FORMULA, MAX_VALIDATION_MESSAGE and MAX_VIEW_ROW_LIMIT are not
evidence of enforcement. MAX_DISPLAY_TITLE is the seventh and is killed by its
own boundary tests, so its result stands.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIMITS = REPO_ROOT / "src" / "dbml_sharepoint" / "analysis" / "limits.py"
LIMITS_REL = "src/dbml_sharepoint/analysis/limits.py"

#: The tests the sweep runs without, which are not all the same kind of thing.
_DESELECTS = (
    # THE POINT OF THE RUN. This test regenerates the API page from the mutated
    # source and fails on every mutant, so leaving it in reports a kill for a
    # ceiling nothing enforces. See the measurement in the module docstring.
    "test/test_template_lint.py::test_generated_api_docs_are_current",
    # The same defect on a second generated page. `finding_help.py` interpolates
    # seven of these constants into its prose, so this test fails on any mutant
    # of those seven whether or not a rule enforces them. MEASURED 2026-08-16:
    # with this line absent, MAX_VIEW_ROW_LIMIT reports killed in both
    # directions, and with it present it survives in both.
    "test/test_finding_help.py::test_generated_findings_page_is_current",
    # Different reason, and safe: this is only about the 180-second runtime
    # timeout. Dropping tests makes a mutant HARDER to kill, so it can hide a
    # kill but it cannot manufacture one.
    "test/test_deploy_runtime.py",
)

#: A ceiling declaration, which is one name and one integer on one line.
_DECLARATION = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)(?P<gap>\s*=\s*)(?P<value>[0-9_]+)\s*$")

#: pytest's exit code for "tests ran and something failed", which is the only
#: non-zero code that means the mutant was killed rather than the run broke.
_TESTS_FAILED = 1


def _git(*args: str) -> str:
    """Run git in the repository and return its stdout."""
    done = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return done.stdout


def _declarations(source: str) -> dict[str, int]:
    """Every constant `limits.py` declares, mapped to its 1-based line number."""
    found: dict[str, int] = {}
    for number, line in enumerate(source.splitlines(), start=1):
        match = _DECLARATION.match(line)
        if match is not None:
            found[match.group("name")] = number
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


def _suite_kills_it() -> bool:
    """Whether the suite fails against whatever is currently on disk."""
    # No `-x`. Under xdist it aborts the session, so a killed mutant exits 2
    # (interrupted), which a collection error exits with too. Whole runs cost
    # about 40 seconds and keep the verdict to pytest's own exit codes.
    done = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            *[flag for name in _DESELECTS for flag in ("--deselect", name)],
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if done.returncode not in (0, _TESTS_FAILED):
        # A collection or usage error is non-zero and is NOT a kill. Reporting
        # it as one would turn a broken run into a clean bill of health.
        tail = "\n".join((done.stdout + done.stderr).splitlines()[-20:])
        # Forced to ASCII: a Windows console is cp1252 and would turn a
        # diagnostic into a UnicodeEncodeError from somewhere else entirely.
        tail = tail.encode("ascii", "replace").decode("ascii")
        raise SystemExit(f"pytest exited {done.returncode}, which is not a verdict:\n{tail}")
    return done.returncode == _TESTS_FAILED


def _sweep(names: list[str], source: str, declarations: dict[str, int]) -> list[str]:
    """Mutate each name up and down, printing every verdict; return survivors."""
    survivors: list[str] = []
    for name in names:
        for delta in (+1, -1):
            mutated, old, new = _mutate(source, name, declarations[name], delta)
            LIMITS.write_text(mutated, encoding="utf-8", newline="\n")
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

    source = LIMITS.read_text(encoding="utf-8")
    declarations = _declarations(source)
    if not declarations:
        raise SystemExit(f"no ceilings found in {LIMITS_REL}, so this sweep proves nothing")

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
        # Restore from the bytes read at the start. NEVER `git checkout --`,
        # which has wiped uncommitted work in this repository.
        LIMITS.write_text(source, encoding="utf-8", newline="\n")

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
