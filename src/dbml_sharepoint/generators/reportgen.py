# src/dbml_sharepoint/generators/reportgen.py
"""Report-query generator: Power Query (M) and T-SQL views from the schema.

The same DBML + mapping that provisions the lists also describes how to
report on them. This module emits:

- one Power Query (M) query per list, ``OData.Feed`` against the list's
  REST endpoint, with lookup and person columns expanded to a join key plus
  display column, and column types applied from the deployer's own typemap.
  ``build`` knows the site (``--site-url``) and bakes it into every query,
  so a shipped bundle has nothing to configure; the standalone ``report``
  command knows no site and falls back to a ``SiteUrl`` text parameter;
- a single T-SQL script of ``CREATE OR ALTER VIEW`` statements (SQLCMD
  variables for the landing/report schemas): a typed view per list plus an
  ``_Enriched`` view joining each lookup to its display column, for lists
  landed in a warehouse by any extract process;
- guide.md with usage instructions and the Power BI relationship table
  derived from the DBML refs.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped here and listed in
guide.md. Person columns land differently per extract tool, so the SQL
views carry them as display-name text while the M queries expand both the
site-user id and display name.
"""

from pathlib import Path
from typing import Any

from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_DIR,
    REPORT_GUIDE,
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
) -> list[str]:
    """Write the reporting bundle under ``out/reporting/`` and return the
    POSIX relpaths written (for checksums.txt).

    Shared by the core and extension CLIs so the shipped reporting
    artifact set cannot drift between them: per-list Power Query (M)
    plus the dictionary/model/audit queries, the SQL views script,
    the reporting guide and the data dictionary.

    ``site_url`` is the deployment target, which ``build`` always has.
    Passing it bakes the site into every query, the SQL script and the
    guide, so the pack loads with nothing configured. It is optional only
    because ``report`` runs without a site at all.
    """
    reporting_dir = out / REPORT_DIR
    pq_dir = reporting_dir / "powerquery"
    sql_dir = reporting_dir / "sql"
    pq_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)
    dictionary_kwargs: dict[str, Any] = dict(
        release=release,
        generated_at=generated_at,
        source_schema=source_schema,
        source_mapping=source_mapping,
    )
    relpaths: list[str] = []
    queries = generate_powerquery(schema, bundle, site_role, site_url=site_url)
    queries.update(
        generate_dictionary_powerquery(
            schema, bundle, site_role, site_url=site_url, **dictionary_kwargs,
        ),
    )
    for filename, content in queries.items():
        write_artifact(pq_dir / filename, content)
        relpaths.append(f"reporting/powerquery/{filename}")
    write_artifact(
        sql_dir / REPORT_VIEWS_SQL,
        generate_sql_views(schema, bundle, site_role, site_url=site_url)
        + "\n"
        + generate_dictionary_sql(schema, bundle, site_role, **dictionary_kwargs),
    )
    write_artifact(
        reporting_dir / REPORT_GUIDE,
        generate_reporting_md(schema, bundle, site_role, site_url=site_url),
    )
    write_artifact(
        reporting_dir / REPORT_DICTIONARY,
        generate_data_dictionary(schema, bundle, site_role, **dictionary_kwargs),
    )
    relpaths += [
        f"{REPORT_DIR}/sql/{REPORT_VIEWS_SQL}",
        f"{REPORT_DIR}/{REPORT_GUIDE}",
        f"{REPORT_DIR}/{REPORT_DICTIONARY}",
    ]
    return relpaths
