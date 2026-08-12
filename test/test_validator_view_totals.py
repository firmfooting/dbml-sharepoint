"""Validator: declared view totals."""
from _findings import none_of, only
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _validator_helpers import _project_errors

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.conditions import Condition, Group, Leaf
from dbml_sharepoint.model.mapping_loader import (
    CrossSiteRef,
    CustomPermissionLevel,
    DemoItem,
    EntityMapping,
    MappingBundle,
    PermissionsConfig,
    SiteGroup,
    ViewDef,
)
from dbml_sharepoint.model.parser import Schema

# --- Declared view totals ---------------------------------------------------

#: Every way a `totals:` declaration can be refused. The tests that ACCEPT a
#: declaration name the whole set, so "no totals complaint" cannot quietly
#: shrink to "no complaint of the one kind I remembered".
_TOTALS_CODES = (
    FindingCode.TOTAL_COLUMN_NOT_DISPLAYED,
    FindingCode.TOTAL_NEEDS_NUMERIC_COLUMN,
    FindingCode.TOTAL_ON_LOOKUP_COLUMN,
    FindingCode.TOTAL_ON_NON_ARITHMETIC_COLUMN,
)


def _no_totals_refusal(findings: list[Finding]) -> None:
    for code in _TOTALS_CODES:
        none_of(findings, code)


def _totals_view(fields: list[str], totals: dict[str, str]) -> dict[str, list[ViewDef]]:
    """The single view `V` on Project that every totals test declares."""
    return {"Project": [ViewDef(title="V", fields=fields, totals=totals)]}


def test_a_total_on_a_column_the_view_does_not_show_is_refused() -> None:
    """The widths failure shape exactly: SharePoint accepts the property and
    renders nothing, because the view has no column to put a figure under."""
    errors = _project_errors(views=_totals_view(["Title"], {"SortOrder": "sum"}))
    f = only(errors, FindingCode.TOTAL_COLUMN_NOT_DISPLAYED)
    assert "'SortOrder'" in f.message

def test_summing_a_choice_column_is_refused_and_points_at_count() -> None:
    errors = _project_errors(views=_totals_view(["Title", "Status"], {"Status": "sum"}))
    f = only(errors, FindingCode.TOTAL_NEEDS_NUMERIC_COLUMN)
    assert "'Status'" in f.message
    # The remedy: count counts ROWS, so it works where sum cannot.
    assert "'count'" in f.message

def test_counting_a_choice_column_is_allowed() -> None:
    """count counts ROWS, not values, so it is legal on any displayed
    column — which is why it is excluded from the numeric-only set rather
    than sharing the numeric rule."""
    errors = _project_errors(views=_totals_view(["Title", "Status"], {"Status": "count"}))
    _no_totals_refusal(errors)

def test_summing_a_numeric_column_is_allowed() -> None:
    errors = _project_errors(
        views=_totals_view(["Title", "SortOrder"], {"SortOrder": "sum"}),
    )
    _no_totals_refusal(errors)

def test_a_total_on_a_calculated_number_is_allowed() -> None:
    """Three of the columns this feature exists for are calculated
    day-counts. The `string;#` prefix that complicates calculated TEXT is a
    column-formatting concern and never reaches a view's Aggregations."""
    schema = make_schema(
        make_table(
            "Project",
            column("Title", required=True),
            column("Score", "int"),
            column("Band", "calculated_text"),
        ),
    )
    bundle = make_bundle(
        entities=["Project"],
        calculated_formulas={"Project": {"Band": '=IF([Score]>5,"High","Low")'}},
        views={
            "Project": [
                ViewDef(title="V", fields=["Title", "Score"], totals={"Score": "avg"}),
            ],
        },
    )
    _no_totals_refusal(validate_against_mapping(schema, bundle))

def _hyperlink_demo(value: object) -> list[Finding]:
    """A whole build's worth of validation, not `_field_plan` alone: the
    demo planner and the demo VALIDATOR are separate readers of the same
    authored value, and a form one accepts and the other refuses never
    reaches generation."""
    schema = make_schema(
        make_table(
            "Doc", column("Title", required=True), column("Link", "hyperlink"),
            # Without a note ENTITY_HAS_NO_NOTE lands in every caller's error
            # list, and both callers assert that list is empty.
            note="The fixture document list.",
        ),
    )
    bundle = make_bundle(
        entities=["Doc"],
        demo_items={
            "Doc": [DemoItem(key="d1", values={"Title": "[DEMO] A row", "Link": value})],
        },
    )
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]

def test_a_hyperlink_demo_value_may_be_a_bare_url() -> None:
    assert not _hyperlink_demo("https://example.invalid/a.pdf")

def test_a_hyperlink_demo_value_may_carry_a_description() -> None:
    """The object form the demo planner accepts. The validator must accept
    it too — it reads every dict, and a lookup reference is not the only
    thing that is one."""
    assert not _hyperlink_demo(
        {"url": "https://example.invalid/a.pdf", "description": "The file"},
    )

def test_a_hyperlink_demo_object_needs_a_url() -> None:
    errors = _hyperlink_demo({"description": "no address"})
    f = only(errors, FindingCode.DEMO_HYPERLINK_OBJECT_INVALID)
    # The keys it actually got, so the author can see what to rename.
    assert "['description']" in f.message

def test_a_hyperlink_demo_object_refuses_unknown_keys() -> None:
    errors = _hyperlink_demo(
        {"url": "https://example.invalid/a.pdf", "label": "wrong key"},
    )
    f = only(errors, FindingCode.DEMO_HYPERLINK_OBJECT_INVALID)
    assert "'label'" in f.message

def test_a_null_hyperlink_url_is_refused() -> None:
    """`str(None)` is "None" — non-empty, and a perfectly valid-looking
    string. A coerced emptiness test passes it through to become a link
    pointing at the word None, so the check is on the STRING, not on its
    stringification."""
    errors = _hyperlink_demo({"url": None})
    f = only(errors, FindingCode.DEMO_HYPERLINK_ADDRESS_INVALID)
    # `got None`, not `got 'None'`: the check saw the value, not its str().
    assert "got None." in f.message

def test_an_empty_hyperlink_url_is_refused() -> None:
    only(
        _hyperlink_demo({"url": "   "}),
        FindingCode.DEMO_HYPERLINK_ADDRESS_INVALID,
    )

def test_a_scalar_hyperlink_demo_value_is_validated_too() -> None:
    """A URL column takes a bare address as well as a record. Checking only
    the record shape left `Link: null` and `Link: 123` unvalidated — and the
    generator refuses both, so the build surfaced a traceback instead of a
    finding. A validator must refuse everything its generator refuses."""
    for bad in (None, 123, ""):
        only(
            _hyperlink_demo(bad),
            FindingCode.DEMO_HYPERLINK_ADDRESS_INVALID,
        )

def _named_group(name: str) -> SiteGroup:
    """One site group. The four membership booleans are the loader's own
    defaults for a declaration that omits them — see `_optional_bool`."""
    return SiteGroup(
        name=name,
        description="d",
        owner_group="Site Owners",
        allow_members_edit_membership=False,
        allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False,
        only_allow_members_view_membership=False,
    )

def test_names_that_differ_only_in_case_are_refused() -> None:
    """SharePoint resolves group, permission-level and view names
    case-insensitively and will not hold two that differ only in case. A
    build that permits both produces a deploy that creates the first and
    collides on the second, mid-run, after the site has already changed.

    Caught here so the collision is a build error rather than a half-applied
    paste.
    """
    schema = make_schema(make_table("Project", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Project"],
        permissions=PermissionsConfig(
            levels=[
                CustomPermissionLevel(
                    name=name, description="d", base_permissions=["ViewListItems"],
                )
                for name in ("APP Reader", "app reader")
            ],
            groups=[_named_group("APP Owners"), _named_group("app owners")],
            default_policy=None,
            overrides={},
        ),
        views={
            "Project": [
                ViewDef(title="Open", fields=["Title"], default=True),
                ViewDef(title="open", fields=["Title"]),
            ],
        },
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    for code in (
        FindingCode.DUPLICATE_PERMISSION_LEVEL_NAME,
        FindingCode.DUPLICATE_GROUP_NAME,
        FindingCode.DUPLICATE_VIEW_TITLE,
    ):
        # Each code also fires on an exact duplicate, so the case clause is
        # the one part of the message this test is actually about.
        assert "only in case" in only(errors, code).message

def test_a_lookup_targets_display_column_counts_as_an_index() -> None:
    """The picker's index is real and spends a real slot, so the ceiling must
    see it. Declaring 20 and needing a 21st has to fail at validate time, not at
    deploy time on someone's tenant."""
    schema = make_schema(
        make_table("Event", column("Status")),
        make_table("FollowUp", column("Event", "int", ref="Event.Id")),
    )
    bundle = make_bundle(entities=["Event", "FollowUp"])
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(schema, bundle)
    assert "Title" in vc.effective_indexes("Event")
    # The child is not a target of anything.
    assert vc.effective_indexes("FollowUp") == set()

def _cross_site_only_target(*, calculated: bool) -> tuple[Schema, MappingBundle]:
    """FlowRunLog is pointed at by exactly one ref, and that ref is cross-site."""
    label = column("Label", "calculated_text" if calculated else "nvarchar")
    schema = make_schema(
        make_table("FlowRunLog", column("Title"), label),
        make_table("Request", column("Origin", "int", ref="FlowRunLog.Id")),
    )
    bundle = make_bundle(
        entities={
            "FlowRunLog": EntityMapping(
                name="FlowRunLog", kind="List", base_template=100,
                site_role="default", display_column="Label",
            ),
            "Request": EntityMapping(
                name="Request", kind="List", base_template=100, site_role="default",
            ),
        },
        cross_site_reference_columns=[CrossSiteRef(entity="Request", column="Origin")],
        calculated_formulas=(
            {"FlowRunLog": {"Label": "=[Title]"}} if calculated else {}
        ),
    )
    return schema, bundle

def test_a_cross_site_only_target_spends_no_index() -> None:
    """A cross-site ref becomes a Choice + URL pair on the SOURCE list. Nothing
    enumerates FlowRunLog, so it has no picker — charging it an index would spend
    one of its twenty on a query that never happens."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    schema, bundle = _cross_site_only_target(calculated=False)
    vc = ValidationContext.build(schema, bundle)
    assert vc.effective_indexes("FlowRunLog") == set()

def test_a_cross_site_only_target_is_not_told_its_picker_breaks() -> None:
    """The warning claims 'this list's lookup picker stops working'. Said about a
    list with no picker it is simply false, and the author's only way to silence
    it is to accept a consequence that cannot occur."""
    schema, bundle = _cross_site_only_target(calculated=True)
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_DISPLAY_COLUMN_UNINDEXABLE,
    )

def test_a_target_of_both_ref_kinds_keeps_its_index() -> None:
    """Per-pair, not per-entity. Excluding every entity NAMED in
    cross_site_reference_columns would strip the index off a list whose picker is
    real, which is the same defect pointing the other way."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    schema = make_schema(
        make_table("FlowRunLog", column("Title")),
        make_table("Request", column("Origin", "int", ref="FlowRunLog.Id")),
        make_table("Alert", column("Source", "int", ref="FlowRunLog.Id")),
    )
    bundle = make_bundle(
        entities=["FlowRunLog", "Request", "Alert"],
        cross_site_reference_columns=[CrossSiteRef(entity="Request", column="Origin")],
    )
    vc = ValidationContext.build(schema, bundle)
    assert vc.effective_indexes("FlowRunLog") == {"Title"}

def test_a_calculated_display_column_does_not_count_as_an_index() -> None:
    """It cannot be indexed, so counting it would push a schema over the ceiling
    for an index that cannot exist — the failure mode in the other direction."""
    schema = make_schema(
        make_table("Event", column("Ref"), column("Label", "calculated_text")),
        make_table("FollowUp", column("Event", "int", ref="Event.Id")),
    )
    bundle = make_bundle(
        entities={
            "Event": EntityMapping(
                name="Event", kind="List", base_template=100,
                site_role="default", display_column="Label",
            ),
            "FollowUp": EntityMapping(
                name="FollowUp", kind="List", base_template=100, site_role="default",
            ),
        },
    )
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(schema, bundle)
    assert "Label" not in vc.effective_indexes("Event")

def _shape_warnings(where: Condition) -> list[str]:
    """The list-view-threshold warnings for one `where` clause on view `V`.

    The clause is a `Condition` rather than a YAML fragment, so the indentation
    that used to decide whether `where:` sat under the view or reparented itself
    to the top level of the mapping is gone. The old spelling needed each caller
    to write the six leading spaces out flush against the left margin and a
    docstring explaining why; a `Group` cannot be attached to the wrong thing.
    """
    schema = make_schema(
        make_table(
            "Job",
            column("Title"),
            column("Status"),
            column("DueDate", "date"),
            indexes=["Status"],
        ),
    )
    bundle = make_bundle(
        entities=["Job"],
        views={
            "Job": [
                ViewDef(title="V", fields=["Title", "Status", "DueDate"], where=where),
            ],
        },
    )
    return [
        f.message
        for f in validate_against_mapping(schema, bundle)
        if f.code is FindingCode.UNINDEXED_FILTER_COLUMNS
    ]

def test_an_or_needs_every_branch_indexed() -> None:
    """An OR cannot narrow to one index. A row matching only the unindexed
    branch is still a row SharePoint has to find, so an indexed branch beside
    an unindexed one buys nothing — and scoring it safe because SOME filtered
    column is indexed is how a scanning view passes validation."""
    where = Group("any_of", (
        Leaf(field="Status", op="eq", value="Open"),
        Leaf(field="DueDate", op="leq", value="today"),
    ))
    assert len(_shape_warnings(where)) == 1

def test_an_or_with_every_branch_indexed_is_quiet() -> None:
    """Both branches narrow, so neither forces a scan."""
    where = Group("any_of", (
        Leaf(field="Status", op="eq", value="Open"),
        Leaf(field="Status", op="eq", value="Held"),
    ))
    assert _shape_warnings(where) == []

def test_an_and_needs_only_one_branch_indexed() -> None:
    """Measured at 6,000 items: an unindexed comparison refused on its own is
    served when ANDed with an indexed one, in either order — SharePoint picks
    the index rather than taking the first column and stopping. So an AND is
    covered by one indexed condition wherever it sits, and this test is what
    stops the OR rule above being applied to both.

    `all_of` explicitly: the YAML this replaces spelled it as a bare list,
    which `parse_condition` turns into exactly this group.
    """
    where = Group("all_of", (
        Leaf(field="Status", op="eq", value="Open"),
        Leaf(field="DueDate", op="leq", value="today"),
    ))
    assert _shape_warnings(where) == []
