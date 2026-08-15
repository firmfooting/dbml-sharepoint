---
title: env_file
sidebar_position: 4
---

# `dbml_sharepoint.model.env_file`

*parse dbml-sharepoint.env build defaults*

Parser for dbml-sharepoint.env, a KEY=value file of build defaults.

A consumer can put build parameters beside their solution instead of
retyping flags on every invocation, starting with the enterprise-reader UPN.
The registry (`ENV_SETTINGS`) names every key this build understands; the
parser (`read_env_file`) is deliberately strict about everything else.

The failure class this project exists to close, per `AGENTS.md`, is a change
that saves, reads back clean, and does nothing on the far side. A permissive
parser that silently skipped a misspelled key or a stray `export` would build
clean and enrol nobody, and nothing downstream could ever see the difference.
Refusing outright is the only way a mistake here is not silent. The strict
rules are fair specifically because the filename is ours: this is not a
`.env` a consumer already has conventions for, so refusing the ones this file
does not need (`export`, interpolation, shell quoting edge cases) costs
nothing a consumer was relying on.

### `ENV_FILENAME`

```python
ENV_FILENAME = 'dbml-sharepoint.env'
```

### `EnvSetting`

```python
@dataclass(frozen=True)
class EnvSetting:
    key: str
    parameter: str
    help: str
```

One key this file is allowed to set.

`key` is the `DBMLSP_`-prefixed name read from the file; `parameter` is
the `execute_build` keyword it supplies; `help` is one line, listed by
`build --help` in a later task.

### `ENV_SETTINGS`

```python
ENV_SETTINGS = (EnvSetting(key='DBMLSP_ENTERPRISE_READER', parameter='enterprise_reader', help='UPN of the enterprise-reader service account to enrol.'),)
```

### `EnvValue`

```python
@dataclass(frozen=True)
class EnvValue:
    setting: EnvSetting
    value: str
    used: bool
    override: str | None
```

One resolved setting, and whether a CLI flag overrode it.

`used` is False when a flag passed on the command line won; `override`
then carries the value that won, for reporting.

### `EnvProvenance`

```python
@dataclass(frozen=True)
class EnvProvenance:
    path: str | None
    digest: str | None
    values: tuple[dbml_sharepoint.model.env_file.EnvValue, ...]
```

What was read, for the build to report. `path` is None when no env
file was found; the caller renders it relative rather than absolute.

### `NO_ENV_FILE`

```python
NO_ENV_FILE = EnvProvenance(path=None, digest=None, values=())
```

### `describe_env_provenance`

```python
def describe_env_provenance(provenance: dbml_sharepoint.model.env_file.EnvProvenance) -> str
```

One line describing what dbml-sharepoint.env a build read, for an
artefact that is not the terminal the build ran in: the manifest,
index.md and the deploy transcript's `log()` line.

An absent line is indistinguishable from a feature that did not run, so
the no-file case is its own explicit sentence rather than nothing.

Reports overridden keys as well as used ones -- naming only the key and
the value that won, never the file's own value, so a losing candidate
(a flag beat it, or the wizard's declined sentinel did) never appears in
a written artefact. Without this, a build where a flag beat the file
left the manifest indistinguishable from one where the file was never
consulted at all.

### `EnvFileError`

Base class for anything wrong with a dbml-sharepoint.env file.

### `EnvFileSyntaxError`

A line does not parse as KEY=value under this file's rules.

### `UnknownEnvKeyError`

A DBMLSP_-prefixed key that is not in ENV_SETTINGS.

### `EnvFileReadError`

The file could not be read or decoded.

Covers `path.read_bytes()` raising `OSError` (a permission error, or a
directory sitting at that name) and the bytes it does return not being
valid UTF-8. Both are caught here rather than left to propagate, because
every catch site downstream only handles `EnvFileError` -- an unguarded
`UnicodeDecodeError` or `OSError` would reach a caller with no handler
for it and print a raw traceback instead of the one clean message this
module exists to guarantee.

### `read_env_file`

```python
def read_env_file(path: pathlib.Path) -> tuple[dict[str, str], str]
```

Parsed settings and the digest, from ONE read of the bytes.

The digest is sha256 of the raw bytes, not of the parsed content, so a
whitespace-only edit still moves it -- and it is computed from the same
bytes the parser reads, because a caller comparing a recorded digest
against the file it was told was parsed needs that to be true. Hence one
function returning both, rather than a digest helper a caller might call
against a file that changed between the two reads.

