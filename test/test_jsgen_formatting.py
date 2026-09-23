# test/test_jsgen_formatting.py
"""The surfaces that only affect what a person sees, and the rules that refuse a save.

Display titles and the formula rewriting they force, column and view
formatters, form layout, and column and list validation. This is the failure
class AGENTS.md opens with: all of it saves, reads back byte-identical and
passes every deploy phase whether or not it does anything on the page.
"""

import json as jsonlib
from pathlib import Path

from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack, write_dbml, write_mapping
from _paths import FIXTURES
from test_jsgen import _generate_views_js

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import UNMANAGED, build_schema_json, generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release

# --- Display names ----------------------------------------------------------


def _display_names_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    # The mapping block sits at an eight-space margin, not the usual twelve:
    # the RiskScore formula is ONE YAML line (splitting it would change the
    # value) and four more columns of indent would push it past E501.
    return pack(
        tmp_path,
        dbml=blocks(
            """
            Enum matrix_version {
              "13.0"
            }
            """,
            table(
                "Risk", ID_PK, TITLE,
                "MatrixVersion matrix_version",
                "RiskManReference nvarchar",
                "RiskScore calculated_number",
            ),
        ),
        mapping=blocks(entities("Risk"), """
        display_names:
          mode: auto
          overrides:
            Risk:
              RiskManReference: "RiskMan Reference"
        calculated_formulas:
          Risk:
            RiskScore: '=IF([MatrixVersion]="13.0",1,IF([RiskManReference]="[MatrixVersion]",2,3))'
        """),
    )


def test_fields_carry_display_titles_and_create_with_internal_name(
    tmp_path: Path,
) -> None:
    """Rename-after-create: the field CREATE body keeps Title = internal name
    (locking a clean InternalName), while display_title carries the desired
    human-readable Title that reconciliation MERGEs afterwards. Overrides win
    over the auto split; with the feature off display_title == title."""
    schema, bundle = _display_names_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"]
        if lst["title"] == "APP_Risk"
    )
    by_title = {f["title"]: f for f in risk["fields_phase1"]}
    assert by_title["MatrixVersion"]["display_title"] == "Matrix Version"
    assert by_title["RiskManReference"]["display_title"] == "RiskMan Reference"
    assert by_title["RiskScore"]["display_title"] == "Risk Score"
    # CREATE bodies keep the internal name so InternalName stays clean.
    assert by_title["MatrixVersion"]["body"]["Title"] == "MatrixVersion"

    off = parse_dbml(FIXTURES / "calculated.dbml")
    off_bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    off_risk = next(
        lst for lst in build_schema_json(
            off, off_bundle, "default", resolved=resolve(off, off_bundle.mapping),
        )["lists"]
    )
    assert all(f["display_title"] == f["title"] for f in off_risk["fields_phase1"])


def test_formula_references_rewritten_to_display_names(tmp_path: Path) -> None:
    """SharePoint resolves formula [refs] against DISPLAY names at write
    time, so once MatrixVersion displays as "Matrix Version" a formula
    saying [MatrixVersion] fails to create. Authors keep internal names;
    the build rewrites refs to display names, outside string literals only
    (bracket text inside a quoted constant is data)."""
    schema, bundle = _display_names_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"]
        if lst["title"] == "APP_Risk"
    )
    formula = next(
        f["body"]["Formula"] for f in risk["fields_phase1"] if f["title"] == "RiskScore"
    )
    assert "[Matrix Version]" in formula
    assert "[RiskMan Reference]" in formula
    # The string literal "[MatrixVersion]" is data and stays verbatim.
    assert '"[MatrixVersion]"' in formula


def test_template_reconciles_title_to_display_title(tmp_path: Path) -> None:
    """The desired display Title is field.display_title (rename-after-create);
    field.title remains the immutable-InternalName expectation everywhere
    else, so probes and identity checks stay keyed on internal names."""
    js = _generate_views_js(tmp_path)
    # Synthetic reconcile callers (the built-in Title patch) carry no
    # display_title; comparing against undefined made every Title patch
    # "drift" forever (seen live). Desired title falls back to the internal.
    assert (
        "const desiredTitle = field.display_title != null ? field.display_title : field.title"
        in js
    )
    assert "actual.Title !== desiredTitle" in js
    assert "patchBody.Title = desiredTitle" in js
    assert "drift('Title', desiredTitle, actual.Title)" in js
    assert "actual.Title !== field.title" not in js
    # Immutable identity stays internal.
    assert "actual.InternalName !== field.title" in js


# --- Column formatting ------------------------------------------------------


def _formatting_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    return pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "Status status"),
        ),
        mapping=blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Status: { elmType: div, txtContent: '@currentField' }
        """),
    )


def test_fields_carry_compact_custom_formatter(tmp_path: Path) -> None:
    schema, bundle = _formatting_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"]
        if lst["title"] == "APP_Risk"
    )
    by_title = {f["title"]: f for f in risk["fields_phase1"]}
    assert by_title["Status"]["custom_formatter"] == (
        '{"elmType":"div","txtContent":"@currentField"}'
    )
    assert by_title["Status"]["body"].get("CustomFormatter") is None
    # Undeclared columns carry an explicit null so the template never
    # touches a hand-applied format.
    assert by_title["Detail" if "Detail" in by_title else "Status"] is not None
    for f in risk["fields_phase1"]:
        if f["title"] != "Status":
            assert f["custom_formatter"] is None


def test_template_reconciles_custom_formatter(tmp_path: Path) -> None:
    """CustomFormatter rides the field reconcile: probed in the base
    $select, compared canonically (key order/whitespace-proof), narrowly
    MERGEd, drift-reported. Declared-null fields are never compared."""
    schema, bundle = _formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert "const canonicalJson = " in js
    assert "'ReadOnlyField', 'Sealed', 'DefaultValue', 'DefaultFormula', 'CustomFormatter'" in js
    assert "field.custom_formatter != null" in js
    assert (
        "canonicalJson(actual.CustomFormatter) !== canonicalJson(field.custom_formatter)"
        in js
    )
    assert "patchBody.CustomFormatter = field.custom_formatter" in js
    assert "drift('CustomFormatter', field.custom_formatter, actual.CustomFormatter)" in js


def test_view_rows_carry_formatting_and_template_reconciles_it(tmp_path: Path) -> None:
    """Row formatting is a declared view setting: SCHEMA carries the compact
    JSON; Phase 3.1 compares canonically, MERGEs CustomFormatter, verifies by
    readback; views without a declaration are never touched."""
    write_dbml(tmp_path, table("Risk", ID_PK, TITLE, "Score int"))
    # `formatting` is spelled block-style, unlike the flow mappings the rest of
    # the suite declares. As a flow mapping it is ONE logical line -- splitting
    # it would change the declared formatter -- and that line is 101 characters
    # flush against the left margin, so no triple-quoted block can hold it
    # within E501. Block style parses to the identical mapping, and the exact
    # rendered JSON is pinned by the assertion below.
    write_mapping(tmp_path, blocks(entities("Risk"), """
        views:
          Risk:
            - title: Hot
              fields: [Title, Score]
              formatting:
                additionalRowClass: "=if([$Score] >= 20, 'sp-css-backgroundColor-BgCoral', '')"
    """))
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    row = next(
        view for view in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["views"]
        if view["title"] == "Hot"
    )
    assert row["formatting"] == (
        '{"additionalRowClass":"=if([$Score] >= 20, \'sp-css-backgroundColor-BgCoral\', \'\')"}'
    )
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert (
        "$select=Id,Title,DefaultView,Hidden,RowLimit,ViewQuery,PersonalView,CustomFormatter"
        in js
    )
    assert "view.formatting != null" in js
    assert "CustomFormatter: view.formatting" in js
    # The view CustomFormatter lives in the view schema XML like ViewQuery,
    # so readback is XML-entity-encoded ('>=' returns as '&gt;=', seen
    # live): compare via xmlDecode before canonical JSON, both sides.
    assert "const canonicalViewFormatter" in js
    assert (
        "canonicalViewFormatter(actual.CustomFormatter) !== canonicalViewFormatter(view.formatting)"
        in js
    )
    # Scoped to Phase 3.1: the FIELD-level comparison stays plain
    # canonicalJson (field CustomFormatter storage is not XML-encoded).
    phase3c = js.split(f"Starting Phase {pn('views')}")[1].split(f"Starting Phase {pn('forms')}")[0]
    assert "canonicalJson(actual.CustomFormatter)" not in phase3c


# --- Form formatting --------------------------------------------------------


def _form_formatting_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    return pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, "ReviewDate date"),
        mapping=blocks(entities("Risk"), """
            display_names:
              mode: auto
            form_formatting:
              Risk:
                body: { sections: [ { displayname: Core, fields: [Title, ReviewDate] } ] }
        """),
    )


def test_required_date_default_and_validation_reach_the_field(tmp_path: Path) -> None:
    """A required cadence baseline can be hidden on New only if its dynamic
    default and save rule survive together. The generated field must reject
    clearing, start at today, and refuse a future date."""
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Risk", ID_PK, TITLE,
            "LastReviewedDate date [not null, default: '[today]']",
        ),
        mapping=blocks(entities("Risk"), """
            column_validation:
              Risk:
                columns:
                  LastReviewedDate:
                    when:
                      - { field: LastReviewedDate, op: leq, value: today }
                    message: Review date cannot be in the future.
        """),
    )
    out = build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
    defaults = {
        (d["list"], d["field"]): d["default_value"] for d in out["field_defaults"]
    }
    assert defaults[("APP_Risk", "LastReviewedDate")] == "[today]"
    field = next(
        f for f in out["lists"][0]["fields_phase1"]
        if f["title"] == "LastReviewedDate"
    )
    assert field["body"]["Required"] is True
    assert field["body"]["DefaultValue"] == "[today]"
    # MEASURED 2026-09-02: a column rule against the clock cannot be exact
    # on its column (TODAY() lags the site, and a column formula may not
    # reference [Modified]), so it moves to the list rule, guarded for a
    # blank, and the column's own rule is CLEARED so the lagging one
    # cannot survive a redeploy beside it. See analysis/save_rules.py.
    assert field["validation_formula"] == ""
    assert field["validation_message"] == ""
    assert out["lists"][0]["validation_formula"] == (
        "=OR(ISBLANK([LastReviewedDate]),[LastReviewedDate]<=[Modified])"
    )
    assert out["lists"][0]["validation_message"] == "Review date cannot be in the future."
    assert out["lists"][0]["validation_hoisted"] == ["LastReviewedDate"]


def test_a_hoisted_date_rule_joins_the_declared_list_rule(tmp_path: Path) -> None:
    """One list, one formula, one message: the declared list rule comes
    first, each hoisted rule follows under its blank guard, and the messages
    are joined in the same order."""
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Action", ID_PK, TITLE,
            "Status nvarchar",
            "CompletedDate date",
            "OccurredAt datetime",
        ),
        mapping=blocks(entities("Action"), """
            list_validation:
              Action:
                when:
                  - any_of:
                      - { field: Status, op: neq, value: Done }
                      - { field: CompletedDate, op: is_not_null }
                message: An action marked Done needs a completed date.
            column_validation:
              Action:
                columns:
                  CompletedDate:
                    when:
                      - { field: CompletedDate, op: leq, value: today }
                    message: An action cannot have been completed in the future.
                  OccurredAt:
                    when:
                      - { field: OccurredAt, op: leq, value: now }
                    message: Not after now.
        """),
    )
    out = build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
    lst = out["lists"][0]
    assert lst["validation_formula"] == (
        '=AND(OR([Status]<>"Done",NOT(ISBLANK([CompletedDate]))),'
        "OR(ISBLANK([CompletedDate]),[CompletedDate]<=[Modified]),"
        "OR(ISBLANK([OccurredAt]),[OccurredAt]<=[Modified]))"
    )
    assert lst["validation_message"] == (
        "An action marked Done needs a completed date. "
        "An action cannot have been completed in the future. Not after now."
    )
    assert lst["validation_hoisted"] == ["CompletedDate", "OccurredAt"]
    fields = {f["title"]: f for f in lst["fields_phase1"]}
    assert fields["CompletedDate"]["validation_formula"] == ""
    assert fields["OccurredAt"]["validation_formula"] == ""


def test_exact_column_validation_skips_unsupported_field_types(tmp_path: Path) -> None:
    """Exact reconciliation clears stale rules only where SharePoint exposes
    ValidationFormula. Writing even an empty formula to Note, Person or
    Lookup fields fails the whole field MERGE with HTTP 500."""
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Risk", ID_PK, TITLE,
            "Summary nvarchar",
            "ReviewDate date",
            "Detail richtext",
            "Notes longtext",
            "Owner person",
            "Parent int [ref: > Risk.Id]",
        ),
        mapping=blocks(entities("Risk"), """
            column_validation:
              Risk:
                reconcile: exact
                columns:
                  Summary:
                    when:
                      - { field: Summary, op: neq, value: forbidden }
                    message: Use a different summary.
        """),
    )
    out = build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
    fields = {
        field["title"]: field
        for field in out["lists"][0]["fields_phase1"]
    }
    fields.update({
        lookup["field"]["title"]: lookup["field"]
        for lookup in out["phase2_lookups"]
    })

    assert fields["Summary"]["validation_formula"] == '=[Summary]<>"forbidden"'
    assert fields["ReviewDate"]["validation_formula"] == ""
    for name in ("Detail", "Notes", "Owner", "Parent"):
        assert fields[name]["validation_formula"] == UNMANAGED, name
        assert fields[name]["validation_message"] == UNMANAGED, name


def test_exact_column_validation_skips_a_multi_value_column(tmp_path: Path) -> None:
    """MEASURED 2026-08-10, and it is the same platform limitation the other
    five kinds in this set were confirmed with: setting a ValidationFormula
    on a MultiChoice field was refused with "This field type does not support
    validation formulas."

    So exact reconciliation must not try to CLEAR one either -- a formula the
    field type cannot carry is already absent, and the request only fails the
    field MERGE. `UNMANAGED`, not `""`.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=blocks("""
            enum audit_event {
              View
              Edit
            }
        """, table("Platform", ID_PK, TITLE, "Summary nvarchar", "Events audit_event[]")),
        mapping=blocks(entities("Platform"), """
            column_validation:
              Platform:
                reconcile: exact
                columns:
                  Summary:
                    when:
                      - { field: Summary, op: neq, value: forbidden }
                    message: Use a different summary.
        """),
    )
    fields = {
        field["title"]: field
        for field in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"][0][
            "fields_phase1"
        ]
    }

    assert fields["Events"]["validation_formula"] == UNMANAGED
    assert fields["Events"]["validation_message"] == UNMANAGED
    # The control: a column that CAN hold one is still cleared, so this test
    # cannot pass by the section being ignored wholesale.
    assert fields["Summary"]["validation_formula"] == '=[Summary]<>"forbidden"'


def test_form_formatting_composed_with_display_rewrite(tmp_path: Path) -> None:
    """ClientFormCustomFormatter is a JSON string whose *JSONFormatter keys
    hold part JSON OBJECTS, the pane-native encoding (the Format pane
    displays string-encoded parts escaped; objects display clean, and the
    renderer accepts both). Body section field lists are the one place SP
    matches by DISPLAY name, so they are rewritten through the display
    map; only declared parts appear."""
    schema, bundle = _form_formatting_inputs(tmp_path)
    rows = build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )["form_formatting"]
    assert [row["list"] for row in rows] == ["APP_Risk"]
    outer = jsonlib.loads(rows[0]["client_form_custom_formatter"])
    assert set(outer) == {"bodyJSONFormatter"}
    body = outer["bodyJSONFormatter"]
    assert isinstance(body, dict)                       # object, not string
    assert body["sections"][0]["fields"] == ["Title", "Review Date"]


def test_template_phase_3d_compare_is_encoding_agnostic(tmp_path: Path) -> None:
    """Sites deployed before the pane-native encoding carry string-encoded
    parts; canonicalFormFormatter must parse string parts before
    canonicalising so semantically-equal layouts compare equal in either
    encoding (no churn, no false readback failures)."""
    schema, bundle = _form_formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    idx = js.index("const canonicalFormFormatter")
    block = js[idx:idx + 800]
    assert "typeof part === 'string'" in block
    assert "JSON.parse(part)" in block


def test_template_phase_3d_reconciles_form_formatting(tmp_path: Path) -> None:
    schema, bundle = _form_formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert f"Starting Phase {pn('forms')}: form formatting" in js
    assert "for (const form of SCHEMA.form_formatting)" in js
    assert "contenttypes?$select=Name,StringId,ClientFormCustomFormatter" in js
    assert "ct.StringId.startsWith('0x01') && !ct.StringId.startsWith('0x0120')" in js
    assert "no default item content type found" in js
    assert "'SP.ContentType'" in js
    assert "canonicalFormFormatter" in js
    assert "did not retain declared form formatting" in js
    assert "phase: '3.2'" in js
    assert js.index(f"Starting Phase {pn('views')}") < js.index(
        f"Starting Phase {pn('forms')}") < js.index(
        f"Starting Phase {pn('acls')}",
    )


def test_list_validation_flows_to_schema_and_template(tmp_path: Path) -> None:
    """ValidationFormula/Message ride the declared list settings: rewritten
    to display names, probed in readListShape, compared via canonicalFormula
    and reconciled by the existing narrow list MERGE."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "ClosureNote nvarchar", "Status status"),
        ),
        mapping=blocks(entities("Risk"), """
            display_names:
              mode: auto
            list_validation:
              Risk:
                when:
                  any_of:
                    - none_of:
                        - { field: Status, op: eq, value: Closed }
                    - { field: ClosureNote, op: is_not_null }
                message: Closing needs a closure note.
        """),
    )
    risk = next(
        lst for lst in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"]
        if lst["title"] == "APP_Risk"
    )
    # The implication "if closed then a closure note" as the grammar spells
    # it (any_of[none_of[antecedent], consequent]). The neq renderer itself
    # admits blanks, and internal names are rewritten to display names,
    # which is what SP resolves against.
    assert risk["validation_formula"] == (
        '=OR([Status]<>"Closed",NOT(ISBLANK([Closure Note])))'
    )
    assert risk["validation_message"] == "Closing needs a closure note."

    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert (
        "'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit', "
        "'ValidationFormula', 'ValidationMessage'"
    ) in js
    # Validation reconciles AFTER the list's fields exist: the formula
    # references columns (by display name) that the same run creates and
    # renames. Merging it with the pre-field list settings fails with
    # "The formula refers to a column that does not exist" (seen live).
    assert "async function reconcileListValidation" in js
    assert "list.validation_formula == null" in js
    assert "did not retain declared validation" in js
    assert "desired.ValidationFormula" not in js
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]
    # The wave creates columns in four steps now, and the merge follows all of
    # them: the decide pass queues, the ChangeSet goes out, the verify pass
    # reads each column back, and the calculated tail is written singly.
    assert phase1.index("for (const col of batchedFields)") < phase1.index(
        "await createBatch.done()",
    ) < phase1.index("for (const { col, created } of verifyWork)") < phase1.index(
        "for (const col of calculatedFields)",
    ) < phase1.index("await reconcileListValidation(list")


def test_a_url_column_is_never_sent_a_validation_formula(tmp_path: Path) -> None:
    """SharePoint refuses ValidationFormula on a URL field even when the
    value is the empty string: HTTP 500, "This field type does not support
    validation formulas." Observed on a live tenant, aborting a paste at
    the field-reconcile phase.

    Under `column_validation: reconcile: exact` the deployer clears the
    formula on every column NOT declared, so one undeclared hyperlink
    column stops a deploy that has nothing else wrong with it. The
    generator must mark those columns unmanaged rather than emit a clear.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Thing", ID_PK, TITLE,
            "Link hyperlink",
            "Note nvarchar",
            "Comment nvarchar",
        ),
        mapping=blocks(entities("Thing"), """
            column_validation:
              Thing:
                reconcile: exact
                columns:
                  Note:
                    when:
                      - { field: Note, op: is_not_null }
                    message: "Needed."
        """),
    )
    schema_json = build_schema_json(
        schema=schema, bundle=bundle, site_role="default", resolved=resolve(schema, bundle.mapping),
    )
    fields = {
        f["title"]: f
        for lst in schema_json["lists"]
        for f in lst["fields_phase1"]
    }
    assert fields["Link"]["validation_formula"] == UNMANAGED, (
        "a hyperlink column must be left unmanaged, not sent an empty "
        "ValidationFormula that SharePoint refuses outright"
    )
    # The declared one still deploys, and an undeclared TEXT column is
    # still cleared. The guard must not become "skip everything".
    assert fields["Note"]["validation_formula"] != UNMANAGED
    assert fields["Comment"]["validation_formula"] == ""
