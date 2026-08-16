# src/dbml_sharepoint/generators/rollbackgen.py
"""Render rollback.js."""

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env


def generate_rollback_js(
    *,
    schema: Schema,
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    generated_at: str,
) -> str:
    env = script_env()
    # Each entry carries the marker its list must show before rollback will
    # delete it. Built from the same helpers the deploy stamps with, so the
    # two cannot disagree about what this family's marker says.
    family = family_for(schema)
    # Children before parents: reverse of the deploy creation order.
    target_lists = [
        {
            "title": bundle.mapping.prefix + name,
            "expected_marker": marker_for(family, name),
        }
        for name in reversed(
            site_tables_in_order(schema, bundle.mapping.entities, site_role),
        )
    ]
    template = env.get_template("rollback.js.j2")
    return template.render(
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        target_lists=target_lists,
        generated_at=generated_at,
    )
