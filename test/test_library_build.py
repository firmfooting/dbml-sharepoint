# test/test_library_build.py
"""A family with one list and one document library builds end to end.

The fixture under `test/fixtures/library/` is what the shipped-solution
build gate would see for a family holding a library: the build validates
clean, the manifest names the folder phase and the folders, and every
emitted script parses under Node.
"""

import re
import subprocess
from pathlib import Path

import pytest
from _node import NODE
from _paths import FIXTURES, JINJA_TEMPLATES

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.pipeline import execute_build

LIBRARY = FIXTURES / "library"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("library-build")
    execute_build(
        schema=LIBRARY / "schema.dbml",
        mapping=LIBRARY / "mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci",
        time_zone="UTC",
        site_role="default",
        out=out,
    )
    return out


def test_the_library_family_builds(built: Path) -> None:
    assert (built / "deploy.js.txt").is_file()
    assert (built / "rollback.js.txt").is_file()


def test_the_manifest_names_the_folder_phase_and_its_folders(built: Path) -> None:
    manifest = (built / "deploy-manifest.md").read_text(encoding="utf-8")
    assert f"## Phase {phase_number('folders')}: declared folders" in manifest
    assert "**LIB_Doc**: Field operations, Corporate" in manifest


def test_the_deploy_carries_the_library_facts(built: Path) -> None:
    deploy = (built / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"is_library": true' in deploy
    assert '"Field operations",\n        "Corporate"' in deploy
    assert '"scope": 1' in deploy
    assert "FileLeafRef" in deploy


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("script", ["deploy.js.txt", "rollback.js.txt"])
def test_every_emitted_script_parses(built: Path, script: str) -> None:
    """The way CI checks a `.js.txt`: piped in, since Node will not read the
    extension, with the CommonJS input type the scripts are written for."""
    assert NODE is not None
    with (built / script).open("rb") as source:
        subprocess.run(  # noqa: S603
            [NODE, "--check", "--input-type=commonjs"],
            stdin=source, check=True, capture_output=True, text=True,
        )


def test_the_manifest_lists_folder_defaults_when_declared(built: Path) -> None:
    manifest = (built / "deploy-manifest.md").read_text(encoding="utf-8")
    assert f"## Phase {phase_number('folder_defaults')}: folder default values" in manifest
    assert "**LIB_Doc**: Corporate (Division=Corporate, Status=Complete)" in manifest
    assert "the defaults apply to files uploaded into the folder" in manifest


#: Helper names any template defines; a script that calls one must define it too.
_DEFINITION = re.compile(
    r"(?:^|\n)\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|"
    r"(?:^|\n)\s*(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\(|[A-Za-z_$][\w$]*\s*=>)",
)


def _helper_universe() -> set[str]:
    templates = Path(JINJA_TEMPLATES)
    names: set[str] = set()
    for path in templates.rglob("*.j2"):
        if path.name.endswith(".js.j2"):
            for m in _DEFINITION.finditer(path.read_text(encoding="utf-8")):
                # Only the script's own top level: deeper names are locals.
                indent = m.group(0).lstrip("\n")
                if indent.startswith("  ") and not indent.startswith("   "):
                    names.add(m.group(1) or m.group(2))
    return names


@pytest.mark.parametrize("script", ["deploy.js.txt", "assess.js.txt", "verify.js.txt"])
def test_every_helper_an_emitted_script_calls_is_defined_in_it(built: Path, script: str) -> None:
    """A template that calls a helper another template defines breaks only the scripts
    that omit the include, and only when its branch runs; this closes that gap."""
    text = (built / script).read_text(encoding="utf-8")
    defined = {m.group(1) or m.group(2) for m in _DEFINITION.finditer(text)}
    # Prose in comments and log strings can say "name(" without calling it.
    code = re.sub(r"//[^\n]*|'[^'\n]*'|`[^`$]*`", "", text)
    called = {
        m.group(1) for m in re.finditer(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", code)
    }
    missing = sorted((called & _helper_universe()) - defined)
    assert not missing, f"{script} calls helpers it never defines: {missing}"
