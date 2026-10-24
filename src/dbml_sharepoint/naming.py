"""Fold names to slugs, kebab case and file stems, one rule each."""

import re

_OUTSIDE_SLUG = re.compile(r"[^a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def slug(text: str, *, sep: str = "-") -> str:
    """``text`` lower-cased, each run outside ``[a-z0-9]`` turned into ``sep``.

    ``sep`` is ``-`` or ``_``. Raises ValueError when nothing is left, so a
    caller cannot name a file or a key with an empty string.
    """
    if sep not in ("-", "_"):
        raise ValueError(f"sep must be '-' or '_', not {sep!r}")
    result = _OUTSIDE_SLUG.sub(sep, text.lower()).strip(sep)
    if not result:
        raise ValueError(f"{text!r} names nothing once folded to [a-z0-9]")
    return result


def kebab(text: str) -> str:
    """``text`` split at camel case, then slugged: ``MutedText`` gives ``muted-text``.

    The split needs a lower-case letter or digit before the capital, so
    ``HTTPStatus`` gives ``httpstatus``.
    """
    return slug(_CAMEL_BOUNDARY.sub("-", text))


def file_stem(text: str) -> str:
    """``text`` folded to what a file name and a directory name share.

    Case is kept, each run outside ``[A-Za-z0-9._-]`` becomes ``-``, and
    ``-`` and ``.`` are stripped from both ends. Returns "" when nothing
    usable is left, which the caller answers for itself.
    """
    return _UNSAFE_IN_FILENAME.sub("-", text).strip("-.")
