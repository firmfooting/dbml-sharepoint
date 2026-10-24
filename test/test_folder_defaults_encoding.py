# test/test_folder_defaults_encoding.py
"""The spelling of each folder default value in the location-based defaults file.

Each expected text is the form the receiver was measured to apply
(`library.folder-defaults.value.*`).
"""

import pytest

from dbml_sharepoint.analysis.folder_defaults import encode_folder_default, person_logins
from dbml_sharepoint.model.mapping_types import FolderDefaultValue

_A = "i:0#.f|membership|a@contoso.com"
_B = "i:0#.f|membership|b@contoso.com"


@pytest.mark.parametrize(("column_type", "value", "text"), [
    ("nvarchar", 'North & "Q"', 'North & "Q"'),
    ("division", "Corporate", "Corporate"),
    ("division[]", ("Red", "Blue"), "Red;#Blue"),
    ("division[]", "Blue", "Blue"),
    ("person", "a@contoso.com", f"-1;#{_A}"),
    ("person[]", ("a@contoso.com", "b@contoso.com"), f"-1;#{_A};#-1;#{_B}"),
    ("boolean", True, "1"),
    ("boolean", False, "0"),
    ("boolean", "TRUE", "1"),
    ("boolean", "0", "0"),
    ("number", "1234.5", "1234.5"),
    ("date", "today", "[today]"),
    ("datetime", "2026-03-14T13:00:00Z", "2026-03-14T13:00:00Z"),
    ("hyperlink", "https://example.com, Example", "https://example.com, Example"),
])
def test_each_value_is_spelled_as_the_receiver_applies_it(
    column_type: str, value: FolderDefaultValue, text: str,
) -> None:
    assert encode_folder_default(column_type, value) == text


def test_only_person_values_carry_logins_to_resolve() -> None:
    assert person_logins("person[]", ("a@contoso.com", "b@contoso.com")) == [_A, _B]
    assert person_logins("nvarchar", "a@contoso.com") == []
