# test/manual/render_probes.py
"""Render each probe template to the pasteable .js an operator uses.

Probes are generated for the same reason deploy.js is: the harness they
share — site guard, digest handling, REST helpers, result table — was
copied into four scripts and had already drifted between them.

Run me after editing anything under templates/:

    .venv/Scripts/python.exe test/manual/render_probes.py
"""

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).parent / "templates"
OUT = Path(__file__).parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=False,  # noqa: S701 — emits JavaScript, not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def revision_of(template_path: Path) -> str:
    """A short content hash of one probe's sources, for it to print at run time.

    A pasted probe has no identity. An operator re-pasting a stale clipboard
    produces a transcript indistinguishable from one where a fix did not work —
    which has already cost a full round trip of diagnosis, the tell being the
    line numbers in a stack trace. A probe that names its own revision makes
    that a one-line check instead.

    Hashes the SOURCES, not the output: hashing the output would have to
    include the hash. Every partial is included because a harness change alters
    behaviour without touching the probe's own template.
    """
    digest = hashlib.sha256()
    for source in [template_path, *sorted(TEMPLATES.glob("_*.js.j2"))]:
        digest.update(source.read_bytes())
    return digest.hexdigest()[:8]


def render_one(template_path: Path) -> str:
    """Render one probe template to its script text."""
    return _env().get_template(template_path.name).render(
        revision=revision_of(template_path),
    )


def probe_templates() -> list[Path]:
    """Templates that render to a probe. Leading-underscore files are
    partials included by those, not probes in their own right."""
    return sorted(p for p in TEMPLATES.glob("*.js.j2") if not p.name.startswith("_"))


def target_for(template_path: Path) -> Path:
    """The rendered .js an operator pastes, for one template."""
    return OUT / template_path.name.removesuffix(".j2")


def render_all() -> list[Path]:
    """Render every probe template. Returns what was written."""
    written = []
    for template in probe_templates():
        target = target_for(template)
        target.write_text(render_one(template), encoding="utf-8")
        written.append(target)
    return written


if __name__ == "__main__":
    for path in render_all():
        print(f"rendered {path}")
