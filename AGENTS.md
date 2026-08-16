# AGENTS.md

Instructions for coding agents working in this repository. Humans should read
[CONTRIBUTING.md](CONTRIBUTING.md) and the engineering doctrine it links:
[Philosophy](website/docs/development/philosophy.md) and
[Workflow](website/docs/development/workflow.md). This file is the short version
plus the things that are easy to get wrong.

`dbml-sharepoint` turns a DBML schema plus a `mapping.yaml` into a browser-paste
`deploy.js.txt` that provisions SharePoint Online lists. The generated scripts run
against other people's production sites.

## The one rule that matters most

**Never assert how SharePoint behaves from plausibility.** Check Microsoft Learn,
or write a probe under `test/manual/` and have the user paste it into a live
site.

The failure class this project exists to close is a formatter or rule that saves,
reads back byte-identical, passes every deploy phase, and does nothing on the
rendered page. Nothing in the build or the deploy can see it, so a wrong
assumption ships silently and stays.

This is not hypothetical. Three "obviously correct" assumptions made in one
session were all wrong: five of thirty-five Fluent icon names did not exist, a
validator rule was backwards against what Learn documents, and a width scale
written from memory omitted five values the reference template actually uses.

Corollaries:

- An enforced rule must never be stronger than what the reference implementation
  actually satisfies.
- When writing a probe, separate the values a measurement **depends on** from the
  values it **observes**. Asserting over the second kind makes the experiment
  kill itself the moment it starts working, and that looks identical to a real
  failure.
- If a live run teaches you something, encode it: a dated comment, a pinned test,
  a design-doc revision.

## Gates

Every change must leave all of these green. They are the same commands the git
hooks run, so a hook can never disagree with CI.

```bash
uv run pytest
uv run ruff check src test website/scripts scripts
uv run mypy
uv run j2lint --ignore jinja-statements-indentation single-statement-per-line -- src/dbml_sharepoint/templates
uv run prek run --all-files markdownlint-cli2
```

Markdown is the one gate not pinned by `pyproject.toml`. markdownlint-cli2 is a
node package, so prek installs it from the `rev:` in `.pre-commit-config.yaml`
and CI runs the same version through `npx`. Those two numbers are held equal by
`test/test_markdownlint_version.py`; bump them together. Rules and exclusions
live in `.markdownlint-cli2.yaml`, which both sides read. Generated pages
(`website/docs/api/**`, `website/docs/reference/findings.md`) are excluded there,
because a violation in one of those can only be fixed in its generator.

Install the git hooks once with `uv run prek install`. Hooks are run by
[prek](https://prek.j178.dev/), pinned in the `dev` group; classic `pre-commit`
is not used here. Run everything by hand with `uv run prek run --all-files`.

`pytest` runs in parallel by default (`-n auto`, capped at 8). Pass **`-n0`** when
you need `--pdb`, deterministic ordering, or readable output from one test:
`uv run pytest -n0 test/test_joins.py`.

## Writing style

- No em dashes. Use commas, parentheses, or a new sentence.
- Banned phrases: "load-bearing", "worth stating plainly", "full stop",
  "carry the argument", "the trap", "isn't just X, it's Y".
- No punchy fragments for drama. Write complete sentences.
- Do not build to a turn of phrase. State the claim directly.
- Technical documentation, not marketing copy.
- Comments explain why, in one line. No paragraph-length comments.
- Write no new documentation unless explicitly asked. Regenerating a committed
  reference, and correcting a page the change has made wrong, are part of the
  change rather than new documentation.

This applies to everything you write: code comments, docstrings, commit
messages, pull request titles and bodies, issues, and the docs under
`website/`. It does not apply retroactively. Existing prose predates the rule
and a repo-wide rewrite would bury real changes in noise, so fix the lines you
are already touching.

## Commits and merging

**The PR title matters, and is not cosmetic.** This repository squash-merges and
the PR title becomes the commit subject on `main`. `release-please` cuts the
changelog by parsing those subjects, so a non-conventional title contributes
*nothing* to the release notes, silently. The release still happens, the code
still ships, and only the notes are wrong.

This has already bitten: PRs #41, #42, #45 and #51 all merged with prose
subjects, and 0.4.0 initially credited the join-ceiling release with a single
documentation tweak. It had to be back-filled with empty commits (#57).

So: **give the pull request a conventional title**: `feat:`, `fix:`, `docs:`,
`chore:`, `test:`, `style:`, `refactor:`, `perf:`, `build:`, `ci:`, `revert:`,
with an optional `(scope)` and a `!` for breaking changes.
`.github/workflows/pr-title.yml` enforces it.

Commits *within* a branch are not linted. They are squashed away, though their
messages survive in the squashed commit's body. Keep one concern per commit
anyway; that is what makes a branch reviewable.

The changelog has no Tests section, so a `test:` title is invisible in release
notes. Pick the type from what the change does, not from which directory it
touches. #42 looked like a pure test-fixture PR but also changed `_views.py`.

Merge commits are disabled. For a change too large to review in one pass, stack
it (`gh stack`), so each layer keeps its own title and its own changelog entry.

## Things that will waste your time

- **Generated files are committed. Everything written must be LF.**
  `.gitattributes` declares `* text=auto eol=lf`, and `Path.write_text`
  defaults to text mode, so a writer that omits `newline="\n"` emits CRLF on
  Windows and marks every file it touched as modified, hiding the one real
  change among the noise. Both committed-output generators were fixed (they go
  through `generate_api.write_page` and an explicit `newline="\n"`), as were
  the shipped bundle artifacts (`bundle.write_artifact`). **Use those helpers
  rather than `write_text` when adding a writer**, because the defect is
  per-call-site and the next writer reintroduces it. If you do see phantom
  drift, diagnose it
  with `git diff --ignore-cr-at-eol` and `git checkout --` the files that come
  back empty. Note `git status` can also report a file modified from a stale
  stat cache alone; if `git diff` is empty for it there is no real change.
- **The deploy.js.txt golden.** Template changes fail
  `test_simple_deploy_js_matches_golden` until the fixture under
  `test/fixtures/expected/` is deliberately regenerated. Review the fixture diff
  like code. It is.
- **Regenerate the API reference** when Python signatures, docstrings or template
  contract comments change: `uv run python website/scripts/generate_api.py`, then
  commit the real diff.
- **A new validator rule needs a test that makes it FIRE.** Referencing the
  code is not enough. `test_every_code_can_actually_be_produced` is a static
  check and says so. Two things watch this, and they are not interchangeable:

  ```bash
  uv run pytest --cov                        # aggregate floor
  uv run pytest --check-finding-reachability # per-rule, names the offender
  ```

  Both are off by default locally and on in CI; config lives in
  `pyproject.toml` and `test/_reachability.py`. Coverage roughly doubles the
  run; reachability is only meaningful over a whole suite.

  **The floor cannot do the reachability job.** It is one number over ~6,000
  branches, so a single rule that stops firing vanishes into it and unrelated
  gains offset it indefinitely. Measured: deleting the only test that fires
  `display_title_too_long` leaves coverage at 95.21%, comfortably over the 95
  floor, while the reachability gate names the rule. Codes not reached yet live
  in `_reachability.NOT_YET_REACHED`, which is a ratchet: entries come out, and
  one going in needs a reason in the pull request.

- **Regenerate the findings reference** when a `FindingCode` or its entry in
  `analysis/finding_help.py` changes: `uv run python
  website/scripts/generate_findings.py`. That catalogue is the source of truth
  for what a code means; `website/docs/reference/findings.md` and
  `dbml-sharepoint explain` both read it, and a currency test fails on a
  hand-edited page. Do not edit the page. It was hand-maintained once and
  silently rotted into a document where all 194 rules stopped rendering.
- **Emitted JS.** For template changes, build an example and `node --check` the
  emitted scripts.
- **`uv run pytest` runs with `filterwarnings = ["error"]`.** A new dependency
  that emits a DeprecationWarning at import time will abort collection across
  every test module, which looks like a catastrophic failure rather than a
  warning. `pyparsing` is capped `<3.3` for exactly this reason. See the comment
  in `pyproject.toml` and the matching rule in `renovate.json`. Lift both
  together or neither.

## Layout

| Path | What |
| --- | --- |
| `src/dbml_sharepoint/analysis/` | Validation. `checks/` holds the individual rules |
| `src/dbml_sharepoint/generators/` | Emit deploy.js.txt, rollback.js.txt, assess.js.txt, reporting |
| `src/dbml_sharepoint/templates/` | Jinja templates for the emitted JS |
| `src/dbml_sharepoint/model/` | Mapping parsing and types |
| `src/dbml_sharepoint/solutions/` | The shipped list templates (schema + mapping + release per family). Inside the package so the wizard can offer them to somebody who never cloned this repository. Only files under the package reach the wheel. Do **not** confuse with `templates/` above, which is Jinja |
| `test/manual/` | Live-site probes. Transcripts are gitignored and a test enforces that no tracked file under these names references a tenant |
| `website/` | Docusaurus docs. `docs/api/` is generated and committed |

A generator must never import from `analysis/checks/`. Where both sides need the
same fact, it lives in a shared module: `analysis/joins.py` is the worked
example.

## Safety

Anything that writes must read back and verify. Anything uncertain must fail
closed with a named error. Undocumented SharePoint surfaces need live proof and
the strictest guards in the codebase. A pull request that weakens a guard has to
argue for it explicitly.
