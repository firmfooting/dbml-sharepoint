# test/test_extension.py
from pathlib import Path

import pytest
import typer

from dbml_sharepoint.extension import (
    BaseExtension,
    DeploymentExtension,
    ManifestExtras,
    NullExtension,
    SiteContext,
    resolve_extension,
)


def _site_context() -> SiteContext:
    return SiteContext(
        site_url="https://contoso.sharepoint.com/sites/test",
        site_role="default",
        release=None,
        output_dir=Path("./build"),
    )


def test_null_extension_extra_validators_is_empty() -> None:
    ext = NullExtension()
    assert ext.extra_validators(bundle="bundle", schema="schema") == []


def test_null_extension_expand_column_defers() -> None:
    ext = NullExtension()
    assert ext.expand_column(table="table", column="column", bundle="bundle") is None


def test_null_extension_seed_lists_is_empty_dict() -> None:
    ext = NullExtension()
    result = ext.seed_lists(bundle="bundle", schema="schema", site_context=_site_context())
    assert result == {}


def test_null_extension_manifest_extras_is_empty() -> None:
    ext = NullExtension()
    extras = ext.manifest_extras(bundle="bundle", schema="schema")
    assert extras == ManifestExtras(sections={}, warnings=[])


def test_null_extension_cli_subcommands_is_noop() -> None:
    ext = NullExtension()
    app = typer.Typer()
    ext.cli_subcommands(app)  # -> None by protocol; must not register anything
    assert app.registered_commands == []


def test_null_extension_name() -> None:
    assert NullExtension.name == "null"


def test_base_extension_hooks_match_null_defaults() -> None:
    # BaseExtension itself carries the same no-op defaults NullExtension inherits.
    ext = BaseExtension()
    assert ext.extra_validators(bundle="b", schema="s") == []
    assert ext.expand_column(table="t", column="c", bundle="b") is None
    assert ext.seed_lists(bundle="b", schema="s", site_context=_site_context()) == {}
    assert ext.manifest_extras(bundle="b", schema="s") == ManifestExtras()
    ext.cli_subcommands(typer.Typer())  # -> None by protocol
    assert BaseExtension.name == "base"


def test_base_extension_satisfies_deployment_extension_protocol() -> None:
    # Typed assignment: mypy --strict verifies BaseExtension structurally
    # implements the DeploymentExtension protocol (five hooks + name ClassVar).
    ext: DeploymentExtension = BaseExtension()
    # Runtime check via @runtime_checkable.
    assert isinstance(ext, DeploymentExtension)


def test_null_extension_satisfies_deployment_extension_protocol() -> None:
    ext: DeploymentExtension = NullExtension()
    assert isinstance(ext, DeploymentExtension)


@pytest.mark.parametrize("name", [None, "null"])
def test_resolve_extension_null_cases(name: str | None) -> None:
    ext = resolve_extension(name)
    assert isinstance(ext, NullExtension)


def test_resolve_extension_empty_string_is_null() -> None:
    ext = resolve_extension("")
    assert isinstance(ext, NullExtension)


def test_resolve_extension_unknown_raises_with_installed_list() -> None:
    with pytest.raises(ValueError, match="installed:"):
        resolve_extension("nope")


def test_resolve_extension_unknown_message_mentions_requested_name() -> None:
    with pytest.raises(ValueError, match="nope"):
        resolve_extension("nope")
