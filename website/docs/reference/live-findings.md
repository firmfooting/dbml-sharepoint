---
title: Live findings
sidebar_position: 90
---

<!-- markdownlint-disable MD013 -->

# Live findings

Every finding below is derived from an evidence package committed under `evidence/probes`, and every surface below is declared upstream in `SURFACES.md` whether or not anything has probed it yet. One row is one check: where a probe result and a reviewed capture answer the same check, they merge into a single row naming both lanes. A check is listed while it is still open, failed, void or referred to a human; settled checks are counted under their surface, not listed. Each row links to that check's own page, which carries the question it answers and the evidence behind it.

Runs: 31. Findings: 112. Captures superseded: 1.

Probes: 33. Probed: 24. Not yet probed: 9.

Checks with a probe result, not settled: 110 of 493. Checks with a reviewed capture, not settled: 3 of 31.

## formula — 9 of 10 probes with evidence, 52 findings

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

177 further checks in this surface are settled.

Not yet probed: `hyperlink-validation-operand-probe.js`.

## expression — no evidence

Not yet probed: `expression-text-operators-probe.js`, `form-visibility-evidence-probe.js`.

## query — 1 of 1 probes with evidence, 9 findings

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

37 further checks in this surface are settled.

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

## form — 1 of 3 probes with evidence, 1 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [form.panel.edit-columns-writes-attributes](findings/form-visibility-20260824-three-form-matrix-form-panel-edit-columns-writes-attributes) | machine | open | form-visibility/20260824-three-form-matrix | — |

9 further checks in this surface are settled.

Not yet probed: `form-visibility-interactive.js`, `form-visibility-storage-probe.js`.

## field — 2 of 3 probes with evidence, 9 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [D1](findings/date-storage-20260902-default-reads-d1) | machine | failed | date-storage/20260902-default-reads | — |
| [D2](findings/date-storage-20260902-default-reads-d2) | machine | failed | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-default-filled](findings/date-storage-20260902-default-reads-field-date-stored-instant-default-filled) | machine | open | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-form-picked](findings/date-storage-20260902-default-reads-field-date-stored-instant-form-picked) | machine | open | date-storage/20260902-default-reads | — |
| [field.date.stored-instant-default-filled](findings/date-storage-20260902-sandbox-reads-field-date-stored-instant-default-filled) | machine | open | date-storage/20260902-sandbox-reads | — |
| [field.date.stored-instant-form-picked](findings/date-storage-20260902-sandbox-reads-field-date-stored-instant-form-picked) | machine | open | date-storage/20260902-sandbox-reads | — |
| [field.multichoice.severity-formatter-render](findings/multi-value-20260828-initial-field-multichoice-severity-formatter-render) | machine | open | multi-value/20260828-initial | — |
| [query.view-query.multichoice-chain-selects](findings/multi-value-20260828-initial-query-view-query-multichoice-chain-selects) | machine | open | multi-value/20260828-initial | — |
| [query.view-query.multichoice-membership-selects](findings/multi-value-20260828-initial-query-view-query-multichoice-membership-selects) | machine | open | multi-value/20260828-initial | — |

29 further checks in this surface are settled.

Not yet probed: `projected-lookup-probe.js`.

## text — 3 of 4 probes with evidence, 1 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [text.group-desc.length-ceiling](findings/group-description-20260828-initial-text-group-desc-length-ceiling) | machine | failed | group-description/20260828-initial | — |

55 further checks in this surface are settled.

Not yet probed: `role-definition-probe.js`.

## access — 3 of 4 probes with evidence, 12 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
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
| [access.principal.person-column-ids-resolve](findings/siteuserinfolist-20260902-initial-access-principal-person-column-ids-resolve) | machine | open | siteuserinfolist/20260902-initial | — |

12 further checks in this surface are settled.

Not yet probed: `reader-bindings-probe.js`.

## scale — 2 of 2 probes with evidence, 17 findings

| Finding | Lanes | State | Run | Observed as |
| --- | --- | --- | --- | --- |
| [scale.index.odata-comparison-found-list](findings/native-index-20260828-initial-scale-index-odata-comparison-found-list) | machine | open | native-index/20260828-initial | — |
| [scale.index.odata-null-found-list](findings/native-index-20260828-initial-scale-index-odata-null-found-list) | machine | open | native-index/20260828-initial | — |
| [scale.native-idx.author-property](findings/native-index-20260828-initial-scale-native-idx-author-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.control-index-readable](findings/native-index-20260828-initial-scale-native-idx-control-index-readable) | machine | failed | native-index/20260828-initial | — |
| [scale.native-idx.created-property](findings/native-index-20260828-initial-scale-native-idx-created-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.editor-property](findings/native-index-20260828-initial-scale-native-idx-editor-property) | machine | void | native-index/20260828-initial | — |
| [scale.native-idx.modified-property](findings/native-index-20260828-initial-scale-native-idx-modified-property) | machine | void | native-index/20260828-initial | — |
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

## library — no evidence

Not yet probed: `document-library-probe.js`.
