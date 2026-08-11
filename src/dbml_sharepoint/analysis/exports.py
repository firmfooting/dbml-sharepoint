"""What an exported multi-value cell is separated by, and what breaks it.

Both sides need this fact and neither owns it. `generators/reportgen.py`
joins a set with the separator; `analysis/validator.py` refuses a member
that contains it. `AGENTS.md` names the pattern -- where both sides
need the same fact, it lives in a shared module, `analysis/joins.py` being
the worked example -- and the alternative here was worse in both
directions: `analysis/` importing from `generators/` inverts the layering,
and putting a text separator in `typemap.py` puts an exported artifact's
spelling inside the module that answers what a DBML type IS.
"""

from collections.abc import Iterable

#: How the exported cell separates the members of a multi-value column.
#:
#: `", "` was rejected twice over: a member is a phrase rather than a token
#: (`Permission change`), so a comma reads as punctuation inside one, and a
#: comma in a cell is the character every CSV consumer downstream of a Power
#: BI export handles differently. A semicolon is what SharePoint itself puts
#: between members on the wire -- measured 2026-08-10, an `<Eq>` against the
#: `;#`-delimited string matched the whole set -- so it is the separator a
#: reader already associates with these columns.
MULTI_VALUE_JOIN = "; "


def ambiguous_members(members: Iterable[str]) -> list[str]:
    """Which of `members` make a joined cell impossible to split back.

    A set holding `"Permission change; revoked"` joins to the same text as
    one holding `"Permission change"` and `"revoked"`, so any count of
    selections taken from the export is wrong and nothing downstream can
    tell. Returned in declaration order, and all of them: naming one of
    three sends the author round the loop twice.

    Only `MULTI_VALUE_JOIN` itself. A bare `;` inside a member joins and
    splits back perfectly well.
    """
    return [member for member in members if MULTI_VALUE_JOIN in member]
