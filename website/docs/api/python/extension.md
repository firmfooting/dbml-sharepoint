---
title: extension
sidebar_position: 51
---

# `dbml_sharepoint.extension`

*Packaging: the extension protocol*

The deployment-extension protocol: the hook
names, parameter order, and return types; this skeleton conforms to it.
Validation issues are reported with `analysis.findings.Finding`.

### `SiteContext`

```python
@dataclass
class SiteContext:
    site_url: str
    site_role: str
    release: dbml_sharepoint.model.release.Release | None
    output_dir: Path
    extension_args: dict[str, dbml_sharepoint.jsonvalue.JsonValue] = field(default_factory=dict)
```

Per-build inputs hooks need: site URL, site role, release
record, output directory, plus extension CLI flag values captured by the
extension's own CLI entry point (e.g. {"org_unit": "QSC"}).

### `ManifestExtras`

```python
@dataclass
class ManifestExtras:
    sections: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
```

Extra manifest content from an extension.

### `DeploymentExtension`

Project-specific extension to the generic deployer.

BaseExtension provides no-op defaults for every hook.

#### `DeploymentExtension.cli_subcommands`

```python
def cli_subcommands(self, app: typer.Typer) -> None
```

#### `DeploymentExtension.expand_column`

```python
def expand_column(self, table: Table, column: Column, bundle: MappingBundle) -> list[dict[str, JsonValue]] | None
```

#### `DeploymentExtension.extra_validators`

```python
def extra_validators(self, bundle: MappingBundle, schema: Schema) -> list[Finding]
```

#### `DeploymentExtension.manifest_extras`

```python
def manifest_extras(self, bundle: MappingBundle, schema: Schema) -> ManifestExtras
```

#### `DeploymentExtension.seed_lists`

```python
def seed_lists(self, bundle: MappingBundle, schema: Schema, site_context: SiteContext) -> dict[str, dict[str, JsonValue]]
```

### `BaseExtension`

No-op defaults for the DeploymentExtension protocol; extensions
override only what they need.

#### `BaseExtension.cli_subcommands`

```python
def cli_subcommands(self, app: typer.Typer) -> None
```

Register wholly-new extension-owned subcommands on the core app.
Must never alter core command signatures.

#### `BaseExtension.expand_column`

```python
def expand_column(self, table: Table, column: Column, bundle: MappingBundle) -> list[dict[str, JsonValue]] | None
```

#### `BaseExtension.extra_validators`

```python
def extra_validators(self, bundle: MappingBundle, schema: Schema) -> list[Finding]
```

#### `BaseExtension.manifest_extras`

```python
def manifest_extras(self, bundle: MappingBundle, schema: Schema) -> ManifestExtras
```

#### `BaseExtension.seed_lists`

```python
def seed_lists(self, bundle: MappingBundle, schema: Schema, site_context: SiteContext) -> dict[str, dict[str, JsonValue]]
```

### `NullExtension`

No-op defaults for the DeploymentExtension protocol; extensions
override only what they need.

### `UnknownExtensionError`

The requested extension name is not installed.

Named so the CLI can report a typo as configuration while a broken
plugin, whose entry-point load or constructor raises, still reaches
the operator as a traceback naming the plugin.

### `resolve_extension`

```python
def resolve_extension(name: str | None) -> DeploymentExtension
```

Resolve by entry-point name; None/'null' -> NullExtension.
Raises ValueError listing installed extensions when the name is unknown.

