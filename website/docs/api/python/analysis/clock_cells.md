---
title: clock_cells
sidebar_position: 25
---

# `dbml_sharepoint.analysis.clock_cells`

*every clock cell, with its evidence or its refusal*

Every clock cell the renderer can meet, with its evidence or its refusal.

A clock cell is one sentinel (`today`, `today+N or today-N`, `now`) on one kind of date
column (`date`, `datetime`, `calculated_date`) for one condition target (a
validation formula, a CAML view filter, a client-side expression). Each cell
is declared here as one of:

- ``measured``: emitted, and a named live run observed the rendering behave;
- ``unmeasured``: emitted, and nothing has observed it (the ratchet in
  `test/test_clock_cells.py` lists these with a reason each);
- ``clock``: emitted, and it reads the formula clock that was measured 16 to
  20 hours behind the site on 2026-09-02, which the validator warns about;
- ``refused``: the renderer raises, and the validator reports the finding.

The renderer does not read this table. The test renders a canonical leaf per
cell through the public renderers and holds them to what is declared here,
so a rendering cannot change without its evidence changing with it. The
scope is the three condition targets; the `[today]` column default is not a
condition and its evidence is `DEFAULT_EVIDENCE`, for the verification
artifact.

### `SENTINELS`

```python
SENTINELS = ('today', 'today_offset', 'now')
```

### `COLUMN_KINDS`

```python
COLUMN_KINDS = ('calculated_date', 'date', 'datetime')
```

### `TARGETS`

```python
TARGETS = ('validation', 'caml', 'expression')
```

### `Evidence`

```python
@dataclass(frozen=True)
class Evidence:
    probe: str
    measured: str
    zone: str
    note: str
```

One live run: the repo file that records it, when, and on which site.

### `ClockCell`

```python
@dataclass(frozen=True)
class ClockCell:
    sentinel: Sentinel
    column_kind: str
    target: str
    status: Status
    renderings: Mapping[Any, str] = field(default_factory=dict)
    evidence: Evidence | None = None
    refusal: ConditionRefusalKind | None = None
```

ClockCell(sentinel: 'Sentinel', column_kind: 'str', target: 'str', status: 'Status', renderings: 'Mapping[Any, str]' = &lt;factory>, evidence: 'Evidence | None' = None, refusal: 'ConditionRefusalKind | None' = None)

### `sentinel_of`

```python
def sentinel_of(value: 'object', column_type: 'str') -> 'Sentinel | None'
```

Which clock sentinel a leaf value is, on a date-ish column; else None.

### `cell_for`

```python
def cell_for(sentinel: 'str', column_kind: 'str', target: 'str') -> 'ClockCell'
```

### `DEFAULT_EVIDENCE`

```python
DEFAULT_EVIDENCE = Evidence(probe='src/dbml_sharepoint/analysis/save_rules.py', measured='2026-09-02', zone='AUS Eastern (UTC+10)', note="the modern form prefilled the site's date; a REST create with the column omitted …
```

### `CELLS`

```python
CELLS = (ClockCell(sentinel='today', column_kind='date', target='validation', status='measured', renderings={('leq', 'today'): '[D]<=[Modified]', ('lt', 'today'): '[D]+1<=[Modified]', ('gt', 'today'): '[D]>[M…
```

