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
from dbml_sharepoint.catalogue import PLACEHOLDER_SITE_URL, Solution, load_solution
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
    reader: str = "", **over: str,
) -> list[str]:
    """The happy-path script: template, directory, prefix, site, confirm.

    `seed` answers the demo-rows question, which the wizard asks only after
    the build is confirmed AND only for a mapping that declares demo items.
    Left out by default so a script that does not reach it stays honest: a
    spare answer at the end of the list is invisible, and a missing one
    surfaces as EOFError rather than as silence.

    `reader` answers the enterprise-reader question, asked (only when the
    copied mapping declares an `enroll_enterprise_reader` group) right after
    the build confirmation, before `seed`. Unlike `seed` it defaults to a
    real answer -- blank, "enrol nobody" -- rather than `None`, because
    every shipped family declares such a group today (unlike demo items),
    so most callers reach the question and a `None` default would silently
    break them. Reader's default answer sits unread when the copied
    mapping declares no such group, which is exactly what "a spare answer
    is invisible" already covers.
    """
    script = {
        "template": "risk-register",
        "destination": str(destination),
        "prefix": "RR_",
        "site_url": "https://contoso.sharepoint.com/sites/x",
        "write": "y",
    }
    script.update(over)
    tail = [build]
    if build == "y":
        tail.append(reader)
        if seed is not None:
            tail.append(seed)
    return [*script.values(), *tail]


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
    return wizard.Answers(
        destination=destination,
        site_url="https://contoso.sharepoint.com/sites/x",
        templates=choices,
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
        str(occupied),      # refused
        str(destination),   # accepted
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
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
    assert "Repointed" in console.text


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
    # happen. The prompts themselves say "List name prefix", so the check has
    # to be against the substitution's own `label old -> new` spelling rather
    # than the bare word.
    reported = " ".join(console.text.split())
    assert "site URL" in reported
    assert "prefix RR_" not in reported


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
    console = ScriptedConsole(_answers(destination, write="n"))

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
        str(destination),
        "RR_",
        "http://insecure.example.com/sites/x",       # refused
        "https://contoso.sharepoint.com/sites/x",    # accepted
        "y",
        "n",
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
        str(destination),
        "has a space",   # refused
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
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
        str(destination),
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
    ])

    assert wizard.run_wizard(console) == 0
    assert "No template" in console.text


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
        str(occupied),      # refused
        str(destination),   # accepted
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
    ])

    assert wizard.run_wizard(console) == 0
    assert occupied.read_text(encoding="utf-8") == "keep me"
    assert "exists and is not a directory" in _collapsed(console)
    assert (destination / "README.md").is_file()


def test_a_whitespace_only_prefix_is_refused_and_reprompted(tmp_path: Path) -> None:
    """The empty half of the prefix guard, which the character class cannot
    catch: ` ` strips to nothing, and writing `prefix: ""` would rename
    every list in the template to its bare entity name without ever saying
    so."""
    destination = tmp_path / "proj"
    console = ScriptedConsole([
        "risk-register",
        str(destination),
        "   ",   # refused: strips to empty
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
    ])

    assert wizard.run_wizard(console) == 0
    assert load_mapping(
        destination / "20-configure" / "mapping.yaml",
    ).mapping.prefix == "RR_"


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
        str(destination),
        "RR_",
        "https://contoso.sharepoint.com/sites/x",
        "y",
        "n",
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


def test_a_template_with_no_prefix_line_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_rewrite_prefix` fails closed, and the wizard has to carry that
    through to an exit code rather than letting a `WizardError` out of a
    prompt loop. The user is told what went wrong and nothing half-written
    is presented as a project."""
    solution = _fake_family(tmp_path / "fake", mapping="entities: {}\n")
    _offer_only(monkeypatch, solution)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", prefix="NEW_"),
    )

    assert wizard.run_wizard(console) == 1
    reported = _collapsed(console)
    assert "Could not scaffold the project" in reported
    assert "no top-level `prefix:` line" in reported


def test_a_template_directory_that_is_not_there_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other arm of the same guard: `copytree` raising `OSError`.

    A template the catalogue offered and the filesystem then could not
    supply is not a case the wizard can recover from, but it is one it must
    name -- an unhandled `FileNotFoundError` out of `shutil` names the
    wizard's internals instead of the template.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    shutil.rmtree(solution.root)

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


def test_the_summary_names_every_answer_before_the_write_is_confirmed(
    tmp_path: Path,
) -> None:
    """The confirm is the only chance to catch a mistyped answer.

    Four questions back, "Write these files?" is not enough on its own to
    review -- the panel above it is what the operator actually checks, and
    a panel that omitted one of the four would be worse than no panel,
    because it looks like a complete summary.
    """
    destination = tmp_path / "proj"
    site_url = "https://contoso.sharepoint.com/sites/ops"
    # Wide, so the destination path cannot be folded mid-word by the wrap.
    console = ScriptedConsole(
        _answers(destination, prefix="ACME_", site_url=site_url), width=400,
    )

    assert wizard.run_wizard(console) == 0
    reported = _collapsed(console)
    # Bounded at BOTH ends. Stopping at the confirm is not enough for the
    # template: `risk-register` is a row in the catalogue table and the
    # default of the project-directory prompt, so that assertion held with
    # or without the panel line it claims to cover. The prefix, directory
    # and site URL are all answers that differ from their defaults, so they
    # appear nowhere but the panel -- but the bound belongs on all four,
    # since the next value added here will not necessarily be chosen that
    # way.
    panel = reported.split("About to write")[1].split("Write these files?")[0]
    assert "risk-register" in panel
    assert str(destination) in panel
    assert "ACME_" in panel
    assert site_url in panel


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
        str(destination),
        "NEW_",
        "https://contoso.sharepoint.com/sites/x",
        "y",          # write
        "y",          # build
        "default",    # site role -- NOT roles[0], see the docstring
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
        str(destination),
        "NEW_",
        "https://contoso.sharepoint.com/sites/x",
        "y",     # write
        "y",     # build
        "",      # Enter -- must not be taken as an answer at all
        "hq",
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
    real address. A wizard that did not re-ask would consume the second
    answer as the seed answer and then run out of input (exit 130), and one
    that raised would fail this test as an error rather than an assertion
    -- so both regressions are distinguishable from a pass.
    """
    captured = _capture_build(monkeypatch)
    console = ScriptedConsole(
        # `seed` left off so `_answers` stops after the typo; the re-ask
        # and the seed answer are appended in the order the wizard asks
        # them, which is what makes an absent re-ask show up as EOFError
        # rather than as the seed question silently eating a UPN.
        [
            *_answers(tmp_path / "proj", build="y", reader="svc.reporting"),
            "svc-reporting@example.org",
            "n",
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
    is_not_asked`. The script carries no answer for it, so a wizard that
    asked would run out of input and exit 130."""
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", build="y"),
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
    walked the operator into it. The script carries no answer for the
    question, so a wizard that asked would run out of input and exit 130.
    """
    solution = _fake_family(tmp_path / "fake")
    _offer_only(monkeypatch, solution)
    captured = _capture_build(monkeypatch)

    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, template="fake-template", build="y"),
    )

    assert wizard.run_wizard(console) == 0
    assert "demo" not in _collapsed(console).lower()
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
    """
    _capture_build(monkeypatch)
    destination = tmp_path / "proj"
    console = ScriptedConsole(
        _answers(destination, build="y", seed="n"), width=400,
    )

    assert wizard.run_wizard(console) == 0
    shown = _collapsed(console)
    caution = shown.index("before seeding")
    question = shown.index("Add the template's demo rows")
    assert caution < question, "the caution must precede the question"
    assert "deploy.md" in shown


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
