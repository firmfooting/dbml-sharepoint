"""The interactive template wizard: the default `dbml-sharepoint` command.

Copies one shipped template into a project directory of the user's own,
optionally gives its lists a name prefix, and offers to build it. The prefix
is a yes/no gate -- "Give these lists a name prefix?", defaulting to no --
followed by the value prompt only when the answer is yes; a template
declaring no prefix skips the pair entirely. Pressing Enter at that gate now
produces unprefixed lists, the opposite of the old default. The Review
panel's `Lists` row is what shows the operator the names they are actually
about to create -- it is the safety net for that reversed default, not
decoration, and stays load-bearing for as long as a blank prefix is a valid
answer.

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
    Solution,
    available_solutions,
)
from dbml_sharepoint.model.env_file import (
    ENV_FILENAME,
    ENV_SETTINGS,
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
    reader: str
    seed: bool
    #: The `dbml-sharepoint.env` `_ask_enterprise_reader` consulted, if any --
    #: threaded into `execute_build` so its artefacts report the same file
    #: this prompt read from. None when the question was never asked (no
    #: reader group to enrol into) or no file was there to consult.
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


def _reader_from_env_file(console: Console) -> tuple[Path, str | None] | None:
    """The `dbml-sharepoint.env` file consulted for a suggested UPN, and
    what it suggested: `(path, upn)`, `upn` is None when the file has
    nothing usable to offer. Returns None only when there was no file to
    thread through to the build at all -- never when one was read.

    Read from a file relative to the CURRENT directory -- the same location
    `build` defaults to -- not the destination the wizard is about to write.
    `_ask_destination` refuses a destination that already exists and is
    non-empty, and `_scaffold` only copies the template in afterwards, so a
    scaffolded project cannot contain the file at prompt time; the CWD is
    the one place it could already be.

    The path is returned even when there is no reader suggestion (an absent
    key) or the suggestion is invalid, so the caller can still pass it on to
    `execute_build`: the file WAS read, and every artefact reporting
    provenance must say so, whether or not this particular key mattered.
    `execute_build`'s own precedence rules -- an explicit wizard answer
    always wins over the file -- take it from there.

    A missing file is the ordinary case and stays silent (LBYL, not a caught
    `FileNotFoundError`), and returns None: there is genuinely nothing to
    thread through.

    A file that fails to PARSE is FATAL: this raises `WizardError`, carrying
    `EnvFileError`'s own message, which already names the path, the line and
    the offending text (`_refuse` in `model/env_file.py`). `build` refuses
    the same file the same way, over the same message; a file the operator
    wrote on purpose and got wrong must not be answered with a warning that
    lets the wizard proceed as though no file were there -- that is what
    `_run`'s manifest and index.md would then go on to claim. `_run` catches
    `WizardError` here before anything is written, the same way it already
    does around `_read_facts`.

    An invalid VALUE inside a file that DOES parse is a different failure and
    stays as it was: reported here as one message, treated as no suggestion,
    with the path still threaded through. This is not an inconsistency with
    `build`: `build` only ever validates a file's reader value because that
    value becomes the one `execute_build` uses, when no flag overrides it.
    Here the file's value is never more than a suggestion the operator must
    retype to accept -- `_ask_enterprise_reader` never passes it as
    `default=` -- so an invalid suggestion is simply withdrawn, and whatever
    the operator goes on to answer (blank, or a real UPN) is validated at the
    prompt exactly as if the file had said nothing at all. Making this fatal
    too would refuse a run over a value nothing downstream was ever going to
    use unvalidated.
    """
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import validate_enterprise_reader  # noqa: PLC0415

    path = Path(ENV_FILENAME)
    if not path.is_file():
        return None
    try:
        file_settings, _digest = read_env_file(path)
    except EnvFileError as exc:
        raise WizardError(str(exc)) from exc
    key = next(s.key for s in ENV_SETTINGS if s.parameter == "enterprise_reader")
    reader = file_settings.get(key)
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


def _ask_enterprise_reader(console: Console) -> tuple[str, Path | None]:
    """Prompt until the answer is blank or passes the CLI's own validator.
    Returns the answer alongside the `dbml-sharepoint.env` path this prompt
    consulted, if any -- the caller threads it into `execute_build` so the
    build's own artefacts report the same file this prompt just read from,
    rather than denying one was ever consulted.

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

    The prompt is a bold noun phrase and the guidance sits on a dim line
    ABOVE it, the shape `_ask_seed` uses. It read "Reporting service account
    to enrol read-only (UPN), or blank for none", which is a sentence, a
    definition and an escape hatch in one unbolded line -- the widest prompt
    in the wizard, and the only one whose label did not survive being read at
    a glance.

    A `dbml-sharepoint.env` present but unparseable is not answered here at
    all: `_reader_from_env_file` raises `WizardError` straight through this
    function, and `_run` catches it before anything is written -- see that
    function's own docstring for why the two failures inside the same file
    (cannot parse, versus parses but the value is invalid) are not the same.

    A `dbml-sharepoint.env` suggestion, when `_reader_from_env_file` finds
    one, is named in the PROMPT TEXT and NEVER passed as `default=`. rich's
    `PromptBase.__call__` returns the default before this function's own
    code runs at all, so a non-blank default here would make a blank answer
    resolve to the file's value instead of "enrol nobody" -- unreachable,
    the same way `_ask_prefix`'s docstring records a single-prompt default
    making its own "no prefix" answer unreachable. WRITE THE REASON AT THIS
    LINE if you are tempted to simplify this into a `default=`; it will
    reopen exactly that defect. Accepting the suggestion means typing it;
    Enter always means nobody.
    """
    # Deferred for the same cycle as `validate_site_url` above -- #171.
    from dbml_sharepoint.cli import validate_enterprise_reader  # noqa: PLC0415

    _guidance(
        console,
        "A service account enrolled read-only across every list this "
        "template creates, so it can report on them. Blank for none.",
    )
    consulted = _reader_from_env_file(console)
    env_file = consulted[0] if consulted is not None else None
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
            return "", env_file
        try:
            validate_enterprise_reader(reader)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc.message}[/red]")
            continue
        return reader, env_file


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

    The escape before [DEMO] is rich's documented way to mean a literal
    bracket. MEASURED 2026-08-11: rich prints it identically with or without,
    because DEMO is not a style it knows. Kept anyway -- it is the documented
    spelling and costs one character -- but NOT because an unescaped one was
    seen to break.
    """
    guide = "30-deploy/deploy.md"
    _guidance(
        console,
        r"Demo rows are titled \[DEMO] and rollback treats a list of them as "
        "demo-only. Some families seed deliberately alarming data so a view "
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
    reader = ""
    env_file = None
    seed = False
    if build:
        # Offered only where the mapping declares a group
        # `--enterprise-reader` could enrol into. Blank stays the default and
        # must map to `ENTERPRISE_READER_DECLINED` below, never "": an empty
        # string would reach `validate_enterprise_reader` and abort a run
        # where the operator simply pressed Enter, which is the safe answer
        # the question exists to allow. Anything NON-blank is validated at
        # the prompt and re-asked on refusal -- the `except typer.Exit` below
        # cannot catch what `validate_enterprise_reader` raises, because
        # `typer.BadParameter` is a `click.UsageError`.
        try:
            if facts.reader_group:
                reader, env_file = _ask_enterprise_reader(console)
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
                # `None`, plain, would mean "no flag and no wizard answer" --
                # unset, the state a future `dbml-sharepoint.env` may fill.
                # `answers.reader` blank means the operator was asked and
                # said nobody, which must stay distinguishable from that.
                enterprise_reader=answers.reader or ENTERPRISE_READER_DECLINED,
                # The file `_ask_enterprise_reader` already consulted, so the
                # build's own artefacts (manifest, index.md, transcript) name
                # it too -- an explicit `answers.reader` always outranks it
                # inside `execute_build`, so threading it through here never
                # changes which UPN gets enrolled, only what gets reported.
                env_file=answers.env_file,
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
