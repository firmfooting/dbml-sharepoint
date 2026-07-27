# test/test_probes.py
"""Gates over the manual probe scripts.

A probe is pasted into a live tenant's browser console by a person, so
nothing about it is exercised by the rest of this suite. These are the
only automated checks it gets, and each one exists because of something
that actually went wrong in this repository.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

MANUAL = Path(__file__).parent / "manual"
TEMPLATES = MANUAL / "templates"

# Everything except tab, newline and carriage return.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
PLACEHOLDER_HOSTS = re.compile(r"https://(example|contoso|tenant|yourtenant|x)\.")


def _load_renderer() -> ModuleType:
    """Import render_probes by path.

    NOT ``from test.manual import render_probes``: ``test`` is a CPython
    stdlib package name, so importing through it is a collision waiting to
    happen on someone else's machine.
    """
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _probe_scripts() -> list[Path]:
    return sorted(MANUAL.glob("*.js"))


def _all_probe_sources() -> list[Path]:
    return _probe_scripts() + sorted(TEMPLATES.glob("*.js.j2"))


def test_rendered_probes_match_their_templates() -> None:
    """An operator pastes the .js, so a stale .js is a probe that does not
    match the template anyone reviewed."""
    render = _load_renderer()
    stale = []
    for template in render.probe_templates():
        target = render.target_for(template)
        actual = target.read_text(encoding="utf-8") if target.exists() else ""
        if render.render_one(template) != actual:
            stale.append(target.name)
    assert not stale, (
        f"Stale rendered probe(s): {stale}. Run: "
        f".venv/Scripts/python.exe test/manual/render_probes.py"
    )


def test_probes_carry_no_tenant_url() -> None:
    """A tenant URL committed here has leaked twice, both times through a
    SITE_URL field an operator edited. Probes read the site they are pasted
    into and must never carry one."""
    offenders = [
        f"{path.name}: {host}"
        for path in _all_probe_sources()
        for host in re.findall(
            r"https://[a-z0-9-]+\.sharepoint\.com", path.read_text(encoding="utf-8"),
        )
        if not PLACEHOLDER_HOSTS.match(host)
    ]
    assert not offenders, f"Tenant URL in probe(s): {offenders}"


WRITE_CALL = re.compile(r"""method:\s*['"](POST|MERGE|DELETE|PUT)['"]""")


def test_a_probe_that_writes_defaults_to_read_only() -> None:
    """A probe that can write must describe what it would do and stop,
    until the operator opts in.

    Both guards are checked as committed, not as designed: this repository
    has twice committed an operator's local run-edit, and a probe whose
    guard ships flipped to true writes to the tenant of whoever pastes it.

    A read-only probe needs no guard, so the requirement is conditional on
    the script actually containing a write call.
    """
    for path in _probe_scripts():
        text = path.read_text(encoding="utf-8")
        if not WRITE_CALL.search(text):
            continue
        declared = {
            flag: value
            for flag in ("CONFIRMED", "ALLOW_WRITES")
            if (m := re.search(rf"^\s*(?:const|let|var)\s+{flag}\s*=\s*(\w+)", text, re.MULTILINE))
            and (value := m.group(1))
        }
        assert declared, (
            f"{path.name} performs writes but declares no guard. It needs at "
            f"least one of CONFIRMED / ALLOW_WRITES."
        )
        # How many guards a probe needs is its own business — one flag
        # gating everything is fine for a probe whose whole purpose is to
        # write. What is not negotiable is that each one ships off.
        for flag, value in declared.items():
            assert value == "false", (
                f"{path.name}: {flag} is committed as {value!r}. Pasting this "
                f"file would write to the tenant of whoever ran it, without "
                f"asking. It must be committed as false."
            )


def test_probes_carry_no_control_characters() -> None:
    """A NUL byte reached generated deploy.js on this branch and was
    invisible to ruff, mypy, j2lint, the golden comparison and the whole
    suite. Only git showed it, as 'Bin N -> M bytes'."""
    for path in _all_probe_sources():
        found = CONTROL_CHARS.findall(path.read_text(encoding="utf-8"))
        assert not found, (
            f"{path.name}: control character(s) {[hex(ord(c)) for c in found]}"
        )


def test_rendered_probes_are_syntactically_valid() -> None:
    """Without this, an operator discovers a probe does not parse by
    pasting it into a live tenant."""
    for path in _probe_scripts():
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"{path.name} does not parse:\n{result.stderr}"
