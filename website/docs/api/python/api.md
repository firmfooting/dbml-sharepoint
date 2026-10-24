---
title: api
sidebar_position: 61
---

# `dbml_sharepoint.api`

*the names dependents import, each re-exported from its home*

The names dependents import from this package, each re-exported from its home.

This is the one module exempt from the one-home rule in the package
docstring. Inside this package, and for extension authors, the defining
modules stay the canonical paths; nothing inside the package imports this
module. A dependent imports from here and from `dbml_sharepoint.testing`
only, and holds itself to that with a protected import-linter contract over
`DEPENDENT_PROTECTED_MODULES`:

```toml
[tool.importlinter]
root_packages = ["<dependent>", "dbml_sharepoint"]
[[tool.importlinter.contracts]]
name = "Core only through dbml_sharepoint.api"
type = "protected"
protected_modules = [<DEPENDENT_PROTECTED_MODULES>]
allowed_importers = ["dbml_sharepoint"]
```

A dependent that copies `DEPENDENT_PROTECTED_MODULES` into its toml keeps a
one-line test comparing that list with `api.DEPENDENT_PROTECTED_MODULES`, so a
module core adds later does not go unprotected.

Removing a name from `__all__` is a breaking change for dependents.

### `DEPENDENT_PROTECTED_MODULES`

```python
DEPENDENT_PROTECTED_MODULES = ('dbml_sharepoint.analysis', 'dbml_sharepoint.bundle', 'dbml_sharepoint.catalogue', 'dbml_sharepoint.cli', 'dbml_sharepoint.extension', 'dbml_sharepoint.extract', 'dbml_sharepoint.generators', 'dbml_s…
```

