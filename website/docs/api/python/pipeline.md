---
title: pipeline
sidebar_position: 48
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

### `execute_extraction`

```python
def execute_extraction(source: pathlib.Path, *, out: pathlib.Path | None = None, entity: str | None = None, prefix: str = 'EX_', project: str | None = None, force: bool = False) -> None
```

One extraction, from a download to a written project directory.

Shared by the `extract` command and the interactive flow, for the same
reason `execute_build` is shared with the template wizard: the wizard
must not be able to produce anything the documented flags could not.
Refusals leave through `typer.Exit`, which both callers understand.

