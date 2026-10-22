"""Render a form.yaml header or footer component tree as formatter JSON.

The build adds no words: every visible word is a literal from the tree. It adds only structural
punctuation: a middle dot between subtitle parts, a colon after a bubble label (unless switched
off) and a slash in a computed date.
A calculated column a header reads is replaced by its translated formula, because a header
reads one as blank.
Shapes follow the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference):
elmType div, span and a; the style properties display, flex, padding, margin, border-radius and
the like; the attributes class, href, target, rel and iconName; `if`, `+`, `==`, `!=`, `&&`,
`||`, `toString()` and `[$Field.displayValue]`. Learn gives no escape for a quote inside an
expression's literal, so a literal containing one is refused. Learn also does not say how a plain
string with an embedded `[$` or `@` marker is read, so static text containing one is refused.
`Number(@now)` as epoch milliseconds is inferred from Learn's `@now + 86400000` sample.
"""

import dataclasses
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

from dbml_sharepoint.analysis.column_projection import system_column_types_for
from dbml_sharepoint.analysis.condition_rendering import ConditionRefusal, to_expression
from dbml_sharepoint.analysis.conditions import REFUSAL_FINDING_CODES
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.formatter_values import quoted
from dbml_sharepoint.analysis.formula.civil import parts_of
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal, too_large
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import (
    ALWAYS,
    NEVER,
    TranslationContext,
    translate_column,
)
from dbml_sharepoint.analysis.formula.zone import out_of_span_instant, site_day, zone_rule
from dbml_sharepoint.analysis.icons import FLEET_ICONS
from dbml_sharepoint.analysis.limits import FORM_HEADER_MAX_CHARS
from dbml_sharepoint.analysis.list_url import list_folder
from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.analysis.typemap import (
    CALCULATED_TYPES,
    DATE_TYPES,
    NUMBER_TYPES,
    element_type,
    is_multi_value,
)
from dbml_sharepoint.model.conditions import Condition
from dbml_sharepoint.model.env_file import HELP_BASE_URL_KEY, HELP_GUIDES_KEY
from dbml_sharepoint.model.form_tree import (
    Badge,
    Banner,
    BannerRule,
    Bubble,
    HeaderTree,
    LinkChip,
    NewItemStep,
    Row,
)
from dbml_sharepoint.model.help_guides import HelpGuides
from dbml_sharepoint.model.mapping_types import EntityMapping, MappingBundle
from dbml_sharepoint.model.parser import Schema

_SCHEMA = "https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json"
_VALUE = "{value}"
_WEB = "{web}"
_SEPARATOR = chr(0xB7)  # middle dot; formatter text, so not a console message
_LITERAL = re.compile(r"('(?:[^']|'')*')")
_REF = re.compile(r"\[\$([A-Za-z0-9_]+)\]")
# A quoted literal is matched first so text inside one is left alone.
_DATE_BLANK = re.compile(r"'(?:[^']|'')*'|\[\$([A-Za-z0-9_]+)\] (==|!=) ''")
_TEXT_TYPES = frozenset({"nvarchar", "longtext"})
# A calculated type is "calculated_" plus the kind of its result; the vocabulary stays in typemap.
_CALCULATED_KIND: dict[str, ColumnKind] = {
    t: "number" if t.endswith("number") else "date" if t.endswith("date") else "text"
    for t in CALCULATED_TYPES
}
_CALCULATED_AS = {t: {"text": "nvarchar"}.get(k, k) for t, k in _CALCULATED_KIND.items()}
_SECONDARY = "ms-fontColor-neutralSecondary"
_HELP_SUFFIX: Final = ", opens the step guide in a new tab"
Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class RenderContext:
    entity: str
    types: Mapping[str, str]  # column -> DBML type, system columns included
    formulas: Mapping[str, str]  # calculated column -> formula
    choices: Mapping[str, tuple[str, ...]]  # choice column -> its values
    zone: str
    list_path: str | None = None  # the list's web-relative folder; None when a retitle may move it
    # stored number columns that are required and have a default, so are never blank
    filled_numbers: frozenset[str] = frozenset()
    # lookup column -> whether it holds many values
    lookups: Mapping[str, bool] = dataclasses.field(default_factory=dict)
    # guide key -> URL; None means help links are off, empty means on with nothing mapped
    help_guides: Mapping[str, str] | None = None


class HeaderRefusal(Exception):  # noqa: N818 -- named for the finding it becomes
    def __init__(self, finding: Finding) -> None:
        super().__init__(finding.message)
        self.finding = finding


@dataclass(frozen=True, slots=True)
class _Value:
    code: str  # the text to show
    blank: str  # true while there is nothing to show
    filled: str  # true while there is something to show


def inline_calculated(expression: str, translations: Mapping[str, str]) -> str:
    """`expression` with each `[$Calc]` outside a quoted literal replaced by its translation."""
    parts = _LITERAL.split(expression)
    for i in range(0, len(parts), 2):
        parts[i] = _REF.sub(lambda m: translations.get(m[1], m[0]), parts[i])
    return "".join(parts)


def _date_text(day: str, order: str) -> str:
    """A day number written as `order` joined by '/', unpadded: toString(45) gives "45" (Learn)."""
    year, month, date = parts_of(day)
    parts = {"d": date, "m": month, "y": year}
    # Parenthesised so no comparison built around the text depends on + against == precedence.
    return "(" + " + '/' + ".join(f"toString({parts[letter]})" for letter in order) + ")"


# Measured: [$ID] is empty on the New form and the item's id on Display and Edit.
_IS_NEW = "([$ID] == '')"


def _chain(pairs: Sequence[tuple[str, str]], fallback: str) -> str:
    code = quoted(fallback)
    for condition, value in reversed(pairs):
        code = f"if({condition}, {quoted(value)}, {code})"
    return code


def _drop_stop(text: str) -> str:
    text = text.rstrip()
    return text.removesuffix(".").rstrip()


def _any(conditions: Sequence[str]) -> str:
    return "(" + " || ".join(conditions) + ")"


def _display(
    word: str, *, when: str | None = None, shown: str | None = None, hidden: str | None = None
) -> str:
    """The display value `word`, or none unless `when` and `shown` hold and `hidden` does not."""
    code = quoted(word)
    if hidden is not None:
        code = f"if({hidden}, 'none', {code})"
    if shown is not None:
        code = f"if({shown}, {code}, 'none')"
    if when is not None:
        code = f"if({when}, {code}, 'none')"
    return word if code == quoted(word) else "=" + code


class _Render:
    def __init__(self, ctx: RenderContext) -> None:
        self.ctx = ctx
        kinds: dict[str, ColumnKind] = {}
        for name, declared in ctx.types.items():
            if name in ctx.formulas:
                continue
            if name in ctx.choices:
                kinds[name] = "choice"
            elif declared in _TEXT_TYPES:
                kinds[name] = "text"
            elif declared in ("int", "number"):
                kinds[name] = "number"
            elif declared in ("date", "datetime"):
                kinds[name] = "date"
        results = {
            n: _CALCULATED_KIND[ctx.types[n]]
            for n in ctx.formulas
            if ctx.types.get(n) in _CALCULATED_KIND
        }
        self.translation = TranslationContext(
            formulas=ctx.formulas,
            kinds=kinds,
            result_types=results,
            choices=ctx.choices,
            zone=ctx.zone,
            moments=frozenset(n for n, t in ctx.types.items() if t == "datetime"),
        )
        self.translated: dict[str, str] = {}
        self.days: dict[str, tuple[str, str]] = {}  # calculated date -> (day number, blank test)
        self.units: dict[str, str] = {}  # calculated column -> the text it adds, for sizing
        # The renderer refuses a calculated column; it is typed as its result and inlined after.
        self.condition_types = {
            n: _CALCULATED_AS.get(t, t) for n, t in ctx.types.items()
        }

    # --- refusals -------------------------------------------------------------------------
    def refusal(self, code: FindingCode, column: str | None, detail: str) -> HeaderRefusal:
        where = self.ctx.entity if column is None else f"{self.ctx.entity}.{column}"
        return HeaderRefusal(Finding(
            code, f"{where}: {detail}",
            location=Location(Section.FORM_FORMATTING, entity=self.ctx.entity, column=column),
        ))

    def from_formula(self, error: FormulaRefusal, column: str, what: str) -> HeaderRefusal:
        return self.refusal(error.code, column, f"{what} {error.detail}.")

    # --- columns --------------------------------------------------------------------------
    def calc(self, column: str) -> str:
        if column not in self.translated:
            try:
                found = translate_column(column, self.translation)
            except FormulaRefusal as error:
                formula = self.ctx.formulas[column]
                raise self.from_formula(error, column, f"the header formula {formula!r}") from error
            self.translated[column] = "(" + found.expression[1:] + ")"
            self.units[column] = found.day or self.translated[column]
            if found.result == "date":
                self.days[column] = (found.day, found.blank)
        return self.translated[column]

    def inline(self, expression: str) -> str:
        names = {m[1] for part in _LITERAL.split(expression)[::2] for m in _REF.finditer(part)}
        return inline_calculated(
            expression, {n: self.calc(n) for n in sorted(names) if n in self.ctx.formulas}
        )

    def is_calculated_date(self, column: str) -> bool:
        kind = _CALCULATED_KIND.get(self.ctx.types[column])
        return column in self.ctx.formulas and kind == "date"

    def date_value(self, column: str, order: str | None) -> _Value:
        if order is None:
            raise self.refusal(
                FindingCode.FORM_HEADER_DATE_ORDER_NEEDED, column,
                "the header shows a calculated date as text, and core cannot know the site's "
                "regional date order: set date_order (dmy, mdy or ymd) on a bubble for it.",
            )
        self.calc(column)
        day, blank = self.days[column]
        # A blank row is hidden by the bubble, so the text is not guarded again.
        filled = f"if({blank}, {NEVER}, {ALWAYS})" if blank else ALWAYS
        return _Value(_date_text(day, order), blank or NEVER, filled)

    def lookup_value(self, column: str) -> _Value:
        if self.ctx.lookups[column]:
            raise self.refusal(
                FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, column,
                f"the chip url_column {column} is a multi-value lookup: a link needs one "
                "value, so use a single-value lookup.",
            )
        # The raw value is "<id>;#<text>", and exactly '' when blank; .lookupValue is undefined.
        raw = f"toString([${column}])"
        text = f"substring({raw}, indexOf({raw}, ';#') + 2, 300)"
        return _Value(text, f"{raw} == ''", f"{raw} != ''")

    def value(self, column: str, order: str | None = None, *, url: bool = False) -> _Value:
        declared = self.ctx.types[column]
        if url and column in self.ctx.lookups:
            return self.lookup_value(column)
        if self.is_calculated_date(column):
            return self.date_value(column, order)
        if column in self.ctx.formulas:
            code = self.calc(column)
            if _CALCULATED_KIND[declared] != "text":
                raise self.refusal(
                    FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, column,
                    "a number is shown in a header, and its display is not measured.",
                )
            return _Value(code, f"{code} == ''", f"{code} != ''")
        stored = f"toString([${column}])"
        if column in self.ctx.choices or declared in _TEXT_TYPES:
            return _Value(f"[${column}]", f"{stored} == ''", f"{stored} != ''")
        if declared in ("date", "datetime"):
            # The documented displayValue is the site's regional format; a blank date is ''.
            return _Value(f"[${column}.displayValue]", f"{stored} == ''", f"{stored} != ''")
        if declared in NUMBER_TYPES:
            # Learn does not say what a blank number is, so only a column that cannot be blank.
            if column not in self.ctx.filled_numbers:
                raise self.refusal(
                    FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, column,
                    f"the header shows the {declared} column {column}, whose blank value is "
                    "not documented: make it required with a default.",
                )
            return _Value(stored, NEVER, ALWAYS)  # raw value; its formatted display is unmeasured
        raise self.refusal(
            FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, column,
            f"the header shows a {declared} column, which it can show only for text, choice, "
            "date and number columns.",
        )

    def date_blank(self, found: re.Match[str]) -> str:
        if found[1] is None or not (
            self.ctx.types.get(found[1]) in ("date", "datetime")
            or self.is_calculated_date(found[1])
        ):
            return found[0]
        return f"toString([${found[1]}]) {found[2]} ''"

    def condition(self, when: Condition) -> str:
        try:
            raw = to_expression(when, self.condition_types)
        except ConditionRefusal as error:
            code = REFUSAL_FINDING_CODES[error.kind]
            raise self.refusal(code, error.field, str(error)) from error
        for literal in _LITERAL.findall(raw):
            if "''" in literal[1:-1]:  # the doubled quote the renderer writes for a single quote
                raise self.refusal(
                    FindingCode.FORM_HEADER_TEXT_UNSUPPORTED, None,
                    f"a condition value contains a single quote ({literal}), and no escape "
                    "for one inside an expression is measured.",
                )
        # A blank date field is not '' (measured), so its blank test is on its text.
        raw = _DATE_BLANK.sub(self.date_blank, raw)
        for part in _LITERAL.split(raw)[::2]:
            for ref in _REF.finditer(part):
                before = part[: ref.start()]
                if self.is_calculated_date(ref[1]) and not before.endswith("toString("):
                    raise self.refusal(
                        FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, ref[1],
                        "a condition compares a calculated date, and only blank or not blank "
                        "is supported.",
                    )
        return "(" + self.inline(raw) + ")"

    # --- text -----------------------------------------------------------------------------
    def lit(self, text: str, where: str, column: str | None = None) -> str:
        """`text` as a quoted literal inside an expression; a single quote is refused."""
        if "'" in text:
            raise self.refusal(
                FindingCode.FORM_HEADER_TEXT_UNSUPPORTED, column,
                f"the {where} text {text!r} contains a single quote, and no escape "
                "for one inside an expression is measured.",
            )
        return quoted(text)

    def plain(self, text: str, where: str, column: str | None = None) -> str:
        """`text` as a plain txtContent or href, or as a literal when it starts like a formula."""
        if "[$" in text or "@" in text:
            raise self.refusal(
                FindingCode.FORM_HEADER_TEXT_UNSUPPORTED, column,
                f"the {where} text {text!r} contains [$ or @, which the formatting reference "
                "does not say a plain string leaves alone.",
            )
        return "=" + self.lit(text, where, column) if text.startswith(("=", "[")) else text

    def template(
        self, text: str, value: str, where: str, column: str | None = None
    ) -> list[str]:
        """The pieces of `text` with `{value}` replaced by `value`, quoted where literal."""
        pieces: list[str] = []
        chunks = text.split(_VALUE)
        for i, chunk in enumerate(chunks):
            if chunk:
                pieces.append(self.lit(chunk, where, column))
            if i < len(chunks) - 1:
                pieces.append(value)
        return pieces or ["''"]

    def url_pieces(self, chip: LinkChip, value: str) -> list[str]:
        """The chip's url template: a leading {web} is @currentWeb, {list} the list's own path."""
        text = chip.url_template or ""
        lead: list[str] = []
        if text.startswith(_WEB):
            lead, text = ["@currentWeb"], text.removeprefix(_WEB)
        if "{list}" in text:
            if self.ctx.list_path is None:
                raise self.refusal(
                    FindingCode.FORM_HEADER_TEXT_UNSUPPORTED, chip.url_column,
                    "the chip url uses {list}, and the list keeps the root folder of an earlier "
                    "title (renamed_from, previous_prefixes or an added title), which its "
                    "current title does not give. Set internal_name to the retained root.",
                )
            # Per-segment encoding as every item link does, so # and % survive.
            encoded = "/".join(quote(seg, safe="") for seg in self.ctx.list_path.split("/"))
            text = text.replace("{list}", encoded)
        return lead + self.template(text, value, "chip url", chip.url_column)

    # --- components -----------------------------------------------------------------------
    def tree(self, tree: HeaderTree) -> Json:
        self.known_columns(tree)
        identity = self.identity(tree)
        chips: Json | None = None
        if tree.chips:
            chips = {
                "elmType": "div",
                "style": {
                    "display": "flex", "flex-wrap": "wrap", "align-items": "center",
                    "margin-left": "-8px", "max-width": "100%",
                },
                "children": [self.chip(c) for c in tree.chips],
            }
        top = [part for part in (identity, chips) if part is not None]
        children: list[Json] = []
        if top:
            children.append({
                "elmType": "div",
                "style": {
                    "display": "flex", "flex-direction": "row", "flex-wrap": "wrap",
                    "justify-content": "space-between", "align-items": "flex-start",
                    "width": "100%", "box-sizing": "border-box",
                },
                "children": top,
            })
        children += [self.row(r) for r in tree.rows]
        if tree.banner is not None:
            children.append(self.banner(tree.banner))
        header: Json = {
            "$schema": _SCHEMA,
            "elmType": "div",
            "attributes": {"class": "ms-borderColor-neutralLight"},
            "style": {
                "display": "flex",
                "flex-direction": "column",
                "width": "100%",
                "box-sizing": "border-box",
                "border-width": "0 0 1px 0",
                "border-style": "solid",
                "padding-bottom": "10px",
                "margin-bottom": "16px",
            },
            "children": children,
        }
        self.size(header)
        return header

    def identity(self, tree: HeaderTree) -> Json | None:
        block = self.title_block(tree)
        tile = self.icon_tile(tree.icon) if tree.icon is not None else None
        kids = [part for part in (tile, block) if part is not None]
        if not kids:
            return None
        return {
            "elmType": "div",
            "style": {
                "display": "flex", "align-items": "flex-start", "min-width": "0",
                "margin-bottom": "6px",
            },
            "children": kids,
        }

    def known_columns(self, tree: HeaderTree) -> None:
        named: list[str] = []
        if tree.title is not None:
            named.append(tree.title.column)
        for part in tree.subtitle:
            named += [part.column] if part.column else list(part.columns)
        named += [c.url_column for c in tree.chips if c.url_column]
        named += [i.column for r in tree.rows for i in r.items if isinstance(i, Bubble)]
        icons = [("banner", tree.banner.icon)] if tree.banner else []
        icons += [("header", tree.icon)] if tree.icon else []
        icons += [("chip", c.icon) for c in tree.chips]
        for where, icon in icons:
            if icon not in FLEET_ICONS:
                raise self.refusal(
                    FindingCode.FORM_HEADER_ICON_UNKNOWN, None,
                    f"the {where} icon {icon!r} is not in the fleet icon vocabulary, and "
                    "SharePoint shows an unknown icon as nothing.",
                )
        for name in named:
            if name not in self.ctx.types:
                raise self.refusal(
                    FindingCode.FORM_HEADER_COLUMN_UNKNOWN, name,
                    f"a header component names {name}, which the entity does not have.",
                )

    def size(self, header: Json) -> None:
        text = json.dumps(header, separators=(",", ":"))
        if len(text) <= FORM_HEADER_MAX_CHARS:
            return
        # Name the calculated column that adds the most characters.
        spent = {c: text.count(json.dumps(t)[1:-1]) * len(t) for c, t in self.units.items()}
        column = max(spent, key=lambda c: spent[c], default=None)
        raise self.refusal(
            FindingCode.FORM_HEADER_TOO_LARGE, column, f"the header {too_large(len(text)).detail}."
        )

    def icon_tile(self, icon: str) -> Json:
        return {
            "elmType": "div",
            "attributes": {"class": TOKENS["neutral"].classes},
            "style": {
                "display": "flex", "align-items": "center", "justify-content": "center",
                "width": "40px", "height": "40px", "border-radius": "8px", "flex": "none",
                "margin-right": "10px", "align-self": "flex-start",
            },
            "children": [{
                "elmType": "div",
                "attributes": {
                    "iconName": icon,
                    "aria-hidden": "true",
                    "class": "ms-fontSize-24 ms-fontColor-themePrimary",
                },
            }],
        }

    def title_block(self, tree: HeaderTree) -> Json | None:
        kids: list[Json] = []
        title = tree.title
        if title is not None:
            v = self.value(title.column)
            blank = self.lit(title.blank, "title blank", title.column)
            lead = ""
            if title.prefix is not None:
                lead = self.lit(title.prefix, "title prefix", title.column) + " + "
            shown = f"=if({v.blank}, {blank}, {lead}{v.code})"
            kids.append({
                "elmType": "div",
                "style": {
                    "display": _display("block", when=self.when(title.when)),
                    "line-height": "24px",
                },
                "attributes": {
                    "class": "ms-fontColor-neutralPrimary ms-fontWeight-bold ms-fontSize-20",
                },
                "txtContent": shown,
            })
        if tree.subtitle:
            kids.append(self.subtitle(tree))
        if not kids:
            return None
        return {
            "elmType": "div",
            "style": {"display": "flex", "flex-direction": "column", "min-width": "0"},
            "children": kids,
        }

    def when(self, when: Condition | None) -> str | None:
        return None if when is None else self.condition(when)

    def subtitle(self, tree: HeaderTree) -> Json:
        shown: list[str] = []  # whether each part shows
        terms: list[str] = []
        only = tree.subtitle[0] if len(tree.subtitle) == 1 else None
        if only and only.text and not only.columns and only.when is None:
            # A lone static sentence is plain text, so it needs no expression.
            text = self.plain(only.text, "subtitle")
            return {
                "elmType": "div",
                "style": {"line-height": "16px"},
                "attributes": {"class": f"{_SECONDARY} ms-fontSize-12"},
                "txtContent": text,
            }
        for part in tree.subtitle:
            if part.column is not None:
                v = self.value(part.column)
                visible, text = v.filled, v.code
            else:
                values = {c: self.value(c) for c in part.columns}
                visible = " && ".join(v.filled for v in values.values()) or "'' == ''"
                wanted = self.when(part.when)
                if wanted is not None:
                    visible = f"{wanted} && {visible}"
                column = part.columns[0] if part.columns else None
                names = "|".join(map(re.escape, values)) or "(?!)"
                chunks = re.split(r"\{(" + names + r")\}", part.text or "")
                text = " + ".join(
                    self.lit(c, 'subtitle', column) if i % 2 == 0 else values[c].code
                    for i, c in enumerate(chunks)
                    if i % 2 or c
                ) or "''"
                if part.fallback is not None:
                    filled = " && ".join(v.filled for v in values.values())
                    text = f"if({filled}, {text}, {self.lit(part.fallback, 'subtitle', column)})"
                    visible = "'' == ''" if wanted is None else wanted
            visible = f"({visible})"
            lead = f"if({_any(shown)}, {quoted(f' {_SEPARATOR} ')}, '') + " if shown else ""
            terms.append(f"if({visible}, {lead}{text}, '')")
            shown.append(visible)
        return {
            "elmType": "div",
            "style": {
                "display": f"=if({_any(shown)}, 'block', 'none')", "line-height": "16px",
            },
            "attributes": {"class": f"{_SECONDARY} ms-fontSize-12"},
            "txtContent": "=" + " + ".join(terms),
        }

    def chip(self, chip: LinkChip) -> Json:
        hidden = None
        if chip.url_column is not None:
            v = self.value(chip.url_column, url=True)
            hidden = v.blank
            # {value} is not escaped: replaceAll in an href blanks the whole form header (measured).
            href = "=" + " + ".join(self.url_pieces(chip, v.code))
        else:
            href = self.plain(chip.url or "", "chip url")
        attributes = {"href": href, "target": "_blank", "rel": "noopener noreferrer"}
        if chip.title is not None:  # a tooltip is a visible word, so only the author's own
            attributes["title"] = self.plain(chip.title, "chip title")
        primary = chip.emphasis == "primary"
        return {
            "elmType": "a",
            "style": {
                "display": _display("inline-flex", when=self.when(chip.when), hidden=hidden),
                "align-items": "center",
                "padding": "6px 12px",
                "border-radius": "4px",
                "border-width": "1px",
                "border-style": "solid",
                **({"border-color": "transparent"} if primary else {}),
                "text-decoration": "none",
                "box-sizing": "border-box",
                "margin": "0 0 6px 8px",
                "white-space": "normal",
                "text-align": "left",
            },
            "attributes": {"class": _PRIMARY if primary else _SECONDARY_BUTTON, **attributes},
            "children": [
                {
                    "elmType": "span",
                    "style": {"margin-right": "6px"},
                    "attributes": {"iconName": chip.icon, "aria-hidden": "true"},
                },
                {"elmType": "span", "txtContent": self.plain(chip.text, "chip")},
            ],
        }

    def row(self, row: Row) -> Json:
        return {
            "elmType": "div",
            "style": {
                "display": _display("flex", when=self.when(row.when)),
                "flex-wrap": "wrap",
                "align-items": "center",
                "width": "100%",
            },
            "children": [
                self.badge(i) if isinstance(i, Badge) else self.bubble(i) for i in row.items
            ],
        }

    def badge(self, badge: Badge) -> Json:
        classes, colour = _pill(badge.token)
        return {
            "elmType": "span",
            "style": {
                "display": _display("inline-block", when=self.when(badge.when)),
                **_PILL,
                **({"color": colour} if colour else {}),
            },
            "attributes": {"class": classes},
            "txtContent": self.plain(badge.text, "badge"),
        }

    def bubble(self, bubble: Bubble) -> Json:
        column = bubble.column
        if bubble.due and self.ctx.types[column] not in DATE_TYPES:
            raise self.refusal(
                FindingCode.FORM_HEADER_DUE_NEEDS_DATE, column,
                f"{column} is marked due but is a {self.ctx.types[column]} column, not a date.",
            )
        if bubble.date_order is not None and not self.is_calculated_date(column):
            raise self.refusal(
                FindingCode.FORM_HEADER_DATE_ORDER_UNUSED, column,
                f"{column} sets date_order but is not a calculated date column.",
            )
        v = self.value(column, bubble.date_order)
        hidden = [
            v.blank,
            *(f"{v.code} == {self.lit(h, 'hide_values', column)}" for h in bubble.hide_values),
        ]
        pairs = [
            (f"{v.code} == {self.lit(k, 'tokens', column)}", t)
            for k, t in bubble.tokens.items()
            if k != "default"
        ]
        fallback = bubble.tokens.get("default", "neutral")
        if bubble.due:
            overdue, guard = self.overdue(column)
            # With a blank text a blank date stays visible, so it must not count as overdue.
            hidden += [f"({v.filled} && {g})" for g in guard] if bubble.blank else guard
            pairs.insert(0, (overdue, "blocked"))
        if bubble.blank is not None:
            hidden = hidden[1:]  # the blank test no longer hides the bubble
            pairs.insert(0, (v.blank, fallback))
        pieces = self.template(bubble.text, v.code, "text", column) if bubble.text else [v.code]
        if bubble.label is not None:
            colon = ": " if bubble.label_colon else ""
            pieces.insert(0, self.lit(f"{bubble.label}{colon}", "label", column))
        if bubble.blank is not None:
            shown = self.lit(bubble.blank, "blank", column)
            pieces = [f"if({v.blank}, {shown}, {' + '.join(pieces)})"]
        classes = {t: _pill(t) for t in {fallback, *(t for _, t in pairs)}}
        style: Json = {
            "display": _display(
                "inline-block",
                when=self.when(bubble.when),
                hidden=_any(hidden) if hidden else None,
            ),
            **_PILL,
        }
        if not pairs:
            css, colour = classes[fallback]
            if colour:
                style["color"] = colour
        else:
            css = "=" + _chain([(c, classes[t][0]) for c, t in pairs], classes[fallback][0])
            # Same branches and order as the class chain, so a neutral branch wins with no colour.
            inks = [(c, classes[t][1]) for c, t in pairs]
            if any(ink for _, ink in inks) or classes[fallback][1]:
                style["color"] = "=" + _chain(inks, classes[fallback][1])
        return {
            "elmType": "span",
            "style": style,
            "attributes": {"class": css},
            "txtContent": "=" + " + ".join(pieces),
        }

    def overdue(self, column: str) -> tuple[str, list[str]]:
        """True from the day after the due date, at the site's local midnight, and when to hide."""
        try:
            rule = zone_rule(self.ctx.zone)
        except FormulaRefusal as error:
            raise self.from_formula(error, column, "the due test") from error
        # Number(@now) as epoch milliseconds is inferred (Learn shows @now + 86400000).
        due, now = f"Number([${column}])", "Number(@now)"
        if self.is_calculated_date(column):  # its day number is already the site's day
            day = self.days[column][0]
            guard = [] if rule.daylight is None else [out_of_span_instant(now, rule)]
            return f"({site_day(now, rule)} > {day})", guard
        # Both days are whole-day arithmetic on the instant, so the browser's zone is never read.
        overdue = f"({site_day(now, rule)} > {site_day(due, rule)})"
        guard = [] if rule.daylight is None else [
            out_of_span_instant(due, rule), out_of_span_instant(now, rule),
        ]
        return overdue, guard

    def steps(self, banner: Banner) -> list[tuple[str, str, BannerRule | NewItemStep]]:
        """Each step's label, its condition and the rule, the new-item step first."""
        found: list[tuple[str, str, BannerRule | NewItemStep]] = []
        if banner.new is not None:
            found.append(("banner new", _IS_NEW, banner.new))
        for number, rule in enumerate(banner.rules, start=1):
            found.append((f"banner rule {number}", self.condition(rule.when), rule))
        return found

    def help_urls(self, steps: list[tuple[str, str, BannerRule | NewItemStep]]) -> list[str]:
        """One URL per step, '' for a step with no link, so the first matching step decides."""
        urls = []
        for label, _, step in steps:
            if step.help is None or self.ctx.help_guides is None:
                urls.append("")
            elif step.help not in self.ctx.help_guides:
                raise self.refusal(
                    FindingCode.FORM_HELP_KEY_UNMAPPED, None,
                    f"{label} help key '{step.help}' is not in DBMLSP_HELP_GUIDES.",
                )
            else:
                urls.append(self.lit(self.ctx.help_guides[step.help], "help url")[1:-1])
        return urls

    def banner(self, banner: Banner) -> Json:
        steps = self.steps(banner)
        rules = [(c, self.lit(s.text, "banner rule")[1:-1]) for _, c, s in steps]
        urls = self.help_urls(steps)
        links = [(c, url) for (c, _), url in zip(rules, urls, strict=True)]
        linked = any(urls)
        action = _chain(rules, "")
        now: list[Json] = [{
            "elmType": "span",
            "style": {"margin-right": "4px"},
            "attributes": {"class": "ms-fontWeight-bold ms-fontColor-neutralPrimary"},
            "txtContent": "To do now:",
        }]
        if linked:
            # The link name reads "<text>, opens ...", so a closing stop would double up.
            spoken = _chain(
                [(c, self.lit(_drop_stop(r.text), "banner rule")[1:-1])
                 for (c, _), (_, _, r) in zip(rules, steps, strict=True)],
                "",
            )
            name = f"={spoken} + {quoted(_HELP_SUFFIX)}"
            shown = _chain([(c, "inline" if u else "none") for c, u in links], "none")
            now.append({
                "elmType": "a",
                "style": {"display": "=" + shown, "text-decoration": "underline"},
                "attributes": {
                    "class": "ms-fontColor-themeDarker ms-fontWeight-semibold",
                    "href": "=" + _chain(links, ""),
                    "target": "_blank",
                    "rel": "noopener noreferrer",
                    "aria-label": name,
                    "title": name,
                },
                "children": [
                    {"elmType": "span", "txtContent": "=" + action},
                    {
                        "elmType": "span",
                        "style": {
                            "margin-left": "4px", "display": "inline-block",
                            "text-decoration": "none",
                        },
                        "attributes": {
                            "iconName": "OpenInNewWindow", "aria-hidden": "true",
                            "class": "ms-fontSize-12",
                        },
                    },
                ],
            })
        plain: Json = {
            "elmType": "span",
            "attributes": {"class": "ms-fontWeight-semibold"},
            "txtContent": "=" + action,
        }
        if linked:
            hidden = _chain([(c, "none" if u else "inline") for c, u in links], "inline")
            plain["style"] = {"display": "=" + hidden}
        now.append(plain)
        lines: list[Json] = [{"elmType": "span", "style": {"min-width": "0"}, "children": now}]
        if any(r.next for _, _, r in steps):
            follows = [
                (c, self.lit(r.next or "", "banner rule next")[1:-1]) for _, c, r in steps
            ]
            visible = _chain([(c, "inline" if t else "none") for c, t in follows], "none")
            lines.append({
                "elmType": "span",
                "style": {"display": "=" + visible, "min-width": "0"},
                "attributes": {"class": f"{_SECONDARY} ms-fontSize-12"},
                "children": [
                    {
                        "elmType": "span",
                        "style": {"margin-right": "4px"},
                        "attributes": {"class": "ms-fontWeight-semibold"},
                        "txtContent": "After that:",
                    },
                    {"elmType": "span", "txtContent": "=" + _chain(follows, "")},
                ],
            })
        return {
            "elmType": "div",
            "style": {
                "display": _display(
                    "flex", when=self.when(banner.when), shown=_any([c for c, _ in rules])
                ),
                "flex-direction": "row",
                "align-items": "flex-start",
                "align-self": "flex-start",
                "max-width": "100%",
                "box-sizing": "border-box",
                "margin-top": "4px",
                "padding": "4px 10px",
                "line-height": "20px",
                "border-width": "1px",
                "border-style": "solid",
                "border-radius": "4px",
            },
            "attributes": {
                "class": "ms-bgColor-themeLighterAlt ms-borderColor-themeLighter "
                "ms-fontColor-themeDarker ms-fontSize-14",
            },
            "children": [
                {
                    "elmType": "span",
                    "style": {"flex": "none", "align-self": "flex-start", "margin": "3px 8px 0 0"},
                    "attributes": {
                        "iconName": banner.icon, "aria-hidden": "true", "class": "ms-fontSize-14",
                    },
                },
                {
                    "elmType": "div",
                    "style": {
                        "display": "flex", "flex-direction": "row", "flex-wrap": "wrap",
                        "align-items": "baseline", "column-gap": "16px", "min-width": "0",
                        "word-wrap": "break-word",
                    },
                    "children": lines,
                },
            ],
        }


_PILL: Json = {
    "border-radius": "12px",
    "padding": "1px 8px",
    "line-height": "18px",
    "border-width": "1px",
    "border-style": "solid",
    "margin": "0 6px 4px 0",
    "box-sizing": "border-box",
}
_DARK = "#323130"  # fixed dark text on the fixed light severity fills, so a dark theme holds
_SEVERITY = frozenset({"good", "low", "warning", "severe", "blocked"})
_TYPE = "ms-fontSize-12 ms-fontWeight-semibold"
_PRIMARY = "ms-bgColor-themePrimary ms-fontColor-white " + _TYPE
_SECONDARY_BUTTON = (
    "ms-bgColor-neutralLighter ms-borderColor-neutralLight ms-fontColor-neutralPrimary " + _TYPE
)


def _pill(name: str) -> tuple[str, str]:
    """A pill's classes and its fixed text colour ('' for a theme-coloured neutral pill)."""
    classes = TOKENS[name].classes
    if name not in _SEVERITY:
        return f"{classes} ms-borderColor-neutralLighter ms-fontColor-neutralPrimary {_TYPE}", ""
    # A white low fill needs a visible edge to read as a pill.
    edge = "neutralTertiary" if name == "low" else "neutralLighter"
    return f"{classes} ms-borderColor-{edge} {_TYPE}", _DARK


def render_header(tree: HeaderTree, ctx: RenderContext) -> Json:
    """The formatter JSON of one header or footer; raises HeaderRefusal naming what it refuses."""
    return _Render(ctx).tree(tree)


def _retitled(bundle: MappingBundle, name: str, entry: EntityMapping) -> bool:
    """A title-derived path is unsafe when a rename keeps the old root folder."""
    return not entry.internal_name and bool(
        entry.renamed_from
        or bundle.mapping.previous_prefixes
        or bundle.mapping.implicit_previous_title(name),
    )


def _context(
    schema: Schema, bundle: MappingBundle, entity: str, zone: str,
    help_guides: Mapping[str, str] | None = None,
) -> RenderContext | None:
    table = next((t for t in schema.tables if t.name == entity), None)
    entry = bundle.mapping.entities.get(entity)
    if table is None or entry is None:
        return None  # an unknown entity is reported where the formatting is checked
    members = {e.name: tuple(e.members) for e in schema.enums}
    types = {
        "Title": "nvarchar",
        **system_column_types_for(entry.kind),
        **{c.name: c.type for c in table.columns},
    }
    # A cross-site reference is expanded into a Choice, not provisioned as a lookup.
    expanded = {c for e, c in bundle.mapping.cross_site_keys() if e == entity}
    types.update(dict.fromkeys(expanded, "nvarchar"))
    return RenderContext(
        entity=entity,
        lookups={
            c.name: is_multi_value(c.type) for c in table.columns
            if c.ref is not None and c.name not in expanded
            and element_type(c.type) not in members
        },
        types=types,
        formulas=bundle.mapping.calculated_formulas.get(entity, {}),
        choices={c.name: members[c.type] for c in table.columns if c.type in members},
        zone=zone,
        list_path=None if _retitled(bundle, entity, entry) else list_folder(
            entry, bundle.mapping.list_title(entity),
        ),
        help_guides=help_guides,
        filled_numbers=frozenset(
            c.name for c in table.columns
            if c.type in NUMBER_TYPES and c.required and c.default is not None
        ),
    )


def resolve_form_headers(
    schema: Schema, bundle: MappingBundle, time_zone: str,
    help: HelpGuides | None = None,  # noqa: A002 -- the documented name
    help_off_warning: bool = True,
) -> tuple[MappingBundle, list[Finding]]:
    """The bundle with each component tree rendered into its entity's header and footer JSON.

    An entity whose part is refused keeps `None` for that part, and the finding says why.
    `help` is None when help links are off: banner `help` keys then render nothing, and one
    warning says so, unless `help_off_warning` is False (the caller cannot see the env settings
    or has already reported why they are unusable).
    """
    findings: list[Finding] = []
    if help is None and help_off_warning and any(
        rule.help is not None
        for trees in bundle.form_trees.values()
        for tree in trees.values()
        if tree.banner is not None
        for rule in (*tree.banner.rules, *([tree.banner.new] if tree.banner.new else []))
    ):
        findings.append(Finding(
            FindingCode.FORM_HELP_OFF,
            f"banner rules carry help keys, but help links are off: set {HELP_BASE_URL_KEY} "
            f"and {HELP_GUIDES_KEY} in the env file to render them.",
            location=Location(Section.FORM_FORMATTING),
        ))
    formatting = dict(bundle.mapping.form_formatting)
    for entity, trees in bundle.form_trees.items():
        ctx = _context(
            schema, bundle, entity, time_zone, None if help is None else help.urls,
        )
        if ctx is None:
            continue
        parts: dict[str, Json | None] = {}
        for part, tree in trees.items():
            try:
                parts[part] = render_header(tree, ctx)
            except HeaderRefusal as refusal:
                findings.append(refusal.finding)
                parts[part] = None
        formatting[entity] = dataclasses.replace(formatting[entity], **parts)
    mapping = dataclasses.replace(bundle.mapping, form_formatting=formatting)
    return dataclasses.replace(bundle, mapping=mapping), findings
