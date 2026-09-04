"""The interactive template wizard: the default `dbml-sharepoint` command.

Copies one shipped template into a project directory of the user's own,
optionally gives its lists a name prefix, and offers to build it. The prefix
is a yes/no gate -- "Give these lists a name prefix?", defaulting to no --
followed by the value prompt only when the answer is yes; a template
declaring no prefix skips the pair entirely. Pressing Enter at that gate now
produces unprefixed lists, the opposite of the old default. The Review
panel's `Lists` row is what shows the operator the names they are actually
about to create. It is the safety net for that reversed default, and it
matters for as long as a blank prefix is a valid answer.

Every question is asked before anything is written, and the whole decision is
reviewed once. The alternative -- confirming a write, then being asked three
more questions, then having a deploy bundle generated against a real site --
put the operator's commitment before the facts they were committing to.

Scope is deliberate. The wizard changes **identity only** -- prefix, site
URL, site role, where the files land. It never edits the schema or the
mapping's structure. Those templates are the tested artifacts: every one of
them is built end-to-end in CI and held to `test_template_standard.py`, and a
wizard that let a user restructure one would be handing them an untested
mapping while implying the opposite.

It is a front end onto `cli.execute_build`, not a second builder. Anything
the wizard produces, the documented flags could have produced.

`Answers` is deliberately plural in its templates. Deploying several
templates to one site is where this is going; `execute_build` takes a single
mapping, so that still means one bundle each, and making it one bundle is a
feature with its own design. What is drawn here is the boundary -- per-site
answers apart from per-template ones -- not the feature.

Every string literal in this module must be ASCII: it is in `_CONSOLE_BOUND`
and `test_messages_bound_for_a_console_are_ascii` walks the AST.
"""

import re
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.bundle import (
    ASSESS_SCRIPT,
    DEMO_SCRIPT,
    DEPLOY_SCRIPT,
    write_artifact,
)
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    PLACEHOLDER_SITE_URL,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
    Journey,
    Solution,
    available_journeys,
    available_solutions,
)
from dbml_sharepoint.model.env_file import (
    ENTERPRISE_READER_KEY,
    ENV_FILENAME,
    EnvFileError,
    read_env_file,
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
#: validator or the shipped templates supports. That is precisely
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
    #: Every entity the mapping declares, paired with the site role that
    #: deploys it. Pairs rather than a dict so the dataclass stays hashable
    #: like its siblings. Sourced from `_TemplateFacts`, which has already
    #: loaded the mapping, so this costs no second read.
    entity_roles: tuple[tuple[str, str], ...]

    def list_titles(self, site_role: str) -> tuple[str, ...]:
        """The SharePoint list titles this template creates for one site role.

        A method rather than a property because it iterates. The rule it
        obeys is plain concatenation, which is what every generator that
        names a list does -- `jsgen`, `assessgen`, `demogen`, `manifestgen`
        and `reportgen` each build the title as `prefix + entity_name` -- so
        this reports the build's behaviour rather than predicting it.

        Named by MODULE, not by line. An earlier version of this docstring
        cited five `file:line` pairs and four of them had drifted within one
        stack of rebases, pointing at a blank line, a docstring and a list
        initialiser. A citation that rots is worse than none: it reads as
        precision and sends the next person to the wrong place.

        FILTERED BY SITE ROLE, because the build is. Every generator goes
        through `ordering.site_tables_in_order`, which keeps only entities
        whose `site_role` matches the one being built. Reporting
        `Solution.lists` unfiltered made the Review panel promise every list
        in the mapping: a mapping declaring `default: Risk` and
        `archive: Archive` had the panel name both while the bundle created
        only `Risk`. Unreachable with the shipped families, which all
        declare `default` and nothing else -- but the site-role question
        exists precisely for the mappings where it is not.

        The ORDER is the mapping's declaration order, not the dependency
        order `site_tables_in_order` computes from the schema. A review names
        a set; matching the order would mean parsing the DBML here for no
        gain the operator can see.
        """
        return tuple(
            self.prefix + name
            for name, role in self.entity_roles
            if role == site_role
        )


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
    #: None when the reader question was never asked, because the mapping
    #: declares no group to enrol into. Blank means it was asked and answered
    #: "nobody". The two must stay distinct: only the second one outranks a
    #: value `dbml-sharepoint.env` supplies.
    reader: str | None
    seed: bool
    #: The `dbml-sharepoint.env` the wizard consulted, if any, threaded into
    #: `execute_build` so its artefacts report the same file. None only when
    #: no file was there to consult.
    env_file: Path | None = None


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
        # "Templates", not "Solution templates". One word for the thing:
        # the intro panel, this table and the prompt below it all say
        # `template`, so a reader never has to work out whether a "solution
        # template" is the same thing as a "template".
        title="Templates",
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


#: What the journey step accepts to mean "show me everything".
_BROWSE_ALL = "all"


def _journey_table(journeys: list[Journey]) -> Table:
    table = Table(
        title="Where to start",
        header_style="bold",
        title_style="bold",
        show_lines=False,
        expand=False,
    )
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Journey", no_wrap=True)
    table.add_column("Templates", justify="right", no_wrap=True)
    table.add_column("What it covers")
    for index, journey in enumerate(journeys, start=1):
        table.add_row(
            str(index), journey.id, str(len(journey.solution_ids)), journey.summary,
        )
    table.add_row("", _BROWSE_ALL, "", "Every template, in one list")
    return table


def _pick_journey(
    console: Console, journeys: list[Journey], solutions: list[Solution],
) -> Solution | list[Solution]:
    """Narrow the catalogue to one reading order, or answer the whole question.

    The whole shelf in one table is a wall, and the number beside each row
    changes whenever a template is added. A journey answers the question
    somebody actually arrives with, which is what they are trying to do
    rather than which register they already know the name of.

    A TEMPLATE NAME IS ALSO AN ANSWER HERE, returned as the choice itself.
    The name has always been the stable handle -- it is what the docs and the
    rebuild command use -- so somebody who arrives knowing `risk-register`
    types it once rather than passing through a menu that exists for people
    who do not.
    """
    if not journeys:
        return solutions
    by_id = {s.id: s for s in solutions}
    console.print(_journey_table(journeys))
    while True:
        answer = Prompt.ask(
            f"[bold]Journey[/bold] (number, name, {_BROWSE_ALL}, or a template)",
            console=console,
        ).strip()
        if not answer:
            continue
        if answer == _BROWSE_ALL:
            return solutions
        if answer in by_id:
            return by_id[answer]
        chosen = next((j for j in journeys if j.id == answer), None)
        if chosen is None and answer.isdigit() and 1 <= int(answer) <= len(journeys):
            chosen = journeys[int(answer) - 1]
        if chosen is None:
            console.print(
                f"[red]No journey or template {answer!r}.[/red] "
                f"Pick a number, a name, or {_BROWSE_ALL}.",
            )
            continue
        # A journey names ids; anything it names that is not on the shelf is
        # a broken journey, and `test_journeys.py` fails the build for it. Be
        # forgiving here anyway rather than crash a picker over a doc file.
        narrowed = [by_id[i] for i in chosen.solution_ids if i in by_id]
        if not narrowed:
            console.print(f"[red]Journey {answer!r} names no template that exists.[/red]")
            continue
        return narrowed


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
    # The declared prefix is shown here, not only in the prompt that follows.
    # A template declaring no prefix is never asked for one at all, which
    # makes this the only place the operator learns what the lists are
    # called before the Review panel names them.
    console.print(
        f"\n  [bold]{escape(solution.title)}[/bold]  -  {count} list"
        f"{'' if count == 1 else 's'}: {lists}"
        f"  -  prefix {solution.prefix or '(none)'}",
    )
    # `detail`, not `summary`: `summary` is capped at `_SUMMARY_MAX` so it
    # fits the table cell above, and reusing it here cut risk-register's
    # sentence at `...SharePoint calculates Resi...`.
    #
    # Routed through `_guidance`, not printed with a hand-written indent:
    # this was the only dim block on screen that still wrapped to column 0,
    # once `_ask_prefix` picked up the same helper for its own guidance line.
    if solution.detail:
        _guidance(console, solution.detail)


def _guidance(console: Console, text: str) -> None:
    """A dim explanatory block, indented under the prompt it precedes.

    Indented through `Padding`, NOT by writing two spaces into the string.
    rich re-wraps at the console width, so a literal indent applies to the
    first line only and every continuation restarts at column 0 -- MEASURED
    at width 72 on 2026-08-12: the reporting guidance broke after `template`
    and put `creates,` hard against the margin, and the seed caution put
    `-- read` there. `Padding` narrows the render width instead, so every
    line of the block sits at the same column and the block reads as one
    thing rather than as prose that fell out of its own indent.

    Shared across every dim block in the wizard: the reporting and seed
    guidance, `_ask_prefix`'s own guidance line, and `_describe`'s detail
    sentence. A guidance line that indents differently from its neighbours is
    a worse defect than one that does not indent at all, since it reads as
    though it belongs to something else.

    Callers pass ONE unbroken string: line breaks are rich's to choose, and
    a hand-placed `\\n` is a wrap decision made against a width the author
    cannot see.
    """
    console.print(Padding(f"[dim]{text}[/dim]", (0, 0, 0, 2)))


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
            console.print(
                f"[red]{escape(str(destination))} exists and is not a "
                "directory.[/red]",
            )
            continue
        if any(destination.iterdir()):
            console.print(
                f"[red]{escape(str(destination))} already exists and is not "
                "empty.[/red] "
                "Pick a path that does not exist yet.",
            )
            continue
        return destination


def _ask_prefix(console: Console, solution: Solution) -> str:
    """Whether this template's lists carry a prefix, and if so, which.

    A yes/no gate, DEFAULTING TO NO, in front of the value prompt -- not a
    blank answer AT the value prompt meaning "no prefix", which is what this
    function did for one round. MEASURED then, and still the reason the gate
    exists rather than a sentinel answer: rich's `PromptBase.__call__` reads

        if value == "" and default != ...:
            return default

    -- so a truly empty raw answer at a prompt carrying `default=solution.
    prefix` (non-empty, since this function only runs when the template
    declares one) can NEVER resolve to blank. It always resolves to the
    declared prefix, before this function's own code runs at all. There was
    no answer an operator could type at a single prompt that reliably meant
    "no prefix" without also being indistinguishable from a typo -- a
    whitespace trick worked only by accident of `.strip()`, and typing a
    real value versus typing "nothing, on purpose" are different decisions
    that deserve different questions.

    Defaulting to NO is deliberate and reverses the old single-prompt
    behaviour, where Enter accepted the template's declared prefix: the
    direction of this project is that prefixes go away, so pressing Enter
    now produces UNPREFIXED lists. The Review panel's `Lists` row is the
    safety net that shows `Risk` versus `RR_Risk` before anything is
    written -- see `_review_panel`.

    Only reached when `solution.prefix` is truthy -- `_run` gates the call
    itself, the same way it gates the reporting and demo-rows questions --
    so a template declaring no prefix asks NEITHER question.

    Once past the gate, the value prompt reverts to requiring a real,
    well-formed value: blank there is refused exactly as it was before this
    function ever grew a "no prefix" meaning, since "no prefix" is now
    answered by the gate and never reaches this prompt at all.
    """
    _guidance(
        console,
        "A prefix keeps these lists from colliding with others named the "
        "same thing. Say no to use the template's own names.",
    )
    if not Confirm.ask(
        "Give these lists a name prefix?", default=False, console=console,
    ):
        return ""
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

    NO `default=`. `cli.NO_SAFE_DEFAULT` names this input, and the reason is
    in `_project_input`'s docstring: a defaulted target arms a real bundle,
    manifest and reporting pack against somebody else's tenant, with only
    the wrong-site guard between that and a mispaste. The shipped default
    `https://contoso.sharepoint.com/sites/example` PASSED `validate_site_url`,
    so Enter was a silently accepted answer rather than a refused one. rich
    returns a default from `PromptBase.__call__` before this function sees
    it, exactly as `_ask_site_role` and `_ask_enterprise_reader` record, so
    removing it is the only fix. `test_no_wizard_default_for_a_named_input`
    holds this.
    """
    # Deferred for a cycle: cli.py imports this module at its top, so this
    # direction stays lazy until `validate_site_url` leaves the CLI -- #171.
    from dbml_sharepoint.cli import (  # noqa: PLC0415
        _site_url_notice,
        validate_site_url,
    )

    # Shown rather than offered: the shape was the only thing the removed
    # default gave the operator, and a printed example cannot be pressed.
    console.print(f"[dim]  For example: {PLACEHOLDER_SITE_URL}[/dim]")
    while True:
        # An empty answer reaches `validate_site_url`, which refuses it, so
        # this loop re-asks rather than falling through. See the docstring.
        site_url = Prompt.ask(
            "[bold]SharePoint site URL[/bold]",
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


def _reader_from_env_file(console: Console) -> tuple[Path, str | None] | None:
    """The `dbml-sharepoint.env` consulted for a suggested UPN, and what it
    suggested: `(path, upn)`, with `upn` None when it offered nothing usable.
    None only when there was no file at all.

    Read relative to the CURRENT directory, the location `build` defaults
    to, not the destination about to be written: `_ask_destination` refuses a
    non-empty destination and `_scaffold` copies the template in afterwards,
    so only the CWD can already hold the file.

    The path comes back even when the key is absent or its value invalid,
    because the file was read and every provenance artefact must say so.

    A file that fails to PARSE is fatal and raises `WizardError`, carrying
    `EnvFileError`'s message, which already names the path, line and text.
    `_run` catches it before anything is written. Warning and proceeding
    would let the manifest and index.md claim no file was ever there.

    An invalid VALUE in a file that parses is not fatal: it is reported, the
    suggestion is withdrawn, and the path still threads through. Unlike
    `build`, the value here is only ever a suggestion the operator must
    retype, so whatever they answer is validated at the prompt regardless.
    """
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import validate_enterprise_reader  # noqa: PLC0415

    path = Path(ENV_FILENAME)
    if not path.exists():
        return None
    if not path.is_file():
        raise WizardError(
            f"{ENV_FILENAME} exists but is not a file. Remove it, or build "
            "with --env-file pointing at a real one.",
        )
    try:
        file_settings, _digest = read_env_file(path)
    except EnvFileError as exc:
        raise WizardError(str(exc)) from exc
    reader = file_settings.get(ENTERPRISE_READER_KEY)
    if reader is None:
        return path, None
    try:
        validate_enterprise_reader(reader)
    except typer.BadParameter as exc:
        console.print(
            f"[red]{ENV_FILENAME} suggests a reader that is not valid: "
            f"{exc.message}[/red]",
        )
        return path, None
    return path, reader


def _ask_enterprise_reader(
    console: Console,
    consulted: tuple[Path, str | None] | None,
) -> str:
    """Prompt until the answer is blank or passes the CLI's own validator.

    `consulted` is `_reader_from_env_file`'s result, read by the caller so
    the file is still consulted where this prompt is never offered.

    Validating at the prompt keeps a refusal recoverable. The answer used to
    travel unchecked into `execute_build`, where `validate_enterprise_reader`
    raises `typer.BadParameter`; that is a `click.UsageError`, not a
    `typer.Exit`, so the wizard's one `except typer.Exit` could not catch it
    and a mistyped UPN printed a raw traceback over an already-written
    project directory.

    Blank is deliberately NOT validated. It is the default and means "enrol
    nobody", and `validate_enterprise_reader` refuses an empty string, so
    checking it would make the safest answer the one answer nobody can give.

    A file suggestion is named in the PROMPT TEXT and NEVER passed as
    `default=`. rich's `PromptBase.__call__` returns the default before this
    function's own code runs, so a non-blank default would make a blank
    answer resolve to the file's value instead of "enrol nobody", exactly
    the defect `_ask_prefix`'s docstring records. WRITE THE REASON AT THIS
    LINE if you are tempted to simplify this into a `default=`. Accepting
    the suggestion means typing it; Enter always means nobody.
    """
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import validate_enterprise_reader  # noqa: PLC0415

    _guidance(
        console,
        "A service account enrolled read-only across every list this "
        "template creates, so it can report on them. Blank for none.",
    )
    suggestion = consulted[1] if consulted is not None else None
    label = "[bold]Reporting account (UPN)[/bold]"
    if suggestion is not None:
        label += (
            f" ({ENV_FILENAME} suggests {escape(suggestion)}; type it to "
            "accept, or leave blank for none)"
        )
    while True:
        # NOT `default=suggestion` -- see the docstring above.
        reader = Prompt.ask(label, default="", console=console).strip()
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

    That path assumes ONE template, which is what the picker collects: the
    fragment is spelled literally here while `_next_panel` computes it as
    `f"{inside}30-deploy/deploy.md"`. The two diverge the day several
    templates are chosen and nest under their own ids, because this question
    is asked once for the whole run and there would then be one guide per
    template. Fixing it needs the multi-template selection that owns the
    question, so it is named here rather than guessed at.

    The escape before the marker is rich's documented way to mean a literal
    bracket. MEASURED 2026-08-11: rich prints it identically with or without,
    because DEMO is not a style it knows. Kept anyway -- it is the documented
    spelling and costs one character -- but NOT because an unescaped one was
    seen to break.

    The marker is interpolated without its trailing space, which the sentence
    supplies: this names the marker mid-sentence rather than quoting the
    string a Title is matched against.
    """
    guide = "30-deploy/deploy.md"
    _guidance(
        console,
        rf"Demo rows are titled \{DEMO_TITLE_PREFIX.rstrip()} so they stay "
        "visible as sample data in every view. Rollback requires per-list "
        "confirmation before every delete. Some families seed deliberately "
        "alarming data so a view "
        f"renders at all -- read {guide} before seeding a site that already "
        "holds real data.",
    )
    return Confirm.ask("Add the demo rows?", default=False, console=console)


def _rewrite_prefix(mapping_path: Path, prefix: str) -> None:
    """Set `prefix:` in the copied mapping, then read it back and verify.

    A targeted line rewrite, not a YAML round-trip. Every shipped mapping
    is heavily commented -- the comments are the documentation for the
    template -- and `yaml.safe_load` followed by `yaml.dump` would discard
    all of them and reorder the file.

    Verified through the real loader rather than by re-reading the text:
    what matters is whether the mapping the build will load carries the
    prefix the user asked for, not whether the line changed.
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
    # `write_artifact`, not `write_text`. The defect AGENTS.md records is
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

    `new` is blank whenever the operator presses Enter at the prefix gate --
    the DEFAULT since the gate reversed -- so `describe()` renders that case
    as `(none)` rather than leaving a bare trailing arrow: "prefix RR_ ->"
    reads as a rendering fault, not as "no prefix". `old` cannot reach
    `describe()` blank: `applies` below requires `old` to be truthy before a
    substitution is even attempted, so an empty `old` is filtered out long
    before there is anything to report. The `(none)` spelling still guards
    that side too, on the chance `applies` is ever loosened.
    """

    label: str
    old: str
    new: str

    @property
    def applies(self) -> bool:
        """A placeholder that is absent or already correct is not a change."""
        return bool(self.old) and self.old != self.new

    def describe(self) -> str:
        return f"{self.label} {self.old or '(none)'} -> {self.new or '(none)'}"


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
            root / MAPPING_RELPATH,
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
    _preserve_env_file(answers)
    return changed, applied


def _is_setting_line(line: str, key: str) -> bool:
    """Whether `line` assigns `key`, under `read_env_file`'s own rules."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return False
    return stripped.partition("=")[0].strip() == key


def _env_text_for_answer(text: str, reader: str | None) -> str:
    """`text` with its reader line set to the answer actually given.

    None means the question was never asked, so the file passes through
    unchanged and the build's own guard still decides. Blank means the
    operator was asked and said nobody, so the line is dropped rather than
    left to enrol somebody on the next build.
    """
    if reader is None:
        return text
    kept = [line for line in text.splitlines() if not _is_setting_line(line, ENTERPRISE_READER_KEY)]
    if reader:
        kept.append(f"{ENTERPRISE_READER_KEY}={_env_value_literal(reader)}")
    return "\n".join(kept) + "\n" if kept else ""


def _env_value_literal(value: str) -> str:
    """`value` written so `read_env_file` reads it back unchanged.

    `validate_enterprise_reader` accepts a leading quote, which the parser
    would read as an opening quote and refuse for never closing. Wrapping in
    the other quote round-trips, because `_unquote` strips one outer pair.
    """
    if value[:1] in ("'", '"'):
        return f'"{value}"' if value[0] == "'" else f"'{value}'"
    return value


def _preserve_env_file(answers: Answers) -> None:
    """Copy the consulted `dbml-sharepoint.env` into the project, with the
    reader line rewritten to the answer given.

    A documented rebuild runs from inside the project, so without a copy it
    drops the reader the first build enrolled. Copying it verbatim is worse:
    an operator who declined the suggestion would get a rebuild that
    permanently enrolled it, and enrolment survives a rollback.

    Never overwrites, so a template shipping its own defaults keeps them.
    """
    if answers.env_file is None:
        return
    source = answers.env_file
    destination = answers.destination / ENV_FILENAME
    if destination.exists() or not source.is_file():
        return
    text = _env_text_for_answer(source.read_text(encoding="utf-8"), answers.reader)
    if not text:
        return
    write_artifact(destination, text)
    _verify_preserved_env_file(destination, answers.reader)


def _verify_preserved_env_file(destination: Path, reader: str | None) -> None:
    """Read the copy back and confirm it says what the operator answered.

    `AGENTS.md` requires anything that writes to read back and verify, and
    an unparseable file here would surface only as a failed rebuild, long
    after the wizard reported success.
    """
    try:
        settings, _digest = read_env_file(destination)
    except EnvFileError as exc:
        raise WizardError(
            f"wrote {destination} but could not read it back: {exc}",
        ) from exc
    if reader is not None and settings.get(ENTERPRISE_READER_KEY, "") != reader:
        raise WizardError(
            f"{destination} reads back as {settings.get(ENTERPRISE_READER_KEY, '')!r}, "
            f"not the {reader!r} that was answered.",
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
    #: Every entity paired with the site role that deploys it, in mapping
    #: declaration order. `roles` above answers "which roles exist"; this
    #: answers "which lists does one role create", which is what the Review
    #: panel has to report to be true.
    entity_roles: tuple[tuple[str, str], ...]
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
        entity_roles=tuple(
            (name, e.site_role) for name, e in bundle.mapping.entities.items()
        ),
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


#: One wider than the longest label. `Reporting`, `Directory` and `Demo rows`
#: are all nine characters, so the column has to be at least ten for a value
#: to be separated from its label by more than the single space `_review_row`
#: adds -- and a new label longer than nine needs this raised.
_REVIEW_LABEL = 10


def _review_row(label: str, value: str) -> str:
    """One label/value line, with the value escaped.

    EVERY value on this panel is operator input or template text: a prefix
    they typed, a directory, a site URL, a UPN, a title from a README. Rich
    reads square brackets as markup, so a prefix of `[bold]` rendered the
    Lists row as a styled `Risk` while the mapping and the deploy script
    carried the literal `[bold]Risk` -- the panel showing one name and the
    build creating another. `_PREFIX_REJECTED` does not refuse brackets and
    should not start to: its comment is explicit that it refuses only what
    breaks a filename or the YAML line, and inventing a SharePoint rule is
    the failure AGENTS.md opens with. Escaping is the fix; rejecting is not.
    """
    return f"[bold]{label:<{_REVIEW_LABEL}}[/bold] {escape(value)}"


def _review_panel(answers: Answers) -> Panel:
    """Every answer, once, before the single confirmation.

    `Lists` is the row that matters. A blank prefix is a valid answer now, so
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
        rows.append(
            _review_row(
                "Lists", ", ".join(choice.list_titles(answers.site_role)),
            ),
        )
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
    # `templates[0]`, because the picker collects exactly one. For several,
    # this has to become one `build` invocation per template -- `_scaffold`
    # and the build loop in `_run` already iterate the whole tuple, so this
    # is the one place that would still print a single command. Left as it
    # is: what the escape hatch should say for N templates is part of
    # multi-template selection, which is out of scope here.
    choice = answers.templates[0]
    inside = _within(_template_root(answers, choice), answers.destination)
    return (
        "\nWhen you are ready:\n\n"
        f"  [bold]cd {escape(str(answers.destination))}[/bold]\n"
        "  [bold]dbml-sharepoint build \\\n"
        # `as_posix()` because this is a command line the operator pastes, and
        # the family standard is one fact -- spelling these paths by hand here
        # let the wizard drift from the layout `Solution` and `_scaffold` use.
        f"    --schema {inside}{SCHEMA_RELPATH.as_posix()} \\\n"
        f"    --mapping {inside}{MAPPING_RELPATH.as_posix()} \\\n"
        f"    --release {inside}{RELEASE_RELPATH.as_posix()} \\\n"
        f"    --site-url {escape(answers.site_url)} \\\n"
        f"    --site-role {answers.site_role} \\\n"
        f"    --out ./{inside}build[/bold]"
    )


def _next_panel(answers: Answers) -> Panel:
    """The procedure, numbered, with paths relative to the project.

    Absolute paths inside the steps wrapped and broke the box, and the
    operator is told where the project is by the panel's own first line, so
    only that one is absolute.

    Rendered as a two-column grid rather than as text with a leading ` 1. `,
    because a wrapped step whose continuation restarts at the left margin
    stops looking like a numbered list at all. The grid hangs the
    continuation under the step text; `pad_edge=False` is what keeps the
    blank line BETWEEN steps from also appearing above the first and below
    the last.

    `deploy.md` is named exactly once either way, and which line carries it
    differs by arm. Seeded, that line is step 3 -- the caution, which has to
    carry the path it points at -- and the footer is dropped, because
    repeating the same path two lines later in a six-line panel is noise.
    Unseeded there is no step 3, so the footer is the only thing pointing at
    the guide and it stays.
    """
    # `templates[0]`, for the same reason as `_rebuild_command` above: one
    # template, so one `inside` and one guide. Several would need a numbered
    # section per template, which is a question for multi-template selection
    # rather than one to answer speculatively here.
    choice = answers.templates[0]
    inside = _within(_template_root(answers, choice), answers.destination)
    guide = f"{inside}30-deploy/deploy.md"
    steps = Table.grid(padding=(1, 1), pad_edge=False)
    steps.add_column(justify="right", no_wrap=True, style="bold")
    steps.add_column(overflow="fold")
    steps.add_row(
        "1.",
        f"Paste [bold]{inside}build/{ASSESS_SCRIPT}[/bold] into the target "
        "site's console. It is read-only, and it is how you find out whether "
        "these list names are already taken.",
    )
    steps.add_row("2.", f"Paste [bold]{inside}build/{DEPLOY_SCRIPT}[/bold].")
    body: list[RenderableType] = [
        f"In [bold]{escape(str(answers.destination))}[/bold]:", "", steps,
    ]
    if answers.seed:
        # The guide is named BEFORE the demo script, not after it: a family
        # may seed data its own procedure tells you not to put on a live
        # site, and an instruction read first is the only one that can
        # prevent that. A seeded bundle carries a THIRD script, and pasting
        # the other two leaves the list empty.
        steps.add_row(
            "3.",
            f"Read [bold]{guide}[/bold] for this template's seeding "
            f"conditions, then paste [bold]{inside}build/{DEMO_SCRIPT}"
            "[/bold] for the demo rows.",
        )
    else:
        body.extend(
            ("", f"[dim]{guide} has the full procedure for this template.[/dim]"),
        )
    return Panel(Group(*body), title="Next", border_style="green")


def _run(console: Console) -> int:
    solutions = available_solutions()
    # A journey is navigation, not a template. A build that shipped without
    # any still offers every template, so this never turns a cosmetic problem
    # into a wizard that refuses to run.
    journeys = available_journeys()
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
    picked = _pick_journey(console, journeys, solutions)
    solution = picked if isinstance(picked, Solution) else _pick_solution(console, picked)
    _describe(console, solution)
    # A template declaring no prefix has one possible answer to this
    # question, and a question with one possible answer is not a question --
    # the same gate `_run` applies to the reporting and demo-rows prompts
    # below. `_describe` above is then the only place the operator learns
    # what their lists will be called before the Review panel names them.
    prefix = _ask_prefix(console, solution) if solution.prefix else ""

    try:
        facts = _read_facts(solution)
        roles = _site_roles([facts])
    except WizardError as exc:
        # Before anything is written. This used to happen after the copy and
        # outside any guard, so a template the loader rejected produced a
        # traceback on top of a project directory that already existed.
        console.print(f"[red]{escape(str(exc))}[/red]")
        return 1

    # Built here, not beside the prefix answer, because it carries the
    # entity/site-role pairs `_read_facts` has just loaded -- that is what
    # lets `list_titles` report the lists this site role actually creates.
    choice = TemplateChoice(solution, prefix, facts.entity_roles)

    console.rule("Site")
    destination = _ask_destination(console, solution)
    site_url = _ask_site_url(console)
    site_role = _ask_site_role(console, roles)

    console.rule("Build")
    build = Confirm.ask(
        "Build the deploy scripts now?", default=True, console=console,
    )
    reader: str | None = None
    env_file = None
    seed = False
    if build:
        # Consulted even where the prompt is not offered, so a mapping with
        # no reader group still reaches the armed guard.
        try:
            consulted = _reader_from_env_file(console)
            env_file = consulted[0] if consulted is not None else None
            # The prompt is offered only where a group exists to enrol into.
            # Blank is its default and means nobody, so it must never reach
            # `validate_enterprise_reader`, which refuses an empty string.
            if facts.reader_group:
                reader = _ask_enterprise_reader(console, consulted)
            if facts.demo_items:
                seed = _ask_seed(console)
        except WizardError as exc:
            # Before anything is written, same as the `_read_facts`/
            # `_site_roles` guard above: `dbml-sharepoint.env` could not be
            # parsed, and `_reader_from_env_file` raised rather than warning
            # and letting the run proceed as though no file were there.
            console.print(f"[red]{escape(str(exc))}[/red]")
            return 1

    answers = Answers(
        destination=destination,
        site_url=site_url,
        site_role=site_role,
        templates=(choice,),
        build=build,
        reader=reader,
        seed=seed,
        env_file=env_file,
    )

    # No `console.rule("Review")`. The other three sections are followed by
    # prompts, which need a break in front of them; this one is followed by a
    # bordered panel TITLED Review, so a rule would put the word on the
    # screen twice, three lines apart, and break nothing that was joined.
    console.print()
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

    console.print(f"\n[green]Wrote[/green] {escape(str(answers.destination))}")
    if repointed:
        # Said plainly, and NOT dimmed: this reports edits the wizard made to
        # the operator's own new files. Naming the substitutions matters
        # because there is more than one -- reporting a file count and a
        # prefix pair when only the site URL moved read as "Repointed 1
        # doc(s) from RR_ to RR_", which is worse than saying nothing.
        # `describe()` also covers the now-default case, pressing Enter at
        # the prefix gate: with `new` blank, "prefix RR_ -> (none)" reads as
        # a decision, not as a rendering fault.
        console.print(
            f"Updated {len(repointed)} documentation files: "
            f"{escape(', '.join(s.describe() for s in applied))}.",
        )

    if not build:
        console.print(_rebuild_command(answers))
        return 0

    # Deferred for a cycle: cli.py imports this module at its top, so this
    # direction stays lazy until `execute_build` leaves the CLI -- #171.
    from dbml_sharepoint.cli import (  # noqa: PLC0415
        ENTERPRISE_READER_DECLINED,
        execute_build,
    )

    for template in answers.templates:
        root = _template_root(answers, template)
        try:
            execute_build(
                schema=root / SCHEMA_RELPATH,
                mapping=root / MAPPING_RELPATH,
                release=root / RELEASE_RELPATH,
                site_url=answers.site_url,
                site_role=answers.site_role,
                out=root / "build",
                seed=answers.seed,
                # None (never asked) leaves the file free to supply a value
                # for the guard to refuse; blank (asked, said nobody)
                # outranks the file. The two must not collapse.
                enterprise_reader=(
                    None
                    if answers.reader is None
                    else answers.reader or ENTERPRISE_READER_DECLINED
                ),
                # Named by the build's own artefacts, so they report the same
                # file the wizard read.
                env_file=answers.env_file,
            )
        except typer.Exit as exc:
            # The build refused and has already said why on stderr. Its exit
            # code is the documented contract; pass it through rather than
            # flattening every refusal to 1.
            return int(exc.exit_code)
        except typer.BadParameter as exc:
            # Reachable since the env file started reaching `execute_build`:
            # its armed guard refuses a reader the mapping has no group for,
            # and `BadParameter` is a `click.UsageError`, not a `typer.Exit`.
            # Unhandled it printed a traceback over an already-scaffolded
            # project. 2 is the documented code for a usage error.
            console.print(f"[red]{escape(exc.message)}[/red]")
            return 2

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
