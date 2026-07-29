# src/dbml_sharepoint/templating.py
"""The one canonical Jinja environment for every rendered artifact.

One constructor for every generator, including the ``comment_safe``
filter the pasteable scripts need. That means a rendering rule —
StrictUndefined so a missing variable fails the build instead of emitting
``undefined`` into a script, and the A5 header-injection guard — is fixed
in exactly one place.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent / "templates"


def comment_safe(value: object) -> str:
    """Neutralise a block-comment terminator in raw header fields.

    Provenance fields (site URL, source file names) are interpolated into
    each script's leading ``/** … */`` block; a crafted ``*/`` must not
    close the comment and inject JS.
    """
    return str(value).replace("*/", "* /")


def script_env() -> Environment:
    """Environment for every generated artifact (scripts and manifests)."""
    # No autoescape by design: these templates emit JavaScript and
    # markdown, not HTML. Interpolations are guarded individually
    # (tojson for values, comment_safe for comment text).
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        autoescape=False,  # noqa: S701 — see comment above
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["comment_safe"] = comment_safe
    return env
