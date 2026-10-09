"""`identities`: the account slots a mapping declares and a build fills.

Shape only. Whether a name or a kind is acceptable is the validator's call
(IDENTITY_NAME_INVALID, IDENTITY_KIND_UNKNOWN), so one mapping reports every
fault at once rather than the first one the loader meets.
"""

from typing import Any

from dbml_sharepoint.model._keys import _known_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import IdentityDeclaration
from dbml_sharepoint.model.reading import optional_str_list, require_str
from dbml_sharepoint.model.sections.context import SectionContext

_IDENTITY_KEYS = frozenset({"description", "kinds"})


def read(sc: SectionContext) -> dict[str, Any]:
    raw = _require_mapping(sc.block("identities"), "identities")
    declared: dict[str, IdentityDeclaration] = {}
    for name, spec in raw.items():
        if not isinstance(name, str):
            raise MappingShapeError(f"identities: a name must be text, got {name!r}")
        context = f"identities.{name}"
        block = _known_keys(spec, _IDENTITY_KEYS, context)
        kinds = (
            ("user",) if block.get("kinds") is None
            else optional_str_list(block, "kinds", context)
        )
        declared[name] = IdentityDeclaration(
            name=name,
            description=require_str(block, "description", context),
            kinds=tuple(kinds),
        )
    return {"identities": declared}
