---
title: Testing
sidebar_position: 3
---

# The test suite

`uv run pytest` reports around 1,300 tests. That number looks alarming and is
mostly an artefact of how it is counted. This page records what is actually
there, why none of it is trimmed, and where the real maintenance cost sits —
so the next person to look at the number does not have to re-derive it.

## What the number is

| | Count |
|---|---|
| Collected cases | 1,293 |
| **Distinct test functions** | **838** |
| Extra cases from parametrisation | 455 |

The gap is concentrated in one file. `test_template_standard.py` is **22
functions producing 399 cases**, because thirteen of them are parametrised
across the whole template library. That is 22 conformance rules applied to 30
templates, not 399 things anyone maintains — and parametrising is what makes a
failure say *which* template drifted instead of "something under `solutions/`
is wrong".

Every other file is close to one case per function: `test_jsgen` 112/112,
`test_reportgen` 37/37, `test_forms` 35/35.

## Why none of it is trimmed

- **Coverage is 95%**, with 17 modules at 100%. There is no dead weight to cut.
- **There are effectively no weak tests.** Every function was walked with an
  AST scan looking for a missing assertion or a lone `is not None`. Two hits,
  one of which uses `pytest.fail` and is fine.
- **The suite is the product.** The failure class this tool exists to close is
  a rule that saves, reads back byte-identical, passes every deploy phase, and
  does nothing on the rendered page. Nothing downstream catches that. These
  tests are the only thing that does.

## Why it all runs every time

Because it costs almost nothing:

| | Time |
|---|---|
| Full suite, local | **~5s** |
| Whole pre-push gate | **~6s** |
| CI tests | 16s (ubuntu) |

Tests are no longer even the largest CI step — `setup-uv` and the two
template-build sweeps each cost more.

Selective running — `pytest-testmon`, `--lf`, per-directory selection — would
save a couple of seconds and reintroduce exactly the risk the suite exists to
remove: a change in `analysis/joins.py` breaking a template conformance rule
nobody thought was related. **A template drifts out of the family precisely
when someone changes something they believed was unrelated.** That is the case
a filtered run misses.

## Parallelism

`-n auto --maxprocesses 8` is in `addopts`. Measured on a 24-core machine:

| Configuration | Wall |
|---|---|
| serial | 17.4s |
| `-n 8` | 6.1s |
| `-n auto` (24 workers) | 6.6s |
| `-n auto --maxprocesses 8` | **4.8s** |

The cap matters: uncapped `auto` is *slower*, because 24 workers spend more on
startup than they save. It is inert on CI runners, which have fewer cores.

Pass **`-n0`** when you need `--pdb`, deterministic ordering, or readable
output from one test:

```bash
uv run pytest -n0 test/test_joins.py
```

## The `conformance` marker

`test_template_standard.py` is marked `conformance`. Skip it for a quieter run
while iterating on something else:

```bash
uv run pytest -m "not conformance"
```

**This is for focus, not speed.** Measured at 4.65s against 4.66s for the full
suite — skipping a third of the cases saves nothing, because `-n auto` already
spreads them across workers and they are not the critical path. CI never
filters.

## Layout

Test modules mirror the *concern*, not the source tree. That distinction is
deliberate and was arrived at by measurement: `test_validator_*.py` calls
`validate_against_mapping` (115×), `validate` (16×) and `validate_all` (3×) —
top-level entry points that run every check. Every test touches every module
under `analysis/checks/`, so splitting the tests to mirror those modules would
have been a fiction. Coverage per section confirms it: no section maps to one
check module.

```
test/
  _paths.py                      where things are, resolved once
  _validator_helpers.py          the seven helpers used by >1 validator module
  test_validator_core.py         shared fixtures, cross-cutting, extension hook
  test_validator_calculated.py   calculated columns, lookup display column
  test_validator_views.py        declared views, display names
  test_validator_formatting.py   column formatting
  test_validator_retirement.py   retired columns
  test_validator_field_sets.py   field sets, the refusals a deploy cannot see
  test_validator_view_totals.py  declared view totals
  test_validator_joins.py        the view join threshold
```

`test_validator.py` was one 4,787-line file. It is the same tests, verbatim, in
eight files of 333–1,039 lines. The split was verified by diffing the full
test-id set before and after (identical) and the coverage totals (identical:
3,663 statements, 183 missing).

### Paths

Never re-derive a path with `Path(__file__).parent.parent` or
`Path(__file__).resolve().parents[1]`. Import from `_paths`:

```python
from _paths import FIXTURES, MANUAL, SOLUTION_TEMPLATES
```

Parent-counting does not fail loudly when a file moves to a different depth —
it resolves somewhere else and the tests break somewhere unrelated. `_paths`
finds the root by searching upward for `pyproject.toml` and raises if it is
absent. Note `JINJA_TEMPLATES` (the `.j2` files the generators render) and
`SOLUTION_TEMPLATES` (the shipped schema + mapping families) are different
directories; both were previously called `TEMPLATES` in different modules.

## The axis that grows

Conformance cases scale as *rules × templates*. At 30 templates that is 399
cases and about 5s. At 100 templates it would be roughly 1,300 cases and ~16s
serial — still fine, but worth knowing that the count grows when a **template**
is added, not when a test is.
