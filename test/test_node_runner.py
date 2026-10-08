"""run_node returns everything a script writes, including from an exit handler."""
import pytest
from _node import NODE, run_node

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def test_a_large_write_from_an_exit_handler_comes_back_whole() -> None:
    # Node writes to a pipe asynchronously on POSIX, so a write past the pipe buffer was lost.
    script = "process.on('exit', () => console.log('__BIG__' + 'x'.repeat(1000000)));\n"
    line = next(ln for ln in run_node(script).splitlines() if ln.startswith("__BIG__"))
    assert line == "__BIG__" + "x" * 1_000_000
