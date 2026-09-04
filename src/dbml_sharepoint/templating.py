# src/dbml_sharepoint/templating.py
"""The one canonical Jinja environment for every rendered artifact.

One constructor for every generator, including the ``comment_safe``
filter the pasteable scripts need. That means a rendering rule
(StrictUndefined so a missing variable fails the build instead of emitting
``undefined`` into a script, and the A5 header-injection guard) is fixed
in exactly one place.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from dbml_sharepoint.analysis.typemap import (
    BASE_TYPE_AS_STRING_PAIRS,
    DERIVED_FIELD_PROPERTIES,
    DERIVED_FIELD_PROPERTY_KINDS,
    MULTI_TYPE_AS_STRING_PAIRS,
    TYPE_AS_STRING_PAIRS,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def comment_safe(value: object) -> str:
    """Neutralise a block-comment terminator in raw header fields.

    Provenance fields (site URL, source file names) are interpolated into
    each script's leading ``/** ... */`` block; a crafted ``*/`` must not
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
        autoescape=False,  # noqa: S701 (see comment above)
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["comment_safe"] = comment_safe
    # A GLOBAL rather than a per-render argument, because the fact belongs to
    # every script that reconciles a field and no generator should be able to
    # forget it. The eleven pairs were previously typed out by hand inside
    # `deploy/_field_reconcile.js.j2`, three languages away from the Python
    # that assigns them, and a missing entry there does not fail this build.
    # It throws in the operator's browser, mid-deploy, on a customer site.
    # `analysis/typemap.py` owns the pairing; `test_typemap.py` asserts the
    # rendered Map covers every FieldKind.
    env.globals["type_as_string_by_kind"] = TYPE_AS_STRING_PAIRS
    # The arity half of the same fact. A LookupMulti reads back the same
    # FieldTypeKind as a Lookup, so the number alone no longer names the type
    # and the deployer picks between these two maps on AllowMultipleValues.
    env.globals["multi_type_as_string_by_kind"] = MULTI_TYPE_AS_STRING_PAIRS
    env.globals["base_type_as_string"] = BASE_TYPE_AS_STRING_PAIRS
    # Rendered into both the probe that SELECTS these properties and the
    # reconciler that COMPARES them, which were two hand-kept copies of one
    # list.
    env.globals["derived_field_properties"] = DERIVED_FIELD_PROPERTIES
    env.globals["derived_field_property_kinds"] = DERIVED_FIELD_PROPERTY_KINDS
    return env
