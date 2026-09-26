# test/test_extension.py
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Any, ClassVar

import pytest
import typer
from _model import bundle as make_bundle
from _model import column as make_column
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.findings import Finding
from dbml_sharepoint.extension import (
    BaseExtension,
    DeploymentExtension,
    ManifestExtras,
    NullExtension,
    SiteContext,
    resolve_extension,
)
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Column, Schema, Table


def _schema() -> Schema:
    return make_schema(make_table("Risk", "Title"))


def _site_context() -> SiteContext:
    return SiteContext(
        site_url="https://contoso.sharepoint.com/sites/test",
        site_role="default",
        release=None,
        output_dir=Path("./build"),
    )


def test_null_extension_extra_validators_is_empty() -> None:
    ext = NullExtension()
    assert ext.extra_validators(bundle=make_bundle(entities=["Risk"]), schema=_schema()) == []


def test_null_extension_expand_column_defers() -> None:
    ext = NullExtension()
    result = ext.expand_column(
        table=make_table("Risk", "Title"),
        column=make_column("Title"),
        bundle=make_bundle(entities=["Risk"]),
    )
    assert result is None


def test_null_extension_seed_lists_is_empty_dict() -> None:
    ext = NullExtension()
    result = ext.seed_lists(
        bundle=make_bundle(entities=["Risk"]),
        schema=_schema(),
        site_context=_site_context(),
    )
    assert result == {}


def test_null_extension_manifest_extras_is_empty() -> None:
    ext = NullExtension()
    extras = ext.manifest_extras(bundle=make_bundle(entities=["Risk"]), schema=_schema())
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
    bundle = make_bundle(entities=["Risk"])
    schema = _schema()
    assert ext.extra_validators(bundle=bundle, schema=schema) == []
    assert ext.expand_column(
        table=make_table("Risk", "Title"), column=make_column("Title"), bundle=bundle,
    ) is None
    assert ext.seed_lists(bundle=bundle, schema=schema, site_context=_site_context()) == {}
    assert ext.manifest_extras(bundle=bundle, schema=schema) == ManifestExtras()
    ext.cli_subcommands(typer.Typer())  # -> None by protocol
    assert BaseExtension.name == "base"


def test_base_extension_satisfies_deployment_extension_protocol() -> None:
    # Typed assignment: the type checker verifies BaseExtension structurally
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


def _installed(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """One real entry point named `acme`, loaded from `value`."""
    point = EntryPoint(name="acme", value=value, group="dbml_sharepoint.extensions")

    def only_acme(*, group: str) -> list[EntryPoint]:
        return [point] if group == "dbml_sharepoint.extensions" else []

    monkeypatch.setattr("dbml_sharepoint.extension.entry_points", only_acme)


def test_resolve_extension_refuses_a_plugin_that_builds_something_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An entry point is untyped, so a plugin building a dict must not pass as an extension."""
    _installed(monkeypatch, "builtins:dict")
    with pytest.raises(TypeError, match=r"'acme' \(builtins:dict\) built a dict"):
        resolve_extension("acme")


def test_resolve_extension_returns_the_extension_a_plugin_builds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(monkeypatch, "dbml_sharepoint.extension:NullExtension")
    assert isinstance(resolve_extension("acme"), NullExtension)


class ProtocolOnlyExtension:
    """Every DeploymentExtension member, and no BaseExtension ancestry."""

    name: ClassVar[str] = "acme"
    requires_project_cli: ClassVar[bool] = False

    def extra_validators(self, bundle: MappingBundle, schema: Schema) -> list[Finding]:
        return []

    def expand_column(
        self, table: Table, column: Column, bundle: MappingBundle,
    ) -> list[dict[str, Any]] | None:
        return None

    def seed_lists(
        self, bundle: MappingBundle, schema: Schema, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]:
        return {}

    def manifest_extras(self, bundle: MappingBundle, schema: Schema) -> ManifestExtras:
        return ManifestExtras()

    def cli_subcommands(self, app: typer.Typer) -> None:
        return


def test_resolve_extension_accepts_a_plugin_that_implements_the_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The architecture page tells a plugin to implement DeploymentExtension, not to subclass."""
    _installed(monkeypatch, f"{__name__}:ProtocolOnlyExtension")
    assert type(resolve_extension("acme")).__name__ == "ProtocolOnlyExtension"


def test_resolve_extension_unknown_message_mentions_requested_name() -> None:
    with pytest.raises(ValueError, match="nope"):
        resolve_extension("nope")
