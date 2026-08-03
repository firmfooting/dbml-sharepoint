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
    # Not a per-entity mapping section like the rest: its paths are
    # `list_permissions.default...` and `list_permissions.overrides[...]`.
    LIST_PERMISSIONS = "list_permissions"
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

    # An extension's own rule, via DeploymentExtension.extra_validators. The
    # core cannot enumerate what a project-specific validator will object to,
    # so they share one code and carry the detail in the message.
    EXTENSION_REPORTED = "extension_reported"

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

    # --- retirement and the sections it folds into (checks/_retirement.py) --
    CALCULATED_FORMULA_REFERENCES_A_RETIRED_COLUMN = (
        "calculated_formula_references_a_retired_column"
    )
    COLUMN_VALIDATION_ON_A_RETIRED_COLUMN = "column_validation_on_a_retired_column"
    COLUMN_VALIDATION_REFERENCES_OTHER_COLUMNS = "column_validation_references_other_columns"
    LIST_VALIDATION_REFERENCES_A_RETIRED_COLUMN = (
        "list_validation_references_a_retired_column"
    )
    RETIRED_COLUMN_NOT_RENDERED = "retired_column_not_rendered"
    RETIRED_COLUMN_REQUIRED_WITH_A_DEFAULT = "retired_column_required_with_a_default"
    RETIRED_COLUMN_STILL_INDEXED = "retired_column_still_indexed"
    RETIRED_DATE_NOT_ISO = "retired_date_not_iso"
    RETIREMENT_STRIPPED_A_DECLARATION = "retirement_stripped_a_declaration"
    RETIREMENT_WITHOUT_DISPLAY_NAMES = "retirement_without_display_names"
    SUPERSEDED_BY_IS_ITSELF_RETIRED = "superseded_by_is_itself_retired"
    SUPERSEDED_BY_NAMES_THE_RETIRED_COLUMN = "superseded_by_names_the_retired_column"
    SUPERSEDED_BY_NOT_RENDERED = "superseded_by_not_rendered"
    UNDEPLOYABLE_DECLARATION_COLUMN = "undeployable_declaration_column"
    VALIDATION_FORMULA_TOO_LONG = "validation_formula_too_long"
    VALIDATION_MESSAGE_TOO_LONG = "validation_message_too_long"
    VIEW_EMPTIED_BY_RETIREMENT = "view_emptied_by_retirement"

    # --- permission levels, groups and policies (checks/_permissions.py) ----
    DUPLICATE_GROUP_NAME = "duplicate_group_name"
    DUPLICATE_PERMISSION_LEVEL_NAME = "duplicate_permission_level_name"
    UNKNOWN_BASE_PERMISSION = "unknown_base_permission"
    UNKNOWN_OWNER_GROUP = "unknown_owner_group"
    UNKNOWN_PERMISSION_LEVEL = "unknown_permission_level"
    UNKNOWN_PRINCIPAL_GROUP = "unknown_principal_group"
    UNKNOWN_SITE_ROLE = "unknown_site_role"
    #: The DBML does not declare this table. Distinct from UNKNOWN_ENTITY,
    #: which is a name the MAPPING does not declare.
    UNKNOWN_TABLE = "unknown_table"
    UNRESOLVABLE_ASSOCIATED_GROUP_ALIAS = "unresolvable_associated_group_alias"

    # --- form visibility (analysis/forms.py) --------------------------------
    FORM_VISIBILITY_CONDITION_UNREACHABLE = "form_visibility_condition_unreachable"
    FORM_VISIBILITY_ON_A_CALCULATED_COLUMN = "form_visibility_on_a_calculated_column"
    REQUIRED_COLUMN_HIDDEN_FROM_THE_NEW_FORM = "required_column_hidden_from_the_new_form"
    REQUIRED_COLUMN_MAY_BE_HIDDEN_AT_CREATION = "required_column_may_be_hidden_at_creation"

    # --- the shared condition grammar (analysis/conditions.py) --------------
    # The prefix names the SUBJECT, not a section: these are reachable from
    # views, form_visibility, column_validation and list_validation alike,
    # and the section is in the location.
    CONDITION_COLUMN_TYPE_UNKNOWN = "condition_column_type_unknown"
    CONDITION_DATE_IS_AN_UNQUOTED_YAML_DATETIME = "condition_date_is_an_unquoted_yaml_datetime"
    CONDITION_DATE_UNPARSEABLE = "condition_date_unparseable"
    CONDITION_DATE_WEARS_WHITESPACE = "condition_date_wears_whitespace"
    CONDITION_FIELD_NOT_RENDERED = "condition_field_not_rendered"
    CONDITION_LOOKUP_UNSUPPORTED_BY_TARGET = "condition_lookup_unsupported_by_target"
    CONDITION_ME_OPERATOR_MEANINGLESS = "condition_me_operator_meaningless"
    CONDITION_ME_TAKES_NO_PROPERTY = "condition_me_takes_no_property"
    CONDITION_ME_UNSUPPORTED_BY_TARGET = "condition_me_unsupported_by_target"
    CONDITION_MEASURE_NOT_APPLICABLE = "condition_measure_not_applicable"
    CONDITION_MEASURE_UNKNOWN = "condition_measure_unknown"
    CONDITION_MEASURE_UNRENDERABLE = "condition_measure_unrenderable"
    CONDITION_NEEDLE_EMPTY = "condition_needle_empty"
    CONDITION_NEGATION_UNRENDERABLE = "condition_negation_unrenderable"
    CONDITION_NEGATIVE_TEXT_OPERATOR_UNRENDERABLE = (
        "condition_negative_text_operator_unrenderable"
    )
    CONDITION_NOW_ON_A_DATE_COLUMN = "condition_now_on_a_date_column"
    CONDITION_NOW_UNSUPPORTED_BY_TARGET = "condition_now_unsupported_by_target"
    CONDITION_OPERAND_TYPE_UNSUPPORTED = "condition_operand_type_unsupported"
    CONDITION_OPERATOR_NOT_NEGATABLE = "condition_operator_not_negatable"
    CONDITION_OPERATOR_UNKNOWN = "condition_operator_unknown"
    CONDITION_OPERATOR_UNRENDERABLE = "condition_operator_unrenderable"
    CONDITION_OPERATOR_UNVERIFIED = "condition_operator_unverified"
    CONDITION_PROPERTY_NOT_APPLICABLE = "condition_property_not_applicable"
    CONDITION_PROPERTY_REQUIRED = "condition_property_required"
    CONDITION_PROPERTY_UNKNOWN = "condition_property_unknown"
    CONDITION_PROPERTY_UNRENDERABLE = "condition_property_unrenderable"
    CONDITION_SENTINEL_WITH_A_SUBSTRING_OPERATOR = "condition_sentinel_with_a_substring_operator"
    CONDITION_SET_EMPTY = "condition_set_empty"
    CONDITION_SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN = (
        "condition_substring_test_on_a_non_text_column"
    )
    CONDITION_TODAY_UNSUPPORTED_BY_TARGET = "condition_today_unsupported_by_target"
    CONDITION_TOO_DEEP = "condition_too_deep"
    CONDITION_TOO_MANY_LEAVES = "condition_too_many_leaves"
    CONDITION_VALUE_HAS_A_CONTROL_CHARACTER = "condition_value_has_a_control_character"
    CONDITION_VALUE_MISSING = "condition_value_missing"
    CONDITION_VALUE_NOT_A_BOOLEAN = "condition_value_not_a_boolean"
    CONDITION_VALUE_NOT_A_LIST = "condition_value_not_a_list"
    CONDITION_VALUE_NOT_A_NUMBER = "condition_value_not_a_number"
    CONDITION_VALUE_NOT_ALLOWED = "condition_value_not_allowed"
    CONDITION_VALUE_NOT_FINITE = "condition_value_not_finite"

    # --- schema-only rules, from validator.validate() ---
    AUTO_INCREMENT_PK_MUST_BE_ID = "auto_increment_pk_must_be_id"
    COLUMN_NAME_TOO_LONG = "column_name_too_long"
    CROSS_SITE_EXPANSION_UNHANDLED = "cross_site_expansion_unhandled"
    DEFAULT_NOT_AN_ENUM_MEMBER = "default_not_an_enum_member"
    DUPLICATE_COLUMN_NAME = "duplicate_column_name"
    DUPLICATE_ENUM_NAME = "duplicate_enum_name"
    DUPLICATE_TABLE_NAME = "duplicate_table_name"
    EMPTY_ENUM = "empty_enum"
    ILLEGAL_COLUMN_NAME_CHARACTER = "illegal_column_name_character"
    LEGACY_CHOICE_TYPE = "legacy_choice_type"
    ORPHAN_ENUM = "orphan_enum"
    RESERVED_COLUMN_NAME = "reserved_column_name"
    UNIQUE_UNSUPPORTED_FOR_TYPE = "unique_unsupported_for_type"
    UNIQUE_WITHOUT_NOT_NULL = "unique_without_not_null"
    UNKNOWN_COLUMN_TYPE = "unknown_column_type"
    UNKNOWN_REF_TARGET = "unknown_ref_target"



@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the build has to say about the declaration it was given."""

    code: FindingCode
    severity: Severity
    message: str
    location: Location | None = None

    @property
    def detail(self) -> str:
        """The code and the message, for anything that shows a finding.

        The code is the identity and the published catalogue in
        `reference/findings.md` is keyed by it, but only the message used to
        reach the terminal and the manifest -- and the message is prose that
        is free to be reworded in any commit. So the operator was shown the
        one part of a finding that is deliberately not searchable, and given
        nothing to carry them to the catalogue entry.

        One property rather than a format string at each site: the CLI's
        error path, the CLI's warning path and the manifest template all
        show findings, and three spellings of "how a finding looks" drift.
        The severity marker stays with the caller because it legitimately
        differs by medium -- `**[WARNING]**` in markdown, `[WARNING]` on a
        terminal.
        """
        return f"{self.code}: {self.message}"
