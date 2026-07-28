# src/dbml_sharepoint/analysis/checks/_context.py
"""Derived lookups shared by every mapping check.

Each check family needs the same handful of indexes over the schema and the
mapping. Building them once here keeps the individual checks readable and
stops two of them disagreeing about how a lookup is derived.

Everything on this object is a pure derivation of ``schema`` and ``bundle``.
Nothing accumulates across checks: a check reports findings, it never
mutates the context. That is what lets the checks run in any order and be
tested one at a time.
"""

from dataclasses import dataclass, field

from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import EnumDef, Schema, Table


@dataclass(frozen=True)
class ValidationContext:
    """Schema, mapping, and the indexes over them that checks share.

    Construct with :meth:`build` rather than by hand — the indexes must
    agree with each other.
    """

    schema: Schema
    bundle: MappingBundle
    table_names: set[str] = field(default_factory=set)
    tables_by_name: dict[str, Table] = field(default_factory=dict)
    enum_by_name: dict[str, EnumDef] = field(default_factory=dict)
    # Columns expanded to a Choice+URL pair rather than deployed as declared,
    # so a check asking "is this column rendered?" must consult this too.
    cross_site_by_entity: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, schema: Schema, bundle: MappingBundle) -> "ValidationContext":
        cross_site_by_entity: dict[str, set[str]] = {}
        for xref in bundle.mapping.cross_site_reference_columns:
            cross_site_by_entity.setdefault(xref.entity, set()).add(xref.column)
        return cls(
            schema=schema,
            bundle=bundle,
            table_names={t.name for t in schema.tables},
            tables_by_name={t.name: t for t in schema.tables},
            enum_by_name={e.name: e for e in schema.enums},
            cross_site_by_entity=cross_site_by_entity,
        )

    def cross_site_columns(self, entity_name: str) -> set[str]:
        """Cross-site reference columns declared on one entity."""
        return self.cross_site_by_entity.get(entity_name, set())
