# src/dbml_sharepoint/extract/run.py
"""One extraction, from a source file to a written project directory."""

import re
from dataclasses import dataclass
from pathlib import Path

from dbml_sharepoint.bundle import write_artifact
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.extract.decode import (
    Extraction,
    Unrecovered,
    decode_list,
    new_enum_registry,
)
from dbml_sharepoint.extract.emit import (
    DEFAULT_PREFIX,
    render_mapping,
    render_release,
    render_schema,
)
from dbml_sharepoint.extract.notes import render_notes
from dbml_sharepoint.extract.sources import Source, SourceError

#: Where the notes land, beside the two files they are about.
NOTES_RELPATH = Path("EXTRACTION-NOTES.md")

#: Where a formatter this tool would not re-derive is preserved. The same
#: directory the shipped families keep formatter JSON in, so a mapping can
#: reference one by path without moving it.
FORMATTING_RELDIR = Path("20-configure") / "formatting"

#: A DBML entity or project name. Anything else is refused rather than
#: sanitised into something that parses but is not what the operator asked
#: for.
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

@dataclass(frozen=True)
class Written:
    """What one run put on disk."""

    root: Path
    schema: Path
    mapping: Path
    release: Path
    notes: Path
    preserved: tuple[Path, ...] = ()


def extraction_from(source: Source, *, entity_names: dict[str, str]) -> Extraction:
    """Decode every list a source described.

    `entity_names` maps a source list's title to the DBML table name to give
    it. The caller resolves the names, because that is where a `--entity`
    flag and a derived-from-the-title default meet, and a default chosen in
    here would be invisible to the report.
    """
    enums = new_enum_registry()
    unrecovered: list[Unrecovered] = []
    extraction = Extraction(source=source.kind, absences=source.capabilities)
    for source_list in source.lists:
        entity = entity_names[source_list.title]
        extraction.entities.append(decode_list(
            source_list.fields,
            entity=entity,
            list_title=source_list.title,
            enums=enums,
            unrecovered=unrecovered,
            list_description=source_list.description,
        ))
        if not source_list.description:
            # Named up front because `build` refuses the schema for it
            # (entity_has_no_note), and an operator who reads the notes first
            # should not meet that as a surprise from the next command.
            unrecovered.append(Unrecovered(
                "list-description", entity,
                "the list has no description on the site, so the table has no "
                "`Note:`. `build` refuses a table without one, because the "
                "Note becomes the list's Description on the site. Write one "
                "saying what the list holds and who uses it.",
            ))
        if source_list.views:
            unrecovered.append(Unrecovered(
                "views", entity,
                f"{len(source_list.views)} view(s) were read from the live "
                "list. Recovering a `views:` declaration from CAML is a "
                "second inversion this tool does not attempt, so they are "
                "not in the mapping.",
            ))
        if source_list.content_type_formatter:
            unrecovered.append(Unrecovered(
                "form-formatting", entity,
                "the list form carries a custom formatter, which is not "
                "re-derived into a `form_formatting` declaration.",
            ))
    extraction.enums.extend(enums.declarations())
    extraction.unrecovered.extend(unrecovered)
    return extraction


def entity_name_for(title: str) -> str:
    """A DBML table name derived from a list title.

    Singular is not attempted. "Risks" becomes `Risks`, because guessing at
    English plurals produces `Statu` from `Status` and a wrong name is
    harder to notice than an ugly one. `--entity` overrides this.
    """
    words = re.split(r"[^A-Za-z0-9]+", title)
    name = "".join(word[:1].upper() + word[1:] for word in words if word)
    if not name or not name[0].isalpha():
        raise SourceError(
            f"cannot derive a table name from the list title {title!r}. "
            "Pass --entity to name it.",
        )
    return name


def project_name_for(entities: list[str]) -> str:
    """The DBML `Project` name, from the first entity, lowercased."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", entities[0]).lower()


def check_identifier(value: str, flag: str) -> str:
    if not _IDENTIFIER.match(value):
        raise SourceError(
            f"{flag} must be a DBML identifier (a letter, then letters, "
            f"digits or underscores); got {value!r}",
        )
    return value


def write(
    extraction: Extraction,
    root: Path,
    *,
    generated_at: str,
    prefix: str = DEFAULT_PREFIX,
    project: str = "",
) -> Written:
    """Write the family layout, then read every file back and verify it.

    Read-back is not ceremony here. The output is the input to `build`, and
    a truncated write produces a schema that parses to fewer columns than
    were extracted, which nothing downstream can tell from a list that
    genuinely has fewer columns.
    """
    project = project or project_name_for([e.name for e in extraction.entities])
    written = {
        root / SCHEMA_RELPATH: render_schema(extraction, project=project),
        root / MAPPING_RELPATH: render_mapping(extraction, prefix=prefix),
        root / RELEASE_RELPATH: render_release(
            source=extraction.source, generated_at=generated_at,
        ),
        root / NOTES_RELPATH: render_notes(extraction, generated_at=generated_at),
    }
    preserved = []
    for entity in extraction.entities:
        for column, formatter in entity.preserved_formatters.items():
            path = root / FORMATTING_RELDIR / f"{entity.name}.{column}.json"
            written[path] = formatter if formatter.endswith("\n") else formatter + "\n"
            preserved.append(path)

    for path, text in written.items():
        write_artifact(path, text)
    _verify(written)

    return Written(
        root=root,
        schema=root / SCHEMA_RELPATH,
        mapping=root / MAPPING_RELPATH,
        release=root / RELEASE_RELPATH,
        notes=root / NOTES_RELPATH,
        preserved=tuple(preserved),
    )


def _verify(written: dict[Path, str]) -> None:
    """Fail closed on anything that did not land as written."""
    for path, text in written.items():
        expected = text.replace("\r\n", "\n").replace("\r", "\n")
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise OSError(
                f"{path}: read back differently from what was written "
                f"({len(actual)} characters on disk, {len(expected)} written). "
                "Nothing here is safe to use; check the disk and rerun.",
            )
