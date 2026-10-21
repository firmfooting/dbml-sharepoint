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


@dataclass(frozen=True)
class SubtitlePart:
    column: str | None = None
    text: str | None = None
    columns: tuple[str, ...] = ()
    when: Condition | None = None


@dataclass(frozen=True)
class LinkChip:
    text: str
    icon: str
    url: str | None = None
    url_column: str | None = None
    url_template: str | None = None
    when: Condition | None = None


@dataclass(frozen=True)
class Bubble:
    column: str
    label: str | None = None
    text: str | None = None
    hide_values: tuple[str, ...] = ()
    tokens: dict[str, str] = field(default_factory=dict)
    due: bool = False
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
    title: Title | None = None
    subtitle: tuple[SubtitlePart, ...] = ()
    chips: tuple[LinkChip, ...] = ()
    rows: tuple[Row, ...] = ()
    banner: Banner | None = None
