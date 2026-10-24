# src/dbml_sharepoint/templating.py
"""The one canonical Jinja environment for every rendered artifact.

One constructor for every generator, including the ``comment_safe``
filter the pasteable scripts need. That means a rendering rule
(StrictUndefined so a missing variable fails the build instead of emitting
``undefined`` into a script, and the A5 header-injection guard) is fixed
in exactly one place.
"""

import re
from collections import ChainMap
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import ClassVar, override

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.bccache import Bucket, BytecodeCache

import dbml_sharepoint
from dbml_sharepoint import APPLICATION_NAME, COMMAND_NAME
from dbml_sharepoint.analysis.permissions import TENANT_WIDE_CLAIM_NEEDLES
from dbml_sharepoint.analysis.typemap import (
    BASE_TYPE_AS_STRING_PAIRS,
    DERIVED_FIELD_PROPERTIES,
    DERIVED_FIELD_PROPERTY_KINDS,
    MULTI_TYPE_AS_STRING_PAIRS,
    TYPE_AS_STRING_PAIRS,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

#: Safe unescaped in a JavaScript string, a CSOM XML attribute and an OData literal.
_APPLICATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class ApplicationNameError(ValueError):
    """An application name the generated scripts cannot carry safely."""


def check_application_name(application: str) -> None:
    """Refuse a name that could escape a string, comment or attribute it is rendered into."""
    if not _APPLICATION_NAME.fullmatch(application):
        raise ApplicationNameError(
            f"application name {application!r} must be 1 to 64 letters, digits, '.', '_' "
            "or '-', starting with a letter or digit",
        )


def comment_safe(value: object) -> str:
    """Neutralise a block-comment terminator in raw header fields.

    Provenance fields (site URL, source file names) are interpolated into
    each script's leading ``/** ... */`` block; a crafted ``*/`` must not
    close the comment and inject JS.
    """
    return str(value).replace("*/", "* /")


def markdown_cell(value: object) -> str:
    """Keep arbitrary text inside one Markdown table cell."""
    return str(value).replace("&", "&amp;").replace("|", "&#124;").replace("\n", " ")


def code_span(value: object) -> str:
    """A Markdown code span whose fence is longer than any backtick run inside the value."""
    text = str(value)
    runs = re.findall(r"`+", text)
    fence = "`" * (max(map(len, runs), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


class _ProcessLoader(FileSystemLoader):
    """Reads each template once per process; every script_env() environment shares the text."""

    _sources: ClassVar[dict[str, tuple[str, str, Callable[[], bool]]]] = {}

    @override
    def get_source(
        self, environment: Environment, template: str,
    ) -> tuple[str, str, Callable[[], bool]]:
        if template not in self._sources:
            source, filename, _ = super().get_source(environment, template)
            self._sources[template] = (source, filename, lambda: True)
        return self._sources[template]


class _MemoryBytecodeCache(BytecodeCache):
    """Compiled templates held for the process, so the partials compile once, not per generator."""

    def __init__(self) -> None:
        self._buckets: dict[str, bytes] = {}

    @override
    def load_bytecode(self, bucket: Bucket) -> None:
        if bucket.key in self._buckets:
            bucket.bytecode_from_string(self._buckets[bucket.key])

    @override
    def dump_bytecode(self, bucket: Bucket) -> None:
        self._buckets[bucket.key] = bucket.bytecode_to_string()


_BYTECODE = _MemoryBytecodeCache()


class ScriptEnvironment(Environment):
    """Jinja types `globals` by its defaults, which rejects data, so ours sit beside them."""

    script_globals: dict[str, object]

    @override
    def make_globals(self, d: MutableMapping[str, object] | None) -> ChainMap[str, object]:
        return ChainMap(super().make_globals(d), self.script_globals)


def script_env(application: str = APPLICATION_NAME) -> ScriptEnvironment:
    """Environment for every generated artifact (scripts and manifests).

    `application` is the identity the artifacts stamp; the version is the distribution's.
    """
    check_application_name(application)
    # No autoescape by design: these templates emit JavaScript and
    # markdown, not HTML. Interpolations are guarded individually
    # (tojson for values, comment_safe for comment text).
    env = ScriptEnvironment(
        loader=_ProcessLoader(TEMPLATES_DIR),
        bytecode_cache=_BYTECODE,
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["comment_safe"] = comment_safe
    env.filters["markdown_cell"] = markdown_cell
    env.filters["code_span"] = code_span
    env_globals: dict[str, object] = {}
    env.script_globals = env_globals

    # A GLOBAL rather than a per-render argument, because the fact belongs to
    # every script that reconciles a field and no generator should be able to
    # forget it. The eleven pairs were previously typed out by hand inside
    # `deploy/_field_reconcile.js.j2`, three languages away from the Python
    # that assigns them, and a missing entry there does not fail this build.
    # It throws in the operator's browser, mid-deploy, on a customer site.
    # `analysis/typemap.py` owns the pairing; `test_typemap.py` asserts the
    # rendered Map covers every FieldKind.
    env_globals["type_as_string_by_kind"] = TYPE_AS_STRING_PAIRS
    # The arity half of the same fact. A LookupMulti reads back the same
    # FieldTypeKind as a Lookup, so the number alone no longer names the type
    # and the deployer picks between these two maps on AllowMultipleValues.
    env_globals["multi_type_as_string_by_kind"] = MULTI_TYPE_AS_STRING_PAIRS
    env_globals["base_type_as_string"] = BASE_TYPE_AS_STRING_PAIRS
    # Rendered into both the probe that SELECTS these properties and the
    # reconciler that COMPARES them, which were two hand-kept copies of one
    # list.
    env_globals["derived_field_properties"] = DERIVED_FIELD_PROPERTIES
    env_globals["derived_field_property_kinds"] = DERIVED_FIELD_PROPERTY_KINDS
    # One list for the deploy's enrolment guard and the shared ensureUser, so the two cannot drift.
    env_globals["tenant_wide_claim_needles"] = TENANT_WIDE_CLAIM_NEEDLES
    # The identity every script and manifest stamps, chosen by the generator's caller.
    env_globals["application_name"] = application
    env_globals["command_name"] = COMMAND_NAME
    # Read per call rather than imported, so the test suite can pin the version its goldens record.
    env_globals["deployer_version"] = dbml_sharepoint.__version__
    return env
