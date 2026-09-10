"""A scripted console, and the plain text of a rendered CLI result.

Shared by `test_wizard.py` and `test_extract.py`, which drive two
different wizards the same way: rich's `Prompt` and `Confirm` both read
through `console.input`, so replacing that keeps the real prompt objects
under test, including their defaults and their `choices=` validation.
"""

import io
import re
from collections.abc import Sequence

from rich.console import Console

#: Rich's SGR escapes. Typer's highlighter styles each run of an option name
#: separately, so `--time-zone` arrives as three of them.
_SGR = re.compile(r"\x1b\[[0-9;]*m")


def plain(rendered: str) -> str:
    """A rendered CLI result with the colour taken out.

    MEASURED 2026-09-10: `typer.rich_utils` sets `FORCE_TERMINAL` at import
    time from `GITHUB_ACTIONS`, `FORCE_COLOR` or `PY_COLORS`, so a CLI error
    is styled on CI and bare on a developer machine. Its highlighter then
    splits `--time-zone` into `-`, `-time` and `-zone`, each in its own
    escape, and the plain string is genuinely absent from the output.

    That is the worst way round. An assertion on rendered text passes where
    it was written and fails only once pushed, saying nothing about the
    behaviour it was meant to pin. Setting `NO_COLOR` from a test does not
    help, because the decision is already made by the time one runs.
    """
    return _SGR.sub("", rendered)


class ScriptedConsole(Console):
    """A console that answers prompts from a fixed list.

    Renders to a StringIO so a test can assert on what the user was shown,
    and raises `EOFError` when the script runs out -- which is what a real
    terminal does on Ctrl-D, and which both wizards already handle. A test
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


def collapsed(console: ScriptedConsole) -> str:
    """What the user was shown, on one line.

    Rich wraps at the console width, so a substring assertion against the
    raw text is a false negative waiting to happen -- a message can be
    correct and still fail the check because it broke over two lines.
    """
    return " ".join(console.text.split())
