# src/dbml_sharepoint/analysis/file_names.py
"""File and folder name rules, from Microsoft's own list.

Learn, "Restrictions and limitations in OneDrive and SharePoint" (read
2026-09-13): these characters are not allowed in a file or folder name,
`" * : < > ? / \\ |`; a leading or trailing space is not allowed; the names
`.lock`, `CON`, `PRN`, `AUX`, `NUL`, `COM0` to `COM9`, `LPT0` to `LPT9`,
`desktop.ini` and any name starting `~$` are refused; `_vti_` may not appear
anywhere in a name; and `forms` is refused at the root of a library. Square
brackets are not on the list, which is why `[DEMO]` may prefix a file name.

Declared folders (`entities.<name>.folders`) and demonstration file names
(`demo_items[].file.name`) both go through this. Nothing here imports
anything, so checks and generators can both read it.
"""

import re

#: The characters Microsoft lists as not allowed in a file or folder name.
INVALID_CHARACTERS = frozenset('"*:<>?/\\|')

#: Names refused outright, compared without regard to case. `forms` is
#: refused only at a library root, which is where every declared folder and
#: every seeded file's folder sits, so it is refused here unconditionally.
_RESERVED = frozenset({
    ".lock", "con", "prn", "aux", "nul", "desktop.ini", "forms",
    *(f"com{digit}" for digit in range(10)),
    *(f"lpt{digit}" for digit in range(10)),
})

#: A device name with an extension (`LPT9.txt`) is still the device name.
_DEVICE_WITH_EXTENSION = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)\.", re.IGNORECASE)


def invalid_file_name_reason(name: str) -> str | None:
    """Why `name` cannot be a SharePoint file or folder name, or None."""
    if not name:
        return "the name is empty"
    bad = sorted(INVALID_CHARACTERS & set(name))
    if bad:
        return (
            f"the name contains {' '.join(bad)}, which SharePoint does not "
            f"allow in a file or folder name"
        )
    if name != name.strip(" "):
        side = "leading" if name.startswith(" ") else "trailing"
        return f"the name has a {side} space, which SharePoint does not allow"
    if name.lower() in _RESERVED or _DEVICE_WITH_EXTENSION.match(name):
        return f"{name!r} is a reserved name"
    if "_vti_" in name.lower():
        return "the name contains _vti_, which SharePoint reserves"
    if name.startswith("~$"):
        return "the name starts with ~$, which SharePoint reserves"
    return None
