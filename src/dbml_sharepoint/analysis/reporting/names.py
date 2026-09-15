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
