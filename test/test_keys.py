"""The unknown-key guard and the mapping-shape guard, tested directly.

Both helpers in `model/_keys.py` were reached only through whichever parser
happened to call them, so their own contract was pinned nowhere and a change
to either one surfaced as a failure in a section test that looks unrelated
(#172). The messages matter as much as the refusals: these are what a
SharePoint admin editing YAML reads instead of a loader traceback, and the
docstrings make specific promises about naming the section and naming the
offending key.
"""

import pytest
import yaml

from dbml_sharepoint.model._keys import _known_keys, _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError, UnknownMappingKeyError


def test_a_mapping_passes_through_unchanged() -> None:
    """The same object, not a copy. Callers index the result afterwards."""
    block = {"Risk": {"title": "Risks"}}
    assert _require_mapping(block, "mapping.entities") is block


@pytest.mark.parametrize(
    ("typed", "read"),
    [
        ("No", "key False is not text (YAML read it as bool)"),
        ("2026", "key 2026 is not text (YAML read it as int)"),
        ("2.10", "key 2.1 is not text (YAML read it as float)"),
        ("010", "key 8 is not text (YAML read it as int)"),
        ("~", "key None is not text (YAML read it as NoneType)"),
    ],
)
def test_a_key_yaml_did_not_read_as_text_is_refused(typed: str, read: str) -> None:
    """Normalising with `str()` cannot give back what was typed: `2.10:`
    came back as "2.1" and `No:` as "False", so the key is refused instead."""
    block = yaml.safe_load(f"{typed}: =TODAY()\nRisk: {{}}")
    with pytest.raises(MappingShapeError) as err:
        _require_mapping(block, "default_formulas.Risk")
    assert str(err.value) == f"default_formulas.Risk: {read}; quote it"


def test_a_number_key_beside_its_quoted_twin_is_refused_rather_than_merged() -> None:
    """`1:` and `"1":` are two keys to YAML, and `str()` folded them into one,
    so one declaration silently replaced the other."""
    block = yaml.safe_load('1: first\n"1": second')
    with pytest.raises(MappingShapeError, match=r"key 1 is not text"):
        _require_mapping(block, "field_sets.Risk")


def test_a_quoted_key_is_text() -> None:
    """Quoting is the fix the refusal names, so it must be enough."""
    block = yaml.safe_load('"No": a\n"2.10": b\n"010": c')
    assert _require_mapping(block, "display_names.overrides.Risk") == {
        "No": "a", "2.10": "b", "010": "c",
    }


def test_an_empty_mapping_is_accepted() -> None:
    """`{}` is this structure with zero entries, which the shipped mappings
    write deliberately. The guard is about SHAPE, never about emptiness."""
    assert _require_mapping({}, "mapping.enum_sources") == {}


def test_an_absent_section_reads_as_empty() -> None:
    """A commented-out or blank key yields None, and every mapping that omits
    an optional section relies on that meaning absent."""
    assert _require_mapping(None, "mapping.forms") == {}


def test_a_required_section_present_with_no_value_is_refused() -> None:
    """`entities:` with nothing under it cannot build. Accepting it as `{}`
    made the build die later on an error naming --site-role, a flag that was
    never the problem."""
    with pytest.raises(
        MappingShapeError, match="required, but the key is present with no value",
    ):
        _require_mapping(None, "mapping.entities", allow_absent=False)


def test_an_empty_list_is_refused_rather_than_coerced() -> None:
    """The defect this guard exists for. `[]` is falsy, so the `or {}` these
    sections were written with loaded the section as absent and reported
    nothing."""
    with pytest.raises(MappingShapeError, match="expected a mapping of names, got list"):
        _require_mapping([], "mapping.enum_sources")


def test_a_populated_list_is_refused_before_it_reaches_items() -> None:
    """A list reaching `.items()` raises AttributeError, which the CLI
    deliberately does not catch, so the admin saw twenty lines of loader
    internals."""
    with pytest.raises(MappingShapeError, match="expected a mapping of names, got list"):
        _require_mapping([{"Risk": {}}], "mapping.entities")


def test_the_mapping_refusal_names_the_section() -> None:
    """The context is the whole point: it tells the author which key to fix."""
    with pytest.raises(MappingShapeError, match=r"mapping\.views\.Risk:"):
        _require_mapping("Risks", "mapping.views.Risk")


def test_known_keys_are_accepted() -> None:
    """A block using only declared keys passes, and comes back untouched.

    The guard reads; it must never normalise or drop a key on the way.
    """
    block = {"title": "Risks"}
    _reject_unknown_keys(block, {"title", "slug"}, "mapping.views")
    assert block == {"title": "Risks"}


def test_a_subset_of_the_known_keys_is_accepted() -> None:
    """Optional keys stay optional. The guard refuses unknown keys, never
    missing ones."""
    block: dict[str, object] = {}
    _reject_unknown_keys(block, {"title", "slug"}, "mapping.views")
    assert block == {}


def test_an_unknown_key_is_refused_and_named() -> None:
    """A typo'd key must not be byte-identical to a deleted one: `deafult:`
    silently never made a view the default."""
    with pytest.raises(UnknownMappingKeyError, match=r"unknown key\(s\) \['deafult'\]"):
        _reject_unknown_keys({"deafult": True}, {"default"}, "mapping.views.Risk")


def test_the_refusal_lists_the_known_keys() -> None:
    """Naming the unknown key alone leaves the author guessing at the right
    spelling, which is the mistake they just made."""
    with pytest.raises(UnknownMappingKeyError, match=r"known: \['default', 'title'\]"):
        _reject_unknown_keys({"nope": 1}, {"title", "default"}, "mapping.views.Risk")


def test_several_unknown_keys_are_all_named_and_sorted() -> None:
    """Reporting one at a time turns a three-typo block into three builds."""
    with pytest.raises(UnknownMappingKeyError, match=r"unknown key\(s\) \['a', 'b', 'c'\]"):
        _reject_unknown_keys({"c": 1, "a": 2, "b": 3}, {"title"}, "mapping.views")


def test_a_non_mapping_block_is_refused_by_the_key_guard_too() -> None:
    """`set(block)` over a string would iterate characters and compare them
    against the allowed keys, which refuses or accepts for the wrong reason."""
    with pytest.raises(MappingShapeError, match="expected a mapping, got str"):
        _reject_unknown_keys("title", {"title"}, "mapping.views.Risk")


def test_the_allowed_set_may_be_a_frozenset() -> None:
    """Every caller in `analysis/styles.py` passes a module-level frozenset."""
    block = {"title": 1}
    _reject_unknown_keys(block, frozenset({"title"}), "ctx")
    assert block == {"title": 1}


def test_a_key_that_is_not_text_is_refused_before_the_unknown_keys() -> None:
    """An unknown key named as False does not tell the author they typed `No:`,
    and sorting 2026 beside a text key raised a bare TypeError before that."""
    with pytest.raises(MappingShapeError) as err:
        _reject_unknown_keys({2026: "a", "b": 2}, {"title"}, "mapping.views")
    assert str(err.value) == (
        "mapping.views: key 2026 is not text (YAML read it as int); quote it"
    )


def test_known_keys_returns_the_block_it_checked() -> None:
    """The same object, typed by what the guard proved, so callers index it."""
    block = {"title": "Risks"}
    assert _known_keys(block, {"title"}, "mapping.views") is block


def test_known_keys_refuses_what_the_guard_refuses() -> None:
    with pytest.raises(MappingShapeError, match="expected a mapping, got list"):
        _known_keys(["title"], {"title"}, "mapping.views.Risk")
    with pytest.raises(UnknownMappingKeyError, match=r"unknown key\(s\) \['deafult'\]"):
        _known_keys({"deafult": True}, {"default"}, "mapping.views.Risk")
