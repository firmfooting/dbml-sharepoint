"""The fleet icon vocabulary. One home, so 102 form headers cannot drift.

These tests assert SHAPE, not existence. Whether a name is a real Fluent
icon is a question only the catalogue can answer, and the suite runs
offline — which is the whole argument for keeping the vocabulary small,
central and reviewed rather than letting each template name its own.
"""

import re

from dbml_sharepoint.analysis.icons import FLEET_ICONS


def test_the_vocabulary_is_a_frozenset_of_non_empty_names() -> None:
    assert isinstance(FLEET_ICONS, frozenset)
    assert FLEET_ICONS, "an empty vocabulary would make the sweep's membership check vacuous"
    assert all(isinstance(name, str) and name for name in FLEET_ICONS)


def test_names_are_pascal_case_fluent_identifiers() -> None:
    """Fluent MDL2 names are PascalCase letters only — no spaces, hyphens
    or separators. A name failing this is certainly wrong; one passing it
    may still be wrong, which is why admission requires a catalogue check.
    """
    bad = sorted(n for n in FLEET_ICONS if not re.fullmatch(r"[A-Z][A-Za-z]*", n))
    assert not bad, f"not Fluent icon identifiers: {bad}"


def test_the_five_names_that_were_invented_stay_out() -> None:
    """Regression on a real mistake, not a hypothetical one. All five were
    proposed for this set by inspection and none exists in the catalogue.
    They read as obviously real, so they are exactly the names a future
    author will reach for again.
    """
    invented = {
        "Calendar", "Key", "Flow", "Scales", "AddFriend",
        "Handshake", "Signature",
    }
    present = invented & FLEET_ICONS
    assert not present, (
        f"{sorted(present)} do not exist in Fluent MDL2 and render as a blank "
        f"header with no error anywhere. Check the catalogue before adding a name."
    )


def test_the_exemplar_icon_is_present() -> None:
    """risk-register ships Shield today, and the sweep asserts membership,
    so the vocabulary must already admit what the library uses."""
    assert "Shield" in FLEET_ICONS
