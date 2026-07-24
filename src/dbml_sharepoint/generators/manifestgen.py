# src/dbml_sharepoint/generators/manifestgen.py
"""Render deploy-manifest.md."""

import json
from typing import Any

from dbml_sharepoint.analysis.phases import phase_numbers
from dbml_sharepoint.analysis.validator import Finding
from dbml_sharepoint.extension import ManifestExtras
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env


def generate_manifest(
    *,
    schema_json: dict[str, Any],
    findings: list[Finding],
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    source_mtime: str,
    generated_at: str,
    manifest_extras: ManifestExtras | None = None,
) -> str:
    template = script_env().get_template("manifest.md.j2")

    counts = {
        "lists": len(schema_json["lists"]),
        "fields_phase1": sum(len(lst["fields_phase1"]) for lst in schema_json["lists"]),
        "phase2_lookups": len(schema_json["phase2_lookups"]),
        "indexed": len(schema_json["indexed_columns"]),
        "views": len(schema_json["views"]),
        "formatted_columns": sum(
            1
            for lst in schema_json["lists"]
            for f in lst["fields_phase1"]
            if f.get("custom_formatter") is not None
        ),
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
    }

    formatted_columns = [
        {"list": lst["title"], "column": f["title"]}
        for lst in schema_json["lists"]
        for f in lst["fields_phase1"]
        if f.get("custom_formatter") is not None
    ]

    def _form_parts(client_formatter: str) -> str:
        keys = list(json.loads(client_formatter))
        order = ["headerJSONFormatter", "bodyJSONFormatter", "footerJSONFormatter"]
        return ", ".join(
            key.removesuffix("JSONFormatter")
            for key in sorted(keys, key=order.index)
        )

    form_formatting = [
        {"list": row["list"], "parts": _form_parts(row["client_form_custom_formatter"])}
        for row in schema_json["form_formatting"]
    ]

    # Reviewer-facing filter/sort/group summary from the declared DSL (the
    # schema_json rows carry generated CAML, which is not review material).
    def _view_summary(list_title: str, view_title: str) -> str:
        prefix = bundle.mapping.prefix
        entity = list_title.removeprefix(prefix)
        for declared in bundle.mapping.views.get(entity, []):
            if declared.title != view_title:
                continue
            parts: list[str] = []
            if declared.where:
                parts.append("filter: " + " AND ".join(
                    f"{cond.field} {cond.op}"
                    + ("" if cond.op in ("is_null", "is_not_null") else f" {cond.value}")
                    for cond in declared.where
                ))
            if declared.sort:
                parts.append("sort: " + ", ".join(
                    f"{entry.field} {entry.direction}" for entry in declared.sort
                ))
            if declared.group_by is not None:
                parts.append(f"group by {declared.group_by.field}")
            return "; ".join(parts)
        return ""

    views = [
        {**view, "summary": _view_summary(view["list"], view["title"])}
        for view in schema_json["views"]
    ]
    # Polymorphic patterns are data-driven: unprefixed entity names in the mapping, rendered
    # with the prefix so the manifest names the physical SP list.
    polymorphic = [
        {
            "list": bundle.mapping.prefix + p.list,
            "field": p.field,
            "discriminator": p.discriminator,
        }
        for p in bundle.mapping.polymorphic_patterns
    ]
    extras = manifest_extras if manifest_extras is not None else ManifestExtras()
    return template.render(
        phase_num=phase_numbers(),
        source_dbml=source_dbml,
        source_mtime=source_mtime,
        site_url=site_url,
        site_role=site_role,
        release=release,
        generated_at=generated_at,
        counts=counts,
        findings=findings,
        polymorphic=polymorphic,
        lists=schema_json["lists"],
        phase2=schema_json["phase2_lookups"],
        indexed=schema_json["indexed_columns"],
        views=views,
        formatted_columns=formatted_columns,
        form_formatting=form_formatting,
        retention=bundle.retention_list_defaults,
        prefix=bundle.mapping.prefix,
        schema_json=schema_json,
        seed_items=schema_json["seed_items"],
        extra_sections=extras.sections,
        extra_warnings=extras.warnings,
    )
