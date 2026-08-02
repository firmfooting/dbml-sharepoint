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
    CROSS_SITE_REFERENCE_COLUMNS = "cross_site_reference_columns"
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
    VERSIONING = "versioning"
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

    # --- checks/_views.py: field sets -------------------------------------
    # A name in the mapping is not a rendered column of the entity. Reached
    # from a field set's members, a view's fields/sort/group_by, and a
    # display-name override -- the same mistake, told apart by the location.
    # --- checks/_views.py: declared views ---------------------------------
    # The list view LOOKUP threshold, one pair of codes for one rule: the
    # same `_join_finding` is reached from a declared view and from the
    # generated All Items view, so the section is what tells them apart.
    # --- checks/_views.py: hide_from_all_items ----------------------------
    # --- checks/_naming.py ------------------------------------------------
    # --- checks/_sources.py -----------------------------------------------
    # A mapping section names an entity that does not resolve to a table. One
    # rule reachable from many sections, so one code -- `location.section` is
    # what says which section asked. `entities:` itself is NOT this code: see
    # ENTITY_NOT_IN_SCHEMA, which is about the declaration rather than a
    # reference to it.
    # --- checks/_structure.py: entities, cross-site refs, indexes, calculated
    ALL_ITEMS_VIEW_DECLARED = "all_items_view_declared"
    CALCULATED_COLUMN_HAS_NO_FORMULA = "calculated_column_has_no_formula"
    CALCULATED_DISPLAY_COLUMN_UNINDEXABLE = "calculated_display_column_unindexable"
    CALCULATED_FORMULA_CYCLE = "calculated_formula_cycle"
    CALCULATED_FORMULA_DEFERRED_LOOKUP = "calculated_formula_deferred_lookup"
    CALCULATED_FORMULA_MISSING_EQUALS = "calculated_formula_missing_equals"
    CALCULATED_FORMULA_SELF_REFERENCE = "calculated_formula_self_reference"
    CALCULATED_FORMULA_TOO_LONG = "calculated_formula_too_long"
    CALCULATED_FORMULA_UNKNOWN_COLUMN = "calculated_formula_unknown_column"
    CALCULATED_FORMULA_UNSUPPORTED_OPERAND = "calculated_formula_unsupported_operand"
    COLUMN_NOT_RENDERED = "column_not_rendered"
    COMPOSITE_INDEX_UNSUPPORTED = "composite_index_unsupported"
    CROSS_SITE_COLUMN_CANNOT_BE_UNIQUE = "cross_site_column_cannot_be_unique"
    CROSS_SITE_COLUMN_HAS_NO_REF = "cross_site_column_has_no_ref"
    CROSS_SITE_GENERATED_NAME_COLLIDES = "cross_site_generated_name_collides"
    CROSS_SITE_GENERATED_NAME_TOO_LONG = "cross_site_generated_name_too_long"
    CROSS_SITE_UNKNOWN_COLUMN = "cross_site_unknown_column"
    DISPLAY_COLUMN_NOT_RENDERED = "display_column_not_rendered"
    DISPLAY_COLUMN_TYPE_UNINDEXABLE = "display_column_type_unindexable"
    DISPLAY_TITLE_TOO_LONG = "display_title_too_long"
    DOCUMENT_LIBRARY_UNSUPPORTED = "document_library_unsupported"
    DUPLICATE_DISPLAY_TITLE = "duplicate_display_title"
    DUPLICATE_INDEX_TARGET = "duplicate_index_target"
    DUPLICATE_VIEW_TITLE = "duplicate_view_title"
    DUPLICATE_VIEW_URL_SLUG = "duplicate_view_url_slug"
    EMPTY_DISPLAY_TITLE = "empty_display_title"
    EMPTY_PREVIOUS_TITLE = "empty_previous_title"
    EMPTY_VIEW_URL_SLUG = "empty_view_url_slug"
    ENTITY_NOT_IN_SCHEMA = "entity_not_in_schema"
    ENUM_MEMBERS_DIFFER = "enum_members_differ"
    ENUM_SOURCE_HAS_NO_DBML_ENUM = "enum_source_has_no_dbml_enum"
    FIELD_SET_EMPTY = "field_set_empty"
    FIELD_SET_NAME_HAS_MARKER = "field_set_name_has_marker"
    FIELD_SET_UNREFERENCED = "field_set_unreferenced"
    FORMATTER_FIELD_NOT_DISPLAYED = "formatter_field_not_displayed"
    FORMATTER_FIELD_NOT_RENDERED = "formatter_field_not_rendered"
    FORMULA_TARGET_NOT_CALCULATED = "formula_target_not_calculated"
    HIDE_IS_UNNECESSARY = "hide_is_unnecessary"
    HIDE_OF_CROSS_SITE_REFERENCE = "hide_of_cross_site_reference"
    HIDE_OF_NON_JOIN_BEARING_COLUMN = "hide_of_non_join_bearing_column"
    HIDE_OF_UNRENDERED_COLUMN = "hide_of_unrendered_column"
    HIDE_WITHOUT_ALL_ITEMS_VIEW = "hide_without_all_items_view"
    INDEX_COLUMN_NOT_RENDERED = "index_column_not_rendered"
    INDEX_COLUMN_TYPE_UNINDEXABLE = "index_column_type_unindexable"
    INDEX_DUPLICATES_UNIQUE_COLUMN = "index_duplicates_unique_column"
    INDEX_LIMIT_APPROACHING = "index_limit_approaching"
    INDEX_LIMIT_EXCEEDED = "index_limit_exceeded"
    INDEX_ON_CALCULATED_COLUMN = "index_on_calculated_column"
    INDEX_SETTINGS_UNSUPPORTED = "index_settings_unsupported"
    JOIN_THRESHOLD_APPROACHED = "join_threshold_approached"
    JOIN_THRESHOLD_EXCEEDED = "join_threshold_exceeded"
    LOOKUP_CROSSES_SITE_ROLE = "lookup_crosses_site_role"
    LOOKUP_DISPLAY_COLUMN_UNKNOWN = "lookup_display_column_unknown"
    LOOKUP_WOULD_RENDER_BLANK = "lookup_would_render_blank"
    MULTIPLE_DEFAULT_VIEWS = "multiple_default_views"
    POLYMORPHIC_COLUMN_NOT_RENDERED = "polymorphic_column_not_rendered"
    PREVIOUS_TITLE_CLAIMED_TWICE = "previous_title_claimed_twice"
    PREVIOUS_TITLE_IS_A_CURRENT_TITLE = "previous_title_is_a_current_title"
    PREVIOUS_TITLE_IS_OWN_TITLE = "previous_title_is_own_title"
    PREVIOUS_TITLE_IS_RESERVED = "previous_title_is_reserved"
    REDUNDANT_DISPLAY_COLUMN_ACCEPTANCE = "redundant_display_column_acceptance"
    RETIRED_COLUMN_IN_FIELD_SET = "retired_column_in_field_set"
    ROW_LIMIT_OUT_OF_RANGE = "row_limit_out_of_range"
    TOTAL_COLUMN_NOT_DISPLAYED = "total_column_not_displayed"
    TOTAL_NEEDS_NUMERIC_COLUMN = "total_needs_numeric_column"
    TOTAL_ON_LOOKUP_COLUMN = "total_on_lookup_column"
    TOTAL_ON_NON_ARITHMETIC_COLUMN = "total_on_non_arithmetic_column"
    UNINDEXED_FILTER_COLUMNS = "unindexed_filter_columns"
    UNKNOWN_ENTITY = "unknown_entity"
    UNKNOWN_FIELD_SET_REFERENCE = "unknown_field_set_reference"
    UNKNOWN_RETENTION_POLICY = "unknown_retention_policy"
    UNMAPPED_SCHEMA_TABLE = "unmapped_schema_table"
    UNSUPPORTED_BASE_TEMPLATE = "unsupported_base_template"
    WATCHED_COLUMN_NOT_RENDERED = "watched_column_not_rendered"
    WIDTH_COLUMN_NOT_DISPLAYED = "width_column_not_displayed"
    WIDTH_OUT_OF_RANGE = "width_out_of_range"

    # --- checks/_formatting.py: column formatting, style specs, form
    # formatting, list validation
    UNDEPLOYABLE_COLUMN_DECLARATION = "undeployable_column_declaration"
    FORMATTER_COLUMN_NOT_RENDERED = "formatter_column_not_rendered"
    FORMATTER_MISSING_ELMTYPE = "formatter_missing_elmtype"
    # One rule, three sections: a formatter naming a [$Field] the entity does
    # not render. `location.section` says whether it was a column formatter, a
    # form part or a view formatter.
    STYLE_REQUIRES_CALCULATED = "style_requires_calculated"
    STYLE_CALCULATED_TYPE_MISMATCH = "style_calculated_type_mismatch"
    STYLE_ON_BOOLEAN_MATCHES_NOTHING = "style_on_boolean_matches_nothing"
    STYLE_MAP_KEY_NOT_IN_ENUM = "style_map_key_not_in_enum"
    COLOR_BY_MAP_KEY_NOT_IN_ENUM = "color_by_map_key_not_in_enum"
    TREND_AGAINST_NOT_RENDERED = "trend_against_not_rendered"
    OVERDUE_GUARD_FIELD_NOT_RENDERED = "overdue_guard_field_not_rendered"
    FORM_PART_REFERENCES_CALCULATED_COLUMN = "form_part_references_calculated_column"
    FORM_SECTION_FIELD_NOT_RENDERED = "form_section_field_not_rendered"
    FORM_SECTION_ENTIRELY_HIDDEN = "form_section_entirely_hidden"
    FORM_COLUMNS_IN_NO_SECTION = "form_columns_in_no_section"
    LIST_VALIDATION_MESSAGE_TOO_LONG = "list_validation_message_too_long"
    LIST_VALIDATION_FORMULA_TOO_LONG = "list_validation_formula_too_long"
    # The condition grammar rejected the expression. `conditions.py` has 28
    # distinct reasons behind this and hands them back as prose; splitting
    # them into codes is that module's classification, not this one's.
    INVALID_CONDITION = "invalid_condition"

    # --- checks/_demo.py: rows seeded by `--seed`
    DEMO_ROWS_ON_DOCUMENT_LIBRARY = "demo_rows_on_document_library"
    DUPLICATE_DEMO_KEY = "duplicate_demo_key"
    DEMO_TITLE_MISSING_MARKER = "demo_title_missing_marker"
    DEMO_COLUMN_NOT_WRITABLE = "demo_column_not_writable"
    DEMO_VALUE_ON_CALCULATED_COLUMN = "demo_value_on_calculated_column"
    DEMO_HYPERLINK_OBJECT_INVALID = "demo_hyperlink_object_invalid"
    DEMO_HYPERLINK_ADDRESS_INVALID = "demo_hyperlink_address_invalid"
    DEMO_OBJECT_VALUE_INVALID = "demo_object_value_invalid"
    DEMO_REF_UNKNOWN_KEY = "demo_ref_unknown_key"
    DEMO_REF_ON_NON_LOOKUP = "demo_ref_on_non_lookup"
    DEMO_REF_TARGET_MISMATCH = "demo_ref_target_mismatch"
    DEMO_REF_FORWARD_REFERENCE = "demo_ref_forward_reference"
    DEMO_PERSON_VALUE_UNSUPPORTED = "demo_person_value_unsupported"
    DEMO_DATE_VALUE_INVALID = "demo_date_value_invalid"
    DEMO_ENUM_VALUE_UNKNOWN = "demo_enum_value_unknown"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the build has to say about the declaration it was given."""

    code: FindingCode
    severity: Severity
    message: str
    location: Location | None = None
