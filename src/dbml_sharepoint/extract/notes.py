# src/dbml_sharepoint/extract/notes.py
"""EXTRACTION-NOTES.md: everything the schema and mapping do not say.

This file is the output, not a courtesy attached to it. A draft schema
that looks complete is worse than no schema, because the person modifying
the list has no way to see which of its columns were dropped or which of
its rules were not re-derived. So every absence is itemised here, grouped
by kind, with the subject it belongs to.

Written as Markdown that passes the repository's markdownlint config,
because it lands in an operator's project and a broken document is a
document nobody finishes reading.
"""

import textwrap
from collections import defaultdict

from dbml_sharepoint.extract.decode import Extraction, Unrecovered

#: Hard wrap, matching the repository's own markdown. The notes land in an
#: operator's project, where markdownlint's default line length applies to
#: them exactly as it does here.
_WIDTH = 79

#: A heading and an explanation per `Unrecovered.kind`. A kind with no
#: entry here still renders, under its own slug, so a new one added in
#: `decode.py` cannot disappear from the report by being forgotten.
#:
#: Each explanation is re-wrapped by `_wrap` before it is written, so the
#: line breaks below are the source file's and not the report's.
_KINDS: dict[str, tuple[str, str]] = {
    "list-description": (
        "Tables with no Note:",
        """A table's `Note:` becomes the list's Description on the site, and
        `build` refuses a table without one. Write it before the first
        build; nothing here could make it up for you.""",
    ),
    "calculated-formula-missing": (
        "Calculated columns with no formula in the field XML",
        """The column is in the schema, and `calculated_formulas` has no
        entry for it. `build` refuses a calculated column with no formula,
        so this shows up at the next gate; supply the formula there.""",
    ),
    "column-formatting": (
        "Column formatters kept verbatim",
        """These formatters are not ones this tool's style vocabulary
        produces, so no `column_formatting` declaration was invented for
        them. Each is written out beside the mapping under `formatting/`;
        reference the file from `column_formatting` to keep it, or
        re-declare it as a style.""",
    ),
    "form-visibility": (
        "Form visibility rules not re-declared",
        """`form_visibility` declares a new/existing gate and a single
        condition list. A formula outside that shape is reported rather
        than approximated, because a visibility rule that is nearly right
        hides the wrong field on somebody's form.""",
    ),
    "column-validation": (
        "Column validation rules not re-declared",
        """`column_validation` declares one comparison and a message. It has
        no raw-formula escape, so a formula outside that shape cannot be
        expressed and is reported here with its text.""",
    ),
    "views": (
        "Views not re-declared",
        """Views were read but not turned into a `views:` declaration.
        Recovering the declared-view DSL from stored CAML is a second
        inversion problem, and a view declaration that is nearly right
        reorders somebody's working list. Declare the views you want; the
        deploy leaves undeclared ones alone.""",
    ),
    "form-formatting": (
        "Form layouts not re-declared",
        """The list form's custom formatter is preserved on the live list
        because the deploy never touches an undeclared one, but it is not
        expressed as a `form_formatting` declaration here.""",
    ),
    "unsupported-field-type": (
        "Columns dropped: no DBML type",
        """These SharePoint field types have no equivalent this tool can
        deploy, so no column was emitted. The full element is quoted so you
        can decide what to do with each one.""",
    ),
    "lookup-target": (
        "Lookup columns dropped",
        """A lookup's target is a list GUID in the field XML. Resolving it
        needs the site's other lists, and a `ref` pointing at the wrong
        table is worse than none, so these were left out.""",
    ),
    "calculated-result-type": (
        "Calculated columns dropped: unknown result type",
        "The calculated types this tool deploys are text, number and date.",
    ),
    "empty-choice": (
        "Choice columns dropped: no choices",
        "A Choice field with no `<CHOICES>` gives nothing to build an enum from.",
    ),
    "number-precision": (
        "Number columns: int or number cannot be told apart",
        """SharePoint stores both DBML types as the same field with the same
        type kind, so the original declaration is not recoverable. `number`
        was emitted because it is the wider of the two; change any that
        should be `int`.""",
    ),
    "fill-in-choice": (
        "Choice columns that allow write-in values",
        """The forward build always deploys a Choice with FillInChoice false,
        so redeploying these removes the ability to type a value outside the
        list.""",
    ),
    "user-selection-mode": (
        "Person columns with a non-default selection mode",
        """`person` deploys as people-only. Nothing in this repository
        establishes what SharePoint's other selection modes map to, so the
        difference is reported rather than guessed at.""",
    ),
    "internal-name": (
        "Columns whose internal name cannot be recreated",
        """A deploy names a column from its DBML identifier, so an internal
        name containing an escaped character produces a DIFFERENT internal
        name on the way back. Rename the live column, or accept the new one
        and migrate the data.""",
    ),
    "renamed-column": (
        "Columns renamed after creation",
        """The column's internal name decodes to a different title than the one
        shown now. SharePoint freezes the internal name when a column is
        created, so a rename leaves the old name behind and anything still
        referencing it - a formula, a view, a formatter, a Power Automate
        flow - breaks when the list is rebuilt. Re-point those references,
        or accept the new internal name and migrate the data.""",
    ),
    "calculated-default": (
        "Defaults dropped from calculated columns",
        """A calculated column derives its value on every edit, so the
        forward build carries no default for one.""",
    ),
}

_HEADER = """\
# Extraction notes

Extracted from {source} on {generated_at}.

These files are a **draft**. Everything below is something the source did not
carry, or something this tool would not guess at. Read it before you edit the
schema, and read it again before you deploy anything.

"""

_CONTRACT = """\
## What was recovered

The list title and description, column names, DBML types, required flags,
defaults, choice sets as named enums, column descriptions, indexes, calculated
formulas rewritten into internal names, per-column validation, form visibility
and column formatting.

A recovered `column_formatting`, `form_visibility` or `column_validation`
declaration was checked by re-running the build's own generator over it and
comparing the result to what the live list actually stores. Anything that did
not reproduce byte for byte is in the list above rather than in the mapping.

## What a read does not carry

"""

#: The sentence that names the source, wrapped at render time because the
#: source name goes in the middle of it and its length varies.
_ABSENCE_LEAD = (
    "This is a scaffolding tool, not a lossless round-trip. Nothing below is "
    "recoverable from {source}, whether or not the list has it:"
)

_NEXT = """\
## Before you deploy

1. Set `prefix` in `mapping.yaml` to your project's prefix. The extracted
   value is a placeholder.
2. Check `versioning` and each entity's `base_template`. Both are declared
   values here, not readings.
3. Run `dbml-sharepoint build` and read every finding. A draft from an
   extraction is expected to produce some; each one names a decision the
   source could not make for you.
4. Deploy against a test site first. The generated scripts run against
   whatever site you paste them into.
"""


def render_notes(extraction: Extraction, *, generated_at: str) -> str:
    """The EXTRACTION-NOTES.md for one run."""
    parts = [_HEADER.format(source=extraction.source, generated_at=generated_at)]
    parts.append(_summary(extraction))

    grouped: dict[str, list[Unrecovered]] = defaultdict(list)
    for item in extraction.unrecovered:
        grouped[item.kind].append(item)

    if grouped:
        parts.append("## Not recovered\n\n")
        # `_KINDS` order first, so the missing `Note:` leads, then any kind
        # this file has no entry for, alphabetically.
        ordered = [kind for kind in _KINDS if kind in grouped]
        ordered += sorted(kind for kind in grouped if kind not in _KINDS)
        for kind in ordered:
            parts.append(_section(kind, grouped[kind]))

    parts.append(_CONTRACT)
    parts.append(_wrap(_ABSENCE_LEAD.format(source=extraction.source)))
    parts.append("\n\n")
    parts.append("".join(_bullet(absence) for absence in extraction.absences))
    parts.append("\n")
    parts.append(_NEXT)
    return "".join(parts)


def _wrap(text: str, *, indent: str = "") -> str:
    return textwrap.fill(
        " ".join(text.split()),
        width=_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _bullet(text: str, *, depth: int = 0) -> str:
    """One wrapped list item, continuation lines aligned under the text."""
    lead = "  " * depth
    body = _wrap(text, indent=f"{lead}  ")
    return f"{lead}- {body[len(lead) + 2:]}\n"


def _summary(extraction: Extraction) -> str:
    lines = ["## What was extracted\n\n"]
    for entity in extraction.entities:
        skipped = _plural(len(entity.skipped), "built-in")
        lines.append(_bullet(
            f"`{entity.name}` from the list {entity.list_title!r}: "
            f"{_plural(len(entity.columns), 'column')}, "
            f"{len(entity.indexes)} indexed, {skipped} skipped.",
        ))
        # Grouped by the test that fired, not one bullet per column. A read
        # of an ordinary list skips eighty-five built-ins, and eighty-five
        # bullets of boilerplate is how the lines that matter above them
        # stop being read.
        by_reason: dict[str, list[str]] = defaultdict(list)
        for name, reason in entity.skipped:
            by_reason[reason].append(name)
        for reason, names in sorted(by_reason.items()):
            lines.append(_bullet(
                f"skipped as {reason}: {', '.join(f'`{n}`' for n in names)}",
                depth=1,
            ))
    lines.append("\n")
    return "".join(lines)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _section(kind: str, items: list[Unrecovered]) -> str:
    heading, explanation = _KINDS.get(
        kind, (kind.replace("-", " ").capitalize(), ""),
    )
    lines = [f"### {heading}\n\n"]
    if explanation:
        lines.append(_wrap(explanation))
        lines.append("\n\n")
    for item in sorted(items, key=lambda i: i.subject):
        lines.append(_bullet(f"`{item.subject}`: {item.detail}"))
    lines.append("\n")
    return "".join(lines)
