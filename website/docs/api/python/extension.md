---
title: extension
sidebar_position: 24
---

# `dbml_sharepoint.extension`

*Packaging: the extension protocol*

The deployment-extension protocol: the hook
names, parameter order, and return types; this skeleton conforms to it.
Validation issues are reported with the validator Finding type.

### `SiteContext`

```python
@dataclass
class SiteContext:
    site_url: str
    site_role: str
    release: Any
    output_dir: Path
    extension_args: dict[str, typing.Any] = field(default_factory=dict)
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
def cli_subcommands(self, app: typer.main.Typer) -> None
```

#### `DeploymentExtension.expand_column`

```python
def expand_column(self, table: Any, column: Any, bundle: Any) -> list[dict[str, Any]] | None
```

#### `DeploymentExtension.extra_validators`

```python
def extra_validators(self, bundle: Any, schema: Any) -> list[typing.Any]
```

#### `DeploymentExtension.manifest_extras`

```python
def manifest_extras(self, bundle: Any, schema: Any) -> dbml_sharepoint.extension.ManifestExtras
```

#### `DeploymentExtension.seed_lists`

```python
def seed_lists(self, bundle: Any, schema: Any, site_context: dbml_sharepoint.extension.SiteContext) -> dict[str, dict[str, typing.Any]]
```

### `BaseExtension`

No-op defaults for the DeploymentExtension protocol; extensions
override only what they need.

#### `BaseExtension.cli_subcommands`

```python
def cli_subcommands(self, app: typer.main.Typer) -> None
```

Register wholly-new extension-owned subcommands on the core app.
Must never alter core command signatures.

#### `BaseExtension.expand_column`

```python
def expand_column(self, table: Any, column: Any, bundle: Any) -> list[dict[str, Any]] | None
```

#### `BaseExtension.extra_validators`

```python
def extra_validators(self, bundle: Any, schema: Any) -> list[typing.Any]
```

#### `BaseExtension.manifest_extras`

```python
def manifest_extras(self, bundle: Any, schema: Any) -> dbml_sharepoint.extension.ManifestExtras
```

#### `BaseExtension.seed_lists`

```python
def seed_lists(self, bundle: Any, schema: Any, site_context: dbml_sharepoint.extension.SiteContext) -> dict[str, dict[str, typing.Any]]
```

### `NullExtension`

No-op defaults for the DeploymentExtension protocol; extensions
override only what they need.

### `resolve_extension`

```python
def resolve_extension(name: str | None) -> dbml_sharepoint.extension.BaseExtension
```

Resolve by entry-point name; None/'null' -> NullExtension.
Raises ValueError listing installed extensions when the name is unknown.

