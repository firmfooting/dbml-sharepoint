# website/scripts/generate_api.py
"""Generate the API reference pages under website/docs/api/.

Stdlib only. Two sources of truth, extracted rather than transcribed:

- Python: each module's own top-level definitions (found via ast, so
  re-exports never masquerade as local API), paired with the imported
  module for signatures and docstrings via inspect. Underscore-prefixed
  names are module-private and excluded. The public API is exactly the
  unprefixed surface.
- Templates: every .j2 file's leading `{# ... #}` contract comment, plus
  the deploy-phase manifest (phases.py) so phase templates carry their
  group/number/name.

Output is deterministic (no timestamps): rerunning on an unchanged tree
produces byte-identical pages, so docs drift shows up as a git diff.

Run from the repository root:

    uv run python website/scripts/generate_api.py
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import re
import shutil
import sys
from pathlib import Path, PurePath

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
PACKAGE_DIR = SRC / "dbml_sharepoint"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
OUT_DIR = REPO_ROOT / "website" / "docs" / "api"

sys.path.insert(0, str(SRC))

# Dotted module paths mirror the package layout (model/, analysis/,
# generators/ layer packages; the packaging spine at the root); sidebar
# order follows this list.
MODULES: list[tuple[str, str]] = [
    ("model.parser", "parse DBML into the in-memory schema"),
    ("model.mapping_loader", "load mapping.yaml and referenced config"),
    ("model.mapping_types", "the mapping vocabulary an extension hook receives"),
    ("model.release", "load release.yaml provenance"),
    ("model.env_file", "parse dbml-sharepoint.env build defaults"),
    ("model.conditions", "the shared condition grammar's types and parser"),
    ("analysis.findings", "what a finding is: code, severity, section, location"),
    ("analysis.validator", "fail-closed build-time rules"),
    ("analysis.rendered_columns", "which columns a provisioned list actually has"),
    ("analysis.column_refs", "column names written inside a formula or formatter"),
    ("analysis.limits", "the SharePoint ceilings, each named once"),
    ("analysis.ordering", "dependency ordering and site filtering"),
    ("analysis.typemap", "DBML types to SharePoint field descriptors"),
    ("analysis.immutable_shape", "the properties a deploy refuses to change"),
    ("analysis.phases", "the deploy-phase manifest"),
    ("analysis.permissions", "SP base-permission bitmask helpers"),
    ("analysis.styles", "the fleet style standard"),
    ("analysis.conditions", "condition normalisation, validation and rendering"),
    ("analysis.condition_description", "human-readable condition prose"),
    ("analysis.demo_marker", "the demo-row Title-prefix contract"),
    ("analysis.forms", "composing declared form visibility"),
    ("generators.jsgen", "deploy.js"),
    ("generators.rollbackgen", "rollback.js"),
    ("generators.assessgen", "assess.js and assess-manifest.md"),
    ("generators.demogen", "demo-data.js"),
    ("generators.manifestgen", "deploy-manifest.md"),
    ("generators.reportgen", "Power Query / SQL reporting pack"),
    ("bundle", "Packaging: the one emission sequence"),
    ("templating", "Packaging: the shared Jinja environment"),
    ("extension", "Packaging: the extension protocol"),
    ("cli", "Packaging: the command-line interface"),
    ("catalogue", "Packaging: the shipped solution templates, as data"),
    ("wizard", "Packaging: the interactive template wizard"),
]

# Sub-package sidebar categories, in layout order.
LAYERS: dict[str, str] = {
    "model": "model: inputs to typed objects",
    "analysis": "analysis: rules and projections",
    "generators": "generators: one artifact family each",
}

_CODE_SPAN = re.compile(r"(`[^`]*`)")


def write_page(path: Path, text: str) -> None:
    """Write one generated page: UTF-8, LF, on every platform.

    `.gitattributes` declares `* text=auto eol=lf`, so this repository's
    working tree is LF and the committed blobs are LF. Writing in text mode
    on Windows produced CRLF, which meant every regeneration reported all
    27 pages as modified when only one had really changed -- drift that is
    not real, that has to be filtered with `git diff --ignore-cr-at-eol`
    before it can be reviewed, and that makes a genuine change easy to
    revert by accident while cleaning up the noise.

    The module docstring promises "rerunning on an unchanged tree produces
    byte-identical pages". On Windows that was only true if you ignored the
    bytes at the end of every line.
    """
    path.write_text(text, encoding="utf-8", newline="\n")


def md_escape(text: str) -> str:
    """Escape prose for CommonMark, leaving code spans untouched."""
    parts = _CODE_SPAN.split(text)
    for i, part in enumerate(parts):
        if not part.startswith("`"):
            parts[i] = part.replace("&", "&amp;").replace("<", "&lt;")
    return "".join(parts)


def docstring_block(obj: object) -> str:
    doc = inspect.getdoc(obj)
    return md_escape(doc) + "\n\n" if doc else ""


def public_definitions(module_name: str) -> list[tuple[str, str]]:
    """Ordered (kind, name) of top-level public defs actually in the module."""
    source_path = PACKAGE_DIR / (module_name.replace(".", "/") + ".py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    defs: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                defs.append(("function", node.name))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                defs.append(("class", node.name))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                # Public constants only: lowercase top-level assignments
                # are wiring (e.g. typer apps), not API.
                if (
                    isinstance(target, ast.Name)
                    and target.id.isupper()
                    and not target.id.startswith("_")
                ):
                    defs.append(("constant", target.id))
    return defs


class _Elided:
    """Stands in for defaults whose repr is nondeterministic noise."""

    def __repr__(self) -> str:
        return "..."


_ELIDED = _Elided()


class _Literal:
    """Stands in for a default that must render the same on every OS."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __repr__(self) -> str:
        return self._text


def _portable_default(value: object) -> object:
    """Replace a default whose repr is platform- or machine-specific.

    Two kinds, both of which have already broken the deterministic-output
    contract:

    - Instance defaults such as typer's OptionInfo repr as
      '<... object at 0x...>', which is machine-specific.
    - `pathlib` defaults repr as their CONCRETE class, so
      `Path("./build")` is `WindowsPath('build')` on Windows and
      `PosixPath('build')` on Linux. That one is worse than noise: the
      page generates cleanly on the author's machine and fails
      `test_generated_api_docs_are_current` on the other OS in CI, which
      reads as a broken test rather than as a portability bug.
    """
    if isinstance(value, PurePath):
        return _Literal(f"Path({value.as_posix()!r})")
    if " object at 0x" in repr(value):
        return _ELIDED
    return value


def clean_signature(obj: object) -> str:
    """str(signature), with non-portable default reprs normalised.

    See `_portable_default` for what gets replaced and why.
    """
    sig = inspect.signature(obj)  # type: ignore[arg-type]
    params = [
        p if p.default is inspect.Parameter.empty
        else p.replace(default=_portable_default(p.default))
        for p in sig.parameters.values()
    ]
    return str(sig.replace(parameters=params))


def render_function(name: str, obj: object) -> str:
    try:
        sig = clean_signature(obj)
    except (TypeError, ValueError):
        sig = "(...)"
    out = f"### `{name}`\n\n```python\ndef {name}{sig}\n```\n\n"
    return out + docstring_block(obj)


def render_class(name: str, obj: type) -> str:
    out = f"### `{name}`\n\n"
    if dataclasses.is_dataclass(obj):
        params = obj.__dataclass_params__  # type: ignore[attr-defined]
        decorator = "@dataclass(frozen=True)" if params.frozen else "@dataclass"
        lines = [f"{decorator}\nclass {name}:"]
        for f in dataclasses.fields(obj):
            default = ""
            if f.default is not dataclasses.MISSING:
                default = f" = {f.default!r}"
            elif f.default_factory is not dataclasses.MISSING:
                factory = getattr(f.default_factory, "__name__", "...")
                default = f" = field(default_factory={factory})"
            lines.append(f"    {f.name}: {_type_str(f.type)}{default}")
        out += "```python\n" + "\n".join(lines) + "\n```\n\n"
    out += docstring_block(obj)
    for method_name, method in inspect.getmembers(obj, inspect.isfunction):
        if method_name.startswith("_") or method.__qualname__.split(".")[0] != name:
            continue
        try:
            sig = str(inspect.signature(method))
        except (TypeError, ValueError):
            sig = "(...)"
        out += f"#### `{name}.{method_name}`\n\n```python\ndef {method_name}{sig}\n```\n\n"
        out += docstring_block(method)
    return out


def _type_str(annotation: object) -> str:
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)


def stable_repr(obj: object) -> str:
    """repr with set iteration order removed, at any depth.

    Sorting only top-level sets was not enough: a dict whose VALUES are
    frozensets fell through to plain repr, so the page differed between
    processes and the docs looked stale on every other run.
    """
    if isinstance(obj, (set, frozenset)):
        # An empty set has no brace form: repr(set()) is "set()", and
        # "set({})" is not merely ugly, it evaluates to an empty DICT.
        # Published docs showing it would teach the wrong literal.
        if not obj:
            return f"{type(obj).__name__}()"
        inner = ", ".join(sorted(stable_repr(x) for x in obj))
        return f"{type(obj).__name__}({{{inner}}})"
    if isinstance(obj, dict):
        items = ", ".join(
            f"{stable_repr(k)}: {stable_repr(v)}" for k, v in obj.items()
        )
        return f"{{{items}}}"
    if isinstance(obj, tuple):
        inner = ", ".join(stable_repr(x) for x in obj)
        return "(" + inner + ("," if len(obj) == 1 else "") + ")"
    if isinstance(obj, list):
        return "[" + ", ".join(stable_repr(x) for x in obj) + "]"
    return repr(obj)


def render_constant(name: str, obj: object) -> str:
    if isinstance(obj, PurePath):
        if not obj.is_absolute():
            # Already portable and already the whole value. The absolute
            # handling below used to catch these too, and its .name
            # fallback silently published a DIFFERENT path: a relative
            # `10-design/schema.dbml` rendered as `schema.dbml`, which a
            # reader building a path from the docs would get wrong.
            value = f'Path("{obj.as_posix()}")'
        else:
            # Machine-absolute paths are noise (and leak the build
            # machine's layout); render package-relative.
            try:
                value = f'Path("{obj.relative_to(SRC).as_posix()}")'
            except ValueError:
                value = f'Path("{obj.name}")'
    else:
        value = stable_repr(obj)
    if len(value) > 200:
        value = value[:200] + "…"
    return f"### `{name}`\n\n```python\n{name} = {value}\n```\n\n"


def generate_python_pages() -> None:
    out_dir = OUT_DIR / "python"
    # Self-cleaning: a module that moves or disappears must not leave a
    # stale page behind (same rule bundle emission applies to artifacts).
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    write_page(
        out_dir / "_category_.json",
        '{\n  "label": "Python modules",\n  "position": 2\n}\n',
    )
    for layer_position, (layer, label) in enumerate(LAYERS.items(), start=1):
        (out_dir / layer).mkdir()
        write_page(
            out_dir / layer / "_category_.json",
            f'{{\n  "label": "{label}",\n  "position": {layer_position}\n}}\n',
        )
    for position, (module_name, role) in enumerate(MODULES, start=1):
        module = importlib.import_module(f"dbml_sharepoint.{module_name}")
        page = (
            f"---\ntitle: {module_name.rsplit('.', 1)[-1]}\n"
            f"sidebar_position: {position}\n---\n\n"
            f"# `dbml_sharepoint.{module_name}`\n\n"
            f"*{md_escape(role)}*\n\n"
        )
        module_doc = inspect.getdoc(module)
        if module_doc:
            page += md_escape(module_doc) + "\n\n"
        for kind, name in public_definitions(module_name):
            obj = getattr(module, name)
            if kind == "function":
                page += render_function(name, obj)
            elif kind == "class":
                page += render_class(name, obj)
            else:
                page += render_constant(name, obj)
        page_path = out_dir / (module_name.replace(".", "/") + ".md")
        write_page(page_path, page)


_CONTRACT_COMMENT = re.compile(r"^\{#(.*?)#\}", re.DOTALL)
_INCLUDE = re.compile(r"""\{%\s*include\s+["']([^"']+)["']\s*%\}""")
_JS_BLOCK_COMMENT = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)
_JINJA_TAG = re.compile(r"\{[%{].*?[%}]\}")


def template_contract(path: Path) -> str:
    """The template's leading contract comment, as one paragraph.

    Preference order: the Jinja `{# ... #}` comment (minus the repo-path
    line), else the script's opening `/** ... */` doc comment, else the
    leading run of `// ...` lines (minus `=== banner ===` lines). Every
    template documents itself one of these three ways.
    """
    text = path.read_text(encoding="utf-8")
    while (match := _CONTRACT_COMMENT.match(text)) is not None:
        lines = [line.strip() for line in match.group(1).strip().splitlines()]
        if lines and ("templates/" in lines[0] and " " not in lines[0]):
            lines = lines[1:]
        if any(lines):
            return md_escape(" ".join(line for line in lines if line))
        text = text[match.end():].lstrip("\n")

    block = _JS_BLOCK_COMMENT.match(text.lstrip())
    if block:
        from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX

        # Most Jinja tags are implementation detail and disappear from the
        # contract page. This marker is operator-facing content inside the
        # contract itself, so resolve it from the same owner as the template.
        body = block.group(1).replace("{{ demo_title_prefix }}", DEMO_TITLE_PREFIX)
        body = _JINJA_TAG.sub("", body)
        lines = [line.strip().lstrip("*").strip() for line in body.splitlines()]
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            if line:
                current.append(line)
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        if current:
            paragraphs.append(" ".join(current))
        return md_escape("\n\n".join(paragraphs))

    slash_lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("//"):
            content = stripped.lstrip("/").strip()
            if not (content.startswith("===") and content.endswith("===")):
                slash_lines.append(content)
        elif (stripped and slash_lines) or stripped:
            break
    return md_escape(" ".join(line for line in slash_lines if line))


def generate_templates_page() -> None:
    from dbml_sharepoint.analysis.phases import phases_context

    includers: dict[str, list[str]] = {}
    all_templates = sorted(TEMPLATES_DIR.rglob("*.j2"))
    for path in all_templates:
        rel = path.relative_to(TEMPLATES_DIR).as_posix()
        for included in _INCLUDE.findall(path.read_text(encoding="utf-8")):
            includers.setdefault(included, []).append(rel)

    phase_by_template: dict[str, str] = {}
    for group in phases_context():
        for step in group["steps"]:
            phase_by_template[step["template"]] = (
                f"Phase {step['number']} ({group['name']}): {step['name']}"
            )

    page = (
        "---\ntitle: Templates\nsidebar_position: 3\n---\n\n"
        "# Template reference\n\n"
        "Every generated script is rendered from these Jinja2 templates. "
        "Each template opens with a contract comment stating what it does "
        "and what it expects, reproduced here verbatim (extracted, not "
        "transcribed). Underscore-prefixed templates are shared partials "
        "or phase bodies included by the entry-point scripts.\n\n"
    )

    def section(title: str, paths: list[Path]) -> str:
        out = f"## {title}\n\n"
        for path in paths:
            rel = path.relative_to(TEMPLATES_DIR).as_posix()
            out += f"### `{rel}`\n\n"
            if rel in phase_by_template:
                out += f"*{phase_by_template[rel]}*\n\n"
            used_by = includers.get(rel) or includers.get(path.name)
            if used_by:
                out += "Included by: " + ", ".join(f"`{u}`" for u in sorted(set(used_by))) + "\n\n"
            contract = template_contract(path)
            out += (contract + "\n\n") if contract else "*(No contract comment.)*\n\n"
        return out

    scripts = [p for p in all_templates if p.parent == TEMPLATES_DIR and not p.name.startswith("_")]
    partials = [p for p in all_templates if p.parent == TEMPLATES_DIR and p.name.startswith("_")]
    phase_bodies = [p for p in all_templates if p.parent != TEMPLATES_DIR]
    page += section("Entry-point scripts", scripts)
    page += section("Shared partials", partials)
    page += section("deploy.js phase bodies", phase_bodies)
    write_page(OUT_DIR / "templates.md", page)



def generate_conditions_page() -> None:
    """The condition grammar reference, EXECUTED rather than transcribed.

    Every cell is either a constant read from the module or the actual
    output of a renderer run on a sample condition. Nothing is typed by
    hand, so no example can be wrong: change a renderer and the page
    rewrites itself, and an operator a target cannot express prints as
    "not supported" because the renderer raised.
    """
    conditions = importlib.import_module("dbml_sharepoint.analysis.conditions")
    model = importlib.import_module("dbml_sharepoint.model.conditions")
    parse = model.parse_condition

    # `Events` is multi-value, and it is in this table so the two membership
    # operators print their real renderings beside the scalar ones -- and so
    # the two formula targets print their refusal, which is the fact an author
    # most needs from this page.
    types = {
        "Status": "nvarchar", "Count": "number", "Owner": "person", "Note": "nvarchar",
        "Events": "audit_event[]",
    }
    samples: list[tuple[str, dict[str, object]]] = [
        ("eq", {"field": "Status", "op": "eq", "value": "Open"}),
        ("neq", {"field": "Status", "op": "neq", "value": "Open"}),
        ("lt", {"field": "Count", "op": "lt", "value": 5}),
        ("geq", {"field": "Count", "op": "geq", "value": 5}),
        ("is_null", {"field": "Note", "op": "is_null"}),
        ("is_not_null", {"field": "Note", "op": "is_not_null"}),
        ("in", {"field": "Status", "op": "in", "value": ["A", "B"]}),
        ("not_in", {"field": "Status", "op": "not_in", "value": ["A", "B"]}),
        ("contains", {"field": "Note", "op": "contains", "value": "x"}),
        ("begins_with", {"field": "Note", "op": "begins_with", "value": "ab"}),
        ("includes", {"field": "Events", "op": "includes", "value": "View"}),
        ("not_includes", {"field": "Events", "op": "not_includes", "value": "View"}),
        ("measure: length", {"field": "Note", "measure": "length", "op": "gt", "value": 10}),
        ("property (person)", {"field": "Owner", "property": "title", "op": "neq", "value": ""}),
    ]
    renderers = [
        ("CAML", conditions.to_caml),
        ("Expression", conditions.to_expression),
        ("Validation", conditions.to_validation),
    ]

    lines: list[str] = [
        "---", "title: Condition grammar", "sidebar_position: 4", "---", "",
        "# Condition grammar", "",
        ":::note Generated",
        "Every rendering below is produced by running the renderer, not written",
        "by hand; see `website/scripts/generate_api.py`.",
        ":::", "",
        docstring_block(model), "",
        "## Operators", "",
        ("`views[].where` renders to CAML, `form_visibility.when` to a"
        " list-formatting expression, and `column_validation.when` /"
        " `list_validation.when` to a classic validation formula."), "",
        "| Declared | " + " | ".join(label for label, _ in renderers) + " |",
        "|---|---|---|---|",
    ]
    for label, raw in samples:
        condition = parse([raw], "sample")
        cells = []
        for _, render in renderers:
            try:
                cells.append("`" + render(condition, types) + "`")
            except ValueError as exc:
                reason = str(exc).split(": ", 1)[-1].split(" (target")[0]
                cells.append("_not supported: " + md_escape(reason) + "_")
        lines.append("| `" + label + "` | " + " | ".join(cells) + " |")

    # The heading is unconditional; the SENTENCE under it is not. An empty
    # set is the good state, and printing a bare header with nothing beneath
    # it reads as a truncated page rather than as "nothing is pending",
    # which is the opposite of the claim the emptiness is meant to make.
    lines += ["", "## Not yet verified", ""]
    if conditions.DISABLED_PENDING_PROBE:
        for target, ops in sorted(conditions.DISABLED_PENDING_PROBE.items()):
            listed = ", ".join("`" + op + "`" for op in sorted(ops))
            lines += [
                "On the **" + target + "** target these are refused until confirmed",
                "against a live tenant: " + listed + ". Plausible from documented syntax",
                "is not the same as observed, and this project has twice been wrong",
                "about expression syntax it had not run.", "",
            ]
    else:
        lines += [
            "Nothing is waiting on a probe that has been written and not run. That",
            "is what this section reports, and an empty one is the good state, so",
            "it says so rather than leaving a blank.", "",
            "It is not a claim that every operator was watched in a form. The four",
            "text operators were; the comparison and null tests rest on formulas",
            "harvested from a live tenant rather than on written syntax. Where a",
            "rendering is derived rather than observed, the source says so.", "",
        ]

    lines += ["## Operand accessors", "", "| Column kind | Required `property` |", "|---|---|"]
    for kind, accessors in sorted(conditions.PROPERTY_ACCESSORS.items()):
        listed = ", ".join("`" + a + "`" for a in sorted(accessors))
        lines.append("| " + kind + " | " + listed + " |")

    lines += [
        "", "## Bounds", "",
        "At most **" + str(conditions.MAX_DEPTH) + "** nested groups and **"
        + str(conditions.MAX_LEAVES) + "** conditions, counted after normalisation;",
        "negation expands each leaf and `in` expands to one condition per value.", "",
        "## Normalisation", "",
        docstring_block(conditions), "",
    ]
    write_page(OUT_DIR / "conditions.md", "\n".join(lines) + "\n")


def generate_index() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_page(
        OUT_DIR / "_category_.json",
        '{\n  "label": "API reference",\n  "position": 6\n}\n',
    )
    page = (
        "---\ntitle: Overview\nsidebar_position: 1\n---\n\n"
        "# API reference\n\n"
        "Generated by `website/scripts/generate_api.py`; do not edit these "
        "pages by hand; rerun the script after changing the source. "
        "Signatures and docstrings come from the modules themselves; the "
        "template contracts come from each template's leading comment.\n\n"
        "| Module | Role |\n|---|---|\n"
    )
    for module_name, role in MODULES:
        page_ref = "python/" + module_name.replace(".", "/") + ".md"
        page += f"| [`{module_name}`]({page_ref}) | {md_escape(role)} |\n"
    page += "\nTemplates: see the [template reference](templates.md).\n"
    write_page(OUT_DIR / "index.md", page)


def write_all() -> None:
    """Every page in one call, so a staleness test can regenerate and diff
    without duplicating the entry point's knowledge of what exists."""
    generate_index()
    generate_python_pages()
    generate_templates_page()
    generate_conditions_page()


if __name__ == "__main__":
    write_all()
    count = len(list((OUT_DIR / "python").rglob("*.md"))) + 2
    print(f"Generated {count} API reference page(s) under {OUT_DIR}")
