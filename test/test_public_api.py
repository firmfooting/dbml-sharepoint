# test/test_public_api.py
"""Four gates over what this package offers an extension author.

Every name now has exactly one importable home, and the package docstring
names those homes. Nothing else keeps that true, so these gates do.

The first refuses a second home for a name. `__all__` is the obvious way to
create one and `from x import Y as Y` is the other, because `mypy --strict`
reads a redundant alias as an explicit re-export. A gate reading only
`__all__` would wave through the alias, which is precisely the construct the
docstring's rationale rejects.

The second is a ratchet over imports deferred into a function body. It counts
them rather than judging them: the reasons differ per site, and one of them is
not a cycle at all.

The third imports every path the docstring names. This repository has been
here before with `website/docs/reference/findings.md`, which was maintained by
hand until every rule in it stopped rendering and nothing noticed.

The fourth covers what the protocol-conformance tests in
`test/test_extension.py` structurally cannot. `Any` satisfies any Protocol in
both directions, so a hook parameter reverting to `Any` leaves every
conformance assertion green while erasing the type it documents.
"""

import ast
import importlib
import re
import typing
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from _paths import PACKAGE

import dbml_sharepoint
from dbml_sharepoint.analysis.findings import (
    Finding,
    FindingCode,
    Location,
    Severity,
)
from dbml_sharepoint.extension import (
    BaseExtension,
    DeploymentExtension,
    ManifestExtras,
    SiteContext,
)
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Column, Schema, Table

#: What an extension author has to be able to import. Held as the objects, so
#: the canonical path each one is documented at comes from the object itself.
REQUIRED_SYMBOLS: tuple[Any, ...] = (
    BaseExtension,
    DeploymentExtension,
    SiteContext,
    ManifestExtras,
    Finding,
    FindingCode,
    Location,
    Severity,
    MappingBundle,
    Schema,
    Table,
    Column,
)

#: Files still deferring an import into a function body. A RATCHET: entries
#: come out, and one going in needs a reason in the pull request.
#:
#: Not all of these are cycles. `wizard.py`'s four are, with `cli.py`, tracked
#: by #171, and `extract/wizard.py`'s two are the same cycle in the same
#: direction: `cli` imports both wizards at its top, so both defer their way
#: back. Of `bundle.py`'s five, only the `reportgen` one is: that module
#: imports `bundle` back. The other four are deliberate lazy loading so
#: `bundle.py` stays importable for its packaging helpers, which its own
#: comment states.
DEFERRED_IMPORTS: dict[str, int] = {
    "bundle.py": 7,
    "wizard.py": 4,
    "extract/wizard.py": 2,
}

#: How a deferred import is declared, since PLC0415 is enforced in `src/`.
#: Counted as a substring, so a suppression listing further codes after this
#: one still registers. Spelled without the leading hash because ruff reads a
#: hash in a comment as a real directive, whatever the surrounding prose says.
DEFERRAL_MARKER = "noqa: PLC0415"

#: A canonical path in the package docstring: a dotted module, then a name
#: that starts with a capital. Every documented symbol is a class or a type
#: alias, so restricting the last segment this way keeps the count meaningful
#: rather than inflating it with bare module mentions.
DOCUMENTED_PATH = re.compile(
    r"\bdbml_sharepoint(?:\.[a-z_][a-z0-9_]*)+\.[A-Z][A-Za-z0-9_]*\b"
)

#: The size of REQUIRED_SYMBOLS today. Written out rather than derived, so
#: dropping a symbol from that tuple cannot quietly lower the floor as well.
#: Never lowered to make a change pass.
DOCUMENTED_MINIMUM = 12


class UnreadableAllError(RuntimeError):
    """An `__all__` this gate cannot evaluate, so it refuses rather than skips.

    A tuple built by concatenation, a name bound elsewhere, or an `__all__ +=`
    all read as "no entries" to a naive parser, which is the hole rather than
    the check.
    """


def _python_modules(root: Path) -> list[Path]:
    """Every module under `root`, in a stable order so failures are diffable."""
    return sorted(root.rglob("*.py"))


def _module_level(body: Sequence[ast.stmt]) -> Iterator[ast.stmt]:
    """Statements that run at import, including inside `if TYPE_CHECKING:`.

    Deliberately not `ast.walk`: a name bound inside a function body is local,
    and counting it as a module-level definition would let a real re-export
    through.
    """
    for node in body:
        yield node
        if isinstance(node, ast.If | ast.For | ast.While):
            yield from _module_level(node.body)
            yield from _module_level(node.orelse)
        elif isinstance(node, ast.With):
            yield from _module_level(node.body)
        elif isinstance(node, ast.Try):
            yield from _module_level(node.body)
            yield from _module_level(node.orelse)
            yield from _module_level(node.finalbody)
            for handler in node.handlers:
                yield from _module_level(handler.body)


def _target_names(target: ast.expr) -> set[str]:
    """The names one assignment target binds, unpacking tuple and list forms."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple | ast.List):
        return {name for element in target.elts for name in _target_names(element)}
    return set()


def _defined_names(module: ast.Module) -> set[str]:
    """What this module defines itself, by any of the five binding forms.

    `ast.AnnAssign` is here because `checks/__init__.py` declares
    `CHECK_FAMILIES` with a type; `ast.TypeAlias` because `findings.py`
    declares `Severity` as a PEP 695 `type` statement.
    """
    names: set[str] = set()
    for node in _module_level(module.body):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names |= _target_names(target)
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            names |= _target_names(node.target)
        elif isinstance(node, ast.TypeAlias):
            names |= _target_names(node.name)
    return names


def _mutates_all(node: ast.stmt) -> bool:
    """`__all__.append(...)` or `.extend(...)`, which read as exporting nothing.

    Neither an assignment nor an augmented one, so the two checks around this
    walked past both and the gate reported CLEAN, which is the state
    `UnreadableAllError` exists to be distinguishable from.
    """
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "__all__"
    )


def _declared_exports(module: ast.Module, relative: str) -> list[str]:
    """The entries of `__all__`, or an empty list where there is none.

    Raises rather than returning nothing when `__all__` is not a literal list
    or tuple of strings, because a silent skip is indistinguishable from a
    module that exports nothing.
    """
    entries: list[str] = []
    for node in _module_level(module.body):
        if isinstance(node, ast.AugAssign) and _target_names(node.target) == {"__all__"}:
            raise UnreadableAllError(
                f"{relative}:{node.lineno}: `__all__` is extended in place. This "
                "gate reads only a literal list or tuple of strings, so write "
                "it as one."
            )
        if _mutates_all(node):
            raise UnreadableAllError(
                f"{relative}:{node.lineno}: `__all__` is mutated by a method "
                "call. This gate reads only a literal list or tuple of "
                "strings, so write it as one."
            )
        if isinstance(node, ast.Assign):
            targets = {name for target in node.targets for name in _target_names(target)}
        elif isinstance(node, ast.AnnAssign):
            targets = _target_names(node.target)
        else:
            continue
        if "__all__" not in targets or node.value is None:
            continue
        entries.extend(_literal_strings(node.value, relative, node.lineno))
    return entries


def _literal_strings(value: ast.expr, relative: str, lineno: int) -> list[str]:
    """The strings in a literal list or tuple, refusing anything else."""
    if not isinstance(value, ast.List | ast.Tuple):
        raise UnreadableAllError(
            f"{relative}:{lineno}: `__all__` is {ast.dump(value)[:60]}, not a "
            "literal list or tuple. This gate cannot tell what it exports."
        )
    names: list[str] = []
    for element in value.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            raise UnreadableAllError(
                f"{relative}:{lineno}: `__all__` holds a non-string entry "
                f"({ast.dump(element)[:60]}), so its contents are not readable here."
            )
        names.append(element.value)
    return names


def _redundant_aliases(module: ast.Module, relative: str) -> list[str]:
    """`import Y as Y`, which `mypy --strict` accepts as an explicit re-export."""
    offenders: list[str] = []
    for node in _module_level(module.body):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        offenders.extend(
            f"{relative}:{node.lineno}: `import {alias.name} as {alias.asname}` "
            "re-exports a name this module does not define"
            for alias in node.names
            if alias.asname is not None and alias.asname == alias.name
        )
    return offenders


def _value_aliases(module: ast.Module, relative: str) -> list[str]:
    """`NAME = other.NAME`, the third way to give one name a second home.

    Neither an `__all__` entry nor an import alias, so the two scans above
    both miss it. `group_description.MARKER_PREFIX = provenance.MARKER_PREFIX`
    was one, kept for "existing importers", which is the compatibility
    argument this design rejects.
    """
    offenders: list[str] = []
    for node in _module_level(module.body):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Attribute)
            and value.attr == target.id
        ):
            offenders.append(
                f"{relative}:{node.lineno}: `{target.id}` aliases another "
                "module's name, giving it a second home"
            )
    return offenders


def re_export_offenders(source: str, relative: str) -> list[str]:
    """Every second home for a name that `source` DECLARES.

    One helper, called by the gate and by its proofs alike. A proof that
    reimplements the scan passes while the real scan is broken.

    A plain `from x import Y` is deliberately not counted, though it does bind
    `Y` in this module's namespace and `analysis.validator.Finding` still
    resolves at runtime because of it. Counting it would flag every ordinary
    import in the package, and `mypy --strict` already refuses that path with
    "does not explicitly export attribute". The three shapes below are the
    ones where a module claims a name as its own, so they are the ones a type
    checker honours and the ones this gate answers for.
    """
    module = ast.parse(source)
    defined = _defined_names(module)
    offenders = [
        f"{relative}: `__all__` names {name!r}, which this module does not define"
        for name in _declared_exports(module, relative)
        if name not in defined
    ]
    offenders.extend(_redundant_aliases(module, relative))
    offenders.extend(_value_aliases(module, relative))
    return offenders


def deferred_counts(root: Path) -> dict[str, int]:
    """Deferral markers per module, keyed by path relative to `root`.

    Files with none are left out, so the result compares directly against the
    ratchet and a file dropping to zero fails as loudly as one going up.
    """
    counts: dict[str, int] = {}
    for path in _python_modules(root):
        found = path.read_text(encoding="utf-8").count(DEFERRAL_MARKER)
        if found:
            counts[path.relative_to(root).as_posix()] = found
    return counts


def _canonical(symbol: Any) -> str:
    """Where a symbol actually lives, asked of the symbol rather than assumed."""
    return f"{symbol.__module__}.{symbol.__name__}"


def documented_paths(doc: str) -> list[str]:
    """The canonical import paths the docstring names, deduplicated."""
    return sorted(set(DOCUMENTED_PATH.findall(doc)))


def unresolvable(paths: Iterable[str]) -> list[str]:
    """Documented paths that do not import, each with the reason."""
    broken: list[str] = []
    for path in paths:
        module_name, _, name = path.rpartition(".")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            broken.append(f"{path}: {exc}")
            continue
        if not hasattr(module, name):
            broken.append(f"{path}: {module_name} defines no {name!r}")
    return broken


def _hooks(owner: type) -> list[str]:
    """The protocol's hook names, read off the class rather than listed here.

    Discovered so a hook added later is covered without editing this file.
    """
    return sorted(
        name
        for name, value in vars(owner).items()
        if not name.startswith("_") and callable(value)
    )


def hook_parameters(owner: type) -> list[tuple[str, object]]:
    """Every hook parameter and its resolved annotation, return types excluded."""
    return [
        (f"{owner.__name__}.{hook}({parameter})", annotation)
        for hook in _hooks(owner)
        for parameter, annotation in typing.get_type_hints(getattr(owner, hook)).items()
        if parameter != "return"
    ]


def mentions_any(annotation: object) -> bool:
    """True for `Any` itself and for `Any` nested inside a generic."""
    if annotation is Any:
        return True
    return any(mentions_any(argument) for argument in typing.get_args(annotation))


def test_no_module_re_exports_another_module_s_name() -> None:
    """Each name must have exactly one importable home.

    The failure names every site.

    A re-export is a second place the name has to be kept in step with, and
    the two drift silently: the alias keeps importing long after the original
    has moved or changed shape.
    """
    modules = _python_modules(PACKAGE)
    # Without this the gate passes on an empty walk, which is how a path that
    # stops matching goes unnoticed.
    assert len(modules) > 50, f"only {len(modules)} modules walked, so this pins nothing"

    offenders = [
        offender
        for path in modules
        for offender in re_export_offenders(
            path.read_text(encoding="utf-8"), path.relative_to(PACKAGE).as_posix(),
        )
    ]

    assert not offenders, (
        "A module re-exports a name it does not define. Import the name from "
        "the module that defines it; the package docstring names those "
        "homes:\n  " + "\n  ".join(offenders)
    )


def test_the_scan_reports_an_all_naming_an_imported_name(tmp_path: Path) -> None:
    """Proof, on a seeded module, that the scan reports what it is for.

    The gate above passes today by finding nothing, which is the same
    observable result as a scan that reads no modules or matches nothing.
    """
    seeded = tmp_path / "aggregator.py"
    seeded.write_text(
        "from dbml_sharepoint.analysis.findings import Finding\n"
        "\n"
        '__all__ = ["Finding", "Reported"]\n'
        "\n"
        "\n"
        "class Reported:\n"
        "    pass\n",
        encoding="utf-8", newline="\n",
    )

    assert re_export_offenders(seeded.read_text(encoding="utf-8"), "aggregator.py") == [
        "aggregator.py: `__all__` names 'Finding', which this module does not define",
    ]


def test_the_scan_reports_a_redundant_alias_import(tmp_path: Path) -> None:
    """`import Y as Y` is a re-export to `mypy --strict`, so it is one here.

    Reading `__all__` alone would leave this construct as a supported way to
    do the forbidden thing, and it is the one a contributor reaches for after
    an `__all__` is refused.
    """
    seeded = tmp_path / "shim.py"
    seeded.write_text(
        "from dbml_sharepoint.analysis.findings import Finding as Finding\n"
        "import dbml_sharepoint.extension as extension\n",
        encoding="utf-8", newline="\n",
    )

    assert re_export_offenders(seeded.read_text(encoding="utf-8"), "shim.py") == [
        (
            "shim.py:1: `import Finding as Finding` re-exports a name this "
            "module does not define"
        ),
    ]


def test_a_module_that_defines_what_it_exports_is_clean(tmp_path: Path) -> None:
    """The complement, so the scan cannot pass by flagging everything.

    All five binding forms appear, because a definition the scan does not
    recognise turns a correct module into a permanent false failure.
    """
    seeded = tmp_path / "owner.py"
    seeded.write_text(
        "from collections.abc import Callable\n"
        "\n"
        '__all__ = ["CHECK_FAMILIES", "Severity", "Reported", "report", "COUNT"]\n'
        "\n"
        "type Severity = str\n"
        "COUNT = 1\n"
        "CHECK_FAMILIES: tuple[Callable[[int], int], ...] = ()\n"
        "\n"
        "\n"
        "class Reported:\n"
        "    pass\n"
        "\n"
        "\n"
        "def report() -> None:\n"
        "    shadowed = 1\n"
        "    return None\n",
        encoding="utf-8", newline="\n",
    )

    assert re_export_offenders(seeded.read_text(encoding="utf-8"), "owner.py") == []


def test_a_name_bound_only_inside_a_function_does_not_count_as_defined(
    tmp_path: Path,
) -> None:
    """A local binding is not a definition, and `ast.walk` cannot tell them apart.

    Without the narrower traversal a module could export any name it happened
    to assign inside any function, which covers most re-exports by accident.
    """
    seeded = tmp_path / "local.py"
    seeded.write_text(
        "from dbml_sharepoint.analysis.findings import Finding\n"
        "\n"
        '__all__ = ["Reported"]\n'
        "\n"
        "\n"
        "def build() -> Finding:\n"
        "    Reported = Finding\n"
        "    return Reported\n",
        encoding="utf-8", newline="\n",
    )

    assert re_export_offenders(seeded.read_text(encoding="utf-8"), "local.py") == [
        "local.py: `__all__` names 'Reported', which this module does not define",
    ]


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("__all__ = _EXPORTS\n", "not a literal"),
        ('__all__ = ["Finding"] + _EXTRA\n', "a concatenation"),
        ('__all__ = ["Finding", _NAME]\n', "a non-string entry"),
        ('__all__ = ["Finding"]\n__all__ += ["Severity"]\n', "extended in place"),
    ],
    ids=["name", "concatenation", "non-string-entry", "augmented"],
)
def test_an_all_that_cannot_be_read_fails_closed(body: str, reason: str) -> None:
    """Four shapes that a naive parser reports as exporting nothing.

    Skipping any of them would leave a documented way past the gate, so each
    raises a named error instead.
    """
    source = "from dbml_sharepoint.analysis.findings import Finding\n\n" + body
    with pytest.raises(UnreadableAllError):
        re_export_offenders(source, f"unreadable_{reason}.py")


def test_a_readable_all_of_either_literal_form_is_evaluated() -> None:
    """A tuple is as readable as a list, so only the unreadable forms raise.

    A tuple is a literal this gate can read, so refusing it would fail on
    correct code.
    """
    for literal in ('["Finding"]', '("Finding",)'):
        source = (
            "from dbml_sharepoint.analysis.findings import Finding\n"
            f"__all__ = {literal}\n"
        )
        assert re_export_offenders(source, "tupled.py") == [
            "tupled.py: `__all__` names 'Finding', which this module does not define",
        ]


def test_no_import_is_deferred_without_a_recorded_reason() -> None:
    """The ratchet over function-body imports, matched exactly.

    Exact rather than "no more than", because a deferral that is removed must
    also fail: that is what forces the number down instead of letting it sit
    at a ceiling nobody revisits.
    """
    assert deferred_counts(PACKAGE) == DEFERRED_IMPORTS, (
        "The deferred imports in `src/` no longer match the recorded ratchet. "
        "A new one needs a reason in the pull request; a removed one means "
        "DEFERRED_IMPORTS above should come down with it."
    )


def test_the_ratchet_counts_a_seeded_deferral(tmp_path: Path) -> None:
    """Proof the count comes from reading files, on a tree with known contents."""
    (tmp_path / "nested").mkdir()
    (tmp_path / "eager.py").write_text(
        "import json\n\n\ndef load() -> None:\n    return None\n",
        encoding="utf-8", newline="\n",
    )
    (tmp_path / "nested" / "lazy.py").write_text(
        "def render() -> None:\n"
        "    import json  # noqa: PLC0415\n"
        "    from pathlib import Path  # noqa: PLC0415, F401\n"
        "    return json.dumps({})\n",
        encoding="utf-8", newline="\n",
    )

    assert deferred_counts(tmp_path) == {"nested/lazy.py": 2}


def test_every_documented_import_path_resolves() -> None:
    """The package docstring is the public surface, so every path it names imports.

    A docstring is not executable and rots without a reader noticing. This one
    is read back and every path in it imported.
    """
    doc = dbml_sharepoint.__doc__
    assert doc, "the package docstring states the public surface; it cannot be empty"

    paths = documented_paths(doc)
    # The anti-vacuity half: a rewording that stops matching would otherwise
    # leave nothing to resolve and pass.
    assert len(paths) >= DOCUMENTED_MINIMUM, (
        f"the docstring names {len(paths)} canonical paths, below the "
        f"{DOCUMENTED_MINIMUM} the extension surface needs. Either a name was "
        "dropped or the paths stopped being written as `module.Name`."
    )

    assert unresolvable(paths) == [], (
        "The package docstring names an import path that does not resolve. "
        "Correct the docstring, or move the name back."
    )


def test_the_resolver_reports_a_path_that_does_not_import() -> None:
    """Proof on an invented docstring, so a clean one cannot hide a broken check."""
    invented = (
        "`dbml_sharepoint.extension.BaseExtension` is real.\n"
        "`dbml_sharepoint.extension.MovedAway` is not.\n"
        "`dbml_sharepoint.model.gone.Thing` is not either.\n"
    )
    paths = documented_paths(invented)
    assert paths == [
        "dbml_sharepoint.extension.BaseExtension",
        "dbml_sharepoint.extension.MovedAway",
        "dbml_sharepoint.model.gone.Thing",
    ]

    broken = unresolvable(paths)
    assert [entry.split(":")[0] for entry in broken] == [
        "dbml_sharepoint.extension.MovedAway",
        "dbml_sharepoint.model.gone.Thing",
    ]


def test_the_documented_paths_are_the_ones_an_extension_author_needs() -> None:
    """The count above says how many paths were found; this says which.

    Each expected path is derived from the imported object rather than typed
    out, so a name that moves changes what is expected here and the docstring
    has to move with it. Eleven strings written by hand would agree with a
    docstring that had gone wrong in the same way.
    """
    assert len(REQUIRED_SYMBOLS) >= DOCUMENTED_MINIMUM, (
        f"REQUIRED_SYMBOLS has shrunk to {len(REQUIRED_SYMBOLS)}, which lets "
        "the docstring drop a name the extension surface needs"
    )
    doc = dbml_sharepoint.__doc__ or ""
    named = documented_paths(doc)
    missing = [
        path for symbol in REQUIRED_SYMBOLS if (path := _canonical(symbol)) not in named
    ]
    assert missing == [], (
        "The package docstring no longer names every path an extension author "
        "needs:\n  " + "\n  ".join(missing)
    )


def test_no_extension_hook_parameter_is_any() -> None:
    """`Any` satisfies any Protocol, so conformance cannot catch it coming back.

    `test_extension.py` asserts `BaseExtension` implements
    `DeploymentExtension`, and that stays green with every parameter typed
    `Any` on either side. The checkable property is the annotation itself.
    """
    for owner in (DeploymentExtension, BaseExtension):
        parameters = hook_parameters(owner)
        assert len(parameters) > 10, (
            f"{owner.__name__}: only {len(parameters)} hook parameters were "
            "inspected, so this pins nothing"
        )
        offenders = [name for name, annotation in parameters if mentions_any(annotation)]
        assert offenders == [], (
            "An extension hook parameter is typed `Any`, which erases a type "
            "this package defines and which no conformance test can see:\n  "
            + "\n  ".join(offenders)
        )


def test_a_hook_return_type_may_still_be_any() -> None:
    """The two `dict[str, Any]` returns are deliberate and stay allowed.

    A seeded field dictionary is genuinely arbitrary JSON. Gating returns as
    well would force a fictitious type on the one place `Any` is honest.
    """
    hints = typing.get_type_hints(BaseExtension.seed_lists)
    assert mentions_any(hints["return"]), (
        "seed_lists returns dict[str, dict[str, Any]]; if that changed, this "
        "test is the record of why it was allowed to"
    )
    assert [name for name, annotation in hook_parameters(BaseExtension)
            if mentions_any(annotation)] == []


def test_the_hook_scan_reports_a_parameter_that_reverted_to_any() -> None:
    """Proof on a seeded class, since the real hooks are typed today.

    Written as a class rather than by editing `extension.py`, so the proof
    cannot leave the source worse than it found it.
    """
    class _Reverted:
        def extra_validators(self, bundle: Any, schema: Schema) -> list[Finding]:
            return []

        def seed_lists(
            self, bundle: MappingBundle, schema: Schema, site_context: SiteContext,
        ) -> dict[str, Any]:
            return {}

    parameters = hook_parameters(_Reverted)
    assert [name for name, annotation in parameters if mentions_any(annotation)] == [
        "_Reverted.extra_validators(bundle)",
    ]


def test_any_nested_in_a_parameter_generic_is_reported() -> None:
    """`bundle: dict[str, Any]` erases the type as thoroughly as bare `Any`.

    Checked directly because no hook takes a generic parameter today, so the
    gate above would never exercise the nested case.
    """
    assert mentions_any(dict[str, Any])
    assert mentions_any(list[dict[str, Any]] | None)
    assert not mentions_any(MappingBundle)
    assert not mentions_any(dict[str, str])
