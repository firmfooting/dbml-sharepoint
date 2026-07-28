"""The family standard, enforced.

Every template is meant to read as a member of one family: the same form
header anatomy, the same section arc, the same width scale, the same colour
vocabulary, and demo data that actually fills every view it declares.
Twenty-nine templates cannot hold that by convention alone, and four of them
are being uplifted in parallel branches that never see each other's work.

`NOT_YET_UPLIFTED` is a **shrinking allowlist, not a skip list.** Each theme
branch removes its own templates in the same commit that uplifts them, so
the sweep proves the claim rather than the commit message asserting it. It
must be EMPTY when the last theme branch lands. Nothing else here is
hardcoded: the roster of templates is discovered by globbing
`templates/*/10-design/schema.dbml`, because a hardcoded roster fails open
and this repository has already had to fix one that did (in the CI template
sweep). `test_the_roster_names_only_real_templates` is the check that keeps
the one hardcoded list honest.

Templates are loaded through the REAL loader and the REAL DBML parser — the
same entry points `dbml_sharepoint.cli` uses — so the sweep sees the objects
the build sees rather than a second, hand-rolled reading of the same YAML.

Spec: `docs/superpowers/specs/2026-07-28-template-family-standard-design.md`,
Part 1 (the seven conventions) and §3.1 (these assertions).
"""

import datetime as dt
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from dbml_sharepoint.analysis.conditions import normalise
from dbml_sharepoint.analysis.icons import FLEET_ICONS
from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES
from dbml_sharepoint.model.conditions import Condition, Group, Leaf
from dbml_sharepoint.model.mapping_loader import Mapping, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

# The twenty-seven templates that have not yet been through a theme branch.
# Removed by the branch that uplifts them; must reach empty.
NOT_YET_UPLIFTED: frozenset[str] = frozenset({
    "asset-register", "audit-actions", "change-register", "complaints-feedback",
    "compliance-obligations", "contract-register", "credentialing-register",
    "declarations-register", "delegations-register", "equipment-maintenance",
    "grants-register", "improvement-register", "incident-management",
    "meeting-actions", "onboarding-tracker",
    "policy-library", "process-register", "project-pipeline", "routine-checks",
    "service-requests", "stakeholder-contacts", "switchboard-log",
    "training-register", "vehicle-log", "visitor-log", "volunteer-register",
})

# §1.2. Order never changes; a small list may collapse the middle beats but
# may not reorder them, and System is always last.
SECTION_ARC: tuple[str, ...] = ("Identify", "Assess", "Act", "Govern", "System")

# §1.2 again: sections are named in each template's own domain language, so
# no literal string match is possible. The mapping from a template's section
# names to the arc's beats is DECLARED, per (template, entity). Adding a
# template's entry here is part of that template's uplift — an undeclared
# section name is a failure, not a pass, because that is the only thing
# standing between five beats and 102 section vocabularies.
SECTION_BEATS: dict[tuple[str, str], dict[str, str]] = {
    ("risk-register", "Risk"): {
        "Describe the risk": "Identify",
        "Assess the risk": "Assess",
        "Response and controls": "Act",
        "Governance": "Govern",
        "System": "System",
    },
    # The three boards are the same artefact at three levels, so they share
    # one vocabulary deliberately. "Streams" is the Assess beat: the whole
    # form is a per-stream rating, and a blank cell means unreported.
    **{
        ("tiered-huddle", entity): {
            "Header": "Identify",
            "Streams": "Assess",
            "Wrap-up": "Govern",
        }
        for entity in ("Tier1Board", "Tier2Board", "Tier3Board")
    },
    ("tiered-huddle", "Escalation"): {
        "The issue": "Identify",
        "Where it goes": "Act",
        "Outcome": "Govern",
    },
    # === Process digitisation & improvement ==================================
    # Five single-list templates that deliberately read as siblings: name the
    # thing, assess it against the definitions, act, govern, and a System
    # section holding the calculated score where one exists. measures-register
    # has no calculated column and no auto-stamp, so it collapses System away
    # rather than shipping an empty heading.
    ("measures-register", "Measure"): {
        "Name the measure": "Identify",
        "Define it": "Assess",
        "Report it": "Act",
        "Govern it": "Govern",
    },
}

# §1.3. Deliberately WEAKER than the archetype table in the spec, which is a
# review judgement rather than a test: this catches a typo (137), a paste
# error (1600) and a unit mistake, and does not catch a person column set to
# 200.
#
# It was first written as a closed set of ten values, from memory of
# risk-register rather than from risk-register — which uses 100, 130, 150,
# 170 and 260, five values that set did not contain. An enforced rule must
# be no stronger than what the reference actually satisfies.
WIDTH_SCALE: frozenset[int] = frozenset(range(100, 321, 10))

# ONE fixed reference date for every `today±N` resolution, on both sides of
# every comparison — a demo row's "today-30" and a view's "today+30" are
# resolved against the same day, so the demo-coverage tests give the same
# answer on every run and in every timezone.
REFERENCE_DATE = dt.date(2026, 7, 1)

# The operators the demo-coverage evaluator implements. Anything else makes
# the view UNEVALUABLE and is reported as a skip naming the view — never
# silently treated as satisfied.
SUPPORTED_OPS: frozenset[str] = frozenset({
    "eq", "neq", "lt", "leq", "gt", "geq", "in", "not_in", "is_null", "is_not_null",
})

# §3.1, the lifecycle/severity assertion — the NARROW, defensible reading.
#
# CATCHES: a Choice (DBML enum) or calculated_text column whose name ends in
# one of these words, and a date column whose name names a deadline.
# DOES NOT CATCH: a lifecycle enum named in some other idiom (risk-register's
# `RiskResponse`, `OverallControlEffectiveness`), or a severity-shaped enum
# that is an assessment input rather than a state (`Likelihood`,
# `Consequence`). Both were tried and both produce false positives on
# legitimate templates, which is worse than a narrower net: a sweep that
# fires on correct work gets weakened, and then it catches nothing.
#
# An earlier draft also treated "any date column a view filters on" as a
# deadline. That fires on tiered-huddle's `BoardDate` — the day a huddle
# board covers, filtered by a rolling-fortnight view and emphatically not a
# deadline — so the view-filter clause is dropped and the rule is name-based
# only.
LIFECYCLE_SUFFIXES: tuple[str, ...] = ("Status", "State", "Rating", "Severity", "Priority")
DEADLINE_NAME = re.compile(r"(Due|Expiry|Expires|Expiration|Deadline|Renewal)", re.IGNORECASE)
DATE_TYPES: frozenset[str] = frozenset({"date", "datetime", "calculated_date"})

_TODAY = re.compile(r"^today(?:([+-])(\d+))?$")


# === Discovery ==============================================================


def _all_templates() -> list[str]:
    """Discovered, never listed — a hardcoded roster fails open."""
    return sorted(p.parent.parent.name for p in TEMPLATES.glob("*/10-design/schema.dbml"))


def _uplifted() -> list[str]:
    return [name for name in _all_templates() if name not in NOT_YET_UPLIFTED]


@dataclass(frozen=True)
class Loaded:
    """One template, through the same two entry points the CLI uses."""

    name: str
    schema: Schema
    mapping: Mapping

    def column_types(self, entity: str) -> dict[str, str]:
        """{internal column name: DBML type} for the entity's table.

        Entity names are the DBML table names; an entity with no table is a
        build error the validator already reports, so an empty dict here
        simply leaves the type-dependent checks with nothing to say.
        """
        for table in self.schema.tables:
            if table.name == entity:
                return {column.name: column.type for column in table.columns}
        return {}

    @property
    def enum_names(self) -> frozenset[str]:
        return frozenset(enum.name for enum in self.schema.enums)


@cache
def _load(template: str) -> Loaded:
    root = TEMPLATES / template
    return Loaded(
        name=template,
        schema=parse_dbml(root / "10-design" / "schema.dbml"),
        mapping=load_mapping(root / "20-configure" / "mapping.yaml").mapping,
    )


# === The roster itself ======================================================


def test_the_roster_names_only_real_templates() -> None:
    """A typo here exempts nothing and leaves a real template unchecked."""
    unknown = NOT_YET_UPLIFTED - set(_all_templates())
    assert not unknown, f"NOT_YET_UPLIFTED names templates that do not exist: {sorted(unknown)}"


def test_at_least_the_exemplars_are_uplifted() -> None:
    """The two templates every theme branch copies from are always in scope."""
    assert set(_uplifted()) >= {"risk-register", "tiered-huddle"}


def test_the_declared_section_beats_are_arc_beats() -> None:
    """Guards SECTION_BEATS itself: a typo'd beat would otherwise fail the
    body test with a message pointing at the template rather than at here."""
    bad = {
        (key, name, beat)
        for key, table in SECTION_BEATS.items()
        for name, beat in table.items()
        if beat not in SECTION_ARC
    }
    assert not bad, f"section beats outside the arc {SECTION_ARC}: {sorted(bad)}"


# === §3.1, one test per assertion ===========================================


@pytest.mark.parametrize("template", _uplifted())
def test_every_list_declares_views_with_exactly_one_default(template: str) -> None:
    """A list with no declared default is a list left on *All Items*."""
    loaded = _load(template)
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        views = loaded.mapping.views.get(entity, [])
        if not views:
            problems.append(f"{entity}: declares no views")
            continue
        defaults = [view.title for view in views if view.default]
        if len(defaults) != 1:
            problems.append(f"{entity}: {len(defaults)} views marked default ({defaults})")
    assert not problems, f"{template}: " + "; ".join(problems)


@pytest.mark.parametrize("template", _uplifted())
def test_every_list_declares_a_form_header_and_a_body(template: str) -> None:
    """A half-built form: a body with no header, or no form_formatting at all."""
    loaded = _load(template)
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        form = loaded.mapping.form_formatting.get(entity)
        if form is None:
            problems.append(f"{entity}: no form_formatting")
            continue
        missing = [part for part, value in (("header", form.header), ("body", form.body))
                   if value is None]
        if missing:
            problems.append(f"{entity}: form_formatting declares no {' or '.join(missing)}")
    assert not problems, f"{template}: " + "; ".join(problems)


@pytest.mark.parametrize("template", _uplifted())
def test_display_names_are_declared(template: str) -> None:
    """Without it, every column title reads as its run-together internal name."""
    loaded = _load(template)
    assert loaded.mapping.display_name_mode is not None, (
        f"{template}: no display_names section — column titles would deploy as "
        f"their internal names"
    )


@pytest.mark.parametrize("template", _uplifted())
def test_every_list_has_demo_items(template: str) -> None:
    """A template nobody can demonstrate."""
    loaded = _load(template)
    missing = [
        entity for entity in sorted(loaded.mapping.entities)
        if not loaded.mapping.demo_items.get(entity)
    ]
    assert not missing, f"{template}: no demo_items for {missing}"


@pytest.mark.parametrize("template", _uplifted())
def test_lifecycle_and_deadline_columns_carry_column_formatting(template: str) -> None:
    """The single-`Status` habit. See LIFECYCLE_SUFFIXES for exactly what
    this catches and — just as importantly — what it deliberately does not."""
    loaded = _load(template)
    enums = loaded.enum_names
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        formatted = set(loaded.mapping.column_formatting.get(entity, {}))
        for name, column_type in loaded.column_types(entity).items():
            if loaded.mapping.is_retired(entity, name) or name in formatted:
                continue
            lifecycle = name.endswith(LIFECYCLE_SUFFIXES) and (
                column_type in enums or column_type == "calculated_text"
            )
            deadline = column_type in DATE_TYPES and DEADLINE_NAME.search(name) is not None
            if lifecycle:
                problems.append(f"{entity}.{name} ({column_type}): lifecycle/severity, unformatted")
            elif deadline:
                problems.append(f"{entity}.{name} ({column_type}): deadline date, unformatted")
    assert not problems, f"{template}: " + "; ".join(problems)


@pytest.mark.parametrize("template", _uplifted())
def test_every_declared_width_is_on_the_scale(template: str) -> None:
    """Invented widths. §1.3's scale is closed; a deviation is meant to be a
    deliberate, visible act rather than a number someone typed."""
    loaded = _load(template)
    problems: list[str] = []
    for entity, views in sorted(loaded.mapping.views.items()):
        for view in views:
            off_scale = {
                column: width for column, width in sorted(view.widths.items())
                if width not in WIDTH_SCALE
            }
            if off_scale:
                problems.append(f"{entity}/{view.title}: {off_scale}")
    assert not problems, (
        f"{template}: widths off the §1.3 scale {sorted(WIDTH_SCALE)} — "
        + "; ".join(problems)
    )


@pytest.mark.parametrize("template", _uplifted())
def test_every_header_has_an_icon_a_title_line_and_a_strapline(template: str) -> None:
    """§1.1's anatomy, in order: a Fluent icon at ms-fontSize-42, a live
    title line at ms-fontSize-16 referencing [$Title], and a one-sentence
    strapline at ms-fontSize-12. Classes are matched as a SET of tokens, not
    as a string — risk-register writes them in a different order and is
    correct."""
    loaded = _load(template)
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        form = loaded.mapping.form_formatting.get(entity)
        header = form.header if form is not None else None
        if header is None:
            problems.append(f"{entity}: no form header declared")
            continue
        nodes = list(_walk(header))
        missing = [
            part for part, present in (
                ("icon", any(_is_icon(node) for node in nodes)),
                ("title line", any(_is_title_line(node) for node in nodes)),
                ("strapline", any(_is_strapline(node) for node in nodes)),
            ) if not present
        ]
        if missing:
            problems.append(f"{entity}: header has no {', no '.join(missing)}")
    assert not problems, f"{template}: " + "; ".join(problems)


@pytest.mark.parametrize("template", _uplifted())
def test_every_header_icon_is_in_the_fleet_vocabulary(template: str) -> None:
    """An invented Fluent name renders as nothing, with no error anywhere in
    the build, the deploy or the browser console."""
    loaded = _load(template)
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        form = loaded.mapping.form_formatting.get(entity)
        if form is None or form.header is None:
            continue  # a missing header is the previous two tests' complaint
        for node in _walk(form.header):
            icon = _attributes(node).get("iconName")
            if isinstance(icon, str) and icon and icon not in FLEET_ICONS:
                problems.append(f"{entity}: iconName {icon!r}")
    assert not problems, (
        f"{template}: not in FLEET_ICONS — " + "; ".join(problems)
    )


@pytest.mark.parametrize("template", _uplifted())
def test_every_body_section_name_comes_from_the_arc(template: str) -> None:
    """§1.2. Sections are named in local language, so this checks the
    DECLARED mapping in SECTION_BEATS: between one and five sections, each
    name declared, and the beats a strictly increasing subsequence of
    Identify → Assess → Act → Govern → System."""
    loaded = _load(template)
    problems: list[str] = []
    for entity in sorted(loaded.mapping.entities):
        form = loaded.mapping.form_formatting.get(entity)
        body = form.body if form is not None else None
        if body is None:
            continue  # a missing body is the form_formatting test's complaint
        names = [
            str(section.get("displayname", ""))
            for section in body.get("sections", [])
            if isinstance(section, dict)
        ]
        if not 1 <= len(names) <= len(SECTION_ARC):
            problems.append(f"{entity}: {len(names)} sections, expected 1-{len(SECTION_ARC)}")
            continue
        table = SECTION_BEATS.get((template, entity))
        if table is None:
            problems.append(
                f"{entity}: no SECTION_BEATS entry — declare each section's arc beat "
                f"(sections are {names})",
            )
            continue
        undeclared = [name for name in names if name not in table]
        if undeclared:
            problems.append(f"{entity}: sections not in SECTION_BEATS: {undeclared}")
            continue
        beats = [table[name] for name in names]
        if not _is_ordered_subsequence(beats):
            problems.append(f"{entity}: beats {beats} are not an in-order subsequence of "
                            f"{list(SECTION_ARC)}")
    assert not problems, f"{template}: " + "; ".join(problems)


@pytest.mark.parametrize("template", _uplifted())
def test_every_declared_view_is_satisfied_by_a_demo_row(template: str) -> None:
    """Demo coverage A. A view that demos empty teaches the adopter it does
    not work.

    CALCULATED columns are handled by evaluating only the conjuncts that can
    be evaluated: a leaf on a calculated column returns UNKNOWN (SharePoint
    computes the value, so demo `values` cannot carry it), and the three-
    valued walk lets UNKNOWN propagate — a row that satisfies every knowable
    conjunct counts as satisfying the view. That is deliberately the weaker
    of the two options the spec allows: it still catches the failure that
    matters (a view whose knowable filter matches nothing) and it can never
    fire on a legitimate template. risk-register's "Above target"
    (`LevelsAboveTarget > 0`) is the case it exists for.
    """
    loaded = _load(template)
    empty: list[str] = []
    unevaluable: list[str] = []
    for entity, views in sorted(loaded.mapping.views.items()):
        rows = [item.values for item in loaded.mapping.demo_items.get(entity, [])]
        types = loaded.column_types(entity)
        for view in views:
            where = f"{entity}/{view.title}"
            if view.where is None:
                if not rows:
                    empty.append(f"{where}: no demo rows at all")
                continue
            try:
                condition = normalise(view.where)
                satisfied = any(_evaluate(condition, row, types) is not False for row in rows)
            except _UnevaluableError as exc:
                unevaluable.append(f"{where}: {exc}")
                continue
            if not satisfied:
                empty.append(where)
    assert not empty, f"{template}: views no demo row satisfies — " + "; ".join(empty)
    if unevaluable:
        pytest.skip(
            f"{template}: {len(unevaluable)} view(s) NOT checked (unsupported operator) — "
            + "; ".join(unevaluable),
        )


@pytest.mark.parametrize("template", _uplifted())
def test_every_formatted_column_is_exercised_by_a_demo_row(
    template: str, capsys: pytest.CaptureFixture[str],
) -> None:
    """Demo coverage B (§1.7): every formatted column must have at least one
    demo row holding a value its `map:` actually keys on. That proves the
    formatter renders, and that the map speaks the data's vocabulary.

    It does NOT demand every individual token be exercised. That was the
    first version of this bar and it is the wrong one:

    - it asks for data nobody would write — no sensible demo row sets a
      risk's TARGET rating to Extreme, and tiered-huddle maps "Not
      applicable" on all 27 stream columns;
    - the bug it aimed at is already caught statically and better. A map key
      that is not a member of the column's enum — the stale key a rename
      leaves behind, which is how these maps actually break — is a build
      error today (analysis/checks/_formatting.py:103, and :120 for nested
      color_by maps).

    Unexercised tokens are still PRINTED, so the information survives the
    decision not to fail on it.

    Reads the RAW style specs (`column_style_specs`), which still carry the
    authored `map:` — the expanded formatter JSON has already turned it into
    an =if chain. Nested `color_by:` maps are attributed to the column they
    read, not to the column they colour. A map on a CALCULATED column is
    skipped: SharePoint computes the value, so no demo `values` dict can
    carry it. Retired columns are skipped for the same reason they are
    exempt elsewhere — retirement takes them off the forms and views.
    """
    loaded = _load(template)
    unexercised: set[str] = set()
    unrendered: set[str] = set()
    for entity, columns in sorted(loaded.mapping.column_style_specs.items()):
        rows = [item.values for item in loaded.mapping.demo_items.get(entity, [])]
        types = loaded.column_types(entity)
        for column, spec in sorted(columns.items()):
            if loaded.mapping.is_retired(entity, column):
                continue
            for source, value_map in _token_maps(column, spec):
                if types.get(source, "") in CALCULATED_TYPES:
                    continue
                if loaded.mapping.is_retired(entity, source):
                    continue
                seen = {
                    str(row[source]) for row in rows
                    if row.get(source) is not None
                }
                if not (set(value_map) & seen):
                    unrendered.add(
                        f"{entity}.{source} (map keys {sorted(value_map)})",
                    )
                for token in sorted(set(value_map.values())):
                    members = {name for name, mapped in value_map.items() if mapped == token}
                    if not (members & seen):
                        unexercised.add(
                            f"{entity}.{source} token {token!r} (members {sorted(members)})",
                        )
    if unexercised:
        with capsys.disabled():
            # T201 is suppressed deliberately: the rule exists to keep stray
            # debug prints out of the suite, and this is the report §1.7 asks
            # for — unexercised tokens are worth surfacing even though the
            # spec decided not to fail on them.
            print(  # noqa: T201
                f"\n[{template}] tokens no demo row exercises "
                f"({len(unexercised)}) — reported, not asserted:\n  "
                + "\n  ".join(sorted(unexercised)),
            )
    assert not unrendered, (
        f"{template}: formatted columns no demo row ever gives a mapped value, so "
        f"the formatter is never seen to render — " + "; ".join(sorted(unrendered))
    )


# === Header/body JSON helpers ===============================================


def _walk(node: Any) -> "list[dict[str, Any]]":
    """Every dict in a formatter JSON tree, depth first."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(_walk(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk(item))
    return found


def _attributes(node: dict[str, Any]) -> dict[str, Any]:
    attributes = node.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _classes(node: dict[str, Any]) -> set[str]:
    """Class tokens as a SET: §1.1 fixes the classes, not their order."""
    raw = _attributes(node).get("class")
    return set(str(raw).split()) if isinstance(raw, str) else set()


def _text(node: dict[str, Any]) -> str:
    value = node.get("txtContent")
    return value if isinstance(value, str) else ""


def _is_icon(node: dict[str, Any]) -> bool:
    icon = _attributes(node).get("iconName")
    return isinstance(icon, str) and bool(icon) and "ms-fontSize-42" in _classes(node)


def _is_title_line(node: dict[str, Any]) -> bool:
    text = _text(node)
    return (
        text.startswith("=")
        and "[$Title]" in text
        and {"ms-fontSize-16", "ms-fontWeight-bold"} <= _classes(node)
    )


def _is_strapline(node: dict[str, Any]) -> bool:
    """A literal sentence, not an expression and not the optional guide link."""
    text = _text(node)
    return (
        node.get("elmType") != "a"
        and bool(text.strip())
        and not text.startswith("=")
        and "ms-fontSize-12" in _classes(node)
    )


def _is_ordered_subsequence(beats: list[str]) -> bool:
    """Strictly increasing positions in SECTION_ARC: beats may be collapsed,
    never reordered, and no two sections may claim the same beat."""
    previous = -1
    for beat in beats:
        position = SECTION_ARC.index(beat)
        if position <= previous:
            return False
        previous = position
    return True


def _token_maps(column: str, spec: dict[str, Any]) -> list[tuple[str, dict[str, str]]]:
    """(source column, {member: token}) for a raw style spec's `map:` blocks."""
    maps: list[tuple[str, dict[str, str]]] = []
    top = spec.get("map")
    if isinstance(top, dict):
        maps.append((column, {str(k): str(v) for k, v in top.items()}))
    colour_by = spec.get("color_by")
    if isinstance(colour_by, dict):
        nested = colour_by.get("map")
        source = str(colour_by.get("field", column))
        if isinstance(nested, dict):
            maps.append((source, {str(k): str(v) for k, v in nested.items()}))
    return maps


# === Evaluating a view's `where` against a demo row =========================


class _UnevaluableError(Exception):
    """This evaluator cannot decide the condition. Reported as a visible skip
    naming the view — never silently treated as satisfied."""


def _evaluate(node: Condition, row: dict[str, Any], types: dict[str, str]) -> bool | None:
    """Three-valued walk. None means UNKNOWN — a leaf this evaluator cannot
    decide from demo `values` (a calculated column, or the `me` sentinel).
    UNKNOWN propagates the way SQL's does, so it can only ever make the
    answer less certain, never falsely negative."""
    if isinstance(node, Leaf):
        return _evaluate_leaf(node, row, types)
    if not isinstance(node, Group):  # pragma: no cover - the type is closed
        raise _UnevaluableError(f"unknown condition node {type(node).__name__}")
    results = [_evaluate(child, row, types) for child in node.children]
    if node.kind == "all_of":
        if any(result is False for result in results):
            return False
        return None if any(result is None for result in results) else True
    if node.kind == "any_of":
        if any(result is True for result in results):
            return True
        return None if any(result is None for result in results) else False
    # normalise() eliminates none_of; reaching it means the tree was not
    # normalised, and guessing would be worse than saying so.
    raise _UnevaluableError(f"group kind {node.kind!r} survived normalisation")


def _evaluate_leaf(leaf: Leaf, row: dict[str, Any], types: dict[str, str]) -> bool | None:
    if leaf.property or leaf.measure:
        raise _UnevaluableError(f"{leaf.field}: 'property'/'measure' comparisons are not evaluated")
    if leaf.op not in SUPPORTED_OPS:
        raise _UnevaluableError(f"operator {leaf.op!r} on {leaf.field!r}")
    column_type = types.get(leaf.field, "")
    if column_type in CALCULATED_TYPES:
        return None  # SharePoint computes it; a demo `values` dict cannot
    if column_type == "person" and leaf.value == "me":
        return None  # the current user is a deploy-time fact
    raw = row.get(leaf.field)
    blank = raw is None or (isinstance(raw, str) and not raw.strip())
    if leaf.op == "is_null":
        return blank
    if leaf.op == "is_not_null":
        return not blank
    if blank:
        # Matches the grammar's own three-valued semantics (see the note in
        # analysis/conditions.py): neq/not_in place the empty value outside
        # the compared literal, every other comparison excludes it.
        return leaf.op in ("neq", "not_in")
    if leaf.op in ("in", "not_in"):
        if not isinstance(leaf.value, list):
            raise _UnevaluableError(f"{leaf.field}: {leaf.op} value is not a list")
        member = any(_compare("eq", raw, candidate) for candidate in leaf.value)
        return member if leaf.op == "in" else not member
    return _compare(leaf.op, raw, leaf.value)


def _compare(op: str, left: Any, right: Any) -> bool:
    lhs, rhs = _align(left, right)
    match op:
        case "eq":
            return bool(lhs == rhs)
        case "neq":
            return bool(lhs != rhs)
        case "lt":
            return bool(lhs < rhs)
        case "leq":
            return bool(lhs <= rhs)
        case "gt":
            return bool(lhs > rhs)
        case "geq":
            return bool(lhs >= rhs)
        case _:  # pragma: no cover - SUPPORTED_OPS gates this
            raise _UnevaluableError(f"operator {op!r}")


def _align(left: Any, right: Any) -> tuple[Any, Any]:
    """Compare like with like: dates if both sides are dates, numbers if both
    are numeric, strings otherwise. Mixed pairs fall to string comparison,
    which is what a choice member against a literal wants anyway."""
    left_date, right_date = _as_date(left), _as_date(right)
    if left_date is not None and right_date is not None:
        return left_date, right_date
    left_number, right_number = _as_number(left), _as_number(right)
    if left_number is not None and right_number is not None:
        return left_number, right_number
    return str(left), str(right)


def _as_date(value: Any) -> dt.date | None:
    """A date, a `today±N` sentinel resolved against REFERENCE_DATE, or an
    ISO `YYYY-MM-DD` string. Deliberately requires the hyphens: ISO basic
    format would read a bare number as a date."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _TODAY.match(text)
    if match is not None:
        offset = int(match.group(2) or 0)
        return REFERENCE_DATE + dt.timedelta(days=-offset if match.group(1) == "-" else offset)
    if "-" not in text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
