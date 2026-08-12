"""The interactive wizard.

Driven through a Console whose `input` is scripted, which is how rich's
`Prompt`/`Confirm` read: both call `console.input`. Patching that rather
than `Prompt.ask` keeps the real prompt objects -- including their default
handling and their validation of a `choices=` answer -- under test.
"""

import hashlib
import io
import shutil
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console

from dbml_sharepoint import wizard
from dbml_sharepoint.catalogue import (
    PLACEHOLDER_SITE_URL,
    Solution,
    available_solutions,
    load_solution,
)
from dbml_sharepoint.model.mapping_loader import load_mapping


class ScriptedConsole(Console):
    """A console that answers prompts from a fixed list.

    Renders to a StringIO so a test can assert on what the user was shown,
    and raises `EOFError` when the script runs out -- which is what a real
    terminal does on Ctrl-D, and which the wizard already handles. A test
    that under-scripts therefore fails as an assertion about the wizard's
    exit code rather than hanging.
    """

    def __init__(self, answers: Sequence[str], width: int = 100) -> None:
        super().__init__(file=io.StringIO(), width=width, force_terminal=False)
        self._answers = list(answers)

    def input(self, prompt: object = "", **kwargs: object) -> str:
        if prompt:
            self.print(prompt, end="")
        if not self._answers:
            raise EOFError
        return self._answers.pop(0)

    @property
    def text(self) -> str:
        assert isinstance(self.file, io.StringIO)
        return self.file.getvalue()


def _answers(
    destination: Path, *, build: str = "n", seed: str | None = None,
    reader: str | None = "", confirm: str = "y", **over: str,
) -> list[str]:
    """The happy-path script, in the order the wizard now asks.

    Everything is asked BEFORE the single confirmation, which is the point of
    the sequence: the operator reviews the whole decision once instead of
    confirming a write and then being asked three more questions.

    The order is: template, prefix, directory, site URL, [site role], build?,
    [reporting], [demo rows], confirm. The prefix sits with the template
    because it is a property of the template; the directory, site URL and
    site role describe the site.

    **A spare answer is no longer invisible, and that is why `seed` and
    `reader` both take `None`.** While the confirmation was the fifth answer,
    an unread answer sat at the END of the list and did nothing. It is now
    the LAST answer, so a spare one in the middle is read by the confirmation
    instead -- blank confirms by default, and the scripted `confirm` value is
    then never consumed at all. A test whose template declares no
    `enroll_enterprise_reader` group but which still passes `reader=""`
    therefore runs to completion whether or not the wizard asked, which is
    exactly the shape of test that proves nothing. Pass `reader=None` (as
    `seed` already defaults) so the script carries no answer the wizard
    should not ask for: a wizard that asks then reads the CONFIRMATION's
    answer as a UPN, is refused, re-asks, runs out and exits 130.

    The site role is absent because every shipped family declares exactly one
    role, so the question is not put -- a family with two needs it inserted
    by hand.
    """
    script = {
        "template": "risk-register",
        "prefix": "RR_",
        "destination": str(destination),
        "site_url": "https://contoso.sharepoint.com/sites/x",
    }
    script.update(over)
    tail = [build]
    if build == "y":
        if reader is not None:
            tail.append(reader)
        if seed is not None:
            tail.append(seed)
    return [*script.values(), *tail, confirm]


def _collapsed(console: ScriptedConsole) -> str:
    """What the user was shown, on one line.

    Rich wraps at the console width, so a substring assertion against the
    raw text is a false negative waiting to happen -- a message can be
    correct and still fail the check because it broke over two lines.
    """
    return " ".join(console.text.split())


#: The smallest mapping `load_mapping` accepts, which is what the wizard
#: reads back after rewriting the prefix and again to find the site roles.
_ONE_ENTITY = (
    'prefix: "OLD_"\n'
    "entities:\n"
    "  Risk: { kind: List, base_template: 100, site_role: default }\n"
)


def _fake_family(root: Path, mapping: str = _ONE_ENTITY) -> Solution:
    """A minimal stand-in for a shipped family, and the `Solution` for it.

    Used where the point of the test is a shape no shipped template has --
    a mapping declaring two site roles, one with no `prefix:` line at all.
    Inventing the template is honest there; doctoring a real one would
    mostly test the doctoring, and pinning a behaviour to a shipped family
    that happens to have the shape today breaks when it stops having it.
    """
    (root / "10-design").mkdir(parents=True, exist_ok=True)
    (root / "20-configure").mkdir(parents=True, exist_ok=True)
    (root / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
    # newline="\n" because this stands in for a *shipped* family, and every
    # shipped file is LF under `.gitattributes`. Text mode would hand the
    # wizard CRLF on Windows and LF everywhere else, so the stand-in would
    # stop resembling the thing it stands in for on one platform only.
    (root / "20-configure" / "mapping.yaml").write_text(
        mapping, encoding="utf-8", newline="\n",
    )
    (root / "20-configure" / "release.yaml").write_text("", encoding="utf-8")
    return Solution(
        id="fake-template",
        title="Fake",
        summary="s",
        detail="s",
        lists=("Risk",),
        prefix="OLD_",
        root=root,
    )


def _choice(prefix: str = "RR_", *, lists: tuple[str, ...] = ("Risk",),
            id_: str = "risk-register") -> wizard.TemplateChoice:
    """A `TemplateChoice` with no files behind it.

    These four functions are pure -- they read `Solution` fields and nothing
    from disk -- so a scaffolded family would only slow the test down.
    """
    return wizard.TemplateChoice(
        solution=Solution(
            id=id_, title="T", summary="s", detail="s",
            lists=lists, prefix=prefix, root=Path("unused"),
        ),
        prefix=prefix,
    )


def _answers_for(*choices: wizard.TemplateChoice, destination: Path) -> wizard.Answers:
    """An `Answers` for the pure-function tests.

    The build fields are filled with the "copy the files only" answers
    because none of these tests is about the build: `_template_root` and
    `_within` read the destination and the templates and nothing else.
    """
    return wizard.Answers(
        destination=destination,
        site_url="https://contoso.sharepoint.com/sites/x",
        site_role="default",
        templates=choices,
        build=False,
        reader="",
        seed=False,
    )


def test_list_titles_are_the_prefix_concatenated() -> None:
    """What jsgen.py:380 and four other generators actually do."""
    assert _choice("ACME_", lists=("Risk", "Control")).list_titles() == (
        "ACME_Risk", "ACME_Control",
    )


def test_a_blank_prefix_names_the_lists_as_declared() -> None:
    """MEASURED 2026-08-12: `prefix: ""` builds and emits `"Risk"`."""
    assert _choice("").list_titles() == ("Risk",)


def test_one_template_lands_directly_in_the_destination(tmp_path: Path) -> None:
    """Every documented path and printed command depends on this.

    Nesting a single template under its own id would move
    `10-design/schema.dbml` for no gain and break the deploy.md the wizard
    sends the operator to.
    """
    choice = _choice()
    answers = _answers_for(choice, destination=tmp_path)
    assert wizard._template_root(answers, choice) == tmp_path
    assert wizard._within(wizard._template_root(answers, choice), tmp_path) == ""


def test_several_templates_nest_by_id(tmp_path: Path) -> None:
    """Two templates cannot share one root.

    The picker collects one today, so this is the only place the branch is
    exercised. It is a pure function; testing it directly is honest.
    """
    first, second = _choice(id_="risk-register"), _choice(id_="audit-actions")
    answers = _answers_for(first, second, destination=tmp_path)
    assert wizard._template_root(answers, first) == tmp_path / "risk-register"
    assert wizard._template_root(answers, second) == tmp_path / "audit-actions"
    assert wizard._within(
        wizard._template_root(answers, second), tmp_path,
    ) == "audit-actions/"


def _offer_only(monkeypatch: pytest.MonkeyPatch, solution: Solution) -> None:
    monkeypatch.setattr(wizard, "available_solutions", lambda: [solution])


def _capture_build(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Record what the wizard hands `execute_build`, and build nothing.

    The real build is exercised by `test_building_now_produces_a_pasteable_
    bundle`; these tests are about the arguments the wizard assembles, which
    a successful build cannot distinguish -- `build` accepts a site role it
    was never asked about just as happily as the right one.
    """
    from dbml_sharepoint import cli

    captured: dict[str, object] = {}

    def record(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(cli, "execute_build", record)
    return captured


def _tree_digest(root: Path) -> dict[str, str]:
    """Content hashes for a tree, ignoring what the wizard refuses to copy.

    `build/` and `reports/` are gitignored, so they exist only in a
    contributor's checkout -- and a test that hashed them would fail for
    whoever had built the template by hand rather than for a real change.
    """
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes(),
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not set(path.relative_to(root).parts) & set(wizard._NEVER_COPY)
    }


def test_scaffolds_the_whole_family(tmp_path: Path) -> None:
    """Not just the three build inputs.

    deploy.md, staff-guide.md and governance.md are the reason the
    templates are worth shipping; a scaffold that dropped them would leave
    the user with a mapping and no explanation of it.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination))

    assert wizard.run_wizard(console) == 0

    assert (destination / "10-design" / "schema.dbml").is_file()
    assert (destination / "20-configure" / "mapping.yaml").is_file()
    assert (destination / "20-configure" / "release.yaml").is_file()
    assert (destination / "30-deploy" / "deploy.md").is_file()
    assert (destination / "README.md").is_file()


def test_the_copy_is_buildable_by_the_real_loader(tmp_path: Path) -> None:
    destination = tmp_path / "proj"
    assert wizard.run_wizard(ScriptedConsole(_answers(destination))) == 0

    bundle = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert bundle.mapping.entities


def test_prefix_substitution_reaches_the_loaded_mapping(tmp_path: Path) -> None:
    """The assertion is on what `load_mapping` returns, not on the text.

    A rewrite that edited a commented-out `prefix:` line, or one inside a
    nested block, would change the file and leave the build using the
    template's original prefix.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, prefix="ACME_"))

    assert wizard.run_wizard(console) == 0

    bundle = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert bundle.mapping.prefix == "ACME_"


def test_substitution_keeps_the_mapping_comments(tmp_path: Path) -> None:
    """A YAML round-trip would have silently deleted them.

    Every shipped mapping is commented, and those comments are the
    documentation for the template -- `risk-register` opens by saying the
    matrix lives in that file.
    """
    destination = tmp_path / "proj"
    assert wizard.run_wizard(ScriptedConsole(_answers(destination))) == 0

    original = load_solution("risk-register").mapping_path.read_text(encoding="utf-8")
    written = (destination / "20-configure" / "mapping.yaml").read_text(
        encoding="utf-8",
    )
    expected = original.count("#")
    assert written.count("#") == expected
    assert written.count("\n") == original.count("\n")


def test_a_previous_build_is_not_copied_into_the_new_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build/` is gitignored, so it exists only in a contributor's
    checkout -- which is exactly where the wizard gets run while being
    developed. A stale deploy.js in a brand-new project is worse than none,
    because it looks like output the wizard produced."""
    source = tmp_path / "fake-template"
    (source / "10-design").mkdir(parents=True)
    (source / "20-configure").mkdir(parents=True)
    (source / "build").mkdir()
    (source / "build" / "deploy.js").write_text("STALE", encoding="utf-8")
    (source / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
    (source / "20-configure" / "mapping.yaml").write_text(
        'prefix: "OLD_"\nentities:\n  Risk: { kind: List, base_template: 100, '
        "site_role: default }\n",
        encoding="utf-8",
    )
    (source / "20-configure" / "release.yaml").write_text("", encoding="utf-8")

    solution = load_solution("risk-register")
    monkeypatch.setattr(
        wizard, "available_solutions", lambda: [
            type(solution)(
                id="fake-template", title="Fake", summary="s", detail="s",
                lists=("Risk",), prefix="OLD_", root=source,
            ),
        ],
    )

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", prefix="NEW_"),
    )
    assert wizard.run_wizard(console) == 0
    assert not (destination / "build").exists()


def test_refuses_a_non_empty_destination_and_reprompts(tmp_path: Path) -> None:
    """Merging a whole tree into somebody's existing project would scatter
    template files through it with no record of which were added."""
    occupied = tmp_path / "taken"
    occupied.mkdir()
    (occupied / "mine.txt").write_text("keep me", encoding="utf-8")
    destination = tmp_path / "proj"

    console = ScriptedConsole([
        "risk-register",
        "RR_",
        str(occupied),      # refused
        str(destination),   # accepted
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert (occupied / "mine.txt").read_text(encoding="utf-8") == "keep me"
    assert list(occupied.iterdir()) == [occupied / "mine.txt"]
    assert (destination / "README.md").is_file()


def test_an_existing_empty_directory_is_accepted_and_scaffolded(
    tmp_path: Path,
) -> None:
    """`_ask_destination` deliberately accepts an existing EMPTY directory.

    `copytree` without `dirs_exist_ok` then raised FileExistsError, so the
    wizard reported "Could not scaffold the project" for a path it had just
    told the user was fine -- and `mkdir foo && cd ..` before running is an
    entirely ordinary thing to have done.
    """
    destination = tmp_path / "proj"
    destination.mkdir()

    assert wizard.run_wizard(ScriptedConsole(_answers(destination))) == 0
    assert (destination / "README.md").is_file()
    assert (destination / "20-configure" / "mapping.yaml").is_file()


def test_changing_the_prefix_repoints_the_copied_documentation(
    tmp_path: Path,
) -> None:
    """The docs name the lists literally, and the wizard sends people to them.

    Choosing ACME_ builds ACME_Risk while deploy.md still said to verify
    that `RR_Risk` exists -- documentation that disagrees with what was
    built, which is the failure this project exists to avoid.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, prefix="ACME_"))

    assert wizard.run_wizard(console) == 0

    stale = [
        str(p.relative_to(destination))
        for p in sorted(destination.rglob("*.md"))
        if "RR_" in p.read_text(encoding="utf-8")
    ]
    assert not stale, f"docs still name the template's prefix: {stale}"
    deploy_md = (destination / "30-deploy" / "deploy.md").read_text(encoding="utf-8")
    assert "ACME_Risk" in deploy_md
    # And it says so rather than editing the user's docs silently.
    assert "Updated" in console.text


def test_the_chosen_site_url_reaches_the_copied_documentation(
    tmp_path: Path,
) -> None:
    """The rebuild command in the copied docs must name the chosen site.

    The same failure `_retitle_docs` exists to prevent, one answer further
    down the same wizard. The operator answers with their site, and the
    project they are handed says to rebuild against
    `https://yourtenant.sharepoint.com/sites/your-site` -- the one
    instruction in that folder guaranteed not to work, and the one they
    return to on every schema change.
    """
    destination = tmp_path / "proj"
    site_url = "https://contoso.sharepoint.com/sites/ops"
    console = ScriptedConsole(_answers(destination, site_url=site_url))

    assert wizard.run_wizard(console) == 0

    stale = [
        str(p.relative_to(destination))
        for p in sorted(destination.rglob("*.md"))
        if PLACEHOLDER_SITE_URL in p.read_text(encoding="utf-8")
    ]
    assert not stale, f"docs still name the placeholder site: {stale}"
    deploy_md = (destination / "30-deploy" / "deploy.md").read_text(encoding="utf-8")
    assert f"--site-url {site_url}" in deploy_md


def test_each_template_repoints_only_its_own_documentation(
    tmp_path: Path,
) -> None:
    """Prefix substitution is per-template, so its blast radius must be too.

    Only reachable by calling `_scaffold` directly -- the picker collects one
    template. Written now because the moment it collects two, a repoint
    scoped to the whole destination would rewrite the other template's
    deploy.md with this template's prefix, silently.

    An earlier version of this test picked arbitrary prefixes (`ACME_`,
    `ZZ_`) and asserted they never leaked into the other template's docs.
    That proved nothing: with `_repoint_docs` reverted to scan
    `answers.destination` (the bug this test exists to catch), the test
    still passed, because each iteration's substitution list only ever
    contains that template's OWN old/new strings -- `ACME_` and `RR_` never
    appear in audit-actions' substitution list at all, so scanning a wider
    tree for them finds nothing there either way.

    The fix is to make one template's substitution *become* the next
    template's target text, so a wrongly-scoped scan has something to find.
    Order matters, which is why risk-register goes first:

    * risk-register ships prefix `RR_`; it is repointed to `AU_` -- the
      prefix audit-actions ships as. After this step, risk's docs say
      `AU_Risk` (correct: risk's OWN new prefix) which is also, not
      coincidentally, the OLD value audit-actions is about to be repointed
      away from.
    * audit-actions ships `AU_` and is repointed to `ZZ_`. Correctly scoped,
      this only touches audit's own tree, so risk's `AU_Risk` is untouched.
      Scoped to the whole destination, `AU_` also matches the `AU_Risk` this
      step just produced, silently rewriting risk's docs to `ZZ_Risk`.

    So after `_scaffold`, risk-register's docs must say `AU_Risk` and must
    never say `ZZ_Risk`. If a future edit "simplifies" these three prefixes
    back to something arbitrary, this collision -- and the guard -- disappear
    without a failure to announce it.
    """
    destination = tmp_path / "site"
    risk = wizard.TemplateChoice(load_solution("risk-register"), "AU_")
    audit = wizard.TemplateChoice(load_solution("audit-actions"), "ZZ_")
    answers = wizard.Answers(
        destination=destination,
        site_url="https://contoso.sharepoint.com/sites/x",
        site_role="default",
        templates=(risk, audit),
        build=False,
        reader="",
        seed=False,
    )

    changed, _ = wizard._scaffold(answers)

    risk_docs = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (destination / "risk-register").rglob("*.md")
    )
    assert "AU_Risk" in risk_docs
    assert "ZZ_Risk" not in risk_docs
    # A wrongly-scoped scan also revisits files it already rewrote in an
    # earlier iteration, so the same path is reported changed twice. Correct
    # scoping never lets two templates' roots overlap, so no path repeats.
    assert len(changed) == len(set(changed))


def test_a_cross_site_link_in_the_docs_is_not_repointed(tmp_path: Path) -> None:
    """Only the deploy target is substituted, not every SharePoint URL.

    credentialing-register's deploy.md carries a formatting-JSON example
    whose `href` points at a by-laws page on a *governance* site -- a
    deliberately different site from the one being deployed to. A fuzzy
    "rewrite anything that looks like a SharePoint URL" would silently
    repoint it at the deploy target, inventing a link to a page that does
    not exist there.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(
            destination,
            template="credentialing-register",
            prefix="CR_",
            site_url="https://contoso.sharepoint.com/sites/ops",
        ),
    )

    assert wizard.run_wizard(console) == 0

    deploy_md = (destination / "30-deploy" / "deploy.md").read_text(encoding="utf-8")
    assert "sites/governance/credentialing-by-laws.aspx" in deploy_md


def test_keeping_the_default_prefix_reports_no_prefix_change(
    tmp_path: Path,
) -> None:
    """The wizard must not report an edit it did not make.

    This used to assert nothing was reported at all, because the prefix was
    the only substitution and keeping it made the whole step a no-op. The
    site URL is always answered, so documentation IS now repointed in this
    case -- and the report has to name the site URL and stay silent about
    the prefix, rather than counting files and claiming a prefix pair. The
    version of this that read "Repointed 1 doc(s) from RR_ to RR_" is
    exactly the wrong answer.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, prefix="RR_"))

    assert wizard.run_wizard(console) == 0
    # Collapsed because rich wraps the report line at the console width, so a
    # substring assertion against the raw text is a false negative waiting to
    # happen.
    #
    # Bounded at BOTH ends, to the report line itself. This read
    # `"prefix RR_" not in reported` against the whole transcript, which
    # worked only while nothing else on screen named the prefix -- `_describe`
    # now shows the template's declared prefix four questions earlier, so the
    # unbounded form fails on a correct run. The bound is what the assertion
    # always meant: the REPORT must not claim a prefix substitution it did
    # not make.
    reported = " ".join(console.text.split())
    report = reported.split("documentation files: ", 1)[1].split(
        "When you are ready", 1,
    )[0]
    assert "site URL" in report
    assert "prefix" not in report


def test_a_long_prefix_is_accepted(tmp_path: Path) -> None:
    """The wizard must not invent a SharePoint rule.

    The old guard was `^[A-Za-z0-9_-]{1,16}$`, whose character set and
    16-character ceiling appear in no Learn page, no probe and no validator
    rule. It rejected prefixes `build` accepts and looped forever with no
    way forward. The authority is the validator, which runs on the build.
    """
    destination = tmp_path / "proj"
    long_prefix = "CONTOSO_GOVERNANCE_RISK_"
    console = ScriptedConsole(_answers(destination, prefix=long_prefix))

    assert wizard.run_wizard(console) == 0
    bundle = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert bundle.mapping.prefix == long_prefix


def test_declining_the_write_leaves_nothing_behind(tmp_path: Path) -> None:
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, confirm="n"))

    assert wizard.run_wizard(console) == 0
    assert not destination.exists()


def test_a_bad_site_url_is_refused_by_the_cli_rule(tmp_path: Path) -> None:
    """The wizard must not develop its own opinion about a site URL.

    `http://` is rejected by `validate_site_url`, which `--site-url` uses;
    the wizard re-prompts rather than restating the rule.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "risk-register",
        "RR_",
        str(destination),
        "http://insecure.example.com/sites/x",       # refused
        "https://contoso.sharepoint.com/sites/x",    # accepted
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert "https" in console.text


def test_a_pasted_site_url_keeps_its_query_out_of_the_copied_docs(
    tmp_path: Path,
) -> None:
    """SharePoint's Copy link puts `?web=1` on the clipboard.

    `_ask_site_url` cleans the answer and returns the cleaned value; this
    pins that the wizard USES the return rather than the raw response. A
    build would survive the difference -- `execute_build` cleans again --
    but `_repoint_docs` bakes this value into every scaffolded deploy.md's
    rebuild command, and the operator comes back to that command on every
    schema change. Documentation disagreeing with what was built is the
    failure `_repoint_docs`' own docstring exists to prevent.

    MEASURED: reverting `_ask_site_url` to return the raw answer left all
    2200 tests green, and `wizard.py` carried its only uncovered line.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "risk-register",
        str(destination),
        "RR_",
        "https://contoso.sharepoint.com/sites/x?web=1",
        "y",   # write
        "n",   # do not build
    ])

    assert wizard.run_wizard(console) == 0

    docs = "\n".join(
        p.read_text(encoding="utf-8") for p in destination.rglob("*.md")
    )
    assert "?web=1" not in docs, "the query reached the copied documentation"
    assert "https://contoso.sharepoint.com/sites/x" in docs
    # And the operator was told, rather than silently handed a different URL.
    shown = " ".join(console.text.split())
    assert "Ignoring the query or fragment" in shown, shown


def test_a_bad_prefix_is_refused_and_reprompted(tmp_path: Path) -> None:
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "risk-register",
        "has a space",   # refused
        "RR_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    bundle = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert bundle.mapping.prefix == "RR_"


def test_a_template_can_be_picked_by_number(tmp_path: Path) -> None:
    """The number is a property of one render and changes when a template
    is added, so the name has to keep working -- but the number is what a
    user reaches for first."""
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, template="1"))

    assert wizard.run_wizard(console) == 0
    assert (destination / "README.md").is_file()


def test_an_unknown_template_reprompts_rather_than_exiting(tmp_path: Path) -> None:
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "no-such-template",
        "risk-register",
        "RR_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert "No template" in console.text


def test_a_blank_template_answer_reprompts_rather_than_picking_the_first(
    tmp_path: Path,
) -> None:
    """Enter is not an answer to the template question.

    It used to default to `solutions[0].id` -- whatever sorts first, which
    is `asset-register` -- so pressing Enter through the wizard scaffolded a
    family nobody chose. Blank is not a mistake worth an error message, so
    the prompt simply repeats; the assertion is therefore that the run ends
    on the template the SECOND answer names, not on the alphabetical first.

    The script would be one answer shorter for a wizard that took the
    default, so the regression shows up as a leftover answer and a
    `risk-register` project rather than as EOF.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "",   # Enter -- must not be taken as an answer at all
        "audit-actions",
        "AU_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    # The identity of what was written, not just what was printed: the
    # catalogue table names every template, so a console assertion alone
    # would hold whichever family the blank answer scaffolded.
    copied = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert tuple(copied.mapping.entities) == load_solution("audit-actions").lists


def test_running_out_of_input_exits_without_a_traceback(tmp_path: Path) -> None:
    """Piped input that ends mid-prompt is not a crash and not a success."""
    assert wizard.run_wizard(ScriptedConsole([])) == 130


def test_building_now_produces_a_pasteable_bundle(tmp_path: Path) -> None:
    """The headline path: template to deploy.js in one command.

    Runs the real `execute_build`, not a stub. The wizard's whole claim is
    that it is a front end onto the documented build rather than a second
    builder, and only actually building proves the arguments it assembles
    are ones that build accepts.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="y", seed="n"))

    assert wizard.run_wizard(console) == 0

    build_dir = destination / "build"
    assert (build_dir / "deploy.js.txt").is_file()
    assert (build_dir / "assess.js.txt").is_file()
    assert (build_dir / "deploy-manifest.md").is_file()


def test_the_built_bundle_carries_the_chosen_prefix(tmp_path: Path) -> None:
    """The prefix has to survive all the way into the emitted JS.

    Asserting it on the loaded mapping proves the substitution landed;
    asserting it here proves nothing downstream re-derived the list names
    from the template's original prefix.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, prefix="ACME_", build="y", seed="n"))

    assert wizard.run_wizard(console) == 0

    deploy_js = (destination / "build" / "deploy.js.txt").read_text(encoding="utf-8")
    assert "ACME_" in deploy_js
    assert "RR_" not in deploy_js


def test_a_refused_build_passes_its_exit_code_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exit codes are the documented contract -- 2 for misuse, 1 for a
    refused build. Flattening every refusal to 1 would make a CI gate
    keying on the table mis-classify it."""
    import typer

    from dbml_sharepoint import cli

    def refuse(**_: object) -> None:
        raise typer.Exit(code=2)

    monkeypatch.setattr(cli, "execute_build", refuse)

    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="y", seed="n"))
    assert wizard.run_wizard(console) == 2


def test_no_shipped_templates_is_reported_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wizard, "available_solutions", list)
    console = ScriptedConsole([])
    assert wizard.run_wizard(console) == 1
    assert "shipped without them" in console.text


def test_cancelling_exits_130_without_a_traceback() -> None:
    """Ctrl-C is a normal way to leave a wizard, not a crash."""

    class Interrupting(ScriptedConsole):
        def input(self, prompt: object = "", **kwargs: object) -> str:
            raise KeyboardInterrupt

    console = Interrupting([])
    assert wizard.run_wizard(console) == 130
    assert "Cancelled" in console.text


def test_a_mapping_with_no_prefix_line_is_refused(tmp_path: Path) -> None:
    """Fails closed with a named error rather than writing a project whose
    prefix silently stayed the template's."""
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text("entities: {}\n", encoding="utf-8")

    with pytest.raises(wizard.WizardError, match="no top-level `prefix:` line"):
        wizard._rewrite_prefix(mapping, "NEW_")


def test_the_declined_build_prints_a_runnable_command(tmp_path: Path) -> None:
    """The paths it prints are relative to the project directory, which is
    the form the copied deploy.md also uses."""
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="n"))

    assert wizard.run_wizard(console) == 0
    assert "10-design/schema.dbml" in console.text
    assert "20-configure/mapping.yaml" in console.text


def test_every_scaffolded_file_is_written_with_lf(tmp_path: Path) -> None:
    """The wizard hands over a project; it must not depend on the machine.

    `.gitattributes` declares the whole repository LF and the templates ship
    that way, but `Path.write_text` inherits the platform newline -- so on
    Windows both rewrites emitted CRLF. Measured before the fix: the copied
    `mapping.yaml` and `30-deploy/deploy.md` came out CRLF while every file
    `copytree` left alone stayed LF, which is the worst version of it -- one
    project, two conventions, decided by which machine ran the wizard.

    Asserted over the whole tree rather than the two known files: the point
    is that no writer added later reintroduces it.
    """
    destination = tmp_path / "proj"
    assert wizard.run_wizard(ScriptedConsole(_answers(destination))) == 0

    crlf = [
        str(path.relative_to(destination))
        for path in sorted(destination.rglob("*"))
        if path.is_file() and b"\r\n" in path.read_bytes()
    ]
    assert not crlf, f"scaffolded with CRLF: {crlf}"


def test_a_destination_that_is_an_existing_file_is_refused_and_reprompted(
    tmp_path: Path,
) -> None:
    """A path that exists and is not a directory needs its own answer.

    It cannot fall through to the emptiness check -- `iterdir` on a file
    raises `NotADirectoryError`, so the wizard would traceback out of a
    prompt on nothing worse than a mistyped path, and one character is all
    it takes to name a file next to the directory you meant.
    """
    occupied = tmp_path / "notes.txt"
    occupied.write_text("keep me", encoding="utf-8")
    destination = tmp_path / "proj"

    console = ScriptedConsole([
        "risk-register",
        "RR_",
        str(occupied),      # refused
        str(destination),   # accepted
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert occupied.read_text(encoding="utf-8") == "keep me"
    assert "exists and is not a directory" in _collapsed(console)
    assert (destination / "README.md").is_file()


def test_a_blank_prefix_is_accepted_and_reaches_the_mapping(
    tmp_path: Path,
) -> None:
    """Blank means "no prefix", exactly as it means "enrol nobody" above.

    MEASURED 2026-08-12: `prefix: ""` builds and emits `"Risk"` as the list
    title throughout deploy.js.txt, and no validator rule requires one. The
    wizard was the only thing refusing it.

    The scripted answer is `" "`, not `""`. risk-register declares `RR_`, so
    `_ask_prefix`'s `Prompt.ask(default=solution.prefix, ...)` carries a
    NON-blank default -- and MEASURED against this checkout's rich: a truly
    empty raw answer never reaches `_ask_prefix`'s own code at all, because
    `PromptBase.__call__` returns `default` outright whenever the raw input
    is exactly `""`, before `process_response` or our own `.strip()` ever
    runs. A single space is not literally empty, so rich passes it through
    unaltered and `_ask_prefix`'s `.strip()` reduces it to blank exactly as
    a deliberately cleared field would.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(_answers(destination, prefix=" ", build="n"))
    assert wizard.run_wizard(console) == 0

    mapping = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert mapping.mapping.prefix == ""


def test_a_blank_prefix_repoints_the_docs_to_the_bare_list_name(
    tmp_path: Path,
) -> None:
    """`RR_Risk` in deploy.md becomes `Risk`, not `_Risk` or `RR_Risk`.

    `" "`, not `""` -- see `test_a_blank_prefix_is_accepted_and_reaches_the_
    mapping` for why a literal empty answer cannot reach blank against
    risk-register's non-blank declared prefix.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(_answers(destination, prefix=" ", build="n"))
    assert wizard.run_wizard(console) == 0

    docs = "\n".join(
        p.read_text(encoding="utf-8") for p in destination.rglob("*.md")
    )
    assert "RR_Risk" not in docs
    assert "Risk" in docs


def test_a_template_declaring_no_prefix_is_not_asked_for_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question with one possible answer is not a question.

    Same gate as the reporting and demo questions. The script here carries no
    prefix answer at all, so if the wizard asks, the destination answer is
    consumed by the prefix prompt and the run fails.
    """
    family = tmp_path / "family"
    solution = _fake_family(
        family,
        mapping='prefix: ""\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
    )
    _offer_only(monkeypatch, replace(solution, prefix=""))

    destination = tmp_path / "out"
    # Final order minus the prefix answer: template, directory, site URL,
    # build?, confirm. If the wizard asks for a prefix anyway, the directory
    # answer is swallowed by that prompt and everything after it shifts, so
    # this fails loudly rather than quietly proving nothing.
    console = ScriptedConsole(
        [solution.id, str(destination),
         "https://contoso.sharepoint.com/sites/x", "n", "y"],
    )
    assert wizard.run_wizard(console) == 0
    assert destination.is_dir()
    # The PROMPT, not the word. `_describe` legitimately mentions the
    # template's declared prefix, and asserting on a bare substring would
    # make this pass or fail on unrelated wording.
    assert "List name prefix" not in _collapsed(console)


def test_a_whitespace_only_prefix_means_no_prefix(tmp_path: Path) -> None:
    """A DELIBERATE behaviour change, replacing the old refusal.

    `_ask_prefix` has always `.strip()`ed the answer, so `"   "` reached the
    emptiness check as `""` and was refused along with a genuinely empty
    answer. Now that blank is a real answer meaning "no prefix", an
    all-whitespace answer is an empty one and means the same thing -- the
    operator cannot see the difference on screen, so the wizard should not
    invent one.

    This REPLACES `test_a_whitespace_only_prefix_is_refused_and_reprompted`,
    which pinned the old refusal -- verified against this checkout on
    2026-08-12 that the old test still existed before it was deleted here;
    the two cannot both hold.

    A prefix with whitespace INSIDE it -- `"AC ME_"` -- is still refused by
    `_PREFIX_REJECTED`, which is what
    `test_a_bad_prefix_is_refused_and_reprompted` and
    `test_a_prefix_with_an_interior_space_is_refused` below cover.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(_answers(destination, prefix="   ", build="n"))
    assert wizard.run_wizard(console) == 0

    mapping = load_mapping(destination / "20-configure" / "mapping.yaml")
    assert mapping.mapping.prefix == ""


def test_a_prefix_with_an_interior_space_is_refused(tmp_path: Path) -> None:
    """`AC ME_` would name a list `AC ME_Risk`. Still a typo, still refused.

    `test_a_bad_prefix_is_refused_and_reprompted` already scripts a refused
    answer containing interior spaces (`"has a space"`), so this is
    deliberately redundant with it: dropping the whitespace-only refusal
    above must not quietly drop the interior-whitespace one too, and a
    second test naming that case explicitly is cheaper than trusting the
    other test's string to keep meaning what it means.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        ["risk-register", "AC ME_", "RR_", str(destination),
         "https://contoso.sharepoint.com/sites/x", "n", "y"],
    )
    assert wizard.run_wizard(console) == 0
    assert "cannot contain whitespace" in _collapsed(console)


def test_guidance_indents_every_wrapped_line() -> None:
    """`_guidance`'s hanging indent is pinned here, not by any caller.

    Every other assertion in this file reads through `_collapsed`, which
    normalises whitespace -- so a `_guidance` that reverted to a literal
    `f"  {text}"` indent (correct on the first line only, per the function's
    own MEASURED docstring note) would be invisible to the rest of the
    suite: the words would still all be there, just wrapped wrong. This
    renders directly at a width narrow enough to force a wrap and reads the
    RAW text, unjoined, because joining it is exactly what would hide the
    regression.
    """
    console = ScriptedConsole([], width=20)
    wizard._guidance(
        console,
        "A prefix keeps these lists from colliding with others on the site.",
    )
    lines = [line for line in console.text.splitlines() if line.strip()]
    assert len(lines) > 1, "the text must actually wrap to prove anything"
    assert all(line.startswith("  ") for line in lines), lines


def test_a_number_outside_the_table_reprompts_rather_than_indexing(
    tmp_path: Path,
) -> None:
    """`0` and a number past the end are both digits, and neither is a row.

    Nothing stops somebody typing the count of templates plus one, and a
    bare `int(answer) - 1` index would have handed back the LAST template
    for `0` -- silently scaffolding a family they did not choose.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "0",     # refused
        "999",   # refused
        "risk-register",
        "RR_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "n",   # build
        "y",   # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert (destination / "30-deploy" / "deploy.md").is_file()
    assert _collapsed(console).count("No template") == 2


def test_a_second_prefix_key_defeats_the_rewrite_and_the_read_back_says_so(
    tmp_path: Path,
) -> None:
    """The case the read-back exists for: the text changed, the meaning did not.

    The rewrite is a targeted `count=1` line edit, and YAML lets the last
    duplicate key win -- so a mapping declaring `prefix:` twice takes the
    edit on the first line and loads the second. Re-reading the *text*
    would have called that a success; only loading the mapping the build
    will load catches it, which is why the check is written that way.
    """
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        'prefix: "A_"\nentities: {}\nprefix: "B_"\n', encoding="utf-8",
    )

    with pytest.raises(wizard.WizardError, match="loaded back as 'B_'"):
        wizard._rewrite_prefix(mapping, "NEW_")


def test_a_template_directory_that_is_not_there_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A template the catalogue offered and the filesystem then could not
    supply is refused by `_read_facts`, before the destination is even
    asked -- an unhandled `FileNotFoundError` reading the shipped mapping
    would otherwise name the wizard's internals instead of the template.
    `_read_facts` catches `OSError` alongside the loader's own exceptions
    and turns it into one named `WizardError`.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    shutil.rmtree(solution.root)

    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, template="fake-template"))

    assert wizard.run_wizard(console) == 1
    assert "could not be loaded" in _collapsed(console)
    assert not destination.exists()


def test_a_rewrite_that_cannot_find_the_prefix_line_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run_wizard` has no top-level `except WizardError` -- only
    `KeyboardInterrupt` and `EOFError` are caught there. The `except
    (WizardError, OSError)` around `_scaffold` in `_run` is the ONLY thing
    standing between a `WizardError` raised mid-scaffold and a raw traceback
    on top of a project directory the wizard has already created, and
    `_read_facts` cannot cover it: that guard runs on the SHIPPED mapping,
    before the write, so it only catches what the real loader itself
    refuses.

    This fixture is built to get past `_read_facts` and fail only in
    `_scaffold`. The whole document is one line of flow-style YAML, so the
    real loader parses `prefix` and `entities` out of it happily -- but
    `_rewrite_prefix`'s `^prefix:` regex requires a line that STARTS with
    `prefix:`, and this line starts with `{`. MEASURED: the real loader
    accepts it and `_rewrite_prefix` still raises "no top-level `prefix:`
    line", which is exactly the gap between "the loader will take it" and
    "the targeted line-rewrite can find where the prefix belongs" that
    `_rewrite_prefix`'s own docstring exists to explain.
    """
    solution = _fake_family(
        tmp_path / "fake",
        mapping=(
            '{prefix: "OLD_", entities: {Risk: {kind: List, base_template: '
            "100, site_role: default}}}\n"
        ),
    )
    _offer_only(monkeypatch, solution)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", prefix="NEW_"),
    )

    assert wizard.run_wizard(console) == 1
    reported = _collapsed(console)
    assert "Could not scaffold the project" in reported
    assert "no top-level `prefix:` line" in reported
    # NOT `not destination.exists()`: `copytree` runs before the rewrite, so
    # the failure this test is about happens mid-scaffold, after the tree is
    # already copied. The wizard does not roll a partial write back -- it is
    # reported, not silently presented as a finished project, which is what
    # the two assertions above establish.


def test_a_copy_that_cannot_be_made_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other arm of the same boundary: `copytree` itself raising
    `OSError` -- a permissions error, a vanished source directory, anything
    discovered only at copy time, after `_read_facts` has already accepted
    the shipped mapping. `run_wizard` has no top-level `except WizardError`,
    so `_run`'s `except (WizardError, OSError)` around `_scaffold` is the
    only thing standing between this and a raw traceback on top of a
    directory the wizard may have already begun writing.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)

    def _refuse_to_copy(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(shutil, "copytree", _refuse_to_copy)

    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, template="fake-template"))

    assert wizard.run_wizard(console) == 1
    assert "Could not scaffold the project" in _collapsed(console)
    assert not destination.exists()


def test_a_template_whose_lists_could_not_be_read_is_still_described(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The catalogue deliberately returns no lists rather than refusing.

    `_mapping_facts` uses a plain `safe_load` of two keys precisely so one
    malformed template cannot take the picker down with it -- which means
    the describe panel has to render for a template with nothing to list,
    and say so, rather than showing an empty `Lists` line that reads like
    the template provisions nothing.
    """
    solution = replace(_fake_family(tmp_path / "fake"), lists=())
    _offer_only(monkeypatch, solution)

    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, template="fake-template"))

    assert wizard.run_wizard(console) == 0
    assert "(none declared)" in _collapsed(console)


def test_every_question_is_asked_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """The whole point of the sequence.

    `Build it now?` used to be answered and then followed by three more
    questions -- site role, reporting account, demo rows -- with nothing
    summarising them before a deploy bundle was generated against a real
    site. Declining at the single confirmation must leave no directory
    behind, no matter how many questions preceded it.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n", confirm="n"),
    )
    assert wizard.run_wizard(console) == 0
    assert not destination.exists()
    assert "Nothing written" in _collapsed(console)


def test_the_review_names_the_lists_that_will_be_created(
    tmp_path: Path,
) -> None:
    """The one thing the wizard never told you.

    You answer `ACME_` and it confirmed `Prefix ACME_`, never `ACME_Risk`.
    Now that a blank prefix is a valid answer this is the only place the
    difference between `Risk` and `ACME_Risk` is visible before the write.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(destination, prefix="ACME_", build="n", confirm="n"),
    )
    assert wizard.run_wizard(console) == 0
    assert "ACME_Risk" in _collapsed(console)


def _review(console: ScriptedConsole) -> str:
    """The Review panel alone, sliced out of the transcript at BOTH ends.

    Every value in that panel was typed by the operator moments earlier, so
    an unbounded substring assertion holds whether or not the panel renders
    the row it claims to cover -- which is exactly how the superseded `About
    to write` test came to check nothing: `risk-register` is a row in the
    catalogue table AND was the default of the project-directory prompt.

    `Review` is the panel's title and `Write the project` is the confirmation
    printed directly beneath it.

    Anchored from the RIGHT, and that is the part not to simplify away. The
    transcript above the panel carries the whole 31-row catalogue table, so
    a LEFT-anchored `split("Review", 1)` binds to the first `Review`
    anywhere on screen. No shipped template's id or title contains the word
    today -- all 31 checked 2026-08-12 -- but a `design-review` or
    `research-review` family added later would move the bound to the top of
    the table and silently re-widen every assertion below to the whole
    transcript. That is a test that stops checking without failing, which is
    the failure this repository exists to close.

    `rsplit` after cutting at the right-hand bound can only narrow that
    slice, NEVER widen it past the title -- it binds to the LAST `Review` at
    or before the confirmation, which is at or after the panel's own title
    line. It is not guaranteed to land exactly ON the title line: MEASURED
    2026-08-12, on a template titled `Design Review, Next steps`, the word
    `Review` occurs again INSIDE the panel's own Template row, and `rsplit`
    binds to THAT occurrence instead -- narrowing the slice and amputating
    the Template row rather than widening past the title. Narrowing is the
    safe direction: it makes a `row in panel` assertion fail loudly, rather
    than passing on a bound that has silently widened to swallow the
    transcript above it.
    """
    head, _, _ = _collapsed(console).partition("Write the project")
    return head.rsplit("Review", 1)[1]


def _next(console: ScriptedConsole) -> str:
    """The closing `Next` panel alone.

    Same right-anchored reasoning as `_review` above, for the same reason:
    `Next` is a common enough word that a future template title could carry
    it, and the catalogue table renders long before this panel does. There
    is nothing printed after the panel, so `rsplit` alone is the bound.
    """
    return _collapsed(console).rsplit("Next", 1)[1]


def test_the_review_names_every_answer(tmp_path: Path) -> None:
    """Supersedes the old `About to write` summary, which named four answers
    and could not name the other three because they had not been asked.

    Asserted as whole ROWS inside the panel, not as values anywhere on
    screen. `Build yes, site role default` is the row that shows why: a bare
    `"default" in shown` passes on the site-role value alone, and passed even
    with the whole Build row deleted.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(
            destination, build="y", seed="y",
            reader="svc.reporting@contoso.com", confirm="n",
        ),
        # Wide, so no row can be folded by the wrap: `_collapsed` rejoins at
        # whitespace, and a row broken mid-value never rejoins.
        width=400,
    )
    assert wizard.run_wizard(console) == 0
    panel = _review(console)
    for row in (
        "Template risk-register - Risk register",
        "Lists RR_Risk",
        f"Directory {destination}",
        "Site https://contoso.sharepoint.com/sites/x",
        "Build yes, site role default",
        "Reporting svc.reporting@contoso.com",
        "Demo rows yes",
    ):
        assert row in panel, row


def test_the_review_says_nobody_when_no_reporting_account_was_given(
    tmp_path: Path,
) -> None:
    """Blank is the DEFAULT answer, so this is the row most operators read.

    `answers.reader or "nobody"` short-circuits, so nothing -- not the test
    suite and not the branch gate, which sees one expression rather than two
    arms -- noticed when the `or "nobody"` was deleted and the row rendered
    as a bare label. An empty value there does not read as "nobody was
    enrolled"; it reads as a field the wizard failed to fill in, on the panel
    whose whole job is to state the decision.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n", reader="", confirm="n"),
        width=400,
    )
    assert wizard.run_wizard(console) == 0
    assert "Reporting nobody" in _review(console)


def test_the_panel_bounds_survive_a_template_named_after_a_panel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The silent rot `_review` and `_next` are right-anchored to prevent.

    No shipped family's id or title contains `Review` or `Next` today -- all
    31 checked 2026-08-12 -- so a left-anchored `split(..., 1)` is correct,
    and would stay correct right up until somebody ships `design-review`. At
    that point the bound jumps to the catalogue table, every assertion inside
    it widens to the whole transcript, and the suite stays green while
    checking nothing. A test that stops checking without failing is the
    failure this repository exists to close, so the offending template is
    invented here rather than waited for.

    The EXCLUSION assertions are what catch a bound that has widened: a
    widened bound still contains every row the real panel does, so
    `"Build ..." in review` passes whether or not the bound holds -- only
    "the prompts above the panel are NOT in it" separates a bound that holds
    from one that has quietly swallowed the screen.

    The positive assertions (`"Build yes, site role default" in review`) are
    NOT redundant with those, and must not be deleted as if they were: they
    are the ONLY guard against the opposite failure, a bound that has
    NARROWED to nothing. An empty string contains no substring, so every
    exclusion assertion above would pass trivially against a `_review` or
    `_next` that returned `""` -- the positive assertion is what proves the
    slice found the panel's real content, not merely the absence of what it
    should not contain.
    """
    solution = replace(
        _fake_family(tmp_path / "fake"),
        id="design-review", title="Design Review, Next steps",
    )
    _offer_only(monkeypatch, solution)
    _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        [solution.id, "NEW_", str(destination),
         "https://contoso.sharepoint.com/sites/x", "y", "y"],
        width=400,
    )
    assert wizard.run_wizard(console) == 0

    review = _review(console)
    assert "Build yes, site role default" in review
    assert "Project directory" not in review
    assert "Write the project" not in review

    closing = _next(console)
    assert "Paste build/deploy.js.txt" in closing
    assert "Project directory" not in closing


def test_the_review_of_a_declined_build_says_files_only(tmp_path: Path) -> None:
    """The other arm, and the two rows that must NOT appear.

    A reporting account and a demo-row answer were never collected, so
    printing `Reporting nobody` and `Demo rows no` here would state a
    decision nobody made -- and would look identical to a run that had been
    asked and had declined both.
    """
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(destination, build="n", confirm="n"), width=400,
    )
    assert wizard.run_wizard(console) == 0
    panel = _review(console)
    assert "Build no, copy the files only" in panel
    assert "Reporting" not in panel
    assert "Demo rows" not in panel


def test_the_confirmation_does_not_promise_a_build_that_was_declined(
    tmp_path: Path,
) -> None:
    """`Write the project and build it?` when it will, `Write the project?`
    when it will not."""
    destination = tmp_path / "out"
    console = ScriptedConsole(_answers(destination, build="n", confirm="n"))
    assert wizard.run_wizard(console) == 0
    assert "Write the project?" in _collapsed(console)


def test_the_confirmation_promises_the_build_that_was_accepted(
    tmp_path: Path,
) -> None:
    """The other arm. A fixed `Write the project?` would understate what the
    Enter key is about to do: generate a deploy bundle, not just copy files."""
    destination = tmp_path / "out"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n", confirm="n"),
    )
    assert wizard.run_wizard(console) == 0
    assert "Write the project and build it?" in _collapsed(console)


def test_the_declined_build_prints_a_command_carrying_the_site_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The escape hatch used to omit `--site-role` because it had not asked.

    Against a mapping declaring `hq` and `branch` and no `default`, the
    printed command therefore fell back to `--site-role default`, which
    `_require_known_site_role` refuses. Moving the question into the site
    section is what fixes it: the role is known whether or not the build runs.
    """
    family = tmp_path / "family"
    solution = _fake_family(
        family,
        mapping='prefix: "OLD_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: hq }\n"
        "  Note: { kind: List, base_template: 100, site_role: branch }\n",
    )
    _offer_only(monkeypatch, solution)

    destination = tmp_path / "out"
    console = ScriptedConsole(
        [solution.id, "NEW_", str(destination),
         "https://contoso.sharepoint.com/sites/x", "branch", "n", "y"],
    )
    assert wizard.run_wizard(console) == 0
    assert "--site-role branch" in _collapsed(console)


def test_the_template_summary_names_the_declared_prefix() -> None:
    """Task 7 is what makes this load-bearing, so it is pinned before then.

    The prefix question becomes conditional there: a template declaring no
    prefix is never asked for one, and this line is then the ONLY place the
    operator learns what their lists will be called before the Review panel
    names them. Dropping it back out of `_describe` leaves the whole suite
    green today, which is exactly why the assertion has to exist today.

    Both spellings, because `(none)` is not a formatting nicety -- a bare
    `prefix ` with nothing after it reads as a template whose prefix could
    not be read, rather than as one that declares none on purpose.
    """
    declared = Solution(
        id="x", title="Fake", summary="s", detail="",
        lists=("Risk",), prefix="RR_", root=Path("unused"),
    )
    with_prefix = ScriptedConsole([])
    wizard._describe(with_prefix, declared)
    assert "prefix RR_" in _collapsed(with_prefix)

    without = ScriptedConsole([])
    wizard._describe(without, replace(declared, prefix=""))
    assert "prefix (none)" in _collapsed(without)


def test_a_template_with_no_detail_sentence_prints_no_empty_line() -> None:
    """`_lead_sentence` returns "" for a README it cannot parse.

    Every shipped family has one, so nothing else reaches the empty arm --
    but a new template whose README opens with a table would print a blank
    dim line under its title, which reads like a rendering fault. Asserted
    as a LINE COUNT against the same solution with a detail, because the
    difference between the two arms is a line that is there or is not:
    a substring assertion cannot see a blank one.
    """
    solution = Solution(
        id="x", title="Fake", summary="s", detail="",
        lists=("Risk", "Control"), prefix="", root=Path("unused"),
    )
    without = ScriptedConsole([])
    wizard._describe(without, solution)
    with_detail = ScriptedConsole([])
    wizard._describe(with_detail, replace(solution, detail="A whole sentence."))

    assert "Fake - 2 lists: Risk, Control" in _collapsed(without)
    assert "A whole sentence." in _collapsed(with_detail)
    assert without.text.count("\n") < with_detail.text.count("\n")


def test_the_only_declared_site_role_is_not_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question with one possible answer is not a question.

    Every shipped family declares `default` and nothing else, so asking
    would put a prompt in front of all thirty of them to collect an answer
    the mapping already gives. The script here carries no answer for it, so
    a wizard that asked would run out of input and exit 130.
    """
    captured = _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="y", seed="n"))

    assert wizard.run_wizard(console) == 0
    assert "Site role" not in _collapsed(console)
    assert captured["site_role"] == "default"
    assert captured["mapping"] == destination / "20-configure" / "mapping.yaml"
    assert captured["schema"] == destination / "10-design" / "schema.dbml"
    assert captured["release"] == destination / "20-configure" / "release.yaml"
    assert captured["out"] == destination / "build"


def test_a_mapping_declaring_two_site_roles_asks_which_to_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And offers exactly the roles the mapping declares, not a fixed list.

    No shipped family has a second role today, so nothing else reaches this
    branch -- but a multi-site mapping is the documented reason `--site-role`
    exists, and the vocabulary has to stay data-driven the way `build` and
    `report` keep it. A hardcoded `default | admin` here would refuse a
    perfectly good mapping whose roles are `hq` and `branch`.

    The scripted answer is `default`, not `archive`, and that is the whole
    experiment. `_site_roles` sorts, so `roles[0]` is `archive` -- answering
    `archive` made the captured value identical for a wizard that asked and
    a wizard that took the first role and never asked at all, with the
    scripted answer sitting unread. Answering the OTHER role separates them.
    The prompt and the vocabulary it offered are asserted too, because
    "offers exactly the roles the mapping declares" is the sentence this
    test opens with and a captured value alone does not show it.
    """
    solution = _fake_family(
        tmp_path / "fake",
        mapping=_ONE_ENTITY + (
            "  Archive: { kind: List, base_template: 100, site_role: archive }\n"
        ),
    )
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "fake-template",
        "NEW_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "default",    # site role -- NOT roles[0], see the docstring
        "y",          # build
        "y",          # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert captured["site_role"] == "default"
    reported = _collapsed(console)
    assert "Site role" in reported
    assert "[archive/default]" in reported


def test_a_mapping_with_no_role_called_default_is_offered_no_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Enter key must not answer with a role nobody declared.

    `Prompt.ask` returns its default WITHOUT checking it against `choices`:
    rich short-circuits an empty answer in `PromptBase.__call__` before
    `process_response` ever runs. So a fixed `default="default"` on a
    mapping whose roles are `branch` and `hq` made Enter produce an
    undeclared role, and `execute_build` then refused it -- the wizard
    offered a dead end as its safest-looking answer, on exactly the
    multi-site mapping `--site-role` exists for.

    The script presses Enter FIRST and answers properly second. That is
    what makes the branch observable: restore the fixed default and this
    captures `default` with `hq` still sitting unread, rather than merely
    failing on a prompt that looks different.
    """
    solution = _fake_family(
        tmp_path / "fake",
        mapping=(
            'prefix: "OLD_"\n'
            "entities:\n"
            "  Risk: { kind: List, base_template: 100, site_role: hq }\n"
            "  Archive: { kind: List, base_template: 100, site_role: branch }\n"
        ),
    )
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "fake-template",
        "NEW_",
        str(destination),
        "https://contoso.sharepoint.com/sites/x",
        "",      # Enter -- must not be taken as an answer at all
        "hq",
        "y",     # build
        "y",     # confirm
    ])

    assert wizard.run_wizard(console) == 0
    assert captured["site_role"] == "hq"
    reported = _collapsed(console)
    assert "[branch/hq]" in reported
    assert "(default)" not in reported


def test_the_shipped_template_is_never_written_to(tmp_path: Path) -> None:
    """The wizard rewrites the COPY, and only the copy.

    Everything it edits -- the prefix line, the placeholders in the
    documentation -- is edited in place, so a path assembled against the
    solution's root rather than the destination would rewrite the template
    inside the installed package. It would work perfectly for the operator
    who ran it, and hand the next one a template carrying somebody else's
    prefix and somebody else's site URL.
    """
    root = load_solution("risk-register").root
    before = _tree_digest(root)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(
            destination,
            prefix="ACME_",
            site_url="https://contoso.sharepoint.com/sites/ops",
            build="y",
            seed="n",
        ),
    )

    assert wizard.run_wizard(console) == 0
    assert _tree_digest(root) == before


@pytest.mark.parametrize(
    ("stdin_tty", "stdout_tty", "expected"),
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_prompting_needs_both_streams_to_be_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdin_tty: bool,
    stdout_tty: bool,
    expected: bool,
) -> None:
    """Either stream being redirected means nobody can answer.

    `dbml-sharepoint | tee log` has a terminal on stdin and a pipe on
    stdout: the prompts go into the file and the user sees a hung command.
    That is the case a stdin-only check misses, and the caller falls back to
    printing help -- which is what a bare invocation did before the wizard
    existed.
    """

    class Stream:
        def __init__(self, tty: bool) -> None:
            self._tty = tty

        def isatty(self) -> bool:
            return self._tty

    monkeypatch.setattr(sys, "stdin", Stream(stdin_tty))
    monkeypatch.setattr(sys, "stdout", Stream(stdout_tty))

    assert wizard.stdin_is_interactive() is expected


def test_a_template_with_demo_items_is_asked_about_seeding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wizard's whole job is a first look at a template, and every colour
    map, row wash and declared view is invisible on an empty list.

    `--seed` has been available to `build` since the beginning and the wizard
    never offered it, so the one path aimed at somebody who has not used this
    tool before was the one path that could not show them what it does.
    """
    captured = _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="y", seed="y"))

    assert wizard.run_wizard(console) == 0
    assert captured["seed"] is True


def test_declining_the_seed_builds_without_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And it is declined by DEFAULT.

    Seeding writes `[DEMO]` rows into somebody's real SharePoint site. The
    documented flag defaults to off and the wizard must not be more forward
    than the flag it stands for -- pressing Enter through the wizard should
    never put demo data on a site.
    """
    captured = _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="y", seed=""))

    assert wizard.run_wizard(console) == 0
    assert captured["seed"] is False


def test_an_empty_reader_answer_means_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty is the default and must stay the safe one: pressing Enter must
    not enrol anybody.

    Also pins that blank is never handed to `validate_enterprise_reader`,
    which refuses the empty string. Validating it would turn the safest
    answer the question offers into the one answer that cannot be given:
    the prompt would refuse, re-ask, run out of script and exit 130 rather
    than 0. The script carries exactly one blank, so that regression is
    what the exit-code assertion below catches.
    """
    captured = _capture_build(monkeypatch)
    console = ScriptedConsole(
        _answers(tmp_path / "proj", build="y", seed="n", reader=""), width=400,
    )
    assert wizard.run_wizard(console) == 0
    assert captured["enterprise_reader"] is None
    assert "must not be empty" not in _collapsed(console)


def test_a_reader_answer_is_passed_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of the empty-answer case above: a real UPN reaches the
    build. Without this, `enterprise_reader is None` could pass merely
    because the key is always wired to `None` regardless of the answer."""
    captured = _capture_build(monkeypatch)
    console = ScriptedConsole(
        _answers(
            tmp_path / "proj", build="y", seed="n",
            reader="svc-reporting@example.org",
        ),
        width=400,
    )
    assert wizard.run_wizard(console) == 0
    assert captured["enterprise_reader"] == "svc-reporting@example.org"


def test_a_bad_reader_address_is_refused_and_reprompted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mistyped UPN must re-ask, not end the run in a traceback.

    `validate_enterprise_reader` raises `typer.BadParameter`, which is a
    `click.UsageError` and NOT a `typer.Exit` -- so the wizard's one
    `except typer.Exit` around `execute_build` could not catch it, and an
    address with no `@` propagated out of `run_wizard` as an unhandled
    exception, on top of a project directory already written to disk.

    The script answers the question twice: once with the typo, once with a
    real address. A wizard that did not re-ask would take the typo as the
    answer and hand it to the build -- which the captured assertion below
    catches -- and one that raised would fail this test as an error rather
    than an assertion, so both regressions are distinguishable from a pass.

    Written out rather than built from `_answers`, because the re-ask is an
    EXTRA answer in the middle of the script and the helper appends only at
    the end.
    """
    captured = _capture_build(monkeypatch)
    console = ScriptedConsole(
        [
            "risk-register",
            "RR_",
            str(tmp_path / "proj"),
            "https://contoso.sharepoint.com/sites/x",
            "y",                            # build
            "svc.reporting",                # refused: no '@'
            "svc-reporting@example.org",    # re-asked, accepted
            "n",                            # demo rows
            "y",                            # confirm
        ],
        width=400,
    )

    assert wizard.run_wizard(console) == 0
    assert captured["enterprise_reader"] == "svc-reporting@example.org"
    assert "single UPN with one '@'" in _collapsed(console)


def test_the_reader_question_is_not_asked_without_a_declared_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question whose only useful answer would be refused by `execute_build`
    is worse than silence -- mirrors `test_a_template_declaring_no_demo_items_
    is_not_asked`.

    `reader=None`, so the script carries no answer for the question. A wizard
    that asked would read the CONFIRMATION's `y` as a UPN, be refused by
    `validate_enterprise_reader` for having no `@`, re-ask, run out of input
    and exit 130. Passing `reader=""` here instead would hand the question a
    real answer and make the run succeed either way -- the exit-code
    assertion would then be pinning nothing, which is the whole reason
    `_answers` grew a `None`.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", build="y", reader=None),
    )

    assert wizard.run_wizard(console) == 0
    assert "enrol" not in _collapsed(console).lower()
    assert captured["enterprise_reader"] is None


def test_a_template_declaring_no_demo_items_is_not_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question whose only useful answer is refused is worse than silence.

    `--seed` against a mapping with no `demo_items` raises
    `SeedRequiresDemoItemsError` and the build exits non-zero, so offering
    the choice would be offering a dead end -- and the wizard would have
    walked the operator into it.

    `reader=None` and `seed` left off, so the script carries an answer for
    every question the wizard SHOULD put and none for either it should not.
    A wizard that asked the demo question would take the confirmation's `y`
    as the seed answer, then run out of input and exit 130.

    The word assertion was `"demo" not in shown` while the closing panel was
    the only place the word could appear. The Review panel now reports
    `Demo rows no` for every build -- accurately, and deliberately, since the
    point of that panel is to state the whole decision -- so the assertion
    names the caution and the QUESTION instead. Both are what "is not asked"
    means, and a wizard that put either would still be caught.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", build="y", reader=None),
    )

    assert wizard.run_wizard(console) == 0
    shown = _collapsed(console)
    assert "Add the demo rows?" not in shown
    assert "Demo rows are titled" not in shown
    assert captured["seed"] is False


def test_seeding_sends_the_operator_to_the_file_it_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A seeded bundle carries a THIRD script, and pasting the other two
    leaves the list empty.

    The closing panel names assess and deploy. Adding a file to the bundle
    without adding it to the instructions is how somebody seeds, sees no
    rows, and concludes the demo data is broken.
    """
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    # Wide, because this assertion reads a PATH out of the rendered
    # panel. `_collapsed` rejoins rich's wrapping at whitespace, and a
    # long path has none -- rich folds it mid-word, so
    # 'demo-data.js.txt' arrives split and the substring is not there.
    # It passed locally and failed on CI purely because the temp path
    # is longer there, which is the worst way to learn it.
    console = ScriptedConsole(
        _answers(destination, build="y", seed="y"), width=400,
    )

    assert wizard.run_wizard(console) == 0
    assert "demo-data.js.txt" in _collapsed(console)


def test_an_unseeded_run_does_not_mention_the_demo_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror: no demo file is written, so naming it would send the
    operator looking for something that is not there."""
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    # Wide, because this assertion reads a PATH out of the rendered
    # panel. `_collapsed` rejoins rich's wrapping at whitespace, and a
    # long path has none -- rich folds it mid-word, so
    # 'demo-data.js.txt' arrives split and the substring is not there.
    # It passed locally and failed on CI purely because the temp path
    # is longer there, which is the worst way to learn it.
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n"), width=400,
    )

    assert wizard.run_wizard(console) == 0
    assert "demo-data.js.txt" not in _collapsed(console)


def test_the_seed_question_carries_its_caution_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shipped family may seed data its own guide forbids on a live site.

    `equipment-maintenance` seeds ONE genuinely overdue infusion pump --
    eighteen days past its annual service -- because a view that demonstrates
    empty teaches the adopter it does not work. Its guide says plainly: do
    not seed a site that already holds a real schedule, and governance treats
    an overdue row as work to explain within five business days.

    So the caution has to reach the operator BEFORE the prompt they answer.
    Offering to create that and mentioning the guide afterwards is offering
    it too late.

    MERGED with a second test that made the same claim about the same path
    and differed only in confirming `n` rather than `y`. Two tests asserting
    one ordering is not two guards -- the second could only ever fail when
    this one did. What the second contributed was the assertion on the
    PATH's position rather than the caution's, and that is folded in below:
    naming `deploy.md` after the question would be an instruction the
    operator cannot act on before deciding.
    """
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n"), width=400,
    )

    assert wizard.run_wizard(console) == 0
    shown = _collapsed(console)
    question = shown.index("Add the demo rows?")
    assert shown.index("before seeding") < question, (
        "the caution must precede the question"
    )
    assert shown.index("30-deploy/deploy.md") < question, (
        "the guide's path must precede the question, not only follow it in "
        "the closing panel"
    )


def test_the_facts_match_between_the_shipped_family_and_the_copy(
    tmp_path: Path,
) -> None:
    """Why asking the build questions before the write is legitimate.

    The wizard reads roles, demo items and the reader group from the SHIPPED
    mapping so it can ask about them before writing anything. That is only
    sound because `_rewrite_prefix` is a single-line regex on `^prefix:` --
    entities, permissions and demo_items are byte-identical in the copy.
    Argued once in the spec; pinned here, because a future rewrite that
    touched a second line would make every gate answer the wrong question.
    """
    solutions = available_solutions()
    # A guard, not a formality: the loop below would pass just as happily
    # over an empty roster, proving nothing while looking like it walked all
    # thirty-one families. `test_no_two_templates_declare_the_same_entity_name`
    # in test_template_standard.py uses the same shape for the same reason.
    assert len(solutions) == 31, (
        f"{len(solutions)} templates discovered, not the 31 this walk was "
        "measured against -- re-verify the invariant before trusting an "
        "empty roster as a pass."
    )
    for solution in solutions:
        destination = tmp_path / solution.id
        console = ScriptedConsole(
            _answers(destination, template=solution.id, build="n"),
        )
        assert wizard.run_wizard(console) == 0, solution.id

        copied = wizard._read_facts(
            replace(solution, root=destination),
        )
        assert copied == wizard._read_facts(solution), solution.id


def test_a_template_the_loader_rejects_is_refused_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named refusal, not a traceback, and no half-made project.

    `_site_roles` used to call `load_mapping` on the copy AFTER the write and
    outside any guard, so a template the loader dislikes produced a traceback
    on top of a directory the wizard had just created. The picker tolerates
    such a template by design -- `_mapping_facts` avoids the loader precisely
    so one bad family cannot take down the list of thirty-one.
    """
    family = tmp_path / "family"
    # `entities:` absent entirely; `load_mapping` indexes `raw["entities"]`.
    solution = _fake_family(family, mapping='prefix: "OLD_"\n')
    _offer_only(monkeypatch, solution)

    destination = tmp_path / "out"
    # Two answers only -- the template and its prefix. The guard runs
    # straight after the prefix, so a third scripted answer would never be
    # consumed, and a spare answer at the end of a script is invisible, which
    # is exactly how a test comes to assert less than it looks like it does.
    # Under-scripting is the honest failure mode here: it surfaces as
    # EOFError and exit 130, not silence.
    console = ScriptedConsole([solution.id, "NEW_"])
    assert wizard.run_wizard(console) == 1
    assert not destination.exists()
    assert "fake-template" in _collapsed(console)


def test_the_site_roles_are_the_intersection(tmp_path: Path) -> None:
    """A role you deploy one site under must be one every template knows.

    The picker collects a single template today, so N=2 is only reachable
    here. `_site_roles` is a pure fold; testing it directly is honest.
    """
    both = wizard._TemplateFacts(
        roles=frozenset({"hq", "branch"}), demo_items=False, reader_group=False,
    )
    one = wizard._TemplateFacts(
        roles=frozenset({"branch"}), demo_items=False, reader_group=False,
    )
    assert wizard._site_roles([both]) == ["branch", "hq"]
    assert wizard._site_roles([both, one]) == ["branch"]


def test_templates_that_share_no_site_role_are_refused(tmp_path: Path) -> None:
    """Rather than picking one and letting `execute_build` refuse it later."""
    hq = wizard._TemplateFacts(
        roles=frozenset({"hq"}), demo_items=False, reader_group=False,
    )
    branch = wizard._TemplateFacts(
        roles=frozenset({"branch"}), demo_items=False, reader_group=False,
    )
    with pytest.raises(wizard.WizardError, match="no site role"):
        wizard._site_roles([hq, branch])


def test_no_templates_chosen_is_a_named_refusal_not_a_type_error() -> None:
    """`frozenset.intersection(*())` raises a bare `TypeError` -- confirmed
    on 3.14, since the star-unpacked call has no arguments at all -- which is
    not the named, fail-closed error AGENTS.md requires for anything
    uncertain.

    Unreachable from `_run` today: the picker always passes `_site_roles`
    exactly one element. But the signature accepts any `Sequence`, and the
    picker is moving toward collecting several templates, so an empty list
    must not regress into an unnamed crash the day that lands.
    """
    with pytest.raises(wizard.WizardError, match="no template"):
        wizard._site_roles([])


@pytest.mark.parametrize(
    ("seed", "carrier"),
    [("y", "seeding conditions"), ("n", "full procedure")],
)
def test_the_next_panel_names_the_guide_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed: str, carrier: str,
) -> None:
    """Once per arm, on a different line in each.

    Seeded, the line is step 3 -- the caution, which has to carry the path it
    points at -- and the dim footer is dropped: repeating the same path two
    lines later, inside a six-line panel, is noise the operator has to read
    past to find out it says nothing new. Unseeded there is no step 3, so the
    footer is the only pointer at the guide and it stays.

    Counted rather than merely present, because "names it once" is the whole
    claim and a `in` assertion cannot tell one mention from two.
    """
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    # Wide, because this reads paths out of a rendered panel; `_collapsed`
    # rejoins rich's wrapping at whitespace and a path has none, so a folded
    # one is silently uncountable.
    console = ScriptedConsole(
        _answers(destination, build="y", seed=seed), width=400,
    )

    assert wizard.run_wizard(console) == 0
    panel = _next(console)
    assert panel.count("30-deploy/deploy.md") == 1
    assert carrier in panel


def test_a_seeded_run_names_the_guide_before_the_demo_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same argument, one screen later: the closing panel is an instruction
    list, and an instruction read first is the only one that can prevent
    anything."""
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="y"), width=400,
    )

    assert wizard.run_wizard(console) == 0
    shown = _collapsed(console)
    assert shown.index("deploy.md", shown.index("Next")) < shown.index(
        "demo-data.js.txt", shown.index("Next"),
    )
