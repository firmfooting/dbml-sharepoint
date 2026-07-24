# Contributing

Thanks for considering a contribution. The project's engineering doctrine
is documented in full on the docs site — read
[Development → Philosophy](website/docs/development/philosophy.md) and
[Development → Workflow](website/docs/development/workflow.md) before
starting anything non-trivial; they explain *why* the gates below exist
and how a change is expected to move from idea to merged.

## Setup

```bash
uv sync
prek install          # or: pre-commit install — installs the git hooks
```

The hooks in `.pre-commit-config.yaml` run the same lint/type/template
checks as CI on every commit (ruff, mypy, j2lint) and the full test
suite on push. They shell out to the project's own pinned tools via
`uv run`, so a hook can never disagree with CI. Run them by hand any
time with `prek run --all-files`.

## The gates

Every change must leave all of these green:

```bash
uv run pytest                               # full suite, incl. the semantic Jinja template lint
uv run ruff check src test website/scripts  # lint
uv run mypy                                 # strict typing: src, test, website/scripts
uv run j2lint --ignore jinja-statements-indentation single-statement-per-line -- src/dbml_sharepoint/templates
```

Notes that save you a round-trip:

- **The deploy.js golden.** Template changes fail
  `test_simple_deploy_js_matches_golden` until the fixture under
  `test/fixtures/expected/` is deliberately regenerated. Review the
  fixture diff like code — it is.
- **Generated docs.** If Python signatures, docstrings or template
  contract comments changed, regenerate the API reference and commit the
  diff: `uv run python website/scripts/generate_api.py`.
- **Emitted JS.** For template changes, build an example and
  `node --check` the emitted scripts.

## Commits

Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, ...) — releases
and the changelog are cut by release-please from commit messages. One
concern per commit, tests included.

## Safety expectations

The generated scripts run against other people's production SharePoint
sites. Anything that writes must read back and verify; anything
uncertain must fail closed with a named error; undocumented SharePoint
surfaces need live proof and the strictest guards in the codebase. If a
live run teaches you something, encode it — dated comment, pinned test,
design-doc revision. Pull requests that weaken a guard need to argue for
it explicitly.
