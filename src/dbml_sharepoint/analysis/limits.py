# src/dbml_sharepoint/analysis/limits.py
"""The SharePoint ceilings this tool enforces, each named exactly once.

Every value here was previously a bare literal at two to five call sites,
several of them inside PROSE that no test ever compared against the code that
enforced it. The 1024-character validation ceiling had eight code copies and
four prose copies; the 20-index ceiling had five. Changing one meant editing a
dozen places and hoping.

That shape fails in the direction this project cares about most. A message
saying "SharePoint's limit is 1024" beside a check that now tests 2048 is not a
crash — it is a build that passes, a deploy that verifies, and an operator told
a number that is not the one being enforced. Nothing downstream can see it.

So: the number lives here, and every enforcement site and every sentence that
quotes one interpolates it. `finding_help.py` already did exactly this with
`CALCULATED_TYPE_LIST`; this module is that pattern applied to the ceilings.

**Values that coincide are still separate facts.** Four constants below are
255 and two are 5000, and they are deliberately not folded together: they are
different SharePoint surfaces that happen to share a number today. Tying a view
setting to a list-size threshold, or a field's Description bound to its
DisplayName bound, would mean a future correction to one silently moved the
other. Each constant's comment says which surface it belongs to.

Nothing in this module imports anything, so it can be read by `model/`,
`analysis/`, `analysis/checks/` and `generators/` alike without touching the
one-way dependency rule in AGENTS.md.
"""

# ---------------------------------------------------------------- names

#: SharePoint's bound on a field's DISPLAY title (the REST `Title` property).
#:
#: DOCUMENTED, not assumed. Microsoft Learn, "Field element (Field)", which
#: lists SharePoint Online among the products it applies to, says of
#: `DisplayName`: "Maximum length is 255 characters."
#: https://learn.microsoft.com/sharepoint/dev/schema/field-element-field
#:
#: `DisplayName` there is the field-schema attribute for the same surface this
#: project writes as the REST `Title` property (see `jsgen`, which POSTs
#: `{"Title": ...}` and renames Title to the declared display afterwards).
#: 255 is the LAST ACCEPTED length, so every check stays `> MAX_DISPLAY_TITLE`
#: and never `>=`. Both boundary directions are pinned by
#: `test_a_display_name_override_longer_than_the_sp_limit_is_an_error` and
#: `test_a_display_name_override_at_the_sp_limit_is_accepted`.
MAX_DISPLAY_TITLE = 255

#: SharePoint's bound on a field's INTERNAL name. A different surface from
#: `MAX_DISPLAY_TITLE` — internal names are what formulas and `[$Field]`
#: references resolve against, and they are immutable after creation.
MAX_INTERNAL_NAME = 32

#: The bound `typemap.format_description` truncates a DBML column note to
#: before it becomes the SharePoint field Description.
#:
#: A THIRD 255, and not the display-title one: this is the Description
#: property, not the Title. Truncation rather than refusal is deliberate — a
#: note is documentation, so losing its tail is better than failing a build.
MAX_FIELD_DESCRIPTION = 255

# ---------------------------------------------------------------- field size

#: `MaxLength` set on every single-line Text field this tool creates. SP's own
#: ceiling for `SP.FieldText.MaxLength`, and its default.
#:
#: A FOURTH 255, and again a different surface: this bounds the DATA a text
#: column can hold, not the length of any name.
MAX_TEXT_FIELD_LENGTH = 255

# ---------------------------------------------------------------- formulas

#: The practical calculated-column formula ceiling.
#:
#: Widely reported as the limit of the Lists UI formula box, but NOT documented
#: by Microsoft for SharePoint — the documented 1000-character formula limit
#: belongs to Dataverse, which is a different product with different rules (the
#: same confusion once had this project believing SharePoint forbade
#: calc-on-calc chains, which it permits). Conservative, so it cannot pass a
#: formula SharePoint would refuse; raising it needs a live probe, not a
#: citation.
MAX_CALCULATED_FORMULA = 1024

#: The ceiling on a rendered `ValidationFormula`, list-level and column-level
#: alike. Measured against the same undocumented surface as
#: `MAX_CALCULATED_FORMULA` and equal to it today, but kept separate: the
#: calculated-column formula box and the validation formula box are different
#: SharePoint surfaces, and a probe that moves one has no authority over the
#: other.
MAX_VALIDATION_FORMULA = 1024

#: The ceiling on a `ValidationMessage` — the text an author writes to explain
#: a refused save. Distinct from the formula bound above; the message is a
#: separate property that SharePoint stores and renders on its own.
MAX_VALIDATION_MESSAGE = 1024

# ---------------------------------------------------------------- indexes

#: Indexes SharePoint permits per list, counting `[unique]` columns and the
#: automatic lookup-target display index.
MAX_LIST_INDEXES = 20

#: Where the approaching-the-ceiling warning starts.
#:
#: The count this tool can see is a FLOOR, not a total. SharePoint creates
#: indexes on its own: opening a modern view sorted on an unindexed column
#: produces one marked "(Automatically created)" that consumes a real slot, and
#: nothing reachable from script reports the true number — the only place it
#: exists is the "You have created N of maximum 20 indices on this list" line
#: on IndexedColumns.aspx. So a schema that validates at exactly
#: `MAX_LIST_INDEXES` can still hit 21 in production, and the headroom below is
#: what the warning exists to preserve.
#:
#: MEASURED 2026-07-31, test/manual/templates/threshold-index-probe.js.j2:
#: opening a modern view sorted on an unindexed column at 3,000 items created
#: an index marked "(Automatically created)" on IndexedColumns.aspx, consuming
#: one of the twenty.
INDEX_WARN_AT = 18

# ---------------------------------------------------------------- view size

#: The per-view page-size ceiling (`SP.View.RowLimit`), which a declared
#: `row_limit:` must fall inside.
#:
#: DELIBERATELY NOT `LIST_VIEW_THRESHOLD`. This is a view setting; that is a
#: list-size threshold. They share a value and nothing else, and folding them
#: into one constant would tie a page size to a throttling limit it has no
#: reason to track.
MAX_VIEW_ROW_LIMIT = 5000

#: SharePoint Online's list view threshold. Microsoft states it CANNOT be
#: changed for SharePoint, and that the effective number "is not always 5,000"
#: because it varies with the site and database activity — so this is the
#: documented figure, not a precise cutoff.
#:
#: The consequence is worse than an error, which is why it is worth warning
#: about at all: with Metadata Navigation and Filtering (on by default) a query
#: no index can serve falls back to returning up to
#: `LIST_VIEW_THRESHOLD_FALLBACK_ROWS` of the NEWEST items, and may return
#: none. A view that silently shows a truncated answer is the failure those
#: checks exist to prevent.
#: https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
LIST_VIEW_THRESHOLD = 5_000

#: How many of the newest items a throttled, Metadata-Navigation-assisted query
#: falls back to returning. See `LIST_VIEW_THRESHOLD`.
LIST_VIEW_THRESHOLD_FALLBACK_ROWS = 1_250
