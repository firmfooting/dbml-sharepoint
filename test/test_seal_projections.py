# test/test_seal_projections.py
"""A projected lookup column is sealed like every other column this tool owns.

It was not, and the omission was never argued. `_lookups.js.j2` says a
projection is "checked for existence only, never reconciled" because a
read-only field does not drift, which is a statement about RECONCILIATION.
Sealing answers a different question: whether a site owner can delete the
column through the UI. Measured on a live site 2026-09-06, all seven
projections in `programme-governance` read back `Sealed: false` and
`CanBeDeleted: true`, while every declared and calculated column on the same
lists read `Sealed: true` and `CanBeDeleted: false`.

Deleting one takes the view that shows it with no warning anywhere.
"""

from pathlib import Path
from typing import Any

import dbml_sharepoint
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

FAMILY = Path(dbml_sharepoint.__file__).parent / "solutions" / "programme-governance"

_FIXED_ARGS: dict[str, Any] = {
    "site_url": "https://example.sharepoint.com/sites/test",
    "site_role": "default",
    "source_dbml": "schema.dbml",
    "source_mtime": "2026-09-06T00:00:00Z",
    "generated_at": "2026-09-06T00:00:00Z",
}


def _family_deploy_js() -> str:
    """The real family, because it is what carries projections in the fleet."""
    return generate_deploy_js(
        schema=parse_dbml(FAMILY / "10-design" / "schema.dbml"),
        bundle=load_mapping(FAMILY / "20-configure" / "mapping.yaml"),
        release=load_release(FAMILY / "20-configure" / "release.yaml"),
        **_FIXED_ARGS,
    )


def test_the_family_still_ships_projections() -> None:
    """The premise of every assertion below. If projections stopped being
    emitted, the seal tests would pass by having nothing to seal."""
    js = _family_deploy_js()
    assert '"projections"' in js
    assert "RelatedRiskTitle" in js


def test_the_seal_phase_enumerates_projections() -> None:
    """The gap itself. `sealDeclared` was built from `fields_phase1`, from each
    phase-2 lookup's own field, and from the built-in Titles PREPARE opened.
    A projection is in none of those three, so it never reached the phase that
    seals, batches and verifies.
    """
    js = _family_deploy_js()
    # The phase body only, so a mention anywhere else in a 180,000-character
    # script cannot pass this.
    seal_phase = js[js.index("seal declared columns"):][:12000]
    assert "projections" in seal_phase, (
        "the seal phase does not mention projections, so a projected lookup "
        "is still left unsealed and deletable through the UI"
    )
