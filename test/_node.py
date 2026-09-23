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
        proc = subprocess.run(  # noqa: S603
            [NODE, "--require", str(prelude), str(path)], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180, check=False,
        )
    # stdout/stderr are None only if capture failed, which cannot happen here;
    # the guard keeps a decode collapse from surfacing as a TypeError that
    # hides the finding the test is asserting on.
    output = (proc.stdout or "") + (proc.stderr or "")
    reads = unselected_reads(output)
    if reads:
        raise UnselectedReadError(reads)
    return output
