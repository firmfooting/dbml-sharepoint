"""The library entry points: what a command does once its inputs are loaded.

`execute_build` and `execute_extraction` are the whole of `build` and
`extract`, callable without going through typer, so the wizard runs exactly
the pipeline the documented flags run rather than a second implementation
that drifts.

They live here rather than in `cli.py` because `cli.py` imports both wizards
at its top, so a wizard reaching back for the pipeline had to defer the
import into a function body to break the cycle (#171).
"""

import datetime as dt
from contextlib import suppress
from difflib import get_close_matches
from pathlib import Path
from textwrap import wrap
from typing import Any

import typer

from dbml_sharepoint.analysis.finding_help import FINDING_HELP, RETIRED_FINDINGS
from dbml_sharepoint.analysis.findings import Finding
from dbml_sharepoint.analysis.folders import UnknownFolderEnumError
from dbml_sharepoint.analysis.groups import declaring_groups
from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.analysis.permissions import lists_granting_group
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.sidecars import (
    CENTRAL_LOG_SITE_DEFAULT,
    CHANGE_LOG_TITLE,
    EXTERNAL_CHANGE_LOG_DEFAULT,
    EXTERNAL_LOG_DEFAULT,
    run_log_title,
)
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_GUIDE,
    REPORT_POWERQUERY_DIR,
    REPORT_SQL_DIR,
    REPORT_VIEWS_SQL,
    SeedRequiresDemoItemsError,
    clear_generated,
    emit_bundle,
    write_artifact,
)
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.extension import (
    SiteContext,
)
from dbml_sharepoint.extract.emit import DEFAULT_PREFIX
from dbml_sharepoint.extract.folder import (
    folder_for_download,
)
from dbml_sharepoint.extract.run import (
    NOTES_RELPATH,
    check_identifier,
    entity_name_for,
    extraction_from,
)
from dbml_sharepoint.extract.run import write as write_extraction
from dbml_sharepoint.extract.sources import load_source
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.reportgen import render_reporting
from dbml_sharepoint.project import (
    CONFIG_ERRORS,
    EnterpriseReaderDeclined,
    config_error,
    echo_env_provenance,
    load_config,
    missing_time_zone,
    require_known_site_role,
    resolve_env_settings,
    resolve_env_time_zone,
    resolve_extension_or_refuse,
    site_url_notice,
    validate_enterprise_reader,
    validate_list_title,
    validate_site_name,
    validate_site_url,
    validate_time_zone,
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
    "acl_scopes": [],
    "requires_manage_permissions": False,
    "seed_items": [],
}


def _echo_warnings(findings: list[Finding]) -> None:
    """Say what the build warned about, on the terminal, or say nothing.

    A build that raised warnings used to print one cheerful success line and
    leave them in the manifest. The manifest is not optional reading and the
    docs say so, but the terminal was teaching the opposite: success means
    there is nothing to look at. The one time it matters, the habit is
    already formed -- and `unique without not_null` is precisely the finding
    discovered in production, by a duplicate.

    Printed in full rather than counted. Warnings are few by construction,
    and a build that raises dozens is itself the signal.

    Silence when clean is deliberate. A "0 warnings" line on every build is
    noise that makes the non-zero case LESS visible, which is the opposite
    of the point; `test_a_clean_build_says_nothing_about_warnings` pins it.

    stderr, matching the error path: this is diagnostic output, and a
    pipeline capturing stdout wants the bundle message, not this.
    """
    warnings = [f for f in findings if f.severity == "warning"]
    if not warnings:
        return
    plural = "" if len(warnings) == 1 else "s"
    typer.echo(f"{len(warnings)} validation warning{plural}:", err=True)
    for f in warnings:
        typer.echo(f"  [WARNING] {f.detail}", err=True)


def execute_build(
    *,
    schema: Path,
    mapping: Path,
    release: Path,
    site_url: str,
    site_role: str,
    out: Path = Path("./build"),
    dry_run: bool = False,
    seed: bool = False,
    time_zone: str | None = None,
    extension: str | None = None,
    enterprise_reader: str | EnterpriseReaderDeclined | None = None,
    env_file: Path | None = None,
    deployment_log_list: str | None = None,
    deployment_log_change_list: str | None = None,
    deployment_log_site: str | None = None,
    change_log_list: str | None = None,
    no_sidecars: bool = False,
) -> None:
    """The `build` pipeline, callable without going through typer.

    Extracted so the wizard can run exactly the same build the documented
    flags run, rather than growing a second implementation that drifts. The
    wizard is a different front end onto this, not a different builder.

    Still raises `typer.Exit` on refusal: the exit codes are the documented
    contract (2 for misuse, 1 for a refused build), and re-mapping them to
    an exception of its own here would give the wizard a second vocabulary
    for the same failures. The wizard catches it.

    `enterprise_reader` carries three states: ``None`` (unset -- no flag was
    given), `EnterpriseReaderDeclined` (the operator was asked and said
    nobody), or a UPN. `env_file`, when given, is a `dbml-sharepoint.env`
    ALREADY resolved to a path by the caller (`build` resolves the default
    location the same way it resolves `--schema`, `--mapping` and
    `--release`; this function does no discovery of its own). When the file
    supplies a value for a setting that is still unset, that value is used;
    an explicit `enterprise_reader` -- a flag or the declined sentinel --
    always wins over the file, because both mean the operator already
    decided.

    `time_zone` is the site's IANA zone, a fact about the site the way
    `site_url` is, and it is REQUIRED: ``None`` here is only "no flag was
    given", and a build refuses once the env file has also had its say and
    still named none. It defaults to ``None`` rather than being a required
    keyword so the file can supply it, the same shape as `enterprise_reader`.
    """
    # Reassigned, not merely checked: everything below -- SiteContext, the
    # manifest, and the reporting pack's `SiteRoot` and SQLCMD `SiteUrl` --
    # reads this variable, so cleaning it here is what keeps a pasted
    # `?web=1` out of every generated endpoint.
    cleaned_site_url = validate_site_url(site_url)
    if notice := site_url_notice(site_url, cleaned_site_url):
        typer.echo(notice, err=True)
    site_url = cleaned_site_url
    parsed_schema, bundle, release_obj = load_config(schema, mapping, release)
    if release_obj is None:  # unreachable: --release is a required option
        raise typer.BadParameter("--release is required for `build`.")
    # Threaded everywhere below rather than rebuilt: the reader gate, the
    # schema view and the manifest all resolve enum sources, and a generator
    # that built its own could build a different one from another. Not once
    # per build, though -- `ValidationContext.build` resolves again from the
    # same inputs. `resolve` is pure, so the two cannot disagree, and the
    # duplicate is accepted rather than removed by an optional pre-built
    # parameter, which would let a caller validate a DIFFERENT resolution
    # from the one deployed.
    resolved = resolve(parsed_schema, bundle.mapping)
    ext = resolve_extension_or_refuse(extension, bundle, mapping)

    if ext.requires_project_cli:
        typer.echo(
            f"Extension {ext.name!r} requires its project-specific CLI; "
            "the generic `dbml-sharepoint build` command cannot supply its "
            "required project inputs. Use the extension's project CLI instead.",
            err=True,
        )
        raise typer.Exit(code=2)

    require_known_site_role(bundle, site_role)

    (
        enterprise_reader, resolved_external, resolved_external_change,
        resolved_site, resolved_change, resolved_zone, env_provenance,
    ) = resolve_env_settings(
        env_file, enterprise_reader, deployment_log_list,
        deployment_log_change_list, deployment_log_site, change_log_list,
        time_zone,
    )
    echo_env_provenance(env_provenance)
    # The zone is validated on the resolved value, wherever it came from, so
    # the file gets the same refusal a flag does rather than a pack built
    # for a zone the database has never heard of.
    if resolved_zone is None:
        raise missing_time_zone()
    time_zone = validate_time_zone(resolved_zone)
    # Post-resolution defaults, and the three states the external log name
    # carries. Nothing said anywhere -- no flag, no file -- means the
    # built-in sidecar names, applied AFTER precedence so a file naming
    # another list is a plain "used", never an override of a default the
    # operator never gave. The defaults themselves carry no provenance:
    # nothing was decided, so nothing is reported.
    #
    # The empty string is the DOCUMENTED DISABLE for the external log (flag
    # or file) and must survive as a state of its own: collapsing it to
    # None here would let the default below put the probe straight back.
    # A padded variant is not the disable and is refused by the title
    # validation, so nothing invisible can turn the feature off.
    if resolved_external is not None and resolved_external != "":
        validate_list_title(resolved_external, "--deployment-log-list")
    if resolved_external_change is not None and resolved_external_change != "":
        validate_list_title(resolved_external_change, "--deployment-changes")
    if resolved_site is not None and resolved_site != "":
        validate_site_name(resolved_site, "--deployment-log-site")
    if resolved_change is not None:
        validate_list_title(resolved_change, "--change-log-list")
    external_log = (
        EXTERNAL_LOG_DEFAULT
        if resolved_external is None
        else resolved_external  # '' stays '' (off); a title stays itself
    )
    external_change_log = (
        EXTERNAL_CHANGE_LOG_DEFAULT
        if resolved_external_change is None
        else resolved_external_change  # '' stays '' (off); a title stays itself
    )
    external_site = (
        CENTRAL_LOG_SITE_DEFAULT
        if resolved_site is None
        else resolved_site
    )
    change_log = resolved_change if resolved_change is not None else CHANGE_LOG_TITLE
    # The site and the deployments list are one feature: '' on either is the
    # documented disable for the external stamps AND for the change list
    # beside them, since a change list with no deployments list to decide
    # LOG_MODE has nowhere to be central about. '' on the change list alone
    # does NOT disable the pair the other way: an org that wants stamps
    # without the central change feed sets only this one to ''.
    if external_site == "" or external_log == "":
        external_site = ""
        external_log = ""
        external_change_log = ""

    # Each title is validated on its own above, so nothing there catches the
    # two naming the SAME list: both probes would succeed against it, stamp
    # rows and change rows would land side by side on one list, and whatever
    # broke downstream (a column the wrong row shape does not carry, a close
    # query matching rows it should not) would blame that symptom rather
    # than the two flags that caused it.
    if external_log and external_change_log and external_log == external_change_log:
        raise typer.BadParameter(
            "--deployment-log-list and --deployment-changes must not name "
            f"the same list ({external_log!r}); each central list wants its "
            "own title.",
        )

    # `isinstance`, not `is not None`: the declined sentinel means nobody is
    # enrolled and must skip validation and the group check just as `None` does.
    if isinstance(enterprise_reader, str):
        validate_enterprise_reader(enterprise_reader)
        perms = bundle.mapping.permissions
        # Two questions, two resolutions. "Does a reader group exist at all"
        # is answered over the DECLARATIONS, because a source whose enum is
        # misspelled still declares one and `group_enum_unknown` is the
        # finding for it; resolving here instead reported "declares no
        # group", sent the author to add a flag that is already there, and
        # took the manifest and every other finding with it.
        declared_readers = [
            g for g in declaring_groups(perms) if g.enroll_enterprise_reader
        ]
        # "Which lists grant it" needs the RESOLVED name, because a
        # `from_enum` group's template spelling matches no assignment.
        targets = [
            g for g in resolved.groups
            if g.enroll_enterprise_reader
        ]
        if not declared_readers:
            # Fail closed rather than emitting a bundle that quietly enrols
            # nobody. The operator would not find out until a report came
            # back short, weeks later. `MULTIPLE_ENTERPRISE_READER_GROUPS`
            # (a validator rule) already refuses more than one such group,
            # so there is nothing to re-check on that side here.
            raise typer.BadParameter(
                "--enterprise-reader was given but the mapping declares no "
                "group with enroll_enterprise_reader: true.",
            )

        # Declaring the group is not the same as granting it anything HERE.
        # `ENTERPRISE_READER_GROUP_NOT_GRANTED` unions every policy block and
        # so is satisfied by a grant in any site role, while a default policy
        # scoped to another role is excluded per list by
        # `permissions_for_entity`. `--site-role branch --enterprise-reader`
        # against a default scoped to `hq` therefore emitted a bundle whose
        # `acl_scopes` was empty: the account is enrolled permanently,
        # the run reports success, and it can read none of this site's lists.
        #
        # Refused here rather than in the validator, which has no site role
        # and could only refuse the mapping outright -- the same mapping is
        # correct for the role that does grant the group. Resolved through
        # `lists_granting_group`, which asks `permissions_for_entity` per list
        # exactly as jsgen does when it binds the live role assignments, so
        # this refuses on what the deploy would do rather than on the
        # mapping's shape.
        deployed_here = site_tables_in_order(
            parsed_schema, bundle.mapping.entities, site_role,
        )
        try:
            # Both scopes: a reader granted only inside a library's folders
            # can still read something here, which is what this gate asks.
            granted_anywhere_here = any(
                reach.granted or reach.folder_only
                for reach in (
                    lists_granting_group(resolved, g.name, deployed_here)
                    for g in targets
                )
            )
        except UnknownFolderEnumError:
            # Deferred, not swallowed: `folder_enum_unknown` is an error, so
            # validation below refuses this build with the finding and the
            # manifest this gate was replacing with a traceback. `True` skips
            # only this gate's own refusal, which would name the wrong cause.
            granted_anywhere_here = True
        # Exactly one, for two reasons. No target at all means every reader
        # source named an enum the schema does not declare, leaving no name
        # to ask about. More than one means a source resolved to a group per
        # member, which cannot hold one identity: deferred, not swallowed,
        # like the `UnknownFolderEnumError` arm above, so
        # `group_enum_enrols_an_identity` names the fault and the manifest
        # still gets written.
        if len(targets) == 1 and not granted_anywhere_here:
            names = ", ".join(repr(g.name) for g in targets)
            raise typer.BadParameter(
                f"--enterprise-reader names an account to enrol into "
                f"{names}, which is granted no permission level on any list "
                f"site role {site_role!r} deploys. The enrolment is permanent "
                f"once the deploy reaches its end and the run would report "
                f"success, so the account would hold access to nothing here "
                f"and nothing on the site would say so. Grant the group in "
                f"this role's list_permissions, build the site role whose "
                f"policy does grant it, or build without "
                f"--enterprise-reader.",
            )

    # Everything above this line is a pure read that can refuse: a malformed
    # URL, an unreadable input file, an extension needing its own CLI, a role
    # the mapping does not declare. None of them has made anything in `out`
    # stale, and `--out` is routinely the directory holding the bundle the
    # operator is part-way through pasting -- so a refusal that learnt nothing
    # must not destroy it. `report` has always drawn the line here; `build`
    # used to clear as its first statement and disagreed.
    #
    # From here the build is committed to writing, so every later refusal DOES
    # clear. That is what the guarantee is actually for: a `deploy.js.txt`
    # describing a schema this run rejected is the stale script an operator
    # could paste.
    clear_generated(out, reporting=True)

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
    # the findings (using an empty schema view), then abort below.
    schema_json = (
        _EMPTY_SCHEMA_JSON
        if errors
        else build_schema_json(
            parsed_schema,
            bundle,
            site_role,
            resolved=resolved,
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

    # Narrowed here rather than by reassigning the parameter above, which
    # would erase the unset/declined distinction before anything consumes it.
    resolved_enterprise_reader = (
        enterprise_reader if isinstance(enterprise_reader, str) else None
    )

    manifest_md = generate_manifest(
        schema_json=schema_json,
        resolved=resolved,
        findings=findings,
        bundle=bundle,
        release=release_obj,
        site_url=site_url,
        site_role=site_role,
        source_dbml=schema.name,
        source_mtime=source_mtime,
        generated_at=generated_at,
        manifest_extras=ext.manifest_extras(bundle, parsed_schema),
        # The manifest is read BEFORE the paste, so this is where the
        # permanent-membership warning has to be. Rendered even on the
        # error path below: a build that refuses still writes a manifest,
        # and the operator reading it should see what the flag would have
        # done once the errors are fixed.
        enterprise_reader=resolved_enterprise_reader,
        env_provenance=env_provenance,
        sidecar_run_log_title=None if no_sidecars else run_log_title(),
        sidecar_change_log_title=None if no_sidecars else change_log,
        deployment_log_list=external_log or "",
        deployment_log_change_list=external_change_log or "",
        deployment_log_site=external_site or "",
    )
    write_artifact(out / "deploy-manifest.md", manifest_md)

    if errors:
        typer.echo(f"Validation produced {len(errors)} error(s); aborting JS generation.", err=True)
        for f in errors:
            typer.echo(f"  [ERROR] {f.detail}", err=True)
        # Warnings too, before the exit. A build that refuses has ALSO found
        # everything else wrong with the mapping, and printing only the
        # errors hides that until the errors are fixed -- so the operator
        # fixes, rebuilds, and meets a second list they could have seen the
        # first time. This is the one path where suppressing them costs an
        # extra round trip rather than nothing.
        _echo_warnings(findings)
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo(f"Dry run complete. Manifest written to {out / 'deploy-manifest.md'}.")
        _echo_warnings(findings)
        return

    try:
        message = emit_bundle(
            out,
            schema=parsed_schema,
            mapping_bundle=bundle,
            resolved=resolved,
            release=release_obj,
            site_url=site_url,
            site_role=site_role,
            schema_name=schema.name,
            mapping_name=mapping.name,
            source_mtime=source_mtime,
            generated_at=generated_at,
            seed=seed,
            time_zone=time_zone,
            extension=ext,
            site_context=site_context,
            enterprise_reader=resolved_enterprise_reader,
            env_provenance=env_provenance,
            deployment_log_list=external_log or "",
            deployment_log_change_list=external_change_log or "",
            deployment_log_site=external_site or "",
            change_log_list=None if no_sidecars else change_log,
            no_sidecars=no_sidecars,
        )
    except SeedRequiresDemoItemsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(message)
    _echo_warnings(findings)


def execute_validation(
    *,
    schema: Path,
    mapping: Path,
    site_role: str = "default",
    extension: str | None = None,
) -> list[Finding]:
    """The `validate` pipeline, callable without going through typer.

    Returns the findings rather than printing them. The command computed
    this list and then destroyed it, so the wizard could not offer a check
    and an extension CLI could not compose one (#171).

    `site_role` does NOT scope the check. `validate_all` takes no role and
    `execute_build` calls it identically, so this reports exactly what a
    build would; the role is here to refuse one the mapping does not
    declare, which moves a typo's discovery earlier.
    """
    parsed_schema, bundle, _ = load_config(schema, mapping, None)
    ext = resolve_extension_or_refuse(extension, bundle, mapping)
    require_known_site_role(bundle, site_role)
    return validate_all(parsed_schema, bundle, ext)


class UnknownFindingCodeError(LookupError):
    """`explain` was given a code no catalogue entry answers.

    Named rather than a bare `LookupError` so a caller can tell "there is
    no such code" from any other lookup failure, and carries the message
    the command prints, suggestion included, because composing that needs
    the catalogue this side already holds.
    """


def execute_explain(code: str) -> str:
    """What `explain` prints, for one code or for the whole catalogue.

    Returns the text rather than echoing it, so the same answer can reach
    a console, a wizard panel or a test without the catalogue lookup being
    re-implemented beside each one.

    Reads `FINDING_HELP`, which ships inside the package. The published
    reference at `reference/findings.md` is generated from the same data,
    so the two cannot disagree.
    """
    if not code:
        rows = [f"  {member.severity:<7}  {member}" for member in sorted(FINDING_HELP)]
        return "\n".join([
            *rows,
            "",
            (
                f"{len(FINDING_HELP)} codes. "
                "Run `dbml-sharepoint explain <code>` for any one of them."
            ),
        ])

    # Tolerate the token exactly as a build prints it. Findings render as
    # `[ERROR] unknown_column_type: schema[Project].Sponsor: ...`, and the obvious
    # thing to do is select the code and paste it -- which brings the colon.
    wanted = code.strip().rstrip(":").lower()
    found = next((c for c in FINDING_HELP if str(c) == wanted), None)
    if found is None and wanted in RETIRED_FINDINGS:
        # A code an older build printed stays answerable after its rule goes.
        return f"{wanted}  [retired]\n\n" + "\n".join(
            wrap(RETIRED_FINDINGS[wanted], width=76),
        )
    if found is None:
        near = get_close_matches(wanted, [str(c) for c in FINDING_HELP], n=3, cutoff=0.6)
        suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
        raise UnknownFindingCodeError(
            f"No finding code {wanted!r}.{suggestion}\n"
            "Run `dbml-sharepoint explain` with no argument to list them all.",
        )

    # Severity off the code, meaning off the catalogue: the two facts have
    # one home each, and this is just the place they are printed together.
    return f"{found}  [{found.severity}]\n\n" + "\n".join(
        wrap(FINDING_HELP[found], width=76),
    )



# Includes the pre-normalisation names for the same reason `bundle`'s
# _LEGACY_ARTIFACTS does: `report` clears its previous output so a query
# for a list that has left the schema cannot outlive it, and a name this
# command used to write is exactly that kind of survivor. Note the old
# DATA-DICTIONARY.md spelling was unique to THIS command -- `build` has
# always written reporting/data-dictionary.md -- which is the
# inconsistency the rename closed.
_REPORT_FILES = (
    REPORT_GUIDE,
    REPORT_DICTIONARY,
    # Superseded names, newest first. `reporting.md` existed only briefly
    # between the case normalisation and this rename, but "briefly" is not
    # "never" for anyone tracking main.
    "reporting.md",
    "REPORTING.md",
    "DATA-DICTIONARY.md",
)
# (subdirectory, glob) pairs naming everything `report` writes below `out`.
_REPORT_DIRECTORY_CONTENTS = (
    (REPORT_POWERQUERY_DIR, "*.pq"),
    (REPORT_SQL_DIR, REPORT_VIEWS_SQL),
)


def _clear_report_output(out: Path) -> None:
    """Remove the artifacts this command writes, and nothing else.

    Deliberately not `rmtree` on powerquery/ and sql/. Those names are
    generic, `--out` is routinely aimed at a directory the operator also
    keeps their own work in, and a hand-written migration sitting beside
    views.sql is not this command's to delete. Remove by the names `report`
    generates, then drop each directory only if emptying it left nothing
    behind.

    `*.pq` is the one broad pattern, and it is deliberate: a stale query
    from a list that has left the schema is indistinguishable from a
    hand-written one, and leaving it is the worse failure, because it
    documents a list that no longer exists. The docs say so; `--out` is not the place
    to keep your own .pq files.
    """
    for dirname, pattern in _REPORT_DIRECTORY_CONTENTS:
        directory = out / dirname
        for path in sorted(directory.glob(pattern)):
            if path.is_file():
                path.unlink()
        with suppress(OSError):
            directory.rmdir()  # refuses when the operator left anything here
    for filename in _REPORT_FILES:
        (out / filename).unlink(missing_ok=True)


def execute_report(
    *,
    schema: Path,
    mapping: Path,
    site_role: str = "default",
    out: Path = Path("./reports"),
    release: Path | None = None,
    time_zone: str | None = None,
    env_file: Path | None = None,
) -> dict[str, str]:
    """The `report` pipeline, callable without going through typer.

    Returns the pack it wrote, relpath to content, so a caller can say what
    landed without re-deriving the file names from the schema.

    `time_zone` reads the same way `execute_build`'s does: a value given
    here wins, `env_file` supplies one when nothing was, and a run with
    neither refuses. `report` used to take the zone as a hard-required flag
    and read no env file at all, so the two commands disagreed about where
    the same site fact could come from (#171).
    """
    # Resolved and refused before anything is read or written: a zone the
    # database does not declare has nothing to derive from, and nothing in
    # `out` is touched.
    resolved_zone, env_provenance = resolve_env_time_zone(env_file, time_zone)
    echo_env_provenance(env_provenance)
    if resolved_zone is None:
        raise missing_time_zone()
    time_zone = validate_time_zone(resolved_zone)

    parsed_schema, bundle, release_obj = load_config(schema, mapping, release)
    require_known_site_role(bundle, site_role)
    # Resolved once for this report: `report` runs no validation pass of its
    # own, so `generate_data_dictionary` below is where an unresolved enum
    # actually gets caught.
    resolved = resolve(parsed_schema, bundle.mapping)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")

    # Render everything before writing anything. This command does not
    # validate, documenting the contract as "assumes a schema that `build`
    # accepts", so the generators are the first thing to meet a schema
    # mistake, and they signal one by raising: an unmapped column type, a
    # composite DBML index. Unhandled, that printed a traceback for a typo
    # in a file the operator hand-edited, which is exactly what
    # `config_error` exists to prevent on the loading side. Rendering up
    # front also keeps a failure from leaving a half-written report set
    # behind, where the stale files outlive the error on the terminal.
    # `render_reporting` is the same composition `build` ships, so the two
    # commands cannot drift in what they write.
    try:
        pack = render_reporting(
            parsed_schema, bundle, site_role,
            resolved=resolved,
            release=release_obj, generated_at=generated_at,
            source_schema=schema.name, source_mapping=mapping.name,
            time_zone=time_zone,
        )
    except ValueError as exc:
        # The schema was read and refused, so whatever is in `out` describes
        # a schema that no longer exists. Clear it rather than leave a stale
        # set looking current. Only reachable once the config loaded and the
        # role resolved: a mistyped --schema path or an unknown --site-role
        # never learns anything about the report, and must not destroy the
        # last good one on its way out.
        _clear_report_output(out)
        typer.echo(
            f"[ERROR] schema {schema}: {exc}\n"
            "Run `build --dry-run` for the full validation report.",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # Drop the previous set so a list removed from the schema does not leave
    # its .pq file behind, outliving the schema that justified it.
    _clear_report_output(out)

    for relpath, content in pack.items():
        write_artifact(out / relpath, content)
    return pack


def _refuse_existing_project(out: Path, *, force: bool) -> None:
    """Refuse to write over a project that is already there.

    Applied to the derived default directory as well as to an explicit
    `--out`: one folder per list makes a second run of the same extraction
    land on the first one's output, which is where a hand-edited schema
    would be lost. An extraction produces a DRAFT, so
    overwriting real work with one is the worst outcome this command has;
    it is refused by name rather than guarded by a prompt, because the
    command must behave the same in a pipe.
    """
    if force:
        return
    present = [
        out / relpath
        for relpath in (SCHEMA_RELPATH, MAPPING_RELPATH, RELEASE_RELPATH, NOTES_RELPATH)
        if (out / relpath).exists()
    ]
    if not present:
        return
    typer.echo(
        "[ERROR] refusing to overwrite an existing project. These already "
        "exist:\n" + "\n".join(f"  {path}" for path in present)
        + "\nPass --out with an empty directory, or --force to overwrite them.",
        err=True,
    )
    raise typer.Exit(code=1)


def execute_extraction(
    source: Path,
    *,
    out: Path | None = None,
    entity: str | None = None,
    prefix: str = DEFAULT_PREFIX,
    project: str | None = None,
    force: bool = False,
) -> None:
    """One extraction, from a download to a written project directory.

    Shared by the `extract` command and the interactive flow, for the same
    reason `execute_build` is shared with the template wizard: the wizard
    must not be able to produce anything the documented flags could not.
    Refusals leave through `typer.Exit`, which both callers understand.
    """
    try:
        loaded = load_source(source)
    except CONFIG_ERRORS as exc:
        config_error("extraction source", source, exc)

    if entity is not None and len(loaded.lists) > 1:
        raise typer.BadParameter(
            f"--entity names one table, but the source describes "
            f"{len(loaded.lists)} lists. Extract them one at a time, or drop "
            "the flag and let each be named from its list title.",
        )
    try:
        entity_names = {
            source_list.title: (
                check_identifier(entity, "--entity")
                if entity is not None
                else entity_name_for(source_list.title)
            )
            for source_list in loaded.lists
        }
        extraction = extraction_from(loaded, entity_names=entity_names)
    except CONFIG_ERRORS as exc:
        config_error("extraction source", source, exc)

    if project is not None:
        check_identifier(project, "--project")
    # The FIRST list's title. A download this tool generates carries exactly
    # one, and a hand-assembled one carrying several has no single folder it
    # could be named after; `--out` is the answer there.
    root = out if out is not None else folder_for_download(
        source, loaded.lists[0].title,
    )
    _refuse_existing_project(root, force=force)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    written = write_extraction(
        extraction,
        root,
        generated_at=generated_at,
        prefix=prefix,
        project=project or "",
    )

    columns = sum(len(e.columns) for e in extraction.entities)
    # A run from inside the list's own folder derives `.` as its root, and
    # "into ." names nothing. Resolve that one case.
    destination = written.root if written.root.name else written.root.resolve()
    typer.echo(
        f"Extracted {len(extraction.entities)} list(s), {columns} column(s) and "
        f"{len(extraction.enums)} enum(s) from {loaded.kind} into {destination}",
    )
    typer.echo(f"  {written.schema}\n  {written.mapping}\n  {written.release}")
    for path in written.preserved:
        typer.echo(f"  {path}")
    typer.echo(
        f"\n{len(extraction.unrecovered)} thing(s) could not be recovered. "
        f"Read {written.notes} before you edit or deploy anything.",
    )
