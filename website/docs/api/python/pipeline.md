---
title: pipeline
sidebar_position: 52
---

# `dbml_sharepoint.pipeline`

*Packaging: the library entry points behind the commands*

The library entry points: what a command does once its inputs are loaded.

`execute_build` and `execute_extraction` are the whole of `build` and
`extract`, callable without going through typer, so the wizard runs exactly
the pipeline the documented flags run rather than a second implementation
that drifts.

They live here rather than in `cli.py` because `cli.py` imports both wizards
at its top, so a wizard reaching back for the pipeline had to defer the
import into a function body to break the cycle (#171).

### `execute_build`

```python
def execute_build(*, schema: pathlib.Path, mapping: pathlib.Path, release: pathlib.Path, site_url: str, site_role: str, out: pathlib.Path = Path('build'), dry_run: bool = False, seed: bool = False, time_zone: str | None = None, extension: str | None = None, enterprise_reader: str | dbml_sharepoint.project.EnterpriseReaderDeclined | None = None, env_file: pathlib.Path | None = None, deployment_log_list: str | None = None, deployment_log_change_list: str | None = None, deployment_log_site: str | None = None, change_log_list: str | None = None, no_sidecars: bool = False) -> None
```

The `build` pipeline, callable without going through typer.

Extracted so the wizard can run exactly the same build the documented
flags run, rather than growing a second implementation that drifts. The
wizard is a different front end onto this, not a different builder.

Still raises `typer.Exit` on refusal: the exit codes are the documented
contract (2 for misuse, 1 for a refused build), and re-mapping them to
an exception of its own here would give the wizard a second vocabulary
for the same failures. The wizard catches it.

`enterprise_reader` carries three states: ``None`` (unset -- no flag was
given), `EnterpriseReaderDeclined` (the operator was asked and said
nobody), or a UPN. `env_file`, when given, is a `dbml-sharepoint.env`
ALREADY resolved to a path by the caller (`build` resolves the default
location the same way it resolves `--schema`, `--mapping` and
`--release`; this function does no discovery of its own). When the file
supplies a value for a setting that is still unset, that value is used;
an explicit `enterprise_reader` -- a flag or the declined sentinel --
always wins over the file, because both mean the operator already
decided.

`time_zone` is the site's IANA zone, a fact about the site the way
`site_url` is, and it is REQUIRED: ``None`` here is only "no flag was
given", and a build refuses once the env file has also had its say and
still named none. It defaults to ``None`` rather than being a required
keyword so the file can supply it, the same shape as `enterprise_reader`.

### `execute_validation`

```python
def execute_validation(*, schema: pathlib.Path, mapping: pathlib.Path, site_role: str = 'default', extension: str | None = None) -> list[dbml_sharepoint.analysis.findings.Finding]
```

The `validate` pipeline, callable without going through typer.

Returns the findings rather than printing them. The command computed
this list and then destroyed it, so the wizard could not offer a check
and an extension CLI could not compose one (#171).

`site_role` does NOT scope the check. `validate_all` takes no role and
`execute_build` calls it identically, so this reports exactly what a
build would; the role is here to refuse one the mapping does not
declare, which moves a typo's discovery earlier.

### `UnknownFindingCodeError`

`explain` was given a code no catalogue entry answers.

Named rather than a bare `LookupError` so a caller can tell "there is
no such code" from any other lookup failure, and carries the message
the command prints, suggestion included, because composing that needs
the catalogue this side already holds.

### `execute_explain`

```python
def execute_explain(code: str) -> str
```

What `explain` prints, for one code or for the whole catalogue.

Returns the text rather than echoing it, so the same answer can reach
a console, a wizard panel or a test without the catalogue lookup being
re-implemented beside each one.

Reads `FINDING_HELP`, which ships inside the package. The published
reference at `reference/findings.md` is generated from the same data,
so the two cannot disagree.

### `execute_report`

```python
def execute_report(*, schema: pathlib.Path, mapping: pathlib.Path, site_role: str = 'default', out: pathlib.Path = Path('reports'), release: pathlib.Path | None = None, time_zone: str | None = None, env_file: pathlib.Path | None = None) -> dict[str, str]
```

The `report` pipeline, callable without going through typer.

Returns the pack it wrote, relpath to content, so a caller can say what
landed without re-deriving the file names from the schema.

`time_zone` reads the same way `execute_build`'s does: a value given
here wins, `env_file` supplies one when nothing was, and a run with
neither refuses. `report` used to take the zone as a hard-required flag
and read no env file at all, so the two commands disagreed about where
the same site fact could come from (#171).

### `execute_extraction`

```python
def execute_extraction(source: pathlib.Path, *, out: pathlib.Path | None = None, entity: str | None = None, prefix: str = 'EX_', project: str | None = None, force: bool = False) -> None
```

One extraction, from a download to a written project directory.

Shared by the `extract` command and the interactive flow, for the same
reason `execute_build` is shared with the template wizard: the wizard
must not be able to produce anything the documented flags could not.
Refusals leave through `typer.Exit`, which both callers understand.

