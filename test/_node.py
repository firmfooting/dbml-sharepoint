# test/_node.py
"""Execute a generated browser script under Node.

Shared by the deploy and assess runtime tests. A golden-file comparison
proves a generated script does not CHANGE; only running it proves it RUNS,
and the emitted scripts are the artefacts operators paste into production
sites.

Node is required; every caller skips without it rather than failing, since
it is not a dependency of the package. That skip is a LOCAL convenience
only: `test/conftest.py` refuses a run under CI with node missing, because
a skip there would retire the whole executed-script suite without turning
anything red.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from _sp_mock import PRELUDE, UnselectedReadError, unselected_reads

NODE = shutil.which("node")


def run_node(script: str) -> str:
    """Run `script` under Node and return stdout+stderr.

    Via a FILE, never `node -e`: deploy.js is far past the Windows
    command-line limit.

    `newline="\n"` is a DELIBERATE behaviour change made when this moved out
    of test_deploy_runtime.py, not part of the move. The previous spelling
    let `write_text` translate on Windows, so the deploy tests were running a
    CRLF copy of a script the generator emits as LF -- the artefact under
    test was not the artefact that ships. This makes Node parse the emitted
    bytes. Kept on review; see AGENTS.md on generated files and LF.

    Every script runs behind `_sp_mock.PRELUDE`, which projects each mock GET
    to its `$select`; a read of a property the request never selected raises
    `UnselectedReadError` here rather than passing on `undefined` (#574). It
    also answers an empty set returned for a single entity with the absent
    status SharePoint gives that entity.
    """
    assert NODE is not None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "run.js"
        path.write_text(script, encoding="utf-8", newline="\n")
        prelude = Path(tmp) / "sp_mock.cjs"
        prelude.write_text(PRELUDE, encoding="utf-8", newline="\n")
        # Files, not pipes: Node writes to a pipe asynchronously on POSIX, so an exit
        # handler's write past the pipe buffer is lost (Node docs, "A note on process I/O").
        out_path, err_path = Path(tmp) / "stdout.txt", Path(tmp) / "stderr.txt"
        with out_path.open("wb") as out, err_path.open("wb") as err:
            subprocess.run(  # noqa: S603
                [NODE, "--require", str(prelude), str(path)], stdout=out, stderr=err,
                timeout=180, check=False,
            )
        stdout = out_path.read_bytes().decode("utf-8", errors="replace")
        stderr = err_path.read_bytes().decode("utf-8", errors="replace")
    output = stdout + stderr
    reads = unselected_reads(output)
    if reads:
        raise UnselectedReadError(reads)
    return output
