---
title: wizard
sidebar_position: 25
---

# `dbml_sharepoint.wizard`

*Packaging — the interactive template wizard*

The interactive template wizard: the default `dbml-sharepoint` command.

Copies one shipped solution template into a project directory of the
user's own, substitutes their list-name prefix, and offers to build it.

Scope is deliberate. The wizard changes **identity only** -- prefix, site
URL, where the files land. It never edits the schema or the mapping's
structure. Those templates are the tested artifacts: every one of them is
built end-to-end in CI and held to `test_template_standard.py`, and a
wizard that let a user restructure one would be handing them an untested
mapping while implying the opposite.

It is a front end onto `cli.execute_build`, not a second builder. Anything
the wizard produces, the documented flags could have produced.

### `WizardError`

The wizard cannot safely continue. Always names what went wrong.

### `Answers`

```python
@dataclass(frozen=True)
class Answers:
    solution: Solution
    destination: Path
    prefix: str
    site_url: str
```

What the wizard collected, before anything is written.

### `run_wizard`

```python
def run_wizard(console: rich.console.Console | None = None) -> int
```

Entry point. Returns the process exit code.

Ctrl-C is a normal way to leave a wizard, not a crash: it exits 130
(the shell's convention for SIGINT) without a traceback.

### `stdin_is_interactive`

```python
def stdin_is_interactive() -> bool
```

Whether it is safe to prompt.

A bare `dbml-sharepoint` in CI, a cron job or a Dockerfile must not
block on a prompt nobody can answer. The caller falls back to printing
help, which is what a bare invocation did before the wizard existed.

