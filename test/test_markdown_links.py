"""Every relative link in the tracked markdown outside the docs site resolves on disk.

Docusaurus refuses a broken link inside `website/` at build time; nothing
else read these, and a blueprint that leaves core takes link targets with it.
"""

import re
import subprocess

import pytest
from _paths import REPO_ROOT

LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
EXCLUDED = ("website/", "CHANGELOG.md")


def _tracked_markdown() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Skipping is honest; returning [] would pass without reading a file.
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    return [name for name in result.stdout.split("\0") if name and not name.startswith(EXCLUDED)]


def test_every_relative_link_outside_the_docs_site_resolves() -> None:
    names = _tracked_markdown()
    assert len(names) > 20, names
    broken = []
    for name in names:
        page = REPO_ROOT / name
        for target in LINK.findall(page.read_text(encoding="utf-8")):
            if "://" in target or target.startswith(("mailto:", "/")):
                continue
            if not (page.parent / target).exists():
                broken.append(f"{name}: {target}")
    assert broken == []


def test_every_command_named_in_markdown_outside_the_docs_site_exists() -> None:
    """A README that names a subcommand the CLI does not have sends the reader to a dead end."""
    from typer.main import get_command

    from dbml_sharepoint.cli import app

    commands = set(getattr(get_command(app), "commands", {}))
    assert commands, "the CLI declares no subcommands, so this pins nothing"
    named = re.compile(r"`dbml-sharepoint ([a-z][a-z-]*)")
    unknown = []
    for name in _tracked_markdown():
        for match in named.finditer((REPO_ROOT / name).read_text(encoding="utf-8")):
            if match.group(1) not in commands:
                unknown.append(f"{name}: dbml-sharepoint {match.group(1)}")
    assert unknown == []
