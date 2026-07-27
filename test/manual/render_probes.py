# test/manual/render_probes.py
"""Render each probe template to the pasteable .js an operator uses.

Probes are generated for the same reason deploy.js is: the harness they
share — site guard, digest handling, REST helpers, result table — was
copied into four scripts and had already drifted between them.

Run me after editing anything under templates/:

    .venv/Scripts/python.exe test/manual/render_probes.py
"""

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


def render_one(template_path: Path) -> str:
    """Render one probe template to its script text."""
    return _env().get_template(template_path.name).render()


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
