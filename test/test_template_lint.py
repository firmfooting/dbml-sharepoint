# test/test_template_lint.py
"""Jinja lint gate for the whole template tree.

The templates are code and get a linter like code. Five rules, applied
to EVERY .j2 file (not just the ones generator tests happen to render):

1. Parses under the production Jinja environment (script_env). A syntax
   error in a rarely-exercised template must fail here, not on an
   operator's build.
2. Every literal {% include %} target exists; dynamic includes are
   allowed only in deploy.js.j2's phase loop.
3. Every template declared by the phases manifest exists.
4. Every template opens with a non-empty contract comment, verified via
   the SAME extraction the API docs use, so the template reference can
   never silently regress to "(No contract comment.)".
5. Every Jinja variable a template references is a context key the
   generators actually pass (or a name deploy.js.j2's phase loop
   provides). A typo like {{ relase.tag }} fails the allowlist; a REAL
   new context key is a deliberate one-line addition to KNOWN_CONTEXT, the
   same reviewed-decision pattern as the deploy.js golden.
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

# Context keys the generators pass to render() (union across jsgen,
# rollbackgen, assessgen, demogen, manifestgen and extractgen) plus the
# three names deploy.js.j2's phase loop provides to included phase bodies.
KNOWN_CONTEXT = {
    # every generator (provenance + identity)
    "site_url", "site_role", "release", "source_dbml", "source_mtime", "generated_at",
    # jsgen (deploy.js)
    "schema_json", "phases",
    # The assessment's inputs, imported from assessgen so deploy.js and
    # assess.js cannot disagree about the same site.
    "assess_requirements", "assess_targets_data", "assess_not_assessable",
    # The single named account `build --enterprise-reader` enrols read-only,
    # or None to emit no enrolment code at all.
    "enterprise_reader",
    "reader_excluded_lists",
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
    # dbml-sharepoint.env provenance, one rendered line: what was read (or
    # that nothing was), same wording in the manifest, index.md and the
    # deploy transcript's log() line.
    "env_file_line",
    # The sidecar lists the logging phase ensures on every deploy (both
    # None under --no-sidecars, which emits no logging phase at all), the
    # run-log stamp columns and change-log column bodies, each shared by an
    # ensure loop and the writer that fills them,
    # and the address plus column set of the CENTRAL deployment log, which
    # a deploy stamps but never creates. That list is what the
    # `deployment-log` family provisions.
    "sidecar_run_log_title", "sidecar_run_log_marker", "sidecar_run_log_fields",
    "sidecar_change_log_title", "sidecar_change_log_marker",
    "sidecar_change_fields", "deployment_log_list", "deployment_log_site",
    "deployment_log_columns", "deployment_log_row_prefix",
    # extractgen (extract.js). `deployer_version` is bare here rather than
    # `release.deployer_version`: extract.js runs before a release.yaml
    # exists, so there is no release object to hang it off.
    "list_paths", "live_format", "download_name", "deployer_version",
    # maintaingen (protection.js, columns.js): one list, named by the
    # operator from the address bar, and no release object for the same
    # reason extract.js has none. BOTH halves of that URL are passed:
    # `list_path` is what the scripts resolve the list by, `list_title` is
    # the slug, which names the output folder and stops being the list's
    # title the moment the list is renamed in place.
    "list_title", "list_path", "marker_prefix",
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
                    f"{rel}: dynamic include. Only deploy.js.j2's phase loop may do that",
                )
    assert not failures, "\n".join(failures)


def test_phase_manifest_templates_exist() -> None:
    for _group_name, steps in DEPLOY_GROUPS:
        for phase_step in steps:
            assert (TEMPLATES_DIR / phase_step.template).is_file(), (
                f"phases manifest declares missing template {phase_step.template!r}"
            )


def _load_generate_api() -> ModuleType:
    """Import the API-docs generator so rule 4 uses ITS extraction,
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
    by another template, or declared by the phases manifest. Anything
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

    Without this the promise in generate_api.py's own docstring ("docs
    drift shows up as a git diff") is unenforced: forgetting to run it is
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
        "generated API docs are stale. Regenerate with:\n"
        "  uv run python website/scripts/generate_api.py"
    )


# === The security model's endpoint inventory ================================

SECURITY_MODEL = REPO_ROOT / "website" / "docs" / "concepts" / "security-model.md"

# Every URL-building call site in the template tree. A suffix is either a
# literal or a template literal opening with a `${name}` this file resolves
# below; anything else is unresolvable and fails rather than passing quietly.
_URL_CALL = re.compile(r"""(?:apiUrl|probeGet)\(\s*[`'"]([^`'"]+)""")
_PATH_CONST = re.compile(r"""const\s+(\w*[Pp]ath)\s*=\s*[`'"]([^`'"$]+)""")
_LEADING_VAR = re.compile(r"^\$\{(\w+)\}")
# The documented families, read out of the doc's own table.
_DOCUMENTED = re.compile(r"`/_api/([^`]+)`")


def _path_consts() -> dict[str, str]:
    """A backtick-quoted `const listPath = web/lists/...` declaration becomes
    {"listPath": "web/lists/..."}.

    One level of indirection is all the templates use, and all this resolves.
    A second level would show up as an unresolvable suffix below, which fails.
    """
    found: dict[str, str] = {}
    for rel in ALL_TEMPLATES:
        text = (TEMPLATES_DIR / rel).read_text(encoding="utf-8")
        for name, value in _PATH_CONST.findall(text):
            found[name] = value
    return found


def _family(suffix: str, consts: dict[str, str], where: str) -> str:
    """The `/_api/<family>` one call site reaches."""
    var = _LEADING_VAR.match(suffix)
    if var:
        resolved = consts.get(var.group(1))
        assert resolved is not None, (
            f"{where}: apiUrl() opens with ${{{var.group(1)}}}, which this test "
            f"cannot resolve to a path. Declare it as `const {var.group(1)} = "
            f"`web/...`` like the others, or teach _path_consts about it. An "
            f"unresolvable call site is an undocumented endpoint."
        )
        suffix = _LEADING_VAR.sub(resolved, suffix)
    return re.split(r"[/?(]", suffix.lstrip("/"), maxsplit=1)[0]


def _used_families() -> dict[str, set[str]]:
    """{family: {templates that reach it}}."""
    consts = _path_consts()
    used: dict[str, set[str]] = {}
    for rel in ALL_TEMPLATES:
        text = (TEMPLATES_DIR / rel).read_text(encoding="utf-8")
        for suffix in _URL_CALL.findall(text):
            family = _family(suffix, consts, f"{rel} ({suffix!r})")
            if family:
                used.setdefault(family, set()).add(rel)
    return used


def test_one_helper_builds_every_api_url() -> None:
    """The security model tells a reviewer that every request goes through one
    site-guarded helper. If a template ever writes `_api/` itself, that claim
    is false and the endpoint inventory below stops seeing everything.

    _cross_web.js.j2 is the one exception, pinned line by line: it IS the
    sanctioned cross-site builder, so its own two template literals are the
    definitions the rest of the claim rests on. The allowlist is exact
    strings, so adding a second offender means editing this list on purpose.
    """
    allowed = {
        # The cross-web helper itself: it IS the sanctioned builder for the
        # one cross-site surface (the central deployment log). Two lines,
        # because contextinfo sits under `_api/` rather than `_api/web/`
        # and the digest must be the TARGET web's own.
        "_cross_web.js.j2": {
            "`${TENANT_ROOT}/sites/${odataName(site)}/_api/web/${suffix}`;",
            "`${TENANT_ROOT}/sites/${odataName(site)}/_api/contextinfo`;",
        },
    }
    offenders = {}
    for rel in ALL_TEMPLATES:
        if rel == "_site_guard.js.j2":
            continue
        text = (TEMPLATES_DIR / rel).read_text(encoding="utf-8")
        hits = {
            line.strip()[:120]
            for line in text.splitlines()
            if "_api/" in line
        }
        excess = hits - allowed.get(rel, set())
        if excess:
            offenders[rel] = sorted(excess)
    assert not offenders, (
        f"{sorted(offenders)} build an '_api/' URL without apiUrl()/"
        f"crossWebApi(). Route it through the helpers in _site_guard.js.j2, "
        f"so the site guard applies and "
        f"website/docs/concepts/security-model.md stays true."
    )


def test_every_endpoint_family_is_in_the_security_model() -> None:
    """The security model's endpoint table is what a tenant reviewer reads
    instead of the scripts. A hand-maintained inventory drifts. This repo has
    already shipped one stale entry (a GetSiteScriptFromWeb extraction that no
    longer existed), so the table is checked against the templates.
    """
    documented = SECURITY_MODEL.read_text(encoding="utf-8")
    undocumented = sorted(
        f"{family} (used by {', '.join(sorted(where))})"
        for family, where in _used_families().items()
        if f"/_api/{family}" not in documented
    )
    assert not undocumented, (
        "endpoint families reached by the templates but absent from the "
        f"security model's table: {undocumented}. Add a row to "
        "website/docs/concepts/security-model.md saying what it is for."
    )


def test_the_security_model_documents_no_unused_endpoint_family() -> None:
    """The mirror. A row describing an endpoint nothing calls any more
    overstates the script's reach to the reviewer deciding on it."""
    used = set(_used_families())
    stale = []
    for raw in _DOCUMENTED.findall(SECURITY_MODEL.read_text(encoding="utf-8")):
        documented = re.sub(r"\(.*", "", raw).removesuffix("/...").strip("/")
        if not any(
            documented == family
            or documented.startswith(f"{family}/")
            or family.startswith(f"{documented}/")
            for family in used
        ):
            stale.append(documented)
    assert not stale, (
        f"the security model documents /_api/ families nothing reaches: "
        f"{sorted(set(stale))}. Remove the row. An endpoint table that "
        f"overstates the surface is as misleading as one that understates it."
    )
