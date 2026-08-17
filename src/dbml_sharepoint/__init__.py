"""DBML -> SharePoint Online list provisioning via browser-console deploy.js.

Every name an extension author needs is imported from the module that defines
it, and this package re-exports nothing. An aggregator here would need an
export list, or a redundant `import X as X`, to survive `mypy --strict`, and
either gives a name a second home to be kept in step with the first.

The paths below are the canonical ones. `test/test_public_api.py` imports each
of them, so a name that moves fails there rather than in a reader's editor.

The extension protocol, in `dbml_sharepoint.extension`:

- `dbml_sharepoint.extension.DeploymentExtension` is the protocol: hook names,
  parameter order, return types.
- `dbml_sharepoint.extension.BaseExtension` is the no-op base to subclass.
- `dbml_sharepoint.extension.SiteContext` is the per-build input `seed_lists`
  receives.
- `dbml_sharepoint.extension.ManifestExtras` is what `manifest_extras` returns.

What a hook reports, in `dbml_sharepoint.analysis.findings`:

- `dbml_sharepoint.analysis.findings.Finding` is one reported problem.
- `dbml_sharepoint.analysis.findings.FindingCode` is its stable code.
- `dbml_sharepoint.analysis.findings.Severity` is "error" or "warning"; an
  error aborts the build.
- `dbml_sharepoint.analysis.findings.Location` is where the finding was found.

What a hook is given, from the parsed inputs:

- `dbml_sharepoint.model.mapping_types.MappingBundle` is the loaded mapping.
- `dbml_sharepoint.model.parser.Schema`, `dbml_sharepoint.model.parser.Table`
  and `dbml_sharepoint.model.parser.Column` are the parsed DBML.
"""

__version__ = "0.1.0"  # x-release-please-version
