# test/test_extract.py
"""The reverse direction: a live list's field XML back to schema + mapping.

Everything here is tested against `rg-project-live-extract.json`, a REAL
read of a real research-governance list taken by `extract.js.txt` and
committed after the tenant host in it was replaced with
`example.sharepoint.com`. Nothing else in it was edited, so it is the only
evidence in this repository of what a live SharePoint list actually stores,
and the decoder is tested against it rather than against XML written here
from memory.

The list exercises both halves of the recovery rule. Six severity chains,
two overdue-date formatters, one single-comparison validation rule and one
form-visibility formula are recovered and then re-composed by the shipped
forward generator; a data-bar formatter, three `OR(ISBLANK(...))`
validation rules and a two-clause visibility formula are refused and
reported. A test below runs the forward generator over each recovered
declaration and compares the result to what the site stores, which is the
property the whole extractor rests on.
"""

import functools
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from _console import ScriptedConsole, collapsed
from _node import NODE
from _paths import FIXTURES
from typer.testing import CliRunner, Result

from dbml_sharepoint.analysis.condition_rendering import to_validation
from dbml_sharepoint.analysis.forms import compose_visibility
from dbml_sharepoint.analysis.styles import expand_style
from dbml_sharepoint.cli import app
from dbml_sharepoint.extract.decode import (
    DecodedEntity,
    Extraction,
    Unrecovered,
    decode_list,
    new_enum_registry,
)
from dbml_sharepoint.extract.emit import (
    DEFAULT_PREFIX,
    render_mapping,
    render_release,
    render_schema,
)
from dbml_sharepoint.extract.field_xml import (
    FieldXmlError,
    builtin_reason,
    is_builtin,
    parse_field_xml,
)
from dbml_sharepoint.extract.folder import (
    FALLBACK_FOLDER,
    README_FILENAME,
    folder_for,
    folder_for_download,
    render_readme,
    seed,
)
from dbml_sharepoint.extract.list_url import ListUrlError, parse_list_url
from dbml_sharepoint.extract.notes import render_notes
from dbml_sharepoint.extract.run import (
    NOTES_RELPATH,
    check_identifier,
    entity_name_for,
    extraction_from,
    project_name_for,
)
from dbml_sharepoint.extract.run import write as write_extraction
from dbml_sharepoint.extract.sources import (
    LIVE_FORMAT,
    LIVE_KIND,
    Source,
    SourceError,
    load_live_json,
    load_source,
)
from dbml_sharepoint.extract.wizard import run_extract_wizard
from dbml_sharepoint.generators.extractgen import (
    DEFAULT_DOWNLOAD_NAME,
    EXTRACT_SCRIPT,
    NoListsError,
    download_name,
    generate_extract_js,
)
from dbml_sharepoint.model.conditions import parse_condition
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

SAMPLE = FIXTURES / "rg-project-live-extract.json"

#: The one list the fixture is a read of, and the table name every test
#: here gives it.
LIST_TITLE = "RG_Project"
ENTITY = "Project"

#: A site and the address-bar URL of `LIST_TITLE` on it. Not the fixture's
#: own site: nothing here reads the list, and an invented tenant keeps the
#: scrubbed host out of the strings these tests assert on.
SITE_URL = "https://contoso.sharepoint.com/sites/Risk"
LIST_URL = f"{SITE_URL}/Lists/{LIST_TITLE}/AllItems.aspx"

GENERATED_AT = "2026-08-27T00:00:00+00:00"

runner = CliRunner()


def field_xml(sp_type: str, body: str = "", **attrs: str) -> str:
    """One CAML `<Field>` element, in the shape SharePoint stores one.

    A builder rather than XML literals in every case, so the attribute
    under test is the only thing that differs between two of them and a
    typo in `StaticName` has nowhere to hide.
    """
    attrs.setdefault("StaticName", "A")
    attrs.setdefault("DisplayName", attrs["StaticName"])
    rendered = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    opened = f'<Field Type="{sp_type}" {rendered}'
    return f"{opened}>{body}</Field>" if body else f"{opened} />"


def choices(*members: str) -> str:
    return "<CHOICES>" + "".join(f"<CHOICE>{m}</CHOICE>" for m in members) + "</CHOICES>"


def _with_formatter(formatter: str) -> str:
    """A Text field carrying a column formatter, escaped as SharePoint does.

    The fixture stores its formatters as `&quot;`-escaped JSON inside a
    double-quoted attribute, so that is what is built here rather than the
    single-quoted spelling that would also parse.
    """
    return field_xml("Text", CustomFormatter=formatter.replace('"', "&quot;"))


def _decode(*xml: str, entity: str = "T", **kwargs: object) -> DecodedEntity:
    """Decode some fields with a fresh registry, discarding the notes."""
    kwargs.setdefault("unrecovered", [])
    return decode_list(
        [parse_field_xml(x) for x in xml],
        entity=entity, list_title="t", enums=new_enum_registry(),
        **kwargs,  # type: ignore[arg-type]
    )


@functools.lru_cache(maxsize=1)
def _source() -> Source:
    """The fixture, read once. Every record in it is frozen."""
    return load_source(SAMPLE)


def _extraction() -> Extraction:
    return extraction_from(_source(), entity_names={LIST_TITLE: ENTITY})


def _entity() -> DecodedEntity:
    return _extraction().entities[0]


def _stored(attribute: str) -> dict[str, str]:
    """{internal name: attribute} for every field that carries one.

    Read straight off the `RawField` records rather than out of the
    decoder's output, so a re-composition test below is comparing against
    the site's own string and not against something this tool produced.
    """
    return {
        f.internal_name: value
        for f in _source().lists[0].fields
        if (value := getattr(f, attribute))
    }


def _live_payload() -> dict[str, Any]:
    """The fixture's download, as a mutable object a test can damage."""
    return json.loads(SAMPLE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# --- The fixture, read as it arrived ---------------------------------------


def test_the_fixture_carries_no_tenant_data() -> None:
    """The fixture is a real read. It ships only because it was scrubbed.

    `test/test_probes.py` scans `test/manual/` for tenant identifiers and
    not `test/fixtures/`, so nothing else would catch a re-copied download
    that still had the site it came from in it.
    """
    text = SAMPLE.read_text(encoding="utf-8")
    lowered = text.lower()
    for identifier in ("tenant-a", "org-a", "user-a", "msteams_"):
        assert identifier not in lowered, identifier
    assert not re.findall(r"[\w.%+-]+@[\w.-]+\.\w{2,}", text)
    assert _source().site_url == "https://example.sharepoint.com/sites/Research"
    assert "\r" not in text, "the fixture must be LF; see AGENTS.md on generated files"
    assert not text.startswith("\ufeff")


def test_the_download_is_read_with_a_byte_order_mark(tmp_path: Path) -> None:
    """A download re-saved by an editor can carry one, and `json.loads`
    refuses it, so `utf-8-sig` is what reads the file and this is the test
    that would fail if it stopped being."""
    path = tmp_path / "download.json"
    path.write_bytes(b"\xef\xbb\xbf" + SAMPLE.read_bytes())
    assert len(load_source(path).lists[0].fields) == 117


def test_every_field_in_the_fixture_decodes() -> None:
    fields = _source().lists[0].fields
    assert len(fields) == 117
    assert all(f.sp_type for f in fields)
    assert _source().lists[0].title == LIST_TITLE


def test_the_built_ins_are_skipped_and_title_is_not() -> None:
    """Eighty-five of the hundred and seventeen fields on an ordinary list
    are SharePoint's own. `Title` satisfies every built-in test and is
    still the one this tool manages, so it is kept."""
    entity = _entity()
    assert len(entity.skipped) == 85
    skipped = {name for name, _ in entity.skipped}
    assert "Title" not in skipped
    assert "ContentType" in skipped
    assert {reason for _, reason in entity.skipped} == {
        "a known built-in column name",
        'marked Hidden="TRUE"',
        'marked FromBaseType="TRUE" (inherited from the list template)',
    }
    content_type = next(
        f for f in _source().lists[0].fields if f.internal_name == "ContentType"
    )
    assert is_builtin(content_type)
    assert builtin_reason(content_type) == "a known built-in column name"


def test_a_non_field_element_is_refused_by_name() -> None:
    with pytest.raises(FieldXmlError, match="expected a <Field> element"):
        parse_field_xml("<Fields />")
    with pytest.raises(FieldXmlError, match="not parseable as XML"):
        parse_field_xml("<Field")
    with pytest.raises(FieldXmlError, match="neither StaticName nor Name"):
        parse_field_xml('<Field Type="Text" DisplayName="x" />')


# --- The type table, field type by field type ------------------------------


#: What each of the fixture's columns must decode to. Every branch of
#: `_column_type` that the real read exercises, pinned to the read rather
#: than to the branch, so a change to the table is checked against evidence.
EXPECTED_TYPES = {
    "Title": "nvarchar",
    "ProjectType": "project_type",
    "Department": "nvarchar",
    "PrincipalInvestigator": "nvarchar",
    "SiteInvestigator": "person",
    "ProtocolReference": "nvarchar",
    "Summary": "richtext",
    "EthicsPathway": "ethics_pathway",
    "ParticipantInvolvement": "participant_involvement",
    "ReviewingHREC": "nvarchar",
    "EthicsStatus": "ethics_status",
    "EthicsReference": "nvarchar",
    "SubmittedDate": "date",
    "EthicsDecisionDate": "date",
    "EthicsApprovalExpiry": "date",
    "ConditionsStatus": "conditions_status",
    "ApprovalConditions": "richtext",
    "SiteAuthorisationStatus": "site_authorisation_status",
    "SSASubmittedDate": "date",
    "AuthorisationDate": "date",
    "AuthorisationReference": "nvarchar",
    "AuthorisedBy": "nvarchar",
    "ProjectStage": "project_stage",
    "NextReportDue": "date",
    "LastReportSubmitted": "date",
    "LatestAmendmentReference": "nvarchar",
    "LatestAmendmentStatus": "latest_amendment_status",
    "LatestAmendmentDate": "date",
    "AmendmentCount": "number",
    "GovernanceNotes": "richtext",
    "CompletedDate": "date",
    "SiteReadiness": "calculated_text",
}


def test_the_fixture_decodes_to_the_expected_types() -> None:
    entity = _entity()
    assert {c.name: c.dbml_type for c in entity.columns} == EXPECTED_TYPES
    assert entity.indexes == [
        "EthicsStatus", "SiteAuthorisationStatus", "ProjectStage", "NextReportDue",
    ]


@pytest.mark.parametrize(("xml", "expected"), [
    (field_xml("Text", MaxLength="255"), "nvarchar"),
    (field_xml("Note", NumLines="6"), "longtext"),
    (field_xml("Note", RichText="TRUE"), "richtext"),
    (field_xml("Boolean"), "boolean"),
    (field_xml("URL"), "hyperlink"),
    (field_xml("User", UserSelectionMode="PeopleOnly"), "person"),
    (field_xml("DateTime"), "datetime"),
    (field_xml("DateTime", Format="DateOnly"), "date"),
    (field_xml("Number"), "number"),
    (field_xml("MultiChoice", choices("x"), Mult="TRUE"), "a[]"),
    (field_xml("Calculated", "<Formula>=1</Formula>", ResultType="Text"),
     "calculated_text"),
    (field_xml("Calculated", "<Formula>=1</Formula>", ResultType="Number"),
     "calculated_number"),
    (field_xml("Calculated", "<Formula>=1</Formula>", ResultType="DateTime"),
     "calculated_date"),
])
def test_one_field_type_at_a_time(xml: str, expected: str) -> None:
    """The branches the fixture does not reach.

    Only the `Type` attribute and the qualifiers this repository already
    deploys are asserted on; nothing here claims a SharePoint behaviour the
    fixture does not show.
    """
    assert [c.dbml_type for c in _decode(xml).columns] == [expected]


@pytest.mark.parametrize(("xml", "kind"), [
    (field_xml("Lookup", List="{guid}"), "lookup-target"),
    (field_xml("Thumbnail"), "unsupported-field-type"),
    (field_xml("Choice"), "empty-choice"),
    (field_xml("Calculated", "<Formula>=1</Formula>", ResultType="Currency"),
     "calculated-result-type"),
])
def test_a_field_with_no_dbml_type_is_dropped_and_named(xml: str, kind: str) -> None:
    """Dropped, never guessed at, and never silently.

    A shorter schema than the list has is the failure mode; every drop puts
    an entry in the notes so the operator can see what is missing.
    """
    unrecovered: list[Unrecovered] = []
    decoded = _decode(xml, unrecovered=unrecovered)
    assert decoded.columns == []
    assert [u.kind for u in unrecovered] == [kind]
    assert unrecovered[0].subject == "T.A"


def test_an_unsupported_field_quotes_its_element() -> None:
    """The notes have to carry enough for somebody to decide what to do."""
    xml = field_xml("Thumbnail", StaticName="Pic")
    unrecovered: list[Unrecovered] = []
    _decode(xml, unrecovered=unrecovered)
    assert xml in unrecovered[0].detail


@pytest.mark.parametrize(("xml", "kind"), [
    (field_xml("Number"), "number-precision"),
    (field_xml("Choice", choices("x"), FillInChoice="TRUE"), "fill-in-choice"),
    (field_xml("User", UserSelectionMode="1"), "user-selection-mode"),
    (field_xml("Text", StaticName="Risk_x0020_Owner", DisplayName="Risk Owner"),
     "internal-name"),
    (field_xml("Calculated", ResultType="Text"), "calculated-formula-missing"),
])
def test_a_column_that_survives_with_a_caveat_still_reports_it(
    xml: str, kind: str,
) -> None:
    """The column is emitted AND the difference is named.

    Dropping these would hide a column the list has; emitting them silently
    would claim a fidelity the forward build does not deliver.
    """
    unrecovered: list[Unrecovered] = []
    decoded = _decode(xml, unrecovered=unrecovered)
    assert len(decoded.columns) == 1
    assert kind in [u.kind for u in unrecovered]


@pytest.mark.parametrize("xml", [
    field_xml("Text", StaticName="Probability", DisplayName="Likelihood"),
    field_xml("Text", StaticName="Risk_x0028_cause_x27a1__xfe0f_ev",
              DisplayName="Description"),
])
def test_a_column_renamed_after_creation_reports_its_fossil_name(xml: str) -> None:
    """The internal name decodes to a different title than the one shown."""
    unrecovered: list[Unrecovered] = []
    decoded = _decode(xml, unrecovered=unrecovered)
    assert len(decoded.columns) == 1
    renamed = [u for u in unrecovered if u.kind == "renamed-column"]
    assert len(renamed) == 1
    assert renamed[0].subject.startswith("T.")


@pytest.mark.parametrize("xml", [
    field_xml("Text", StaticName="Due_x002f_reviewdate",
              DisplayName="Due/review date"),
    field_xml("Text", StaticName="Status", DisplayName="Status "),
    field_xml("Text", StaticName="Risk_x0020_Owner", DisplayName="Risk Owner"),
])
def test_a_current_internal_name_is_not_reported_as_renamed(xml: str) -> None:
    """Whitespace and case differences are SharePoint's own, not a rename."""
    unrecovered: list[Unrecovered] = []
    _decode(xml, unrecovered=unrecovered)
    assert "renamed-column" not in [u.kind for u in unrecovered]


def test_a_field_element_carrying_a_dtd_is_refused() -> None:
    """MEASURED 2026-08-27: `ET.fromstring` refuses an external entity and
    expands an internal one, so a DOCTYPE is the whole amplification
    surface. A real SchemaXml is one element with no prolog."""
    with pytest.raises(FieldXmlError, match="document type declaration"):
        parse_field_xml(
            '<!DOCTYPE f [<!ENTITY a "aa">]>' + field_xml("Text", DisplayName="&a;"),
        )


def test_a_calculated_column_carries_no_default() -> None:
    """`typemap` refuses a default on a calculated column, so one is dropped
    rather than emitted into a schema the build would then reject."""
    unrecovered: list[Unrecovered] = []
    decoded = _decode(
        field_xml(
            "Calculated", "<Formula>=1</Formula><Default>x</Default>",
            ResultType="Text",
        ),
        unrecovered=unrecovered,
    )
    assert decoded.columns[0].default is None
    assert "calculated-default" in [u.kind for u in unrecovered]


def test_a_boolean_default_becomes_a_boolean() -> None:
    """SharePoint spells it `1`; DBML spells it `true`."""
    decoded = _decode(field_xml("Boolean", "<Default>1</Default>"))
    assert decoded.columns[0].default is True


# --- Enums -----------------------------------------------------------------


def test_columns_offering_the_same_choices_share_one_enum() -> None:
    """The only evidence a read carries about a shared vocabulary.

    Two columns with the identical ordered member list came from one enum in
    whatever schema built the list, so they get one here.
    """
    members = choices("Low", "High")
    decoded = _decode(
        field_xml("Choice", members, StaticName="A"),
        field_xml("Choice", members, StaticName="B"),
    )
    assert {c.dbml_type for c in decoded.columns} == {"a"}


def test_a_different_member_order_is_a_different_enum() -> None:
    """Order is meaningful: it is the order the picker renders in."""
    decoded = _decode(
        field_xml("Choice", choices("x", "y"), StaticName="A"),
        field_xml("Choice", choices("y", "x"), StaticName="B"),
    )
    assert [c.dbml_type for c in decoded.columns] == ["a", "b"]


def test_an_enum_name_that_would_collide_with_a_type_is_qualified() -> None:
    """`Enum date { ... }` produces a schema whose every `date` column is
    silently that enum. The registry moves out of the way instead."""
    decoded = _decode(
        field_xml("Choice", choices("x"), StaticName="Date"), entity="Risk",
    )
    assert decoded.columns[0].dbml_type == "risk_date"


def test_the_fixture_yields_eight_enums_named_from_their_columns() -> None:
    assert _extraction().enum_names() == {
        "project_type", "ethics_pathway", "participant_involvement",
        "ethics_status", "conditions_status", "site_authorisation_status",
        "project_stage", "latest_amendment_status",
    }


# --- Verification: the forward generator re-run over what was recovered ----
#
# This is the property the extractor rests on. An inversion is accepted
# only when the SHIPPED generator reproduces the artifact the site stores,
# so these tests re-run that generator here, independently of `inverse.py`,
# against the strings the read actually returned.


def test_every_recovered_formatter_reproduces_the_stored_one() -> None:
    """Eight column formatters were recovered as style specs. Expanding
    each one has to give back the JSON the live list holds."""
    entity = _entity()
    stored = _stored("custom_formatter")
    assert set(entity.column_formatting) == {
        "EthicsStatus", "SiteAuthorisationStatus", "ProjectStage",
        "ConditionsStatus", "LatestAmendmentStatus", "SiteReadiness",
        "EthicsApprovalExpiry", "NextReportDue",
    }
    for column, spec in entity.column_formatting.items():
        expanded = expand_style(spec, f"{ENTITY}.{column}")
        assert expanded == json.loads(stored[column]), column


def test_the_recovered_severity_specs_carry_what_the_formatter_showed() -> None:
    """`SiteReadiness` is calculated, so its formatter reads past the
    `string;#` prefix SharePoint puts on a calculated value, and the
    recovered spec has to say so or it would expand to a chain that never
    matches."""
    formatting = _entity().column_formatting
    assert formatting["SiteReadiness"]["calculated"] is True
    assert formatting["EthicsStatus"].get("calculated") is None
    assert formatting["NextReportDue"] == {
        "style": "overdue-date",
        "guard": {"field": "ProjectStage", "not": ["Completed", "Discontinued"]},
    }


def test_the_recovered_validation_reproduces_the_stored_formula() -> None:
    """One of the four validation rules is a single comparison, which is
    all `column_validation` declares. Re-rendering it has to give back what
    the site stores.

    Compared with the brackets stripped that SharePoint strips on save.
    That normalisation is recorded, live-verified, in
    `templates/deploy/_field_reconcile.js.j2`; it is applied here rather
    than borrowed from `inverse.py`, so this test would still fail if the
    inverter's own comparison went wrong.
    """
    entity = _entity()
    types = {c.name: c.dbml_type for c in entity.columns}
    assert set(entity.column_validation) == {"AmendmentCount"}
    declared = entity.column_validation["AmendmentCount"]
    assert declared["message"]
    condition = parse_condition(declared["when"], f"{ENTITY}.AmendmentCount")
    rendered = f"={to_validation(condition, types)}"
    stripped = re.sub(r"\[([A-Za-z0-9_]+)\]", r"\1", rendered)
    assert stripped == _stored("validation_formula")["AmendmentCount"]


def test_the_recovered_visibility_reproduces_the_stored_formula() -> None:
    """`compose_visibility` renders the gate and the condition together, so
    re-running it is an exact comparison rather than a normalised one."""
    entity = _entity()
    types = {c.name: c.dbml_type for c in entity.columns}
    assert set(entity.form_visibility) == {"ApprovalConditions"}
    declared = entity.form_visibility["ApprovalConditions"]
    # Neither form is turned off, so the declaration spells only `when`.
    assert set(declared) == {"when"}
    rendered = compose_visibility(
        new=True, existing=True,
        when=parse_condition(declared["when"], f"{ENTITY}.ApprovalConditions"),
        types=types,
    )
    assert rendered == _stored("client_validation_formula")["ApprovalConditions"]


#: The declaration shapes `form_visibility` and `column_validation` accept.
#: The fixture's list uses one of each, so the rest are round-tripped
#: through the SHIPPED generator below rather than left untested. The
#: observed string is not written here from memory: it is whatever
#: `compose_visibility` and `to_validation` emit, which is the same code
#: the deploy writes to the site.
_OPEN = {"field": "Stage", "op": "eq", "value": "Open"}
_CLOSED = {"field": "Stage", "op": "eq", "value": "Closed"}
_TYPES = {"Stage": "nvarchar", "ReviewedOn": "date", "Count": "number"}


@pytest.mark.parametrize("declared", [
    {"when": [_OPEN]},
    {"when": [_OPEN, {"field": "Owner", "op": "neq", "value": ""}]},
    {"when": [{"any_of": [_OPEN, _CLOSED]}]},
    # The gate spellings. A recovered declaration names only the form it
    # turns off, because that is how the shipped mappings are authored and
    # an extracted one should diff against them.
    {"new": False},
    {"existing": False},
    {"new": False, "when": [_OPEN]},
    {"existing": False, "when": [_OPEN]},
    {"new": False, "existing": False},
])
def test_a_visibility_declaration_survives_the_round_trip(
    declared: dict[str, Any],
) -> None:
    from dbml_sharepoint.extract.inverse import invert_form_visibility
    context = "T.Notes"
    types = {**_TYPES, "Owner": "nvarchar"}
    when = declared.get("when")
    observed = compose_visibility(
        new=declared.get("new", True),
        existing=declared.get("existing", True),
        when=parse_condition(when, context) if when is not None else None,
        types=types,
    )
    assert invert_form_visibility(observed, types, context) == declared


@pytest.mark.parametrize("when", [
    [{"field": "ReviewedOn", "op": "leq", "value": "today"}],
    [{"field": "Count", "op": "geq", "value": 0}],
    [{"field": "Stage", "op": "neq", "value": "Closed"}],
])
def test_a_validation_declaration_survives_the_round_trip(
    when: list[dict[str, Any]],
) -> None:
    """Fed the SPELLING SharePoint stores, not the one the build wrote.

    The site strips brackets it does not need and removes whitespace on
    save. That normalisation is recorded, live-verified, in
    `templates/deploy/_field_reconcile.js.j2`, and it is applied here so
    the inverter meets the string a read actually returns.
    """
    from dbml_sharepoint.extract.inverse import invert_column_validation
    context = "T.A"
    message = "Check this value."
    rendered = f"={to_validation(parse_condition(when, context), _TYPES)}"
    stored = re.sub(r"\s+", "", re.sub(r"\[([A-Za-z0-9_]+)\]", r"\1", rendered))
    assert invert_column_validation(stored, message, _TYPES, context) == {
        "when": when, "message": message,
    }


@pytest.mark.parametrize(("when", "recovered"), [
    ([{"field": "ReviewedOn", "op": "lt", "value": "today"}],
     [{"field": "ReviewedOn", "op": "leq", "value": "today-1"}]),
    ([{"field": "ReviewedOn", "op": "leq", "value": "today+365"}],
     [{"field": "ReviewedOn", "op": "leq", "value": "today+365"}]),
    ([{"field": "ReviewedOn", "op": "geq", "value": "today"}],
     [{"field": "ReviewedOn", "op": "gt", "value": "today-1"}]),
])
def test_a_rule_against_the_save_instant_comes_back_in_its_canonical_spelling(
    when: list[dict[str, Any]], recovered: list[dict[str, Any]],
) -> None:
    """MEASURED 2026-09-02: date rules render against [Modified], the save
    instant, with the offset on the column. Two spellings can render to one
    formula ("before today" is "on or before yesterday"), so the inverter
    returns the canonical one, which re-renders to the same formula."""
    from dbml_sharepoint.extract.inverse import invert_column_validation
    context = "T.A"
    rendered = f"={to_validation(parse_condition(when, context), _TYPES)}"
    stored = re.sub(r"\s+", "", re.sub(r"\[([A-Za-z0-9_]+)\]", r"\1", rendered))
    assert invert_column_validation(stored, "m", _TYPES, context) == {
        "when": recovered, "message": "m",
    }


def test_the_calculated_formula_comes_back_from_the_read() -> None:
    """The formula is the part somebody modifying the list most needs, and
    it is in the field XML of a live read."""
    formulas = _entity().calculated_formulas
    assert set(formulas) == {"SiteReadiness"}
    assert formulas["SiteReadiness"].startswith('=IF(EthicsStatus="Withdrawn"')
    assert "SiteAuthorisationStatus" in formulas["SiteReadiness"]


def test_what_the_inverters_refused_is_reported_and_not_in_the_mapping() -> None:
    """The refuse path, measured on the same read.

    A data-bar formatter, three `OR(ISBLANK(...))` validation rules and a
    two-clause visibility formula are outside what this tool re-derives. A
    regression that started accepting one of them shows up here as a
    missing entry rather than as a mapping nobody checked.
    """
    extraction = _extraction()
    entity = extraction.entities[0]
    refused: dict[str, set[str]] = {}
    for item in extraction.unrecovered:
        refused.setdefault(item.kind, set()).add(item.subject)

    assert refused["column-formatting"] == {
        f"{ENTITY}.AmendmentCount", f"{ENTITY}.EthicsPathway",
    }
    assert refused["column-validation"] == {
        f"{ENTITY}.SubmittedDate", f"{ENTITY}.EthicsDecisionDate",
        f"{ENTITY}.AuthorisationDate",
    }
    assert refused["form-visibility"] == {f"{ENTITY}.CompletedDate"}

    for kind, section in (
        ("column-formatting", entity.column_formatting),
        ("column-validation", entity.column_validation),
        ("form-visibility", entity.form_visibility),
    ):
        assert not {f"{ENTITY}.{c}" for c in section} & refused[kind], kind


def test_the_data_bar_formatter_is_preserved_verbatim() -> None:
    """`invert_column_formatting` proposes severity and overdue-date and
    nothing else, so a data bar is kept whole rather than re-derived into a
    style spec that would deploy something else."""
    preserved = _entity().preserved_formatters
    assert set(preserved) == {"AmendmentCount", "EthicsPathway"}
    assert "sp-field-dataBars" in preserved["AmendmentCount"]
    assert json.loads(preserved["AmendmentCount"]) == json.loads(
        _stored("custom_formatter")["AmendmentCount"],
    )


def test_a_formatter_outside_the_vocabulary_is_preserved_verbatim() -> None:
    """The CustomFormatter decision: re-derive what the style vocabulary
    produces, keep the rest whole rather than inventing a mapping."""
    formatter = json.dumps({"elmType": "div", "txtContent": "@currentField"})
    unrecovered: list[Unrecovered] = []
    decoded = _decode(_with_formatter(formatter), unrecovered=unrecovered)
    assert decoded.preserved_formatters == {"A": formatter}
    assert decoded.column_formatting == {}
    assert [u.kind for u in unrecovered] == ["column-formatting"]


def test_the_read_reports_views_and_the_form_formatter() -> None:
    """Read and reported, never decoded. Recovering a `views:` declaration
    from CAML is a second inversion problem this tool does not attempt, and
    the list form's own formatter is left on the site untouched."""
    source_list = _source().lists[0]
    assert len(source_list.views) == 6
    assert source_list.content_type_formatter
    kinds = {u.kind for u in _extraction().unrecovered}
    assert "views" in kinds
    assert "form-formatting" in kinds


def test_a_list_with_no_description_is_named_before_build_refuses_it() -> None:
    """The fixture's list has an empty Description, which `build` refuses as
    `entity_has_no_note`. It is reported here so the operator meets it in
    the notes rather than as a surprise from the next command."""
    assert _source().lists[0].description == ""
    notes = render_notes(_extraction(), generated_at=GENERATED_AT)
    headings = re.findall(r"^### (.+)$", notes, re.MULTILINE)
    assert headings[0] == "Tables with no Note:"
    assert "## What a read does not carry" in notes


# --- What is emitted -------------------------------------------------------


def test_the_emitted_schema_parses(tmp_path: Path) -> None:
    """The output IS `build`'s input, so this is the contract."""
    path = tmp_path / "schema.dbml"
    path.write_text(render_schema(_extraction(), project="project"), newline="\n")
    schema = parse_dbml(path)
    assert [t.name for t in schema.tables] == [ENTITY]
    assert len(schema.enums) == 8
    assert {c.name for c in schema.tables[0].columns} >= set(EXPECTED_TYPES)


def test_the_emitted_mapping_loads(tmp_path: Path) -> None:
    path = tmp_path / "mapping.yaml"
    path.write_text(render_mapping(_extraction()), newline="\n")
    bundle = load_mapping(path)
    assert bundle.mapping.prefix == DEFAULT_PREFIX
    assert set(bundle.mapping.entities) == {ENTITY}
    assert set(bundle.mapping.column_formatting[ENTITY]) == set(
        _entity().column_formatting,
    )
    assert set(bundle.mapping.form_visibility[ENTITY].columns) == {"ApprovalConditions"}
    assert set(bundle.mapping.column_validation[ENTITY].columns) == {"AmendmentCount"}


def test_the_emitted_release_loads(tmp_path: Path) -> None:
    from dbml_sharepoint.model.release import load_release
    path = tmp_path / "release.yaml"
    path.write_text(
        render_release(source=LIVE_KIND, generated_at=GENERATED_AT), newline="\n",
    )
    release = load_release(path)
    assert release.release_tag == "0.0.0"


def test_the_schema_synthesises_id_and_never_reads_one() -> None:
    """SharePoint provisions `Id` on every list, so a schema that declared it
    from the read would be telling the deploy to create it."""
    dbml = render_schema(_extraction(), project="project")
    assert re.search(r"^  Id +int +\[pk, increment\]$", dbml, re.MULTILINE)
    assert _decode(field_xml("Counter", StaticName="ID")).columns == []


def test_a_description_with_a_newline_does_not_break_the_dbml(tmp_path: Path) -> None:
    """A literal break inside a single-quoted DBML string is a parse error,
    so a multi-line SharePoint description is folded to one line."""
    decoded = _decode(field_xml("Text", Description="one&#10;two"))
    extraction = Extraction(entities=[decoded], source=LIVE_KIND)
    path = tmp_path / "s.dbml"
    path.write_text(render_schema(extraction, project="p"), newline="\n")
    assert parse_dbml(path).tables[0].columns[1].note == "one two"


def test_display_names_are_declared_only_when_a_title_differs() -> None:
    """`mode: auto` re-derives "Risk Owner" from `RiskOwner`, so a list whose
    titles all equal their internal names needs no section at all, and
    declaring one would have the deploy rewrite every title to the value it
    already holds.

    An override is recorded only for a title `auto` would not produce; the
    fixture has none, which is itself evidence that this list was deployed
    from a schema rather than built in the UI.
    """
    assert _entity().display_overrides == {}

    plain = _decode(field_xml("Text", StaticName="Owner"))
    assert "display_names" not in yaml.safe_load(
        render_mapping(Extraction(entities=[plain])),
    )

    derived = _decode(
        field_xml("Text", StaticName="RiskOwner", DisplayName="Risk Owner"),
    )
    assert derived.display_overrides == {}
    assert yaml.safe_load(
        render_mapping(Extraction(entities=[derived])),
    )["display_names"] == {"mode": "auto"}

    renamed = _decode(
        field_xml("Text", StaticName="RiskOwner", DisplayName="Accountable person"),
    )
    assert renamed.display_overrides == {"RiskOwner": "Accountable person"}
    assert yaml.safe_load(
        render_mapping(Extraction(entities=[renamed])),
    )["display_names"]["overrides"] == {"T": {"RiskOwner": "Accountable person"}}


def test_a_calculated_formula_comes_back_in_internal_names() -> None:
    """SharePoint stores the formula against DISPLAY names, because that is
    what it resolves them against when the field is created. The mapping is
    authored in internal names, so the rewrite runs backwards here."""
    decoded = _decode(
        field_xml("Text", StaticName="RiskOwner", DisplayName="Risk Owner"),
        field_xml(
            "Calculated",
            "<Formula>=UPPER([Risk Owner])</Formula>"
            '<FieldRefs><FieldRef Name="RiskOwner" /></FieldRefs>',
            StaticName="OwnerUpper", DisplayName="Owner Upper", ResultType="Text",
        ),
    )
    assert decoded.calculated_formulas == {"OwnerUpper": "=UPPER([RiskOwner])"}


# --- Writing ---------------------------------------------------------------


def test_write_lands_the_family_layout(tmp_path: Path) -> None:
    written = write_extraction(_extraction(), tmp_path, generated_at=GENERATED_AT)
    assert written.schema == tmp_path / "10-design" / "schema.dbml"
    assert written.mapping == tmp_path / "20-configure" / "mapping.yaml"
    assert written.release == tmp_path / "20-configure" / "release.yaml"
    assert written.notes == tmp_path / NOTES_RELPATH
    for path in (written.schema, written.mapping, written.release, written.notes):
        assert path.is_file()
        assert "\r" not in path.read_text(encoding="utf-8")


def test_write_reads_every_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated write produces a schema that parses to fewer columns than
    were extracted, and nothing downstream can tell that from a list that
    genuinely has fewer. So the writer verifies rather than trusting.

    The truncation is injected at the one writer, because a disk that
    short-writes is not reproducible and an untested read-back is the same
    as none.
    """
    def short(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text[: len(text) // 2], encoding="utf-8", newline="\n")

    monkeypatch.setattr("dbml_sharepoint.extract.run.write_artifact", short)
    with pytest.raises(OSError, match="read back differently"):
        write_extraction(_extraction(), tmp_path, generated_at=GENERATED_AT)


def test_a_preserved_formatter_is_written_beside_the_mapping(tmp_path: Path) -> None:
    formatter = json.dumps({"elmType": "div", "txtContent": "@currentField"})
    decoded = _decode(_with_formatter(formatter), entity="Risk")
    written = write_extraction(
        Extraction(entities=[decoded], source=LIVE_KIND), tmp_path,
        generated_at=GENERATED_AT,
    )
    assert written.preserved == (
        tmp_path / "20-configure" / "formatting" / "Risk.A.json",
    )
    assert json.loads(written.preserved[0].read_text()) == json.loads(formatter)


# --- Naming ----------------------------------------------------------------


def test_a_table_name_is_derived_without_guessing_at_plurals() -> None:
    """`Statuses` -> `Statu` is how a plural-stripper fails, and a wrong name
    is harder to notice than an ugly one."""
    assert entity_name_for("Risks") == "Risks"
    assert entity_name_for("RG_Project") == "RGProject"
    assert entity_name_for("Risk register") == "RiskRegister"
    with pytest.raises(SourceError, match="cannot derive a table name"):
        entity_name_for("2026")


def test_the_project_name_comes_from_the_first_entity() -> None:
    assert project_name_for(["RiskRegister"]) == "risk_register"


@pytest.mark.parametrize("value", ["1risk", "risk-register", "", "risk register"])
def test_a_name_that_is_not_a_dbml_identifier_is_refused(value: str) -> None:
    with pytest.raises(SourceError, match="must be a DBML identifier"):
        check_identifier(value, "--entity")


# --- The per-list folder ----------------------------------------------------


@pytest.mark.parametrize(("title", "expected"), [
    ("RG_Project", "RG_Project"),
    ("Risk register", "Risk-register"),
    ("Risks / Controls", "Risks-Controls"),
    ("..", FALLBACK_FOLDER),
    # A Japanese list title, written as escapes so this file stays ASCII.
    # Every character in it is outside the safe set, so nothing is left.
    ("\u9805\u76ee", FALLBACK_FOLDER),
])
def test_the_folder_is_named_after_the_list(title: str, expected: str) -> None:
    """Sanitised for a directory name and nothing more, and never empty: a
    title with nothing usable in it still has to land somewhere."""
    assert folder_for(title) == Path(expected)


def test_the_folder_and_the_download_agree() -> None:
    """The whole flow rests on this. The readme says to save the download
    into the folder, and the wizard then looks for it there by name."""
    for title in ("RG_Project", "Risk register", "Risks / Controls"):
        assert download_name([title]) == f"{folder_for(title).name}-extract.json"


@pytest.mark.parametrize("source", [
    # Named bare, from a directory that is not the list's own folder.
    Path("RG_Project-extract.json"),
    # From the browser's own download directory.
    Path("/tmp/dl/RG_Project-extract.json"),  # noqa: S108
    # The in-place case below is keyed on the parent's NAME, so a download
    # sitting in some other list's folder does not join that one.
    Path("Risk-register") / "RG_Project-extract.json",
])
def test_the_default_directory_is_the_lists_own_folder(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One folder per list, wherever the download was read from."""
    monkeypatch.chdir(tmp_path)
    assert folder_for_download(source, LIST_TITLE) == Path(LIST_TITLE)


def test_a_download_already_in_the_lists_folder_is_extracted_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both ways of naming the same file, from the parent and from inside.
    The download is in the folder because the readme said to put it there,
    and a second folder of the same name nested inside it is not what
    either instruction promised."""
    folder = tmp_path / LIST_TITLE
    folder.mkdir()
    monkeypatch.chdir(tmp_path)
    from_parent = Path(LIST_TITLE) / download_name([LIST_TITLE])
    assert folder_for_download(from_parent, LIST_TITLE) == Path(LIST_TITLE)

    monkeypatch.chdir(folder)
    assert folder_for_download(Path(download_name([LIST_TITLE])), LIST_TITLE) == Path()


def test_the_readme_says_what_to_do_with_the_folder() -> None:
    readme = render_readme(list_title=LIST_TITLE, site_url=SITE_URL)
    assert LIST_TITLE in readme
    assert SITE_URL in readme
    # The three things it exists to say: which script to paste, what the
    # download will be called, and the command that reads it back.
    assert EXTRACT_SCRIPT in readme
    assert download_name([LIST_TITLE]) in readme
    assert f"dbml-sharepoint extract {download_name([LIST_TITLE])}" in readme
    assert NOTES_RELPATH.as_posix() in readme


#: markdownlint's default line length, and the rule as MD013 actually
#: applies it: a line past the limit is reported only when there is
#: whitespace beyond the limit to break at, so a long URL or a one-token
#: command is left alone. Asserting the plain length instead would be
#: stronger than the linter and would fail on a list title nothing is wrong
#: with. VERIFIED 2026-08-27 against markdownlint-cli2 0.18.1 with no
#: configuration, which is what an operator's own repository would use.
_MD013_WIDTH = 80


@pytest.mark.parametrize("title", [LIST_TITLE, "Risk register", "A" * 60])
def test_the_readme_is_wrapped_and_carries_no_bare_url(title: str) -> None:
    """It lands in an operator's project, where markdownlint's defaults
    apply to it. Both rules it can break depend on values not known until it
    renders: MD013 on the list title and the file names, MD034 on the site
    URL."""
    rendered = render_readme(list_title=title, site_url=SITE_URL)
    breakable = [
        line
        for line in rendered.splitlines()
        if len(line) > _MD013_WIDTH and " " in line[_MD013_WIDTH:]
    ]
    assert breakable == []
    assert f"`{SITE_URL}`" in rendered


def test_seeding_writes_the_script_and_the_readme(tmp_path: Path) -> None:
    """Both files, and the folder they go in, from one call. `--out` names
    the script and the readme follows it."""
    seeded = seed(
        list_title=LIST_TITLE,
        site_url=SITE_URL,
        generated_at=GENERATED_AT,
        script=tmp_path / LIST_TITLE / EXTRACT_SCRIPT,
    )
    assert seeded.folder == tmp_path / LIST_TITLE
    assert seeded.script.name == EXTRACT_SCRIPT
    assert seeded.readme is not None
    assert seeded.readme.name == README_FILENAME
    assert SITE_URL in seeded.script.read_text(encoding="utf-8")
    assert download_name([LIST_TITLE]) in seeded.readme.read_text(encoding="utf-8")


def test_seeding_leaves_an_existing_readme_alone(tmp_path: Path) -> None:
    """`readme.md` and `README.md` are the same file on Windows, so a
    `--out` aimed at a directory somebody else owns must not overwrite the
    one already there."""
    (tmp_path / README_FILENAME).write_text("mine\n", encoding="utf-8")
    seeded = seed(
        list_title=LIST_TITLE,
        site_url=SITE_URL,
        generated_at=GENERATED_AT,
        script=tmp_path / EXTRACT_SCRIPT,
    )
    assert seeded.readme is None
    assert (tmp_path / README_FILENAME).read_text(encoding="utf-8") == "mine\n"


# --- The list URL -----------------------------------------------------------


@pytest.mark.parametrize(("url", "site", "title"), [
    ("https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx",
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
    ("https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/",
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
    ("https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project",
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
    # The address bar percent-encodes a title with a space in it.
    ("https://contoso.sharepoint.com/sites/Risk/Lists/Risk%20Register/AllItems.aspx",
     "https://contoso.sharepoint.com/sites/Risk", "Risk Register"),
    # SharePoint's own Copy link puts `?web=1` on the clipboard, and a view
    # URL carries a RootFolder query and an anchor. None of them say which
    # list this is.
    (("https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx"
      "?viewid=1234&web=1#top"),
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
    # Lowercase, because an operator retyping the path has no reason to
    # keep the capital the address bar shows.
    ("https://contoso.sharepoint.com/sites/Risk/lists/RG_Project/AllItems.aspx",
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
    # A tenant root site has no /sites/ segment at all.
    ("https://contoso.sharepoint.com/Lists/RG_Project/AllItems.aspx",
     "https://contoso.sharepoint.com", "RG_Project"),
    # A site literally named Lists: the LAST segment is the list's.
    ("https://contoso.sharepoint.com/sites/Lists/Lists/RG_Project/AllItems.aspx",
     "https://contoso.sharepoint.com/sites/Lists", "RG_Project"),
    ("  https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx  ",
     "https://contoso.sharepoint.com/sites/Risk", "RG_Project"),
])
def test_a_list_url_splits_into_a_site_and_a_title(
    url: str, site: str, title: str,
) -> None:
    parsed = parse_list_url(url)
    assert parsed.site_url == site
    assert parsed.list_title == title


@pytest.mark.parametrize(("url", "message"), [
    # A site URL is the one thing an operator is most likely to paste, and
    # it does not name a list. Refused rather than guessed at, because the
    # title is the thing being read.
    ("https://contoso.sharepoint.com/sites/Risk", "no /Lists/<name>/ segment"),
    ("https://contoso.sharepoint.com/sites/Risk/SitePages/Home.aspx",
     "no /Lists/<name>/ segment"),
    ("https://contoso.sharepoint.com/sites/Risk/Lists/", "names no list"),
    ("https://contoso.sharepoint.com/sites/Risk/Lists/%20/", "names no list"),
    ("contoso.sharepoint.com/sites/Risk/Lists/RG_Project", "absolute https:// list URL"),
    ("http://contoso.sharepoint.com/sites/Risk/Lists/RG_Project",
     "absolute https:// list URL"),
    ("not a url", "absolute https:// list URL"),
])
def test_a_url_that_does_not_name_a_list_is_refused(url: str, message: str) -> None:
    with pytest.raises(ListUrlError, match=re.escape(message)):
        parse_list_url(url)


def test_a_host_containing_lists_is_not_cut_at_its_own_name() -> None:
    """The segment is searched for in the PATH, not in the whole URL."""
    parsed = parse_list_url("https://lists.sharepoint.com/sites/A/Lists/B/AllItems.aspx")
    assert parsed.site_url == "https://lists.sharepoint.com/sites/A"
    assert parsed.list_title == "B"


# --- The download, refused when it is damaged ------------------------------


def _download(body: str) -> str:
    """One download's JSON, with the format key already right."""
    return f'{{"format": "{LIVE_FORMAT}", {body}}}'


@pytest.mark.parametrize(("payload", "message"), [
    ('{"format": "something-else", "lists": []}', "was not written by"),
    (_download('"lists": []'), "declares no lists"),
    (_download('"lists": [1]'), "is not an object"),
    (_download('"lists": [{"fields": []}]'), "has no title"),
    (_download('"lists": [{"title": "a"}]'), "is missing or is not a list"),
    (_download('"lists": [{"title": "a", "fields": []}]'), "nothing to extract"),
    (_download('"lists": [{"title": "a", "fields": [1]}]'), "not a string of XML"),
    (_download('"lists": [{"title": "a", "fields": ["<Fields />"]}]'),
     "expected a <Field> element"),
    ("not json", "not valid JSON"),
    ("[]", "expected a JSON object"),
])
def test_a_damaged_download_is_refused_with_a_sentence(
    payload: str, message: str,
) -> None:
    """Refused whole, never half-decoded.

    A download that lost some of its fields decodes into a schema that
    parses and builds and is short of columns, which is the failure this
    tool exists to make visible rather than to produce.
    """
    with pytest.raises(SourceError, match=re.escape(message)):
        load_live_json(payload)


def test_a_file_that_cannot_be_read_as_text_is_refused(tmp_path: Path) -> None:
    missing = tmp_path / "nothing.json"
    with pytest.raises(SourceError, match=re.escape("nothing.json")):
        load_source(missing)

    binary = tmp_path / "download.json"
    binary.write_bytes(b"\xff\xfe\x00{")
    with pytest.raises(SourceError, match="not UTF-8 text"):
        load_source(binary)


def test_a_file_that_is_not_the_download_names_the_command_that_makes_one(
    tmp_path: Path,
) -> None:
    """The CSV export was read here once. An operator who still has one, or
    who feeds this the wrong file, gets pointed at `extract-script` rather
    than at a JSON parser's error."""
    path = tmp_path / "RG_Project.csv"
    path.write_text("Title,Category\nx,y\n", newline="\n")
    with pytest.raises(SourceError, match="extract-script"):
        load_source(path)


def test_the_download_is_read_whatever_it_was_renamed_to(tmp_path: Path) -> None:
    """An operator who renames a download should still get their schema."""
    path = tmp_path / "download.txt"
    path.write_text(json.dumps(_live_payload()), newline="\n")
    assert load_source(path).kind == LIVE_KIND
    assert load_source(path).lists[0].title == LIST_TITLE


# --- The browser-paste script ----------------------------------------------


def _extract_js(titles: list[str] | None = None) -> str:
    return generate_extract_js(
        site_url="https://example.sharepoint.com/sites/risk",
        list_titles=titles or ["RR_Risk"],
        generated_at=GENERATED_AT,
    )


def test_the_extract_script_is_read_only() -> None:
    """It carries no write helpers at all, which is stronger than not using
    them: `_http_write.js.j2` is simply not included."""
    js = _extract_js()
    assert "method: 'POST'" not in js
    assert "X-HTTP-Method" not in js
    assert "X-RequestDigest" not in js
    assert "contextinfo" not in js
    assert "postJson" not in js


def test_the_extract_script_reads_only_proven_endpoints() -> None:
    """Every REST shape here is one this repository already exercises: the
    fields and content-type reads come from
    `test/manual/form-visibility-storage-probe.js`, the view select from
    `templates/deploy/_views.js.j2`, and the paged list enumeration from
    `rollback.js.j2`."""
    js = _extract_js()
    assert "/fields?$select=InternalName,SchemaXml" in js
    assert "contenttypes?$select=Name,StringId,ClientFormCustomFormatter" in js
    assert "views?$select=Id,Title,DefaultView,Hidden,PersonalView" in js
    assert "web/lists?$select=Title,Hidden" in js
    assert "$expand=ViewFields" in js


def test_the_extract_script_pages_rather_than_capping() -> None:
    """A `$top` cap on a wider list loses the tail, and a schema four columns
    short is exactly what this tool exists to make visible."""
    js = _extract_js()
    assert "__next" in js
    assert "$top" not in js.split("/fields?$select=")[1].split("\n")[0]


def test_the_extract_script_declares_the_format_the_reader_expects() -> None:
    """The one fact the JS writer and the Python reader share."""
    assert f'const FORMAT = "{LIVE_FORMAT}"' in _extract_js()


def test_the_extract_script_carries_the_site_guard() -> None:
    js = _extract_js()
    assert "_spPageContextInfo" in js
    assert "site-mismatch" in js
    assert "[SP-EXTRACT]" in js


def test_a_failed_list_read_downloads_nothing() -> None:
    """A partial extraction produces a schema that parses, builds, and is
    missing a list. Nothing downstream can tell that from a site with one
    list fewer, so the script aborts instead."""
    js = _extract_js()
    assert "'list-read-failed'" in js
    assert "Nothing was downloaded" in js


def test_the_script_refuses_to_read_nothing() -> None:
    with pytest.raises(NoListsError, match="no lists were named"):
        generate_extract_js(
            site_url="https://example.sharepoint.com/sites/x",
            list_titles=[], generated_at=GENERATED_AT,
        )


@pytest.mark.parametrize(("titles", "expected"), [
    (["RR_Risk"], "RR_Risk-extract.json"),
    (["Risk register"], "Risk-register-extract.json"),
    (["../etc/passwd"], "etc-passwd-extract.json"),
    (["..."], DEFAULT_DOWNLOAD_NAME),
    (["A", "B"], DEFAULT_DOWNLOAD_NAME),
])
def test_the_download_name_holds_no_path_separator(
    titles: list[str], expected: str,
) -> None:
    """This string reaches the DOM as an anchor's `download` attribute."""
    assert download_name(titles) == expected


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_extract_script_parses_under_node() -> None:
    """Only a parse proves it is JavaScript. It is not RUN here: every
    statement in it is a fetch against a live SharePoint site."""
    assert NODE is not None
    proc = subprocess.run(  # noqa: S603
        [NODE, "--check", "--input-type=commonjs"],
        input=_extract_js([LIST_TITLE]),
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- The command surface ---------------------------------------------------


def _run(*args: str) -> Result:
    return runner.invoke(app, list(args))


def test_extract_writes_the_whole_project(tmp_path: Path) -> None:
    """The acceptance path from the brief, run end to end."""
    out = tmp_path / "project"
    result = _run("extract", str(SAMPLE), "--out", str(out), "--entity", ENTITY)
    assert result.exit_code == 0, result.output
    assert "32 column(s)" in result.output
    assert "8 enum(s)" in result.output
    assert LIVE_KIND in result.output
    assert "EXTRACTION-NOTES.md" in result.output
    for relpath in (
        Path("10-design") / "schema.dbml",
        Path("20-configure") / "mapping.yaml",
        Path("20-configure") / "release.yaml",
        NOTES_RELPATH,
    ):
        assert (out / relpath).is_file(), relpath
    for column in ("AmendmentCount", "EthicsPathway"):
        preserved = out / "20-configure" / "formatting" / f"{ENTITY}.{column}.json"
        assert preserved.is_file(), preserved


def test_extract_writes_into_the_folder_named_for_the_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no `--out`, the project lands in a directory named after the
    LIST, not after the download, and the summary line says which one. The
    name comes out of the payload, so a download an operator renamed still
    lands where `extract-script` put the script."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "downloads" / "renamed.json"
    source.parent.mkdir()
    source.write_text(SAMPLE.read_text(encoding="utf-8"), newline="\n")

    result = _run("extract", str(source))
    assert result.exit_code == 0, result.output
    root = tmp_path / LIST_TITLE
    assert (root / NOTES_RELPATH).is_file()
    assert LIST_TITLE in result.output
    # Nothing was written back into the directory the download came out of.
    assert list(source.parent.iterdir()) == [source]


def test_extract_joins_the_folder_the_download_is_already_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal case: `extract-script` made the folder and the readme said
    to save the download into it. Extracting from inside that folder must
    not nest a second one of the same name."""
    folder = tmp_path / LIST_TITLE
    folder.mkdir()
    source = folder / download_name([LIST_TITLE])
    source.write_text(SAMPLE.read_text(encoding="utf-8"), newline="\n")
    monkeypatch.chdir(folder)

    assert _run("extract", source.name).exit_code == 0
    assert (folder / NOTES_RELPATH).is_file()
    assert not (folder / LIST_TITLE).exists()


def test_extract_out_overrides_the_lists_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "somewhere-else"
    assert _run("extract", str(SAMPLE), "--out", str(out)).exit_code == 0
    assert (out / NOTES_RELPATH).is_file()
    assert not (tmp_path / LIST_TITLE).exists()


def test_extract_refuses_to_overwrite_a_project(tmp_path: Path) -> None:
    """One folder per list, so a second run of the same extraction lands on
    the first one's output. It is refused by name, not by a prompt, so the
    command behaves the same in a pipe."""
    out = tmp_path / "project"
    assert _run("extract", str(SAMPLE), "--out", str(out)).exit_code == 0
    again = _run("extract", str(SAMPLE), "--out", str(out))
    assert again.exit_code == 1
    assert "refusing to overwrite" in again.output
    assert "schema.dbml" in again.output
    forced = _run("extract", str(SAMPLE), "--out", str(out), "--force")
    assert forced.exit_code == 0, forced.output


def test_extract_refuses_a_source_it_cannot_read(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("nothing here\n", newline="\n")
    result = _run("extract", str(path), "--out", str(tmp_path / "p"))
    assert result.exit_code != 0
    assert "extract-script" in result.output


def test_extract_refuses_an_entity_name_for_several_lists(tmp_path: Path) -> None:
    """One flag cannot name two tables, and picking one of them silently is
    how a second list ends up merged into the first."""
    payload = _live_payload()
    payload["lists"].append({**payload["lists"][0], "title": "RG_Amendment"})
    path = tmp_path / "download.json"
    path.write_text(json.dumps(payload), newline="\n")
    result = _run(
        "extract", str(path), "--out", str(tmp_path / "p"), "--entity", ENTITY,
    )
    assert result.exit_code != 0
    assert "describes 2 lists" in result.output


def test_extract_refuses_a_name_that_is_not_an_identifier(tmp_path: Path) -> None:
    result = _run(
        "extract", str(SAMPLE), "--out", str(tmp_path / "p"),
        "--entity", "risk-register",
    )
    assert result.exit_code != 0
    assert "must be a DBML identifier" in result.output


def test_extract_script_writes_a_pasteable_file(tmp_path: Path) -> None:
    """One URL in, one script out. The title and the site are both split
    out of the string the browser address bar already holds."""
    out = tmp_path / EXTRACT_SCRIPT
    result = _run("extract-script", LIST_URL, "--out", str(out))
    assert result.exit_code == 0, result.output
    assert "makes no changes" in result.output
    assert f"'{LIST_TITLE}'" in result.output
    assert SITE_URL in result.output
    text = out.read_text(encoding="utf-8")
    assert "\r" not in text
    assert LIST_TITLE in text


def test_extract_script_makes_the_lists_own_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no `--out` the script goes into a folder named after the list,
    beside a readme, and the two are what `extract` then writes into."""
    monkeypatch.chdir(tmp_path)
    result = _run("extract-script", LIST_URL)
    assert result.exit_code == 0, result.output
    folder = tmp_path / LIST_TITLE
    assert (folder / EXTRACT_SCRIPT).is_file()
    assert (folder / README_FILENAME).is_file()
    # The download's name and the command that reads it back are both in the
    # output, because the flow stops here until a human does the browser
    # half of it.
    assert download_name([LIST_TITLE]) in result.output
    assert "dbml-sharepoint extract" in result.output
    assert README_FILENAME in result.output


def test_extract_script_leaves_a_readme_that_is_already_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--out` can aim at a directory somebody else owns, and `readme.md`
    is `README.md` on Windows. The script is still written; the readme is
    not, and the output says so."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / README_FILENAME).write_text("mine\n", newline="\n")
    result = _run("extract-script", LIST_URL, "--out", EXTRACT_SCRIPT)
    assert result.exit_code == 0, result.output
    assert (tmp_path / EXTRACT_SCRIPT).is_file()
    assert (tmp_path / README_FILENAME).read_text(encoding="utf-8") == "mine\n"
    assert "alone" in result.output


def test_extract_script_refuses_a_url_that_names_no_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A site URL is what an operator reaches for first, and it says nothing
    about which list to read."""
    monkeypatch.chdir(tmp_path)
    result = _run("extract-script", SITE_URL)
    assert result.exit_code != 0
    assert "/Lists/" in result.output
    assert list(tmp_path.iterdir()) == []


def test_extract_script_refuses_a_url_that_is_not_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script is pasted into whatever site is open, so the URL it guards
    on has to be a real one."""
    monkeypatch.chdir(tmp_path)
    result = _run("extract-script", "not a url")
    assert result.exit_code != 0
    assert list(tmp_path.iterdir()) == []


# --- The wizard -------------------------------------------------------------
#
# Driven through `_console.ScriptedConsole`, the same way `test_wizard.py`
# drives the `new` wizard: rich's `Prompt` and `Confirm` both read through
# `console.input`, so scripting that keeps the real prompt objects under
# test. Every one of these runs in `tmp_path`, because the wizard writes
# into the current directory by design.


def _downloaded(folder: Path, name: str | None = None) -> Path:
    """The fixture, saved where the wizard will look for it.

    Written before the run rather than during it: the answers are scripted
    up front, so there is no point between the confirmation and the search
    at which a test could put the file there.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name or download_name([LIST_TITLE]))
    path.write_text(SAMPLE.read_text(encoding="utf-8"), newline="\n")
    return path


def test_the_wizard_goes_from_a_url_to_a_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole flow, with the browser half already done. One URL and one
    yes, and the script, the readme and the draft are all in one folder."""
    monkeypatch.chdir(tmp_path)
    _downloaded(tmp_path / LIST_TITLE)

    console = ScriptedConsole([LIST_URL, "y"])
    assert run_extract_wizard(console) == 0
    folder = tmp_path / LIST_TITLE
    for relpath in (
        Path(EXTRACT_SCRIPT), Path(README_FILENAME), NOTES_RELPATH,
        Path("10-design") / "schema.dbml",
        Path("20-configure") / "mapping.yaml",
    ):
        assert (folder / relpath).is_file(), relpath


def test_the_wizard_re_asks_a_url_that_names_no_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same two gates the flags use, and neither one ends the run: a
    site URL is the thing an operator reaches for first."""
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole([SITE_URL, "not a url", LIST_URL, "n"])
    assert run_extract_wizard(console) == 0
    shown = collapsed(console)
    assert "/Lists/" in shown
    assert (tmp_path / LIST_TITLE / EXTRACT_SCRIPT).is_file()


def test_the_wizard_stops_when_the_download_is_not_saved_yet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answering no is not a failure. The browser half can take a while, and
    the run leaves behind the command that finishes it."""
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole([LIST_URL, "n"])
    assert run_extract_wizard(console) == 0
    shown = collapsed(console)
    assert "Nothing extracted" in shown
    assert "dbml-sharepoint extract" in shown
    assert not (tmp_path / LIST_TITLE / NOTES_RELPATH).exists()


def test_the_wizard_asks_once_for_a_download_that_is_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A browser that saved into its own download directory is the ordinary
    way this goes wrong. The draft still lands in the list's folder, because
    that is what the folder is named after."""
    monkeypatch.chdir(tmp_path)
    elsewhere = _downloaded(tmp_path / "Downloads", "renamed.json")

    console = ScriptedConsole([LIST_URL, "y", str(elsewhere)])
    assert run_extract_wizard(console) == 0
    assert (tmp_path / LIST_TITLE / NOTES_RELPATH).is_file()
    # Nothing was written back beside the download it read.
    assert list(elsewhere.parent.iterdir()) == [elsewhere]


def test_the_wizard_stops_after_one_wrong_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once, not in a loop. A second wrong answer means something other
    than a typo, and the message says how to finish by hand."""
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole([LIST_URL, "y", str(tmp_path / "nowhere.json")])
    assert run_extract_wizard(console) == 1
    assert "Nothing at" in collapsed(console)


def test_the_wizard_passes_the_flags_it_was_given_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`extract --entity X` with no download is the same run with one
    question already answered, so the flags cannot mean one thing here and
    another on the command line."""
    monkeypatch.chdir(tmp_path)
    _downloaded(tmp_path / LIST_TITLE)

    console = ScriptedConsole([LIST_URL, "y"])
    assert run_extract_wizard(console, entity=ENTITY, prefix="ACME_") == 0
    schema = (tmp_path / LIST_TITLE / "10-design" / "schema.dbml").read_text(
        encoding="utf-8",
    )
    assert f"Table {ENTITY}" in schema
    mapping = (tmp_path / LIST_TITLE / "20-configure" / "mapping.yaml").read_text(
        encoding="utf-8",
    )
    assert "prefix: ACME_" in mapping


def test_the_wizard_passes_an_extraction_refusal_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusals are the documented contract of `extract`, and flattening
    them to 1 here would make the wizard a second implementation of it."""
    monkeypatch.chdir(tmp_path)
    _downloaded(tmp_path / LIST_TITLE)
    assert run_extract_wizard(ScriptedConsole([LIST_URL, "y"])) == 0

    again = ScriptedConsole([LIST_URL, "y"])
    assert run_extract_wizard(again) == 1


def test_the_wizard_passes_a_usage_error_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A usage error leaves as `typer.BadParameter`, not as `typer.Exit`, so
    it takes the other clause and gets 2, the code the flags give it.

    Reached with a hand-assembled download describing two lists, which is
    what the second prompt can be pointed at."""
    monkeypatch.chdir(tmp_path)
    payload = _live_payload()
    payload["lists"].append({**payload["lists"][0], "title": "RG_Amendment"})
    folder = tmp_path / LIST_TITLE
    folder.mkdir()
    (folder / download_name([LIST_TITLE])).write_text(
        json.dumps(payload), newline="\n",
    )

    console = ScriptedConsole([LIST_URL, "y"])
    assert run_extract_wizard(console, entity=ENTITY) == 2
    assert "describes 2 lists" in collapsed(console)


def test_the_wizard_leaves_quietly_when_input_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ctrl-D at the first prompt. 130 is the shell's code for a signalled
    exit, and it is not a traceback."""
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole([])
    assert run_extract_wizard(console) == 130
    assert "Input ended" in collapsed(console)


def test_the_wizard_leaves_quietly_on_ctrl_c(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other normal way to leave a wizard, and the other 130."""
    monkeypatch.chdir(tmp_path)

    class Interrupted(ScriptedConsole):
        def input(self, prompt: object = "", **kwargs: object) -> str:
            raise KeyboardInterrupt

    console = Interrupted([])
    assert run_extract_wizard(console) == 130
    assert "Cancelled" in collapsed(console)


def test_the_wizard_reports_a_folder_it_cannot_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file already sitting where the folder has to go. Named rather than
    raised, because a traceback out of a wizard says nothing about which of
    the questions went wrong."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / LIST_TITLE).write_text("not a directory\n", newline="\n")
    console = ScriptedConsole([LIST_URL])
    assert run_extract_wizard(console) == 1
    assert "Could not write the script" in collapsed(console)


def test_extract_with_no_download_and_no_terminal_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CliRunner's stdin is a pipe, which is what CI and a Dockerfile are.
    A wizard would block on a prompt nobody can answer."""
    monkeypatch.chdir(tmp_path)
    result = _run("extract")
    assert result.exit_code == 2
    assert "no terminal" in result.output
    assert list(tmp_path.iterdir()) == []


def test_extract_refuses_out_with_no_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--out` names where a download is extracted to, and the interactive
    flow always writes into the list's own folder. Silently ignoring the
    flag is how an operator loses a run."""
    monkeypatch.chdir(tmp_path)
    result = _run("extract", "--out", str(tmp_path / "p"))
    assert result.exit_code == 2
    # rich highlights the `--out` token when colour is enabled (CI does),
    # splicing ANSI escapes into the middle of the message. Assert on the
    # message, not the decoration.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--out has no download" in plain


def test_a_stored_rule_the_build_now_refuses_reports_the_renderers_reason() -> None:
    """A list deployed before 2026-09-02 may carry `[W]<=TODAY()` on a
    datetime column. It inverts to `leq today`, which the build now refuses,
    and the report has to say why rather than call a single comparison
    "not a single comparison"."""
    from dbml_sharepoint.extract.inverse import Unrenderable, invert_column_validation

    result = invert_column_validation(
        "=[OccurredAt]<=TODAY()", "Not in the future.", {"OccurredAt": "datetime"}, "ctx",
    )
    assert isinstance(result, Unrenderable)
    assert "now" in result.reason
