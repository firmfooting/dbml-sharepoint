"""Names shared by reporting artifacts and their operator instructions."""

import hashlib


def query_name(title: str) -> str:
    """Portable query basename, also used by cross-query references."""
    name = "".join(
        f"%{ord(c):02X}" if c in '%<>:"/\\|?*' or c < " " else c
        for c in title
    )
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved |= {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"}
    if name.split(".")[0].rstrip(" ").upper() in reserved:
        name = f"%{ord(name[0]):02X}" + name[1:]
    if len(name.encode("utf-8")) > 180:
        name = "%~" + name[:20] + hashlib.sha256(title.encode("utf-8")).hexdigest()
    return name


#: What a list's base function is called, after its query name.
BASE_SUFFIX = "_Base"


def base_query_name(title: str) -> str:
    """The function query that fetches one list's rows for a site URL.

    A query that reads another list calls this function rather than naming
    that list's query. The list query carries the list's reporting-only
    columns, and two lists whose reporting-only columns read each other
    would name each other, which in M is a cyclic reference that fails only
    at refresh. The base reads no other query, so no chain of reads can
    return to where it started. Reported 2026-09-18 against a
    programme-governance pack whose ten queries formed twelve such cycles.
    """
    return query_name(title) + BASE_SUFFIX
