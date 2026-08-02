---
title: Findings
sidebar_position: 6
---

# Finding reference

Every message the validator produces carries a `FindingCode`. The code is the
finding's identity: it is stable, it is what tests and tooling key off, and it
is what to search for here. The wording of a message is prose for a human and
may be reworded at any time.

A finding also carries a `location` — the section, entity, view, column and
sub-key it is about — which is normally the dotted path the message opens with.

One row per code, and `test_every_code_is_documented` fails the build if a code
has no row or a row has no code.

| Code | Severity | What it means |
|---|---|---|
| `unclassified` | error | **Temporary.** A finding the code migration has not named yet. No rule produces this deliberately; its absence is how the migration is known to be finished. |
| `all_items_view_declared` | error | A view named `All Items` is declared; that view is generated with every rendered column and no filter, and cannot be overridden. |
| `calculated_column_has_no_formula` | error | A `calculated_*` DBML column has no matching entry under `calculated_formulas:`. |
| `calculated_display_column_unindexable` | warning | A lookup target's display column is calculated, and calculated columns cannot be indexed, so its picker stops working once the list passes roughly 5,000 items. |
| `calculated_formula_cycle` | error | Calculated columns on one entity depend on each other in a cycle, so no creation order can satisfy them. |
| `calculated_formula_deferred_lookup` | error | A calculated formula references a lookup the deploy defers to Phase 2. The calculated field is created in Phase 1, before that column exists. |
| `calculated_formula_missing_equals` | error | A calculated formula does not start with `=`. |
| `calculated_formula_self_reference` | error | A calculated formula references its own column. |
| `calculated_formula_too_long` | error | A calculated formula is longer than SharePoint's limit. |
| `calculated_formula_unknown_column` | error | A calculated formula references a column that is not rendered. SharePoint resolves references when the field is created and rejects the POST on any miss. |
| `calculated_formula_unsupported_operand` | error | A calculated formula references a Lookup, Person, multi-line-text, rich-text or Hyperlink column. Measured against a live site: SharePoint refuses all five when the field is created. |
| `column_not_rendered` | error | A name in the mapping is not a rendered column of the entity. Reached from a field set's members, a view's `fields`/`sort`/`group_by`, and a display-name override. |
| `composite_index_unsupported` | error | A DBML `indexes { }` entry names more than one column; the deployer can represent only a one-column index. |
| `cross_site_column_cannot_be_unique` | error | A cross-site reference column is marked `[unique]`. Its logical column is replaced by generated `Abbreviation` and `SiteUrl` fields, so the constraint would never be deployed. |
| `cross_site_column_has_no_ref` | error | A `cross_site_reference_columns:` entry names a column with no DBML `ref:`. |
| `cross_site_generated_name_collides` | error | A cross-site column's generated companion field has the same name as a column the DBML already declares. |
| `cross_site_generated_name_too_long` | error | A cross-site column's generated `Abbreviation` or `SiteUrl` field exceeds SharePoint's 32-character internal-name limit. |
| `cross_site_unknown_column` | error | A `cross_site_reference_columns:` entry names a column the entity's table does not declare. |
| `display_column_not_rendered` | error | A lookup target's `display_column` names a column the deploy never creates, so the automatic index would be created on a field that does not exist. |
| `display_column_type_unindexable` | error | A lookup target's `display_column` is a type SharePoint cannot index. The deploy sets `Indexed=true`, reads it back and aborts part-way through when it did not stick. |
| `display_title_too_long` | error | A display title exceeds SharePoint's 255-character bound. |
| `document_library_unsupported` | error | An entity declares `kind: DocumentLibrary`. A library's items are files and this tool writes list rows, so the kind is refused outright — see issue #14. |
| `duplicate_display_title` | error | Two columns of one entity resolve to the same display title, making them indistinguishable on every form and view. |
| `duplicate_index_target` | error | One table's `indexes { }` names the same column twice. |
| `duplicate_view_title` | error | Two views on one entity share a title, or differ only in case — SharePoint treats those as one view. |
| `duplicate_view_url_slug` | error | Two view titles collapse to the same `.aspx` URL slug, so the two view pages would fight over one page. |
| `empty_display_title` | error | A display-name override resolves to an empty title. |
| `empty_previous_title` | error | A `renamed_from` entry is blank. |
| `empty_view_url_slug` | error | A view title yields an empty URL slug; it needs at least one letter or digit. |
| `entity_not_in_schema` | error | The mapping's `entities:` declares a name the DBML schema has no table for. |
| `enum_members_differ` | error | A DBML enum's members differ from the choices configured for it in `enum_sources`. |
| `enum_source_has_no_dbml_enum` | warning | A configured `enum_sources` entry has no matching DBML enum in the schema. |
| `field_set_empty` | error | A field set declares no columns. |
| `field_set_name_has_marker` | error | A field set's name contains `@`, which is the marker a view's `fields` uses to reference a set. |
| `field_set_unreferenced` | warning | A field set is declared but no view on that entity expands it. |
| `formatter_field_not_displayed` | error | A view formatter references a real column the view does not display; a view formatter can only read columns in its own `fields`, so the format would never fire. |
| `formatter_field_not_rendered` | error | A view formatter references a column the entity does not render. |
| `formula_target_not_calculated` | error | A `calculated_formulas:` entry names a column that is not `calculated_text` or `calculated_number`. |
| `color_by_map_key_not_in_enum` | error | A `data-bar` `color_by` map names a choice the source column's enum does not contain. |
| `formatter_column_not_rendered` | error | A `column_formatting:` entry targets a column the entity does not render. |
| `formatter_missing_elmtype` | error | A column formatter's JSON has no root `elmType`, so it is not a SharePoint column-formatting object. |
| `form_columns_in_no_section` | warning | Columns are referenced by no form body section. SharePoint appends them to the last section, so the form still renders — but the declared arrangement stops being the deployed one. |
| `form_part_references_calculated_column` | error | A form header or footer references a calculated column. Calculated columns resolve to an empty string there, so the part renders blank with no error anywhere. |
| `form_section_entirely_hidden` | error | Every column in a form body section is declared `new: false` and `existing: false`, so the section renders as a bare heading. Not asserted of the last section, which is SharePoint's documented catch-all. |
| `form_section_field_not_rendered` | error | A form body section names a field the entity does not render. |
| `hide_is_unnecessary` | warning | `hide_from_all_items` is set on an entity whose `All Items` view is already within the join ceiling with nothing hidden. |
| `hide_of_cross_site_reference` | error | `hide_from_all_items` names a cross-site reference, which expands to a Choice + URL pair and costs no join operation. |
| `hide_of_non_join_bearing_column` | error | `hide_from_all_items` names a column that costs no join operation; only a join-bearing column may be hidden. |
| `hide_of_unrendered_column` | error | `hide_from_all_items` names a column the generated `All Items` view does not render — usually a typo. |
| `hide_without_all_items_view` | error | `hide_from_all_items` names a column on an entity for which no `All Items` view is generated at all, so the key would silently do nothing. |
| `index_column_not_rendered` | error | An `indexes { }` entry names a column the deploy never creates. |
| `index_column_type_unindexable` | error | An `indexes { }` entry names a column of a type SharePoint cannot index. |
| `index_duplicates_unique_column` | error | An `indexes { }` entry names a column that already carries an implicit index from its `[unique]` setting. |
| `index_limit_approaching` | warning | A list is at 18 or 19 of its 20 indexes. SharePoint creates indexes by itself — opening a sorted view on an unindexed column adds one — and those are invisible to this build, so leave headroom. |
| `index_limit_exceeded` | error | A list's effective indexes exceed SharePoint's limit of 20. The message names the implicit contributors, which are the ones an author cannot count. |
| `index_on_calculated_column` | error | An `indexes { }` entry names a calculated column. SharePoint accepts the flag and reads it back false. |
| `index_settings_unsupported` | error | A DBML index carries `name`, `unique`, `type`, `pk` or `note`. SharePoint exposes none of them, so declare a bare column index. |
| `invalid_condition` | error | The condition grammar rejected a declared `when:`. `conditions.py` has 28 distinct reasons behind this and reports them as prose. |
| `demo_column_not_writable` | error | A demo row writes a column the deploy does not create, or writes `Id`. |
| `demo_date_value_invalid` | error | A demo row's date value is neither `today+N`/`today-N` nor a real ISO calendar date. |
| `demo_enum_value_unknown` | error | A demo row's value is not a member of the column's enum. |
| `demo_hyperlink_address_invalid` | error | A demo row's hyperlink address is not a non-empty string. Checked as a string, not stringified — `str(None)` is `"None"`, which would deploy as a link pointing at the word None. |
| `demo_hyperlink_object_invalid` | error | A demo row's hyperlink object value is not `{url: <address>, description: <label>}` with `description` optional. |
| `demo_object_value_invalid` | error | A demo row's object value is not exactly `{demo_ref: <key>}`. |
| `demo_person_value_unsupported` | error | A demo row writes a person column with something other than `"@me"`, the deploying operator. |
| `demo_ref_forward_reference` | error | A self-referencing demo row's `demo_ref` names a row declared at or after it, so the target does not exist when the row is written. |
| `demo_ref_on_non_lookup` | error | A demo row uses `demo_ref` on a column that is not a lookup. |
| `demo_ref_target_mismatch` | error | A demo row's `demo_ref` resolves to a row of a different entity from the one the lookup targets. |
| `demo_ref_unknown_key` | error | A demo row's `demo_ref` names a key no demo row declares. |
| `demo_rows_on_document_library` | error | `demo_items:` seeds a `DocumentLibrary`. A library's items are files and seeding posts to `/items`, which SharePoint refuses outright — so the paste fails in front of whoever was being shown the demo. |
| `demo_title_missing_marker` | error | A demo row's `Title` does not start with `[DEMO] `, the marker the teardown trusts to tell demo rows from real records. |
| `demo_value_on_calculated_column` | error | A demo row writes a calculated column. Set its inputs instead. |
| `duplicate_demo_key` | error | Two demo rows share a key. Keys are global across entities because `demo_ref` resolves against all of them. |
| `join_threshold_approached` | warning | A view renders join-bearing columns at that ceiling, which held on the tenant measured but may not travel. |
| `join_threshold_exceeded` | error | A view renders more join-bearing columns than the measured ceiling of 12 join operations, and SharePoint returns the view blank at any list size. Reached from a declared view and from the generated `All Items` view. |
| `list_validation_formula_too_long` | error | A `list_validation:` rule renders to a formula longer than 1024 characters once display names are substituted. |
| `list_validation_message_too_long` | error | A `list_validation:` message is longer than 1024 characters. |
| `lookup_crosses_site_role` | error | A lookup's source and target entities map to different `site_role`s; a SharePoint lookup cannot span webs. |
| `lookup_display_column_unknown` | error | A lookup target declares a `display_column` that is not one of its columns, so the deploy would emit an unresolvable `LookupField`. |
| `lookup_would_render_blank` | error | A lookup target has no `Title` column and declares no `display_column`, so every lookup into it renders blank. |
| `multiple_default_views` | error | More than one view on an entity is marked default; a SharePoint list has exactly one. |
| `overdue_guard_field_not_rendered` | error | An `overdue-date` style's `guard.field` names a column the entity does not render. |
| `polymorphic_column_not_rendered` | error | A `polymorphic_patterns:` entry's `field` or `discriminator` names a column the deploy never creates. |
| `previous_title_claimed_twice` | error | Two views claim the same previous title. |
| `previous_title_is_a_current_title` | error | A `renamed_from` entry is another declared view's current title. |
| `previous_title_is_own_title` | error | A `renamed_from` entry repeats the view's own current title. |
| `previous_title_is_reserved` | error | A `renamed_from` entry claims `All Items`, which is reserved for the generated recovery view. |
| `redundant_display_column_acceptance` | warning | `accept_unindexable_display_column` is set on an entity with nothing to accept: nothing looks it up, or its display column is not calculated. |
| `retired_column_in_field_set` | warning | A field set names a retired column; retirement strips it from every view that expands the set, and the build continues. |
| `row_limit_out_of_range` | error | A view's `row_limit` is outside 1-5000. |
| `style_calculated_type_mismatch` | error | `calculated: true` is set on a style whose column is not the `calculated_*` type that style expects. |
| `style_map_key_not_in_enum` | error | A `severity` or `pill` map names a choice the column's enum does not contain. |
| `style_on_boolean_matches_nothing` | error | A `severity` or `pill` style sits on a Yes/No column. Both compare `@currentField` against quoted strings, so every branch is false and the cell renders unstyled — silently. |
| `style_requires_calculated` | error | A `severity`, `data-bar` or `overdue-date` style sits on the matching `calculated_*` column but does not set `calculated: true`, so SharePoint's typed formatter value is never decoded. |
| `total_column_not_displayed` | error | A `totals` entry names a column that is not one of the view's fields, so SharePoint has no column to put the figure under. |
| `total_needs_numeric_column` | error | A numeric-only total is declared on a non-numeric column. |
| `total_on_lookup_column` | error | A total other than `count` is declared on a lookup column, whose stored value is a row id rather than a quantity. |
| `total_on_non_arithmetic_column` | error | A total other than `count` is declared on a person, rich-text, long-text or hyperlink column. |
| `trend_against_not_rendered` | error | A `trend` style's `against` names a column the entity does not render. |
| `undeployable_column_declaration` | error | A per-column declaration targets `Title` or a SharePoint system column. The deploy never writes those properties, so the declaration would validate clean and do nothing. |
| `unindexed_filter_columns` | warning | A view's `where` filters on columns with no effective index, so past the list view threshold SharePoint may silently return a truncated answer. |
| `unknown_entity` | error | A mapping section names an entity the schema does not declare, or the mapping does not list. Reached from `views`, `field_sets`, `display_names`, `retention`, `watched_lists`, `polymorphic_patterns`, `versioning.overrides`, `cross_site_reference_columns`, `column_formatting`, `form_formatting`, `list_validation` and `demo_items` — the `location` says which. |
| `unknown_field_set_reference` | error | A view's `fields` references `@name`, but the entity declares no field set of that name. |
| `unknown_retention_policy` | error | A retention `list_defaults` entry names a policy that is not defined. |
| `unmapped_schema_table` | error | A DBML table has no `entities:` entry, so it would be dropped from the deploy plan without an error. |
| `unsupported_base_template` | error | An entity's `base_template` is not 100. The create call sends `BaseTemplate` and never sends `kind`, so any other number provisions a list the rest of the build does not model. |
| `watched_column_not_rendered` | error | A `watched_lists:` entry names a column the deploy never creates. |
| `width_column_not_displayed` | error | A `widths` entry names a column that is not one of the view's fields. |
| `width_out_of_range` | error | A column width is outside 16-2000 pixels. |
