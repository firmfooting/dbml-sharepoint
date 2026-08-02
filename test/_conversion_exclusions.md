# Sites excluded from the test-input fragment conversion

Consult this before converting any test input to the `_packs` helpers. Each
entry is here because a mechanical conversion would change behaviour, and in
most cases would do so **silently** — the test keeps passing against the wrong
input.

Anchored on **test function names**, not line numbers. The first version of this
list used line numbers and they had already drifted before it was executed, in
`test_jsgen.py`, because two unrelated merges landed in between.

This lives in `test/` rather than beside the plan because `docs/superpowers/` is
gitignored (see `.gitignore`) — a plan there is local to one machine, and this
list has to survive.

## A. Glued literals that form ONE logical line

Two adjacent string literals with **no `\n` between them** make a single
YAML/DBML line. Stacking them in a triple-quoted block inserts a newline and
changes the document. Convert these by joining the fragments into one line, or
leave them.

| File | Enclosing function | Tail of the glued fragment |
|---|---|---|
| `test_jsgen.py` | `_display_names_inputs` | `RiskScore: '=IF([MatrixVersion]="13.0",1,` |
| `test_jsgen.py` | `test_view_rows_carry_formatting_and_template_reconciles_it` | `additionalRowClass: "=if([$Score] >= 20, ` |
| `test_lookups.py` | `test_a_declared_display_column_wins` | `site_role: default, ` |
| `test_lookups.py` | `test_a_calculated_display_column_is_excluded` | `site_role: default, ` |
| `test_mapping_loader.py` | `test_entity_sub_keys_are_checked` | `site_role: default, ` |
| `test_mapping_loader.py` | `test_accept_unindexable_display_column_defaults_false_and_parses` | `site_role: default, ` |
| `test_validator_calculated.py` | `_display_type_inputs` | `site_role: default, ` |
| `test_validator_calculated.py` | `test_a_display_column_that_is_never_rendered_is_an_error` | `site_role: default, ` |
| `test_validator_calculated.py` | `test_a_pointless_acceptance_warns` | `site_role: default, ` |
| `test_validator_calculated.py` | `test_an_acceptance_on_an_unlooked_up_calculated_column_states_the_truth` | `site_role: default, ` |
| `test_validator_view_totals.py` | `_cross_site_only_target` | `site_role: default, ` |
| `test_validator_view_totals.py` | `test_a_calculated_display_column_does_not_count_as_an_index` | `site_role: default, ` |

Note `test_mapping_loader.test_entity_sub_keys_are_checked` contains a
**deliberate typo** (`display_colum`). It is the point of the test. Do not
correct it.

## B. `.replace()` needles — highest risk, now guarded

`str.replace` returns the input unchanged when the needle is absent, and raises
nothing. Re-indent the base document without adjusting the needle identically
and the test runs against the **unmodified** input and still passes.

These are routed through `_packs.replaced()`, which asserts the needle matched:

| File | Function | Base |
|---|---|---|
| `test_lookups.py` | `test_a_declared_display_column_wins` | `_PLAIN` |
| `test_lookups.py` | `test_a_calculated_display_column_is_excluded` | `_PLAIN` |
| `test_lookups.py` | `test_a_ref_target_unmapped_is_absent` | `_PLAIN` |
| `test_lookups.py` | (cross-site test) | `_CROSS_SITE_MAPPING` |
| `test_cli.py` | `test_malformed_dbml_is_a_message_not_a_traceback` | `simple.dbml` contents |
| `test_cli.py` | (second malformed-schema test) | `simple.dbml` contents |

The two `test_cli.py` needles match a line read out of
`test/fixtures/simple.dbml`. Their risk is not indentation — it is the fixture
changing underneath them.

`test_mapping_loader.py`'s `example.replace("<Entity>", "Project")` uses a
placeholder needle with no leading whitespace and is indentation-safe.

## C. Assertion and expected-output text — never convert

Glued runs in messages, expected CAML, and expected Markdown. Not file payloads.

`test_conditions.py` · `test_jsgen.py` (the `<Where>…`, `<GroupBy …>`,
`<Or><IsNull>…` expectations) · `test_rollbackgen.py` · `test_template_lint.py` ·
`test_template_standard.py` · `test_manifestgen.py` (retired-column table rows) ·
`test_deploy_runtime.py` · `test/manual/make_threshold_rows.py`

## D. Single-line sentinel files — leave as-is

`"stale"`, `"preserve me"`, `"mine"`, `"-- hand written"` and similar, mostly in
`test_bundle.py` and `test_cli.py`. Not DBML or YAML. `_packs` would append a
trailing newline they do not have, changing what the test asserts.

## E. Files with no write sites — nothing to convert

`test_template_standard.py`, `test_conditions.py`, `test_template_lint.py`,
`test_rollbackgen.py`, `test_icons.py`. Their fragments are all assertion text.

## F. Dynamic payloads — skip and report

f-strings, `+ variable`, and anything assembled in a loop or conditional. About
70 sites. Converting these needs judgement about what the interpolation means,
not a mechanical rewrite.

## Verifying a conversion

```bash
uv run pytest -n0 -q test/<file>.py     # pass count must not change
uv run pytest                            # full suite
uv run pytest --cov=src/dbml_sharepoint --cov-report=term -q | grep TOTAL
```

Coverage is the alarm that matters: a delta means a converted payload exercises
a different code path, so the input changed.

**The expected figure is `3666 182 95%`, and it is now deterministic.** It was
not, briefly: `conditions.py:713` — the "not a number" refusal — was reached
only when the property suite's permissive strategy happened to draw a `bool`,
about one run in ten. That produced a phantom one-line delta with a 1-in-10
false-positive rate, exactly where this document tells you to treat a delta as
a signal.

It was first misdiagnosed as a `-n auto` combine artefact. It reproduced
serially. Fixed at source by
`test_conditions_properties.test_a_bool_on_a_numeric_column_is_refused`, which
pins the line. If you see a one-line delta again, look for another
Hypothesis-reached line before assuming your conversion caused it — and check
serially, because parallelism was not the cause last time.
