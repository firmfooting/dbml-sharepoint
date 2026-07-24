"""Command-line interface for dbml-sharepoint."""

import datetime as dt
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.bundle import SeedRequiresDemoItemsError, clear_generated, emit_bundle
from dbml_sharepoint.extension import SiteContext, resolve_extension
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_powerquery,
    generate_reporting_md,
    generate_sql_views,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

app = typer.Typer(
    name="dbml-sharepoint",
    help="Generic DBML → SharePoint browser-paste deploy.js generator.",
    no_args_is_help=True,
)

# Empty schema view used to render a findings-only manifest when validation
# fails: build_schema_json cannot run safely on an invalid schema.
_EMPTY_SCHEMA_JSON: dict[str, Any] = {
    "lists": [],
    "phase2_lookups": [],
    "indexed_columns": [],
    "views": [],
    "form_formatting": [],
    "permission_levels": [],
    "groups": [],
    "list_assignments": [],
    "seed_items": [],
}


def validate_site_url(site_url: str) -> None:
    """Reject a malformed or non-https ``--site-url`` at parse time (A5).

    The URL is interpolated into the generated deploy.js (as ``SITE_URL`` and in
    the site-match preflight comparison), so it must be a well-formed absolute
    ``https://`` URL with a host. Catches typos (``http://``, a bare path, a
    missing host) before the operator pastes into a privileged console. Shared
    by the core CLI and any extension project CLIs that compose it. Raises
    ``typer.BadParameter`` (exit 2) on failure.
    """
    parsed = urlparse(site_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise typer.BadParameter(
            f"--site-url must be an absolute https:// URL with a host "
            f"(got {site_url!r}).",
        )


@app.command()
def build(
    schema: Path = typer.Option(..., help="Path to the DBML schema file."),
    mapping: Path = typer.Option(..., help="Path to schema/sharepoint-mapping.yaml."),
    release: Path = typer.Option(..., help="Path to release.yaml."),
    site_url: str = typer.Option(..., help="Target SharePoint site URL."),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./build"), help="Output directory."),
    dry_run: bool = typer.Option(False, help="Validate only; no JS output."),
    seed: bool = typer.Option(
        False,
        "--seed",
        help="Also emit demo-data.js from the mapping's demo_items — "
        "'[DEMO] '-marked sample rows pasted after deploy.js.",
    ),
    extension: str | None = typer.Option(
        None,
        help="Extension name; overrides the mapping's `extension:` key. Resolved via entry points.",
    ),
) -> None:
    """Generate deploy.js + manifest from the DBML schema and mapping."""
    clear_generated(out, reporting=True)
    validate_site_url(site_url)
    parsed_schema = parse_dbml(schema)
    bundle = load_mapping(mapping)
    release_obj = load_release(release)
    ext = resolve_extension(extension or bundle.mapping.extension)

    if ext.requires_project_cli:
        typer.echo(
            f"Extension {ext.name!r} requires its project-specific CLI; "
            "the generic `dbml-sharepoint build` command cannot supply its "
            "required project inputs. Use the extension's project CLI instead.",
            err=True,
        )
        raise typer.Exit(code=2)

    # Site-role vocabulary is data-driven: the valid roles are those declared
    # by the mapping's entities (no hardcoded any labels you choose). A misspelled role
    # would otherwise be silently filtered to an empty deploy plan (exit 0).
    known_roles = {e.site_role for e in bundle.mapping.entities.values()}
    if site_role not in known_roles:
        typer.echo(
            f"Invalid --site-role {site_role!r}; the mapping declares: "
            f"{', '.join(sorted(known_roles)) or '(none)'}.",
            err=True,
        )
        raise typer.Exit(code=2)

    findings = validate_all(parsed_schema, bundle, ext)
    errors = [f for f in findings if f.severity == "error"]

    site_context = SiteContext(
        site_url=site_url,
        site_role=site_role,
        release=release_obj,
        output_dir=out,
        extension_args={},
    )

    # Only render the schema view when the schema is valid: build_schema_json
    # calls map_column(), which raises on unsupported/legacy types that
    # validate() already flags. On error we still emit a manifest documenting
    # the findings — using an empty schema view — then abort below.
    schema_json = (
        _EMPTY_SCHEMA_JSON
        if errors
        else build_schema_json(
            parsed_schema,
            bundle,
            site_role,
            site_url=site_url,
            release=release_obj,
            extension=ext,
            site_context=site_context,
        )
    )

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    source_mtime = dt.datetime.fromtimestamp(
        schema.stat().st_mtime, dt.UTC,
    ).isoformat(timespec="seconds")

    manifest_md = generate_manifest(
        schema_json=schema_json,
        findings=findings,
        bundle=bundle,
        release=release_obj,
        site_url=site_url,
        site_role=site_role,
        source_dbml=schema.name,
        source_mtime=source_mtime,
        generated_at=generated_at,
        manifest_extras=ext.manifest_extras(bundle, parsed_schema),
    )
    (out / "deploy-manifest.md").write_text(manifest_md, encoding="utf-8")

    if errors:
        typer.echo(f"Validation produced {len(errors)} error(s); aborting JS generation.", err=True)
        for f in errors:
            typer.echo(f"  [ERROR] {f.message}", err=True)
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo(f"Dry run complete. Manifest written to {out / 'deploy-manifest.md'}.")
        return

    try:
        message = emit_bundle(
            out,
            schema=parsed_schema,
            mapping_bundle=bundle,
            release=release_obj,
            site_url=site_url,
            site_role=site_role,
            schema_name=schema.name,
            mapping_name=mapping.name,
            source_mtime=source_mtime,
            generated_at=generated_at,
            seed=seed,
            extension=ext,
            site_context=site_context,
        )
    except SeedRequiresDemoItemsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(message)


@app.command()
def report(
    schema: Path = typer.Option(..., help="Path to the DBML schema file."),
    mapping: Path = typer.Option(..., help="Path to schema/sharepoint-mapping.yaml."),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./reports"), help="Output directory."),
    release: Path | None = typer.Option(
        None,
        help="Optional release.yaml; stamps release metadata into DATA-DICTIONARY.md.",
    ),
) -> None:
    """Generate reporting queries (Power Query M + SQL views) from the schema.

    Emits one .pq file per list, a SQLCMD views script, REPORTING.md with
    usage instructions and the Power BI relationship table, and a
    DATA-DICTIONARY.md companion. Assumes a schema that `build` accepts;
    run `build --dry-run` first if unsure.
    """
    parsed_schema = parse_dbml(schema)
    bundle = load_mapping(mapping)
    release_obj = load_release(release) if release is not None else None

    # Same data-driven role vocabulary as `build`: a misspelled role would
    # otherwise silently produce an empty report set (exit 0).
    known_roles = {e.site_role for e in bundle.mapping.entities.values()}
    if site_role not in known_roles:
        typer.echo(
            f"Invalid --site-role {site_role!r}; the mapping declares: "
            f"{', '.join(sorted(known_roles)) or '(none)'}.",
            err=True,
        )
        raise typer.Exit(code=2)

    pq_dir = out / "powerquery"
    sql_dir = out / "sql"
    pq_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    dictionary_kwargs: dict[str, Any] = dict(
        release=release_obj,
        generated_at=generated_at,
        source_schema=schema.name,
        source_mapping=mapping.name,
    )

    queries = generate_powerquery(parsed_schema, bundle, site_role)
    queries.update(
        generate_dictionary_powerquery(
            parsed_schema, bundle, site_role, **dictionary_kwargs,
        ),
    )
    for filename, content in queries.items():
        (pq_dir / filename).write_text(content, encoding="utf-8")
    (sql_dir / "views.sql").write_text(
        generate_sql_views(parsed_schema, bundle, site_role)
        + "\n"
        + generate_dictionary_sql(
            parsed_schema, bundle, site_role, **dictionary_kwargs,
        ),
        encoding="utf-8",
    )
    (out / "REPORTING.md").write_text(
        generate_reporting_md(parsed_schema, bundle, site_role), encoding="utf-8",
    )
    (out / "DATA-DICTIONARY.md").write_text(
        generate_data_dictionary(
            parsed_schema, bundle, site_role, **dictionary_kwargs,
        ),
        encoding="utf-8",
    )
    typer.echo(
        f"Generated {len(queries)} Power Query file(s), sql/views.sql, "
        f"REPORTING.md and DATA-DICTIONARY.md in {out}.",
    )


@app.command()
def version() -> None:
    """Print the deployer version."""
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
