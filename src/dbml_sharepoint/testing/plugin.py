# src/dbml_sharepoint/testing/plugin.py
"""Node is optional locally and mandatory in CI.

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
"""

import os

import pytest

from dbml_sharepoint.testing import node


def node_is_required() -> bool:
    """Whether a missing node should fail the run rather than skip it."""
    return bool(os.environ.get("CI"))


def pytest_configure(config: pytest.Config) -> None:
    """Register `requires_node`, so `--strict-markers` accepts it."""
    config.addinivalue_line(
        "markers", "requires_node: executes a script under node; skipped locally without it",
    )


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item],
) -> None:
    """Refuse a CI run that would silently skip every executed-script test."""
    del session, config
    # Read at run time, so a monkeypatched `node.NODE` is the one checked.
    if node.NODE is not None:
        return
    if node_is_required():
        message = (
            "node is not on PATH and CI is set. The runtime tests execute every "
            "emitted script against a mock web, and they skip without node, so "
            "this run would report green having tested none of them. Install "
            "node (in GitHub Actions, pin it with actions/setup-node) or unset CI."
        )
        raise pytest.UsageError(message)
    skip = pytest.mark.skip(reason="node is not on PATH")
    for item in items:
        if item.get_closest_marker("requires_node") is not None:
            item.add_marker(skip)
