import pytest

from dbml_sharepoint.analysis.list_url import (
    list_url_key,
    list_url_path,
    server_relative,
)
from dbml_sharepoint.model.errors import MappingValueError


@pytest.mark.parametrize("declared", [
    "Lists/Mail Ledger", "/Lists/Mail Ledger", "Lists/Mail Ledger/",
    "Lists//Mail Ledger", " Lists/Mail Ledger ", "Lists\\Mail Ledger",
])
def test_every_spelling_gives_one_key(declared: str) -> None:
    assert list_url_key(declared) == "lists/mail ledger"
    assert list_url_path(declared) == "Lists/Mail Ledger"


def test_path_keeps_the_declared_case() -> None:
    assert list_url_path("/Lists/MailLedger/") == "Lists/MailLedger"


@pytest.mark.parametrize("bad", ["", "/", "Lists/a|b", "Lists/../x", "./x", "a\x00b"])
def test_unsafe_urls_are_refused(bad: str) -> None:
    with pytest.raises(MappingValueError):
        list_url_key(bad)


def test_server_relative_joins_the_site_path() -> None:
    assert server_relative("/sites/ops/", "Lists/Mail Ledger") == (
        "/sites/ops/Lists/Mail Ledger")
    assert server_relative("", "TaskRegisterV2") == (
        "/TaskRegisterV2")


def test_apostrophe_percent_and_mixed_case_are_kept_or_lowered() -> None:
    assert list_url_path("Lists/Bob's 100% List") == "Lists/Bob's 100% List"
    assert list_url_path("Lists/50%off") == "Lists/50%off"
    assert list_url_key("LISTS/Bob's mail LEDGER") == "lists/bob's mail ledger"


@pytest.mark.parametrize("bad", [
    "Lists/a%7Cb", "%2e%2e/x", "Lists/a%00b", "Lists%5C..%5CX", "Lists/Mail%20Ledger",
    "Lists/%FF", "Lists/%e2%82",
])
def test_any_percent_escape_is_refused_not_decoded(bad: str) -> None:
    with pytest.raises(MappingValueError):
        list_url_key(bad)


def test_server_relative_without_slashes_on_either_side() -> None:
    assert server_relative("sites/ops", "/Lists/X") == "/sites/ops/Lists/X"
