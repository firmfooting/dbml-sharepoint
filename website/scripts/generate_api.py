# website/scripts/generate_api.py
"""Generate the API reference pages under website/docs/api/.

Stdlib only. Two sources of truth, extracted rather than transcribed:

- Python: each module's own top-level definitions (found via ast, so
  re-exports never masquerade as local API), paired with the imported
  module for signatures and docstrings via inspect. Underscore-prefixed
  names are module-private and excluded — the public API is exactly the
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
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
PACKAGE_DIR = SRC / "dbml_sharepoint"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
OUT_DIR = REPO_ROOT / "website" / "docs" / "api"

sys.path.insert(0, str(SRC))

# Layer order mirrors the README repository map; sidebar order follows it.
MODULES: list[tuple[str, str]] = [
    ("parser", "Model — parse DBML into the in-memory schema"),
    ("mapping_loader", "Model — load mapping.yaml and referenced config"),
    ("release", "Model — load release.yaml provenance"),
    ("validator", "Analysis — fail-closed build-time rules"),
    ("ordering", "Analysis — dependency ordering and site filtering"),
    ("typemap", "Analysis — DBML types to SharePoint field descriptors"),
    ("phases", "Analysis — the deploy-phase manifest"),
    ("permissions", "Analysis — SP base-permission bitmask helpers"),
    ("styles", "Analysis — the fleet style standard"),
    ("jsgen", "Generator — deploy.js"),
    ("rollbackgen", "Generator — rollback.js"),
    ("assessgen", "Generator — assess.js and assess-manifest.md"),
    ("demogen", "Generator — demo-data.js"),
    ("manifestgen", "Generator — deploy-manifest.md"),
    ("reportgen", "Generator — Power Query / SQL reporting pack"),
    ("bundle", "Packaging — the one emission sequence"),
    ("templating", "Packaging — the shared Jinja environment"),
    ("extension", "Packaging — the extension protocol"),
    ("cli", "Packaging — the command-line interface"),
]

_CODE_SPAN = re.compile(r"(`[^`]*`)")


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
    source = (PACKAGE_DIR / f"{module_name}.py").read_text(encoding="utf-8")
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


def clean_signature(obj: object) -> str:
    """str(signature), with address-bearing default reprs elided.

    Instance defaults (e.g. typer OptionInfo) repr as
    '<... object at 0x...>' — machine-specific, so they would defeat
    the deterministic-output contract."""
    sig = inspect.signature(obj)  # type: ignore[arg-type]
    params = [
        p.replace(default=_ELIDED)
        if p.default is not inspect.Parameter.empty
        and " object at 0x" in repr(p.default)
        else p
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
        lines = [f"@dataclass\nclass {name}:"]
        for f in dataclasses.fields(obj):
            default = ""
            if f.default is not dataclasses.MISSING:
                default = f" = {f.default!r}"
            elif f.default_factory is not dataclasses.MISSING:
                default = f" = {getattr(f.default_factory, '__name__', '...')}()"
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


def render_constant(name: str, obj: object) -> str:
    if isinstance(obj, Path):
        # Machine-absolute paths are noise (and leak the build machine's
        # layout); render package-relative.
        try:
            value = f'Path("{obj.relative_to(SRC).as_posix()}")'
        except ValueError:
            value = f'Path("{obj.name}")'
    elif isinstance(obj, (set, frozenset)):
        # Set iteration order is nondeterministic; sort for stable diffs.
        inner = ", ".join(sorted(repr(x) for x in obj))
        value = f"{type(obj).__name__}({{{inner}}})"
    else:
        value = repr(obj)
    if len(value) > 200:
        value = value[:200] + "…"
    return f"### `{name}`\n\n```python\n{name} = {value}\n```\n\n"


def generate_python_pages() -> None:
    out_dir = OUT_DIR / "python"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_category_.json").write_text(
        '{\n  "label": "Python modules",\n  "position": 2\n}\n', encoding="utf-8",
    )
    for position, (module_name, role) in enumerate(MODULES, start=1):
        module = importlib.import_module(f"dbml_sharepoint.{module_name}")
        page = (
            f"---\ntitle: {module_name}\nsidebar_position: {position}\n---\n\n"
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
        (out_dir / f"{module_name}.md").write_text(page, encoding="utf-8")


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
        body = _JINJA_TAG.sub("", block.group(1))
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
    from dbml_sharepoint.phases import phases_context

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
                f"Phase {step['number']} ({group['name']}) — {step['name']}"
            )

    page = (
        "---\ntitle: Templates\nsidebar_position: 3\n---\n\n"
        "# Template reference\n\n"
        "Every generated script is rendered from these Jinja2 templates. "
        "Each template opens with a contract comment stating what it does "
        "and what it expects — reproduced here verbatim (extracted, not "
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
    (OUT_DIR / "templates.md").write_text(page, encoding="utf-8")


def generate_index() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_category_.json").write_text(
        '{\n  "label": "API reference",\n  "position": 6\n}\n', encoding="utf-8",
    )
    page = (
        "---\ntitle: Overview\nsidebar_position: 1\n---\n\n"
        "# API reference\n\n"
        "Generated by `website/scripts/generate_api.py` — do not edit these "
        "pages by hand; rerun the script after changing the source. "
        "Signatures and docstrings come from the modules themselves; the "
        "template contracts come from each template's leading comment.\n\n"
        "| Module | Role |\n|---|---|\n"
    )
    for module_name, role in MODULES:
        page += f"| [`{module_name}`](python/{module_name}.md) | {md_escape(role)} |\n"
    page += "\nTemplates: see the [template reference](templates.md).\n"
    (OUT_DIR / "index.md").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    generate_index()
    generate_python_pages()
    generate_templates_page()
    count = len(list((OUT_DIR / "python").glob("*.md"))) + 2
    print(f"Generated {count} API reference page(s) under {OUT_DIR}")
