# Wizard refusal on an unparseable dbml-sharepoint.env

## Defect

`_reader_from_env_file` caught `EnvFileError` from `read_env_file`, printed
the message in red, and returned `None`. `_run` then continued, never
threaded an `env_file` into `execute_build`, and every artefact the build
wrote (manifest, index.md, deploy transcript) stated "No
dbml-sharepoint.env file was read." even though a file was there and the
operator had just been told, in passing, that it was broken.

`build` refuses the same file outright, naming the path, the line and the
text. Two commands reading the same file must not disagree about whether
it is fatal.

## Where the call happens relative to writing

`_reader_from_env_file` runs inside `_ask_enterprise_reader`, called from
`_run`'s "Build" section. That section runs after the template, prefix,
destination, site URL and site role questions, but strictly before the
Review panel, the "Write the project?" confirmation, and `_scaffold`
(the first thing that writes anything). Refusing there writes nothing.

## Fix

- `_reader_from_env_file` now raises `WizardError(str(exc))` from the
  caught `EnvFileError`, instead of printing and returning `None`. The
  message already names the path, the line and the offending text (from
  `_refuse` in `model/env_file.py`), so no new formatting was needed.
- `_run`'s "if build:" block wraps the calls to `_ask_enterprise_reader`
  and `_ask_seed` in `try`/`except WizardError`, printing the message in
  red and returning 1 -- the same abort mechanism already used around
  `_read_facts`/`_site_roles` and `_scaffold`. No second mechanism was
  invented.
- Docstrings on `_reader_from_env_file` and `_ask_enterprise_reader` were
  rewritten to describe the new behaviour and to explain why the two
  failure modes inside the same file are not the same (see below).

## The invalid-value case (decision)

Kept as a warning, not made fatal. Reasoning:

`build` validates a file's reader value only because that value, when no
flag overrides it, becomes the exact value `execute_build` uses -- so an
invalid one there really does need to abort the build.

The wizard's use of the file is structurally different: `_ask_enterprise_
reader` never passes the file's suggestion as `default=` (a `PromptBase`
default would make a blank answer unreachable, which is documented
separately). The suggestion only ever reaches `execute_build` if the
operator retypes it, and retyping goes through the same prompt-level
`validate_enterprise_reader` loop as any other typed answer. An invalid
file value is therefore never used unvalidated by anything downstream, and
no artefact ever claims otherwise -- the manifest correctly reports either
"Overridden" (the declined sentinel beat it) or nothing at all, exactly as
if the file had said nothing. Refusing the run over a value nothing was
ever going to use would be stopping a working run for no reason a false
artefact could result from.

## Tests

`test/test_wizard.py`:

- `test_an_unparsable_env_file_refuses_the_wizard_not_a_traceback` --
  replaces the old "clean message, continue" test. Asserts the message
  names the line and text, exit code 1, `execute_build` never called
  (`captured == {}`), and the destination directory was never created.
- `test_a_non_utf8_env_file_also_refuses_the_wizard` -- same shape, for
  `EnvFileReadError` (a subclass of `EnvFileError`), proving the refusal
  is not specific to `EnvFileSyntaxError`.
- `test_an_invalid_env_file_reader_is_a_clean_message_not_a_traceback` --
  unchanged in behaviour, docstring extended to cross-reference the new
  fatal case and state why it stays a warning.
- `test_no_env_file_behaves_exactly_as_before`,
  `test_the_wizard_offers_the_env_files_reader`,
  `test_a_blank_reader_answer_still_means_nobody_with_a_file_present`,
  `test_the_wizard_threads_the_env_file_into_execute_build`,
  `test_a_wizard_build_with_an_env_file_names_it_in_the_manifest` --
  all still pass unmodified: absent file, valid suggestion, and blank
  answer all behave exactly as before.

## Verification

- `uv run pytest` -- all green.
- `uv run ruff check src test website/scripts` -- clean.
- `uv run mypy` -- clean, 120 source files.
- `uv run prek run --all-files markdownlint-cli2` -- passed.
- `uv run python website/scripts/generate_api.py` -- produced no diff
  (the changed docstrings are not part of the rendered API surface for
  private functions), so nothing to commit there.
- Mutation check: reverted the `raise WizardError` back to the old
  `console.print` + `return None`, reran the two new tests. Both failed
  (`assert 0 == 1`, exit code stayed 0 -- the run continued instead of
  refusing). Restored the fix; both tests pass again, and the full suite
  is green.

## Concerns

None outstanding. The invalid-value/unparseable-file distinction is
deliberate and documented in both the code and this report; if a future
reviewer disagrees with keeping the invalid-value case non-fatal, the
change is a two-line `raise WizardError` in the `except typer.BadParameter`
branch of `_reader_from_env_file`, mirroring the one already made here.
