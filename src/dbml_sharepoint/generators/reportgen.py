# src/dbml_sharepoint/generators/reportgen.py
"""The reporting pack: one composition and one write policy.

The pack is six artifacts from three renderers: the per-list and loadable
Power Query files from ``report_m``, the SQL views script from
``report_sql``, and the guide and data dictionary from ``report_md``. What
each one carries is decided in ``analysis/reporting``. This module decides
only which files exist, what they are called and in what order they are
written.

:func:`render_reporting` is the composition, and it returns text rather
than writing it. ``build`` (through :func:`emit_reporting`) and the
standalone ``report`` command both take the pack from it, so the two
cannot drift in what they ship, and both write only after every artifact
has rendered, so a generator refusal cannot leave a half-written set
behind with the stale files outliving the error on the terminal. The
``report`` command used to be a second copy of this composition with its
own write policy (#171).
"""

from pathlib import Path

from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_DIR,
    REPORT_GUIDE,
    REPORT_POWERQUERY_DIR,
    REPORT_SQL_DIR,
    REPORT_VIEWS_SQL,
    write_artifact,
)
from dbml_sharepoint.generators.report_m import (
    generate_dictionary_powerquery,
    generate_powerquery,
)
from dbml_sharepoint.generators.report_md import (
    generate_data_dictionary,
    generate_reporting_md,
)
from dbml_sharepoint.generators.report_sql import (
    generate_dictionary_sql,
    generate_sql_views,
)
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release


def render_reporting(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
    site_url: str | None = None,
    time_zone: str | None = None,
) -> dict[str, str]:
    """The whole reporting pack as {relative path: content}, nothing written.

    Paths are POSIX and relative to the pack's root: ``powerquery/<name>.pq``
    for every list query, the users dimension and the three loadable
    tables, then ``sql/views.sql``, ``guide.md`` and ``data-dictionary.md``.
    That order is the order :func:`emit_reporting` writes and reports them
    in, which ``checksums.txt`` sorts anyway.

    ``site_url`` is the deployment target, which ``build`` always has.
    Passing it bakes the site into every query, the SQL script and the
    guide, so the pack loads with nothing configured. It is optional only
    because ``report`` runs without a site at all.

    ``time_zone`` is the site's IANA zone, which both commands require:
    every list query then carries its daylight-saving transitions and the
    site-date helpers, and the guide and dictionary describe them. Optional
    here only so the composition stays callable from a library without one.

    Raises ``ValueError`` where a renderer refuses the schema: an unhandled
    field kind, a multi-value member the export cannot split back, a
    projection the schema lacks, a zone the database does not declare.
    Nothing has been written when it does, which is the point of returning
    text.
    """
    queries = generate_powerquery(
        schema, bundle, site_role, site_url=site_url, time_zone=time_zone,
    )
    queries.update(generate_dictionary_powerquery(
        schema, bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=source_schema, source_mapping=source_mapping,
        site_url=site_url, time_zone=time_zone,
    ))
    pack = {
        f"{REPORT_POWERQUERY_DIR}/{filename}": content
        for filename, content in queries.items()
    }
    pack[f"{REPORT_SQL_DIR}/{REPORT_VIEWS_SQL}"] = (
        generate_sql_views(
            schema, bundle, site_role, site_url=site_url, time_zone=time_zone,
        )
        + "\n"
        + generate_dictionary_sql(
            schema, bundle, site_role,
            release=release, generated_at=generated_at,
            source_schema=source_schema, source_mapping=source_mapping,
            time_zone=time_zone,
        )
    )
    pack[REPORT_GUIDE] = generate_reporting_md(
        schema, bundle, site_role, site_url=site_url, time_zone=time_zone,
    )
    pack[REPORT_DICTIONARY] = generate_data_dictionary(
        schema, bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=source_schema, source_mapping=source_mapping,
        time_zone=time_zone,
    )
    return pack


def emit_reporting(
    out: Path,
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
    site_url: str | None = None,
    time_zone: str | None = None,
) -> list[str]:
    """Write the reporting pack under ``out/reporting/`` and return the
    POSIX relpaths written, for checksums.txt.

    Shared by the core and extension CLIs so the shipped reporting artifact
    set cannot drift between them. :func:`render_reporting` is the
    composition; this is the write policy, and it writes nothing until
    every artifact has rendered.
    """
    pack = render_reporting(
        schema, bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=source_schema, source_mapping=source_mapping,
        site_url=site_url, time_zone=time_zone,
    )
    relpaths: list[str] = []
    for relpath, content in pack.items():
        write_artifact(out / REPORT_DIR / relpath, content)
        relpaths.append(f"{REPORT_DIR}/{relpath}")
    return relpaths
