# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub security advisories](https://github.com/shauneccles/dbml-sharepoint/security/advisories/new)
rather than opening a public issue. You should get an initial response
within a week.

## Scope worth knowing about

dbml-sharepoint generates scripts that an operator pastes into the
browser console of a SharePoint site they administer, running under that
operator's own session. There are no stored credentials, no app
principals and no network services in this package. The security-relevant
surface is therefore the *generated code*:

- anything that could make a generated script act against a site other
  than the one baked in at build time (site-guard bypass);
- anything that could smuggle attacker-controlled content from the DBML,
  mapping YAML or referenced config files into the generated JavaScript
  outside the intended JSON-encoded values (template injection);
- anything that could make the read-only assessment script perform a
  write.

Reports in those categories are treated as security issues, not bugs.
