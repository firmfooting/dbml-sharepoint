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

from dbml_sharepoint.analysis.lookups import lookup_display_columns
from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES, supports_unique
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
    # The same declarations keyed as (entity, column). Checks that ask "is THIS
    # column cross-site?" need the pair: a cross-site ref and a real lookup can
    # both point out of the same entity, and only the first is exempt.
    cross_site_pairs: set[tuple[str, str]] = field(default_factory=set)
    # {entity: calculated column names}. Derived once here rather than in
    # each check, so no two of them can disagree about what "calculated"
    # means — which is the whole point of this object.
    calculated_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # Effective SharePoint indexes declared by the schema: bare DBML
    # indexes plus the implicit index SharePoint creates for a supported
    # [unique] column. Kept here because both the per-list index ceiling and
    # filtered-view safety checks must use exactly the same accounting.
    explicit_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)
    unique_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)
    effective_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, schema: Schema, bundle: MappingBundle) -> "ValidationContext":
        cross_site_by_entity: dict[str, set[str]] = {}
        cross_site_pairs: set[tuple[str, str]] = set()
        for xref in bundle.mapping.cross_site_reference_columns:
            cross_site_by_entity.setdefault(xref.entity, set()).add(xref.column)
            cross_site_pairs.add((xref.entity, xref.column))
        enum_names = {e.name for e in schema.enums}
        explicit_indexes_by_entity = {
            table.name: {
                index.columns[0]
                for index in table.indexes
                if len(index.columns) == 1
            }
            for table in schema.tables
        }
        unique_indexes_by_entity = {
            table.name: {
                column.name
                for column in table.columns
                if (
                    column.unique
                    # SharePoint creates the built-in ID index itself; the
                    # declared identity column is not rendered by this tool.
                    and not (
                        column.name == "Id"
                        and column.is_pk
                        and column.is_auto_increment
                    )
                    # Cross-site logical columns expand to two companion
                    # fields, so the declared column itself never exists.
                    and column.name not in cross_site_by_entity.get(table.name, set())
                    and supports_unique(column, enum_names)
                )
            }
            for table in schema.tables
        }
        calculated_by_entity = {
            table.name: {
                col.name for col in table.columns
                if col.type in CALCULATED_TYPES
            }
            for table in schema.tables
        }
        # A lookup's picker enumerates its target list, and past the 5,000-item
        # threshold that enumeration is refused unless the displayed column is
        # indexed — so this index is not optional and it spends a real slot.
        # Folded in HERE rather than checked separately so the existing
        # 20-index ceiling counts it: a schema declaring twenty and needing a
        # twenty-first fails at validate time, before anything is deployed.
        # A cross-site ref is excluded: it is a Choice + URL pair, so no far-side
        # list is enumerated and there is no picker to buy an index for.
        display_columns = lookup_display_columns(
            schema, bundle.mapping.entities, calculated_by_entity, cross_site_pairs,
        )
        return cls(
            schema=schema,
            bundle=bundle,
            table_names={t.name for t in schema.tables},
            tables_by_name={t.name: t for t in schema.tables},
            enum_by_name={e.name: e for e in schema.enums},
            cross_site_by_entity=cross_site_by_entity,
            cross_site_pairs=cross_site_pairs,
            calculated_by_entity=calculated_by_entity,
            explicit_indexes_by_entity=explicit_indexes_by_entity,
            unique_indexes_by_entity=unique_indexes_by_entity,
            effective_indexes_by_entity={
                table.name: (
                    explicit_indexes_by_entity[table.name]
                    | unique_indexes_by_entity[table.name]
                    | ({display_columns[table.name]}
                       if table.name in display_columns else set())
                )
                for table in schema.tables
            },
        )

    def cross_site_columns(self, entity_name: str) -> set[str]:
        """Cross-site reference columns declared on one entity."""
        return self.cross_site_by_entity.get(entity_name, set())

    def effective_indexes(self, entity_name: str) -> set[str]:
        """Declared and implicit SharePoint indexes for one entity."""
        return self.effective_indexes_by_entity.get(entity_name, set())
