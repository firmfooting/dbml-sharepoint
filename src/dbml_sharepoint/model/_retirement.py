# src/dbml_sharepoint/model/_retirement.py
"""Parsing and folding of the retired_columns: section.

A retirement is declared once and then REWRITES other sections at load
time: it synthesises a form_visibility entry, appends the display-title
suffix, and strips the column from every view and form body that named it.
Keeping that fold here means the rest of the loader deals only in the
already-resolved structures, and the record of what was rewritten travels
on Mapping.retirement_strips for the validator to report.
"""

from dataclasses import replace
from typing import Any, cast

from dbml_sharepoint.model._keys import _reject_unknown_keys
from dbml_sharepoint.model._mapping_types import (
    RETIRED_SUFFIX,
    EntitySection,
    FormFormatting,
    FormVisibility,
    Mapping,
    RetiredColumn,
    RetirementStrip,
    ViewDef,
)

_RETIREMENT_KEYS = frozenset({"retired", "superseded_by", "reason", "hide_existing"})


def _parse_retired_columns(raw: Any, context: str) -> dict[str, RetiredColumn]:
    """Parse one entity's `retired_columns` block.

    Two accepted forms: the bare list shorthand (`[ColA, ColB]`) for the
    minimal case, and the full mapping form carrying retired /
    superseded_by / reason / hide_existing. Structural checks only.
    """
    if isinstance(raw, list):
        bare: dict[str, RetiredColumn] = {}
        for item in raw:
            if not isinstance(item, str):
                raise ValueError(
                    f"{context}: bare-list entries must be column names, "
                    f"got {type(item).__name__}",
                )
            bare[item] = RetiredColumn(column=item)
        return bare
    if not isinstance(raw, dict):
        raise ValueError(
            f"{context}: expected a mapping of column name to retirement "
            f"details, or a bare list of column names, got "
            f"{type(raw).__name__}",
        )
    parsed: dict[str, RetiredColumn] = {}
    for col, spec in raw.items():
        col_ctx = f"{context}.{col}"
        if not isinstance(spec, dict):
            raise ValueError(
                f"{col_ctx}: expected a mapping with 'retired' and optional "
                f"superseded_by / reason / hide_existing, got "
                f"{type(spec).__name__}",
            )
        _reject_unknown_keys(spec, _RETIREMENT_KEYS, col_ctx)
        retired = spec.get("retired")
        if retired is None:
            raise ValueError(f"{col_ctx}: 'retired' (an ISO date) is required")
        hide = spec.get("hide_existing", False)
        if not isinstance(hide, bool):
            raise ValueError(
                f"{col_ctx}.hide_existing must be a boolean, got {hide!r}",
            )
        superseded = spec.get("superseded_by")
        parsed[str(col)] = RetiredColumn(
            column=str(col),
            # A YAML date scalar arrives as datetime.date; str() normalises
            # it back to the ISO text the validator and manifest expect.
            retired=str(retired),
            superseded_by=str(superseded) if superseded is not None else None,
            reason=str(spec.get("reason", "")),
            hide_existing=hide,
        )
    return parsed


def _strip_retired_from_view(
    view: ViewDef,
    entity: str,
    retired: dict[str, RetiredColumn],
    strips: list[RetirementStrip],
) -> ViewDef:
    """A copy of the view with retired columns removed from `fields` and
    `widths`, recording each removal in `strips`.

    Retirement must never break a build, so an explicit reference is
    stripped and reported as a warning rather than failing — and stripping
    the width too keeps the validator's "widths must name one of this
    view's fields" check honest, which would otherwise turn retirement into
    an ERROR.
    """
    named = [name for name in view.fields if name in retired]
    widths_named = [name for name in view.widths if name in retired]
    if not named and not widths_named:
        return view
    strips += [
        RetirementStrip(
            entity=entity, column=name,
            context=f"views[{entity}].{view.title} fields",
        )
        for name in named
    ]
    strips += [
        RetirementStrip(
            entity=entity, column=name,
            context=f"views[{entity}].{view.title} widths",
        )
        for name in widths_named
    ]
    return replace(
        view,
        fields=[name for name in view.fields if name not in retired],
        widths={col: px for col, px in view.widths.items() if col not in retired},
    )


def _strip_retired_from_form(
    form: FormFormatting,
    entity: str,
    retired: dict[str, RetiredColumn],
    strips: list[RetirementStrip],
) -> FormFormatting:
    """A copy of the form layout with retired columns removed from its body
    `sections[].fields`, recording each removal.

    Retirement's contract is that the column leaves the entry experience. A
    section that still lists a retired field would rely on SharePoint
    honouring the hiding formula over an explicit section placement, which
    is untested against live SharePoint — and the fold already strips views
    and widths, so leaving form bodies alone would be an inconsistency
    resting on an assumption.

    ONLY `sections[].fields` is touched: it is the single shape in an
    otherwise arbitrary formatter JSON with a known meaning, and the one the
    validator already walks. Every other key is left exactly as authored. A
    section left with an empty `fields` list is KEPT — an empty section is
    the author's layout decision to clean up, and dropping it would be a
    second-order mutation of their JSON.
    """
    body = form.body
    if body is None:
        return form
    sections = body.get("sections")
    if not isinstance(sections, list):
        return form

    def _fields_of(section: object) -> list[Any] | None:
        if isinstance(section, dict) and isinstance(section.get("fields"), list):
            return cast("list[Any]", section["fields"])
        return None

    named = [
        name
        for section in sections
        for name in (_fields_of(section) or [])
        if name in retired
    ]
    if not named:
        return form
    # dict.fromkeys: one column may legitimately be listed under two
    # sections in a hand-authored body; that is one retirement, not two.
    strips += [
        RetirementStrip(
            entity=entity, column=name,
            context=f"form_formatting[{entity}].body sections",
        )
        for name in dict.fromkeys(named)
    ]
    stripped = [
        (
            {**section, "fields": [n for n in fields if n not in retired]}
            if (fields := _fields_of(section)) is not None
            and isinstance(section, dict)
            else section
        )
        for section in sections
    ]
    # Re-spreading an existing key keeps its original position, so the rest
    # of the body renders byte-for-byte as authored.
    return replace(form, body={**body, "sections": stripped})


def _apply_retirement(mapping: Mapping) -> None:
    """Fold every `retired_columns` declaration into the already-parsed
    structures, in place.

    Retirement introduces NO new deploy-time capability: it resolves here
    into mechanisms deploy.js already implements — `form_visibility`,
    `display_name_overrides` and each view's field list. The parsed
    `retired_columns` dict stays on the Mapping as the authoritative record
    for the manifest, the data dictionary and the validator; folding rather
    than dispersing accessors keeps the single emission sequence intact.

    Form behaviour resolves to `new: false` — nobody enters new data into a
    retired column — and `existing: true` unless `hide_existing` is
    declared, so the history the column exists to preserve stays readable
    on the Display form. The Edit and Display forms cannot be separated on
    a modern list, so hiding from one hides from the other; that is why the
    spec's "hidden on new AND edit, readable on display" is not achievable
    and why the default keeps the read side.

    A synthesised section reconciles as `declared`, not `exact`: retiring
    one column must not silently start clearing the ClientValidationFormula
    of every other column on that list. When the author already declared a
    section, their own reconcile mode stands.

    Carve-out: a retired CALCULATED column never reaches form_visibility.
    SharePoint never renders calculated columns on entry forms and the
    validator errors on one declared there, so folding blindly would make
    retiring a calculated column an unfixable build error. The loader has
    not seen the DBML, so calculated columns are identified by their
    `calculated_formulas` entry — which the validator requires for every
    calculated column, in both directions.

    INVARIANT: this carve-out is correct only while `calculated_formulas`
    keys are exactly the set of `calculated_*` columns. That pairing is
    enforced downstream, in validate_against_mapping, and pinned by
    test_calculated_formula_pairing_guards_the_retirement_carve_out.

    Ordering: `field_sets` expansion rewrites `views[].fields` BEFORE this
    call, so the strip below always operates on the resolved, de-duplicated
    field list.
    """
    for entity, retired in mapping.retired_columns.items():
        if not retired:
            continue
        calculated = set(mapping.calculated_formulas.get(entity, {}))
        for column, spec in retired.items():
            if column not in calculated:
                section = mapping.form_visibility.get(entity)
                if section is None:
                    section = EntitySection(reconcile="declared", columns={})
                    mapping.form_visibility[entity] = section
                elif column in section.columns:
                    mapping.retirement_strips.append(RetirementStrip(
                        entity=entity, column=column,
                        context=f"form_visibility[{entity}].columns",
                    ))
                section.columns[column] = FormVisibility(
                    new=False, existing=not spec.hide_existing,
                )
            # Read before write: display_name_for returns an explicit
            # override when one is declared and the auto-split name
            # otherwise, so the suffix appends to whichever already wins.
            base = mapping.display_name_for(entity, column)
            mapping.display_name_overrides.setdefault(entity, {})[column] = (
                base + RETIRED_SUFFIX
            )
        views = mapping.views.get(entity)
        if views:
            mapping.views[entity] = [
                _strip_retired_from_view(
                    view, entity, retired, mapping.retirement_strips,
                )
                for view in views
            ]
        form = mapping.form_formatting.get(entity)
        if form is not None:
            mapping.form_formatting[entity] = _strip_retired_from_form(
                form, entity, retired, mapping.retirement_strips,
            )

