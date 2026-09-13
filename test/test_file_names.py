"""File and folder name rules, from Microsoft's own list.

Learn, "Restrictions and limitations in OneDrive and SharePoint" (read
2026-09-13): the characters `" * : < > ? / \\ |` are not allowed in a file or
folder name, nor is a leading or trailing space, nor a handful of reserved
names. Square brackets are not on the list, which is what lets `[DEMO]`
prefix a file name.
"""

import pytest

from dbml_sharepoint.analysis.file_names import invalid_file_name_reason


@pytest.mark.parametrize(
    "name",
    [
        "Clinical services",
        "[DEMO] Privacy and health records - 2026 Q3.docx",
        "a.b",
        "Executive and governance",
        "console",  # CON with more letters is an ordinary name
    ],
)
def test_a_legal_name_has_no_reason(name: str) -> None:
    assert invalid_file_name_reason(name) is None


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ('a"b', '"'),
        ("a*b", "*"),
        ("a:b", ":"),
        ("a<b", "<"),
        ("a>b", ">"),
        ("a?b", "?"),
        ("a/b", "/"),
        ("a\\b", "\\"),
        ("a|b", "|"),
        (" lead", "leading"),
        ("trail ", "trailing"),
        ("", "empty"),
        ("CON", "reserved"),
        ("com3", "reserved"),
        ("LPT9.txt", "reserved"),
        (".lock", "reserved"),
        ("desktop.ini", "reserved"),
        ("forms", "reserved"),
        ("a_vti_b", "_vti_"),
        ("~$temp.docx", "~$"),
    ],
)
def test_an_illegal_name_names_the_rule_it_breaks(name: str, fragment: str) -> None:
    reason = invalid_file_name_reason(name)
    assert reason is not None
    assert fragment in reason
