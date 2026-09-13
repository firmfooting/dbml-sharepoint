---
title: project
sidebar_position: 47
---

# `dbml_sharepoint.project`

*Packaging: a project's inputs, found and loaded*

The project's inputs: finding them, loading them, and refusing a bad one.

Everything here is what a command needs BEFORE it can do anything: the three
config files, the extension a mapping declares, the site facts that name a
target, and the `dbml-sharepoint.env` defaults file. Split out of `cli.py` so
`wizard.py` can borrow the same validators without importing the module that
imports it, which was a real cycle rather than a lazy-loading choice (#171).

Refusals are still `typer` exceptions. The exit codes are the documented
contract -- 2 for misuse, 1 for a refused build -- and a second vocabulary
for the same failures would have to be translated back at every call site.

### `CONFIG_ERRORS`

```python
CONFIG_ERRORS = (<class 'ValueError'>, <class 'KeyError'>, <class 'OSError'>, <class 'yaml.error.YAMLError'>, <class 'pyparsing.exceptions.ParseBaseException'>)
```

### `config_error`

```python
def config_error(what: str, path: pathlib.Path | None, exc: Exception) -> NoReturn
```

### `load_config`

```python
def load_config(schema: pathlib.Path, mapping: pathlib.Path, release: pathlib.Path | None) -> tuple[dbml_sharepoint.model.parser.Schema, dbml_sharepoint.model.mapping_types.MappingBundle, dbml_sharepoint.model.release.Release | None]
```

Load the three config files, reporting a bad one as a message.

Any of these can fail on a typo in a file the operator edited by hand,
and an unhandled exception rendered ~20 lines of loader internals above
the single sentence saying what is wrong. The person who hits it is a
SharePoint admin editing YAML: not one frame of that stack is
actionable, and the semantic (post-load) errors beside it are already
clean one-liners, so the contrast made a config typo look like a crash
in the tool rather than a mistake in the file.

This CLI has no verbosity flag, so the traceback is not tucked behind
one. Inventing `--traceback` here would advertise an option the rest of
the interface does not have.

### `resolve_extension_or_refuse`

```python
def resolve_extension_or_refuse(extension: str | None, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, mapping: pathlib.Path) -> dbml_sharepoint.extension.BaseExtension
```

Resolve the extension name, reporting an unknown one as a message.

`resolve_extension` raises `ValueError`, which `CONFIG_ERRORS` already
covers, but every call sat one line outside `load_config`'s boundary,
so a typo in `--extension` or in a mapping's `extension:` key reached
the operator as a rich traceback rather than as the refusal the CLI
prints for any other bad input. The wrapper lives here rather than
inside `load_config` because that helper is about reading the three
config files, and an extension name is not one of them.

### `project_input`

```python
def project_input(explicit: pathlib.Path | None, relpath: pathlib.Path, flag: str, *, from_the_project: bool = True) -> pathlib.Path
```

The path the operator gave, or the family standard's, or a refusal.

`catalogue` declares where a project keeps its three inputs and
`test_template_standard` enforces it across every shipped family,
so inside a scaffolded project these paths are an already-proven fact
rather than a guess. Making the operator retype them on every rebuild --
the most repeated action in the tool, since the intended workflow is
edit-mapping, rebuild, re-paste -- was asking for something we already
had.

An explicit flag always wins. A default that cannot be overridden is a
trap, and pointing `--schema` at a scratch copy while the rest of the
project stays put is an ordinary thing to want.

Defaulting from a LAYOUT is safe in a way that defaulting a site URL
would not be: being wrong here means a file that is not there, and this
refuses. Being wrong about a target means a bundle armed for someone
else's tenant, with only the wrong-site guard between that and a
mispaste -- so `--site-url` stays required and is not treated the same
way.

The refusal names the standard path, because for anyone outside a
project that message is the entire feature. "Missing option '--schema'"
is true and teaches nothing.

`from_the_project=False` withdraws the default for an input whose
provenance is only implied by the others -- `build` passes it for
`--release` when the schema or mapping was named explicitly. A release
is not self-describing: nothing ties a release.yaml to the schema it
documents, so borrowing one across projects produces confident, wrong
provenance rather than an obviously missing one. The paths themselves
need no such guard; they name the file they load.

### `require_known_site_role`

```python
def require_known_site_role(bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> None
```

Refuse a role the mapping does not declare.

The vocabulary is data-driven -- the valid roles are whatever the
entities declare, never a hardcoded list -- because a misspelled role
would otherwise be silently filtered to an empty entity set and exit 0,
reporting success for a build that would provision nothing.

Shared by `build`, `report` and `validate` rather than spelled three
times: three commands disagreeing about which roles exist is exactly
the kind of drift that makes a `--dry-run` pass and the real build
refuse.

### `NO_SAFE_DEFAULT`

```python
NO_SAFE_DEFAULT = frozenset({'site_url'})
```

### `validate_site_url`

```python
def validate_site_url(site_url: str) -> str
```

Reject a malformed or non-https ``--site-url``, and return it cleaned.

The URL is interpolated into the generated deploy.js.txt (as ``SITE_URL`` and in
the site-match preflight comparison), so it must be a well-formed absolute
``https://`` URL with a host. Catches typos (``http://``, a bare path, a
missing host) before the operator pastes into a privileged console. Shared
by the core CLI and any extension project CLIs that compose it. Raises
``typer.BadParameter`` (exit 2) on failure.

RETURNS the URL with any query or fragment removed, rather than refusing
it. SharePoint's own **Copy link** puts `?web=1` on the clipboard, so the
most common paste carried one, and nothing downstream stripped it: the
reporting pack bakes this value into the Power Query `SiteRoot` and the
SQLCMD `SiteUrl`, producing endpoints like
`https://tenant/sites/X?web=1/_api/web`. Every consumer reads the value
`execute_build` holds after this call, so cleaning it once here reaches
all of them.

Normalising rather than refusing follows the precedent already on this
branch -- `_SITE_ROOT_M` trims a pasted LIST url back to the site root
rather than making the operator edit it. But a silent rewrite of what
somebody typed is its own defect, so the caller is expected to compare
and say so; see `site_url_notice`.

### `site_url_notice`

```python
def site_url_notice(given: str, used: str) -> str
```

What to tell the operator when the site URL was cleaned, or "".

A rewrite nobody is told about is indistinguishable from a rewrite that
went wrong. Returned rather than printed so the CLI and the wizard can
each render it in their own voice.

### `validate_time_zone`

```python
def validate_time_zone(time_zone: str) -> str
```

Refuse a ``--time-zone`` the IANA database does not declare.

The reporting pack derives the site's daylight-saving transitions from
the name, so a name the database does not declare has nothing to derive
from, and a name that is merely close (`Melbourne`, `australia/melbourne`)
is refused with the spelling it probably meant rather than guessed at.
Shared by `build`, `report` and the wizard, so the three cannot come to
disagree about what a usable zone is. Raises ``typer.BadParameter``
(exit 2) on failure, the same contract as `validate_site_url`.

Returned unchanged when it passes: nothing about a zone name needs
cleaning, and a silent rewrite of what somebody typed is the defect
`site_url_notice` exists to report.

### `missing_time_zone`

```python
def missing_time_zone() -> typer._click.exceptions.BadParameter
```

The refusal for a run that named no zone anywhere.

Not a typer-level required option, because `dbml-sharepoint.env` may
supply it (`DBMLSP_TIME_ZONE`), so "required" here means "required
after the file has been read". A run that reached this far has been
told nothing about the site's zone, and the pack cannot convert a
timestamp by a zone it was never given. Shared by `build` and `report`,
which read the zone the same way.

### `EnterpriseReaderDeclined`

```python
@dataclass(frozen=True)
class EnterpriseReaderDeclined:
```

Sentinel: the operator was asked and chose nobody.

`execute_build`'s `enterprise_reader` parameter carries three states, not
two -- unset (no flag, no wizard answer, ``None``), this sentinel
(explicitly nobody), and a UPN (``str``). Only the unset state is a
default a future ``dbml-sharepoint.env`` may fill; this one must survive
untouched, because it is what the wizard sends for a deliberate blank
answer at `_ask_enterprise_reader`. A bare `object()` would work at
runtime but repr as an unreadable address; this dataclass gives it a
name instead.

### `ENTERPRISE_READER_DECLINED`

```python
ENTERPRISE_READER_DECLINED = ENTERPRISE_READER_DECLINED
```

### `validate_enterprise_reader`

```python
def validate_enterprise_reader(address: str) -> None
```

Refuse anything that is not a plain UPN.

The `|` check is the one doing real work. A claims login name --
`i:0#.f|membership|svc@example.org` -- contains an `@` and would pass a
naive check, then hand `web/ensureuser` a principal other than the user
it appears to name. Refusing the character outright is cheaper than
parsing claims, and no legitimate UPN contains one.

### `resolve_env_file`

```python
def resolve_env_file(env_file: pathlib.Path | None) -> pathlib.Path | None
```

The env file `build` should read, or None when there is nothing to.

An explicit --env-file must exist, so a typo cannot silently build
without the settings the operator asked for. At the default location an
absent file is ordinary and not an error, but something present that is
not a readable file is refused rather than treated as absent.

### `UnwiredEnvSettingError`

An `ENV_SETTINGS` entry whose `parameter` `resolve_env_settings`
does not know how to apply.

Not a build-time failure a consumer's file can cause -- this fires only
when a contributor adds a registry entry without also teaching
`resolve_env_settings` how to use it, so it is a programming error, not
an `EnvFileError`. It is still raised rather than logged and swallowed:
a contributor who adds the second entry gets a loud failure the moment a
build actually exercises the key, rather than a build that succeeds
while quietly discarding what the file asked for.

### `validate_list_title`

```python
def validate_list_title(value: str, flag: str) -> None
```

Refuse a list title that cannot survive the emitted script.

The empty string is NOT validated here: `--deployment-log-list ''` is a
deliberate disable, checked by the caller before this runs, and a padded
or control-bearing variant of it still lands here and is refused.

Titles are interpolated into `getbytitle('...')` URLs through
`odataName`, which escapes quotes but cannot escape a newline; and a
title padded with spaces would silently name a different list than the
operator sees in the UI.

### `validate_site_name`

```python
def validate_site_name(value: str, flag: str) -> None
```

Refuse a central-logging SITE name that cannot address a web.

A site name is not a list title: it is the last segment of
`/sites/<name>`, interpolated by `crossWebApi`, so the display-title
length limit is the wrong rule and a space is fatal rather than merely
confusing. What matters is that the segment stays one segment -- a
leading or trailing slash would produce `/sites//name` or a trailing
empty segment, and an embedded slash would silently address a different
web than the operator named.

The empty string is NOT validated here: `--deployment-log-site ''` is the
documented disable, checked by the caller before this runs.

### `resolve_env_settings`

```python
def resolve_env_settings(env_file: pathlib.Path | None, enterprise_reader: str | dbml_sharepoint.project.EnterpriseReaderDeclined | None, deployment_log_list: str | None, deployment_log_change_list: str | None, deployment_log_site: str | None, change_log_list: str | None, time_zone: str | None) -> tuple[str | dbml_sharepoint.project.EnterpriseReaderDeclined | None, str | None, str | None, str | None, str | None, str | None, dbml_sharepoint.model.env_file.EnvProvenance]
```

Apply a resolved dbml-sharepoint.env file, honouring anything already
supplied explicitly. Builds the `EnvProvenance` in the same pass that
decides what is used, so the record can never drift from the decision it
describes -- there is exactly one place this precedence is applied.

Precedence: an explicit value -- a flag, or the wizard's declined
sentinel -- always wins over the file; the file wins over the built-in
default of nothing supplied at all.

`env_file` is a path already resolved by the caller (`resolve_env_file`
for `build`); this function does no discovery of its own, only parsing.

The four list-name settings resolve to ``None`` ONLY when neither a flag
nor the file supplied anything (so the template can distinguish "the
operator turned the external log off" from "nothing was said"): the
build's own flags carry defaults, so in practice a plain build always
names its defaults here. The time zone has no default at all: ``None``
after this is a build that must refuse, see `missing_time_zone`.

### `resolve_env_time_zone`

```python
def resolve_env_time_zone(env_file: pathlib.Path | None, time_zone: str | None) -> tuple[str | None, dbml_sharepoint.model.env_file.EnvProvenance]
```

The zone for a command that consumes the file's zone and nothing else.

`report` wants the precedence `build` applies -- a flag beats the file,
the file beats nothing said -- without inheriting the other five
settings, so this runs the one resolver and narrows the record to the
key it actually used. Reporting the rest would have a `report` run say
it applied an enterprise reader it never reads.

### `echo_env_provenance`

```python
def echo_env_provenance(provenance: dbml_sharepoint.model.env_file.EnvProvenance) -> None
```

Say what was read, and what won. An absent line here is
indistinguishable from a feature that did not run, so the no-file case
is stated explicitly rather than left silent.

