"""The export contract: what a joined cell is separated by, and what breaks it."""

from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN, ambiguous_members


def test_a_member_containing_the_separator_is_ambiguous() -> None:
    """`{"a; b"}` and `{"a", "b"}` join to the same text, so the export
    cannot be split back into what the row held."""
    assert ambiguous_members(["View", "Permission change; revoked"]) == [
        "Permission change; revoked",
    ]


def test_a_bare_semicolon_is_not_ambiguous() -> None:
    """The separator is `"; "` and only that. A member holding `;` joins and
    splits back perfectly well, and refusing it would cost a legitimate
    schema for a fault it does not have."""
    assert ambiguous_members(["Edit;Export", "View"]) == []


def test_every_offender_is_named_in_declaration_order() -> None:
    """The message lists them, so the caller must get all of them and in the
    order the author wrote them -- naming one of three sends somebody back
    round the loop twice."""
    assert ambiguous_members(["a; b", "ok", "c; d"]) == ["a; b", "c; d"]


def test_the_separator_is_the_one_the_export_actually_uses() -> None:
    """Pinned so the constant and the joined cell cannot drift apart."""
    assert MULTI_VALUE_JOIN == "; "
