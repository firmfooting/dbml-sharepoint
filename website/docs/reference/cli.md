---
title: CLI
sidebar_position: 1
---

# CLI reference

```bash
dbml-sharepoint COMMAND [OPTIONS]
```

## `build`

Generate the full deployment bundle (deploy.js.txt, rollback.js.txt, assess.js.txt,
manifests, reporting, index.md, checksums.txt — plus demo-data.js.txt with
`--seed`).

| Option | Default | Meaning |
|---|---|---|
| `--schema PATH` | `10-design/schema.dbml` | Path to the DBML schema file |
| `--mapping PATH` | `20-configure/mapping.yaml` | Path to the mapping YAML |
| `--release PATH` | `20-configure/release.yaml` | Path to release.yaml |
| `--site-url URL` | required | Target SharePoint site URL |
| `--site-role ROLE` | `default` | Which entities deploy here; must match a `site_role` declared by the mapping's entities |
| `--out PATH` | `./build` | Output directory |
| `--dry-run` | off | Validate only; no JS output |
| `--seed` | off | Also emit demo-data.js.txt from the mapping's `demo_items` |
| `--extension NAME` | mapping's `extension:` | Extension to apply; resolved via entry points |

### Running inside a project

The three input paths default to the layout every shipped template uses and
`dbml-sharepoint new` creates, so a rebuild from the project root is one flag:

```bash
dbml-sharepoint build --site-url https://yourtenant.sharepoint.com/sites/your-site
```

An explicit flag always wins. Outside a project directory, a missing input
names the path it looked for rather than only the flag.

`--site-url` is deliberately **not** given a remembered default. A wrong
file path fails loudly on the next line; a wrong target produces a bundle
armed for somebody else's tenant, with only the script's wrong-site guard
between that and a mispaste.

Behaviour worth knowing:

- Validation errors refuse the build — the manifest lists every finding.
- `--site-role` is checked against the roles the mapping actually
  declares; a misspelled role is an error, never a silently empty
  deploy plan.
- `--dry-run` still writes `deploy-manifest.md`, so you can read the
  findings and the deployment plan. It is the JS that is withheld.
- An extension that requires its own project CLI causes `build` to exit
  with instructions rather than emitting a half-configured bundle.

## `validate`

Check a schema and mapping. No site URL, no release, no output.

```bash
dbml-sharepoint validate          # inside a project directory
```

| Option | Default | Meaning |
|---|---|---|
| `--schema PATH` | `10-design/schema.dbml` | Path to the DBML schema file |
| `--mapping PATH` | `20-configure/mapping.yaml` | Path to the mapping YAML |
| `--site-role ROLE` | `default` | Rejected if the mapping does not declare it; does **not** narrow what is checked |
| `--extension NAME` | mapping's `extension:` | Extension whose extra validators to run |

Prints every finding with its code, then a count. Exits **1** if there are
errors, **0** otherwise — warnings do not fail it, the same rule `build`
applies.

**Validation is always project-wide.** `--site-role` does not scope it, and
an earlier version of this table wrongly said it selected which entities to
check. A finding under `admin` is reported even when validating with
`--site-role default`, which is deliberate: a mapping is one document, and
an error hidden until somebody deploys that role means the mapping reads
clean right up until the deploy that breaks. `validate_all` takes no role at
all, and `build` calls it exactly the same way — so this matches what a build
would report, which is the only useful contract for a pre-build check.

What the flag does do here is reject a role the mapping does not declare, so
`validate --site-role adnim` fails now rather than at
`build --site-role adnim` later.

### `validate` versus `build --dry-run`

They answer different questions, which is why both exist:

| | Question | Needs a site URL | Writes |
|---|---|---|---|
| `validate` | Is my schema and mapping correct? | no | nothing |
| `build --dry-run` | What would this build do against that site, without emitting JS? | yes | `deploy-manifest.md` |

`deploy-manifest.md` is a run sheet, not a findings report: step 3 of its
sequence sends the operator to `<site-url>/_layouts/15/settings.aspx`. That
is why `--dry-run` still requires a target, and why `validate` writes no
manifest rather than one with a placeholder in its instructions.

Reach for `validate` while editing. Reach for `--dry-run` when you want to
read the deployment plan before committing to the paste.

## `explain`

Say what a finding code means, without leaving the terminal.

```console
$ dbml-sharepoint explain unknown_column_type
unknown_column_type  [error]

A column's DBML type is not one the typemap knows.
```

The token may be pasted exactly as a build prints it — a trailing colon is
tolerated, because findings render as
`[ERROR] unknown_column_type: Project.Sponsor: ...` and the obvious thing to
do is select the code and paste it.

With no argument it lists every code and its severity. An unrecognised code
exits **2** and suggests the nearest matches.

The catalogue it reads, `analysis/finding_help.py`, ships inside the package
and is the same source the [findings reference](findings.md) is generated
from, so the two cannot disagree.

## Exit codes

Measured, because a CI gate keys on these:

| Code | Meaning |
|---|---|
| `0` | Success, including a `--dry-run` that found no errors |
| `1` | The build refused: validation errors, or an unreadable/invalid input file |
| `2` | Usage error — a missing required option, or a `--site-role` the mapping does not declare |

A validation failure exits **1**, not 2. `2` is the usage-error code
`typer` raises before the pipeline runs at all. Gate on non-zero rather
than on a specific code.

An unreadable or malformed input file is part of exit **1**, not 2 — a
refused build rather than a misuse of the command line. It is reported as a
single message naming the file and, where the parser gives one, the line:

```console
$ dbml-sharepoint build --mapping ./mapping.yaml …
[ERROR] mapping ./mapping.yaml: while parsing a flow mapping
  in "./mapping.yaml", line 3, column 12
expected ',' or '}', but got '<stream end>'
```

That covers what the YAML and DBML parsers reject, and the loader's own
checks — an unknown key, a missing required one, a value of the wrong kind.

It also covers a section whose *shape* is wrong — valid YAML, wrong kind of
value — for every section read as a mapping of names:

```console
$ dbml-sharepoint build --mapping ./mapping.yaml …
[ERROR] mapping ./mapping.yaml: views: expected a mapping of names, got list
```

Note this refuses `views: []` as well as a populated list. An empty sequence
where a mapping belongs used to be swallowed by the loader's `or {}`, so the
section loaded as empty and the build reported success having deployed none
of what was written there — the same typo as the populated case, failing
silently instead of loudly.

This is a rule about **shape, not emptiness**. Declaring no views is
entirely valid and is not what this refuses — omitting the section, `views:`
with nothing under it, and `views: {}` are all accepted, and every
non-`DocumentLibrary` list still gets the generated `All Items` view
regardless (authors are in fact forbidden from declaring one).

`{}` and `[]` are not two ways of writing "empty". These sections are keyed
by name: `{}` is that structure with zero entries, `[]` is a different
structure. The shipped mappings already depend on the distinction —

```yaml
enum_sources: {}                 # keyed by name
versioning:
  overrides: {}                  # keyed by name
watched_lists: []                # a list
permission_levels: []            # a list
```

— so `[]` under a name-keyed section says the author has the wrong shape in
mind, which is worth catching before they populate it.

The guard lives in the loader, not the CLI. `_CONFIG_ERRORS` deliberately
does not catch `AttributeError`/`TypeError`, because an unexpected error
really is a bug in the tool and must keep its stack; widening it would have
dressed every genuine loader bug up as a bad mapping file. Closed by #141.

## `report`

Emit the reporting pack only (no site URL required): `powerquery/`,
`sql/views.sql`, `guide.md`, `data-dictionary.md`.

Each run replaces the previous pack, so a list dropped from the schema does
not leave its `.pq` file behind. What it removes is exactly what it writes:
every `*.pq` under `powerquery/`, `sql/views.sql`, `guide.md` and
`data-dictionary.md` — then `powerquery/` and `sql/` themselves, but only if
emptying them left nothing. Treat `*.pq` as owned by this command: keep
hand-written queries somewhere other than `--out`. Anything else survives,
including files of other types sitting inside those two directories.

An input the command never got past — an unreadable schema or mapping, an
unknown `--site-role` — leaves the existing pack untouched. A schema it
reads and then refuses clears the pack, which by then describes a schema
that no longer exists.

| Option | Default | Meaning |
|---|---|---|
| `--schema PATH` | `10-design/schema.dbml` | Path to the DBML schema file |
| `--mapping PATH` | `20-configure/mapping.yaml` | Path to the mapping YAML |
| `--site-role ROLE` | `default` | Which entities to include |
| `--out PATH` | `./reports` | Output directory |
| `--release PATH` | `20-configure/release.yaml` when present | Stamp release provenance into the outputs |

Inside a project directory that makes the whole command `dbml-sharepoint
report`. `--release` stays genuinely optional — an unstamped dictionary is
a supported result, so unlike the other two a missing release.yaml is not
a refusal; it is simply picked up when it is there.

## `version`

Print the deployer version.
