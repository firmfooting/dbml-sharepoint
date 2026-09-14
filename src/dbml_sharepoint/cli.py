"""Command-line interface for dbml-sharepoint."""

import datetime as dt
from collections.abc import Callable
from contextlib import suppress
from difflib import get_close_matches
from pathlib import Path
from textwrap import wrap

import typer

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.finding_help import FINDING_HELP, RETIRED_FINDINGS
from dbml_sharepoint.analysis.sidecars import (
    CENTRAL_LOG_SITE_DEFAULT,
    CHANGE_LOG_TITLE,
    EXTERNAL_CHANGE_LOG_DEFAULT,
    EXTERNAL_LOG_DEFAULT,
)
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_GUIDE,
    REPORT_POWERQUERY_DIR,
    REPORT_SQL_DIR,
    REPORT_VIEWS_SQL,
    write_artifact,
)
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.extract.emit import DEFAULT_PREFIX
from dbml_sharepoint.extract.folder import (
    README_FILENAME,
    folder_for,
    seed,
)
from dbml_sharepoint.extract.list_url import ListUrlError, parse_list_url
from dbml_sharepoint.extract.wizard import run_extract_wizard
from dbml_sharepoint.generators.extractgen import EXTRACT_SCRIPT, download_name
from dbml_sharepoint.generators.identifygen import (
    DEFAULT_DOWNLOAD_NAME,
    IDENTIFY_SCRIPT,
    generate_identify_js,
)
from dbml_sharepoint.generators.maintaingen import (
    COLUMNS_SCRIPT,
    PROTECTION_SCRIPT,
    generate_columns_js,
    generate_protection_js,
)
from dbml_sharepoint.generators.reportgen import render_reporting
from dbml_sharepoint.model.env_file import (
    ENV_FILENAME,
    ENV_SETTINGS,
    TIME_ZONE_KEY,
)
from dbml_sharepoint.pipeline import execute_build, execute_extraction
from dbml_sharepoint.project import (
    load_config,
    project_input,
    require_known_site_role,
    resolve_env_file,
    resolve_extension_or_refuse,
    validate_site_url,
    validate_time_zone,
)
from dbml_sharepoint.wizard import run_wizard, stdin_is_interactive

app = typer.Typer(
    name="dbml-sharepoint",
    # ASCII "->" rather than an arrow. This string is rendered by rich to a
    # console whose encoding the locale decides, and a cp1252 console cannot
    # encode U+2192 -- which made a bare `--help`, the first command anybody
    # runs, raise UnicodeEncodeError instead of printing. rich already
    # substitutes ASCII box-drawing on a legacy console; it does not
    # substitute our own text. Guarded by
    # test_help_text_survives_a_legacy_windows_code_page.
    help="Generic DBML -> SharePoint browser-paste deploy.js.txt generator.",
    # Not `no_args_is_help`: a bare invocation runs the wizard. The help
    # fallback moved into the callback below, which can tell an interactive
    # terminal from a pipe -- `no_args_is_help` cannot.
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive wizard when invoked with no subcommand.

    Every documented flag still works exactly as before: `build`, `report`
    and `version` are untouched, and this callback returns immediately when
    one of them was named.

    A bare invocation only prompts when stdin AND stdout are both a
    terminal. In CI, a cron job, a Dockerfile or a pipe it prints help and
    exits 0, which is what a bare invocation did before the wizard existed
    -- so nothing that scripted `dbml-sharepoint` changes behaviour.
    """
    if ctx.invoked_subcommand is not None:
        return
    if not stdin_is_interactive():
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)
    raise typer.Exit(code=run_wizard())


@app.command()
def new() -> None:
    """Interactively copy a solution template into a new project.

    The same wizard a bare `dbml-sharepoint` runs, named so it can be asked
    for explicitly and so it appears in `--help`.
    """
    raise typer.Exit(code=run_wizard())


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


def _env_file_help() -> str:
    """The `--env-file` option's help text, with the key names discoverable
    from `build --help` alone.

    The key NAMES only, not each key's full help: the prose column of the
    options table shrinks as option names grow, and a 25-char unbreakable
    key inside prose ellipsises once three new `--deployment-log-*` options
    land (live CI finding 2026-09-05, windows runner at effective width 78:
    `DBMLSP_ENTERPRISE_READER` rendered as `DBMLSP_ENTERPRISE_REA...`). The
    full key/help pairs live in the epilog panel, which spans the whole
    console width and cannot be squeezed by the name column; the test that
    pins every key and help line against `build --help` reads both.
    """
    keys = ", ".join(setting.key for setting in ENV_SETTINGS)
    return (
        f"Path to a {ENV_FILENAME} defaults file. Default: {ENV_FILENAME} "
        "in the current directory, when present. A flag given on the command "
        f"line always wins over a value the file supplies. Accepted keys: {keys}"
    )


def _env_keys_epilog() -> str:
    """The `build` epilog: every env key with its full help, one per entry.

    Typer renders the epilog below the options table at FULL console width,
    so the prose column's width games don't apply and a long key can never
    be ellipsised by an option name growing elsewhere. The
    `--env-file` option help carries the bare key names; this panel is the
    authoritative key/help listing (live CI finding 2026-09-05: keys inside
    the options-table prose ellipsised at the windows runner's width once
    the deployment-log options widened the name column).

    Entries are separated by a BLANK line, not a single newline: rich
    reflows an epilog paragraph, so single newlines are collapsed and the
    entries run together into one wrapped block on a narrow console. A blank
    line is the paragraph break rich honours. Square brackets are escaped
    for the same renderer -- `[x]` in a key's help would be read as markup
    and disappear from the panel entirely.
    """
    lines = [
        f"{_escape_rich(setting.key)}: {_escape_rich(setting.help)}"
        for setting in ENV_SETTINGS
    ]
    return "Environment file keys (dbml-sharepoint.env):\n\n" + "\n\n".join(lines)


def _escape_rich(text: str) -> str:
    """Make `text` render literally in a rich-formatted help panel."""
    return text.replace("[", r"\[")


@app.command(epilog=_env_keys_epilog())
def build(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    release: Path | None = typer.Option(
        None, help=f"Path to release.yaml. Default: {RELEASE_RELPATH}",
    ),
    site_url: str = typer.Option(..., help="Target SharePoint site URL."),
    time_zone: str | None = typer.Option(
        None,
        "--time-zone",
        help="The site's time zone as an IANA name, such as Australia/Melbourne "
        "or Europe/London (Site settings > Regional settings > Time zone). "
        "The reporting pack converts every timestamp by it and checks the "
        f"site agrees at each refresh. Required, from this flag or from "
        f"{ENV_FILENAME}'s {TIME_ZONE_KEY}.",
    ),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./build"), help="Output directory."),
    dry_run: bool = typer.Option(False, help="Validate only; no JS output."),
    seed: bool = typer.Option(
        False,
        "--seed",
        help="Also emit demo-data.js.txt from the mapping's demo_items -- "
        f"'{DEMO_TITLE_PREFIX}'-marked sample rows pasted after deploy.js.txt.",
    ),
    enterprise_reader: str | None = typer.Option(
        None,
        help="UPN of a reporting service account to enrol, read-only, into "
        f"the mapping's enterprise-reader group. Omitted, this falls back to "
        f"{ENV_FILENAME}'s DBMLSP_ENTERPRISE_READER when that file supplies "
        "one, and otherwise enrols nobody.",
    ),
    extension: str | None = typer.Option(
        None,
        help="Extension name; overrides the mapping's `extension:` key. Resolved via entry points.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help=_env_file_help(),
    ),
    deployment_log_list: str | None = typer.Option(
        None,
        "--deployment-log-list",
        help="Title of the central deployment log list to stamp start, stop "
        "and provenance rows into. Created by deploying the deployment-log "
        "family to the logging site; every other deploy stamps it when it can "
        f"reach it. Default: '{EXTERNAL_LOG_DEFAULT}' on site "
        f"'{CENTRAL_LOG_SITE_DEFAULT}' unless {ENV_FILENAME} names another; "
        "pass '' to disable the external stamps.",
    ),
    deployment_log_change_list: str | None = typer.Option(
        None,
        "--deployment-changes",
        help="Title of the central change log to write type-2 change rows "
        "into, on the same site as --deployment-log-list, beside it. Created "
        "by deploying the deployment-log family; every other deploy writes "
        f"to it when it can reach it. Default: '{EXTERNAL_CHANGE_LOG_DEFAULT}' "
        f"unless {ENV_FILENAME} names another; pass '' to disable the "
        "central change rows.",
    ),
    deployment_log_site: str | None = typer.Option(
        None,
        "--deployment-log-site",
        help="Title of the central logging SITE the deployment log list "
        "lives on. Created by hand from the SharePoint start page: this tool "
        f"provisions lists, never sites. Default: '{CENTRAL_LOG_SITE_DEFAULT}' "
        f"unless {ENV_FILENAME} names another; pass '' to disable the stamps.",
    ),
    change_log_list: str | None = typer.Option(
        None,
        "--change-log-list",
        help="Title of the hidden change log the deploy writes type-2 "
        "rows into (old value, new value, effective window). Created if "
        f"absent, owned by marker. Default: {CHANGE_LOG_TITLE}, or what "
        f"{ENV_FILENAME} names.",
    ),
    no_sidecars: bool = typer.Option(
        False,
        "--no-sidecars",
        help="Skip both built-in sidecar lists (the run log and the change "
        "log) entirely: no lists created, no stamps, no change rows. Only "
        "bites when the central deployment log is out of reach, since a run "
        "that finds it writes there and makes no sidecars either way.",
    ),
) -> None:
    """Generate deploy.js.txt + manifest from the DBML schema and mapping.

    Resolves the three input paths here rather than inside `execute_build`:
    the defaults are a convenience for a person at a terminal, and
    `execute_build` is the programmatic entry point the wizard and extension
    CLIs compose. Those callers know exactly which files they mean, and a
    path that silently came from the working directory would be a surprise
    in a library call.
    """
    # The same rule `report` applies, and for a sharper reason: this command
    # emits the bundle somebody pastes into a tenant. Defaulting the release
    # is only safe when the schema and mapping came from the project too.
    # Otherwise `build --schema ../other/... --mapping ../other/...` run from
    # a project directory stamps THIS project's release tag and schema
    # version into a deploy bundle describing somebody else's schema --
    # measured at "Release tag: 1.0.0" on a bundle built from a schema whose
    # own release said 0.1.0-test. Nothing links a release.yaml to the schema
    # it describes, so the only safe inference is that all three came from
    # the same place.
    #
    # Refuses rather than skipping the stamp: a release is REQUIRED here, so
    # unlike `report` there is no unstamped mode to fall back to. That higher
    # cost is why the threshold is BOTH inputs, not either -- `report` can
    # afford `schema is None and mapping is None` because being wrong there
    # only loses a stamp, while the same rule here would outlaw pointing
    # `--schema` at a scratch copy with the rest of the project left in
    # place, which `project_input` documents as an ordinary thing to want
    # and `test_an_explicit_path_beats_the_project_default` pins.
    #
    # One foreign input plus one from the project is the case this lets
    # through. It is the combination that mostly cannot validate anyway --
    # another project's schema against this project's mapping -- whereas
    # both-foreign is unambiguous, and is exactly what was measured.
    from_the_project = schema is None or mapping is None
    execute_build(
        schema=project_input(schema, SCHEMA_RELPATH, "--schema"),
        mapping=project_input(mapping, MAPPING_RELPATH, "--mapping"),
        release=project_input(
            release, RELEASE_RELPATH, "--release", from_the_project=from_the_project,
        ),
        site_url=site_url,
        time_zone=time_zone,
        site_role=site_role,
        out=out,
        dry_run=dry_run,
        seed=seed,
        extension=extension,
        enterprise_reader=enterprise_reader,
        env_file=resolve_env_file(env_file),
        deployment_log_list=deployment_log_list,
        deployment_log_change_list=deployment_log_change_list,
        deployment_log_site=deployment_log_site,
        change_log_list=change_log_list,
        no_sidecars=no_sidecars,
    )


@app.command()
def validate(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    site_role: str = typer.Option(
        "default",
        help="Site role; must match one the mapping declares. Does NOT narrow "
             "what is checked -- validation is always project-wide.",
    ),
    extension: str | None = typer.Option(
        None,
        help="Extension name; overrides the mapping's `extension:` key. Resolved via entry points.",
    ),
) -> None:
    """Check the schema and mapping. No site URL, no output, no release.

    `validate_all` takes a schema, a mapping bundle and an extension --
    not a site URL and not a release. Answering "is this correct?" through
    `build --dry-run` therefore cost an invented tenant URL, on the tightest
    loop in the tool: edit the mapping, check, edit again.

    Deliberately NOT the same thing as `build --dry-run`, which keeps its
    contract unchanged. The two answer different questions:

    * `validate` -- is my schema and mapping correct?
    * `build --dry-run` -- what would this build do against that site,
      without emitting JS?

    The second is a run sheet for a named target. `deploy-manifest.md` does
    not merely stamp the site URL in a header; step 3 of its run sequence
    sends the operator to `<site_url>/_layouts/15/settings.aspx`. Rendering
    that with a not-supplied marker would produce an artifact whose own
    instructions are fiction, which is why this command writes no manifest
    rather than `--dry-run` learning to omit the target.

    Writes nothing at all, and takes no `--out`. A question, not an artifact.

    `--site-role` does NOT scope the check, and must not. `validate_all`
    takes no role and `build` calls it identically, so validation has always
    been project-wide -- this reports exactly what a build would. Narrowing
    it would hide an error under `admin` from anyone validating `default`,
    which means the mapping reads clean until the deploy that breaks. The
    flag's job here is to reject a role the mapping does not declare, moving
    a typo's discovery earlier. Pinned by
    `test_validate_checks_every_role_not_just_the_selected_one`.
    """
    schema = project_input(schema, SCHEMA_RELPATH, "--schema")
    mapping = project_input(mapping, MAPPING_RELPATH, "--mapping")
    parsed_schema, bundle, _ = load_config(schema, mapping, None)
    ext = resolve_extension_or_refuse(extension, bundle, mapping)
    require_known_site_role(bundle, site_role)

    findings = validate_all(parsed_schema, bundle, ext)
    for f in findings:
        typer.echo(f"  [{f.severity.upper()}] {f.code}: {f.message}", err=True)

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    typer.echo(
        f"{schema}: {errors} error(s), {warnings} warning(s).",
        err=errors > 0,
    )
    if errors:
        raise typer.Exit(code=1)


@app.command()
def explain(
    code: str = typer.Argument(
        "",
        help="A finding code, as printed beside a build's findings. "
        "Omit to list every code.",
    ),
) -> None:
    """Say what a finding code means, without leaving the terminal.

    The code is a finding's identity -- stable, and what the catalogue is
    keyed by -- while the message beside it is prose that may be reworded in
    any release. So the code is the only part worth looking up, and until
    now the only place to look it up was a website.

    Reads `FINDING_HELP`, which ships inside the package. The published
    reference at `reference/findings.md` is generated from the same data, so
    the two cannot disagree.
    """
    if not code:
        for member in sorted(FINDING_HELP):
            typer.echo(f"  {member.severity:<7}  {member}")
        typer.echo(
            f"\n{len(FINDING_HELP)} codes. "
            "Run `dbml-sharepoint explain <code>` for any one of them.",
        )
        return

    # Tolerate the token exactly as a build prints it. Findings render as
    # `[ERROR] unknown_column_type: schema[Project].Sponsor: ...`, and the obvious
    # thing to do is select the code and paste it -- which brings the colon.
    wanted = code.strip().rstrip(":").lower()
    found = next((c for c in FINDING_HELP if str(c) == wanted), None)
    if found is None and wanted in RETIRED_FINDINGS:
        # A code an older build printed stays answerable after its rule goes.
        typer.echo(f"{wanted}  [retired]\n")
        for line in wrap(RETIRED_FINDINGS[wanted], width=76):
            typer.echo(line)
        return
    if found is None:
        near = get_close_matches(wanted, [str(c) for c in FINDING_HELP], n=3, cutoff=0.6)
        suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
        typer.echo(
            f"No finding code {wanted!r}.{suggestion}\n"
            "Run `dbml-sharepoint explain` with no argument to list them all.",
            err=True,
        )
        raise typer.Exit(code=2)

    # Severity off the code, meaning off the catalogue: the two facts have
    # one home each, and this is just the place they are printed together.
    typer.echo(f"{found}  [{found.severity}]\n")
    for line in wrap(FINDING_HELP[found], width=76):
        typer.echo(line)


@app.command()
def report(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    time_zone: str = typer.Option(
        ...,
        "--time-zone",
        help="The site's time zone as an IANA name, such as Australia/Melbourne "
        "or Europe/London (Site settings > Regional settings > Time zone). "
        "Every list query carries its daylight-saving transitions.",
    ),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./reports"), help="Output directory."),
    release: Path | None = typer.Option(
        None,
        help="Optional release.yaml; stamps release metadata into "
        f"data-dictionary.md. Default: {RELEASE_RELPATH} when it exists.",
    ),
) -> None:
    """Generate reporting queries (Power Query M + SQL views) from the schema.

    Emits one .pq file per list, a SQLCMD views script, guide.md with
    usage instructions and the Power BI relationship table, and a
    data-dictionary.md companion. Assumes a schema that `build` accepts;
    run `build --dry-run` first if unsure.

    `--time-zone` is a required option here rather than one the env file
    may supply: this command reads no `dbml-sharepoint.env`, and inventing
    that discovery for one key would give `report` half of `build`'s
    precedence rules. It needs no site URL, because the pack it writes
    reads a `SiteUrl` parameter instead, but the zone shapes the queries
    themselves and has no parameter to fall back on.
    """
    # Refused first, before any file is read: a zone the database does not
    # declare has nothing to derive from, and nothing in `out` is touched.
    time_zone = validate_time_zone(time_zone)
    # Whether this run is reporting on the project in the working directory,
    # or on files somebody named explicitly. It decides the release default
    # below, so it has to be read BEFORE the paths are resolved.
    from_the_project = schema is None and mapping is None

    schema = project_input(schema, SCHEMA_RELPATH, "--schema")
    mapping = project_input(mapping, MAPPING_RELPATH, "--mapping")
    # Not through `project_input`: this option is genuinely optional and its
    # absence is a supported mode (an unstamped dictionary), so a missing
    # release.yaml must not refuse the way a missing schema does. Picking it
    # up when it IS there means running `report` inside a project stamps the
    # provenance it could always have had.
    #
    # Only when the schema and mapping came from the project too. Otherwise
    # `report --schema ../other/schema.dbml --mapping ../other/mapping.yaml`
    # run from a project directory would stamp THIS project's release tag and
    # schema version onto a data dictionary describing somebody else's
    # schema -- provenance that is not merely missing but wrong, and wrong in
    # a way the output looks confident about. Nothing links a release.yaml to
    # the schema it describes, so the only safe inference is that all three
    # came from the same place.
    if release is None and from_the_project and RELEASE_RELPATH.is_file():
        release = RELEASE_RELPATH
    parsed_schema, bundle, release_obj = load_config(schema, mapping, release)

    require_known_site_role(bundle, site_role)

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
    queries = [p for p in pack if p.startswith(f"{REPORT_POWERQUERY_DIR}/")]
    typer.echo(
        f"Generated {len(queries)} Power Query file(s), "
        f"{REPORT_SQL_DIR}/{REPORT_VIEWS_SQL}, "
        f"{REPORT_GUIDE} and {REPORT_DICTIONARY} in {out}.",
    )


@app.command("extract-script")
def extract_script(
    url: str = typer.Argument(
        ...,
        help="The list's URL, copied from the browser address bar with the "
        "list open, e.g. https://contoso.sharepoint.com/sites/Risk/Lists/"
        "RG_Project/AllItems.aspx",
    ),
    out: Path | None = typer.Option(
        None,
        help="Where to write the script, with the readme beside it. Default: "
        f"<list name>/{EXTRACT_SCRIPT}",
    ),
) -> None:
    """Generate the read-only browser-paste script that reads a live list.

    Takes the whole list URL, because that is the one string the browser
    address bar already holds: the site and the list title are split out of
    it rather than asked for separately. One list per script.

    The script and a readme are written into a folder named after the list,
    which is where `dbml-sharepoint extract` then writes the draft schema
    and mapping, so both halves of the flow keep one directory.

    Paste the emitted file into the browser console on that site. It
    downloads the list's field definitions as JSON; feed that JSON to
    `dbml-sharepoint extract` to get a draft schema and mapping.

    Every request the script makes is a GET. It carries no write helpers.
    """
    try:
        target = parse_list_url(url)
    except ListUrlError as exc:
        raise typer.BadParameter(str(exc)) from exc
    # Still asked of `validate_site_url`, which owns what a usable site URL
    # is, so the split half meets the same rule an operator-typed one does.
    used = validate_site_url(target.site_url)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    seeded = seed(
        list_title=target.list_title,
        list_path=target.list_path,
        site_url=used,
        generated_at=generated_at,
        script=out,
    )
    typer.echo(f"Reading the list at {target.list_path!r} on {used}.")
    typer.echo(
        f"Wrote {seeded.script}. Open it, copy all of it, and paste it into the "
        f"browser console on {used}. It makes no changes.",
    )
    if seeded.readme is not None:
        typer.echo(f"Wrote {seeded.readme}, which has the rest of the procedure.")
    else:
        typer.echo(f"Left the {README_FILENAME} already in {seeded.folder} alone.")
    download = download_name([target.list_title])
    typer.echo(
        f"The script downloads {download}. Save it into {seeded.folder}, then "
        f"run: dbml-sharepoint extract {seeded.folder / download}",
    )


_LIST_URL_HELP = (
    "The list's URL, copied from the browser address bar with the list open, "
    "e.g. https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx"
)


def _maintenance_script(
    url: str,
    out: Path | None,
    *,
    script_name: str,
    render: Callable[..., str],
    does: str,
) -> None:
    """Write one list-maintenance script from a pasted list URL.

    The site and the list's server-relative path are split out of the one
    string the address bar holds, then the site half meets the same rule an
    operator-typed `--site-url` does.

    THE SCRIPT RESOLVES BY PATH, NOT BY THE SLUG. A list renamed in place
    keeps the slug it was created with, so on any site that has been through a
    `renamed_from` migration the slug is not the list's title and a by-title
    script 404s on its first read. The slug still names the output folder,
    which is where `extract-script` writes too, so one list's scripts stay
    together.
    """
    try:
        target = parse_list_url(url)
    except ListUrlError as exc:
        raise typer.BadParameter(str(exc)) from exc
    used = validate_site_url(target.site_url)
    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    path = out if out is not None else folder_for(target.list_title) / script_name
    write_artifact(path, render(
        site_url=used, list_title=target.list_title,
        list_path=target.list_path, generated_at=generated_at,
    ))
    # The PATH is echoed, because that is what the script resolves and what an
    # operator can check against the address bar. Its title may differ.
    typer.echo(f"Wrote {path} for the list at {target.list_path!r} on {used}.")
    typer.echo(
        "Open it, copy all of it, and paste it into the browser console on "
        f"{used} from a classic page such as _layouts/15/settings.aspx. It {does}",
    )


@app.command("protection-script")
def protection_script(
    url: str = typer.Argument(..., help=_LIST_URL_HELP),
    out: Path | None = typer.Option(
        None, help=f"Where to write the script. Default: <list name>/{PROTECTION_SCRIPT}",
    ),
) -> None:
    """Generate the browser-paste script that locks, unlocks, seals or unseals one list.

    The script prints the list's deletion lock and the Sealed flag on each
    custom column, then takes one word at a time: lock or unlock sets
    AllowDeletion, seal or unseal sets Sealed on every custom column not
    already in that state. Every write is read back, and a readback that
    disagrees stops the run. It deletes nothing.
    """
    _maintenance_script(
        url, out, script_name=PROTECTION_SCRIPT, render=generate_protection_js,
        does="prompts for each action and reads every write back.",
    )


@app.command("columns-script")
def columns_script(
    url: str = typer.Argument(..., help=_LIST_URL_HELP),
    out: Path | None = typer.Option(
        None, help=f"Where to write the script. Default: <list name>/{COLUMNS_SCRIPT}",
    ),
) -> None:
    """Generate the browser-paste script that enumerates and deletes one list's custom columns.

    The script prints the custom columns and asks for one by internal name,
    never by position. Built-in and hidden fields never appear. Every item is
    read to see whether the column holds a value: an empty column needs its
    internal name typed again after that scan, and one with values, or whose
    values cannot be read, needs
    DELETE NON-EMPTY typed. A sealed column is unsealed and read back before
    the delete, and the column is read back after it and must be gone. The
    table is printed again after each delete; a blank answer finishes.

    Deleting a column removes its values from every item, and nothing goes
    to the recycle bin.
    """
    _maintenance_script(
        url, out, script_name=COLUMNS_SCRIPT, render=generate_columns_js,
        does="asks for a typed confirmation before every delete.",
    )


@app.command("identify-script")
def identify_script(
    site_url: str | None = typer.Option(
        None,
        help="Pin the script to one site, e.g. "
        "https://contoso.sharepoint.com/sites/Risk. Omit it for a portable "
        "script that inventories whichever site it is pasted on.",
    ),
    out: Path | None = typer.Option(
        None,
        help=f"Where to write the script. Default: {IDENTIFY_SCRIPT} in the "
        "current directory.",
    ),
) -> None:
    """Generate the read-only browser-paste script that reports what is on a site.

    The script reads the web's own facts, every list, group and permission
    level, and which of them this tool provisioned and for which family. It
    reads the columns of the lists it owns, and reports the last deployment
    the site recorded. It prints the result as tables and offers it as a JSON
    download.

    NO SITE URL IS NEEDED. The script runs against whichever web it is
    pasted on, so one file walks every site in a fleet. Pass --site-url to pin
    it to one, which is worth doing when handing the file to somebody else.

    Every request the script makes is a GET. It carries no write helpers.
    """
    used = validate_site_url(site_url) if site_url is not None else None
    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    path = out if out is not None else Path(IDENTIFY_SCRIPT)
    write_artifact(path, generate_identify_js(site_url=used, generated_at=generated_at))

    where = f"on {used}" if used is not None else "on any site in the fleet"
    typer.echo(f"Wrote {path}, for pasting {where}.")
    typer.echo(
        "Open it, copy all of it, and paste it into the browser console on a "
        "classic page such as _layouts/15/settings.aspx. It makes no changes.",
    )
    typer.echo(
        f"It prints what it found and downloads {DEFAULT_DOWNLOAD_NAME}. Keep "
        "one download per site to build a fleet view.",
    )


@app.command()
def extract(
    source: Path | None = typer.Argument(
        None,
        help="The JSON extract.js.txt downloaded from the site. Omit it to be "
        "walked through the whole flow, starting from the list's URL.",
    ),
    out: Path | None = typer.Option(
        None,
        help="Project directory to write into. Default: a folder named after "
        "the list, which is the one extract-script wrote the script into.",
    ),
    entity: str | None = typer.Option(
        None,
        help="DBML table name for the extracted list. Default: derived from the "
        "list title. Only valid when the source describes one list.",
    ),
    prefix: str = typer.Option(
        DEFAULT_PREFIX,
        help="The mapping's list-name prefix. An extraction cannot know the "
        f"deploying project's, so it defaults to {DEFAULT_PREFIX!r}.",
    ),
    project: str | None = typer.Option(
        None, help="DBML Project name. Default: the first entity name, lowercased.",
    ),
    force: bool = typer.Option(
        False, help="Overwrite an existing schema.dbml, mapping.yaml or release.yaml.",
    ),
) -> None:
    """Recover a draft schema.dbml and mapping.yaml from an existing list.

    Takes the JSON `dbml-sharepoint extract-script` produced and you pasted
    into the browser console. That read is the only input; nothing here is
    recovered from an export.

    With no argument it runs interactively instead, asking for the list's
    URL, writing the script, waiting while you paste it, and extracting the
    download when you say it has landed. The same two commands do the work
    either way.

    This is a SCAFFOLDING tool, not a lossless round-trip. What the read
    carries is recovered; everything else is itemised in the
    EXTRACTION-NOTES.md written beside the output. Read that file before
    editing the schema, and again before deploying anything.
    """
    if source is None:
        if out is not None:
            raise typer.BadParameter(
                "--out has no download to write from. Name the JSON to "
                "extract, or drop --out and be asked for the list's URL; the "
                "interactive flow always writes into the list's own folder.",
            )
        if not stdin_is_interactive():
            # Same rule the wizard callback applies: never block on a prompt
            # nobody can answer. A pipe or a CI job that ran `extract` with no
            # argument meant to name a file, so this is a usage error rather
            # than a help screen.
            typer.echo(
                "[ERROR] no download named, and there is no terminal to ask "
                "at. Pass the JSON that extract.js.txt downloaded.",
                err=True,
            )
            raise typer.Exit(code=2)
        raise typer.Exit(code=run_extract_wizard(
            entity=entity, prefix=prefix, project=project, force=force,
        ))
    execute_extraction(
        source, out=out, entity=entity, prefix=prefix, project=project, force=force,
    )


@app.command()
def version() -> None:
    """Print the deployer version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
