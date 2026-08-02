"""The interactive template wizard: the default `dbml-sharepoint` command.

Copies one shipped solution template into a project directory of the
user's own, substitutes their list-name prefix, and offers to build it.

Scope is deliberate. The wizard changes **identity only** -- prefix, site
URL, where the files land. It never edits the schema or the mapping's
structure. Those templates are the tested artifacts: every one of them is
built end-to-end in CI and held to `test_template_standard.py`, and a
wizard that let a user restructure one would be handing them an untested
mapping while implying the opposite.

It is a front end onto `cli.execute_build`, not a second builder. Anything
the wizard produces, the documented flags could have produced.
"""

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from dbml_sharepoint.catalogue import Solution, available_solutions
from dbml_sharepoint.model.mapping_loader import load_mapping

#: Copied templates must not carry a previous build. These names are
#: gitignored in the repository, so they exist only in a contributor's
#: checkout -- but that is exactly where the wizard gets run during
#: development, and a stale deploy.js in a new project is worse than none.
_NEVER_COPY = ("build", "reports", "__pycache__")

#: Weaker than SharePoint's own rules on purpose. The authority is the
#: validator, which runs on the build; a wizard rule stronger than what the
#: thirty shipped templates satisfy would refuse input the tool accepts.
#: Every shipped prefix is alphanumerics plus a trailing underscore.
_PREFIX_OK = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


class WizardError(RuntimeError):
    """The wizard cannot safely continue. Always names what went wrong."""


@dataclass(frozen=True)
class Answers:
    """What the wizard collected, before anything is written."""

    solution: Solution
    destination: Path
    prefix: str
    site_url: str


def _catalogue_table(solutions: list[Solution]) -> Table:
    table = Table(
        title="Solution templates",
        header_style="bold",
        title_style="bold",
        show_lines=False,
        expand=False,
    )
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Template", no_wrap=True)
    table.add_column("Lists", justify="right", no_wrap=True)
    table.add_column("Title")
    for index, solution in enumerate(solutions, start=1):
        table.add_row(
            str(index), solution.id, str(len(solution.lists)), solution.title,
        )
    return table


def _pick_solution(console: Console, solutions: list[Solution]) -> Solution:
    """Choose by number or by name, re-prompting until one resolves.

    Accepts the name as well as the index because the number is a property
    of this render -- it changes when a template is added -- and somebody
    reading the docs knows the template as `risk-register`.
    """
    console.print(_catalogue_table(solutions))
    by_name = {s.id: s for s in solutions}
    while True:
        answer = Prompt.ask(
            "\n[bold]Pick a template[/bold] (number or name)",
            default=solutions[0].id,
            console=console,
        ).strip()
        if answer in by_name:
            return by_name[answer]
        if answer.isdigit() and 1 <= int(answer) <= len(solutions):
            return solutions[int(answer) - 1]
        console.print(f"[red]No template {answer!r}.[/red] Pick a number or a name.")


def _describe(console: Console, solution: Solution) -> None:
    lists = ", ".join(solution.lists) or "(none declared)"
    console.print(
        Panel(
            f"{solution.summary}\n\n"
            f"[bold]Lists[/bold]  {lists}\n"
            f"[bold]Prefix[/bold] {solution.prefix}",
            title=solution.title,
            border_style="cyan",
        ),
    )


def _ask_destination(console: Console, solution: Solution) -> Path:
    """Where the project goes. Never writes into a non-empty directory.

    Refusing rather than merging is the safe default: the wizard copies a
    whole tree, so merging into somebody's existing project would scatter
    template files through it with no record of which were added.
    """
    while True:
        raw = Prompt.ask(
            "[bold]Project directory[/bold]",
            default=f"./{solution.id}",
            console=console,
        ).strip()
        destination = Path(raw).expanduser()
        if not destination.exists():
            return destination
        if not destination.is_dir():
            console.print(f"[red]{destination} exists and is not a directory.[/red]")
            continue
        if any(destination.iterdir()):
            console.print(
                f"[red]{destination} already exists and is not empty.[/red] "
                "Pick a path that does not exist yet.",
            )
            continue
        return destination


def _ask_prefix(console: Console, solution: Solution) -> str:
    while True:
        prefix = Prompt.ask(
            "[bold]List name prefix[/bold]",
            default=solution.prefix,
            console=console,
        ).strip()
        if _PREFIX_OK.match(prefix):
            return prefix
        console.print(
            "[red]Use letters, digits, hyphen or underscore (1-16 chars).[/red]",
        )


def _ask_site_url(console: Console) -> str:
    """Prompt until the URL passes the CLI's own validator.

    Calls `validate_site_url` rather than restating its rule, so the wizard
    cannot come to disagree with `--site-url` about what is acceptable.
    """
    from dbml_sharepoint.cli import validate_site_url

    while True:
        site_url = Prompt.ask(
            "[bold]SharePoint site URL[/bold]",
            default="https://contoso.sharepoint.com/sites/example",
            console=console,
        ).strip()
        try:
            validate_site_url(site_url)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc.message}[/red]")
            continue
        return site_url


def _rewrite_prefix(mapping_path: Path, prefix: str) -> None:
    """Set `prefix:` in the copied mapping, then read it back and verify.

    A targeted line rewrite, not a YAML round-trip. Every shipped mapping
    is heavily commented -- the comments are the documentation for the
    template -- and `yaml.safe_load` followed by `yaml.dump` would discard
    all of them and reorder the file.

    Verified through the real loader rather than by re-reading the text:
    the question is not whether the line changed, it is whether the mapping
    the build will load carries the prefix the user asked for.
    """
    text = mapping_path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"^prefix:.*$", f'prefix: "{prefix}"', text, count=1, flags=re.MULTILINE,
    )
    if count != 1:
        raise WizardError(
            f"{mapping_path} has no top-level `prefix:` line to set "
            f"(found {count}). The template does not match the family "
            f"standard; refusing to guess where the prefix belongs.",
        )
    mapping_path.write_text(new_text, encoding="utf-8")

    bundle = load_mapping(mapping_path)
    if bundle.mapping.prefix != prefix:
        raise WizardError(
            f"wrote prefix {prefix!r} to {mapping_path} but the mapping "
            f"loaded back as {bundle.mapping.prefix!r}.",
        )


def _scaffold(answers: Answers) -> None:
    shutil.copytree(
        answers.solution.root,
        answers.destination,
        ignore=shutil.ignore_patterns(*_NEVER_COPY),
    )
    _rewrite_prefix(
        answers.destination / answers.solution.mapping_path.relative_to(
            answers.solution.root,
        ),
        answers.prefix,
    )


def _site_roles(mapping_path: Path) -> list[str]:
    """The roles the copied mapping actually declares.

    Same data-driven vocabulary `build` and `report` use: the valid roles
    are whatever the entities declare, never a hardcoded list.
    """
    bundle = load_mapping(mapping_path)
    return sorted({e.site_role for e in bundle.mapping.entities.values()})


def _run(console: Console) -> int:
    solutions = available_solutions()
    if not solutions:
        console.print(
            "[red]No solution templates found.[/red] This build of "
            "dbml-sharepoint shipped without them.",
        )
        return 1

    console.print(
        Panel(
            "Copy a shipped list template into a project of your own, then "
            "build it into a pasteable deploy.js.\n\n"
            "[dim]Everything here is also available as flags -- run "
            "`dbml-sharepoint build --help`.[/dim]",
            title="dbml-sharepoint",
            border_style="green",
        ),
    )

    solution = _pick_solution(console, solutions)
    _describe(console, solution)

    destination = _ask_destination(console, solution)
    prefix = _ask_prefix(console, solution)
    site_url = _ask_site_url(console)
    answers = Answers(solution, destination, prefix, site_url)

    console.print()
    console.print(
        Panel(
            f"[bold]Template[/bold]  {answers.solution.id}\n"
            f"[bold]Directory[/bold] {answers.destination}\n"
            f"[bold]Prefix[/bold]    {answers.prefix}\n"
            f"[bold]Site[/bold]      {answers.site_url}",
            title="About to write",
            border_style="yellow",
        ),
    )
    if not Confirm.ask("Write these files?", default=True, console=console):
        console.print("[yellow]Nothing written.[/yellow]")
        return 0

    try:
        _scaffold(answers)
    except (WizardError, OSError) as exc:
        console.print(f"[red]Could not scaffold the project:[/red] {exc}")
        return 1

    mapping_path = answers.destination / "20-configure" / "mapping.yaml"
    schema_path = answers.destination / "10-design" / "schema.dbml"
    release_path = answers.destination / "20-configure" / "release.yaml"
    console.print(f"\n[green]Wrote[/green] {answers.destination}")

    if not Confirm.ask("\nBuild it now?", default=True, console=console):
        console.print(
            "\nWhen you are ready:\n\n"
            f"  [bold]cd {answers.destination}[/bold]\n"
            "  [bold]dbml-sharepoint build \\\n"
            "    --schema 10-design/schema.dbml \\\n"
            "    --mapping 20-configure/mapping.yaml \\\n"
            "    --release 20-configure/release.yaml \\\n"
            f"    --site-url {answers.site_url} \\\n"
            "    --out ./build[/bold]",
        )
        return 0

    roles = _site_roles(mapping_path)
    site_role = roles[0] if len(roles) == 1 else Prompt.ask(
        "[bold]Site role[/bold]", choices=roles, default="default", console=console,
    )

    from dbml_sharepoint.cli import execute_build

    try:
        execute_build(
            schema=schema_path,
            mapping=mapping_path,
            release=release_path,
            site_url=answers.site_url,
            site_role=site_role,
            out=answers.destination / "build",
        )
    except typer.Exit as exc:
        # The build refused and has already said why on stderr. Its exit
        # code is the documented contract; pass it through rather than
        # flattening every refusal to 1.
        return int(exc.exit_code)

    console.print(
        Panel(
            f"Paste [bold]{answers.destination / 'build' / 'assess.js'}[/bold] "
            "into the target site's console first -- it is read-only and "
            "tells you what is already there.\n\n"
            f"Then [bold]{answers.destination / 'build' / 'deploy.js'}[/bold].\n\n"
            f"[dim]{answers.destination / '30-deploy' / 'DEPLOY.md'} has the "
            "full procedure for this template.[/dim]",
            title="Next",
            border_style="green",
        ),
    )
    return 0


def run_wizard(console: Console | None = None) -> int:
    """Entry point. Returns the process exit code.

    Ctrl-C is a normal way to leave a wizard, not a crash: it exits 130
    (the shell's convention for SIGINT) without a traceback.
    """
    console = console or Console()
    try:
        return _run(console)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return 130
    except EOFError:
        # stdin closed mid-prompt -- piped input that ran out, or a
        # terminal that went away. Not a crash, and not success.
        console.print("\n[yellow]Input ended; nothing written.[/yellow]")
        return 130


def stdin_is_interactive() -> bool:
    """Whether it is safe to prompt.

    A bare `dbml-sharepoint` in CI, a cron job or a Dockerfile must not
    block on a prompt nobody can answer. The caller falls back to printing
    help, which is what a bare invocation did before the wizard existed.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()
