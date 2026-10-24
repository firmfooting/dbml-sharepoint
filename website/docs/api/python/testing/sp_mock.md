---
title: sp_mock
sidebar_position: 64
---

# `dbml_sharepoint.testing.sp_mock`

*the SharePoint mock prelude a script runs against*

Make every mock GET answer only what its `$select` asked for (#574).

A live site returns the properties a request selects and nothing else. A mock
that hands back every property it holds lets a script read one it never
selected, and that read passes here and gets `undefined` on a tenant. The
two defects #574 found this way both only showed on an idempotent re-run,
where a drift check compared `undefined` with the declared value and wrote
on every run.

`PRELUDE` is loaded ahead of every script `run_node` executes. It turns
`globalThis.fetch` into an accessor, so every harness and every sabotage
wrapper that assigns it is wrapped without editing any test module. Only the
outermost call (the one the script made) is projected: a wrapper calling the
fetch beneath it runs in an AsyncLocalStorage context that passes responses
through untouched, so a harness still sees its own full rows.

A nested GET, such as a `$batch` part the batch mock redispatches, has only
its `text()` projected, since that is the body a batch envelope carries.

Projection follows the spike measured in #574: decode `$select`; keep the
first segment of each selected name, every `$expand` name, `__metadata` and
`odata.*` or `@odata.*` annotations; ignore case; pass `*` through; apply to a
verbose `d`, `d.results[]`, `value[]`, and a bare entity answered to an
`odata=nometadata` Accept (#634). Error answers and requests with no `$select`,
which includes every single-property read, are left alone.

The tripwire does not throw inside the script, because a script's own
try/catch could swallow it and the test would pass. Each projected row is a
Proxy that RECORDS a read of a PascalCase property that was neither selected
nor assigned by the script; camelCase names are the script's own. At exit the
prelude prints the record after `SENTINEL`, and `run_node` fails the test
naming the property, the request URL and the script line that read it.

A GET of one entity that a harness answers with an empty set is answered
instead with the status SharePoint was measured giving an absent entity of
that kind: 404 for a list or a site group, the absent-400 for a field or view
by name. Other kinds, an item by id among them, keep the harness's answer
until one is measured. An empty set is never an entity, and a catch-all that
answered one made "absent" and "present with nothing in it" the same
observation (#574).

### `SENTINEL`

```python
SENTINEL = '__DBMLSP_UNSELECTED_READS__'
```

### `UnselectedRead`

```python
@dataclass(frozen=True)
class UnselectedRead:
    prop: str
    url: str
    line: int | None
    source: str
```

One read of a property the request that produced the row never selected.

### `UnselectedReadError`

A script read a SharePoint property its request did not `$select`.

### `unselected_reads`

```python
def unselected_reads(output: str) -> list[UnselectedRead]
```

The reads the prelude recorded in `output`, or `[]` when it recorded none.

### `PRELUDE`

```python
PRELUDE = '\n\'use strict\';\n(() => {\n  const SENTINEL = \'__DBMLSP_UNSELECTED_READS__\';\n  const fs = require(\'node:fs\');\n  const { AsyncLocalStorage } = require(\'node:async_hooks\');\n  const inner = n…
```

