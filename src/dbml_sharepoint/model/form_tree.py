"""The typed nodes of a form.yaml header or footer component tree.

Split from the parser because the mapping types hold a tree, and the parser
reads the style vocabulary, which imports the mapping types.
"""

from dataclasses import dataclass, field

from dbml_sharepoint.model.conditions import Condition


@dataclass(frozen=True)
class Title:
    column: str
    blank: str
    when: Condition | None = None
    prefix: str | None = None  # static text before the value, shown only while there is a value


@dataclass(frozen=True)
class SubtitlePart:
    column: str | None = None
    text: str | None = None
    columns: tuple[str, ...] = ()
    fallback: str | None = None  # shown in place of `text` while a named column is empty
    when: Condition | None = None


@dataclass(frozen=True)
class LinkChip:
    text: str
    icon: str
    url: str | None = None
    url_column: str | None = None
    url_template: str | None = None
    title: str | None = None  # the tooltip, only when the author writes one
    when: Condition | None = None


@dataclass(frozen=True)
class Bubble:
    column: str
    label: str | None = None
    text: str | None = None
    hide_values: tuple[str, ...] = ()
    tokens: dict[str, str] = field(default_factory=dict)
    due: bool = False
    date_order: str | None = None  # dmy, mdy or ymd: how a computed date is written
    label_colon: bool = True  # False writes the label as given, with no colon added
    blank: str | None = None  # shown alone while the column is empty; without it the bubble hides
    when: Condition | None = None


@dataclass(frozen=True)
class Badge:
    text: str
    token: str
    when: Condition | None = None


@dataclass(frozen=True)
class Row:
    items: tuple[Bubble | Badge, ...]
    when: Condition | None = None


@dataclass(frozen=True)
class BannerRule:
    when: Condition
    text: str


@dataclass(frozen=True)
class Banner:
    label: str
    icon: str
    rules: tuple[BannerRule, ...]
    when: Condition | None = None


@dataclass(frozen=True)
class HeaderTree:
    icon: str | None = None
    title: Title | None = None
    subtitle: tuple[SubtitlePart, ...] = ()
    chips: tuple[LinkChip, ...] = ()
    chips_align: str | None = None  # top, middle or bottom, against the header bar
    rows: tuple[Row, ...] = ()
    banner: Banner | None = None
