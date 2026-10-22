"""Rendering a header: every element's display, class and text, evaluated over rows."""

import dataclasses
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
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
from dbml_sharepoint.model.help_guides import HelpGuides
from dbml_sharepoint.model.mapping_types import FormFormatting, MappingBundle
from dbml_sharepoint.model.parser import Column, Schema

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

SITE = "Australia/Melbourne"
NOW = "2026-10-20T12:00:00Z"
TYPE = "ms-fontSize-12 ms-fontWeight-semibold"
NEUTRAL = (
    f"{TOKENS['neutral'].classes} ms-borderColor-neutralLighter ms-fontColor-neutralPrimary {TYPE}"
)
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


def _parts(tree: HeaderTree) -> list[dict[str, object]]:
    """The title and subtitle nodes: the text block inside row one's identity."""
    identity = _kids(_kids(_render(tree))[0])[0]
    return _kids(_kids(identity)[-1])


def _chip_nodes(rendered: dict[str, object]) -> list[dict[str, object]]:
    return _kids(_kids(_kids(rendered)[0])[-1])


def _attrs(node: dict[str, object]) -> dict[str, object]:
    attributes = node["attributes"]
    assert isinstance(attributes, dict)
    return attributes


def _now(banner: dict[str, object]) -> list[dict[str, object]]:
    """The label, the link when the rules map one, and the plain action of a step box."""
    return _kids(_kids(_kids(banner)[1])[0])


def _action(banner: dict[str, object]) -> dict[str, object]:
    return _now(banner)[-1]


def _bubble(item: Bubble, zone: str = SITE) -> dict[str, object]:
    return _kids(_kids(_render(HeaderTree(rows=(Row((item,)),)), zone))[0])[0]


def _text(bubble: dict[str, object]) -> object:
    return bubble["txtContent"]


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
        banner=Banner(icon="Lightbulb", rules=(BannerRule(Leaf("Score", "eq", "Cold"), "t"),)),
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
    assert _attr(header, "class") == "ms-borderColor-neutralLight"


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
    assert display.endswith(", 'none', 'inline-block')")
    for status, expected in (("Open", "inline-block"), ("Done", "none"), ("Late", "inline-block"),
                             ("", "inline-block"), ("Other", "inline-block")):
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
    title = _parts(HeaderTree(title=Title("Title", "Nothing yet")))[0]
    assert _ev(title["txtContent"], {"Title": "Alpha"}) == "Alpha"
    assert _ev(title["txtContent"], {"Title": ""}) == "Nothing yet"
    assert _style(title, "display") == "block"


def test_a_false_title_when_hides_the_title() -> None:
    title = _parts(HeaderTree(title=Title("Title", "", OPEN)))[0]
    assert _ev(_style(title, "display"), {"Status": "Open"}) == "block"
    assert _ev(_style(title, "display"), {"Status": "Done"}) == "none"


def test_subtitle_parts_join_with_a_dot_only_between_shown_parts() -> None:
    tree = HeaderTree(subtitle=(
        SubtitlePart(column="Risk"),
        SubtitlePart(text="Case {Case} / {Notes}", columns=("Case",), when=OPEN),
        SubtitlePart(text="Seen {Seen}", columns=("Seen",)),
    ))
    node = _parts(tree)[0]
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
    chip = _chip_nodes(_render(HeaderTree(chips=(
        LinkChip("Open case", "ContactLink", url_column="Case", url_template="https://e/x?id={value}"),
        LinkChip("Help", "Feedback", url="https://e/help"),
    ))))
    assert _ev(_style(chip[0], "display"), {"Case": ""}) == "none"
    assert _ev(_style(chip[0], "display"), {"Case": "7"}) == "inline-flex"
    assert _ev(_attr(chip[0], "href"), {"Case": "7"}) == "https://e/x?id=7"
    assert _attr(chip[1], "href") == "https://e/help"
    assert _style(chip[1], "display") == "inline-flex"
    assert _kids(chip[0])[1]["txtContent"] == "Open case"
    assert _attr(_kids(chip[0])[0], "iconName") == "ContactLink"


def test_a_lookup_url_column_shows_the_text_after_the_raw_id_and_hides_when_blank() -> None:
    ctx = dataclasses.replace(_ctx(), types={**TYPES, "Meeting": "int"}, lookups={"Meeting": False})
    link = LinkChip("Records", "ContactLink", url_column="Meeting", url_template="https://e/?v={value}")
    chip = _chip_nodes(render_header(HeaderTree(chips=(link,)), ctx))[0]
    # Measured on a list form: the raw value is "<id>;#<text>", and exactly '' when blank.
    assert _attr(chip, "href") == (
        "='https://e/?v=' + substring(toString([$Meeting]), "
        "indexOf(toString([$Meeting]), ';#') + 2, 300)"
    )
    assert _style(chip, "display") == "=if(toString([$Meeting]) == '', 'none', 'inline-flex')"
    assert _ev(_style(chip, "display"), {"Meeting": ""}) == "none"
    assert _ev(_style(chip, "display"), {"Meeting": "1;#Board, May"}) == "inline-flex"
    assert _ev(_attr(chip, "href"), {"Meeting": "1;#Board, May"}) == "https://e/?v=Board, May"


def test_a_multi_lookup_url_column_is_refused() -> None:
    ctx = dataclasses.replace(_ctx(), types={**TYPES, "Meeting": "int"}, lookups={"Meeting": True})
    chip = LinkChip("R", "ContactLink", url_column="Meeting", url_template="{value}")
    tree = HeaderTree(chips=(chip,))
    with pytest.raises(HeaderRefusal, match="multi-value lookup"):
        render_header(tree, ctx)


def test_the_chip_is_roomy() -> None:
    chip = _chip_nodes(_render(HeaderTree(chips=(LinkChip("Help", "Feedback", url="u"),))))[0]
    assert _style(chip, "padding") == "6px 12px"
    assert _style(chip, "margin") == "0 0 6px 8px"


def test_a_chip_when_hides_it() -> None:
    tree = HeaderTree(chips=(LinkChip("Help", "Feedback", url="u", when=OPEN),))
    chip = _chip_nodes(_render(tree))[0]
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
        "inline-block", NEUTRAL, "High",
    )


def test_tokens_map_values_and_a_default_takes_the_rest() -> None:
    bubble = _bubble(Bubble("Risk", tokens={"High": "severe", "Low": "good", "default": "muted"}))
    assert _shown(bubble, {"Risk": "High"})[1] == form_header._pill("severe")[0]
    assert _shown(bubble, {"Risk": "Low"})[1] == form_header._pill("good")[0]
    assert _shown(bubble, {"Risk": "Other"})[1] == form_header._pill("muted")[0]
    # No `default` key gives the neutral token.
    plain = _bubble(Bubble("Risk", tokens={"High": "severe"}))
    assert _shown(plain, {"Risk": "Other"})[1] == NEUTRAL


def test_label_and_text_template_wrap_the_value() -> None:
    bubble = _bubble(Bubble("Risk", label="Rating", text="{value} risk"))
    assert _shown(bubble, {"Risk": "High"})[2] == "Rating: High risk"
    both = _bubble(Bubble("Risk", text="<{value}|{value}>"))
    assert _shown(both, {"Risk": "A"})[2] == "<A|A>"


def test_a_bubble_when_hides_it() -> None:
    bubble = _bubble(Bubble("Risk", when=OPEN))
    assert _shown(bubble, {"Status": "Open", "Risk": "x"})[0] == "inline-block"
    assert _shown(bubble, {"Status": "Late", "Risk": "x"})[0] == "none"


def test_a_stored_date_shows_its_display_value() -> None:
    bubble = _bubble(Bubble("Due"))
    shown = {"Due": date_field(1_800_000_000_000), "Due.displayValue": "5/3/2026"}
    assert _shown(bubble, shown)[0::2] == ("inline-block", "5/3/2026")
    blank = {"Due": date_field(None), "Due.displayValue": ""}
    assert _shown(bubble, blank)[0] == "none"


def test_badge_is_fixed_text_with_a_token_and_a_when() -> None:
    node = _kids(_kids(_render(HeaderTree(rows=(
        Row((Badge("No assessment", "warning", OPEN),)),
    ))))[0])[0]
    assert node["txtContent"] == "No assessment"
    assert _attr(node, "class") == (
        f"{TOKENS['warning'].classes} ms-borderColor-neutralLighter {TYPE}"
    )
    assert _ev(_style(node, "display"), {"Status": "Open"}) == "inline-block"
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
    assert _shown(bubble, early)[1] == form_header._pill("good")[0]


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
        icon="Lightbulb",
        rules=(
            BannerRule(Leaf("Risk", "eq", "High"), "first"),
            BannerRule(Leaf("Status", "eq", "Open"), "second"),
            BannerRule(Leaf("Score", "eq", "Cold"), "third"),
        ),
        when=Leaf("Notes", "is_null"),
    ))))[0]
    text = _action(banner)["txtContent"]
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
    assert _attr(_kids(banner)[0], "iconName") == "Lightbulb"


# --- text kept verbatim ------------------------------------------------------------------------


def test_braces_percent_and_double_quotes_render_as_written() -> None:
    # Nothing in the formatting reference gives these a meaning inside a single-quoted literal or
    # a plain string; the evaluator only shows the expressions pass them through unchanged.
    odd = 'Is {raw} 100% "q"'
    tree = HeaderTree(
        icon="Shield", title=Title("Title", odd),
        subtitle=(SubtitlePart(text=f"{odd} {{Case}}", columns=("Case",)),),
        chips=(LinkChip(odd, "ContactLink", url_column="Case", url_template="https://e/?q={value}&p=100%"),),
        rows=(Row((
            Bubble("Risk", label=odd, text=f"{odd}{{value}}", hide_values=(odd,),
                   tokens={odd: "severe", "default": "good"}),
            Badge(odd, "muted"),
        )),),
        banner=Banner(icon="Lightbulb", rules=(BannerRule(Leaf("Risk", "eq", "x"), odd),)),
    )
    top, row, banner = _kids(_render(tree))
    identity, actions = _kids(top)
    title, subtitle = _kids(_kids(identity)[-1])
    assert _ev(title["txtContent"], {"Title": ""}) == odd
    assert _ev(subtitle["txtContent"], {"Case": "7"}) == f"{odd} 7"
    chip = _kids(actions)[0]
    assert _kids(chip)[1]["txtContent"] == odd
    assert _ev(_attr(chip, "href"), {"Case": "7"}) == "https://e/?q=7&p=100%"
    bubble, badge = _kids(row)
    assert _ev(_text(bubble), {"Risk": "v"}) == f"{odd}: {odd}v"
    assert _ev(_style(bubble, "display"), {"Risk": odd}) == "none"
    assert str(_ev(_attr(bubble, "class"), {"Risk": odd})).startswith(TOKENS["severe"].classes)
    assert badge["txtContent"] == odd
    assert _ev(_action(banner)["txtContent"], {"Risk": "x"}) == odd


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
        icon="Lightbulb", rules=(BannerRule(Leaf("Risk", "eq", "x"), t),),
    )),
    "banner next": lambda t: HeaderTree(banner=Banner(
        icon="Lightbulb", rules=(BannerRule(OPEN, "ok", None, t),),
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
        banner=Banner(icon="Lightbulb", rules=(BannerRule(OPEN, "t"),), when=QUOTED)
    ),
    "banner rule when": HeaderTree(
        banner=Banner(icon="Lightbulb", rules=(BannerRule(QUOTED, "t"),)),
    ),
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
    chip = _chip_nodes(_render(HeaderTree(chips=(LinkChip("It's", "Feedback", url="u"),))))[0]
    assert _kids(chip)[1]["txtContent"] == "It's"


@pytest.mark.parametrize("marker", ["[$Case]", "a@b.example", "@now"])
def test_static_text_with_an_embedded_special_marker_is_refused(marker: str) -> None:
    sites = (
        HeaderTree(chips=(LinkChip(marker, "Feedback", url="u"),)),
        HeaderTree(chips=(LinkChip("a", "Feedback", url=marker),)),
        HeaderTree(rows=(Row((Badge(marker, "muted"),)),)),
    )
    for tree in sites:
        with pytest.raises(HeaderRefusal) as found:
            _render(tree)
        assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED


def test_text_that_looks_like_a_special_value_is_quoted_not_evaluated() -> None:
    header = _render(HeaderTree(rows=(Row((Badge("=1+1", "muted"),)),)))
    badge = _kids(_kids(header)[0])[0]
    assert _ev(badge["txtContent"], {}) == "=1+1"


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
        HeaderTree(banner=Banner(icon="Calendar", rules=(BannerRule(OPEN, "t"),))),
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


def _bundle(tree: HeaderTree, extra: list[Column] | None = None) -> tuple[Schema, MappingBundle]:
    task = table(
        "Task",
        column("Status", "task_status"), column("Risk"), column("Case"), column("Due", "date"),
        column("Score", "calculated_text"), *(extra or []),
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


# --- header icon tile and strapline ------------------------------------------------------------


def test_an_unknown_header_icon_is_refused_through_resolve() -> None:
    schema_, base = _bundle(HeaderTree(icon="Calendar"))
    _, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HEADER_ICON_UNKNOWN]
    assert "the header icon 'Calendar'" in findings[0].message


def test_the_icon_header_still_obeys_the_size_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form_header, "FORM_HEADER_MAX_CHARS", 400)
    with pytest.raises(form_header.HeaderRefusal) as found:
        _render(HeaderTree(icon="Shield", title=Title("Title", "x" * 600)))
    assert found.value.finding.code is FindingCode.FORM_HEADER_TOO_LARGE


def test_a_lone_static_subtitle_is_plain_text() -> None:
    strap = _parts(HeaderTree(subtitle=(SubtitlePart(text="One sentence."),)))[0]
    assert strap["txtContent"] == "One sentence."


def test_a_static_subtitle_part_shows_beside_a_column_part() -> None:
    tree = HeaderTree(subtitle=(SubtitlePart(text="Static."), SubtitlePart(column="Case")))
    strap = _parts(tree)[0]
    assert _ev(strap["txtContent"], {"Case": "C1"}) == "Static. · C1"
    assert _ev(strap["txtContent"], {"Case": ""}) == "Static."


def test_a_subtitle_fallback_shows_while_a_column_is_empty() -> None:
    part = SubtitlePart(text="Case {Case}", columns=("Case",), fallback="No case yet")
    strap = _parts(HeaderTree(subtitle=(part,)))[0]
    assert _ev(strap["txtContent"], {"Case": "C1"}) == "Case C1"
    assert _ev(strap["txtContent"], {"Case": ""}) == "No case yet"
    assert _ev(_style(strap, "display"), {"Case": ""}) == "block"

REFERENCE = Path(__file__).parent / "fixtures" / "form_header"
GUIDES_URL = "https://hub.fabrikam.net/sites/help/SitePages/"
REFERENCE_RULES = (
    BannerRule(
        Leaf("Status", "eq", "Open"), "Start the work.", "start-work",
        "You set the status to In progress.",
    ),
    BannerRule(
        Leaf("Status", "eq", "Late"), "Chase the owner.", None, "The owner replies in the thread.",
    ),
    BannerRule(Leaf("Status", "eq", "Done"), "Wait for the approver."),
)
REFERENCE_HEADER = HeaderTree(
    icon="WorkItem",
    title=Title("Title", "Untitled"),
    subtitle=(SubtitlePart(text="Action item"),),
    chips=(
        LinkChip("Meeting guide", "Lightbulb", url=GUIDES_URL + "Guide.aspx", emphasis="primary"),
        LinkChip("See actions of this type", "ClipboardList", url=GUIDES_URL + "Actions.aspx"),
    ),
    rows=(Row((
        Bubble("Status", tokens={"Open": "low", "Late": "blocked"}),
        Badge("Item type: Action", "neutral"),
    )),),
    banner=Banner(rules=REFERENCE_RULES),
)
REFERENCE_FOOTER = HeaderTree(
    subtitle=(SubtitlePart(text="Static."),),
    banner=Banner(rules=(BannerRule(OPEN, "Open now"),), icon="Lightbulb"),
)


def _golden(name: str, tree: HeaderTree) -> None:
    ctx = dataclasses.replace(_ctx(), help_guides={"start-work": GUIDES_URL + "Start.aspx"})
    text = json.dumps(render_header(tree, ctx), indent=2) + "\n"
    assert (REFERENCE / name).read_text(encoding="utf-8") == text


def test_byte_exact_render_of_the_reference_header() -> None:
    _golden("header.json", REFERENCE_HEADER)


def test_byte_exact_render_of_a_footer() -> None:
    _golden("footer.json", REFERENCE_FOOTER)


@pytest.mark.parametrize(
    ("tree", "code"),
    [
        (HeaderTree(rows=(Row((Bubble("Nope"),)),)), FindingCode.FORM_HEADER_COLUMN_UNKNOWN),
        (HeaderTree(banner=Banner(icon="Calendar", rules=(BannerRule(OPEN, "t"),))),
         FindingCode.FORM_HEADER_ICON_UNKNOWN),
        (HeaderTree(rows=(Row((Bubble("Risk", due=True),)),)),
         FindingCode.FORM_HEADER_DUE_NEEDS_DATE),
    ],
)
def test_a_footer_is_refused_for_the_header_rules(tree: HeaderTree, code: FindingCode) -> None:
    schema_, base = _bundle(HeaderTree())
    base = dataclasses.replace(base, form_trees={"Task": {"footer": tree}})
    resolved, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [code]
    assert resolved.mapping.form_formatting["Task"].footer is None


def test_an_oversize_footer_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form_header, "FORM_HEADER_MAX_CHARS", 400)
    schema_, base = _bundle(HeaderTree())
    tree = HeaderTree(subtitle=(SubtitlePart(text="x" * 600),))
    base = dataclasses.replace(base, form_trees={"Task": {"footer": tree}})
    _, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HEADER_TOO_LARGE]


# --- web-relative links, title prefix, label colon and number bubbles -----------------------


def _chip_href(chip: LinkChip, ctx: RenderContext) -> object:
    node = _chip_nodes(render_header(HeaderTree(chips=(chip,)), ctx))[0]
    return _attr(node, "href")


def test_a_web_template_starts_at_the_site_and_list_gives_the_list_path() -> None:
    template = "{web}/{list}/History.aspx?FilterField1=Case&FilterValue1={value}"
    chip = LinkChip("History", "Feedback", url_column="Case", url_template=template)
    ctx = dataclasses.replace(_ctx(), list_path="Lists/Tasks")
    href = _chip_href(chip, ctx)
    assert href == (
        "=@currentWeb + '/Lists/Tasks/History.aspx?FilterField1=Case&FilterValue1=' + [$Case]"
    )


def _list_href(
    *, kind: Literal["List", "DocumentLibrary"] = "List", title: str | None = None,
    internal_name: str | None = None, renamed_from: tuple[str, ...] = (),
    previous_prefixes: tuple[str, ...] = (),
) -> object:
    schema_, base = _bundle(HeaderTree())
    entity = dataclasses.replace(
        base.mapping.entities["Task"], kind=kind, title=title, internal_name=internal_name,
        renamed_from=renamed_from,
    )
    mapping = dataclasses.replace(
        base.mapping, entities={"Task": entity}, previous_prefixes=previous_prefixes,
    )
    ctx = form_header._context(schema_, dataclasses.replace(base, mapping=mapping), "Task", SITE)
    assert ctx is not None
    chip = LinkChip("H", "Feedback", url_column="Case", url_template="{web}/{list}/x?{value}")
    return _chip_href(chip, ctx)


def test_a_list_token_with_an_internal_name_is_encoded_per_segment() -> None:
    assert _list_href(internal_name="Lists/Tasks #1") == (
        "=@currentWeb + '/Lists/Tasks%20%231/x?' + [$Case]"
    )


def test_a_list_token_without_an_internal_name_is_the_derived_list_path() -> None:
    assert _list_href() == "=@currentWeb + '/Lists/APP_Task/x?' + [$Case]"


def test_a_list_token_without_an_internal_name_on_a_library_has_no_lists_prefix() -> None:
    assert _list_href(kind="DocumentLibrary") == (
        "=@currentWeb + '/APP_Task/x?' + [$Case]"
    )


@pytest.mark.parametrize(("renamed", "prefixes"), [(("Old",), ()), ((), ("OLD_",))])
def test_a_derived_list_token_is_refused_when_a_rename_keeps_the_old_root(
    renamed: tuple[str, ...], prefixes: tuple[str, ...],
) -> None:
    with pytest.raises(HeaderRefusal) as found:
        _list_href(renamed_from=renamed, previous_prefixes=prefixes)
    assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED
    assert "Set internal_name" in found.value.finding.message


def test_a_derived_list_token_is_refused_when_a_title_is_added() -> None:
    with pytest.raises(HeaderRefusal) as found:
        _list_href(title="Task Log")
    assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED


def test_a_declared_internal_name_survives_a_rename() -> None:
    assert _list_href(internal_name="Lists/Tasks", renamed_from=("Old",)) == (
        "=@currentWeb + '/Lists/Tasks/x?' + [$Case]"
    )


def test_a_web_template_keeps_the_quote_refusal() -> None:
    chip = LinkChip("H", "Feedback", url_column="Case", url_template="{web}/it's/{value}")
    with pytest.raises(HeaderRefusal) as found:
        _chip_href(chip, _ctx())
    assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED


def test_title_prefix_shows_only_with_a_value() -> None:
    tree = HeaderTree(title=Title("Title", "Untitled", prefix="Workspace: "))
    title = _parts(tree)[0]
    assert title["txtContent"] == (
        "=if(toString([$Title]) == '', 'Untitled', 'Workspace: ' + [$Title])"
    )
    assert _ev(title["txtContent"], {"Title": "Alpha"}) == "Workspace: Alpha"
    assert _ev(title["txtContent"], {"Title": ""}) == "Untitled"


def test_title_prefix_with_a_quote_is_refused() -> None:
    with pytest.raises(HeaderRefusal) as found:
        _render(HeaderTree(title=Title("Title", "x", prefix="It's ")))
    assert found.value.finding.code is FindingCode.FORM_HEADER_TEXT_UNSUPPORTED


def test_label_colon_is_the_default_and_can_be_switched_off() -> None:
    assert _text(_bubble(Bubble("Risk", label="Wave gate"))) == "='Wave gate: ' + [$Risk]"
    off = _bubble(Bubble("Risk", label="Wave gate ", label_colon=False))
    assert _text(off) == "='Wave gate ' + [$Risk]"
    assert _ev(_text(off), {"Risk": "A"}) == "Wave gate A"


NUMBERS = {**TYPES, "Points": "int", "Cost": "number", "Loose": "number"}


def _numbers(filled: frozenset[str] = frozenset({"Points", "Cost"})) -> RenderContext:
    return RenderContext("Task", NUMBERS, FORMULAS, {"Status": STATUSES}, SITE, "", filled)


def test_a_required_number_with_a_default_shows_its_raw_value() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Points", label="Points", tokens={"3": "severe"}),)),))
    bubble = _kids(_kids(render_header(tree, _numbers()))[0])[0]
    assert _text(bubble) == "='Points: ' + toString([$Points])"
    assert _shown(bubble, {"Points": 3})[2] == "Points: 3"
    assert _shown(bubble, {"Points": 3})[1] == form_header._pill("severe")[0]
    assert _shown(bubble, {"Points": 4})[1] == NEUTRAL


def test_a_number_that_can_be_blank_is_refused() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Loose"),)),))
    with pytest.raises(HeaderRefusal) as found:
        render_header(tree, _numbers())
    assert found.value.finding.code is FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
    assert "Task.Loose" in found.value.finding.message


def test_resolve_marks_only_required_numbers_with_a_default_as_showable() -> None:
    cols = [column("Points", "int", required=True, default=1), column("Cost", "number")]
    schema_, base = _bundle(
        HeaderTree(rows=(Row((Bubble("Points"), Bubble("Cost"))),)), extra=cols,
    )
    _, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED]
    assert "Cost" in findings[0].message


def test_a_chip_tooltip_is_only_the_authors_and_its_icon_is_hidden() -> None:
    chips = _chip_nodes(_render(HeaderTree(chips=(
        LinkChip("Open case", "Feedback", url="u"),
        LinkChip("Help", "Feedback", url="u", title="Help centre"),
    ))))
    assert _attr(chips[0], "href") == "u"
    assert {k: v for k, v in _attrs(chips[0]).items() if k != "class"} == {
        "href": "u", "target": "_blank", "rel": "noopener noreferrer",
    }
    assert _attr(chips[1], "title") == "Help centre"
    assert _attr(_kids(chips[0])[0], "aria-hidden") == "true"
    assert _attr(chips[0], "target") == "_blank"


def test_a_bubble_blank_text_shows_alone_while_the_column_is_empty() -> None:
    bubble = _bubble(Bubble("Risk", label="Risk", blank="Not set", tokens={"High": "severe"}))
    assert _text(bubble) == "=if(toString([$Risk]) == '', 'Not set', 'Risk: ' + [$Risk])"
    assert _shown(bubble, {"Risk": ""}) == ("inline-block", NEUTRAL, "Not set")
    assert _shown(bubble, {"Risk": "High"})[2] == "Risk: High"
    assert str(_shown(bubble, {"Risk": "High"})[1]).startswith(TOKENS["severe"].classes)


def test_a_blank_text_keeps_hide_values_and_a_blank_due_date_is_not_overdue() -> None:
    hid = _bubble(Bubble("Risk", blank="Not set", hide_values=("None",)))
    assert _shown(hid, {"Risk": "None"})[0] == "none"
    assert _shown(hid, {"Risk": ""})[0] == "inline-block"
    due = _bubble(Bubble("Due", blank="No date", due=True))
    empty = {"Due": date_field(None), "Due.displayValue": ""}
    shown = _shown(due, empty)
    assert shown[0] == "inline-block"
    assert shown[1] == NEUTRAL
    assert shown[2] == "No date"


def test_a_list_token_percent_encodes_each_segment_and_keeps_the_slashes() -> None:
    chip = LinkChip("H", "Feedback", url_column="Case", url_template="{web}/{list}/x?{value}")
    ctx = dataclasses.replace(_ctx(), list_path="Lists/Cost #Centre 50%")
    assert _chip_href(chip, ctx) == "=@currentWeb + '/Lists/Cost%20%23Centre%2050%25/x?' + [$Case]"


# --- the help link ------------------------------------------------------------------------------

GUIDES = {"g-a": "https://h/a", "g-c": "https://h/c"}

_MIXED = (
    BannerRule(Leaf("Risk", "eq", "High"), "a", "g-a"),
    BannerRule(Leaf("Risk", "eq", "Low"), "b"),
    BannerRule(Leaf("Status", "eq", "Open"), "c", "g-c"),
)


def _help_ctx() -> RenderContext:
    return dataclasses.replace(_ctx(), help_guides=GUIDES)


def _help_banner(*rules: BannerRule, when: Leaf | None = None) -> dict[str, object]:
    tree = HeaderTree(banner=Banner(icon="Lightbulb", rules=rules, when=when))
    return _kids(render_header(tree, _help_ctx()))[0]


def _style_keys(node: dict[str, object]) -> set[str]:
    style = node["style"]
    assert isinstance(style, dict)
    return set(style)


SUFFIX = ", opens the step guide in a new tab"
HIGH, LOW, OPEN_ROW = (
    {"Risk": "High", "Status": "Open"}, {"Risk": "Low", "Status": "Open"},
    {"Risk": "x", "Status": "Open"},
)


def test_a_rule_with_help_shows_the_link_and_hides_the_plain_action() -> None:
    label, link, plain = _now(_help_banner(*_MIXED))
    assert link["elmType"] == "a"
    for row, href, link_shown, plain_shown in (
        (HIGH, "https://h/a", "inline", "none"),
        (LOW, "", "none", "inline"),
        (OPEN_ROW, "https://h/c", "inline", "none"),
    ):
        assert _ev(_attr(link, "href"), row) == href
        assert _ev(_style(link, "display"), row) == link_shown
        assert _ev(_style(plain, "display"), row) == plain_shown
    assert _ev(_kids(link)[0]["txtContent"], HIGH) == "a"
    assert _ev(_kids(link)[0]["txtContent"], LOW) == "b"
    assert _ev(plain["txtContent"], LOW) == "b"
    assert label["txtContent"] == "To do now:"


def test_the_linked_action_has_a_visible_first_name_target_rel_and_glyph() -> None:
    link = _now(_help_banner(*_MIXED))[1]
    for key in ("aria-label", "title"):
        assert _ev(_attr(link, key), HIGH) == "a" + SUFFIX
        assert _ev(_attr(link, key), OPEN_ROW) == "c" + SUFFIX
        assert str(_attr(link, key)).endswith(f" + '{SUFFIX}'")
    assert _attr(link, "target") == "_blank"
    assert _attr(link, "rel") == "noopener noreferrer"
    assert _style(link, "text-decoration") == "underline"
    glyph = _kids(link)[1]
    assert _attr(glyph, "iconName") == "OpenInNewWindow"
    assert _attr(glyph, "aria-hidden") == "true"


def test_the_link_name_drops_one_trailing_stop_but_the_visible_text_keeps_it() -> None:
    rules = (
        BannerRule(Leaf("Risk", "eq", "High"), "Confirm the rating. ", "g-a"),
        BannerRule(OPEN, "Pick one", "g-c"),
        BannerRule(Leaf("Risk", "eq", "z"), "Wait...", "g-c"),
    )
    link, _plain = _now(_help_banner(*rules))[1:]
    visible = _kids(link)[0]["txtContent"]
    for key in ("aria-label", "title"):
        assert _ev(_attr(link, key), HIGH) == "Confirm the rating" + SUFFIX
        assert _ev(_attr(link, key), {"Risk": "y", "Status": "Open"}) == "Pick one" + SUFFIX
        assert _ev(_attr(link, key), {"Risk": "z"}) == "Wait.." + SUFFIX
    assert _ev(visible, HIGH) == "Confirm the rating. "
    assert _ev(visible, {"Risk": "z"}) == "Wait..."


def test_a_rule_without_help_shows_plain_text_only() -> None:
    banner = _help_banner(BannerRule(OPEN, "b"))
    _label, plain = _now(banner)
    assert plain["elmType"] == "span"
    assert "style" not in plain
    assert '"elmType": "a"' not in json.dumps(banner)
    assert _ev(plain["txtContent"], {"Status": "Open"}) == "b"


def test_mixed_rules_render_the_golden_href_and_display() -> None:
    _label, link, plain = _now(_help_banner(*_MIXED))
    a, b, c = "([$Risk] == 'High')", "([$Risk] == 'Low')", "([$Status] == 'Open')"
    assert _attr(link, "href") == (
        f"=if({a}, 'https://h/a', if({b}, '', if({c}, 'https://h/c', '')))"
    )
    assert _style(link, "display") == (
        f"=if({a}, 'inline', if({b}, 'none', if({c}, 'inline', 'none')))"
    )
    assert _style(plain, "display") == (
        f"=if({a}, 'none', if({b}, 'inline', if({c}, 'none', 'inline')))"
    )


def test_labels_are_fixed_copy() -> None:
    banner = _help_banner(BannerRule(OPEN, "a", None, "n"))
    assert _now(banner)[0]["txtContent"] == "To do now:"
    after = _kids(_kids(banner)[1])[1]
    assert _kids(after)[0]["txtContent"] == "After that:"


def test_a_rule_without_next_hides_after_that() -> None:
    rules = (BannerRule(OPEN, "a", None, "then b"), BannerRule(Leaf("Risk", "eq", "x"), "c"))
    after = _kids(_kids(_help_banner(*rules))[1])[1]
    follows = _kids(after)[1]["txtContent"]
    assert _ev(_style(after, "display"), {"Status": "Open"}) == "inline"
    assert _ev(follows, {"Status": "Open"}) == "then b"
    assert _ev(_style(after, "display"), {"Status": "Late", "Risk": "x"}) == "none"
    assert _ev(follows, {"Status": "Late", "Risk": "x"}) == ""
    assert _ev(_style(after, "display"), {"Status": "Late"}) == "none"


def test_no_rule_with_next_means_no_after_that_node() -> None:
    assert len(_kids(_kids(_help_banner(BannerRule(OPEN, "a")))[1])) == 1


def test_a_status_with_no_rule_hides_the_box() -> None:
    box = _help_banner(*_MIXED)
    assert _ev(_style(box, "display"), {"Risk": "x", "Status": "Done"}) == "none"
    assert _ev(_style(box, "display"), OPEN_ROW) == "flex"


def test_step_box_is_content_width() -> None:
    box = _help_banner(*_MIXED)
    assert _style(box, "align-self") == "flex-start"
    assert _style(box, "max-width") == "100%"
    assert "width" not in _style_keys(box)


def test_the_banner_icon_defaults_to_forward() -> None:
    tree = HeaderTree(banner=Banner(rules=(BannerRule(OPEN, "t"),)))
    arrow = _kids(_kids(_render(tree))[0])[0]
    assert _attr(arrow, "iconName") == "Forward"
    assert _attr(arrow, "aria-hidden") == "true"


def test_a_hidden_banner_hides_the_link() -> None:
    banner = _help_banner(*_MIXED, when=Leaf("Notes", "is_null"))
    row = {"Risk": "High", "Status": "Open", "Notes": "x"}
    assert _ev(_style(banner, "display"), row) == "none"  # the link is a child of it


def test_a_hash_question_mark_or_ampersand_in_text_does_not_break_the_expression() -> None:
    odd = "Open #3 now? a&b"
    banner = _help_banner(BannerRule(OPEN, odd, "g-a", odd))
    link = _now(banner)[1]
    row = {"Status": "Open"}
    assert _ev(_kids(link)[0]["txtContent"], row) == odd
    assert _ev(_attr(link, "aria-label"), row) == odd + SUFFIX
    assert _ev(_kids(_kids(_kids(banner)[1])[1])[1]["txtContent"], row) == odd


# --- the redesigned tree ------------------------------------------------------------------------


def _walk(node: object) -> list[dict[str, object]]:
    assert isinstance(node, dict)
    found = [node]
    for kid in node.get("children", []):
        found += _walk(kid)
    return found


def _full() -> dict[str, object]:
    ctx = dataclasses.replace(_ctx(), help_guides={"start-work": GUIDES_URL + "Start.aspx"})
    return render_header(REFERENCE_HEADER, ctx)


def test_root_is_a_flex_column_with_the_separator() -> None:
    root = _full()
    assert _attr(root, "class") == "ms-borderColor-neutralLight"
    assert _style(root, "display") == "flex"
    assert _style(root, "flex-direction") == "column"
    assert _style(root, "width") == "100%"
    assert _style(root, "border-width") == "0 0 1px 0"
    assert _style(root, "border-style") == "solid"


def test_no_node_uses_the_border_shorthand() -> None:
    for node in _walk(_full()):
        style = node.get("style", {})
        assert isinstance(style, dict)
        assert "border" not in style


def test_row_one_wraps_and_holds_tile_title_and_buttons() -> None:
    top = _kids(_full())[0]
    assert _style(top, "flex-wrap") == "wrap"
    assert _style(top, "justify-content") == "space-between"
    identity, actions = _kids(top)
    tile, block = _kids(identity)
    assert _attr(_kids(tile)[0], "iconName") == "WorkItem"
    assert [_attr(k, "class") for k in _kids(block)] == [
        "ms-fontColor-neutralPrimary ms-fontWeight-bold ms-fontSize-20",
        "ms-fontColor-neutralSecondary ms-fontSize-12",
    ]
    assert [_kids(a)[1]["txtContent"] for a in _kids(actions)] == [
        "Meeting guide", "See actions of this type",
    ]


def test_tile_is_40px_with_a_24px_icon_and_top_aligned() -> None:
    tile = _kids(_kids(_kids(_full())[0])[0])[0]
    assert (_style(tile, "width"), _style(tile, "height")) == ("40px", "40px")
    assert _style(tile, "align-self") == "flex-start"
    assert _attr(_kids(tile)[0], "class") == "ms-fontSize-24 ms-fontColor-themePrimary"


def test_secondary_and_primary_buttons_carry_the_spec_classes() -> None:
    primary, secondary = _kids(_kids(_kids(_full())[0])[1])
    assert _attr(primary, "class") == (
        "ms-bgColor-themePrimary ms-fontColor-white ms-fontSize-12 ms-fontWeight-semibold"
    )
    assert _style(primary, "border-color") == "transparent"
    assert _attr(secondary, "class") == (
        "ms-bgColor-neutralLighter ms-borderColor-neutralLight ms-fontColor-neutralPrimary "
        "ms-fontSize-12 ms-fontWeight-semibold"
    )
    assert "border-color" not in _style_keys(secondary)
    assert _style(secondary, "white-space") == "normal"


def test_low_status_pill_is_outlined_and_severity_pills_have_fixed_dark_text() -> None:
    pill, badge = _kids(_kids(_full())[1])
    low, late, other = {"Status": "Open"}, {"Status": "Late"}, {"Status": "Done"}
    assert "ms-borderColor-neutralTertiary" in str(_ev(_attr(pill, "class"), low))
    assert "ms-borderColor-neutralTertiary" not in str(_ev(_attr(pill, "class"), late))
    assert _ev(_style(pill, "color"), low) == "#323130"
    assert _ev(_style(pill, "color"), late) == "#323130"
    assert _ev(_style(pill, "color"), other) == ""
    assert "ms-fontColor-neutralPrimary" in str(_ev(_attr(pill, "class"), other))
    assert _attr(badge, "class") == NEUTRAL
    assert "color" not in _style_keys(badge)
    assert _ev(_style(pill, "display"), low) == "inline-block"


def test_secondary_is_the_default_emphasis() -> None:
    assert LinkChip("a", "Feedback", url="u").emphasis == "secondary"


def test_an_unmapped_key_is_refused_naming_key_entity_and_rule() -> None:
    tree = HeaderTree(banner=Banner(icon="Lightbulb", rules=(
        BannerRule(OPEN, "a", "g-a"), BannerRule(Leaf("Risk", "eq", "x"), "b", "nope"),
    )))
    with pytest.raises(HeaderRefusal) as found:
        render_header(tree, _help_ctx())
    assert found.value.finding.code is FindingCode.FORM_HELP_KEY_UNMAPPED
    assert found.value.finding.message == (
        "Task: banner rule 2 help key 'nope' is not in DBMLSP_HELP_GUIDES."
    )


def test_help_off_renders_no_link_and_reports_one_warning() -> None:
    tree = HeaderTree(banner=Banner(icon="Lightbulb", rules=_MIXED))
    schema_, base = _bundle(tree)
    resolved, findings = resolve_form_headers(schema_, base, SITE)
    assert [f.code for f in findings] == [FindingCode.FORM_HELP_OFF]
    assert findings[0].severity == "warning"
    assert "DBMLSP_HELP_BASE_URL" in findings[0].message
    assert "DBMLSP_HELP_GUIDES" in findings[0].message
    assert "Help for this step" not in json.dumps(resolved.mapping.form_formatting["Task"].header)


def test_help_off_without_any_help_key_reports_nothing() -> None:
    tree = HeaderTree(banner=Banner(icon="Lightbulb", rules=(BannerRule(OPEN, "t"),)))
    schema_, base = _bundle(tree)
    assert resolve_form_headers(schema_, base, SITE)[1] == []


def test_help_on_through_resolve_renders_the_url() -> None:
    schema_, base = _bundle(HeaderTree(banner=Banner(icon="Lightbulb", rules=_MIXED)))
    resolved, findings = resolve_form_headers(schema_, base, SITE, HelpGuides(GUIDES))
    assert findings == []
    assert "https://h/a" in json.dumps(resolved.mapping.form_formatting["Task"].header)


def test_a_neutral_branch_has_no_fixed_text_colour_ahead_of_a_severity_default() -> None:
    bubble = _bubble(Bubble("Risk", tokens={"Done": "neutral", "default": "warning"}))
    assert _ev(_style(bubble, "color"), {"Risk": "Done"}) == ""
    assert _ev(_style(bubble, "color"), {"Risk": "Other"}) == "#323130"
    assert "ms-fontColor-neutralPrimary" in str(_ev(_attr(bubble, "class"), {"Risk": "Done"}))


def test_the_header_wraps_with_the_documented_property() -> None:
    text = json.dumps(_full())
    assert "overflow-wrap" not in text
    assert '"word-wrap": "break-word"' in text
