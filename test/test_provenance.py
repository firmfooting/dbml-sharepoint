"""The one marker prefix every provisioned object opens with."""

from pathlib import Path

from dbml_sharepoint.analysis import group_description, list_description, provenance


def test_the_prefix_has_one_owner() -> None:
    assert provenance.MARKER_PREFIX == "Provisioned by dbml-sharepoint"


def test_the_group_marker_shapes_open_with_it() -> None:
    assert group_description.SHARED_MARKER.startswith(provenance.MARKER_PREFIX)
    assert group_description.FAMILY_MARKER_TEMPLATE.startswith(provenance.MARKER_PREFIX)


def test_the_list_marker_opens_with_it() -> None:
    assert list_description.MARKER_TEMPLATE.startswith(provenance.MARKER_PREFIX)


def test_only_provenance_and_prose_spell_the_prefix() -> None:
    """A second spelling is a second thing to change and one to forget.

    `finding_help.py` is exempt by name: it is operator-facing prose that
    quotes the marker to explain a finding, not a second definition of it.
    """
    root = Path(group_description.__file__).parent
    exempt = {"provenance.py", "finding_help.py"}
    offenders = [
        p.name
        for p in sorted(root.rglob("*.py"))
        if p.name not in exempt
        and "Provisioned by dbml-sharepoint" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"the prefix is spelled literally in: {offenders}"
