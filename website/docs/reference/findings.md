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
| `unknown_entity` | error | A mapping section names an entity the schema does not declare, or the mapping does not list. Reached from `views`, `field_sets`, `display_names` and `retention` — the `location` says which. |
| `field_set_name_has_marker` | error | A field set's name contains `@`, which is the marker a view's `fields` uses to reference a set. |
| `field_set_empty` | error | A field set declares no columns. |
| `field_set_unreferenced` | warning | A field set is declared but no view on that entity expands it. |
| `retired_column_in_field_set` | warning | A field set names a retired column; retirement strips it from every view that expands the set, and the build continues. |
| `column_not_rendered` | error | A name in the mapping is not a rendered column of the entity. Reached from a field set's members, a view's `fields`/`sort`/`group_by`, and a display-name override. |
| `all_items_view_declared` | error | A view named `All Items` is declared; that view is generated with every rendered column and no filter, and cannot be overridden. |
| `duplicate_view_title` | error | Two views on one entity share a title, or differ only in case — SharePoint treats those as one view. |
| `duplicate_view_url_slug` | error | Two view titles collapse to the same `.aspx` URL slug, so the two view pages would fight over one page. |
| `empty_view_url_slug` | error | A view title yields an empty URL slug; it needs at least one letter or digit. |
| `multiple_default_views` | error | More than one view on an entity is marked default; a SharePoint list has exactly one. |
| `empty_previous_title` | error | A `renamed_from` entry is blank. |
| `previous_title_is_own_title` | error | A `renamed_from` entry repeats the view's own current title. |
| `previous_title_is_reserved` | error | A `renamed_from` entry claims `All Items`, which is reserved for the generated recovery view. |
| `previous_title_is_a_current_title` | error | A `renamed_from` entry is another declared view's current title. |
| `previous_title_claimed_twice` | error | Two views claim the same previous title. |
| `unknown_field_set_reference` | error | A view's `fields` references `@name`, but the entity declares no field set of that name. |
| `row_limit_out_of_range` | error | A view's `row_limit` is outside 1-5000. |
| `unindexed_filter_columns` | warning | A view's `where` filters on columns with no effective index, so past the list view threshold SharePoint may silently return a truncated answer. |
| `formatter_field_not_rendered` | error | A view formatter references a column the entity does not render. |
| `formatter_field_not_displayed` | error | A view formatter references a real column the view does not display; a view formatter can only read columns in its own `fields`, so the format would never fire. |
| `width_column_not_displayed` | error | A `widths` entry names a column that is not one of the view's fields. |
| `width_out_of_range` | error | A column width is outside 16-2000 pixels. |
| `total_column_not_displayed` | error | A `totals` entry names a column that is not one of the view's fields, so SharePoint has no column to put the figure under. |
| `total_on_lookup_column` | error | A total other than `count` is declared on a lookup column, whose stored value is a row id rather than a quantity. |
| `total_on_non_arithmetic_column` | error | A total other than `count` is declared on a person, rich-text, long-text or hyperlink column. |
| `total_needs_numeric_column` | error | A numeric-only total is declared on a non-numeric column. |
| `join_threshold_exceeded` | error | A view renders more join-bearing columns than the measured ceiling of 12 join operations, and SharePoint returns the view blank at any list size. Reached from a declared view and from the generated `All Items` view. |
| `join_threshold_approached` | warning | A view renders join-bearing columns at that ceiling, which held on the tenant measured but may not travel. |
| `hide_without_all_items_view` | error | `hide_from_all_items` names a column on an entity for which no `All Items` view is generated at all, so the key would silently do nothing. |
| `hide_of_cross_site_reference` | error | `hide_from_all_items` names a cross-site reference, which expands to a Choice + URL pair and costs no join operation. |
| `hide_of_unrendered_column` | error | `hide_from_all_items` names a column the generated `All Items` view does not render — usually a typo. |
| `hide_of_non_join_bearing_column` | error | `hide_from_all_items` names a column that costs no join operation; only a join-bearing column may be hidden. |
| `hide_is_unnecessary` | warning | `hide_from_all_items` is set on an entity whose `All Items` view is already within the join ceiling with nothing hidden. |
| `empty_display_title` | error | A display-name override resolves to an empty title. |
| `display_title_too_long` | error | A display title exceeds SharePoint's 255-character bound. |
| `duplicate_display_title` | error | Two columns of one entity resolve to the same display title, making them indistinguishable on every form and view. |
| `lookup_crosses_site_role` | error | A lookup's source and target entities map to different `site_role`s; a SharePoint lookup cannot span webs. |
| `lookup_display_column_unknown` | error | A lookup target declares a `display_column` that is not one of its columns, so the deploy would emit an unresolvable `LookupField`. |
| `lookup_would_render_blank` | error | A lookup target has no `Title` column and declares no `display_column`, so every lookup into it renders blank. |
| `unknown_retention_policy` | error | A retention `list_defaults` entry names a policy that is not defined. |
| `enum_source_has_no_dbml_enum` | warning | A configured `enum_sources` entry has no matching DBML enum in the schema. |
| `enum_members_differ` | error | A DBML enum's members differ from the choices configured for it in `enum_sources`. |
