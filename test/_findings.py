"""Assert on what a finding IS, not on how it happens to be worded.

Before findings had codes, 294 assertions matched substrings of human prose.
That is how a test comes to pass while asserting nothing: the deleted `_named`
helper's docstring recorded two of its own assertions that could never fail,
because the sentence they searched contained the word either way.

A message is for a person and may be reworded in any commit. The code is the
identity. Assert on the code, and on the structured `location`; keep a
substring check only where the test cares that a particular VALUE reached the
reader.
"""

from collections.abc import Iterable

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Severity


def codes(findings: Iterable[Finding]) -> set[FindingCode]:
    """Every distinct code in `findings`."""
    return {f.code for f in findings}


def only(findings: Iterable[Finding], code: FindingCode) -> Finding:
    """The one finding carrying `code`, asserting there is exactly one.

    The failure message names what WAS found. `assert len(found) == 1` tells
    you a count and nothing else, and the count is never the interesting part
    — the interesting part is which rule fired instead.
    """
    items = list(findings)
    found = [f for f in items if f.code == code]
    assert len(found) == 1, (
        f"expected exactly one {code}, got {len(found)}. "
        f"Findings present: {', '.join(sorted(str(f.code) for f in items)) or '<none>'}"
    )
    return found[0]


def none_of(findings: Iterable[Finding], code: FindingCode) -> None:
    """Assert `code` is absent, naming what is present if it is not.

    The counterpart to `only`, for the many tests that assert a declaration is
    accepted. `assert findings == []` is a stronger claim than most of them
    mean and breaks whenever an unrelated rule starts firing on the fixture.
    """
    hit = [f for f in findings if f.code == code]
    assert not hit, f"expected no {code}, got {len(hit)}: {[f.message for f in hit]}"


def messages(findings: Iterable[Finding], code: FindingCode) -> list[str]:
    """The messages of every finding carrying `code`.

    For the tests that legitimately care about a value in the prose — a column
    name the reader needs, a limit the message quotes. Reach for `only` first.
    """
    return [f.message for f in findings if f.code == code]


def by_severity(findings: Iterable[Finding], severity: Severity) -> list[Finding]:
    """Findings of one severity, replacing the `if f.severity == ...` filter
    spelled out at well over a hundred call sites."""
    return [f for f in findings if f.severity == severity]
