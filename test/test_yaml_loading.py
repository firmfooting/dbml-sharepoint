# test/test_yaml_loading.py
"""The one YAML parser, and the gate that keeps every read going through it.

`yaml.safe_load` keeps the last of two identical keys in a mapping and reports
nothing (#672). `model/_yaml.py` refuses the repeat, and it only protects the
files that are read with it, so the gate below holds the package to it.
"""

import ast
import io
from pathlib import Path

import pytest
import yaml
from _paths import PACKAGE, SOLUTION_TEMPLATES

from dbml_sharepoint.model import _yaml


def _refusal(text: str) -> str:
    """The parser's message for `text`, read as a stream so it carries no snippet."""
    with pytest.raises(yaml.YAMLError) as err:
        _yaml.safe_load(io.StringIO(text))
    return str(err.value)


def test_a_key_written_twice_is_refused_naming_both_lines() -> None:
    assert _refusal("a: 1\nb: 2\na: 3\n") == (
        "while constructing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        "found duplicate key 'a' (first at line 1)\n"
        '  in "<file>", line 3, column 1'
    )


@pytest.mark.parametrize(
    ("text", "key"),
    [
        pytest.param("a:\n  b: 1\n  c: 2\n  b: 3\n", "'b'", id="nested"),
        pytest.param("a: {b: 1, b: 2}\n", "'b'", id="flow"),
        pytest.param("- {b: 1, b: 2}\n", "'b'", id="in-a-sequence"),
        pytest.param("!!set {a, a}\n", "'a'", id="set"),
    ],
)
def test_a_repeat_is_refused_wherever_a_mapping_sits(text: str, key: str) -> None:
    assert f"found duplicate key {key}" in _refusal(text)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        pytest.param("1: a\n0x1: b\n", "1", id="int-and-hex"),
        pytest.param("~: a\nnull: b\n", "None", id="two-nulls"),
    ],
)
def test_keys_that_construct_equal_are_one_key(text: str, key: str) -> None:
    """A dict holds one entry for two keys that compare equal, so the second
    replaced the first exactly as a repeated spelling did."""
    assert f"found duplicate key {key} (first at line 1)" in _refusal(text)


def test_keys_of_different_types_are_distinct() -> None:
    """`1:` and `"1":` are two keys to YAML and to a dict alike. Refusing the
    int is `_text_key`'s job, where the context can be named."""
    assert _yaml.safe_load('1: a\n"1": b\n') == {1: "a", "1": "b"}


def test_a_key_beside_a_merge_overrides_it() -> None:
    """The merge-key spec lets a key written beside `<<` override the merged
    one, and the shipped programme-governance mapping does that."""
    assert _yaml.safe_load("base: &b {x: 1}\nuse: {<<: *b, x: 2}\n")["use"] == {"x": 2}
    merged = _yaml.safe_load("a: &a {x: 1}\nb: &b {y: 1}\nuse: {<<: [*a, *b], x: 2, y: 3}\n")
    assert merged["use"] == {"x": 2, "y": 3}


def test_a_repeat_inside_a_merge_source_is_refused() -> None:
    """The source is flattened into its user and never constructed alone, so
    a check in `construct_mapping` would not see it."""
    assert "found duplicate key 'x'" in _refusal("use: {<<: {x: 1, x: 2}}\n")


def test_a_nested_merge_flattened_before_it_is_built_is_not_a_repeat() -> None:
    """PyYAML builds mappings breadth first, so `use` flattens `b` in place
    before `b` is built, leaving `x` twice in its pairs. A check that read
    those pairs again would refuse a document SafeLoader reads correctly."""
    text = "defs:\n  inner:\n    b: &b {<<: &a {x: 1}, x: 3}\nuse: {<<: *b}\n"
    assert _yaml.safe_load(text) == yaml.safe_load(text)
    assert _yaml.safe_load(text)["use"] == {"x": 3}


def test_a_value_key_loads_as_safe_loader_reads_it() -> None:
    """PyYAML tags a bare `=` key specially and retags it as text while
    flattening, so it cannot be constructed before that."""
    assert _yaml.safe_load("=: 1\n") == yaml.safe_load("=: 1\n") == {"=": 1}


@pytest.mark.parametrize("text", ["? [a, b]\n: 1\n", "? {a: 1}\n: 1\n"])
def test_an_unhashable_key_fails_as_safe_loader_fails(text: str) -> None:
    with pytest.raises(yaml.YAMLError) as ours:
        _yaml.safe_load(text)
    with pytest.raises(yaml.YAMLError) as theirs:
        yaml.safe_load(text)
    assert str(ours.value) == str(theirs.value)
    assert "found unhashable key" in str(ours.value)


def test_every_shipped_yaml_file_loads_unchanged() -> None:
    """An enforced rule must not be stronger than the reference implementation.

    The programme-governance mapping overrides a merged width, which is the
    case a naive repeat check refuses, so it is named as well as globbed.
    """
    shipped = sorted(SOLUTION_TEMPLATES.rglob("*.yaml"))
    governance = SOLUTION_TEMPLATES / "programme-governance" / "20-configure" / "mapping.yaml"
    assert governance in shipped
    assert "<<: *action_spine\n        Title: 300\n" in governance.read_text(encoding="utf-8")
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        assert _yaml.safe_load(text) == yaml.safe_load(text), path


#: PyYAML's functions that construct a document from text.
_LOAD_FUNCTIONS = frozenset({
    "load", "load_all", "safe_load", "safe_load_all",
    "full_load", "full_load_all", "unsafe_load", "unsafe_load_all",
})

#: The one module allowed to use them or a PyYAML loader class.
_PARSER = "model/_yaml.py"


def _is_loading_name(name: str) -> bool:
    return name in _LOAD_FUNCTIONS or name.endswith("Loader")


def _yaml_loads(root: Path) -> dict[str, list[str]]:
    """Every use of PyYAML's loading machinery under `root`, by module.

    A call through `yaml.` or an alias of it, a loader class such as
    `yaml.SafeLoader`, and a `from yaml import` of either.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = {
            alias.asname or alias.name
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names if alias.name == "yaml"
        }
        uses: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and _is_loading_name(node.attr)
            ):
                uses.append((node.lineno, f"{node.value.id}.{node.attr}"))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "yaml":
                uses.extend(
                    (node.lineno, f"from {node.module} import {alias.name}")
                    for alias in node.names if _is_loading_name(alias.name)
                )
        if uses:
            found[path.relative_to(root).as_posix()] = [f"{n}: {use}" for n, use in sorted(uses)]
    return found


def test_the_package_parses_yaml_only_through_the_unique_key_loader() -> None:
    """`yaml.safe_load` anywhere else would read a repeated key silently again.

    Static, like `test_the_package_has_exactly_one_writer`, because the defect
    is per call site: the next parse someone adds reintroduces it, and nothing
    in ruff, pyrefly or the rest of the suite would say so.
    """
    found = _yaml_loads(PACKAGE)
    # Not vacuous: the parser's own base class is a use the walk has to see.
    assert _PARSER in found, sorted(found)
    outside = {module: uses for module, uses in found.items() if module != _PARSER}
    assert not outside, (
        "parse YAML with `dbml_sharepoint.model._yaml.safe_load`, which refuses "
        f"a repeated key. Found: {outside}"
    )


def test_the_gate_sees_every_spelling_of_a_direct_load(tmp_path: Path) -> None:
    (tmp_path / "direct.py").write_text(
        "import yaml\nyaml.safe_load(s)\nyaml.load(s, Loader=yaml.SafeLoader)\n",
        encoding="utf-8",
    )
    (tmp_path / "aliased.py").write_text("import yaml as y\ny.load_all(s)\n", encoding="utf-8")
    (tmp_path / "imported.py").write_text(
        "from yaml import CSafeLoader, safe_load\n", encoding="utf-8",
    )
    (tmp_path / "clean.py").write_text(
        "import yaml\nyaml.safe_dump(d)\nexcept_ = yaml.YAMLError\n", encoding="utf-8",
    )
    assert _yaml_loads(tmp_path) == {
        "aliased.py": ["2: y.load_all"],
        "direct.py": ["2: yaml.safe_load", "3: yaml.SafeLoader", "3: yaml.load"],
        "imported.py": [
            "1: from yaml import CSafeLoader", "1: from yaml import safe_load",
        ],
    }
