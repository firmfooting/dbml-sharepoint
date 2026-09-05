---
title: env_file
sidebar_position: 5
---

# `dbml_sharepoint.model.env_file`

*parse dbml-sharepoint.env build defaults*

Parser for dbml-sharepoint.env, a KEY=value file of build defaults.

A consumer can keep build parameters beside their solution instead of
retyping flags. `ENV_SETTINGS` names every key this build understands, and
`read_env_file` refuses everything else.

Refusing is the point. A permissive parser that skipped a misspelled key or
a stray `export` would build clean, enrol nobody, and leave nothing
downstream able to see the difference. The strictness costs a consumer
nothing, because the filename is ours and no existing `.env` conventions
apply to it.

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

### `ENTERPRISE_READER_KEY`

```python
ENTERPRISE_READER_KEY = 'DBMLSP_ENTERPRISE_READER'
```

### `ENTERPRISE_READER_PARAMETER`

```python
ENTERPRISE_READER_PARAMETER = 'enterprise_reader'
```

### `DEPLOYMENT_LOG_LIST_KEY`

```python
DEPLOYMENT_LOG_LIST_KEY = 'DBMLSP_DEPLOY_LOG_LIST'
```

### `DEPLOYMENT_LOG_LIST_PARAMETER`

```python
DEPLOYMENT_LOG_LIST_PARAMETER = 'deployment_log_list'
```

### `DEPLOYMENT_LOG_SITE_KEY`

```python
DEPLOYMENT_LOG_SITE_KEY = 'DBMLSP_DEPLOY_LOG_SITE'
```

### `DEPLOYMENT_LOG_SITE_PARAMETER`

```python
DEPLOYMENT_LOG_SITE_PARAMETER = 'deployment_log_site'
```

### `CHANGE_LOG_LIST_KEY`

```python
CHANGE_LOG_LIST_KEY = 'DBMLSP_CHANGE_LOG_LIST'
```

### `CHANGE_LOG_LIST_PARAMETER`

```python
CHANGE_LOG_LIST_PARAMETER = 'change_log_list'
```

### `ENV_SETTINGS`

```python
ENV_SETTINGS = (EnvSetting(key='DBMLSP_ENTERPRISE_READER', parameter='enterprise_reader', help='UPN of the enterprise-reader service account to enrol.'), EnvSetting(key='DBMLSP_DEPLOY_LOG_LIST', parameter='deploymen…
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

One line naming the env file a build read, for the manifest, index.md
and the deploy transcript.

The no-file case gets its own sentence, because an absent line reads the
same as a feature that never ran. Overridden keys are named alongside
used ones, reporting only the value that won, so a losing candidate never
reaches a written artefact.

### `EnvFileError`

Base class for anything wrong with a dbml-sharepoint.env file.

### `EnvFileSyntaxError`

A line does not parse as KEY=value under this file's rules.

### `UnknownEnvKeyError`

A DBMLSP_-prefixed key that is not in ENV_SETTINGS.

### `EnvFileReadError`

The file could not be read or decoded.

Covers `OSError` from `read_bytes` and bytes that are not valid UTF-8.
Both are wrapped here because every catch site downstream handles only
`EnvFileError`, and an unwrapped one would print a raw traceback.

### `read_env_file`

```python
def read_env_file(path: pathlib.Path) -> tuple[dict[str, str], str]
```

Parsed settings and the digest, from ONE read of the bytes.

The digest is sha256 of the raw bytes, so a whitespace-only edit moves
it. One function returns both, rather than a separate digest helper a
caller could run against a file that changed between the two reads.

