# src/dbml_sharepoint/analysis/findings.py
"""What a finding IS, separate from what produces one.

`checks/*` needs the vocabulary without importing the orchestrator, the same
layering rule that already forbids a generator importing from `checks/`.

The `code` is the identity. Everything keys off it: tests, the docs catalogue,
and `--explain`. The `message` is prose for a human and is free to be reworded
in any commit -- before this module existed, 294 test assertions matched
substrings of it, so it could not be.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

type Severity = Literal["error", "warning"]


class Section(StrEnum):
    """The mapping section a finding is about.

    These eighteen names were already being spelled into message prefixes by
    hand at 175 sites; this makes the set closed and the spelling checked.
    """

    CALCULATED_FORMULAS = "calculated_formulas"
    COLUMN_FORMATTING = "column_formatting"
    COLUMN_VALIDATION = "column_validation"
    CONDITIONS = "conditions"
    DEMO_ITEMS = "demo_items"
    DISPLAY_NAMES = "display_names"
    ENTITIES = "entities"
    ENUM_SOURCES = "enum_sources"
    FIELD_SETS = "field_sets"
    FORM_FORMATTING = "form_formatting"
    FORM_VISIBILITY = "form_visibility"
    GROUPS = "groups"
    LIST_VALIDATION = "list_validation"
    PERMISSION_LEVELS = "permission_levels"
    POLYMORPHIC_PATTERNS = "polymorphic_patterns"
    # Not one of the eighteen message prefixes: retention lives in its own
    # `retention-policies.yaml`, and its two findings were written as prose
    # rather than as a dotted path. The section is real even where the message
    # never spelled it.
    RETENTION = "retention"
    RETIRED_COLUMNS = "retired_columns"
    SCHEMA = "schema"
    VIEWS = "views"
    WATCHED_LISTS = "watched_lists"


@dataclass(frozen=True, slots=True)
class Location:
    """Where a finding is, as data rather than as a rendered prefix."""

    section: Section
    entity: str | None = None
    column: str | None = None
    view: str | None = None
    sub: str | None = None

    @property
    def path(self) -> str:
        """The dotted path these messages have always rendered by hand."""
        head = str(self.section)
        if self.entity is not None:
            head = f"{head}[{self.entity}]"
        tail = [p for p in (self.view, self.column, self.sub) if p is not None]
        return ".".join([head, *tail])


class FindingCode(StrEnum):
    """One member per rule. The catalogue of everything this tool can say.

    Adding a rule means adding a member here and a row in
    `website/docs/reference/findings.md`; `test_every_code_is_documented`
    enforces the pair.
    """

    # TEMPORARY. Scaffolding for the migration: every one of the 174
    # construction sites got this in one pass so the tree compiles while the
    # real codes are named a check module at a time. Task 3 of the
    # typed-boundaries plan deletes this member, and
    # `test_no_finding_is_unclassified` is how we will know it is gone.
    UNCLASSIFIED = "unclassified"

    # Reachable from `views`, `field_sets`, `display_names` and `retention`:
    # one rule, four sections, and the section is in the location.
    UNKNOWN_ENTITY = "unknown_entity"

    # --- checks/_views.py: field sets -------------------------------------
    FIELD_SET_NAME_HAS_MARKER = "field_set_name_has_marker"
    FIELD_SET_EMPTY = "field_set_empty"
    FIELD_SET_UNREFERENCED = "field_set_unreferenced"
    RETIRED_COLUMN_IN_FIELD_SET = "retired_column_in_field_set"

    # A name in the mapping is not a rendered column of the entity. Reached
    # from a field set's members, a view's fields/sort/group_by, and a
    # display-name override -- the same mistake, told apart by the location.
    COLUMN_NOT_RENDERED = "column_not_rendered"

    # --- checks/_views.py: declared views ---------------------------------
    ALL_ITEMS_VIEW_DECLARED = "all_items_view_declared"
    DUPLICATE_VIEW_TITLE = "duplicate_view_title"
    DUPLICATE_VIEW_URL_SLUG = "duplicate_view_url_slug"
    EMPTY_VIEW_URL_SLUG = "empty_view_url_slug"
    MULTIPLE_DEFAULT_VIEWS = "multiple_default_views"
    EMPTY_PREVIOUS_TITLE = "empty_previous_title"
    PREVIOUS_TITLE_IS_OWN_TITLE = "previous_title_is_own_title"
    PREVIOUS_TITLE_IS_RESERVED = "previous_title_is_reserved"
    PREVIOUS_TITLE_IS_A_CURRENT_TITLE = "previous_title_is_a_current_title"
    PREVIOUS_TITLE_CLAIMED_TWICE = "previous_title_claimed_twice"
    UNKNOWN_FIELD_SET_REFERENCE = "unknown_field_set_reference"
    ROW_LIMIT_OUT_OF_RANGE = "row_limit_out_of_range"
    UNINDEXED_FILTER_COLUMNS = "unindexed_filter_columns"
    FORMATTER_FIELD_NOT_RENDERED = "formatter_field_not_rendered"
    FORMATTER_FIELD_NOT_DISPLAYED = "formatter_field_not_displayed"
    WIDTH_COLUMN_NOT_DISPLAYED = "width_column_not_displayed"
    WIDTH_OUT_OF_RANGE = "width_out_of_range"
    TOTAL_COLUMN_NOT_DISPLAYED = "total_column_not_displayed"
    TOTAL_ON_LOOKUP_COLUMN = "total_on_lookup_column"
    TOTAL_ON_NON_ARITHMETIC_COLUMN = "total_on_non_arithmetic_column"
    TOTAL_NEEDS_NUMERIC_COLUMN = "total_needs_numeric_column"

    # The list view LOOKUP threshold, one pair of codes for one rule: the
    # same `_join_finding` is reached from a declared view and from the
    # generated All Items view, so the section is what tells them apart.
    JOIN_THRESHOLD_EXCEEDED = "join_threshold_exceeded"
    JOIN_THRESHOLD_APPROACHED = "join_threshold_approached"

    # --- checks/_views.py: hide_from_all_items ----------------------------
    HIDE_WITHOUT_ALL_ITEMS_VIEW = "hide_without_all_items_view"
    HIDE_OF_CROSS_SITE_REFERENCE = "hide_of_cross_site_reference"
    HIDE_OF_UNRENDERED_COLUMN = "hide_of_unrendered_column"
    HIDE_OF_NON_JOIN_BEARING_COLUMN = "hide_of_non_join_bearing_column"
    HIDE_IS_UNNECESSARY = "hide_is_unnecessary"

    # --- checks/_naming.py ------------------------------------------------
    EMPTY_DISPLAY_TITLE = "empty_display_title"
    DISPLAY_TITLE_TOO_LONG = "display_title_too_long"
    DUPLICATE_DISPLAY_TITLE = "duplicate_display_title"
    LOOKUP_CROSSES_SITE_ROLE = "lookup_crosses_site_role"
    LOOKUP_DISPLAY_COLUMN_UNKNOWN = "lookup_display_column_unknown"
    LOOKUP_WOULD_RENDER_BLANK = "lookup_would_render_blank"

    # --- checks/_sources.py -----------------------------------------------
    UNKNOWN_RETENTION_POLICY = "unknown_retention_policy"
    ENUM_SOURCE_HAS_NO_DBML_ENUM = "enum_source_has_no_dbml_enum"
    ENUM_MEMBERS_DIFFER = "enum_members_differ"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the build has to say about the declaration it was given."""

    code: FindingCode
    severity: Severity
    message: str
    location: Location | None = None
