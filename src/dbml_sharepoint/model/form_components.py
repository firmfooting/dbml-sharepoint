"""Parse the header component tree of a form.yaml into the nodes of `form_tree`.

Every visible word comes from the file; nothing here adds one. Text is kept
byte for byte, so quotes, braces and percent signs are the author's.
"""

from collections.abc import Callable

from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.model._keys import _known_keys
from dbml_sharepoint.model.conditions import Condition, parse_condition
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
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

_VALUE = "{value}"
_WEB = "{web}"
DATE_ORDERS = ("dmy", "mdy", "ymd")
CHIP_ALIGNS = ("top", "middle", "bottom")
_HEADER_ONLY = ("icon", "title", "chips_align")


def _text(raw: object, context: str) -> str:
    if not isinstance(raw, str):
        raise MappingShapeError(f"{context}: expected text, got {raw!r}; quote it")
    return raw


def _nonblank(raw: object, context: str) -> str:
    value = _text(raw, context)
    if not value:
        raise MappingShapeError(f"{context}: must not be empty")
    return value


def _when(block: dict[str, object], context: str) -> Condition | None:
    raw = block.get("when")
    return None if raw is None else parse_condition(raw, f"{context}.when")


def _list(raw: object, context: str, *, empty: str) -> list[object]:
    if not isinstance(raw, list):
        raise MappingShapeError(f"{context}: expected a list, got {type(raw).__name__}")
    if not raw:
        raise MappingShapeError(f"{context}: {empty}")
    return raw


def _token(raw: object, context: str) -> str:
    name = _text(raw, context)
    if name not in TOKENS:
        raise MappingValueError(f"{context}: unknown token {name!r} (known: {sorted(TOKENS)})")
    return name


def _template(raw: object, context: str, *, url: bool = False) -> str:
    value = _nonblank(raw, context)
    if _VALUE not in value:
        raise MappingValueError(f"{context}: must contain {_VALUE}, where the column's value goes")
    if url and _WEB in value.removeprefix(_WEB):
        raise MappingValueError(f"{context}: {_WEB} is the site's address, so only a leading one")
    return value


def _title(raw: object, context: str) -> Title:
    block = _known_keys(raw, {"column", "blank", "prefix", "when"}, context)
    prefix = block.get("prefix")
    return Title(
        _nonblank(block.get("column"), f"{context}.column"),
        _text(block.get("blank"), f"{context}.blank"),
        _when(block, context),
        None if prefix is None else _nonblank(prefix, f"{context}.prefix"),
    )


def _subtitle_part(raw: object, context: str) -> SubtitlePart:
    if isinstance(raw, str):
        return SubtitlePart(column=_nonblank(raw, context))
    block = _known_keys(raw, {"text", "columns", "fallback", "when"}, context)
    text = _nonblank(block.get("text"), f"{context}.text")
    if block.get("columns") is None:
        if block.get("fallback") is not None:
            raise MappingShapeError(f"{context}: a fallback needs columns to wait for")
        return SubtitlePart(text=text, when=_when(block, context))
    columns = tuple(
        _nonblank(c, f"{context}.columns")
        for c in _list(block["columns"], f"{context}.columns", empty="name a column")
    )
    fallback = block.get("fallback")
    return SubtitlePart(
        text=text,
        columns=columns,
        fallback=None if fallback is None else _nonblank(fallback, f"{context}.fallback"),
        when=_when(block, context),
    )


def _chip(raw: object, context: str) -> LinkChip:
    block = _known_keys(
        raw, {"text", "icon", "url", "url_column", "url_template", "title", "when"}, context,
    )
    url, column, template = (block.get(k) for k in ("url", "url_column", "url_template"))
    if url is not None and (column is not None or template is not None):
        raise MappingShapeError(f"{context}: give either url or url_column with url_template")
    if url is None and (column is None or template is None):
        raise MappingShapeError(f"{context}: give url, or both url_column and url_template")
    title = block.get("title")
    return LinkChip(
        _nonblank(block.get("text"), f"{context}.text"),
        _nonblank(block.get("icon"), f"{context}.icon"),
        None if url is None else _nonblank(url, f"{context}.url"),
        None if column is None else _nonblank(column, f"{context}.url_column"),
        None if template is None else _template(template, f"{context}.url_template", url=True),
        None if title is None else _nonblank(title, f"{context}.title"),
        _when(block, context),
    )


def _badge(raw: object, context: str) -> Badge:
    block = _known_keys(raw, {"text", "token", "when"}, context)
    return Badge(
        _nonblank(block.get("text"), f"{context}.text"),
        _token(block.get("token"), f"{context}.token"),
        _when(block, context),
    )


def _bubble(raw: object, context: str) -> Bubble:
    block = _known_keys(
        raw,
        {
            "column", "label", "label_colon", "blank", "text", "hide_values", "tokens", "due",
            "date_order", "when",
        },
        context,
    )
    due = block.get("due", False)
    if not isinstance(due, bool):
        raise MappingShapeError(f"{context}.due: expected true or false, got {due!r}")
    colon = block.get("label_colon", True)
    if not isinstance(colon, bool):
        raise MappingShapeError(f"{context}.label_colon: expected true or false, got {colon!r}")
    raw_tokens = block.get("tokens")
    if raw_tokens is not None and not isinstance(raw_tokens, dict):
        raise MappingShapeError(f"{context}.tokens: expected a mapping of value to token")
    tokens: dict[object, object] = {} if raw_tokens is None else raw_tokens
    hide = block.get("hide_values")
    hidden: list[object] = (
        [] if hide is None else _list(hide, f"{context}.hide_values", empty="list a value")
    )
    label = block.get("label")
    text = block.get("text")
    order = block.get("date_order")
    if order is not None and order not in DATE_ORDERS:
        raise MappingValueError(
            f"{context}.date_order: expected one of {', '.join(DATE_ORDERS)}, got {order!r}"
        )
    return Bubble(
        column=_nonblank(block.get("column"), f"{context}.column"),
        label=None if label is None else _text(label, f"{context}.label"),
        text=None if text is None else _template(text, f"{context}.text"),
        hide_values=tuple(_text(v, f"{context}.hide_values") for v in hidden),
        tokens={
            _text(k, f"{context}.tokens"): _token(v, f"{context}.tokens.{k}")
            for k, v in tokens.items()
        },
        due=due,
        date_order=order,
        label_colon=colon,
        blank=None if block.get("blank") is None else _nonblank(block["blank"], f"{context}.blank"),
        when=_when(block, context),
    )


def _row(raw: object, context: str) -> Row:
    block = _known_keys(raw, {"when", "items"}, context)
    items: list[Bubble | Badge] = []
    for index, item in enumerate(
        _list(block.get("items"), f"{context}.items", empty="a row needs at least one item"),
    ):
        where = f"{context}.items[{index}]"
        if isinstance(item, dict) and "badge" in item:
            items.append(_badge(_known_keys(item, {"badge"}, where)["badge"], f"{where}.badge"))
        else:
            items.append(_bubble(item, where))
    return Row(tuple(items), _when(block, context))


def _banner(raw: object, context: str) -> Banner:
    block = _known_keys(raw, {"label", "icon", "when", "rules"}, context)
    rules: list[BannerRule] = []
    for index, rule in enumerate(
        _list(block.get("rules"), f"{context}.rules", empty="a banner needs at least one rule"),
    ):
        where = f"{context}.rules[{index}]"
        entry = _known_keys(rule, {"when", "text"}, where)
        if entry.get("when") is None:
            raise MappingShapeError(f"{where}: 'when' is required on a rule")
        rules.append(BannerRule(
            parse_condition(entry["when"], f"{where}.when"),
            _nonblank(entry.get("text"), f"{where}.text"),
        ))
    return Banner(
        _nonblank(block.get("label"), f"{context}.label"),
        _nonblank(block.get("icon"), f"{context}.icon"),
        tuple(rules),
        _when(block, context),
    )


def _many[T](
    block: dict[str, object], key: str, context: str, parse: Callable[[object, str], T],
) -> tuple[T, ...]:
    if block.get(key) is None:
        return ()
    items = _list(block[key], f"{context}.{key}", empty="drop it or add an entry")
    return tuple(parse(item, f"{context}.{key}[{i}]") for i, item in enumerate(items))


def parse_header(raw: object, context: str, *, footer: bool = False) -> HeaderTree:
    """A header or footer component tree; an unknown key is refused by name.

    A footer has no title, icon tile or header bar, so those keys are refused on one.
    """
    block = _known_keys(
        raw, {"icon", "title", "subtitle", "chips", "chips_align", "rows", "banner"}, context,
    )
    if footer:
        for key in _HEADER_ONLY:
            if block.get(key) is not None:
                raise MappingShapeError(f"{context}.{key}: a footer takes no {key}; use a header")
    align = block.get("chips_align")
    if align is not None and align not in CHIP_ALIGNS:
        raise MappingValueError(
            f"{context}.chips_align: expected one of {', '.join(CHIP_ALIGNS)}, got {align!r}"
        )
    return HeaderTree(
        icon=None if block.get("icon") is None else _nonblank(block["icon"], f"{context}.icon"),
        title=None if block.get("title") is None else _title(block["title"], f"{context}.title"),
        subtitle=_many(block, "subtitle", context, _subtitle_part),
        chips=_many(block, "chips", context, _chip),
        chips_align=align,
        rows=_many(block, "rows", context, _row),
        banner=(
            None if block.get("banner") is None
            else _banner(block["banner"], f"{context}.banner")
        ),
    )
