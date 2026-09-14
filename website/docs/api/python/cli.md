---
title: cli
sidebar_position: 49
---

# `dbml_sharepoint.cli`

*Packaging: the command-line interface*

Command-line interface for dbml-sharepoint.

### `main`

```python
def main(ctx: typer.models.Context) -> None
```

Run the interactive wizard when invoked with no subcommand.

Every documented flag still works exactly as before: `build`, `report`
and `version` are untouched, and this callback returns immediately when
one of them was named.

A bare invocation only prompts when stdin AND stdout are both a
terminal. In CI, a cron job, a Dockerfile or a pipe it prints help and
exits 0, which is what a bare invocation did before the wizard existed
-- so nothing that scripted `dbml-sharepoint` changes behaviour.

### `new`

```python
def new() -> None
```

Interactively copy a solution template into a new project.

The same wizard a bare `dbml-sharepoint` runs, named so it can be asked
for explicitly and so it appears in `--help`.

### `build`

```python
def build(schema: pathlib.Path | None = ..., mapping: pathlib.Path | None = ..., release: pathlib.Path | None = ..., site_url: str = ..., time_zone: str | None = ..., site_role: str = ..., out: pathlib.Path = ..., dry_run: bool = ..., seed: bool = ..., enterprise_reader: str | None = ..., extension: str | None = ..., env_file: pathlib.Path | None = ..., deployment_log_list: str | None = ..., deployment_log_change_list: str | None = ..., deployment_log_site: str | None = ..., change_log_list: str | None = ..., no_sidecars: bool = ...) -> None
```

Generate deploy.js.txt + manifest from the DBML schema and mapping.

Resolves the three input paths here rather than inside `execute_build`:
the defaults are a convenience for a person at a terminal, and
`execute_build` is the programmatic entry point the wizard and extension
CLIs compose. Those callers know exactly which files they mean, and a
path that silently came from the working directory would be a surprise
in a library call.

### `validate`

```python
def validate(schema: pathlib.Path | None = ..., mapping: pathlib.Path | None = ..., site_role: str = ..., extension: str | None = ...) -> None
```

Check the schema and mapping. No site URL, no output, no release.

`validate_all` takes a schema, a mapping bundle and an extension --
not a site URL and not a release. Answering "is this correct?" through
`build --dry-run` therefore cost an invented tenant URL, on the tightest
loop in the tool: edit the mapping, check, edit again.

Deliberately NOT the same thing as `build --dry-run`, which keeps its
contract unchanged. The two answer different questions:

* `validate` -- is my schema and mapping correct?
* `build --dry-run` -- what would this build do against that site,
  without emitting JS?

The second is a run sheet for a named target. `deploy-manifest.md` does
not merely stamp the site URL in a header; step 3 of its run sequence
sends the operator to `<site_url>/_layouts/15/settings.aspx`. Rendering
that with a not-supplied marker would produce an artifact whose own
instructions are fiction, which is why this command writes no manifest
rather than `--dry-run` learning to omit the target.

Writes nothing at all, and takes no `--out`. A question, not an artifact.

`--site-role` does NOT scope the check, and must not. `validate_all`
takes no role and `build` calls it identically, so validation has always
been project-wide -- this reports exactly what a build would. Narrowing
it would hide an error under `admin` from anyone validating `default`,
which means the mapping reads clean until the deploy that breaks. The
flag's job here is to reject a role the mapping does not declare, moving
a typo's discovery earlier. Pinned by
`test_validate_checks_every_role_not_just_the_selected_one`.

### `explain`

```python
def explain(code: str = ...) -> None
```

Say what a finding code means, without leaving the terminal.

The code is a finding's identity -- stable, and what the catalogue is
keyed by -- while the message beside it is prose that may be reworded in
any release. So the code is the only part worth looking up, and until
now the only place to look it up was a website.

Reads `FINDING_HELP`, which ships inside the package. The published
reference at `reference/findings.md` is generated from the same data, so
the two cannot disagree.

### `report`

```python
def report(schema: pathlib.Path | None = ..., mapping: pathlib.Path | None = ..., time_zone: str = ..., site_role: str = ..., out: pathlib.Path = ..., release: pathlib.Path | None = ...) -> None
```

Generate reporting queries (Power Query M + SQL views) from the schema.

Emits one .pq file per list, a SQLCMD views script, guide.md with
usage instructions and the Power BI relationship table, and a
data-dictionary.md companion. Assumes a schema that `build` accepts;
run `build --dry-run` first if unsure.

`--time-zone` is a required option here rather than one the env file
may supply: this command reads no `dbml-sharepoint.env`, and inventing
that discovery for one key would give `report` half of `build`'s
precedence rules. It needs no site URL, because the pack it writes
reads a `SiteUrl` parameter instead, but the zone shapes the queries
themselves and has no parameter to fall back on.

### `extract_script`

```python
def extract_script(url: str = ..., out: pathlib.Path | None = ...) -> None
```

Generate the read-only browser-paste script that reads a live list.

Takes the whole list URL, because that is the one string the browser
address bar already holds: the site and the list title are split out of
it rather than asked for separately. One list per script.

The script and a readme are written into a folder named after the list,
which is where `dbml-sharepoint extract` then writes the draft schema
and mapping, so both halves of the flow keep one directory.

Paste the emitted file into the browser console on that site. It
downloads the list's field definitions as JSON; feed that JSON to
`dbml-sharepoint extract` to get a draft schema and mapping.

Every request the script makes is a GET. It carries no write helpers.

### `protection_script`

```python
def protection_script(url: str = ..., out: pathlib.Path | None = ...) -> None
```

Generate the browser-paste script that locks, unlocks, seals or unseals one list.

The script prints the list's deletion lock and the Sealed flag on each
custom column, then takes one word at a time: lock or unlock sets
AllowDeletion, seal or unseal sets Sealed on every custom column not
already in that state. Every write is read back, and a readback that
disagrees stops the run. It deletes nothing.

### `columns_script`

```python
def columns_script(url: str = ..., out: pathlib.Path | None = ...) -> None
```

Generate the browser-paste script that enumerates and deletes one list's custom columns.

The script prints the custom columns and asks for one by internal name,
never by position. Built-in and hidden fields never appear. Every item is
read to see whether the column holds a value: an empty column needs its
internal name typed again after that scan, and one with values, or whose
values cannot be read, needs
DELETE NON-EMPTY typed. A sealed column is unsealed and read back before
the delete, and the column is read back after it and must be gone. The
table is printed again after each delete; a blank answer finishes.

Deleting a column removes its values from every item, and nothing goes
to the recycle bin.

### `identify_script`

```python
def identify_script(site_url: str | None = ..., out: pathlib.Path | None = ...) -> None
```

Generate the read-only browser-paste script that reports what is on a site.

The script reads the web's own facts, every list, group and permission
level, and which of them this tool provisioned and for which family. It
reads the columns of the lists it owns, and reports the last deployment
the site recorded. It prints the result as tables and offers it as a JSON
download.

NO SITE URL IS NEEDED. The script runs against whichever web it is
pasted on, so one file walks every site in a fleet. Pass --site-url to pin
it to one, which is worth doing when handing the file to somebody else.

Every request the script makes is a GET. It carries no write helpers.

### `extract`

```python
def extract(source: pathlib.Path | None = ..., out: pathlib.Path | None = ..., entity: str | None = ..., prefix: str = ..., project: str | None = ..., force: bool = ...) -> None
```

Recover a draft schema.dbml and mapping.yaml from an existing list.

Takes the JSON `dbml-sharepoint extract-script` produced and you pasted
into the browser console. That read is the only input; nothing here is
recovered from an export.

With no argument it runs interactively instead, asking for the list's
URL, writing the script, waiting while you paste it, and extracting the
download when you say it has landed. The same two commands do the work
either way.

This is a SCAFFOLDING tool, not a lossless round-trip. What the read
carries is recovered; everything else is itemised in the
EXTRACTION-NOTES.md written beside the output. Read that file before
editing the schema, and again before deploying anything.

### `version`

```python
def version() -> None
```

Print the deployer version.

