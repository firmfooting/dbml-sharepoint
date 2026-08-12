# test/_node.py
"""Execute a generated browser script under Node.

Shared by the deploy and assess runtime tests. A golden-file comparison
proves a generated script does not CHANGE; only running it proves it RUNS,
and the emitted scripts are the artefacts operators paste into production
sites.

Node is required; every caller skips without it rather than failing, since
it is not a dependency of the package.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

NODE = shutil.which("node")


def run_node(script: str) -> str:
    """Run `script` under Node and return stdout+stderr.

    Via a FILE, never `node -e`: deploy.js is far past the Windows
    command-line limit. Written with an explicit LF newline so the script
    Node parses is byte-for-byte the one the generator emitted.
    """
    assert NODE is not None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "run.js"
        path.write_text(script, encoding="utf-8", newline="\n")
        proc = subprocess.run(  # noqa: S603
            [NODE, str(path)], capture_output=True, text=True, timeout=180, check=False,
        )
    return proc.stdout + proc.stderr
