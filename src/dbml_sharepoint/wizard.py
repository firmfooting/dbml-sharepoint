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
    """What the wizard collected, before anything is written.

    Every field is filled before the single confirmation, which is the
    point: the operator reviews the whole decision once rather than
    confirming a write and then being asked three more questions.
    """

    destination: Path
    site_url: str
    site_role: str
    templates: tuple[TemplateChoice, ...]
    build: bool
    reader: str
    seed: bool


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
            "[bold]Template[/bold] (number or name)",
            console=console,
        ).strip()
        if not answer:
            # No default. `solutions[0].id` is whatever sorts first --
            # `asset-register` -- which is not an answer, and Enter used to
            # scaffold it silently. Blank is not a mistake worth an error
            # message; just ask again.
            continue
        if answer in by_name:
            return by_name[answer]
        if answer.isdigit() and 1 <= int(answer) <= len(solutions):
            return solutions[int(answer) - 1]
        console.print(f"[red]No template {answer!r}.[/red] Pick a number or a name.")


def _describe(console: Console, solution: Solution) -> None:
    """What the chosen template is, in two lines rather than a box.

    A Panel here competed with the Review panel four questions later, and
    the operator has just chosen this template off a table that already
    named it -- so the point is confirmation, not presentation.
    """
    lists = ", ".join(solution.lists) or "(none declared)"
    count = len(solution.lists)
    console.print(
        f"\n  [bold]{solution.title}[/bold]  -  {count} list"
        f"{'' if count == 1 else 's'}: {lists}",
    )
    # `detail`, not `summary`: `summary` is capped at `_SUMMARY_MAX` so it
    # fits the table cell above, and reusing it here cut risk-register's
    # sentence at `...SharePoint calculates Resi...`.
    if solution.detail:
        console.print(f"  [dim]{solution.detail}[/dim]\n")


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


def _ask_site_role(console: Console, roles: list[str]) -> str:
    """Which site role to build under. Not asked when there is only one.

    Asked in the site section rather than the build section, because the role
    describes the site and because the command printed when the build is
    declined has to carry `--site-role`. It could not, while the question
    came after `Build it now?`.
    """
    if len(roles) == 1:
        return roles[0]
    if "default" in roles:
        # Every shipped family declares `default`, so Enter is a real answer
        # whenever the mapping declares it too.
        return Prompt.ask(
            "[bold]Site role[/bold]", choices=roles, default="default",
            console=console,
        )
    # No default offered, because `Prompt.ask` returns one WITHOUT checking it
    # against `choices` -- rich short-circuits an empty answer in
    # `PromptBase.__call__` before `process_response` runs. A fixed
    # `default="default"` therefore let Enter answer a mapping whose roles are
    # `hq` and `branch` with a role it never declared, and `execute_build`
    # refused it: a dead end behind the key that looks safest.
    return Prompt.ask("[bold]Site role[/bold]", choices=roles, console=console)


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


def _ask_seed(console: Console) -> bool:
    """Offer the template's demo rows, caution first.

    Every colour map, row wash and declared view is invisible on an empty
    list, and the wizard is the one path aimed at somebody who has not seen
    this tool work -- so it was the one path that could not show them.
    Declined by default: seeding writes `[DEMO]` rows into a real site, and
    the wizard must not be more forward than the documented flag it stands
    for.

    The caution goes BEFORE the question, because the question is where the
    decision is made. A shipped family may seed deliberately alarming data to
    make a view render at all -- equipment-maintenance ships one genuinely
    overdue infusion pump, eighteen days past its annual service, and its
    guide says in as many words not to seed a site that already holds a real
    schedule.

    The guide is named by its path INSIDE the project, not absolutely: this
    runs before the destination has been written, and the operator is told
    where the project is by the Review panel a moment later.

    The escape before [DEMO] is rich's documented way to mean a literal
    bracket. MEASURED 2026-08-11: rich prints it identically with or without,
    because DEMO is not a style it knows. Kept anyway -- it is the documented
    spelling and costs one character -- but NOT because an unescaped one was
    seen to break.
    """
    guide = "30-deploy/deploy.md"
    console.print(
        r"[dim]  Demo rows are titled \[DEMO] and rollback treats a list of "
        "them as demo-only.\n  Some families seed deliberately alarming data "
        f"so a view renders at all -- read\n  {guide} before seeding a site "
        "that already holds real data.[/dim]",
    )
    return Confirm.ask("Add the demo rows?", default=False, console=console)


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
    root: Path, substitutions: Sequence[_Substitution],
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

    Scoped to ONE template's tree, not the whole project directory. The
    prefix substitution belongs to the template that declared it, so a
    project holding two templates must not have the first one's prefix
    rewritten through the second one's deploy.md. Identical while the picker
    collects one template, which is why it is worth fixing before it does not.
    """
    wanted = [s for s in substitutions if s.applies]
    changed: list[Path] = []
    applied: list[_Substitution] = []
    for path in sorted(root.rglob("*.md")):
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
    changed: list[Path] = []
    applied: list[_Substitution] = []
    for choice in answers.templates:
        root = _template_root(answers, choice)
        shutil.copytree(
            choice.solution.root,
            root,
            ignore=shutil.ignore_patterns(*_NEVER_COPY),
            # The destination may already exist: `_ask_destination` accepts an
            # existing EMPTY directory, and without this copytree raises
            # FileExistsError and the wizard reports a scaffold failure for a
            # path it had just told the user was fine.
            dirs_exist_ok=True,
        )
        _rewrite_prefix(
            root / choice.solution.mapping_path.relative_to(choice.solution.root),
            choice.prefix,
        )
        template_changed, template_applied = _repoint_docs(
            root,
            (
                _Substitution("prefix", choice.solution.prefix, choice.prefix),
                _Substitution("site URL", PLACEHOLDER_SITE_URL, answers.site_url),
            ),
        )
        changed.extend(template_changed)
        applied.extend(s for s in template_applied if s not in applied)
    return changed, applied


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


#: Wide enough for `Reporting`, the longest label.
_REVIEW_LABEL = 10


def _review_row(label: str, value: str) -> str:
    return f"[bold]{label:<{_REVIEW_LABEL}}[/bold] {value}"


def _review_panel(answers: Answers) -> Panel:
    """Every answer, once, before the single confirmation.

    `Lists` is the load-bearing row. A blank prefix is a valid answer now, so
    this is the only place the operator sees whether they are about to create
    `Risk` or `ACME_Risk`. The titles are `prefix + entity`, which is what
    the generators do -- reported, not predicted.
    """
    rows = []
    for choice in answers.templates:
        rows.append(
            _review_row(
                "Template", f"{choice.solution.id} - {choice.solution.title}",
            ),
        )
        rows.append(_review_row("Lists", ", ".join(choice.list_titles())))
    rows.append(_review_row("Directory", str(answers.destination)))
    rows.append(_review_row("Site", answers.site_url))
    if not answers.build:
        rows.append(_review_row("Build", "no, copy the files only"))
    else:
        rows.append(_review_row("Build", f"yes, site role {answers.site_role}"))
        rows.append(_review_row("Reporting", answers.reader or "nobody"))
        rows.append(_review_row("Demo rows", "yes" if answers.seed else "no"))
    return Panel("\n".join(rows), title="Review", border_style="yellow")


def _rebuild_command(answers: Answers) -> str:
    """What to run later, complete enough to actually work.

    `--site-role` is always present. It used to be absent because the wizard
    printed this before asking, so against a mapping declaring `hq` and
    `branch` the command it handed the operator was one
    `_require_known_site_role` refuses.
    """
    choice = answers.templates[0]
    inside = _within(_template_root(answers, choice), answers.destination)
    return (
        "\nWhen you are ready:\n\n"
        f"  [bold]cd {answers.destination}[/bold]\n"
        "  [bold]dbml-sharepoint build \\\n"
        f"    --schema {inside}10-design/schema.dbml \\\n"
        f"    --mapping {inside}20-configure/mapping.yaml \\\n"
        f"    --release {inside}20-configure/release.yaml \\\n"
        f"    --site-url {answers.site_url} \\\n"
        f"    --site-role {answers.site_role} \\\n"
        f"    --out ./{inside}build[/bold]"
    )


def _next_panel(answers: Answers) -> Panel:
    """The procedure, numbered, with paths relative to the project.

    Absolute paths inside the steps wrapped and broke the box, and the
    operator is told where the project is by the panel's own first line, so
    only that one is absolute.

    OBSERVED 2026-08-12 on a real run: an unseeded panel names `deploy.md`
    once, in the footer; a seeded one names it again in step 3. That is two
    mentions, not one -- kept, because a caution that does not carry the path
    it points at is not a caution, and the footer's claim ("the full
    procedure") is a different claim from step 3's ("this template's seeding
    conditions").
    """
    choice = answers.templates[0]
    inside = _within(_template_root(answers, choice), answers.destination)
    guide = f"{inside}30-deploy/deploy.md"
    steps = [
        (
            f" 1. Paste [bold]{inside}build/{ASSESS_SCRIPT}[/bold] into the "
            "target site's console. It is read-only, and it is how you find "
            "out whether these list names are already taken."
        ),
        f" 2. Paste [bold]{inside}build/{DEPLOY_SCRIPT}[/bold].",
    ]
    if answers.seed:
        # The guide is named BEFORE the demo script, not after it: a family
        # may seed data its own procedure tells you not to put on a live
        # site, and an instruction read first is the only one that can
        # prevent that. A seeded bundle carries a THIRD script, and pasting
        # the other two leaves the list empty.
        steps.append(
            f" 3. Read [bold]{guide}[/bold] for this template's seeding "
            f"conditions, then paste [bold]{inside}build/{DEMO_SCRIPT}"
            "[/bold] for the demo rows.",
        )
    return Panel(
        f"In [bold]{answers.destination}[/bold]:\n\n"
        + "\n\n".join(steps)
        + f"\n\n[dim]{guide} has the full procedure for this template.[/dim]",
        title="Next",
        border_style="green",
    )


def _run(console: Console) -> int:
    solutions = available_solutions()
    if not solutions:
        console.print(
            "[red]No templates found.[/red] This build of dbml-sharepoint "
            "shipped without them.",
        )
        return 1

    console.print(
        Panel(
            "Copy a shipped template into a project of your own, then build "
            "it into a pasteable deploy script.\n\n"
            "[dim]Everything here is also available as flags -- run "
            "`dbml-sharepoint build --help`.[/dim]",
            title="dbml-sharepoint",
            border_style="green",
        ),
    )

    # rich degrades a rule to ASCII by itself: `Rule.__rich_console__`
    # substitutes "-" when `options.ascii_only` and the configured characters
    # are not. VERIFIED against rich 15.0.0 on 2026-08-12, which is why no
    # `characters=` argument is passed. The section TITLES are literals in
    # this module and must stay ASCII regardless.
    console.rule("Template")
    solution = _pick_solution(console, solutions)
    _describe(console, solution)
    # Unconditional here. Task 7 makes the prefix optional and gates this
    # call on `solution.prefix`; keeping the two changes apart keeps this
    # task's diff about the SEQUENCE and nothing else.
    prefix = _ask_prefix(console, solution)
    choice = TemplateChoice(solution, prefix)

    try:
        facts = _read_facts(solution)
        roles = _site_roles([facts])
    except WizardError as exc:
        # Before anything is written. This used to happen after the copy and
        # outside any guard, so a template the loader rejected produced a
        # traceback on top of a project directory that already existed.
        console.print(f"[red]{exc}[/red]")
        return 1

    console.rule("Site")
    destination = _ask_destination(console, solution)
    site_url = _ask_site_url(console)
    site_role = _ask_site_role(console, roles)

    console.rule("Build")
    build = Confirm.ask(
        "Build the deploy scripts now?", default=True, console=console,
    )
    reader = ""
    seed = False
    if build:
        # Offered only where the mapping declares a group
        # `--enterprise-reader` could enrol into. Blank stays the default and
        # must map to None below, never "": an empty string would reach
        # `validate_enterprise_reader` and abort a run where the operator
        # simply pressed Enter, which is the safe answer the question exists
        # to allow. Anything NON-blank is validated at the prompt and re-asked
        # on refusal -- the `except typer.Exit` below cannot catch what
        # `validate_enterprise_reader` raises, because `typer.BadParameter` is
        # a `click.UsageError`.
        if facts.reader_group:
            reader = _ask_enterprise_reader(console)
        if facts.demo_items:
            seed = _ask_seed(console)

    answers = Answers(
        destination=destination,
        site_url=site_url,
        site_role=site_role,
        templates=(choice,),
        build=build,
        reader=reader,
        seed=seed,
    )

    console.rule("Review")
    console.print(_review_panel(answers))
    if not Confirm.ask(
        "Write the project and build it?" if build else "Write the project?",
        default=True,
        console=console,
    ):
        console.print("[yellow]Nothing written.[/yellow]")
        return 0

    try:
        repointed, applied = _scaffold(answers)
    except (WizardError, OSError) as exc:
        console.print(f"[red]Could not scaffold the project:[/red] {exc}")
        return 1

    console.print(f"\n[green]Wrote[/green] {answers.destination}")
    if repointed:
        # Said plainly, and NOT dimmed: this reports edits the wizard made to
        # the operator's own new files. Naming the substitutions matters
        # because there is more than one -- reporting a file count and a
        # prefix pair when only the site URL moved read as "Repointed 1
        # doc(s) from RR_ to RR_", which is worse than saying nothing.
        console.print(
            f"Updated {len(repointed)} documentation file(s): "
            f"{', '.join(s.describe() for s in applied)}.",
        )

    if not build:
        console.print(_rebuild_command(answers))
        return 0

    # Deferred for a cycle: cli.py imports this module at its top, so this
    # direction stays lazy until `execute_build` leaves the CLI -- #171.
    from dbml_sharepoint.cli import execute_build  # noqa: PLC0415

    for template in answers.templates:
        root = _template_root(answers, template)
        try:
            execute_build(
                schema=root / "10-design" / "schema.dbml",
                mapping=root / "20-configure" / "mapping.yaml",
                release=root / "20-configure" / "release.yaml",
                site_url=answers.site_url,
                site_role=answers.site_role,
                out=root / "build",
                seed=answers.seed,
                enterprise_reader=answers.reader or None,
            )
        except typer.Exit as exc:
            # The build refused and has already said why on stderr. Its exit
            # code is the documented contract; pass it through rather than
            # flattening every refusal to 1.
            return int(exc.exit_code)

    console.print(_next_panel(answers))
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
