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


def test_two_words_read_as_one_boolean_are_both_named() -> None:
    """`No` and `Off` are two words to the author, so naming only `False`
    would not say what was written twice."""
    assert _refusal("map: { No: blocked, Off: warning }\n") == (
        "while constructing a mapping\n"
        '  in "<file>", line 1, column 6\n'
        "found duplicate key False: 'No' (line 1) and 'Off' (line 1) both read as False; "
        "quote them\n"
        '  in "<file>", line 1, column 21'
    )


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        pytest.param(
            "1: a\n0x1: b\n",
            "found duplicate key 1: '1' (line 1) and '0x1' (line 2) both read as 1; quote them",
            id="int-and-hex",
        ),
        pytest.param(
            "~: a\nnull: b\n",
            "found duplicate key None: '~' (line 1) and 'null' (line 2) both read as None; "
            "quote them",
            id="two-nulls",
        ),
        pytest.param(
            "1: a\n1.0: b\n",
            "found duplicate key 1.0: '1' (line 1) and '1.0' (line 2) read as 1 and 1.0, "
            "which are equal; quote them",
            id="int-and-float",
        ),
        pytest.param(
            "No: a\nNo: b\n", "found duplicate key False (first at line 1)",
            id="one-spelling-twice",
        ),
    ],
)
def test_keys_that_construct_equal_are_one_key(text: str, problem: str) -> None:
    """A dict holds one entry for two keys that compare equal, so the second
    replaced the first exactly as a repeated spelling did. Both spellings are
    named where they differ."""
    assert f"\n{problem}\n" in _refusal(text)


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


def test_a_second_merge_key_in_one_mapping_is_refused() -> None:
    """Two `<<` keys are a repeat under the spec, and PyYAML settles their
    clash the opposite way to the list form, so neither reading is safe."""
    two_keys = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: *a\n  <<: *b\n"
    listed = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: [*a, *b]\n"
    assert yaml.safe_load(two_keys)["use"] == {"x": 2}
    assert yaml.safe_load(listed)["use"] == _yaml.safe_load(listed)["use"] == {"x": 1}
    assert _refusal(two_keys) == (
        "while constructing a mapping\n"
        '  in "<file>", line 4, column 3\n'
        "found duplicate key '<<' (first at line 4)\n"
        '  in "<file>", line 5, column 3'
    )


def test_a_quoted_merge_spelling_is_a_text_key_not_a_second_merge() -> None:
    text = 'a: &a {x: 1}\nuse: {<<: *a, "<<": 2}\n'
    assert _yaml.safe_load(text) == yaml.safe_load(text)
    assert _yaml.safe_load(text)["use"] == {"x": 1, "<<": 2}


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


#: The PyYAML names a module other than the parser may use, none of which parse.
_ALLOWED = frozenset({
    # Catching the parser's refusal.
    "YAMLError",
    # Writing a document: `extract/emit.py` renders the mapping it recovers.
    "safe_dump",
})

#: The one module allowed to use the rest of PyYAML.
_PARSER = "model/_yaml.py"


def _is_pyyaml(module: str) -> bool:
    return module == "yaml" or module.startswith("yaml.")


def _bindings(tree: ast.Module) -> dict[str, str]:
    """Each name an `import` binds to PyYAML, and the module it names.

    `import yaml.loader` binds `yaml` to the package, as Python does, and
    `import yaml.loader as ld` binds `ld` to the submodule.
    """
    return {
        alias.asname or "yaml": alias.name if alias.asname else "yaml"
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names if _is_pyyaml(alias.name)
    }


def _chain(name: ast.Name, parents: dict[ast.AST, ast.AST]) -> list[str]:
    """The attributes read off `name`, outermost last: `yaml.loader.X` is `[loader, X]`."""
    attrs: list[str] = []
    node: ast.AST = name
    while isinstance(parent := parents.get(node), ast.Attribute) and parent.value is node:
        attrs.append(parent.attr)
        node = parent
    return attrs


def _unlisted_yaml_uses(root: Path) -> dict[str, list[str]]:
    """Every reach into PyYAML under `root` past `_ALLOWED`, by module.

    A name read through `yaml`, an alias of it or a submodule, followed to
    the first attribute below the package; any `from yaml.<sub> import`;
    `from yaml import *`; and a `from yaml import` of a name not listed.
    Reaching PyYAML through `getattr` or `importlib` is out of scope.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bound = _bindings(tree)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        uses: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in bound:
                attrs = _chain(node, parents)
                below = [*bound[node.id].split(".")[1:], *attrs]
                if not below or below[0] not in _ALLOWED:
                    uses.append((node.lineno, ".".join([node.id, *attrs])))
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and _is_pyyaml(node.module or "")
            ):
                uses.extend(
                    (node.lineno, f"from {node.module} import {alias.name}")
                    for alias in node.names
                    if node.module != "yaml" or alias.name not in _ALLOWED
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
    found = _unlisted_yaml_uses(PACKAGE)
    # Not vacuous: the parser's own base class is a use the walk has to see.
    assert _PARSER in found, sorted(found)
    outside = {module: uses for module, uses in found.items() if module != _PARSER}
    assert not outside, (
        "parse YAML with `dbml_sharepoint.model._yaml.safe_load`, which refuses "
        f"a repeated key, or add a name that cannot parse to `_ALLOWED`. Found: {outside}"
    )


def test_the_gate_flags_every_spelling_that_reaches_past_the_allowlist(tmp_path: Path) -> None:
    seeded = {
        "direct.py": "import yaml\nyaml.safe_load(s)\nyaml.load(s, Loader=yaml.SafeLoader)\n",
        "aliased.py": "import yaml as y\ny.load_all(s)\n",
        "imported.py": "from yaml import CSafeLoader, safe_load\n",
        "lower_level.py": "import yaml\nyaml.compose(s)\nyaml.compose_all(s)\nyaml.parse(s)\n",
        "submodule.py": "import yaml.loader\nyaml.safe_load(s)\nyaml.loader.SafeLoader(s)\n",
        "submodule_aliased.py": "import yaml.loader as ld\nld.SafeLoader(s)\n",
        "submodule_imported.py": "from yaml import loader\n",
        "star.py": "from yaml import *\n",
        "from_submodule.py": "from yaml.constructor import SafeConstructor\n",
        "passed_on.py": "import yaml\nparse_with(yaml)\n",
        "clean.py": (
            "import yaml\nfrom yaml import YAMLError\nyaml.safe_dump(d)\n"
            "except_ = yaml.YAMLError\nname = yaml.YAMLError.__name__\n"
        ),
    }
    for name, text in seeded.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert _unlisted_yaml_uses(tmp_path) == {
        "aliased.py": ["2: y.load_all"],
        "direct.py": ["2: yaml.safe_load", "3: yaml.SafeLoader", "3: yaml.load"],
        "from_submodule.py": ["1: from yaml.constructor import SafeConstructor"],
        "imported.py": ["1: from yaml import CSafeLoader", "1: from yaml import safe_load"],
        "lower_level.py": ["2: yaml.compose", "3: yaml.compose_all", "4: yaml.parse"],
        "passed_on.py": ["2: yaml"],
        "star.py": ["1: from yaml import *"],
        "submodule.py": ["2: yaml.safe_load", "3: yaml.loader.SafeLoader"],
        "submodule_aliased.py": ["2: ld.SafeLoader"],
        "submodule_imported.py": ["1: from yaml import loader"],
    }
