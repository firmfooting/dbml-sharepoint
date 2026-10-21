"""Rendering a header: every element's display, class and text, evaluated over rows."""

import dataclasses
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from _format_eval import date_field, evaluate_expression, evaluate_rows
from _model import bundle, column, enum, schema, table
from _node import NODE

from dbml_sharepoint.analysis import form_header
from dbml_sharepoint.analysis.column_refs import formatter_field_refs
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.form_header import (
    HeaderRefusal,
    RenderContext,
    inline_calculated,
    render_header,
    resolve_form_headers,
)
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import TranslationContext, translate_column
from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.form_tree import (
    Badge,
    Banner,
    BannerRule,
    Bubble,
    HeaderTree,
    LinkChip,
    Row,
    SubtitlePart,
    Title,
)
from dbml_sharepoint.model.mapping_types import FormFormatting, MappingBundle
from dbml_sharepoint.model.parser import Schema

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

SITE = "Australia/Melbourne"
NOW = "2026-10-20T12:00:00Z"
STATUSES = ("Open", "Done", "Late")
SCORE = 'IF([Status]="Open","Hot",IF([Status]="Done","","Cold"))'
TYPES = {
    "Title": "nvarchar",
    "Status": "task_status",
    "Risk": "nvarchar",
    "Notes": "nvarchar",
    "Case": "nvarchar",
    "Due": "date",
    "Seen": "datetime",
    "Score": "calculated_text",
    "Count": "calculated_number",
    "Later": "calculated_date",
    "Owner": "person",
}
FORMULAS = {"Score": SCORE, "Count": "1+1", "Later": "DATE(2026,1,1)"}
OPEN = Leaf("Status", "eq", "Open")


def _ctx(zone: str = SITE) -> RenderContext:
    return RenderContext("Task", TYPES, FORMULAS, {"Status": STATUSES}, zone)


def _render(tree: HeaderTree, zone: str = SITE) -> dict[str, object]:
    return render_header(tree, _ctx(zone))


def _kids(node: object) -> list[dict[str, object]]:
    assert isinstance(node, dict)
    kids = node["children"]
    assert isinstance(kids, list)
    return kids


def _ev(expr: object, row: Mapping[str, object], *, tz: str = "UTC", now: str = NOW) -> object:
    assert isinstance(expr, str)
    if not expr.startswith("="):
        return expr  # a plain string is shown as it is
    return evaluate_expression(expr, row, browser_tz=tz, now=now)


def _style(node: dict[str, object], key: str) -> object:
    style = node["style"]
    assert isinstance(style, dict)
    return style[key]


def _attr(node: dict[str, object], key: str) -> object:
    attributes = node["attributes"]
    assert isinstance(attributes, dict)
    return attributes[key]


def _bubble(item: Bubble, zone: str = SITE) -> dict[str, object]:
    return _kids(_kids(_render(HeaderTree(rows=(Row((item,)),)), zone))[0])[0]


def _text(bubble: dict[str, object]) -> object:
    return _kids(bubble)[0]["txtContent"]


def _shown(bubble: dict[str, object], row: Mapping[str, object]) -> tuple[object, object, object]:
    return (
        _ev(_style(bubble, "display"), row),
        _ev(_attr(bubble, "class"), row),
        _ev(_text(bubble), row),
    )


# --- shape ------------------------------------------------------------------------------------


def test_rendered_header_never_references_a_calculated_column() -> None:
    tree = HeaderTree(
        title=Title("Title", "x", Leaf("Score", "eq", "Hot")),
        chips=(LinkChip("Go", "ContactLink", url_column="Score", url_template="https://e/{value}"),),
        rows=(Row((Bubble("Score", tokens={"Hot": "severe"}),), Leaf("Score", "eq", "Hot")),),
        banner=Banner("L", "Lightbulb", (BannerRule(Leaf("Score", "eq", "Cold"), "t"),)),
    )
    header = _render(tree)
    assert "Score" not in formatter_field_refs(header)
    assert "[$Score" not in json.dumps(header)


def test_no_browser_zone_reader_is_emitted() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Due", due=True),)),))
    text = json.dumps(_render(tree))
    for reader in ("getDate", "getMonth", "getYear", "toLocale", "Date("):
        assert reader not in text


def test_the_wrapper_follows_the_shipped_header_samples() -> None:
    header = _render(HeaderTree(title=Title("Title", "")))
    assert header["elmType"] == "div"
    assert str(header["$schema"]).endswith("column-formatting.schema.json")
    assert _attr(header, "class") == "ms-borderColor-neutralTertiary"


# --- calculated columns ------------------------------------------------------------------------


def test_a_bubble_on_a_calculated_column_equals_the_translation() -> None:
    kinds: dict[str, ColumnKind] = {"Status": "choice"}
    translation = TranslationContext(
        FORMULAS, kinds, {"Score": "text"}, {"Status": STATUSES}, SITE,
    )
    translated = translate_column("Score", translation)
    code = "(" + translated.expression[1:] + ")"
    assert _text(_bubble(Bubble("Score"))) == f"={code}"


def test_blank_calculated_value_hides_the_bubble_with_no_second_condition() -> None:
    bubble = _bubble(Bubble("Score"))
    display = _style(bubble, "display")
    assert isinstance(display, str)
    assert display.endswith(", 'none', 'inline-flex')")
    for status, expected in (("Open", "inline-flex"), ("Done", "none"), ("Late", "inline-flex"),
                             ("", "inline-flex"), ("Other", "inline-flex")):
        assert _ev(display, {"Status": status}) == expected, status


def test_a_calculated_column_in_a_when_is_inlined() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Notes"),), Leaf("Score", "eq", "Hot")),))
    row = _kids(_render(tree))[0]
    assert "[$Score" not in json.dumps(row)
    display = _style(row, "display")
    assert _ev(display, {"Status": "Open"}) == "flex"
    assert _ev(display, {"Status": "Late"}) == "none"
    assert _ev(display, {"Status": "Done"}) == "none"


def test_inline_calculated_skips_quoted_text() -> None:
    assert inline_calculated("[$Calc] == '[$Calc] it''s [$Calc]'", {"Calc": "(x)"}) == (
        "(x) == '[$Calc] it''s [$Calc]'"
    )
    assert inline_calculated("[$Other] == [$Calc]", {"Calc": "(x)"}) == "[$Other] == (x)"


def test_a_calculated_number_is_refused_naming_the_column() -> None:
    with pytest.raises(HeaderRefusal) as number:
        _bubble(Bubble("Count"))
    assert number.value.finding.code is FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED
    assert "Task.Count" in number.value.finding.message


# --- title and subtitle -------------------------------------------------------------------------


def test_title_shows_the_column_or_the_blank_text() -> None:
    title = _kids(_kids(_render(HeaderTree(title=Title("Title", "Nothing yet"))))[0])[0]
    assert _ev(title["txtContent"], {"Title": "Alpha"}) == "Alpha"
    assert _ev(title["txtContent"], {"Title": ""}) == "Nothing yet"
    assert _style(title, "display") == "block"


def test_a_false_title_when_hides_the_title() -> None:
    title = _kids(_kids(_render(HeaderTree(title=Title("Title", "", OPEN))))[0])[0]
    assert _ev(_style(title, "display"), {"Status": "Open"}) == "block"
    assert _ev(_style(title, "display"), {"Status": "Done"}) == "none"


def test_subtitle_parts_join_with_a_dot_only_between_shown_parts() -> None:
    tree = HeaderTree(subtitle=(
        SubtitlePart(column="Risk"),
        SubtitlePart(text="Case {Case} / {Notes}", columns=("Case",), when=OPEN),
        SubtitlePart(text="Seen {Seen}", columns=("Seen",)),
    ))
    node = _kids(_kids(_render(tree))[0])[0]
    dot = " · "
    seen = date_field(1_000_000_000_000)
    base = {
        "Status": "Open", "Risk": "", "Case": "", "Seen": date_field(None), "Seen.displayValue": "",
    }
    assert _ev(node["txtContent"], base) == ""
    assert _ev(_style(node, "display"), base) == "none"
    row = {**base, "Risk": "High", "Case": "C1"}
    assert _ev(node["txtContent"], row) == f"High{dot}Case C1 / {{Notes}}"
    assert _ev(node["txtContent"], {**row, "Status": "Done"}) == "High"
    only_case = {**base, "Case": "C1"}
    assert _ev(node["txtContent"], only_case) == "Case C1 / {Notes}"
    everything = {**row, "Seen": seen, "Seen.displayValue": "21/10/2026"}
    assert _ev(node["txtContent"], everything) == (
        f"High{dot}Case C1 / {{Notes}}{dot}Seen 21/10/2026"
    )
    assert _ev(_style(node, "display"), everything) == "block"


# --- chips --------------------------------------------------------------------------------------


def test_a_column_chip_is_hidden_while_its_column_is_blank() -> None:
    chip = _kids(_kids(_render(HeaderTree(chips=(
        LinkChip("Open case", "ContactLink", url_column="Case", url_template="https://e/x?id={value}"),
        LinkChip("Help", "Feedback", url="https://e/help"),
    ))))[0])
    assert _ev(_style(chip[0], "display"), {"Case": ""}) == "none"
    assert _ev(_style(chip[0], "display"), {"Case": "7"}) == "inline-flex"
    assert _ev(_attr(chip[0], "href"), {"Case": "7"}) == "https://e/x?id=7"
    assert _attr(chip[1], "href") == "https://e/help"
    assert _style(chip[1], "display") == "inline-flex"
    assert _kids(chip[0])[1]["txtContent"] == "Open case"
    assert _attr(_kids(chip[0])[0], "iconName") == "ContactLink"


def test_a_chip_when_hides_it() -> None:
    tree = HeaderTree(chips=(LinkChip("Help", "Feedback", url="u", when=OPEN),))
    chip = _kids(_kids(_render(tree))[0])[0]
    assert _ev(_style(chip, "display"), {"Status": "Open"}) == "inline-flex"
    assert _ev(_style(chip, "display"), {"Status": "Done"}) == "none"


# --- rows and bubbles -------------------------------------------------------------------------


def test_a_row_when_hides_the_whole_row() -> None:
    row = _kids(_render(HeaderTree(rows=(Row((Bubble("Risk"),), OPEN),))))[0]
    assert _ev(_style(row, "display"), {"Status": "Open"}) == "flex"
    assert _ev(_style(row, "display"), {"Status": "Late"}) == "none"


def test_a_bubble_is_hidden_while_blank_and_for_hide_values() -> None:
    bubble = _bubble(Bubble("Risk", hide_values=("None", "N/A")))
    assert _shown(bubble, {"Risk": ""})[0] == "none"
    assert _shown(bubble, {"Risk": "None"})[0] == "none"
    assert _shown(bubble, {"Risk": "N/A"})[0] == "none"
    assert _shown(bubble, {"Risk": "High"}) == (
        "inline-flex", f"{TOKENS['neutral'].classes} ms-fontColor-neutralSecondary", "High",
    )


def test_tokens_map_values_and_a_default_takes_the_rest() -> None:
    bubble = _bubble(Bubble("Risk", tokens={"High": "severe", "Low": "good", "default": "muted"}))
    suffix = " ms-fontColor-neutralSecondary"
    assert _shown(bubble, {"Risk": "High"})[1] == TOKENS["severe"].classes + suffix
    assert _shown(bubble, {"Risk": "Low"})[1] == TOKENS["good"].classes + suffix
    assert _shown(bubble, {"Risk": "Other"})[1] == TOKENS["muted"].classes + suffix
    # No `default` key gives the neutral token.
    plain = _bubble(Bubble("Risk", tokens={"High": "severe"}))
    assert _shown(plain, {"Risk": "Other"})[1] == TOKENS["neutral"].classes + suffix


def test_label_and_text_template_wrap_the_value() -> None:
    bubble = _bubble(Bubble("Risk", label="Rating", text="{value} risk"))
    assert _shown(bubble, {"Risk": "High"})[2] == "Rating: High risk"
    both = _bubble(Bubble("Risk", text="<{value}|{value}>"))
    assert _shown(both, {"Risk": "A"})[2] == "<A|A>"


def test_a_bubble_when_hides_it() -> None:
    bubble = _bubble(Bubble("Risk", when=OPEN))
    assert _shown(bubble, {"Status": "Open", "Risk": "x"})[0] == "inline-flex"
    assert _shown(bubble, {"Status": "Late", "Risk": "x"})[0] == "none"


def test_a_stored_date_shows_its_display_value() -> None:
    bubble = _bubble(Bubble("Due"))
    shown = {"Due": date_field(1_800_000_000_000), "Due.displayValue": "5/3/2026"}
    assert _shown(bubble, shown)[0::2] == ("inline-flex", "5/3/2026")
    blank = {"Due": date_field(None), "Due.displayValue": ""}
    assert _shown(bubble, blank)[0] == "none"


def test_badge_is_fixed_text_with_a_token_and_a_when() -> None:
    node = _kids(_kids(_render(HeaderTree(rows=(
        Row((Badge("No assessment", "warning", OPEN),)),
    ))))[0])[0]
    assert _kids(node)[0]["txtContent"] == "No assessment"
    assert _attr(node, "class") == f"{TOKENS['warning'].classes} ms-fontColor-neutralSecondary"
    assert _ev(_style(node, "display"), {"Status": "Open"}) == "inline-flex"
    assert _ev(_style(node, "display"), {"Status": "Done"}) == "none"


# --- the due bubble ------------------------------------------------------------------------------


def _local(zone: str, day: str, clock: str) -> datetime:
    naive = datetime.fromisoformat(f"{day}T{clock}")
    return naive.replace(tzinfo=ZoneInfo(zone)).astimezone(UTC)


def _ms(instant: datetime) -> int:
    return int(instant.timestamp() * 1000)


def _iso(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# The days either side of both daylight changes of each site zone in 2026, and an ordinary day.
DUE_DAYS = {
    SITE: ("2026-03-05", "2026-04-03", "2026-04-04", "2026-04-05", "2026-10-02", "2026-10-03",
           "2026-10-04"),
    "America/Los_Angeles": ("2026-03-06", "2026-03-07", "2026-03-08", "2026-10-31", "2026-11-01"),
}
BROWSERS = ("Australia/Melbourne", "UTC", "America/Los_Angeles")


@pytest.mark.parametrize("zone", DUE_DAYS)
def test_the_due_bubble_turns_blocked_from_the_day_after_the_due_date(zone: str) -> None:
    bubble = _bubble(Bubble("Due", due=True, tokens={"default": "good"}), zone)
    rows = []
    dues = []
    for day in DUE_DAYS[zone]:
        for clock in ("00:00:00", "12:00:00", "23:59:59"):
            instant = _local(zone, day, clock)
            rows.append({"Due": date_field(_ms(instant)), "Due.displayValue": day})
            dues.append(day)
    for day in DUE_DAYS[zone]:
        after = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
        midnight = _local(zone, after, "00:00:00")
        for now in (midnight - timedelta(seconds=1), midnight, midnight + timedelta(seconds=1)):
            site_today = now.astimezone(ZoneInfo(zone)).date().isoformat()
            for browser in BROWSERS:
                classes = evaluate_rows(
                    str(_attr(bubble, "class")), rows, browser_tz=browser, now=_iso(now)
                )
                for due, got in zip(dues, classes, strict=True):
                    expected = site_today > due
                    assert (TOKENS["blocked"].classes in str(got)) is expected, (
                        zone, browser, now, due,
                    )


def test_the_due_bubble_hides_a_blank_date_and_keeps_its_normal_token() -> None:
    bubble = _bubble(Bubble("Due", due=True, tokens={"default": "good"}))
    blank = {"Due": date_field(None), "Due.displayValue": ""}
    assert _shown(bubble, blank)[0] == "none"
    later = date_field(_ms(_local(SITE, "2026-12-31", "00:00:00")))
    early = {"Due": later, "Due.displayValue": "x"}
    assert _shown(bubble, early)[1] == f"{TOKENS['good'].classes} ms-fontColor-neutralSecondary"


def test_due_on_a_text_column_is_refused() -> None:
    with pytest.raises(HeaderRefusal) as found:
        _bubble(Bubble("Risk", due=True))
    assert found.value.finding.code is FindingCode.FORM_HEADER_DUE_NEEDS_DATE
    assert "Task.Risk" in found.value.finding.message


def test_a_zone_the_expressions_cannot_encode_refuses_the_due_test() -> None:
    with pytest.raises(HeaderRefusal) as found:
        _bubble(Bubble("Due", due=True), "Asia/Tehran")
    assert found.value.finding.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


# --- the banner ---------------------------------------------------------------------------------


def test_banner_shows_the_first_matching_rule_and_hides_with_none() -> None:
    banner = _kids(_render(HeaderTree(banner=Banner(
        "Next:", "Lightbulb",
        (
            BannerRule(Leaf("Risk", "eq", "High"), "first"),
            BannerRule(Leaf("Status", "eq", "Open"), "second"),
            BannerRule(Leaf("Score", "eq", "Cold"), "third"),
        ),
        when=Leaf("Notes", "is_null"),
    ))))[0]
    text = _kids(banner)[2]["txtContent"]
    for row, shown, said in (
        ({"Risk": "High", "Status": "Open"}, "flex", "first"),
        ({"Risk": "Low", "Status": "Open"}, "flex", "second"),
        ({"Risk": "Low", "Status": "Late"}, "flex", "third"),
        ({"Risk": "Low", "Status": "Done"}, "none", ""),
        ({"Risk": "High", "Status": "Open", "Notes": "x"}, "none", "first"),
    ):
        full = {"Notes": "", **row}
        assert _ev(_style(banner, "display"), full) == shown, full
        assert _ev(text, full) == said, full
    assert _kids(banner)[1]["txtContent"] == "Next:"
    assert _attr(_kids(banner)[0], "iconName") == "Lightbulb"


# --- text kept verbatim ------------------------------------------------------------------------


def test_braces_percent_and_double_quotes_render_as_written() -> None:
    # Nothing in the formatting reference gives these a meaning inside a single-quoted literal or
    # a plain string; the evaluator only shows the expressions pass them through unchanged.
    odd = 'Is {raw} 100% "q"'
    tree = HeaderTree(
        title=Title("Title", odd),
        subtitle=(SubtitlePart(text=f"{odd} {{Case}}", columns=("Case",)),),
        chips=(LinkChip(odd, "ContactLink", url_column="Case", url_template="https://e/?q={value}&p=100%"),),
        rows=(Row((
            Bubble("Risk", label=odd, text=f"{odd}{{value}}", hide_values=(odd,),
                   tokens={odd: "severe", "default": "good"}),
            Badge(odd, "muted"),
        )),),
        banner=Banner(odd, "Lightbulb", (BannerRule(Leaf("Risk", "eq", "x"), odd),)),
    )
    title_block, chips, row, banner = _kids(_render(tree))
    assert _ev(_kids(title_block)[0]["txtContent"], {"Title": ""}) == odd
    assert _ev(_kids(title_block)[1]["txtContent"], {"Case": "7"}) == f"{odd} 7"
    assert _kids(_kids(chips)[0])[1]["txtContent"] == odd
    assert _ev(_attr(_kids(chips)[0], "href"), {"Case": "7"}) == "https://e/?q=7&p=100%"
    bubble, badge = _kids(row)
    assert _ev(_text(bubble), {"Risk": "v"}) == f"{odd}: {odd}v"
    assert _ev(_style(bubble, "display"), {"Risk": odd}) == "none"
    assert str(_ev(_attr(bubble, "class"), {"Risk": odd})).startswith(TOKENS["severe"].classes)
    assert _kids(badge)[0]["txtContent"] == odd
    assert _ev(_kids(banner)[2]["txtContent"], {"Risk": "x"}) == odd
    assert _kids(banner)[1]["txtContent"] == odd


QUOTE_SITES: dict[str, Callable[[str], HeaderTree]] = {
    "title blank": lambda t: HeaderTree(title=Title("Title", t)),
    "subtitle": lambda t: HeaderTree(subtitle=(SubtitlePart(text=t, columns=("Case",)),)),
    "chip url": lambda t: HeaderTree(chips=(
        LinkChip("a", "Feedback", url_column="Case", url_template=t + "{value}"),
    )),
    "label": lambda t: HeaderTree(rows=(Row((Bubble("Risk", label=t),)),)),
    "text": lambda t: HeaderTree(rows=(Row((Bubble("Risk", text=t + "{value}"),)),)),
    "hide_values": lambda t: HeaderTree(rows=(Row((Bubble("Risk", hide_values=(t,)),)),)),
    "tokens": lambda t: HeaderTree(rows=(Row((Bubble("Risk", tokens={t: "good"}),)),)),
    "banner rule": lambda t: HeaderTree(banner=Banner(
        "L", "Lightbulb", (BannerRule(Leaf("Risk", "eq", "x"), t),),
    )),
    "starts like a formula": lambda t: HeaderTree(chips=(LinkChip("=" + t, "Feedback", url="u"),)),
}


@pytest.mark.parametrize("site", QUOTE_SITES)
def test_a_single_quote_inside_an_expression_is_refused(site: str) -> None:
    with pytest.raises(HeaderRefusal) as found:
        _render(QUOTE_SITES[site]("It's"))
    assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED
    assert "It's" in found.value.finding.message


QUOTED = Leaf("Risk", "eq", "O'x")
WHEN_SITES: dict[str, HeaderTree] = {
    "title when": HeaderTree(title=Title("Title", "b", when=QUOTED)),
    "subtitle when": HeaderTree(
        subtitle=(SubtitlePart(text="{Case}", columns=("Case",), when=QUOTED),)
    ),
    "chip when": HeaderTree(chips=(LinkChip("a", "Feedback", url="u", when=QUOTED),)),
    "row when": HeaderTree(rows=(Row((Bubble("Risk"),), QUOTED),)),
    "badge when": HeaderTree(rows=(Row((Badge("a", "muted", when=QUOTED),)),)),
    "bubble when": HeaderTree(rows=(Row((Bubble("Risk", when=QUOTED),)),)),
    "banner when": HeaderTree(
        banner=Banner("L", "Lightbulb", (BannerRule(OPEN, "t"),), when=QUOTED)
    ),
    "banner rule when": HeaderTree(banner=Banner("L", "Lightbulb", (BannerRule(QUOTED, "t"),))),
}


@pytest.mark.parametrize("site", [*QUOTE_SITES, *WHEN_SITES])
def test_a_single_quote_in_any_header_expression_is_refused_through_resolve(site: str) -> None:
    tree = WHEN_SITES[site] if site in WHEN_SITES else QUOTE_SITES[site]("It's")
    schema_, base = _bundle(tree)
    resolved, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HEADER_TEXT_UNSUPPORTED]
    assert "no escape" in findings[0].message
    assert resolved.mapping.form_formatting["Task"].header is None


def test_a_single_quote_in_plain_static_text_is_kept() -> None:
    chip = _kids(_kids(_render(HeaderTree(chips=(LinkChip("It's", "Feedback", url="u"),))))[0])[0]
    assert _kids(chip)[1]["txtContent"] == "It's"


@pytest.mark.parametrize("marker", ["[$Case]", "a@b.example", "@now"])
def test_static_text_with_an_embedded_special_marker_is_refused(marker: str) -> None:
    sites = (
        HeaderTree(chips=(LinkChip(marker, "Feedback", url="u"),)),
        HeaderTree(chips=(LinkChip("a", "Feedback", url=marker),)),
        HeaderTree(rows=(Row((Badge(marker, "muted"),)),)),
        HeaderTree(banner=Banner(marker, "Lightbulb", (BannerRule(OPEN, "t"),))),
    )
    for tree in sites:
        with pytest.raises(HeaderRefusal) as found:
            _render(tree)
        assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED


def test_text_that_looks_like_a_special_value_is_quoted_not_evaluated() -> None:
    header = _render(HeaderTree(rows=(Row((Badge("=1+1", "muted"),)),)))
    badge = _kids(_kids(header)[0])[0]
    assert _ev(_kids(badge)[0]["txtContent"], {}) == "=1+1"


# --- size, refusals and resolution --------------------------------------------------------


def test_header_over_budget_is_refused_naming_the_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form_header, "FORM_HEADER_MAX_CHARS", 400)
    with pytest.raises(HeaderRefusal) as found:
        _render(HeaderTree(rows=(Row((Bubble("Score", tokens={"Hot": "severe"}),)),)))
    assert found.value.finding.code is FindingCode.FORM_HEADER_TOO_LARGE
    assert "Task.Score" in found.value.finding.message


def test_an_icon_outside_the_fleet_vocabulary_is_refused_through_resolve() -> None:
    for tree in (
        HeaderTree(chips=(LinkChip("Go", "Calendar", url="u"),)),
        HeaderTree(banner=Banner("L", "Calendar", (BannerRule(OPEN, "t"),))),
    ):
        schema_, base = _bundle(tree)
        resolved, findings = resolve_form_headers(schema_, base, SITE)
        assert [f.code for f in findings] == [FindingCode.FORM_HEADER_ICON_UNKNOWN]
        assert "'Calendar'" in findings[0].message
        assert resolved.mapping.form_formatting["Task"].header is None


def test_an_oversize_header_with_no_calculated_column_says_the_header() -> None:
    schema_, base = _bundle(HeaderTree(title=Title("Title", "x" * 600)))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(form_header, "FORM_HEADER_MAX_CHARS", 400)
        _, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HEADER_TOO_LARGE]
    assert "the header" in findings[0].message
    assert "None" not in findings[0].message


def _bundle(tree: HeaderTree) -> tuple[Schema, MappingBundle]:
    task = table(
        "Task",
        column("Status", "task_status"), column("Risk"), column("Case"), column("Due", "date"),
        column("Score", "calculated_text"),
    )
    base = bundle(
        entities=["Task"],
        calculated_formulas={"Task": {"Score": SCORE}},
        form_formatting={"Task": FormFormatting()},
    )
    base = dataclasses.replace(base, form_trees={"Task": {"header": tree}})
    return schema(task, enums=[enum("task_status", *STATUSES)]), base


def test_resolve_sets_the_header_and_leaves_the_rest() -> None:
    schema_, base = _bundle(HeaderTree(rows=(Row((Bubble("Score"),)),)))
    resolved, findings = resolve_form_headers(schema_, base, SITE)
    assert findings == []
    formatting = resolved.mapping.form_formatting["Task"]
    assert formatting.header is not None
    assert formatting.footer is None
    assert base.mapping.form_formatting["Task"].header is None


def test_resolve_leaves_a_refused_header_none_and_says_why() -> None:
    cases = (
        (Bubble("Risk", due=True), FindingCode.FORM_HEADER_DUE_NEEDS_DATE),
        (Bubble("Nope"), FindingCode.FORM_HEADER_COLUMN_UNKNOWN),
    )
    for item, code in cases:
        schema_, base = _bundle(HeaderTree(rows=(Row((item,)),)))
        resolved, findings = resolve_form_headers(schema_, base, SITE)
        assert [f.code for f in findings] == [code]
        assert resolved.mapping.form_formatting["Task"].header is None


def test_resolve_reports_an_oversize_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form_header, "FORM_HEADER_MAX_CHARS", 400)
    schema_, base = _bundle(HeaderTree(rows=(Row((Bubble("Score", tokens={"Hot": "good"}),)),)))
    resolved, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HEADER_TOO_LARGE]
    assert resolved.mapping.form_formatting["Task"].header is None


def test_a_condition_the_renderer_refuses_becomes_its_existing_finding() -> None:
    schema_, base = _bundle(HeaderTree(rows=(Row((Bubble("Risk"),), Leaf("Ghost", "eq", "x")),)))
    _, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.CONDITION_COLUMN_TYPE_UNKNOWN]


def test_a_blank_date_test_in_a_when_uses_its_text() -> None:
    row = _kids(_render(HeaderTree(rows=(Row((Bubble("Risk"),), Leaf("Due", "is_null")),))))[0]
    display = _style(row, "display")
    assert _ev(display, {"Due": date_field(None)}) == "flex"
    assert _ev(display, {"Due": date_field(1_800_000_000_000)}) == "none"


def test_a_person_column_is_refused_by_name() -> None:
    with pytest.raises(HeaderRefusal) as found:
        _bubble(Bubble("Owner"))
    assert found.value.finding.code is FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
    assert re.search(r"Task\.Owner", found.value.finding.message)
