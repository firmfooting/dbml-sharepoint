---
title: Live findings
sidebar_position: 90
---

<!-- markdownlint-disable MD013 -->

# Live findings

Every finding below is derived from an evidence package committed under `evidence/probes`, and every surface below is declared upstream in `SURFACES.md` whether or not anything has probed it yet. One row is one check: where a probe result and a reviewed capture answer the same check, they merge into a single row naming both lanes. A check is listed while it is still open, failed, void or referred to a human; settled checks are counted under their surface, not listed. Each row links to that check's own page, which carries the question it answers and the evidence behind it.

Runs: 140. Findings: 412. Captures superseded: 1.

Probes: 99. Probed: 74. Not yet probed: 25.

Checks with a probe result, not settled: 410 of 1814. Checks with a reviewed capture, not settled: 9 of 48.

## formula — 9 of 11 probes with evidence, 67 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [formula.datetime.client-now-rule](findings/datetime-sentinel-20260824-sandbox-1-formula-datetime-client-now-rule) | visible | needs-human | datetime-sentinel/20260824-sandbox-1 | unknown |
| [formula.datetime.control-today-allows-yesterday](findings/datetime-sentinel-20260824-sandbox-1-formula-datetime-control-today-allows-yesterday) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [formula.datetime.today-plus-one-allows-later-today](findings/datetime-sentinel-20260824-sandbox-1-formula-datetime-today-plus-one-allows-later-today) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [formula.datetime.today-rejects-earlier-today](findings/datetime-sentinel-20260824-sandbox-1-formula-datetime-today-rejects-earlier-today) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml-adhoc.now-element-discriminates](findings/datetime-sentinel-20260824-sandbox-1-query-caml-adhoc-now-element-discriminates) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml-adhoc.now-element-include-time-discriminates](findings/datetime-sentinel-20260824-sandbox-1-query-caml-adhoc-now-element-include-time-discriminates) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml-adhoc.today-element-date-granular](findings/datetime-sentinel-20260824-sandbox-1-query-caml-adhoc-today-element-date-granular) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml-adhoc.today-element-include-time-discriminates](findings/datetime-sentinel-20260824-sandbox-1-query-caml-adhoc-today-element-include-time-discriminates) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml.control-bogus-element-refused](findings/datetime-sentinel-20260824-sandbox-1-query-caml-control-bogus-element-refused) | machine | failed | datetime-sentinel/20260824-sandbox-1 | — |
| [query.view-query.today-include-time-roundtrip](findings/datetime-sentinel-20260824-sandbox-1-query-view-query-today-include-time-roundtrip) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.view-query.today-include-time-selects](findings/datetime-sentinel-20260824-sandbox-1-query-view-query-today-include-time-selects) | machine | open | datetime-sentinel/20260824-sandbox-1 | — |
| [query.caml.control-bogus-element-refused](findings/datetime-sentinel-20260902-post-fix-query-caml-control-bogus-element-refused) | machine | failed | datetime-sentinel/20260902-post-fix | — |
| [formula.datetime.today-plus-one-ceiling-tomorrow-night](findings/datetime-sentinel-20260902-rerun-eod-formula-datetime-today-plus-one-ceiling-tomorrow-night) | machine | open | datetime-sentinel/20260902-rerun-eod | — |
| [query.caml.control-bogus-element-refused](findings/datetime-sentinel-20260902-rerun-eod-query-caml-control-bogus-element-refused) | machine | failed | datetime-sentinel/20260902-rerun-eod | — |
| [formula.datetime.control-today-allows-yesterday](findings/datetime-sentinel-20260902-tz-gate-closed-formula-datetime-control-today-allows-yesterday) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [formula.datetime.today-plus-one-allows-later-today](findings/datetime-sentinel-20260902-tz-gate-closed-formula-datetime-today-plus-one-allows-later-today) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [formula.datetime.today-rejects-earlier-today](findings/datetime-sentinel-20260902-tz-gate-closed-formula-datetime-today-rejects-earlier-today) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.caml-adhoc.now-element-discriminates](findings/datetime-sentinel-20260902-tz-gate-closed-query-caml-adhoc-now-element-discriminates) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.caml-adhoc.now-element-include-time-discriminates](findings/datetime-sentinel-20260902-tz-gate-closed-query-caml-adhoc-now-element-include-time-discriminates) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.caml-adhoc.today-element-date-granular](findings/datetime-sentinel-20260902-tz-gate-closed-query-caml-adhoc-today-element-date-granular) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.caml-adhoc.today-element-include-time-discriminates](findings/datetime-sentinel-20260902-tz-gate-closed-query-caml-adhoc-today-element-include-time-discriminates) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.caml.control-bogus-element-refused](findings/datetime-sentinel-20260902-tz-gate-closed-query-caml-control-bogus-element-refused) | machine | failed | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.view-query.today-include-time-roundtrip](findings/datetime-sentinel-20260902-tz-gate-closed-query-view-query-today-include-time-roundtrip) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [query.view-query.today-include-time-selects](findings/datetime-sentinel-20260902-tz-gate-closed-query-view-query-today-include-time-selects) | machine | open | datetime-sentinel/20260902-tz-gate-closed | — |
| [formula.datetime.control-today-allows-yesterday](findings/datetime-sentinel-20260903-fixed-sources-rerun-formula-datetime-control-today-allows-yesterday) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [formula.datetime.today-plus-one-allows-later-today](findings/datetime-sentinel-20260903-fixed-sources-rerun-formula-datetime-today-plus-one-allows-later-today) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [formula.datetime.today-rejects-earlier-today](findings/datetime-sentinel-20260903-fixed-sources-rerun-formula-datetime-today-rejects-earlier-today) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.caml-adhoc.now-element-discriminates](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-caml-adhoc-now-element-discriminates) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.caml-adhoc.now-element-include-time-discriminates](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-caml-adhoc-now-element-include-time-discriminates) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.caml-adhoc.today-element-date-granular](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-caml-adhoc-today-element-date-granular) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.caml-adhoc.today-element-include-time-discriminates](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-caml-adhoc-today-element-include-time-discriminates) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.caml.control-bogus-element-refused](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-caml-control-bogus-element-refused) | machine | failed | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.view-query.today-include-time-roundtrip](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-view-query-today-include-time-roundtrip) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [query.view-query.today-include-time-selects](findings/datetime-sentinel-20260903-fixed-sources-rerun-query-view-query-today-include-time-selects) | machine | open | datetime-sentinel/20260903-fixed-sources-rerun | — |
| [formula.validation.form-edit-today-under-modified-rule](findings/form-validation-20260902-form-steps-formula-validation-form-edit-today-under-modified-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.form-edit-tomorrow-under-modified-rule](findings/form-validation-20260902-form-steps-formula-validation-form-edit-tomorrow-under-modified-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.form-new-today-under-modified-rule](findings/form-validation-20260902-form-steps-formula-validation-form-new-today-under-modified-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.form-new-today-under-today-rule](findings/form-validation-20260902-form-steps-formula-validation-form-new-today-under-today-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.form-new-tomorrow-under-modified-rule](findings/form-validation-20260902-form-steps-formula-validation-form-new-tomorrow-under-modified-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.form-new-tomorrow-under-today-rule](findings/form-validation-20260902-form-steps-formula-validation-form-new-tomorrow-under-today-rule) | machine | open | form-validation/20260902-form-steps | — |
| [formula.validation.fixture-form-rows-readback](findings/form-validation-20260902-setup-formula-validation-fixture-form-rows-readback) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.fixture-rules-readback](findings/form-validation-20260902-setup-formula-validation-fixture-rules-readback) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-edit-today-under-modified-rule](findings/form-validation-20260902-setup-formula-validation-form-edit-today-under-modified-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-edit-tomorrow-under-modified-rule](findings/form-validation-20260902-setup-formula-validation-form-edit-tomorrow-under-modified-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-new-today-under-modified-rule](findings/form-validation-20260902-setup-formula-validation-form-new-today-under-modified-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-new-today-under-today-rule](findings/form-validation-20260902-setup-formula-validation-form-new-today-under-today-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-new-tomorrow-under-modified-rule](findings/form-validation-20260902-setup-formula-validation-form-new-tomorrow-under-modified-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.form-new-tomorrow-under-today-rule](findings/form-validation-20260902-setup-formula-validation-form-new-tomorrow-under-today-rule) | machine | open | form-validation/20260902-setup | — |
| [formula.validation.bulk-edit-today-under-modified-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-bulk-edit-today-under-modified-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.form-edit-today-under-three-column-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-form-edit-today-under-three-column-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.form-edit-tomorrow-under-three-column-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-form-edit-tomorrow-under-three-column-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.form-new-prefilled-default-under-modified-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-form-new-prefilled-default-under-modified-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.grid-edit-today-under-modified-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-grid-edit-today-under-modified-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.grid-edit-tomorrow-under-modified-rule](findings/save-instant-paths-20260902-form-steps-formula-validation-grid-edit-tomorrow-under-modified-rule) | machine | open | save-instant-paths/20260902-form-steps | — |
| [formula.validation.bulk-edit-today-under-modified-rule](findings/save-instant-paths-20260902-setup-formula-validation-bulk-edit-today-under-modified-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.fixture-path-rows-readback](findings/save-instant-paths-20260902-setup-formula-validation-fixture-path-rows-readback) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.fixture-three-column-rule-readback](findings/save-instant-paths-20260902-setup-formula-validation-fixture-three-column-rule-readback) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.form-edit-today-under-three-column-rule](findings/save-instant-paths-20260902-setup-formula-validation-form-edit-today-under-three-column-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.form-edit-tomorrow-under-three-column-rule](findings/save-instant-paths-20260902-setup-formula-validation-form-edit-tomorrow-under-three-column-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.form-new-prefilled-default-under-modified-rule](findings/save-instant-paths-20260902-setup-formula-validation-form-new-prefilled-default-under-modified-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.grid-edit-today-under-modified-rule](findings/save-instant-paths-20260902-setup-formula-validation-grid-edit-today-under-modified-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [formula.validation.grid-edit-tomorrow-under-modified-rule](findings/save-instant-paths-20260902-setup-formula-validation-grid-edit-tomorrow-under-modified-rule) | machine | open | save-instant-paths/20260902-setup | — |
| [query.caml-adhoc.today-element-site-date](findings/today-source-20260902-first-contact-query-caml-adhoc-today-element-site-date) | machine | failed | today-source/20260902-first-contact | — |
| [query.caml-adhoc.today-offset-element-previous-day](findings/today-source-20260902-first-contact-query-caml-adhoc-today-offset-element-previous-day) | machine | failed | today-source/20260902-first-contact | — |
| [field.date.dynamic-default-rest-fill](findings/today-source-20260919-d52f44c7-field-date-dynamic-default-rest-fill) | machine | open | today-source/20260919-d52f44c7 | — |
| [query.caml-adhoc.today-element-site-date](findings/today-source-20260919-d52f44c7-query-caml-adhoc-today-element-site-date) | machine | open | today-source/20260919-d52f44c7 | — |
| [query.caml-adhoc.today-element-vs-today-function](findings/today-source-20260919-d52f44c7-query-caml-adhoc-today-element-vs-today-function) | machine | open | today-source/20260919-d52f44c7 | — |

301 further checks in this surface are settled.

Not yet probed: `hyperlink-validation-operand-probe.js`, `blank-operand-probe.js`.

## expression — no evidence

Not yet probed: `expression-text-operators-probe.js`, `form-visibility-evidence-probe.js`.

## query — 2 of 3 probes with evidence, 9 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [view.filter-editor.and-chain-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-and-chain-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.mixed-group-left-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-mixed-group-left-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.mixed-group-right-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-mixed-group-right-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.or-chain-with-isnull-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-or-chain-with-isnull-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.readonlyview-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-readonlyview-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.smallest-mixed-tree-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-smallest-mixed-tree-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.filter-editor.ui-chain-40](findings/caml-chain-depth-20260828-run-view-filter-editor-ui-chain-40) | machine, visible | needs-human | caml-chain-depth/20260828-run | site-owner |
| [view.filter-editor.wrapper-group-left-editable](findings/caml-chain-depth-20260828-run-view-filter-editor-wrapper-group-left-editable) | machine | open | caml-chain-depth/20260828-run | — |
| [view.view-page.chain-40-rows-listed](findings/caml-chain-depth-20260828-run-view-view-page-chain-40-rows-listed) | machine | open | caml-chain-depth/20260828-run | — |

48 further checks in this surface are settled.

Not yet probed: `calculated-filter-probe.js`.

## view — 2 of 2 probes with evidence, 6 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [view-aggregations-totals](findings/view-aggregations-20260827-totals-view-aggregations-totals) | visible | needs-human | view-aggregations/20260827-totals | unknown |
| [view.totals.binds-by-internal-name](findings/view-aggregations-20260827-totals-view-totals-binds-by-internal-name) | machine | open | view-aggregations/20260827-totals | — |
| [view.totals.row-renders](findings/view-aggregations-20260827-totals-view-totals-row-renders) | machine | open | view-aggregations/20260827-totals | — |
| [view.totals.two-columns-in-order](findings/view-aggregations-20260827-totals-view-totals-two-columns-in-order) | machine | open | view-aggregations/20260827-totals | — |
| [view.filter-editor.ground-truth-guarded-refused](findings/view-edit-page-20260828-run-3-view-filter-editor-ground-truth-guarded-refused) | machine | open | view-edit-page/20260828-run-3 | — |
| [view.filter-editor.ground-truth-plain-editable](findings/view-edit-page-20260828-run-3-view-filter-editor-ground-truth-plain-editable) | machine | open | view-edit-page/20260828-run-3 | — |

27 further checks in this surface are settled.

## form — 1 of 3 probes with evidence, 16 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [form.panel.edit-columns-writes-attributes](findings/form-visibility-20260824-three-form-matrix-form-panel-edit-columns-writes-attributes) | machine | open | form-visibility/20260824-three-form-matrix | — |
| [form.edit-form.independent-of-new-form](findings/form-visibility-20260919-8983fbf3-form-edit-form-independent-of-new-form) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.new-form.attribute-at-creation](findings/form-visibility-20260919-8983fbf3-form-new-form-attribute-at-creation) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.new-form.setter-on-calculated-column](findings/form-visibility-20260919-8983fbf3-form-new-form-setter-on-calculated-column) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.new-form.setter-on-sealed-field](findings/form-visibility-20260919-8983fbf3-form-new-form-setter-on-sealed-field) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.new-form.setter-persists-without-update](findings/form-visibility-20260919-8983fbf3-form-new-form-setter-persists-without-update) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.new-form.setter-reshows-hidden](findings/form-visibility-20260919-8983fbf3-form-new-form-setter-reshows-hidden) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.panel.edit-columns-writes-attributes](findings/form-visibility-20260919-8983fbf3-form-panel-edit-columns-writes-attributes) | machine | open | form-visibility/20260919-8983fbf3 | — |
| [form.panel.edit-columns-writes-attributes](findings/form-visibility-20260919-abf10e2c-form-panel-edit-columns-writes-attributes) | machine | open | form-visibility/20260919-abf10e2c | — |
| [form.edit-form.independent-of-new-form](findings/form-visibility-20260919-dd6dca5f-form-edit-form-independent-of-new-form) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.new-form.attribute-at-creation](findings/form-visibility-20260919-dd6dca5f-form-new-form-attribute-at-creation) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.new-form.setter-on-calculated-column](findings/form-visibility-20260919-dd6dca5f-form-new-form-setter-on-calculated-column) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.new-form.setter-on-sealed-field](findings/form-visibility-20260919-dd6dca5f-form-new-form-setter-on-sealed-field) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.new-form.setter-persists-without-update](findings/form-visibility-20260919-dd6dca5f-form-new-form-setter-persists-without-update) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.new-form.setter-reshows-hidden](findings/form-visibility-20260919-dd6dca5f-form-new-form-setter-reshows-hidden) | machine | open | form-visibility/20260919-dd6dca5f | — |
| [form.panel.edit-columns-writes-attributes](findings/form-visibility-20260919-dd6dca5f-form-panel-edit-columns-writes-attributes) | machine | open | form-visibility/20260919-dd6dca5f | — |

15 further checks in this surface are settled.

Not yet probed: `form-visibility-interactive.js`, `form-visibility-storage-probe.js`.

## field — 15 of 19 probes with evidence, 23 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [D1](findings/date-storage-20260902-default-reads-d1) | machine | failed | date-storage/20260902-default-reads | — |
| [D2](findings/date-storage-20260902-default-reads-d2) | machine | failed | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-default-filled](findings/date-storage-20260902-default-reads-field-date-stored-instant-default-filled) | machine | open | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-form-picked](findings/date-storage-20260902-default-reads-field-date-stored-instant-form-picked) | machine | open | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-default-filled](findings/date-storage-20260902-sandbox-reads-field-date-stored-instant-default-filled) | machine | open | date-storage/20260902-sandbox-reads | — |
| [field.date.stored-instant-form-picked](findings/date-storage-20260902-sandbox-reads-field-date-stored-instant-form-picked) | machine | open | date-storage/20260902-sandbox-reads | — |
| [field.date.stored-instant-default-filled](findings/date-storage-20260919-f44157df-field-date-stored-instant-default-filled) | machine | failed | date-storage/20260919-f44157df | — |
| [field.date.stored-instant-form-picked](findings/date-storage-20260919-f44157df-field-date-stored-instant-form-picked) | machine | failed | date-storage/20260919-f44157df | — |
| [field.lookup.showfield-display-name-spelling](findings/lookup-showfield-20260919-49b8f670-field-lookup-showfield-display-name-spelling) | machine | open | lookup-showfield/20260919-49b8f670 | — |
| [field.lookup.showfield-edit-form](findings/lookup-showfield-20260919-49b8f670-field-lookup-showfield-edit-form) | machine | open | lookup-showfield/20260919-49b8f670 | — |
| [field.lookup.showfield-display-name-spelling](findings/lookup-showfield-20260920-41641bfa-field-lookup-showfield-display-name-spelling) | machine | open | lookup-showfield/20260920-41641bfa | — |
| [field.lookup.showfield-edit-form](findings/lookup-showfield-20260920-41641bfa-field-lookup-showfield-edit-form) | machine | open | lookup-showfield/20260920-41641bfa | — |
| [field.multichoice.severity-formatter-render](findings/multi-value-20260828-initial-field-multichoice-severity-formatter-render) | machine | open | multi-value/20260828-initial | — |
| [query.view-query.multichoice-chain-selects](findings/multi-value-20260828-initial-query-view-query-multichoice-chain-selects) | machine | open | multi-value/20260828-initial | — |
| [query.view-query.multichoice-membership-selects](findings/multi-value-20260828-initial-query-view-query-multichoice-membership-selects) | machine | open | multi-value/20260828-initial | — |
| [field.date.control-site-time-zone](findings/site-zone-transitions-20260919-5c27debf-field-date-control-site-time-zone) | machine | open | site-zone-transitions/20260919-5c27debf | — |
| [field.date.control-utctolocaltime-answers](findings/site-zone-transitions-20260919-5c27debf-field-date-control-utctolocaltime-answers) | machine | open | site-zone-transitions/20260919-5c27debf | — |
| [field.date.shipped-offsets-match-site-biases](findings/site-zone-transitions-20260919-5c27debf-field-date-shipped-offsets-match-site-biases) | machine | open | site-zone-transitions/20260919-5c27debf | — |
| [field.date.shipped-transition-offset-after](findings/site-zone-transitions-20260919-5c27debf-field-date-shipped-transition-offset-after) | machine | open | site-zone-transitions/20260919-5c27debf | — |
| [field.date.shipped-transition-offset-before](findings/site-zone-transitions-20260919-5c27debf-field-date-shipped-transition-offset-before) | machine | open | site-zone-transitions/20260919-5c27debf | — |
| [field.date.shipped-offsets-match-site-biases](findings/site-zone-transitions-20260919-a955cb73-field-date-shipped-offsets-match-site-biases) | machine | failed | site-zone-transitions/20260919-a955cb73 | — |
| [field.date.shipped-transition-offset-after](findings/site-zone-transitions-20260919-a955cb73-field-date-shipped-transition-offset-after) | machine | failed | site-zone-transitions/20260919-a955cb73 | — |
| [field.date.shipped-transition-offset-before](findings/site-zone-transitions-20260919-a955cb73-field-date-shipped-transition-offset-before) | machine | failed | site-zone-transitions/20260919-a955cb73 | — |

229 further checks in this surface are settled.

Not yet probed: `list-settings-probe.js`, `multilookup-probe.js`, `unique-transition-probe.js`, `calculated-date-rest-probe.js`.

## text — 4 of 5 probes with evidence, 2 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [text.group-desc.length-ceiling](findings/group-description-20260828-initial-text-group-desc-length-ceiling) | machine | failed | group-description/20260828-initial | — |
| [text.role-desc.length-ceiling](findings/role-definition-20260903-sandbox-text-role-desc-length-ceiling) | machine | failed | role-definition/20260903-sandbox | — |

64 further checks in this surface are settled.

Not yet probed: `item-text-roundtrip-probe.js`.

## access — 5 of 9 probes with evidence, 34 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [access.built-in-level.administrator-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-administrator-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.contributor-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-contributor-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.editor-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-editor-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.guest-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-guest-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.masquerade-delete-guarded](findings/built-in-levels-20260919-03432e71-access-built-in-level-masquerade-delete-guarded) | machine | void | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.reader-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-reader-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.built-in-level.webdesigner-deletable](findings/built-in-levels-20260919-03432e71-access-built-in-level-webdesigner-deletable) | machine | open | built-in-levels/20260919-03432e71 | — |
| [access.effective-perms.list-scope-viewlistitems](findings/enterprise-reader-20260828-initial-access-effective-perms-list-scope-viewlistitems) | machine | open | enterprise-reader/20260828-initial | — |
| [access.effective-perms.web-scope-useremoteapis](findings/enterprise-reader-20260828-initial-access-effective-perms-web-scope-useremoteapis) | machine | open | enterprise-reader/20260828-initial | — |
| [access.group.members-at-top-5000](findings/enterprise-reader-20260828-initial-access-group-members-at-top-5000) | machine | open | enterprise-reader/20260828-initial | — |
| [access.group.members-next-link-second-page](findings/enterprise-reader-20260828-initial-access-group-members-next-link-second-page) | machine | open | enterprise-reader/20260828-initial | — |
| [access.group.members-no-top-next-link](findings/enterprise-reader-20260828-initial-access-group-members-no-top-next-link) | machine | open | enterprise-reader/20260828-initial | — |
| [access.principal.reader-resolves-readonly](findings/enterprise-reader-20260828-initial-access-principal-reader-resolves-readonly) | machine | open | enterprise-reader/20260828-initial | — |
| [access.lookup-acl.control-source-readable](findings/lookup-acl-20260828-initial-access-lookup-acl-control-source-readable) | machine | open | lookup-acl/20260828-initial | — |
| [access.lookup-acl.control-target-denied](findings/lookup-acl-20260828-initial-access-lookup-acl-control-target-denied) | machine | open | lookup-acl/20260828-initial | — |
| [access.lookup-acl.display-value-to-denied-reader](findings/lookup-acl-20260828-initial-access-lookup-acl-display-value-to-denied-reader) | machine | open | lookup-acl/20260828-initial | — |
| [access.lookup-acl.expand-reaches-other-columns](findings/lookup-acl-20260828-initial-access-lookup-acl-expand-reaches-other-columns) | machine | open | lookup-acl/20260828-initial | — |
| [field.lookup.picker-omits-empty-label](findings/lookup-acl-20260828-initial-field-lookup-picker-omits-empty-label) | machine | open | lookup-acl/20260828-initial | — |
| [access.lookup-acl.control-source-readable](findings/lookup-acl-20260919-5e0bfb00-access-lookup-acl-control-source-readable) | machine | open | lookup-acl/20260919-5e0bfb00 | — |
| [access.lookup-acl.control-target-denied](findings/lookup-acl-20260919-5e0bfb00-access-lookup-acl-control-target-denied) | machine | open | lookup-acl/20260919-5e0bfb00 | — |
| [access.lookup-acl.display-value-to-denied-reader](findings/lookup-acl-20260919-5e0bfb00-access-lookup-acl-display-value-to-denied-reader) | machine | open | lookup-acl/20260919-5e0bfb00 | — |
| [access.lookup-acl.expand-reaches-other-columns](findings/lookup-acl-20260919-5e0bfb00-access-lookup-acl-expand-reaches-other-columns) | machine | open | lookup-acl/20260919-5e0bfb00 | — |
| [field.lookup.picker-omits-empty-label](findings/lookup-acl-20260919-5e0bfb00-field-lookup-picker-omits-empty-label) | machine | open | lookup-acl/20260919-5e0bfb00 | — |
| [access.lookup-acl.control-target-denied](findings/lookup-acl-20260919-b2fb1755-access-lookup-acl-control-target-denied) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [access.lookup-acl.display-value-to-denied-reader](findings/lookup-acl-20260919-b2fb1755-access-lookup-acl-display-value-to-denied-reader) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [access.lookup-acl.expand-reaches-other-columns](findings/lookup-acl-20260919-b2fb1755-access-lookup-acl-expand-reaches-other-columns) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [field.lookup.calculated-display-field](findings/lookup-acl-20260919-b2fb1755-field-lookup-calculated-display-field) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [field.lookup.empty-label-linked-readback](findings/lookup-acl-20260919-b2fb1755-field-lookup-empty-label-linked-readback) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [field.lookup.picker-omits-empty-label](findings/lookup-acl-20260919-b2fb1755-field-lookup-picker-omits-empty-label) | machine | open | lookup-acl/20260919-b2fb1755 | — |
| [access.role-binding.web-scope-by-group](findings/reader-bindings-20260902-reader-run-access-role-binding-web-scope-by-group) | machine | open | reader-bindings/20260902-reader-run | — |
| [access.role-binding.control-web-roleassignments-readable](findings/reader-bindings-20260903-void-differential-access-role-binding-control-web-roleassignments-readable) | machine | failed | reader-bindings/20260903-void-differential | — |
| [access.role-binding.web-scope-by-group](findings/reader-bindings-20260903-void-differential-access-role-binding-web-scope-by-group) | machine, visible | void | reader-bindings/20260903-void-differential | reader |
| [access.principal.person-column-ids-resolve](findings/siteuserinfolist-20260902-initial-access-principal-person-column-ids-resolve) | machine | open | siteuserinfolist/20260902-initial | — |
| [access.principal.person-column-ids-resolve](findings/siteuserinfolist-20260919-23666adc-access-principal-person-column-ids-resolve) | machine | open | siteuserinfolist/20260919-23666adc | — |

65 further checks in this surface are settled.

Not yet probed: `operator-safety-grant-probe.js`, `last-binding-removal-probe.js`, `item-access-probe.js`, `items-role-assignments-probe.js`.

## scale — 2 of 2 probes with evidence, 24 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [scale.index.odata-comparison-found-list](findings/native-index-20260828-initial-scale-index-odata-comparison-found-list) | machine | open | native-index/20260828-initial | — |
| [scale.index.odata-null-found-list](findings/native-index-20260828-initial-scale-index-odata-null-found-list) | machine | open | native-index/20260828-initial | — |
| [scale.native-idx.author-property](findings/native-index-20260828-initial-scale-native-idx-author-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.control-index-readable](findings/native-index-20260828-initial-scale-native-idx-control-index-readable) | machine | failed | native-index/20260828-initial | — |
| [scale.native-idx.created-property](findings/native-index-20260828-initial-scale-native-idx-created-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.editor-property](findings/native-index-20260828-initial-scale-native-idx-editor-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.modified-property](findings/native-index-20260828-initial-scale-native-idx-modified-property) | machine | void | native-index/20260828-initial | — |
| [scale.index.odata-comparison-found-list](findings/native-index-20260919-24bb42c1-scale-index-odata-comparison-found-list) | machine | open | native-index/20260919-24bb42c1 | — |
| [scale.index.odata-null-found-list](findings/native-index-20260919-24bb42c1-scale-index-odata-null-found-list) | machine | open | native-index/20260919-24bb42c1 | — |
| [scale.native-idx.author-property](findings/native-index-20260919-24bb42c1-scale-native-idx-author-property) | machine | void | native-index/20260919-24bb42c1 | — |
| [scale.native-idx.control-index-readable](findings/native-index-20260919-24bb42c1-scale-native-idx-control-index-readable) | machine | failed | native-index/20260919-24bb42c1 | — |
| [scale.native-idx.created-property](findings/native-index-20260919-24bb42c1-scale-native-idx-created-property) | machine | void | native-index/20260919-24bb42c1 | — |
| [scale.native-idx.editor-property](findings/native-index-20260919-24bb42c1-scale-native-idx-editor-property) | machine | void | native-index/20260919-24bb42c1 | — |
| [scale.native-idx.modified-property](findings/native-index-20260919-24bb42c1-scale-native-idx-modified-property) | machine | void | native-index/20260919-24bb42c1 | — |
| [scale.index.caml-isnotnull-unindexed-datetime](findings/threshold-index-20260827-272-guard-scale-index-caml-isnotnull-unindexed-datetime) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.index.target-status-filter](findings/threshold-index-20260827-272-guard-scale-index-target-status-filter) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.join.created-by-counts-as-join](findings/threshold-index-20260827-272-guard-scale-join-created-by-counts-as-join) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.join.lookup-column-ceiling](findings/threshold-index-20260827-272-guard-scale-join-lookup-column-ceiling) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.join.modified-by-counts-as-join](findings/threshold-index-20260827-272-guard-scale-join-modified-by-counts-as-join) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.join.person-counts-as-join](findings/threshold-index-20260827-272-guard-scale-join-person-counts-as-join) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.join.projected-field-costs-a-join](findings/threshold-index-20260827-272-guard-scale-join-projected-field-costs-a-join) | machine | open | threshold-index/20260827-272-guard | — |
| [scale.threshold.guarded-comparison-unindexed-text](findings/threshold-index-20260827-272-guard-scale-threshold-guarded-comparison-unindexed-text) | machine | open | threshold-index/20260827-272-guard | — |
| [view.filter-editor.negated-clause-rows](findings/threshold-index-20260827-272-guard-view-filter-editor-negated-clause-rows) | machine | open | threshold-index/20260827-272-guard | — |
| [view.filter-editor.plain-clause-rows](findings/threshold-index-20260827-272-guard-view-filter-editor-plain-clause-rows) | machine | open | threshold-index/20260827-272-guard | — |

49 further checks in this surface are settled.

## search — 1 of 1 probes with evidence, 5 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [query.odata.continuation-link-emitted](findings/search-discovery-20260828-initial-query-odata-continuation-link-emitted) | machine | open | search-discovery/20260828-initial | — |
| [query.odata.continuation-link-followed](findings/search-discovery-20260828-initial-query-odata-continuation-link-followed) | machine | open | search-discovery/20260828-initial | — |
| [search.discovery.security-trimming](findings/search-discovery-20260828-initial-search-discovery-security-trimming) | machine | open | search-discovery/20260828-initial | — |
| [search.discovery.title-match-exactness](findings/search-discovery-20260828-initial-search-discovery-title-match-exactness) | machine | open | search-discovery/20260828-initial | — |
| [search.managed-prop.description-marker-spelling](findings/search-discovery-20260828-initial-search-managed-prop-description-marker-spelling) | machine | open | search-discovery/20260828-initial | — |

9 further checks in this surface are settled.

## library — 31 of 38 probes with evidence, 225 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [library.lookup.picker-enumerates-files](findings/cross-lookup-20260907-sandbox-library-lookup-picker-enumerates-files) | machine | open | cross-lookup/20260907-sandbox | — |
| [library.lookup.picker-enumerates-files](findings/cross-lookup-20260919-0ab4ea77-library-lookup-picker-enumerates-files) | machine | open | cross-lookup/20260919-0ab4ea77 | — |
| [library.lookup.library-to-list-indexed](findings/cross-lookup-20260920-9abc51a5-library-lookup-library-to-list-indexed) | machine | open | cross-lookup/20260920-9abc51a5 | — |
| [library.lookup.list-to-library-indexed](findings/cross-lookup-20260920-9abc51a5-library-lookup-list-to-library-indexed) | machine | open | cross-lookup/20260920-9abc51a5 | — |
| [library.lookup.picker-enumerates-files](findings/cross-lookup-20260920-9abc51a5-library-lookup-picker-enumerates-files) | machine | open | cross-lookup/20260920-9abc51a5 | — |
| [library.access.unique-permissions-library](findings/library-access-20260903-sandbox-library-access-unique-permissions-library) | machine | open | library-access/20260903-sandbox | — |
| [library.view.group-by-multi-value-lookup](findings/library-grouping-20260908-sandbox-library-view-group-by-multi-value-lookup) | machine | open | library-grouping/20260908-sandbox | — |
| [library.index.control-small-library-shapes](findings/library-index-threshold-20260919-09e019fe-library-index-control-small-library-shapes) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.control-threshold-id-served](findings/library-index-threshold-20260919-09e019fe-library-index-control-threshold-id-served) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.control-unindexed-person-refused](findings/library-index-threshold-20260919-09e019fe-library-index-control-unindexed-person-refused) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.control-unindexed-refused](findings/library-index-threshold-20260919-09e019fe-library-index-control-unindexed-refused) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.fixture-file-count](findings/library-index-threshold-20260919-09e019fe-library-index-fixture-file-count) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.fixture-target-seeded](findings/library-index-threshold-20260919-09e019fe-library-index-fixture-target-seeded) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-author](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-author) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-created](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-created) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-editor](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-editor) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-modified](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-modified) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-name](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-name) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.threshold-filter-title](findings/library-index-threshold-20260919-09e019fe-library-index-threshold-filter-title) | machine | open | library-index-threshold/20260919-09e019fe | — |
| [library.index.control-small-library-shapes](findings/library-index-threshold-20260919-4cf09602-library-index-control-small-library-shapes) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.control-threshold-id-served](findings/library-index-threshold-20260919-4cf09602-library-index-control-threshold-id-served) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.control-unindexed-person-refused](findings/library-index-threshold-20260919-4cf09602-library-index-control-unindexed-person-refused) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.control-unindexed-refused](findings/library-index-threshold-20260919-4cf09602-library-index-control-unindexed-refused) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.fixture-file-count](findings/library-index-threshold-20260919-4cf09602-library-index-fixture-file-count) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.fixture-target-seeded](findings/library-index-threshold-20260919-4cf09602-library-index-fixture-target-seeded) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-author](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-author) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-created](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-created) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-editor](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-editor) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-modified](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-modified) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-name](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-name) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.threshold-filter-title](findings/library-index-threshold-20260919-4cf09602-library-index-threshold-filter-title) | machine | open | library-index-threshold/20260919-4cf09602 | — |
| [library.index.control-small-library-shapes](findings/library-index-threshold-20260919-dd817683-library-index-control-small-library-shapes) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.control-threshold-id-served](findings/library-index-threshold-20260919-dd817683-library-index-control-threshold-id-served) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.control-unindexed-person-refused](findings/library-index-threshold-20260919-dd817683-library-index-control-unindexed-person-refused) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.control-unindexed-refused](findings/library-index-threshold-20260919-dd817683-library-index-control-unindexed-refused) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.fixture-file-count](findings/library-index-threshold-20260919-dd817683-library-index-fixture-file-count) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.fixture-target-seeded](findings/library-index-threshold-20260919-dd817683-library-index-fixture-target-seeded) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-author](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-author) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-created](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-created) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-editor](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-editor) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-modified](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-modified) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-name](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-name) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.index.threshold-filter-title](findings/library-index-threshold-20260919-dd817683-library-index-threshold-filter-title) | machine | open | library-index-threshold/20260919-dd817683 | — |
| [library.large-list.control-group-by-single-value-column](findings/library-large-list-calculated-20260908-sandbox-library-large-list-control-group-by-single-value-column) | machine | failed | library-large-list-calculated/20260908-sandbox | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-calculated-20260908-sandbox-library-large-list-control-missing-group-column-ungrouped) | machine | failed | library-large-list-calculated/20260908-sandbox | — |
| [library.large-list.group-by-calculated-value](findings/library-large-list-calculated-20260908-sandbox-library-large-list-group-by-calculated-value) | machine | void | library-large-list-calculated/20260908-sandbox | — |
| [library.large-list.control-unindexed-filter-refused](findings/library-large-list-calculated-20260919-a353a14d-library-large-list-control-unindexed-filter-refused) | machine | open | library-large-list-calculated/20260919-a353a14d | — |
| [library.large-list.filter-on-calculated-value](findings/library-large-list-calculated-20260919-a353a14d-library-large-list-filter-on-calculated-value) | machine | void | library-large-list-calculated/20260919-a353a14d | — |
| [library.large-list.ui-group-by-multilevel-renders](findings/library-large-list-foldered-group-view-20260909-sandbox-library-large-list-ui-group-by-multilevel-renders) | machine, visible | needs-human | library-large-list-foldered-group-view/20260909-sandbox | site-owner |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-foldered-group-view-20260909-sandbox-library-large-list-ui-threshold-banner-text) | machine, visible | needs-human | library-large-list-foldered-group-view/20260909-sandbox | site-owner |
| [library.large-list.control-ui-folder-scope-rendered](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-control-ui-folder-scope-rendered) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.control-ui-foldered-page-identity](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-control-ui-foldered-page-identity) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.ui-group-by-multilevel-renders](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-ui-group-by-multilevel-renders) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-foldered-group-view-20260909-sandbox-rest-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-foldered-group-view/20260909-sandbox-rest | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-foldered-group-view-20260919-4d3074e0-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-foldered-group-view/20260919-4d3074e0 | — |
| [library.large-list.ui-group-by-multilevel-renders](findings/library-large-list-foldered-group-view-20260919-4d3074e0-library-large-list-ui-group-by-multilevel-renders) | machine | open | library-large-list-foldered-group-view/20260919-4d3074e0 | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-foldered-group-view-20260919-4d3074e0-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-foldered-group-view/20260919-4d3074e0 | — |
| [library.large-list.control-ui-folder-scope-rendered](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-control-ui-folder-scope-rendered) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.control-ui-foldered-page-identity](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-control-ui-foldered-page-identity) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.ui-group-by-multilevel-renders](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-ui-group-by-multilevel-renders) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-foldered-group-view-20260919-d196194e-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-foldered-group-view/20260919-d196194e | — |
| [library.large-list.control-foldered-folder-path-narrows](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-foldered-folder-path-narrows) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-foldered-group-by-narrowed-honoured](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-foldered-group-by-narrowed-honoured) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-foldered-id-query-served](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-foldered-id-query-served) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-foldered-render-where-absent-refused](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-foldered-render-where-absent-refused) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-foldered-unindexed-filter-refused](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-foldered-unindexed-filter-refused) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-multilevel-single-level-honoured](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-multilevel-single-level-honoured) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-ui-folder-scope-rendered](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-ui-folder-scope-rendered) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-ui-foldered-default-view-unchanged](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-ui-foldered-default-view-unchanged) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-ui-foldered-fixture-readable-after-view-writes](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-ui-foldered-fixture-readable-after-view-writes) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-ui-foldered-page-identity](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-ui-foldered-page-identity) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-foldered-file-count](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-foldered-file-count) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-foldered-folder-counts](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-foldered-folder-counts) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-foldered-index-written-under-threshold](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-foldered-index-written-under-threshold) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-foldered-ui-views-created](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-foldered-ui-views-created) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-foldered-witness-unindexed](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-foldered-witness-unindexed) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-multilevel-file-count](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-multilevel-file-count) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.fixture-multilevel-under-threshold](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-fixture-multilevel-under-threshold) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.foldered-group-by-folder-scoped](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-foldered-group-by-folder-scoped) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.foldered-group-by-folder-scoped-counts](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-foldered-group-by-folder-scoped-counts) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.foldered-group-by-refusal-signature](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-foldered-group-by-refusal-signature) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.foldered-group-by-root-scoped](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-foldered-group-by-root-scoped) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.multilevel-group-by-three-levels](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-multilevel-group-by-three-levels) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.multilevel-group-by-two-levels](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-multilevel-group-by-two-levels) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.ui-group-by-multilevel-renders](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-ui-group-by-multilevel-renders) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-foldered-group-view-20260919-dc09886a-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-foldered-group-view/20260919-dc09886a | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-group-view-20260908-sandbox-library-large-list-control-missing-group-column-ungrouped) | machine | failed | library-large-list-group-view/20260908-sandbox | — |
| [library.large-list.filtered-group-by-past-threshold](findings/library-large-list-group-view-20260908-sandbox-library-large-list-filtered-group-by-past-threshold) | machine | void | library-large-list-group-view/20260908-sandbox | — |
| [library.large-list.group-by-indexed-column](findings/library-large-list-group-view-20260908-sandbox-library-large-list-group-by-indexed-column) | machine | void | library-large-list-group-view/20260908-sandbox | — |
| [library.large-list.group-by-native-index-column](findings/library-large-list-group-view-20260908-sandbox-library-large-list-group-by-native-index-column) | machine | void | library-large-list-group-view/20260908-sandbox | — |
| [library.large-list.control-absent-column-refused](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-absent-column-refused) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-choice-description-sticks](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-choice-description-sticks) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-choice-unknown-property-refused](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-choice-unknown-property-refused) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-group-by-single-value-column](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-group-by-single-value-column) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-id-query-served](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-id-query-served) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-missing-group-column-ungrouped) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-render-where-absent-refused](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-render-where-absent-refused) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-unindexed-filter-refused](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-control-unindexed-filter-refused) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.default-view-renders-first-page](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-default-view-renders-first-page) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.filtered-group-by-past-threshold](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-filtered-group-by-past-threshold) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.fixture-index-flags-clear](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-fixture-index-flags-clear) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.group-by-indexed-column](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-group-by-indexed-column) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.group-by-native-index-column](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-group-by-native-index-column) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.index-choice-column](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-index-choice-column) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.scope-recursive-changes-throttle](findings/library-large-list-group-view-20260919-e49d3b4a-library-large-list-scope-recursive-changes-throttle) | machine | open | library-large-list-group-view/20260919-e49d3b4a | — |
| [library.large-list.control-unindexed-filter-refused](findings/library-large-list-index-20260919-1266a678-library-large-list-control-unindexed-filter-refused) | machine | failed | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.fixture-index-flags-clear](findings/library-large-list-index-20260919-1266a678-library-large-list-fixture-index-flags-clear) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-choice-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-choice-column) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-date-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-date-column) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-is-per-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-is-per-column) | machine | void | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-lookup-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-lookup-column) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-number-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-number-column) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-removes-filter-throttle](findings/library-large-list-index-20260919-1266a678-library-large-list-index-removes-filter-throttle) | machine | void | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-removes-sort-throttle](findings/library-large-list-index-20260919-1266a678-library-large-list-index-removes-sort-throttle) | machine | void | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.index-text-column](findings/library-large-list-index-20260919-1266a678-library-large-list-index-text-column) | machine | open | library-large-list-index/20260919-1266a678 | — |
| [library.large-list.control-unindexed-filter-refused](findings/library-large-list-index-20260919-dc62b460-library-large-list-control-unindexed-filter-refused) | machine | failed | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.fixture-index-flags-clear](findings/library-large-list-index-20260919-dc62b460-library-large-list-fixture-index-flags-clear) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-choice-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-choice-column) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-date-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-date-column) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-is-per-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-is-per-column) | machine | void | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-lookup-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-lookup-column) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-number-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-number-column) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-removes-filter-throttle](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-removes-filter-throttle) | machine | void | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-removes-sort-throttle](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-removes-sort-throttle) | machine | void | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.index-text-column](findings/library-large-list-index-20260919-dc62b460-library-large-list-index-text-column) | machine | open | library-large-list-index/20260919-dc62b460 | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-control-ui-modern-renders-below-threshold) | machine, visible | needs-human | library-large-list-modern-view/20260909-sandbox | site-owner |
| [library.large-list.fixture-preindex-index-written-under-threshold](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-fixture-preindex-index-written-under-threshold) | machine | open | library-large-list-modern-view/20260909-sandbox | — |
| [library.large-list.fixture-preindex-library-present](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-fixture-preindex-library-present) | machine | open | library-large-list-modern-view/20260909-sandbox | — |
| [library.large-list.fixture-preindex-witness-unindexed](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-fixture-preindex-witness-unindexed) | machine | open | library-large-list-modern-view/20260909-sandbox | — |
| [library.large-list.fixture-ui-grouped-views-created](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-fixture-ui-grouped-views-created) | machine | open | library-large-list-modern-view/20260909-sandbox | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-ui-column-header-filter-past-threshold) | machine, visible | needs-human | library-large-list-modern-view/20260909-sandbox | site-owner |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260909-sandbox-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine, visible | needs-human | library-large-list-modern-view/20260909-sandbox | site-owner |
| [library.large-list.control-ui-default-view-unchanged](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-control-ui-default-view-unchanged) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.control-ui-experience-is-modern](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-control-ui-experience-is-modern) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.control-ui-fixture-readable-after-view-writes](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-control-ui-fixture-readable-after-view-writes) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.control-ui-page-identity-matches-fixture](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-control-ui-page-identity-matches-fixture) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.fixture-preindex-index-written-under-threshold](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-fixture-preindex-index-written-under-threshold) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.fixture-preindex-library-present](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-fixture-preindex-library-present) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.fixture-preindex-witness-unindexed](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-fixture-preindex-witness-unindexed) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.fixture-ui-grouped-views-created](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-fixture-ui-grouped-views-created) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-column-header-filter-past-threshold) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-default-view-renders-past-threshold](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-default-view-renders-past-threshold) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-group-by-indexed-column-renders](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-group-by-indexed-column-renders) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-group-by-unindexed-column-renders](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-group-by-unindexed-column-renders) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-modern-view-20260919-13ae5e81-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-modern-view/20260919-13ae5e81 | — |
| [library.large-list.control-ui-default-view-unchanged](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-control-ui-default-view-unchanged) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.control-ui-fixture-readable-after-view-writes](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-control-ui-fixture-readable-after-view-writes) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.fixture-ui-grouped-views-created](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-fixture-ui-grouped-views-created) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-ui-column-header-filter-past-threshold) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.ui-group-by-indexed-column-renders](findings/library-large-list-modern-view-20260919-29eac26e-library-large-list-ui-group-by-indexed-column-renders) | machine | open | library-large-list-modern-view/20260919-29eac26e | — |
| [library.large-list.control-ui-experience-is-modern](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-control-ui-experience-is-modern) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.control-ui-page-identity-matches-fixture](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-control-ui-page-identity-matches-fixture) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-column-header-filter-past-threshold) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-default-view-renders-past-threshold](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-default-view-renders-past-threshold) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-group-by-indexed-column-renders](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-group-by-indexed-column-renders) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-group-by-unindexed-column-renders](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-group-by-unindexed-column-renders) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-modern-view-20260919-5faba72b-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-modern-view/20260919-5faba72b | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260919-605bd86a-library-large-list-ui-column-header-filter-past-threshold) | machine | open | library-large-list-modern-view/20260919-605bd86a | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260919-605bd86a-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-modern-view/20260919-605bd86a | — |
| [library.large-list.ui-group-by-indexed-column-renders](findings/library-large-list-modern-view-20260919-605bd86a-library-large-list-ui-group-by-indexed-column-renders) | machine | open | library-large-list-modern-view/20260919-605bd86a | — |
| [library.large-list.control-ui-default-view-unchanged](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-control-ui-default-view-unchanged) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.control-ui-experience-is-modern](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-control-ui-experience-is-modern) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.control-ui-fixture-readable-after-view-writes](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-control-ui-fixture-readable-after-view-writes) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.control-ui-modern-renders-below-threshold](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-control-ui-modern-renders-below-threshold) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.control-ui-page-identity-matches-fixture](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-control-ui-page-identity-matches-fixture) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.fixture-preindex-index-written-under-threshold](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-fixture-preindex-index-written-under-threshold) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.fixture-preindex-library-present](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-fixture-preindex-library-present) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.fixture-preindex-witness-unindexed](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-fixture-preindex-witness-unindexed) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.fixture-ui-grouped-views-created](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-fixture-ui-grouped-views-created) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-column-header-filter-past-threshold](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-column-header-filter-past-threshold) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-default-view-renders-past-threshold](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-default-view-renders-past-threshold) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-group-by-indexed-column-folder-scoped](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-group-by-indexed-column-folder-scoped) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-group-by-indexed-column-renders](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-group-by-indexed-column-renders) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-group-by-unindexed-column-renders](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-group-by-unindexed-column-renders) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.ui-threshold-banner-text](findings/library-large-list-modern-view-20260919-72f140a4-library-large-list-ui-threshold-banner-text) | machine | open | library-large-list-modern-view/20260919-72f140a4 | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-control-missing-group-column-ungrouped) | machine | failed | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.control-multilevel-group-by-narrowed-honoured](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-control-multilevel-group-by-narrowed-honoured) | machine | failed | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.group-by-indexed-column-generous-wait](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-group-by-indexed-column-generous-wait) | machine | void | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.multilevel-group-by-field-order](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-multilevel-group-by-field-order) | machine | void | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.multilevel-group-by-indexed](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-multilevel-group-by-indexed) | machine | void | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.multilevel-group-by-unindexed](findings/library-large-list-multilevel-group-view-20260908-sandbox-library-large-list-multilevel-group-by-unindexed) | machine | void | library-large-list-multilevel-group-view/20260908-sandbox | — |
| [library.large-list.control-multilevel-group-by-narrowed-honoured](findings/library-large-list-multilevel-group-view-20260919-3bc9faff-library-large-list-control-multilevel-group-by-narrowed-honoured) | machine | failed | library-large-list-multilevel-group-view/20260919-3bc9faff | — |
| [library.large-list.multilevel-group-by-indexed](findings/library-large-list-multilevel-group-view-20260919-3bc9faff-library-large-list-multilevel-group-by-indexed) | machine | void | library-large-list-multilevel-group-view/20260919-3bc9faff | — |
| [library.large-list.multilevel-group-by-unindexed](findings/library-large-list-multilevel-group-view-20260919-3bc9faff-library-large-list-multilevel-group-by-unindexed) | machine | void | library-large-list-multilevel-group-view/20260919-3bc9faff | — |
| [library.large-list.control-absent-column-refused](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-absent-column-refused) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-choice-description-sticks](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-choice-description-sticks) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-choice-unknown-property-refused](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-choice-unknown-property-refused) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-group-by-single-value-column](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-group-by-single-value-column) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-id-query-served](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-id-query-served) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-missing-group-column-ungrouped) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-multilevel-group-by-narrowed-honoured](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-multilevel-group-by-narrowed-honoured) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-render-where-absent-refused](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-render-where-absent-refused) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-unindexed-filter-refused](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-control-unindexed-filter-refused) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.fixture-index-flags-clear](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-fixture-index-flags-clear) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.group-by-indexed-column-generous-wait](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-group-by-indexed-column-generous-wait) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.index-choice-column](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-index-choice-column) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.index-date-column](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-index-date-column) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.index-number-column](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-index-number-column) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.indexed-filter-serves-while-group-by-refused](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-indexed-filter-serves-while-group-by-refused) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.multilevel-group-by-field-order](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-multilevel-group-by-field-order) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.multilevel-group-by-indexed](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-multilevel-group-by-indexed) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.multilevel-group-by-refusal-signature](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-multilevel-group-by-refusal-signature) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.multilevel-group-by-unindexed](findings/library-large-list-multilevel-group-view-20260919-3e21b363-library-large-list-multilevel-group-by-unindexed) | machine | open | library-large-list-multilevel-group-view/20260919-3e21b363 | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-preindex-group-view-20260908-sandbox-library-large-list-control-missing-group-column-ungrouped) | machine | failed | library-large-list-preindex-group-view/20260908-sandbox | — |
| [library.large-list.control-preindex-group-by-narrowed-honoured](findings/library-large-list-preindex-group-view-20260908-sandbox-library-large-list-control-preindex-group-by-narrowed-honoured) | machine | void | library-large-list-preindex-group-view/20260908-sandbox | — |
| [library.large-list.group-by-native-index-column](findings/library-large-list-preindex-group-view-20260908-sandbox-library-large-list-group-by-native-index-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox | — |
| [library.large-list.preindex-group-by-indexed-column](findings/library-large-list-preindex-group-view-20260908-sandbox-library-large-list-preindex-group-by-indexed-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox | — |
| [library.large-list.preindex-group-by-unindexed-column](findings/library-large-list-preindex-group-view-20260908-sandbox-library-large-list-preindex-group-by-unindexed-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox | — |
| [library.large-list.control-missing-group-column-ungrouped](findings/library-large-list-preindex-group-view-20260908-sandbox-run2-library-large-list-control-missing-group-column-ungrouped) | machine | failed | library-large-list-preindex-group-view/20260908-sandbox-run2 | — |
| [library.large-list.control-preindex-group-by-narrowed-honoured](findings/library-large-list-preindex-group-view-20260908-sandbox-run2-library-large-list-control-preindex-group-by-narrowed-honoured) | machine | void | library-large-list-preindex-group-view/20260908-sandbox-run2 | — |
| [library.large-list.group-by-native-index-column](findings/library-large-list-preindex-group-view-20260908-sandbox-run2-library-large-list-group-by-native-index-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox-run2 | — |
| [library.large-list.preindex-group-by-indexed-column](findings/library-large-list-preindex-group-view-20260908-sandbox-run2-library-large-list-preindex-group-by-indexed-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox-run2 | — |
| [library.large-list.preindex-group-by-unindexed-column](findings/library-large-list-preindex-group-view-20260908-sandbox-run2-library-large-list-preindex-group-by-unindexed-column) | machine | void | library-large-list-preindex-group-view/20260908-sandbox-run2 | — |
| [library.search.discovery-on-library](findings/library-view-search-20260904-sandbox-library-search-discovery-on-library) | machine | open | library-view-search/20260904-sandbox | — |

600 further checks in this surface are settled.

Not yet probed: `library-guards-probe.js`, `folder-create-refusal-probe.js`, `folder-under-schema-probe.js`, `library-builtin-view-probe.js`, `library-header-token-probe.js`, `library-sharing-probe.js`, `library-lookup-write-probe.js`.

## transport — 2 of 4 probes with evidence, 1 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [transport.batch.changeset-addvalidate-date-iso](findings/batch-item-create-20261001-28bb31fe-transport-batch-changeset-addvalidate-date-iso) | machine | open | batch-item-create/20261001-28bb31fe | — |

19 further checks in this surface are settled.

Not yet probed: `batch-field-create-probe.js`, `list-identity-cache-probe.js`.
