# test/test_markdownlint_version.py
"""One gate: the markdownlint pinned for the hook is the one CI runs.

Every other lint gate in this repository is pinned once, in pyproject.toml,
and both the prek hook and the CI step reach it through `uv run` -- which is
why `.pre-commit-config.yaml` can claim "a hook can never drift from the
version CI uses". markdownlint-cli2 is a node package, so it breaks that
arrangement: the version lives in the hook's `rev:` and again in the CI step's
`npx markdownlint-cli2@...`.

Two copies of a number drift, and this pair drifts SILENTLY -- both sides keep
working, they just enforce different rulesets, and the symptom is a commit that
passes locally and fails in CI (or the reverse) for no visible reason. So the
number is asserted rather than remembered.
"""

import re

from _paths import REPO_ROOT

HOOK_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: The `rev:` on the line after the markdownlint-cli2 repo. Anchored to that
#: repo URL so it cannot accidentally read the rev of a neighbouring hook.
HOOK_REV = re.compile(
    r"repo:\s*https://github\.com/DavidAnson/markdownlint-cli2\s*\n\s*rev:\s*v?(\S+)"
)

#: The npx invocation. `@` then the version, stopping at whitespace or a
#: quote so the trailing glob argument is not swallowed.
#:
#: Spelled as an explicit character class rather than `(\S+?)\b`, which looks
#: right and reads "0" out of "0.23.2" -- there is a word boundary before the
#: dot. `test_the_gate_would_catch_a_drifted_pin` caught that on first run.
CI_PIN = re.compile(r"markdownlint-cli2@v?([0-9][^\s\"']*)")


def test_the_hook_and_ci_pin_the_same_markdownlint() -> None:
    """The two copies of the version must agree."""
    hook = HOOK_REV.search(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert hook, (
        f"no markdownlint-cli2 `rev:` found in {HOOK_CONFIG.name}. If the hook "
        "was removed on purpose, remove the CI step and this test with it."
    )

    ci = CI_PIN.findall(WORKFLOW.read_text(encoding="utf-8"))
    assert ci, (
        f"no `markdownlint-cli2@<version>` found in {WORKFLOW.name}. The hook "
        "still pins one, so markdown is linted locally and not in CI."
    )

    mismatched = sorted({version for version in ci if version != hook.group(1)})
    assert not mismatched, (
        f"{HOOK_CONFIG.name} pins markdownlint-cli2 {hook.group(1)} but "
        f"{WORKFLOW.name} runs {', '.join(mismatched)}. Bump both together: a "
        "hook and a CI step enforcing different rulesets fail each other's "
        "commits for reasons neither log explains."
    )


def test_the_gate_would_catch_a_drifted_pin() -> None:
    """The complement, so the rule above cannot pass by matching nothing.

    A regex that stopped matching would make the assertions above vacuous and
    permanently green -- the same silent drift the gate exists to refuse.
    """
    found = HOOK_REV.search(
        "  - repo: https://github.com/DavidAnson/markdownlint-cli2\n    rev: v0.23.2\n"
    )
    assert found is not None
    assert found.group(1) == "0.23.2"

    # A different repo's rev must not be mistaken for this one's.
    assert not HOOK_REV.search(
        "  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v6.0.0\n"
    )

    assert CI_PIN.findall('run: npx --yes markdownlint-cli2@0.23.2 "**/*.md"') == [
        "0.23.2"
    ]
    # And the bare name, with no version, is not a pin.
    assert CI_PIN.findall("run: npx markdownlint-cli2") == []
