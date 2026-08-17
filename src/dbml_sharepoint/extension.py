# src/dbml_sharepoint/extension.py
"""The deployment-extension protocol: the hook
names, parameter order, and return types; this skeleton conforms to it.
Validation issues are reported with the validator Finding type."""
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

import typer

from dbml_sharepoint.analysis.findings import Finding
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Column, Schema, Table


@dataclass
class SiteContext:
    """Per-build inputs hooks need: site URL, site role, release
    record, output directory, plus extension CLI flag values captured by the
    extension's own CLI entry point (e.g. {"org_unit": "QSC"})."""
    site_url: str
    site_role: str
    release: Any                          # release.Release | None
    output_dir: Path
    extension_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManifestExtras:
    """Extra manifest content from an extension."""
    sections: dict[str, str] = field(default_factory=dict)   # heading -> markdown body
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class DeploymentExtension(Protocol):
    """Project-specific extension to the generic deployer.

    BaseExtension provides no-op defaults for every hook.
    """

    name: ClassVar[str]
    """Identifier used in mapping YAML's `extension:` field and in
    entry-point registration."""

    requires_project_cli: ClassVar[bool]
    """True when the generic build command lacks required project inputs."""

    def extra_validators(
        self, bundle: MappingBundle, schema: Schema,
    ) -> list[Finding]: ...

    def expand_column(
        self, table: Table, column: Column, bundle: MappingBundle,
    ) -> list[dict[str, Any]] | None: ...

    def seed_lists(
        self, bundle: MappingBundle, schema: Schema, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]: ...

    def manifest_extras(
        self, bundle: MappingBundle, schema: Schema,
    ) -> ManifestExtras: ...

    def cli_subcommands(self, app: typer.Typer) -> None: ...


class BaseExtension:
    """No-op defaults for the DeploymentExtension protocol; extensions
    override only what they need."""
    name: ClassVar[str] = "base"
    # Project extensions that require additional CLI arguments must opt out of
    # the generic `dbml-sharepoint build` entry point explicitly. This marker
    # is checked after resolution and before any output directory or artifact
    # is created; inheriting the extension protocol alone is not sufficient
    # evidence that the generic CLI can supply its required context.
    requires_project_cli: ClassVar[bool] = False

    def extra_validators(
        self, bundle: MappingBundle, schema: Schema,
    ) -> list[Finding]:
        return []                         # non-empty errors abort the build

    def expand_column(
        self, table: Table, column: Column, bundle: MappingBundle,
    ) -> list[dict[str, Any]] | None:
        return None                       # None = defer to core's default field emission

    def seed_lists(
        self, bundle: MappingBundle, schema: Schema, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]:
        # SP list title -> field dict, embedded in the deploy script seed
        return {}

    def manifest_extras(
        self, bundle: MappingBundle, schema: Schema,
    ) -> ManifestExtras:
        return ManifestExtras()

    def cli_subcommands(self, app: typer.Typer) -> None:
        """Register wholly-new extension-owned subcommands on the core app.
        Must never alter core command signatures."""
        return


class NullExtension(BaseExtension):
    name: ClassVar[str] = "null"


class UnknownExtensionError(ValueError):
    """The requested extension name is not installed.

    Named so the CLI can report a typo as configuration while a broken
    plugin, whose entry-point load or constructor raises, still reaches
    the operator as a traceback naming the plugin.
    """


def resolve_extension(name: str | None) -> BaseExtension:
    """Resolve by entry-point name; None/'null' -> NullExtension.
    Raises ValueError listing installed extensions when the name is unknown."""
    if name in (None, "", "null"):
        return NullExtension()
    eps = entry_points(group="dbml_sharepoint.extensions")
    for ep in eps:
        if ep.name == name:
            return ep.load()()  # type: ignore[no-any-return]
    installed = sorted(ep.name for ep in eps)
    raise UnknownExtensionError(
        f"Unknown extension {name!r}; installed: {installed or 'none'}"
    )
