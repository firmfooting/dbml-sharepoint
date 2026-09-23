# src/dbml_sharepoint/generators/assessgen.py
"""Site-assessment generator: read-only assess.js + assess-manifest.md.

Derives a pack's deployment requirements from its schema+mapping and emits
a browser-console script that probes a target site for them across three
tiers (always-run enumerations, pack-driven attempt-probes, and a printed
not-assessable honesty block). STRICTLY read-only. See the read-only
guarantee test. Spec: docs/plans/2026-07-24-tenant-assessment-design.md.
"""

from dataclasses import dataclass
from typing import Any

from dbml_sharepoint.analysis.clock_usage import clock_usage
from dbml_sharepoint.analysis.group_description import marker_for_group
from dbml_sharepoint.analysis.limits import (
    INDEX_CHANGE_CEILING,
    LIST_VIEW_THRESHOLD,
)
from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.analysis.permissions import requires_manage_permissions
from dbml_sharepoint.analysis.rendered_columns import rendered_columns
from dbml_sharepoint.analysis.resolve import ResolvedMapping
from dbml_sharepoint.analysis.role_definition_description import marker_for_level
from dbml_sharepoint.analysis.typemap import map_column
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, Table
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env


@dataclass(frozen=True)
class Requirement:
    key: str
    description: str
    level_on_fail: str  # BLOCKED | WARN | INFO


def _declared_unique_columns(
    table: Table, enum_names: set[str], cross_site_cols: set[str],
) -> list[str]:
    """Internal names of the columns this table's deploy declares unique.

    Asked through `map_column`, the mapper whose `unique` the deploy's field
    bodies read, so assess cannot disagree with the constraint the deploy will
    actually send. The built-in Title is the one column that never reaches the
    field-body builder: `jsgen._title_patch` takes `col.unique` straight off
    the column, and this follows it. Cross-site columns are skipped because
    the active extension builds their bodies and core cannot know what it
    declares. `test_assess_targets_name_the_columns_the_deploy_declares_unique`
    holds the two spellings equal.
    """
    names: list[str] = []
    for col in table.columns:
        if col.name in cross_site_cols:
            continue
        if col.name == "Id" and col.is_pk and col.is_auto_increment:
            continue
        if col.name == "Title":
            if col.unique:
                names.append("Title")
        elif map_column(col, enum_names).unique:
            names.append(col.name)
    return names


def assess_targets(
    schema: Schema, bundle: MappingBundle, site_role: str, *, resolved: ResolvedMapping,
) -> dict[str, Any]:
    """The data-driven inputs the assess.js probes loop over.

    `list_markers` pairs each declared list title with the exact provenance
    marker its Description must carry. Pairs rather than a mapping, because
    the template emits this as a JavaScript object literal and a list titled
    `__proto__` would then set the prototype instead of becoming a key. It is
    IMPORTED from
    `analysis.list_description`, never re-spelled here or in the template: a
    second spelling would let assess.js quietly disagree with deploy.js about
    the same list, reporting drift on a description the deploy considers
    correct (or, worse, staying silent on one it does not).

    `list_view_threshold` and `index_change_ceiling` are the two list-size
    ceilings the item-count probe reports against. They travel in the payload
    for the same reason: the emitted script quotes both numbers to the
    operator and reads them from `analysis.limits` rather than spelling them.
    """
    # Fails closed as the strict `declared_folders`/`declared_groups` did
    # before this read anything: assess.js must never silently omit a
    # declared group or folder it should be probing for.
    #
    # Mapping-wide rather than scoped to this site role, which is wider than
    # those resolvers were, for the reason `jsgen.build_schema_json` gives at
    # its own call: the emitted script runs against a live site, and a
    # misspelled `from_enum` anywhere in the file is evidence about the file.
    # `report_md` stays role-scoped because it only writes documentation.
    resolved.require_resolved()
    m = bundle.mapping
    by_name = {table.name: table for table in schema.tables}
    cross_site_keys = m.cross_site_keys()
    titles: list[str] = []
    templates: set[int] = set()
    table_names: list[str] = []
    # One family per schema, so it is resolved once rather than per list --
    # same as jsgen, which composes the descriptions this checks for.
    family = family_for(schema)
    # Pairs, not a mapping: emitted as a JS object literal, a title of
    # `__proto__` sets the prototype instead of creating an own property,
    # and the marker check then finds nothing and stays silent.
    markers: list[tuple[str, str]] = []
    # [[list title, [[internal name, declared display title], ...]], ...] for
    # every column whose display title differs from its internal name. Pairs
    # for the same reason `markers` is: emitted as a JS object literal, a
    # column named `__proto__` would set the prototype instead of becoming a
    # key, and the check would then compare nothing and stay silent.
    #
    # Only the DIFFERENT ones. A site where every column displays under its
    # internal name has nothing to drift, and carrying the identities would
    # roughly double this payload for no check.
    display_titles: list[list[Any]] = []
    # [[new title, [[previous title, previous marker], ...]], ...], lists
    # rather than tuples so the Python side compares equal to the JSON.
    renames: list[list[Any]] = []
    # [[library title, [folder, ...]], ...] for every library that declares
    # folders: the assessment checks nothing stands where a folder will go.
    library_folders: list[list[Any]] = []
    library_roots: list[list[str]] = []
    # [[list title, [internal name, ...]], ...] in DECLARATION order, for
    # every list holding at least one column declared unique. Pairs for the
    # same reason `markers` is.
    unique_columns: list[list[Any]] = []
    enum_names = {enum.name for enum in schema.enums}
    for table_name in site_tables_in_order(schema, bundle.mapping.entities, site_role):
        entity = bundle.mapping.entities[table_name]
        titles.append(bundle.mapping.list_title(table_name))
        entity_folders = resolved.folders[table_name]
        if entity.is_library and entity_folders:
            library_folders.append(
                [bundle.mapping.list_title(table_name), list(entity_folders)],
            )
        if entity.internal_name:
            library_roots.append([bundle.mapping.list_title(table_name), entity.internal_name])
        previous = bundle.mapping.previous_titles(table_name)
        if previous:
            renames.append([
                bundle.mapping.list_title(table_name),
                [[title, marker_for(family, name)] for title, name in previous],
            ])
        templates.add(int(entity.base_template))
        table_names.append(table_name)
        markers.append((bundle.mapping.list_title(table_name), marker_for(family, table_name)))
        table = by_name.get(table_name)
        if table is not None:
            # Declared columns only. A lookup PROJECTION is renamed by the
            # deploy too and can drift the same way, but the set of projection
            # names lives on the validator's context, which a generator may
            # not import from, and duplicating how they are spelled here is
            # exactly the drift `analysis/joins.py` exists to prevent. Worth a
            # shared helper when somebody needs it; not worth a second
            # spelling now.
            declared = [
                [column, m.display_name_for(table_name, column)]
                for column in sorted(rendered_columns(
                    table,
                    {c for (e, c) in cross_site_keys if e == table_name},
                ))
                if m.display_name_for(table_name, column) != column
            ]
            if declared:
                display_titles.append([bundle.mapping.list_title(table_name), declared])
            unique = _declared_unique_columns(
                table, enum_names,
                {c for (e, c) in cross_site_keys if e == table_name},
            )
            if unique:
                unique_columns.append([bundle.mapping.list_title(table_name), unique])
    m = bundle.mapping
    perms = m.permissions
    site_groups = resolved.groups
    # [[current name, [[previous name, previous marker], ...]], ...] for
    # every level and group that has previous names, the same shape as
    # `renames` above so one assessment loop serves all three.
    level_renames: list[list[Any]] = [
        [lvl.name, [[p, marker_for_level(family, p)] for p in lvl.previous_names]]
        for lvl in (perms.levels if perms else [])
        if lvl.previous_names
    ]
    group_renames: list[list[Any]] = [
        [grp.name, [[p, marker_for_group(p, family)] for p in grp.previous_names]]
        for grp in site_groups
        if grp.previous_names
    ]
    # Does any list THIS RUN provisions end up with versioning on? Asked
    # through `versioning_for`, the same merge jsgen deploys from.
    #
    # It used to be `default.enable_versioning or any(override.get(
    # "enable_versioning"))`, which was wrong twice over and in the direction
    # that reads as harmless. The `any` looked at EVERY entity's override,
    # including entities belonging to another site role and so absent from
    # this script; and it read the raw override with bare truthiness, so a
    # YAML `"false"` counted as on. Both made assess.js probe for a version
    # surface on a site where nothing versions -- a WARN with nothing behind
    # it, which is how a warning stops meaning anything.
    versioning_on = any(m.versioning_for(name).enable_versioning for name in table_names)
    return {
        # Whether anything this run ships reads `today` on the site: a view
        # filter's <Today/>, a column's [today] default, a validation rule.
        # The site's zone governs storage, display and the view windows;
        # validation rules compare against [Modified] since 2026-09-02, and
        # TODAY() itself ran 16 to 20 hours behind the site (see `time_zone`
        # in _assess_body.js.j2).
        "uses_today": clock_usage(schema, m, table_names).uses_today,
        "list_titles": titles,
        "list_markers": markers,
        "list_display_titles": display_titles,
        "list_unique_columns": unique_columns,
        "list_renames": renames,
        "level_renames": level_renames,
        "group_renames": group_renames,
        "base_templates": sorted(templates),
        "library_folders": library_folders,
        "library_roots": library_roots,
        # The two list-size ceilings the item-count probe reports against,
        # carried in the payload so the template spells neither number and
        # cannot disagree with `analysis.limits`.
        "list_view_threshold": LIST_VIEW_THRESHOLD,
        "index_change_ceiling": INDEX_CHANGE_CEILING,
        "declares_groups": bool(site_groups),
        "declares_seal": bool(m.seal_columns),
        "declares_prevent_deletion": bool(m.prevent_list_deletion),
        "declares_column_formatting": bool(m.column_formatting),
        "declares_form_formatting": bool(m.form_formatting),
        "declares_versioning": versioning_on,
        # Shared with manifestgen/jsgen's schema_json and deploy.js's own
        # live preflight, so the three cannot independently drift again --
        # see requires_manage_permissions's docstring and #166 item 5.
        "requires_manage_permissions": requires_manage_permissions(
            resolved, table_names,
        ),
    }


def derive_requirements(
    schema: Schema, bundle: MappingBundle, site_role: str, *, resolved: ResolvedMapping,
) -> list[Requirement]:
    """The pack's site requirements, worst-case severity on probe failure."""
    t = assess_targets(schema, bundle, site_role, resolved=resolved)
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
    for title in t["list_titles"]:
        # A requirement key, because only one can degrade the verdict: the
        # verdict loop walks REQUIREMENTS and skips a key with no finding,
        # which is also how an absent list reports no size at all.
        #
        # WARN and never BLOCKED. See `INDEX_CHANGE_CEILING` for the two
        # Microsoft sources that disagree about what happens over the larger
        # band, and for what would license BLOCKED.
        reqs.append(Requirement(
            f"item_count:{title}",
            f"Existing list '{title}' is under the {LIST_VIEW_THRESHOLD:,}-item "
            f"list view threshold",
            "WARN",
        ))
    for title, root in t["library_roots"]:
        reqs.append(Requirement(
            f"library_root:{title}",
            f"Existing library '{title}' has the declared immutable URL name '{root}'",
            "BLOCKED",
        ))
    for title, folders in t["library_folders"]:
        # A file standing where a folder is declared stops the folder phase,
        # so it is known before the paste rather than part-way through it.
        reqs.append(Requirement(
            f"folder_shape:{title}",
            f"Each declared folder of '{title}' ({', '.join(folders)}) is absent "
            f"or a folder, not a file of that name",
            "BLOCKED",
        ))
    for title, columns in t["list_unique_columns"]:
        # #550 made a declared `unique` actually deploy its constraint, so a
        # list provisioned before that fix holds the column unconstrained and
        # the next field phase asks for the constraint over data that never
        # carried it. Asked here because deploy's own preflight says it before
        # any write but does not stop the run, so by the time the field phase
        # asks, the rename, security, logging and list phases have written.
        #
        # WARN and never BLOCKED. What SharePoint does with that transition
        # over existing duplicate values is not established, so refusing a
        # deploy on it would be a rule stronger than anything measured.
        reqs.append(Requirement(
            f"pending_unique:{title}",
            f"Columns of '{title}' declared unique ({', '.join(columns)}) already "
            f"carry EnforceUniqueValues, so the next deploy asks for no "
            f"constraint over existing data",
            "WARN",
        ))
    for title, _marker in t["list_markers"]:
        # Ownership is required before ordinary deploy may reconcile an
        # existing list. A missing marker cannot be repaired automatically,
        # because writing it would manufacture the evidence rollback trusts.
        reqs.append(Requirement(
            f"provenance_marker:{title}",
            f"Existing list '{title}' carries this declaration's exact provenance marker",
            "BLOCKED",
        ))
    for name, _previous in t["level_renames"]:
        reqs.append(Requirement(
            f"rename_level:{name}",
            f"Previous names of permission level '{name}' are absent, or exactly one "
            f"carries its exact previous marker while '{name}' is absent",
            "BLOCKED",
        ))
    for name, _previous in t["group_renames"]:
        reqs.append(Requirement(
            f"rename_group:{name}",
            f"Previous names of site group '{name}' are absent, or exactly one "
            f"carries its exact previous marker while '{name}' is absent",
            "BLOCKED",
        ))
    for title, _previous in t["list_renames"]:
        # The rename decision, predicted before any write: exactly one
        # previous title carrying its own marker, and the current title
        # absent, is the only shape the deploy will rename.
        reqs.append(Requirement(
            f"rename:{title}",
            f"Previous titles of '{title}' are absent, or exactly one carries its "
            f"exact previous marker while '{title}' is absent",
            "BLOCKED",
        ))
    if t["uses_today"]:
        reqs.append(Requirement(
            "time_zone",
            "Site regional time zone is the users' zone (dates are stored and "
            "shown in it, and the pack's `today` windows are read against its day)",
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
    resolved: ResolvedMapping,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    generated_at: str,
) -> str:
    requirements = [
        {"key": r.key, "description": r.description, "level_on_fail": r.level_on_fail}
        for r in derive_requirements(schema, bundle, site_role, resolved=resolved)
    ]
    return _render(
        "assess.js.j2",
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        generated_at=generated_at,
        targets=assess_targets(schema, bundle, site_role, resolved=resolved),
        requirements=requirements,
        not_assessable=list(NOT_ASSESSABLE),
    )


def generate_assess_manifest(
    *,
    schema: Schema,
    bundle: MappingBundle,
    resolved: ResolvedMapping,
    site_url: str,
    site_role: str,
) -> str:
    return _render(
        "assess-manifest.md.j2",
        site_url=site_url,
        prefix=bundle.mapping.prefix,
        requirements=derive_requirements(schema, bundle, site_role, resolved=resolved),
        targets=assess_targets(schema, bundle, site_role, resolved=resolved),
        not_assessable=list(NOT_ASSESSABLE),
    )
