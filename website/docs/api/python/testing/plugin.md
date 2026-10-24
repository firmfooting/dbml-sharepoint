---
title: plugin
sidebar_position: 65
---

# `dbml_sharepoint.testing.plugin`

*the pytest plugin: node optional locally, required in CI*

Node is optional locally and mandatory in CI.

An emitted script is executed against a mock web because a golden comparison
proves a script did not change, and only running it proves it runs. Those
tests skip without node, which is right on a contributor's machine and wrong
on a runner: a skip is green, so an image that stopped shipping node would
retire the whole executed-script suite without turning anything red.

The requirement is keyed on `CI`, which every CI provider sets and a
contributor never does. Loading is opt-in, through
`pytest_plugins = ["dbml_sharepoint.testing.plugin"]` in a conftest, and never
a `pytest11` entry point, so installing or upgrading this package cannot
change another project's test run uninvited.

### `node_is_required`

```python
def node_is_required() -> bool
```

Whether a missing node should fail the run rather than skip it.

### `pytest_configure`

```python
def pytest_configure(config: pytest.Config) -> None
```

Register `requires_node`, so `--strict-markers` accepts it.

### `pytest_collection_modifyitems`

```python
def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None
```

Refuse a CI run that would silently skip every executed-script test.

