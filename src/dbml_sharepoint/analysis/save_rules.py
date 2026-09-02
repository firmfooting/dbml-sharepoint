"""Where a save rule that compares a date with the clock is enforced.

MEASURED 2026-09-02 on a live tenant in "(UTC+10:00) Canberra, Melbourne,
Sydney", at 10:57 local, with the server clock correct:

- A date-only column with default formula `=TODAY()` filled 1 September
  while the site's date was the 2nd; `=[D]<=TODAY()` refused the 2nd as
  "in the future". `=[W]<=NOW()` accepted an instant 20 hours before now
  and refused one 12 hours before. The formula clock sits 16 to 20 hours
  behind the site: a western wall clock read as site-local time, and no
  site setting moves it.
- In a LIST validation formula, `[D]<=[Modified]` accepted today's
  site-local midnight and refused tomorrow's and a 30-day control; an
  update to five seconds before the save was accepted while an hour after
  was refused. SharePoint stamps Created and Modified for the save in
  progress before it evaluates the list formula, so `[Modified]` is the
  save's own instant, in site-local time, on create and on update.
- A COLUMN validation formula may reference only its own column:
  "The formula cannot refer to another column."
- Through the modern form at 11:49 local, with the site zone unchanged for
  over an hour: a date-only column under `=[DT]<=TODAY()` still refused
  today, so the lag is not a setting propagating; under the list rule
  `=OR(ISBLANK([DM]),[DM]<=[Modified])` the form saved today and refused
  tomorrow with the rule's own message. The form path behaves as REST did.
- The lag is the formula engine's alone. At 12:40 local a CAML `<Today/>`
  on a date-only column matched the 2 September rows and not the 1
  September ones, `<Today OffsetDays='-1'/>` matched the 1 September ones,
  `<Today/>` with IncludeTimeValue was the current instant, and a `[today]` column
  default filled the current instant, while a `=TODAY()` default formula
  on the same item filled 1 September, and the modern form's New form
  prefilled the same `[today]` default with the site's date. Views and
  dynamic defaults need no change; the signed-in user's profile regional
  settings were empty.
- The paths the rule had not been through (save-instant-paths probe, 19:59
  local): under `OR(ISBLANK([TR]),[TR]<=[Modified])` with TR a date-only
  column carrying the dynamic default `[today]`, five bare REST creates and
  one through the form's own endpoint all saved, the default and Modified
  stamped to the same second, so the default does not race the rule. The
  modern form's Edit saved today and refused tomorrow with the rule's
  message; grid view saved today on one row and on four; the New form
  prefilled the date-only default with the site's date (stored as
  site-local midnight) and the datetime default with the current minute,
  and saved. Not yet observed: grid view refusing tomorrow, and the bulk
  Edit pane. SharePoint reads `[DM]<=[Modified]` back as `DM<=Modified`.

So a column rule that compares a date with `today` or `now` cannot be
exact where it was declared, and is hoisted onto the list rule here. The
renderer then compares against `[Modified]`. Shared by the deployer, the
manifest and the validator, so the three cannot disagree about which
rules moved.
"""

from dbml_sharepoint.analysis.conditions import leaves
from dbml_sharepoint.analysis.typemap import DATE_TYPES, NOW_SENTINEL, TODAY_SENTINEL
from dbml_sharepoint.model.conditions import Condition, Group, Leaf
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListValidation,
    Mapping,
)


def compares_with_the_clock(condition: Condition, column_types: dict[str, str]) -> bool:
    """Whether any leaf compares a date or datetime column with `today` or
    `now`. The literal word on a text column is a word."""
    for leaf in leaves(condition):
        if column_types.get(leaf.field) not in DATE_TYPES:
            continue
        value = leaf.value
        if isinstance(value, str) and (TODAY_SENTINEL.match(value) or NOW_SENTINEL.match(value)):
            return True
    return False


def hoisted_columns(
    section: EntitySection[ColumnValidation] | None, column_types: dict[str, str],
) -> list[tuple[str, ColumnValidation]]:
    """The column rules that move to the list, in declaration order."""
    if section is None:
        return []
    return [
        (column, rule)
        for column, rule in section.columns.items()
        if compares_with_the_clock(rule.when, column_types)
    ]


def _conjuncts(condition: Condition) -> list[Condition]:
    """A top-level AND's children, or the condition itself; AND is associative."""
    if isinstance(condition, Group) and condition.kind == "all_of":
        return list(condition.children)
    return [condition]


def _accepts_a_blank(column: str, condition: Condition) -> bool:
    """Whether a rule already passes a blank: a top-level OR with an
    `is_null` test on its own column."""
    return (
        isinstance(condition, Group)
        and condition.kind == "any_of"
        and any(
            isinstance(child, Leaf) and child.field == column and child.op == "is_null"
            for child in condition.children
        )
    )


def effective_list_validation(
    mapping: Mapping, entity: str, column_types: dict[str, str],
) -> ListValidation | None:
    """The list rule the deployer writes: the declared one, with every
    hoisted column rule joined by AND and each hoisted rule guarded so a
    blank never fails it, as a column rule never fires on a blank. Messages
    are joined in the same order, the declared list rule's first.

    The join spends no characters it does not need, because the result is
    measured against SharePoint's formula limit: a declared AND contributes
    its conjuncts rather than nesting, and a rule that already accepts a
    blank is not guarded twice."""
    declared = mapping.list_validation.get(entity)
    hoisted = hoisted_columns(mapping.column_validation.get(entity), column_types)
    if not hoisted:
        return declared
    parts: list[Condition] = []
    if declared is not None:
        parts += _conjuncts(declared.when)
    for column, rule in hoisted:
        if _accepts_a_blank(column, rule.when):
            parts.append(rule.when)
        else:
            parts.append(Group("any_of", (Leaf(field=column, op="is_null"), rule.when)))
    messages = ([declared.message] if declared is not None else []) + [
        rule.message for _, rule in hoisted
    ]
    return ListValidation(when=Group("all_of", tuple(parts)), message=" ".join(messages))
