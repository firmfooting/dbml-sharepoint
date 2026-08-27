"""A scripted console, for the tests that drive a wizard.

Shared by `test_wizard.py` and `test_extract.py`, which drive two
different wizards the same way: rich's `Prompt` and `Confirm` both read
through `console.input`, so replacing that keeps the real prompt objects
under test, including their defaults and their `choices=` validation.
"""

import io
from collections.abc import Sequence

from rich.console import Console


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
