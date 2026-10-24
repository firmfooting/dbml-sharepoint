---
title: node
sidebar_position: 63
---

# `dbml_sharepoint.testing.node`

*run an emitted script under node behind the SharePoint mock*

Execute a generated browser script under Node.

Shared by the runtime tests of this package and of its dependents. A
golden-file comparison proves a generated script does not CHANGE; only running
it proves it RUNS, and the emitted scripts are the artefacts operators paste
into production sites.

Node is required; every caller skips without it rather than failing, since
it is not a dependency of the package. That skip is a LOCAL convenience
only: `dbml_sharepoint.testing.plugin` refuses a run under CI with node
missing, because a skip there would retire the whole executed-script suite
without turning anything red.

### `NODE`

```python
NODE = shutil.which('node')
```

### `run_node`

```python
def run_node(script: str) -> str
```

Run `script` under Node and return stdout+stderr.

    Via a FILE, never `node -e`: deploy.js is far past the Windows
    command-line limit.

    `newline="
"` is a DELIBERATE behaviour change made when this moved out
    of test_deploy_runtime.py, not part of the move. The previous spelling
    let `write_text` translate on Windows, so the deploy tests were running a
    CRLF copy of a script the generator emits as LF -- the artefact under
    test was not the artefact that ships. This makes Node parse the emitted
    bytes. Kept on review; see AGENTS.md on generated files and LF.

    Every script runs behind `sp_mock.PRELUDE`, which projects each mock GET
    to its `$select`; a read of a property the request never selected raises
    `UnselectedReadError` here rather than passing on `undefined` (#574). It
    also answers an empty set returned for a single entity with the absent
    status SharePoint gives that entity.
    

