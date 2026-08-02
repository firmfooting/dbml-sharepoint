"""The interactive wizard.

Driven through a Console whose `input` is scripted, which is how rich's
`Prompt`/`Confirm` read: both call `console.input`. Patching that rather
than `Prompt.ask` keeps the real prompt objects -- including their default
handling and their validation of a `choices=` answer -- under test.
"""

import io
from collections.abc import Sequence
from pathlib import Path

import pytest
from rich.console import Console

from dbml_sharepoint import wizard
from dbml_sharepoint.catalogue import load_solution
from dbml_sharepoint.model.mapping_loader import load_mapping


class ScriptedConsole(Console):
    """A console that answers prompts from a fixed list.

    Renders to a StringIO so a test can assert on what the user was shown,
    and raises `EOFError` when the script runs out -- which is what a real
    terminal does on Ctrl-D, and which the wizard already handles. A test
    that under-scripts therefore fails as an assertion about the wizard's
    exit code rather than hanging.
    """

    def __init__(self, answers: Sequence[str]) -> None:
        super().__init__(file=io.StringIO(), width=100, force_terminal=False)
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


def _answers(destination: Path, *, build: str = "n", **over: str) -> list[str]:
    """The happy-path script: template, directory, prefix, site, confirm."""
    script = {
        "template": "risk-register",
        "destination": str(destination),
        "prefix": "RR_",
        "site_url": "https://contoso.sharepoint.com/sites/x",
        "write": "y",
    }
    script.update(over)
    return [*script.values(), build]


def test_scaffolds_the_whole_family(tmp_path: Path) -> None:
    """Not just the three build inputs.

    DEPLOY.md, STAFF-GUIDE.md and GOVERNANCE.md are the reason the
    templates are worth shipping; a scaffold that dropped them would leave
    the user with a mapping and no explanation of it.
    """
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination))

    assert wizard.run_wizard(console) == 0

    assert (destination / "10-design" / "schema.dbml").is_file()
    assert (destination / "20-configure" / "mapping.yaml").is_file()
    assert (destination / "20-configure" / "release.yaml").is_file()
    assert (destination / "30-deploy" / "DEPLOY.md").is_file()
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
                id="fake-template", title="Fake", summary="s",
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
    console = ScriptedConsole(_answers(destination, build="y"))

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
    console = ScriptedConsole(_answers(destination, prefix="ACME_", build="y"))

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
    console = ScriptedConsole(_answers(destination, build="y"))
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
    the form the copied DEPLOY.md also uses."""
    destination = tmp_path / "proj"
    console = ScriptedConsole(_answers(destination, build="n"))

    assert wizard.run_wizard(console) == 0
    assert "10-design/schema.dbml" in console.text
    assert "20-configure/mapping.yaml" in console.text
