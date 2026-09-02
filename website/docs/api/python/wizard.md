---
title: wizard
sidebar_position: 36
---

# `dbml_sharepoint.wizard`

*Packaging: the interactive template wizard*

The interactive template wizard: the default `dbml-sharepoint` command.

Copies one shipped template into a project directory of the user's own,
optionally gives its lists a name prefix, and offers to build it. The prefix
is a yes/no gate -- "Give these lists a name prefix?", defaulting to no --
followed by the value prompt only when the answer is yes; a template
declaring no prefix skips the pair entirely. Pressing Enter at that gate now
produces unprefixed lists, the opposite of the old default. The Review
panel's `Lists` row is what shows the operator the names they are actually
about to create. It is the safety net for that reversed default, and it
matters for as long as a blank prefix is a valid answer.

Every question is asked before anything is written, and the whole decision is
reviewed once. The alternative -- confirming a write, then being asked three
more questions, then having a deploy bundle generated against a real site --
put the operator's commitment before the facts they were committing to.

Scope is deliberate. The wizard changes **identity only** -- prefix, site
URL, site role, where the files land. It never edits the schema or the
mapping's structure. Those templates are the tested artifacts: every one of
them is built end-to-end in CI and held to `test_template_standard.py`, and a
wizard that let a user restructure one would be handing them an untested
mapping while implying the opposite.

It is a front end onto `cli.execute_build`, not a second builder. Anything
the wizard produces, the documented flags could have produced.

`Answers` is deliberately plural in its templates. Deploying several
templates to one site is where this is going; `execute_build` takes a single
mapping, so that still means one bundle each, and making it one bundle is a
feature with its own design. What is drawn here is the boundary -- per-site
answers apart from per-template ones -- not the feature.

Every string literal in this module must be ASCII: it is in `_CONSOLE_BOUND`
and `test_messages_bound_for_a_console_are_ascii` walks the AST.

### `WizardError`

The wizard cannot safely continue. Always names what went wrong.

### `TemplateChoice`

```python
@dataclass(frozen=True)
class TemplateChoice:
    solution: Solution
    prefix: str
    entity_roles: tuple[tuple[str, str], ...]
```

One chosen template, and the prefix its lists will carry.

Separate from `Answers` because the two answer different questions. A
prefix belongs to a template -- it renames that template's lists and
nothing else -- while the directory, the site URL and the site role
describe one SharePoint site. Several templates deployed to one site is
the direction this is headed, and that boundary is the part of it worth
drawing now.

#### `TemplateChoice.list_titles`

```python
def list_titles(self, site_role: str) -> tuple[str, ...]
```

The SharePoint list titles this template creates for one site role.

A method rather than a property because it iterates. The rule it
obeys is plain concatenation, which is what every generator that
names a list does -- `jsgen`, `assessgen`, `demogen`, `manifestgen`
and `reportgen` each build the title as `prefix + entity_name` -- so
this reports the build's behaviour rather than predicting it.

Named by MODULE, not by line. An earlier version of this docstring
cited five `file:line` pairs and four of them had drifted within one
stack of rebases, pointing at a blank line, a docstring and a list
initialiser. A citation that rots is worse than none: it reads as
precision and sends the next person to the wrong place.

FILTERED BY SITE ROLE, because the build is. Every generator goes
through `ordering.site_tables_in_order`, which keeps only entities
whose `site_role` matches the one being built. Reporting
`Solution.lists` unfiltered made the Review panel promise every list
in the mapping: a mapping declaring `default: Risk` and
`archive: Archive` had the panel name both while the bundle created
only `Risk`. Unreachable with the shipped families, which all
declare `default` and nothing else -- but the site-role question
exists precisely for the mappings where it is not.

The ORDER is the mapping's declaration order, not the dependency
order `site_tables_in_order` computes from the schema. A review names
a set; matching the order would mean parsing the DBML here for no
gain the operator can see.

### `Answers`

```python
@dataclass(frozen=True)
class Answers:
    destination: Path
    site_url: str
    site_role: str
    templates: tuple[dbml_sharepoint.wizard.TemplateChoice, ...]
    build: bool
    reader: str | None
    seed: bool
    env_file: pathlib.Path | None = None
```

What the wizard collected, before anything is written.

Every field is filled before the single confirmation, which is the
point: the operator reviews the whole decision once rather than
confirming a write and then being asked three more questions.

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

