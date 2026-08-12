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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from dbml_sharepoint.bundle import (
    ASSESS_SCRIPT,
    DEMO_SCRIPT,
    DEPLOY_SCRIPT,
    write_artifact,
)
from dbml_sharepoint.catalogue import (
    PLACEHOLDER_SITE_URL,
    Solution,
    available_solutions,
)
from dbml_sharepoint.model.mapping_loader import load_mapping

#: Copied templates must not carry a previous build. These names are
#: gitignored in the repository, so they exist only in a contributor's
#: checkout -- but that is exactly where the wizard gets run during
#: development, and a stale deploy script in a new project is worse than none.
_NEVER_COPY = ("build", "reports", "__pycache__")

#: Refuses only what cannot be a filename component or would corrupt the
#: YAML line the prefix is written into. NOT a SharePoint rule.
#:
#: This was `^[A-Za-z0-9_-]{1,16}$`, which invented both a character set
#: and a 16-character ceiling that nothing in Microsoft Learn, the
#: validator or the thirty shipped templates supports. That is precisely
#: the "assert from plausibility" failure AGENTS.md opens with, and it made
#: the wizard reject prefixes `--build` accepts, looping forever on a
#: perfectly good answer with no way to proceed.
#:
#: The authority for what SharePoint accepts is the validator, which runs
#: on the build; the wizard's job is to stop the obviously-broken input
#: that would fail confusingly later, and nothing more.
_PREFIX_REJECTED = re.compile(r'[\s/\\:*?"<>|]')


class WizardError(RuntimeError):
    """The wizard cannot safely continue. Always names what went wrong."""


@dataclass(frozen=True)
class TemplateChoice:
    """One chosen template, and the prefix its lists will carry.

    Separate from `Answers` because the two answer different questions. A
    prefix belongs to a template -- it renames that template's lists and
    nothing else -- while the directory, the site URL and the site role
    describe one SharePoint site. Several templates deployed to one site is
    the direction this is headed, and that boundary is the part of it worth
    drawing now.
    """

    solution: Solution
    #: "" is a real answer meaning "no prefix", not a missing one. MEASURED
    #: 2026-08-12: `prefix: ""` builds and emits `"Risk"` as the list title
    #: throughout deploy.js.txt. Nothing outside this wizard requires one.
    prefix: str

    def list_titles(self) -> tuple[str, ...]:
        """The SharePoint list titles this template will create.

        A method rather than a property because it iterates. The rule it
        obeys is plain concatenation, which is what `jsgen.py:380`,
        `assessgen.py:39`, `demogen.py:109`, `manifestgen.py:77` and
        `reportgen.py:176` all do -- so this reports the build's behaviour
        rather than predicting it.
        """
        return tuple(self.prefix + name for name in self.solution.lists)


@dataclass(frozen=True)
class Answers:
    """What the wizard collected, before anything is written."""

    destination: Path
    site_url: str
    templates: tuple[TemplateChoice, ...]


def _template_root(answers: Answers, choice: TemplateChoice) -> Path:
    """Where one template's files land inside the project directory.

    The destination itself while there is one template, so every documented
    path, every printed command and every existing test stays exactly as it
    is. Several templates cannot share one root, so they nest by template id.
    """
    if len(answers.templates) == 1:
        return answers.destination
    return answers.destination / choice.solution.id


def _within(root: Path, destination: Path) -> str:
    """`root` as a path fragment relative to `destination`, or "" if equal.

    Used to build the relative paths the wizard prints. Absolute paths wrap
    and break the panel boxes, and the operator has just been told where the
    project is -- repeating it on every line of the procedure is noise.
    """
    relative = root.relative_to(destination).as_posix()
    return "" if relative == "." else f"{relative}/"


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
        if prefix and not _PREFIX_REJECTED.search(prefix):
            return prefix
        console.print(
            "[red]A prefix cannot be empty or contain whitespace or any of "
            '[/red][bold]/ \\ : * ? " < > |[/bold][red].[/red]',
        )


def _ask_site_url(console: Console) -> str:
    """Prompt until the URL passes the CLI's own validator.

    Calls `validate_site_url` rather than restating its rule, so the wizard
    cannot come to disagree with `--site-url` about what is acceptable.
    """
    # Deferred for a cycle: cli.py imports this module at its top, so this
    # direction stays lazy until `validate_site_url` leaves the CLI -- #171.
    from dbml_sharepoint.cli import (  # noqa: PLC0415
        _site_url_notice,
        validate_site_url,
    )

    while True:
        site_url = Prompt.ask(
            "[bold]SharePoint site URL[/bold]",
            default="https://contoso.sharepoint.com/sites/example",
            console=console,
        ).strip()
        try:
            cleaned = validate_site_url(site_url)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc.message}[/red]")
            continue
        # Said out loud, because the operator is about to see this URL in the
        # Review panel and in the printed rebuild command, and a value that
        # silently differs from what they typed reads as a bug in those.
        if notice := _site_url_notice(site_url, cleaned):
            console.print(f"[dim]  {notice}[/dim]")
        return cleaned


def _ask_enterprise_reader(console: Console) -> str:
    """Prompt until the answer is blank or passes the CLI's own validator.

    The same re-ask loop as `_ask_site_url`, for a sharper reason. This
    answer used to travel unchecked all the way into `execute_build`, and
    `validate_enterprise_reader` raises `typer.BadParameter` -- which is a
    `click.UsageError`, NOT a `typer.Exit`. The wizard's one `except
    typer.Exit` around the build therefore could not catch it, so a
    mistyped UPN (`svc.reporting`, no `@`) left `run_wizard` as an
    unhandled exception and printed a raw traceback -- on top of a project
    directory the wizard had already written. Validating at the prompt
    keeps the refusal where the answer was given, and keeps it recoverable.

    Blank is deliberately NOT validated. It is the default and it means
    "enrol nobody"; `validate_enterprise_reader` refuses an empty string,
    so passing it through would make the safest answer the question offers
    the one answer that cannot be given.
    """
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import validate_enterprise_reader  # noqa: PLC0415

    while True:
        reader = Prompt.ask(
            "Reporting service account to enrol read-only (UPN), or blank "
            "for none",
            default="",
            console=console,
        ).strip()
        if not reader:
            return ""
        try:
            validate_enterprise_reader(reader)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc.message}[/red]")
            continue
        return reader


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
    # `write_artifact`, not `write_text`. The trap AGENTS.md records is
    # per-call-site: text mode inherits the platform newline, so this wrote
    # CRLF on Windows and handed the operator a mapping whose line endings
    # depend on which machine ran the wizard. The templates ship LF.
    write_artifact(mapping_path, new_text)

    bundle = load_mapping(mapping_path)
    if bundle.mapping.prefix != prefix:
        raise WizardError(
            f"wrote prefix {prefix!r} to {mapping_path} but the mapping "
            f"loaded back as {bundle.mapping.prefix!r}.",
        )


@dataclass(frozen=True)
class _Substitution:
    """One placeholder the wizard answers, and what it was answered with.

    Carries a `label` so the wizard can say which substitutions it made
    rather than counting files and leaving the operator to guess. When only
    the site URL changed, "Repointed 1 doc(s) from RR_ to RR_" was both
    wrong and confusing.
    """

    label: str
    old: str
    new: str

    @property
    def applies(self) -> bool:
        """A placeholder that is absent or already correct is not a change."""
        return bool(self.old) and self.old != self.new

    def describe(self) -> str:
        return f"{self.label} {self.old} -> {self.new}"


def _repoint_docs(
    destination: Path, substitutions: Sequence[_Substitution],
) -> tuple[list[Path], list[_Substitution]]:
    """Point the copied documentation at what the operator actually chose.

    Two things in a shipped family are written as placeholders that the
    wizard then answers:

    * the **list-name prefix**. Changing it renames every list, and the
      template's deploy.md, README.md and governance.md name them
      literally: choosing `ACME_` for risk-register produces `ACME_Risk`
      while deploy.md still says to verify `RR_Risk` exists.
    * the **site URL** in the rebuild command. The operator answers with
      their own site, and without this the copied deploy.md still tells
      them to build against `yourtenant.sharepoint.com/sites/your-site` --
      the one instruction in the folder guaranteed not to work, and the one
      they come back to on every schema change.

    The wizard sends the operator to these files, so documentation that
    disagrees with what was built is the failure this project exists to
    avoid, in miniature. That argument never applied only to the prefix; it
    was just the only substitution that existed.

    Substitutions are LITERAL, never pattern-matched. Not every SharePoint
    URL in a template is the deploy target -- credentialing-register links a
    by-laws page on a governance site -- and rewriting anything URL-shaped
    would invent dead links. `PLACEHOLDER_SITE_URL` is the agreed spelling
    and a template-standard test keeps the families using it.

    Markdown only, and that is checked rather than assumed: nothing else in
    a shipped family carries either value -- the schema declares logical
    names, the mapping's own `prefix:` is already rewritten, the site URL is
    a build argument that appears in no config file, and the formatting JSON
    refers to columns, not lists.

    Returns the files it changed and the substitutions it applied, so the
    caller can report both rather than editing the operator's new
    documentation silently.
    """
    wanted = [s for s in substitutions if s.applies]
    changed: list[Path] = []
    applied: list[_Substitution] = []
    for path in sorted(destination.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        rewritten = text
        for substitution in wanted:
            if substitution.old not in rewritten:
                continue
            rewritten = rewritten.replace(substitution.old, substitution.new)
            if substitution not in applied:
                applied.append(substitution)
        if rewritten == text:
            continue
        # Same reason as the mapping rewrite above, and it matters more here:
        # the site-URL substitution applies on every run, so `write_text`
        # would have rewritten a documentation file in every scaffolded
        # project with CRLF rather than the LF it was copied with.
        write_artifact(path, rewritten)
        changed.append(path)
    return changed, applied


def _scaffold(answers: Answers) -> tuple[list[Path], list[_Substitution]]:
    solution = answers.templates[0].solution
    prefix = answers.templates[0].prefix
    shutil.copytree(
        solution.root,
        answers.destination,
        ignore=shutil.ignore_patterns(*_NEVER_COPY),
        # The destination may already exist: `_ask_destination` accepts an
        # existing EMPTY directory, and without this copytree raises
        # FileExistsError and the wizard reports a scaffold failure for a
        # path it had just told the user was fine.
        dirs_exist_ok=True,
    )
    _rewrite_prefix(
        answers.destination / solution.mapping_path.relative_to(solution.root),
        prefix,
    )
    return _repoint_docs(
        answers.destination,
        (
            _Substitution("prefix", solution.prefix, prefix),
            _Substitution("site URL", PLACEHOLDER_SITE_URL, answers.site_url),
        ),
    )


@dataclass(frozen=True)
class _TemplateFacts:
    """What a shipped mapping declares that changes which questions are put.

    Read from the SHIPPED mapping, before anything is written, so the build
    questions can be asked alongside the rest. Sound because `_rewrite_prefix`
    only ever rewrites the `prefix:` line -- pinned by
    `test_the_facts_match_between_the_shipped_family_and_the_copy`.
    """

    roles: frozenset[str]
    #: `--seed` against a mapping with no `demo_items` raises
    #: `SeedRequiresDemoItemsError` and the build exits non-zero. Offering
    #: the question there would be offering a dead end.
    demo_items: bool
    #: `execute_build` refuses `--enterprise-reader` outright against a
    #: mapping declaring no `enroll_enterprise_reader` group. Same reason.
    reader_group: bool


def _read_facts(solution: Solution) -> _TemplateFacts:
    """Load one template's mapping, or refuse by name.

    `load_mapping` raises `ValueError` for anything it dislikes, `KeyError`
    for an absent required section, and passes through `OSError` and
    `yaml.YAMLError` from the read. The wizard is the error boundary here, so
    all four become one `WizardError` naming the template -- which is what
    the caller prints before writing anything.
    """
    try:
        bundle = load_mapping(solution.mapping_path)
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise WizardError(
            f"the {solution.id} template's mapping could not be loaded: {exc}",
        ) from exc
    permissions = bundle.mapping.permissions
    return _TemplateFacts(
        roles=frozenset(e.site_role for e in bundle.mapping.entities.values()),
        demo_items=any(bundle.mapping.demo_items.values()),
        reader_group=any(
            g.enroll_enterprise_reader
            for g in (permissions.groups if permissions else [])
        ),
    )


def _site_roles(facts: Sequence[_TemplateFacts]) -> list[str]:
    """The roles every chosen template understands, sorted.

    An intersection, not a union: the site role is a property of the SITE
    being deployed to, so a role only one of two templates declares would be
    refused by `_require_known_site_role` for the other. With one template --
    which is what the picker collects today -- this is that template's own
    roles, unchanged.
    """
    if not facts:
        # `frozenset.intersection(*())` raises a bare `TypeError`, not a
        # named refusal -- unreachable from `_run` today, which always
        # passes exactly one element, but the signature accepts any
        # `Sequence` and multi-template selection is where this is headed.
        raise WizardError("no template was chosen, so there is no site role.")
    shared = frozenset.intersection(*(f.roles for f in facts))
    if not shared:
        raise WizardError(
            "the chosen templates share no site role, so there is none this "
            "site could be built under. Declared: "
            + "; ".join(", ".join(sorted(f.roles)) for f in facts),
        )
    return sorted(shared)


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
            "build it into a pasteable deploy script.\n\n"
            "[dim]Everything here is also available as flags -- run "
            "`dbml-sharepoint build --help`.[/dim]",
            title="dbml-sharepoint",
            border_style="green",
        ),
    )

    solution = _pick_solution(console, solutions)
    try:
        facts = _read_facts(solution)
    except WizardError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    _describe(console, solution)

    destination = _ask_destination(console, solution)
    prefix = _ask_prefix(console, solution)
    site_url = _ask_site_url(console)
    answers = Answers(
        destination=destination,
        site_url=site_url,
        templates=(TemplateChoice(solution, prefix),),
    )

    console.print()
    console.print(
        Panel(
            f"[bold]Template[/bold]  {answers.templates[0].solution.id}\n"
            f"[bold]Directory[/bold] {answers.destination}\n"
            f"[bold]Prefix[/bold]    {answers.templates[0].prefix}\n"
            f"[bold]Site[/bold]      {answers.site_url}",
            title="About to write",
            border_style="yellow",
        ),
    )
    if not Confirm.ask("Write these files?", default=True, console=console):
        console.print("[yellow]Nothing written.[/yellow]")
        return 0

    try:
        repointed, applied = _scaffold(answers)
    except (WizardError, OSError) as exc:
        console.print(f"[red]Could not scaffold the project:[/red] {exc}")
        return 1

    mapping_path = answers.destination / "20-configure" / "mapping.yaml"
    schema_path = answers.destination / "10-design" / "schema.dbml"
    release_path = answers.destination / "20-configure" / "release.yaml"
    console.print(f"\n[green]Wrote[/green] {answers.destination}")
    if repointed:
        # Say so, and say WHICH, rather than editing the user's new
        # documentation silently. Naming the substitutions matters now that
        # there is more than one: reporting a file count and a prefix pair
        # when only the site URL moved read as "Repointed 1 doc(s) from RR_
        # to RR_", which is worse than saying nothing.
        console.print(
            f"[dim]Repointed {len(repointed)} doc(s): "
            f"{', '.join(s.describe() for s in applied)}.[/dim]",
        )

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

    roles = _site_roles([facts])
    if len(roles) == 1:
        site_role = roles[0]
    elif "default" in roles:
        # Every shipped family declares `default`, so Enter is a real answer
        # whenever the mapping declares it too.
        site_role = Prompt.ask(
            "[bold]Site role[/bold]", choices=roles, default="default", console=console,
        )
    else:
        # No default offered, because `Prompt.ask` returns one WITHOUT
        # checking it against `choices` -- rich short-circuits an empty
        # answer in `PromptBase.__call__` before `process_response` runs.
        # A fixed `default="default"` therefore let Enter answer a mapping
        # whose roles are `hq` and `branch` with a role it never declared,
        # and `execute_build` refused it: a dead end behind the key that
        # looks safest. Here Enter is not an answer and the prompt repeats.
        site_role = Prompt.ask("[bold]Site role[/bold]", choices=roles, console=console)

    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import execute_build  # noqa: PLC0415

    # Offered only where the mapping declares a group `--enterprise-reader`
    # could enrol into -- see `_TemplateFacts.reader_group`. Blank stays the
    # default and must map to None, never "": an empty string would reach
    # `validate_enterprise_reader` and abort a run where the operator simply
    # pressed Enter, which is exactly the safe answer this question exists
    # to allow. Anything NON-blank is validated at the prompt and re-asked
    # on refusal -- see `_ask_enterprise_reader`; the `except typer.Exit`
    # below cannot catch what that validator raises.
    reader = ""
    if facts.reader_group:
        reader = _ask_enterprise_reader(console)

    # Every colour map, row wash and declared view is invisible on an empty
    # list, and the wizard is the one path aimed at somebody who has not seen
    # this tool work -- so it was the one path that could not show them.
    # Offered only where the mapping HAS demo items, and declined by default:
    # seeding writes `[DEMO]` rows into a real site, and the wizard must not
    # be more forward than the documented flag it stands for.
    seed = False
    if facts.demo_items:
        # The caution goes BEFORE the question, because the question is where
        # the decision is made. A shipped family may seed deliberately alarming
        # data to make a view render at all -- equipment-maintenance ships one
        # genuinely overdue infusion pump, eighteen days past its annual
        # service, and its guide says in as many words not to seed a site that
        # already holds a real schedule. Governance there treats an overdue row
        # as work to explain within five business days. Offering to create that
        # and mentioning the guide afterwards is offering it too late.
        #
        # The escape before [DEMO] is rich's documented way to mean a
        # literal bracket. MEASURED 2026-08-11: rich prints it identically
        # with or without, because DEMO is not a style it knows. Kept
        # anyway -- it is the documented spelling and costs one character
        # -- but NOT because an unescaped one was seen to break. An
        # earlier version of this comment claimed rich swallowed it, which
        # was never measured and is false.
        console.print(
            r"[dim]Demo rows are titled \[DEMO] and rollback treats a list of "
            "them as demo-only. Some families seed deliberately alarming data "
            "so a view renders at all -- read "
            f"{answers.destination / '30-deploy' / 'deploy.md'} before seeding "
            "a site that already holds real data.[/dim]",
        )
        seed = Confirm.ask(
            "Add the template's demo rows, so the views and colours have "
            "something to show?",
            default=False,
            console=console,
        )

    try:
        execute_build(
            schema=schema_path,
            mapping=mapping_path,
            release=release_path,
            site_url=answers.site_url,
            site_role=site_role,
            out=answers.destination / "build",
            seed=seed,
            enterprise_reader=reader or None,
        )
    except typer.Exit as exc:
        # The build refused and has already said why on stderr. Its exit
        # code is the documented contract; pass it through rather than
        # flattening every refusal to 1.
        return int(exc.exit_code)

    console.print(
        Panel(
            f"Paste [bold]{answers.destination / 'build' / ASSESS_SCRIPT}"
            "[/bold] into the target site's console first -- it is read-only "
            "and tells you what is already there.\n\n"
            "Then [bold]"
            f"{answers.destination / 'build' / DEPLOY_SCRIPT}[/bold]."
            # A seeded bundle carries a THIRD script, and pasting the
            # other two leaves the list empty. Adding a file to the
            # bundle without adding it to the instructions is how
            # somebody seeds, sees no rows, and concludes the demo data
            # is broken.
            + (
                # The guide is named BEFORE the demo script, not after it:
                # a family may seed data its own procedure tells you not
                # to put on a live site, and an instruction read first is
                # the only one that can prevent that.
                f"\n\nRead [bold]"
                f"{answers.destination / '30-deploy' / 'deploy.md'}[/bold]"
                " for this template's seeding conditions, then paste "
                f"[bold]{answers.destination / 'build' / DEMO_SCRIPT}"
                "[/bold] for the demo rows."
                if seed
                else ""
            )
            + "\n\n"
            f"[dim]{answers.destination / '30-deploy' / 'deploy.md'} has the "
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
