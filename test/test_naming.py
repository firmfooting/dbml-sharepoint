"""The slug, kebab and file stem rules dependents share."""

import pytest

from dbml_sharepoint.generators.extractgen import list_slug
from dbml_sharepoint.naming import file_stem, kebab, slug


@pytest.mark.parametrize(
    ("text", "expected"), [("Risk Log", "risk-log"), ("  a__b  ", "a-b"), ("RiskLog", "risklog")]
)
def test_slug(text: str, expected: str) -> None:
    assert slug(text) == expected


def test_slug_with_underscores() -> None:
    assert slug("Owner assignment", sep="_") == "owner_assignment"


def test_slug_refuses_another_separator() -> None:
    with pytest.raises(ValueError, match="sep"):
        slug("Risk Log", sep=".")


@pytest.mark.parametrize("text", ["", "---", "Café"[3:], "日本"])
def test_a_slug_that_names_nothing_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="names nothing"):
        slug(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("MutedText", "muted-text"), ("muted text", "muted-text"), ("HTTPStatus", "httpstatus")],
)
def test_kebab(text: str, expected: str) -> None:
    assert kebab(text) == expected


def test_file_stem_is_the_extract_rule() -> None:
    assert file_stem("Risk Log") == "Risk-Log"
    assert file_stem("日本") == ""
    assert list_slug("Risk Log") == file_stem("Risk Log")
