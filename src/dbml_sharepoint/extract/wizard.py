# src/dbml_sharepoint/extract/wizard.py
"""The interactive `extract` flow: a list URL in, a draft schema out.

`dbml-sharepoint extract` with no argument runs this. It is a front end
onto the two documented commands rather than a second implementation of
them: the URL goes through `list_url.parse_list_url` and the CLI's own
`validate_site_url`, the script and the readme through `folder.seed`, and
the download through `cli.execute_extraction`. Anything produced here, the
flags could have produced.

What it adds is the wait. The script has to be pasted into a browser and
the download saved by hand between the two commands, and somebody who has
not read the help has no way to know that is the shape of the flow. So the
questions stop where the operator has to do something, and pick up again
when they say they have.

There is no output-directory question. The folder is named after the list
by `folder.folder_for`, which is what makes the two halves land in the
same place; asking would make that agreement optional.

Every string literal in this module must be ASCII: it is in
`_CONSOLE_BOUND` and `test_messages_bound_for_a_console_are_ascii` walks
the AST.
"""

import datetime as dt
from pathlib import Path

import typer
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from dbml_sharepoint.extract.emit import DEFAULT_PREFIX
from dbml_sharepoint.extract.folder import README_FILENAME, Seeded, seed
from dbml_sharepoint.extract.list_url import ListUrl, ListUrlError, parse_list_url
from dbml_sharepoint.generators.extractgen import download_name


def ask_list_url(console: Console) -> ListUrl:
    """Prompt until the answer names both a site and a list.

    Two gates, and both are somebody else's. `parse_list_url` decides
    whether a URL names a list; `validate_site_url` decides whether what is
    left of it is a site this tool will point a script at. Restating either
    rule here is how the wizard would come to disagree with the flags.

    The site URL comes back CLEANED, from the validator rather than from
    the split, because that is the string the emitted script guards on.

    Nothing gets past the first gate and then fails the second today: both
    require an absolute https URL with a host. The second clause is here so
    that a tightening of `validate_site_url` re-asks rather than crashing
    out of the wizard, which is why it is not dead code.
    """
    # Deferred for a cycle: `cli` imports this module at its top, so this
    # direction stays lazy until `validate_site_url` leaves the CLI -- #171.
    from dbml_sharepoint.cli import validate_site_url  # noqa: PLC0415

    console.print(
        "[dim]  Open the list in SharePoint and copy the address bar, for "
        "example\n  https://contoso.sharepoint.com/sites/Risk/Lists/"
        "RG_Project/AllItems.aspx[/dim]",
    )
    while True:
        answer = Prompt.ask("[bold]List URL[/bold]", console=console).strip()
        try:
            target = parse_list_url(answer)
        except ListUrlError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            continue
        try:
            site_url = validate_site_url(target.site_url)
        except typer.BadParameter as exc:
            console.print(f"[red]{escape(exc.message)}[/red]")
            continue
        return ListUrl(site_url=site_url, list_title=target.list_title)


def _paste_panel(seeded: Seeded, download: Path) -> Panel:
    """The three things to do in the browser, before the wait."""
    steps = Table.grid(padding=(1, 1), pad_edge=False)
    steps.add_column(justify="right", no_wrap=True, style="bold")
    steps.add_column(overflow="fold")
    steps.add_row("1.", "Open the list in SharePoint and open the browser console (F12).")
    steps.add_row(
        "2.",
        f"Paste the whole of [bold]{escape(str(seeded.script))}[/bold] into it. "
        "Every request it makes is a GET, so it changes nothing on the site.",
    )
    steps.add_row(
        "3.",
        f"It downloads [bold]{escape(download.name)}[/bold]. Save that file into "
        f"[bold]{escape(str(seeded.folder))}[/bold].",
    )
    body: list[RenderableType] = [steps]
    if seeded.readme is None:
        body.extend((
            "",
            (
                f"[dim]A {README_FILENAME} was already in that folder, so it "
                "was left alone.[/dim]"
            ),
        ))
    return Panel(Group(*body), title="In the browser", border_style="green")


def _find_download(console: Console, expected: Path) -> Path | None:
    """The download, asked for once when it is not where it should be.

    Once, not in a loop. The operator has just said the file is there, so a
    second answer that is also wrong means something other than a typo, and
    a wizard that keeps asking is harder to leave than one that stops.
    """
    if expected.is_file():
        return expected
    console.print(f"[yellow]Nothing at {escape(str(expected))}.[/yellow]")
    answer = Prompt.ask(
        "[bold]Path to the download[/bold]", console=console,
    ).strip()
    given = Path(answer).expanduser()
    if given.is_file():
        return given
    console.print(
        f"[red]Nothing at {escape(str(given))} either.[/red] Save the "
        "download, then run: dbml-sharepoint extract "
        f"{escape(str(expected))}",
    )
    return None


def _run(
    console: Console,
    *,
    entity: str | None,
    prefix: str,
    project: str | None,
    force: bool,
) -> int:
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import execute_extraction  # noqa: PLC0415

    console.print(
        Panel(
            "Recover a draft schema and mapping from a SharePoint list that "
            "already exists.\n\n"
            "There are three parts to it. This asks for the list's URL and "
            "writes a read-only script; you paste that script into the "
            "browser console on the site; the file it downloads comes back "
            "here as a draft.\n\n"
            "[dim]Everything here is also available as flags -- run "
            "`dbml-sharepoint extract --help`.[/dim]",
            title="dbml-sharepoint extract",
            border_style="green",
        ),
    )

    console.rule("List")
    target = ask_list_url(console)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    try:
        seeded = seed(
            list_title=target.list_title,
            site_url=target.site_url,
            generated_at=generated_at,
        )
    except OSError as exc:
        console.print(f"[red]Could not write the script:[/red] {escape(str(exc))}")
        return 1
    console.print(
        f"\n[green]Wrote[/green] {escape(str(seeded.script))}"
        + (f" and {escape(str(seeded.readme))}" if seeded.readme else ""),
    )

    download = seeded.folder / download_name([target.list_title])
    console.print()
    console.print(_paste_panel(seeded, download))

    if not Confirm.ask(
        f"Is {download.name} saved in {seeded.folder}?",
        default=True,
        console=console,
    ):
        console.print(
            "[yellow]Nothing extracted.[/yellow] When the file is there, run: "
            f"dbml-sharepoint extract {escape(str(download))}",
        )
        return 0

    source = _find_download(console, download)
    if source is None:
        return 1

    console.rule("Extract")
    try:
        execute_extraction(
            source,
            # The list's own folder, always. This is the one place the
            # wizard would need an --out question, and not asking it is what
            # keeps the script, the download and the draft together.
            out=seeded.folder,
            entity=entity,
            prefix=prefix,
            project=project,
            force=force,
        )
    except typer.Exit as exc:
        # The extraction refused and has already said why. Its exit code is
        # the documented contract; pass it through rather than flattening
        # every refusal to 1.
        return int(exc.exit_code)
    except typer.BadParameter as exc:
        # `click.UsageError`, not `typer.Exit`, so the clause above cannot
        # catch it. 2 is the documented code for a usage error.
        console.print(f"[red]{escape(exc.message)}[/red]")
        return 2
    return 0


def run_extract_wizard(
    console: Console | None = None,
    *,
    entity: str | None = None,
    prefix: str = DEFAULT_PREFIX,
    project: str | None = None,
    force: bool = False,
) -> int:
    """Entry point. Returns the process exit code.

    The flags `extract` was given are carried through rather than asked
    for, so `dbml-sharepoint extract --prefix ACME_` is the same run with
    one question already answered.

    Ctrl-C is a normal way to leave a wizard, not a crash: it exits 130
    (the shell's convention for SIGINT) without a traceback.
    """
    console = console or Console()
    try:
        return _run(
            console, entity=entity, prefix=prefix, project=project, force=force,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return 130
    except EOFError:
        # stdin closed mid-prompt -- piped input that ran out, or a
        # terminal that went away. Not a crash, and not success.
        console.print("\n[yellow]Input ended; nothing more written.[/yellow]")
        return 130
