# test/test_sidecar_field_bodies.py
"""The sidecar logs declare their columns in the same spelling the deploy uses.

`analysis/sidecars.py` writes create bodies by hand, and `jsgen` derives its
own from `analysis/typemap.py`. The two disagreed about exactly one field kind
and nothing in the build could see it: Boolean was `SP.FieldBoolean` in the
sidecars and `SP.Field` in the generator.

Live on 2026-09-06 that cost a site its change log. `IsCurrent` was refused
HTTP 400 on create, the loop abandoned `ReleaseTag` behind it, and the list
came out with eight of its ten columns, so the type-2 close had no way to mark
a current row and the phase refused to write any. The same site carries twelve
Boolean columns provisioned through the generator's spelling, three of them
indexed, so the spelling that works was already proven there.
"""

import pytest

from dbml_sharepoint.analysis.sidecars import CHANGE_FIELDS, RUN_LOG_STAMP_COLUMNS
from dbml_sharepoint.analysis.typemap import entity_type_for_type_kind

ALL_BODIES = [
    *[("CHANGE_FIELDS", body) for body in CHANGE_FIELDS],
    *[("RUN_LOG_STAMP_COLUMNS", body) for body in RUN_LOG_STAMP_COLUMNS],
]


@pytest.mark.parametrize(
    ("where", "body"), ALL_BODIES, ids=[f"{w}-{b['Title']}" for w, b in ALL_BODIES],
)
def test_a_sidecar_column_names_the_entity_type_the_deploy_uses(
    where: str, body: dict[str, object],
) -> None:
    """One authority for what a field kind is called over REST.

    A body that names its own subtype is a body that can drift from the one
    the generator sends, and the drift only shows up as an HTTP 400 on
    somebody's production site.
    """
    kind = body["FieldTypeKind"]
    assert isinstance(kind, int)
    declared = body["__metadata"]
    assert isinstance(declared, dict)
    assert declared["type"] == entity_type_for_type_kind(kind), (
        f"{where}.{body['Title']} names {declared['type']!r} for FieldTypeKind "
        f"{kind}, but the deploy creates that kind as "
        f"{entity_type_for_type_kind(kind)!r}"
    )


def test_the_boolean_spelling_is_the_one_proven_on_a_live_site() -> None:
    """Pinned by name because this is the pairing that broke.

    `SP.FieldBoolean` is not a type the AddField endpoint took. `SP.Field`
    with FieldTypeKind 8 is what every Boolean column this tool has ever
    provisioned was created with.
    """
    assert entity_type_for_type_kind(8) == "SP.Field"
