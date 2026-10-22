# test/test_form_components.py
"""The header component tree: typed nodes, and refusals that name the key."""

import pytest

from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.form_components import parse_header
from dbml_sharepoint.model.form_tree import (
    Badge,
    Banner,
    BannerRule,
    Bubble,
    HeaderTree,
    LinkChip,
    NewItemStep,
    Row,
    SubtitlePart,
    Title,
)

_IS_OPEN = {"field": "Status", "op": "eq", "value": "Open"}
_OPEN = Leaf("Status", "eq", "Open")


def _parse(raw: object) -> HeaderTree:
    return parse_header(raw, "header")


def _row(*items: object) -> dict[str, object]:
    return {"rows": [{"items": list(items)}]}


def test_the_full_tree_parses() -> None:
    tree = _parse({
        "title": {"column": "Title", "blank": "Untitled", "when": _IS_OPEN},
        "subtitle": ["Owner", {"text": "Due {Due}", "columns": ["Due"], "when": _IS_OPEN}],
        "chips": [
            {"text": "Help", "icon": "Help", "url": "https://example.com"},
            {
                "text": "Case", "icon": "Link", "url_column": "CaseId",
                "url_template": "https://example.com/{value}", "when": _IS_OPEN,
            },
        ],
        "rows": [{"when": _IS_OPEN, "items": [
            {
                "column": "Risk", "label": "Risk", "text": "{value} risk",
                "hide_values": ["None"], "tokens": {"High": "severe", "default": "neutral"},
                "when": _IS_OPEN,
            },
            {"column": "Due", "due": True, "tokens": {"default": "good"}},
            {"badge": {"text": "No assessment", "token": "muted"}},
        ]}],
        "banner": {
            "icon": "Info",
            "rules": [{"when": _IS_OPEN, "text": "Open"}],
        },
    })
    assert tree == HeaderTree(
        title=Title("Title", "Untitled", _OPEN),
        subtitle=(
            SubtitlePart(column="Owner"),
            SubtitlePart(text="Due {Due}", columns=("Due",), when=_OPEN),
        ),
        chips=(
            LinkChip("Help", "Help", url="https://example.com"),
            LinkChip(
                "Case", "Link", url_column="CaseId",
                url_template="https://example.com/{value}", when=_OPEN,
            ),
        ),
        rows=(Row(
            (
                Bubble(
                    "Risk", label="Risk", text="{value} risk", hide_values=("None",),
                    tokens={"High": "severe", "default": "neutral"}, when=_OPEN,
                ),
                Bubble("Due", due=True, tokens={"default": "good"}),
                Badge("No assessment", "muted"),
            ),
            _OPEN,
        ),),
        banner=Banner((BannerRule(_OPEN, "Open"),), "Info"),
    )


def test_unknown_token_is_refused_naming_the_vocabulary() -> None:
    with pytest.raises(MappingValueError, match=r"unknown token 'loud'.*good"):
        _parse(_row({"column": "Risk", "tokens": {"High": "loud"}}))


def test_a_chip_with_both_url_forms_is_refused() -> None:
    chip = {
        "text": "Case", "icon": "Link", "url": "https://example.com",
        "url_column": "CaseId", "url_template": "x/{value}",
    }
    with pytest.raises(MappingShapeError, match=r"chips\[0\].*either url or"):
        _parse({"chips": [chip]})


def test_url_template_without_value_is_refused() -> None:
    chip = {"text": "Case", "icon": "Link", "url_column": "CaseId", "url_template": "x/y"}
    with pytest.raises(MappingValueError, match=r"url_template.*\{value\}"):
        _parse({"chips": [chip]})


def test_a_bubble_text_template_without_value_is_refused() -> None:
    with pytest.raises(MappingValueError, match=r"text.*\{value\}"):
        _parse(_row({"column": "Risk", "text": "High risk"}))


def test_a_row_item_may_carry_its_own_when() -> None:
    tree = _parse(_row({"column": "Risk", "when": _IS_OPEN}))
    assert tree.rows[0].items[0] == Bubble("Risk", when=_OPEN)


def test_a_row_with_no_items_is_refused() -> None:
    with pytest.raises(MappingShapeError, match="at least one item"):
        _parse({"rows": [{"items": []}]})


def test_a_banner_with_no_rules_is_refused() -> None:
    with pytest.raises(MappingShapeError, match="at least one rule"):
        _parse({"banner": {"icon": "Info", "rules": []}})


def test_text_with_quotes_and_braces_parses_verbatim() -> None:
    label = "Owner's {x} 50%"
    assert _parse(_row({"column": "Owner", "label": label})).rows[0].items[0] == Bubble(
        "Owner", label=label,
    )


def test_an_unknown_key_is_refused_by_name() -> None:
    with pytest.raises(UnknownMappingKeyError, match="colour"):
        _parse(_row({"column": "Risk", "colour": "red"}))


@pytest.mark.parametrize("order", ["dmy", "mdy", "ymd"])
def test_a_bubble_keeps_its_date_order(order: str) -> None:
    tree = _parse(_row({"column": "Review", "date_order": order}))
    item = tree.rows[0].items[0]
    assert isinstance(item, Bubble)
    assert item.date_order == order


def test_a_bubble_without_a_date_order_has_none() -> None:
    item = _parse(_row({"column": "Review"})).rows[0].items[0]
    assert isinstance(item, Bubble)
    assert item.date_order is None


@pytest.mark.parametrize("order", ["DMY", "dd/mm/yyyy", "", 5])
def test_any_other_date_order_is_refused_naming_the_key(order: object) -> None:
    with pytest.raises(MappingValueError, match=r"date_order"):
        _parse(_row({"column": "Review", "date_order": order}))


def test_a_header_icon_parses() -> None:
    assert _parse({"icon": "Shield", "title": {"column": "Title", "blank": "New"}}).icon == "Shield"
    assert _parse({"title": {"column": "Title", "blank": "New"}}).icon is None


def test_a_header_icon_must_not_be_empty() -> None:
    with pytest.raises(MappingShapeError, match=r"header\.icon"):
        _parse({"icon": ""})


def test_a_static_subtitle_part_needs_no_columns() -> None:
    assert _parse({"subtitle": [{"text": "Plain."}]}).subtitle == (SubtitlePart(text="Plain."),)


def test_a_subtitle_fallback_parses_and_needs_columns() -> None:
    part = _parse({"subtitle": [{"text": "Due {Due}", "columns": ["Due"], "fallback": "No date"}]})
    assert part.subtitle[0].fallback == "No date"
    with pytest.raises(MappingShapeError, match="fallback needs columns"):
        _parse({"subtitle": [{"text": "Plain.", "fallback": "x"}]})


def test_label_and_chips_align_are_refused_as_unknown_keys() -> None:
    with pytest.raises(UnknownMappingKeyError, match="chips_align"):
        _parse({"chips_align": "top"})
    rules = [{"when": _IS_OPEN, "text": "a"}]
    with pytest.raises(UnknownMappingKeyError, match="label"):
        _parse({"banner": {"label": "Notice", "icon": "Info", "rules": rules}})


@pytest.mark.parametrize("key", ["icon", "title"])
def test_a_footer_refuses_header_only_keys(key: str) -> None:
    raw = {"icon": "Shield", "title": {"column": "T", "blank": "x"}}
    with pytest.raises(MappingShapeError, match=f"footer.{key}: a footer takes no {key}"):
        parse_header({key: raw[key]}, "footer", footer=True)


def test_a_footer_parses_the_shared_components() -> None:
    tree = parse_header({"subtitle": [{"text": "Hi."}], "rows": [{"items": [{"column": "A"}]}]},
                        "footer", footer=True)
    assert tree.subtitle and tree.rows


def test_title_prefix_and_label_colon_parse() -> None:
    tree = _parse({
        "title": {"column": "Title", "blank": "x", "prefix": "Workspace: "},
        **_row({"column": "Risk", "label": "Gate ", "label_colon": False}),
    })
    assert tree.title == Title("Title", "x", prefix="Workspace: ")
    assert tree.rows[0].items[0] == Bubble("Risk", label="Gate ", label_colon=False)


def test_label_colon_must_be_a_boolean_and_prefix_not_empty() -> None:
    with pytest.raises(MappingShapeError, match="label_colon"):
        _parse(_row({"column": "Risk", "label_colon": "no"}))
    with pytest.raises(MappingShapeError, match="prefix"):
        _parse({"title": {"column": "Title", "blank": "", "prefix": ""}})


def test_web_token_is_leading_only() -> None:
    chip = {"text": "H", "icon": "Link", "url_column": "C"}
    ok = _parse({"chips": [{**chip, "url_template": "{web}/{list}/x?{value}"}]})
    assert ok.chips[0].url_template == "{web}/{list}/x?{value}"
    with pytest.raises(MappingValueError, match=r"leading"):
        _parse({"chips": [{**chip, "url_template": "x/{web}/{value}"}]})


def test_chip_title_and_bubble_blank_parse() -> None:
    chip = {"text": "H", "icon": "Link", "url": "u", "title": "Help centre"}
    assert _parse({"chips": [chip]}).chips[0].title == "Help centre"
    assert _parse(_row({"column": "Risk", "blank": "Not set"})).rows[0].items[0] == Bubble(
        "Risk", blank="Not set",
    )
    with pytest.raises(MappingShapeError, match="blank"):
        _parse(_row({"column": "Risk", "blank": ""}))


def test_a_banner_rule_help_key_is_parsed_and_defaults_to_none() -> None:
    tree = _parse({"banner": {"icon": "Info", "rules": [
        {"when": _IS_OPEN, "text": "a", "help": "g-a"},
        {"when": _IS_OPEN, "text": "b"},
    ]}})
    assert tree.banner is not None
    assert [rule.help for rule in tree.banner.rules] == ["g-a", None]


@pytest.mark.parametrize("blank", ["", None])
def test_a_blank_banner_rule_help_key_is_refused_naming_it(blank: object) -> None:
    with pytest.raises(MappingShapeError, match=r"rules\[0\]\.help"):
        _parse({"banner": {"icon": "Info", "rules": [
            {"when": _IS_OPEN, "text": "a", "help": blank},
        ]}})


def test_next_is_parsed_and_defaults_to_none() -> None:
    tree = _parse({"banner": {"rules": [
        {"when": _IS_OPEN, "text": "a", "next": "The owner replies."},
        {"when": _IS_OPEN, "text": "b"},
    ]}})
    assert tree.banner is not None
    assert [rule.next for rule in tree.banner.rules] == ["The owner replies.", None]
    assert tree.banner.icon == "Forward"


def test_next_without_text_is_refused_naming_the_rule() -> None:
    with pytest.raises(MappingShapeError, match=r"header\.banner\.rules\[1\]\.text"):
        _parse({"banner": {"rules": [
            {"when": _IS_OPEN, "text": "a"},
            {"when": _IS_OPEN, "next": "Then this."},
        ]}})


@pytest.mark.parametrize("blank", ["", None])
def test_a_blank_next_is_refused_naming_it(blank: object) -> None:
    with pytest.raises(MappingShapeError, match=r"rules\[0\]\.next"):
        _parse({"banner": {"rules": [{"when": _IS_OPEN, "text": "a", "next": blank}]}})


def test_a_new_step_is_parsed_and_a_banner_may_hold_only_it() -> None:
    tree = _parse({"banner": {"new": {"text": "Fill in.", "next": "Save it.", "help": "g-a"}}})
    assert tree.banner is not None
    assert tree.banner.rules == ()
    assert tree.banner.new == NewItemStep("Fill in.", "g-a", "Save it.")
    both = _parse({"banner": {"new": {"text": "Fill in."}, "rules": [
        {"when": _IS_OPEN, "text": "a"},
    ]}})
    assert both.banner is not None
    assert both.banner.new == NewItemStep("Fill in.")
    assert len(both.banner.rules) == 1


def test_a_banner_with_neither_rules_nor_new_is_refused() -> None:
    with pytest.raises(MappingShapeError, match=r"banner\.rules"):
        _parse({"banner": {"icon": "Info"}})


@pytest.mark.parametrize("key", ["text", "next", "help"])
@pytest.mark.parametrize("blank", ["", None])
def test_a_blank_new_step_key_is_refused_naming_it(key: str, blank: object) -> None:
    step = {"text": "a", key: blank}
    with pytest.raises(MappingShapeError, match=rf"banner\.new\.{key}"):
        _parse({"banner": {"new": step}})


def test_a_new_step_needs_text_and_refuses_a_when_key() -> None:
    with pytest.raises(MappingShapeError, match=r"banner\.new\.text"):
        _parse({"banner": {"new": {"next": "x"}}})
    with pytest.raises(UnknownMappingKeyError, match=r"banner\.new.*when"):
        _parse({"banner": {"new": {"text": "a", "when": _IS_OPEN}}})


def test_emphasis_defaults_to_secondary() -> None:
    chip = {"text": "H", "icon": "Link", "url": "u"}
    assert _parse({"chips": [chip]}).chips[0].emphasis == "secondary"
    assert _parse({"chips": [{**chip, "emphasis": "primary"}]}).chips[0].emphasis == "primary"


@pytest.mark.parametrize("emphasis", ["Primary", "tertiary", "", None, 1])
def test_emphasis_other_than_primary_or_secondary_is_refused(emphasis: object) -> None:
    chip = {"text": "H", "icon": "Link", "url": "u", "emphasis": emphasis}
    with pytest.raises(MappingValueError, match=r"chips\[0\]\.emphasis.*primary, secondary"):
        _parse({"chips": [chip]})
