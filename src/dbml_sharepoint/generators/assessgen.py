# src/dbml_sharepoint/generators/assessgen.py
"""Site-assessment generator: read-only assess.js + assess-manifest.md.

Derives a pack's deployment requirements from its schema+mapping and emits
a browser-console script that probes a target site for them across three
tiers (always-run enumerations, pack-driven attempt-probes, and a printed
not-assessable honesty block). STRICTLY read-only — see the read-only
guarantee test. Spec: docs/plans/2026-07-24-tenant-assessment-design.md.
"""

from dataclasses import dataclass
from typing import Any

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.analysis.permissions import requires_manage_permissions
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env


@dataclass(frozen=True)
class Requirement:
    key: str
    description: str
    level_on_fail: str  # BLOCKED | WARN | INFO


def assess_targets(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> dict[str, Any]:
    """The data-driven inputs the assess.js probes loop over.

    `list_markers` maps each declared list title to the exact provenance
    marker its Description must carry. It is IMPORTED from
    `analysis.list_description`, never re-spelled here or in the template: a
    second spelling would let assess.js quietly disagree with deploy.js about
    the same list, reporting drift on a description the deploy considers
    correct (or, worse, staying silent on one it does not).
    """
    prefix = bundle.mapping.prefix
    titles: list[str] = []
    templates: set[int] = set()
    table_names: list[str] = []
    # One family per schema, so it is resolved once rather than per list --
    # same as jsgen, which composes the descriptions this checks for.
    family = family_for(schema)
    markers: dict[str, str] = {}
    for table_name in site_tables_in_order(schema, bundle.mapping.entities, site_role):
        entity = bundle.mapping.entities[table_name]
        titles.append(prefix + table_name)
        templates.add(int(entity.base_template))
        table_names.append(table_name)
        markers[prefix + table_name] = marker_for(family, table_name)
    m = bundle.mapping
    perms = m.permissions
    versioning_on = bool(m.versioning_default.enable_versioning) or any(
        v.get("enable_versioning") for v in m.versioning_overrides.values()
    )
    return {
        "list_titles": titles,
        "list_markers": markers,
        "base_templates": sorted(templates),
        "declares_groups": bool(perms and perms.groups),
        "declares_seal": bool(m.seal_columns),
        "declares_prevent_deletion": bool(m.prevent_list_deletion),
        "declares_column_formatting": bool(m.column_formatting),
        "declares_form_formatting": bool(m.form_formatting),
        "declares_versioning": versioning_on,
        # Shared with manifestgen/jsgen's schema_json and deploy.js's own
        # live preflight, so the three cannot independently drift again --
        # see requires_manage_permissions's docstring and #166 item 5.
        "requires_manage_permissions": requires_manage_permissions(m, table_names),
    }


def derive_requirements(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[Requirement]:
    """The pack's site requirements, worst-case severity on probe failure."""
    t = assess_targets(schema, bundle, site_role)
    reqs: list[Requirement] = [
        Requirement("manage_lists_bit",
                    "Operator holds ManageLists on the site", "BLOCKED"),
        Requirement("site_not_locked",
                    "Site is not read-only / locked", "BLOCKED"),
    ]
    for template_id in t["base_templates"]:
        reqs.append(Requirement(
            f"list_template_{template_id}",
            f"Base template {template_id} is creatable on the web", "BLOCKED",
        ))
    for title in t["list_titles"]:
        reqs.append(Requirement(
            f"collision:{title}",
            f"List '{title}' is absent or a redeploy target (not a foreign list)",
            "BLOCKED",
        ))
    for title in t["list_markers"]:
        # WARN, never BLOCKED. A list whose Description an owner rewrote is
        # still a perfectly good list and deploying over it is safe -- the
        # deploy is what repairs it. What is broken is REPORTING: fleet
        # discovery enumerates Description, so between deploys that site
        # returns fewer rows and nothing knows it should have returned more.
        # Degraded is exactly that: deployable, but review it first.
        reqs.append(Requirement(
            f"provenance_marker:{title}",
            f"List '{title}' still carries the provenance marker fleet reporting finds it by",
            "WARN",
        ))
    if t["requires_manage_permissions"]:
        reqs.append(Requirement("manage_permissions_bit",
                                "Operator holds ManagePermissions", "BLOCKED"))
    if t["declares_groups"]:
        reqs.append(Requirement(
            "process_query",
            "CSOM ProcessQuery available (group owner correction)", "WARN"))
    if t["declares_seal"]:
        reqs.append(Requirement("sealed_surface",
                                "SP.Field.Sealed property surface present", "WARN"))
    if t["declares_prevent_deletion"]:
        reqs.append(Requirement(
            "allow_deletion_surface",
            "SP.List.AllowDeletion property surface present", "WARN"))
    if t["declares_column_formatting"]:
        reqs.append(Requirement(
            "custom_formatter_surface",
            "SP.Field.CustomFormatter property surface present", "WARN"))
    if t["declares_form_formatting"]:
        reqs.append(Requirement(
            "form_formatter_surface",
            "ClientFormCustomFormatter property surface present", "WARN"))
    if t["declares_versioning"]:
        reqs.append(Requirement(
            "version_trim_mode",
            "Service-managed version auto-trim does not override declared limits",
            "WARN"))
    return reqs


# Tier-3: items research confirmed are NOT assessable from operator site
# context. Shared verbatim by assess.js and assess-manifest.md.
NOT_ASSESSABLE: tuple[str, ...] = (
    ("Power Automate / Power Apps inventory (lives in Power Platform APIs, "
     "no SharePoint REST surface from site context)"),
    "Audit settings (SSOM-only; not exposed via CSOM/REST)",
    "Information-barrier segments and mode (tenant-admin only)",
    ("Authoritative tenant sharing capability and storage quota ceilings "
     "(tenant-admin SiteProperties)"),
    ("Retention POLICY coverage of the site (only inferable via the "
     "Preservation Hold Library signal)"),
    "Webhook subscription enumeration (bound to the creating app identity)",
    "Edit-form column-description suppression (SharePoint platform behaviour)",
    "[$Created] view-field resolution in formatters (tenant/locale dependent)",
    "Format-pane JSON display encoding (renders identically either way)",
)


def _render(template_name: str, **context: Any) -> str:
    return script_env().get_template(template_name).render(**context)


def generate_assess_js(
    *,
    schema: Schema,
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    generated_at: str,
) -> str:
    requirements = [
        {"key": r.key, "description": r.description, "level_on_fail": r.level_on_fail}
        for r in derive_requirements(schema, bundle, site_role)
    ]
    return _render(
        "assess.js.j2",
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        generated_at=generated_at,
        targets=assess_targets(schema, bundle, site_role),
        requirements=requirements,
        not_assessable=list(NOT_ASSESSABLE),
    )


def generate_assess_manifest(
    *,
    schema: Schema,
    bundle: MappingBundle,
    site_url: str,
    site_role: str,
) -> str:
    return _render(
        "assess-manifest.md.j2",
        site_url=site_url,
        prefix=bundle.mapping.prefix,
        requirements=derive_requirements(schema, bundle, site_role),
        targets=assess_targets(schema, bundle, site_role),
        not_assessable=list(NOT_ASSESSABLE),
    )
