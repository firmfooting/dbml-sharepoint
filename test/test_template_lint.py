# test/test_template_lint.py
"""Jinja lint gate for the whole template tree.

The templates are code and get a linter like code. Five rules, applied
to EVERY .j2 file (not just the ones generator tests happen to render):

1. Parses under the production Jinja environment (script_env) — a syntax
   error in a rarely-exercised template must fail here, not on an
   operator's build.
2. Every literal {% include %} target exists; dynamic includes are
   allowed only in deploy.js.j2's phase loop.
3. Every template declared by the phases manifest exists.
4. Every template opens with a non-empty contract comment — verified via
   the SAME extraction the API docs use, so the template reference can
   never silently regress to "(No contract comment.)".
5. Every Jinja variable a template references is a context key the
   generators actually pass (or a name deploy.js.j2's phase loop
   provides). A typo like {{ relase.tag }} fails the allowlist; a REAL
   new context key is a deliberate one-line addition to KNOWN_CONTEXT —
   the same reviewed-decision pattern as the deploy.js golden.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
from jinja2 import Environment, TemplateSyntaxError, meta, nodes

from dbml_sharepoint.analysis.phases import DEPLOY_GROUPS
from dbml_sharepoint.model.parser import Table, TableIndex
from dbml_sharepoint.templating import TEMPLATES_DIR, script_env

SRC_DIR = TEMPLATES_DIR.parent
REPO_ROOT = TEMPLATES_DIR.parents[2]

ALL_TEMPLATES = sorted(
    p.relative_to(TEMPLATES_DIR).as_posix() for p in TEMPLATES_DIR.rglob("*.j2")
)

# Context keys the generators pass to render() — union across jsgen,
# rollbackgen, assessgen, demogen and manifestgen — plus the three names
# deploy.js.j2's phase loop provides to included phase bodies.
KNOWN_CONTEXT = {
    # every generator (provenance + identity)
    "site_url", "site_role", "release", "source_dbml", "source_mtime", "generated_at",
    # jsgen (deploy.js)
    "schema_json", "phases",
    # The marker distinguishing "clear this value" from "not managed here".
    # Passed in rather than hard-coded on both sides so the two can never
    # disagree about what unmanaged looks like.
    "unmanaged_sentinel",
    # demogen
    "demo_plan", "demo_title_prefix",
    # rollbackgen
    "target_lists",
    # assessgen
    "targets", "requirements", "not_assessable",
    # manifestgen
    "phase_num", "counts", "findings", "polymorphic", "lists", "phase2",
    "indexed", "views", "formatted_columns", "form_formatting", "retention",
    "retired_columns",
    "form_visibility", "column_validation", "reconcile_modes", "list_validation",
    "prefix", "seed_items", "extra_sections", "extra_warnings",
    # provided by deploy.js.j2's phase loop to included phase bodies
    "phase", "step", "group",
}


def _source(rel: str) -> str:
    return (TEMPLATES_DIR / rel).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def env() -> Environment:
    return script_env()


@pytest.mark.parametrize("rel", ALL_TEMPLATES)
def test_template_parses_under_production_environment(rel: str, env: Environment) -> None:
    try:
        env.parse(_source(rel), name=rel)
    except TemplateSyntaxError as err:  # pragma: no cover - the message IS the value
        pytest.fail(f"{rel}:{err.lineno}: {err.message}")


def test_every_literal_include_target_exists(env: Environment) -> None:
    failures: list[str] = []
    for rel in ALL_TEMPLATES:
        tree = env.parse(_source(rel), name=rel)
        for node in tree.find_all(nodes.Include):
            target = node.template
            if isinstance(target, nodes.Const):
                if not (TEMPLATES_DIR / str(target.value)).is_file():
                    failures.append(f"{rel}: include target {target.value!r} does not exist")
            elif rel != "deploy.js.j2":
                failures.append(
                    f"{rel}: dynamic include — only deploy.js.j2's phase loop may do that",
                )
    assert not failures, "\n".join(failures)


def test_phase_manifest_templates_exist() -> None:
    for _group_name, steps in DEPLOY_GROUPS:
        for phase_step in steps:
            assert (TEMPLATES_DIR / phase_step.template).is_file(), (
                f"phases manifest declares missing template {phase_step.template!r}"
            )


def _load_generate_api() -> ModuleType:
    """Import the API-docs generator so rule 4 uses ITS extraction —
    one source of truth for what counts as a contract comment."""
    path = REPO_ROOT / "website" / "scripts" / "generate_api.py"
    spec = importlib.util.spec_from_file_location("generate_api", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_api"] = module
    spec.loader.exec_module(module)
    return module


def test_every_template_has_a_contract_comment() -> None:
    generate_api = _load_generate_api()
    missing = [
        rel
        for rel in ALL_TEMPLATES
        if not generate_api.template_contract(TEMPLATES_DIR / rel)
    ]
    assert not missing, (
        "templates without a contract comment (the API docs extract these "
        f"verbatim): {missing}"
    )


def test_generated_dataclass_docs_preserve_constructor_semantics() -> None:
    generate_api = _load_generate_api()
    index_docs = generate_api.render_class("TableIndex", TableIndex)
    table_docs = generate_api.render_class("Table", Table)
    assert "@dataclass(frozen=True)" in index_docs
    assert "field(default_factory=list)" in table_docs
    assert "= list()" not in table_docs


def test_template_variables_are_known_context(env: Environment) -> None:
    failures: list[str] = []
    for rel in ALL_TEMPLATES:
        tree = env.parse(_source(rel), name=rel)
        unknown = meta.find_undeclared_variables(tree) - KNOWN_CONTEXT
        if unknown:
            failures.append(f"{rel}: unknown variable(s) {sorted(unknown)}")
    assert not failures, (
        "either a typo in the template or a new generator context key "
        "that must be added to KNOWN_CONTEXT deliberately:\n" + "\n".join(failures)
    )


def test_no_orphan_templates(env: Environment) -> None:
    """Every template is an entry point (named in a generator), included
    by another template, or declared by the phases manifest — anything
    else is dead code that generator tests would never catch rotting."""
    referenced: set[str] = set()
    for py in sorted(SRC_DIR.rglob("*.py")):
        referenced.update(
            re.findall(r'"([\w./-]+\.j2)"', py.read_text(encoding="utf-8")),
        )
    for rel in ALL_TEMPLATES:
        for node in env.parse(_source(rel), name=rel).find_all(nodes.Include):
            if isinstance(node.template, nodes.Const):
                referenced.add(str(node.template.value))
    referenced.update(
        phase_step.template for _g, steps in DEPLOY_GROUPS for phase_step in steps
    )
    orphans = sorted(set(ALL_TEMPLATES) - referenced)
    assert not orphans, f"templates nothing references: {orphans}"


def test_generated_api_docs_are_current(tmp_path: Path) -> None:
    """The generator is deterministic by design, so a committed page that
    differs from a fresh run means someone changed the code and did not
    regenerate.

    Without this the promise in generate_api.py's own docstring — "docs
    drift shows up as a git diff" — is unenforced: forgetting to run it is
    completely silent, which is how a reference page starts describing code
    that no longer exists.
    """
    generate_api = _load_generate_api()
    committed: Path = generate_api.OUT_DIR
    try:
        generate_api.OUT_DIR = tmp_path  # type: ignore[attr-defined]
        generate_api.write_all()
    finally:
        generate_api.OUT_DIR = committed  # type: ignore[attr-defined]

    def pages(root: Path) -> dict[Path, str]:
        return {q.relative_to(root): q.read_text(encoding="utf-8") for q in root.rglob("*.md")}

    fresh = pages(tmp_path)
    have = pages(committed)
    assert have == fresh, (
        "generated API docs are stale — regenerate with:\n"
        "  uv run python website/scripts/generate_api.py"
    )
