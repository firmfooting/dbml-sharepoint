---
title: findings
sidebar_position: 5
---

# `dbml_sharepoint.analysis.findings`

*what a finding is — code, severity, section, location*

What a finding IS, separate from what produces one.

`checks/*` needs the vocabulary without importing the orchestrator, the same
layering rule that already forbids a generator importing from `checks/`.

The `code` is the identity. Everything keys off it: tests, the docs catalogue,
and `--explain`. The `message` is prose for a human and is free to be reworded
in any commit -- before this module existed, 294 test assertions matched
substrings of it, so it could not be.

### `Section`

The mapping section a finding is about.

These eighteen names were already being spelled into message prefixes by
hand at 175 sites; this makes the set closed and the spelling checked.

### `Location`

```python
@dataclass(frozen=True)
class Location:
    section: Section
    entity: str | None = None
    column: str | None = None
    view: str | None = None
    sub: str | None = None
```

Where a finding is, as data rather than as a rendered prefix.

### `FindingCode`

One member per rule. The catalogue of everything this tool can say.

Adding a rule means adding a member here and a row in
`website/docs/reference/findings.md`; `test_every_code_is_documented`
enforces the pair.

### `Finding`

```python
@dataclass(frozen=True)
class Finding:
    code: FindingCode
    severity: Severity
    message: str
    location: dbml_sharepoint.analysis.findings.Location | None = None
```

One thing the build has to say about the declaration it was given.

