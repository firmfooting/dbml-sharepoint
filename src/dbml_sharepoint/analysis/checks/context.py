# src/dbml_sharepoint/analysis/checks/context.py
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
from typing import NamedTuple

from dbml_sharepoint.analysis.list_description import family_for
from dbml_sharepoint.analysis.lookups import lookup_display_columns, lookup_target_entities
from dbml_sharepoint.analysis.reporting.plan import (
    VALIDATION_TIME_ZONE,
    ListPlan,
    build_plans,
)
from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES, supports_unique
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import EnumDef, Schema, Table


class IndexTarget(NamedTuple):
    """One representable `indexes { }` entry: where it is declared and what it names."""

    # Position in Table.indexes counting every entry, composite ones included,
    # because that is the number `indexes[n]` renders in a finding's location.
    position: int
    column: str


@dataclass(frozen=True)
class ValidationContext:
    """Schema, mapping, and the indexes over them that checks share.

    Construct with :meth:`build` rather than by hand, because the indexes
    must agree with each other.
    """

    schema: Schema
    bundle: MappingBundle
    # The family the emitter stamps into every list Description, resolved
    # once from the same helper `generators.jsgen` uses.
    family: str = ""
    table_names: set[str] = field(default_factory=set)
    tables_by_name: dict[str, Table] = field(default_factory=dict)
    enum_by_name: dict[str, EnumDef] = field(default_factory=dict)
    enum_members_by_name: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Columns expanded to a Choice+URL pair rather than deployed as declared,
    # so a check asking "is this column rendered?" must consult this too.
    cross_site_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # The same declarations keyed as (entity, column). Checks that ask "is THIS
    # column cross-site?" need the pair: a cross-site ref and a real lookup can
    # both point out of the same entity, and only the first is exempt.
    cross_site_pairs: set[tuple[str, str]] = field(default_factory=set)
    # The entities a real Lookup points at, built here so every check reads
    # one value. A second derivation once told a list reached only by a
    # cross-site ref, which has no picker, that its picker would stop working.
    lookup_targets: set[str] = field(default_factory=set)
    # {entity: calculated column names}. Derived once here rather than in
    # each check, so no two of them can disagree about what "calculated"
    # means, which is the whole point of this object.
    calculated_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # {entity: projected field names}. A lookup's projected (dependent)
    # fields are synthetic read-only Lookup columns named ``{column}{target}``;
    # they exist on the list so a view can render the target's real value,
    # but they are not DBML columns. Kept here so the view renderability check
    # and the projection declaration check agree on the generated name.
    projected_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # The one derivation of which columns the schema indexes, in declaration
    # order. Every rule that reports on an `indexes { }` entry reads this, so
    # a rule and the ceiling below can never disagree about what counts.
    index_targets_by_entity: dict[str, list[IndexTarget]] = field(default_factory=dict)
    # Effective SharePoint indexes declared by the schema: bare DBML
    # indexes plus the implicit index SharePoint creates for a supported
    # [unique] column. The set form of `index_targets_by_entity` above. Kept
    # here because both the per-list index ceiling and filtered-view safety
    # checks must use exactly the same accounting.
    explicit_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)
    unique_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # {entity: the display column folded into effective_indexes below}. Kept
    # so the over-budget error can NAME the implicit twenty-first index rather
    # than leave an author counting twenty and finding no explanation.
    display_index_by_entity: dict[str, str] = field(default_factory=dict)
    effective_indexes_by_entity: dict[str, set[str]] = field(default_factory=dict)
    # {site_role: {entity: plan}}, or None for a role the planner refused.
    # Two families read the report query's columns off this rather than
    # deriving them again: `_naming` for a declared column landing on a name
    # the pack adds, `_derived` for what an expression may reference. Every
    # condition the planner refuses (an unmapped column type, a multi-value
    # member holding the export separator, a projection the schema lacks, an
    # unknown zone) is a finding of its own elsewhere, so a refused role
    # reads as "nothing to say here" rather than as an error of this
    # object's.
    report_plans_by_role: dict[str, dict[str, ListPlan] | None] = field(
        default_factory=dict,
    )

    @classmethod
    def build(cls, schema: Schema, bundle: MappingBundle) -> "ValidationContext":
        cross_site_by_entity: dict[str, set[str]] = {}
        cross_site_pairs: set[tuple[str, str]] = set()
        for xref in bundle.mapping.cross_site_reference_columns:
            cross_site_by_entity.setdefault(xref.entity, set()).add(xref.column)
            cross_site_pairs.add((xref.entity, xref.column))
        lookup_targets = lookup_target_entities(schema, cross_site_pairs)
        family = family_for(schema)
        enum_names = {e.name for e in schema.enums}
        index_targets_by_entity = {
            table.name: [
                IndexTarget(position, index.columns[0])
                for position, index in enumerate(table.indexes)
                if len(index.columns) == 1
            ]
            for table in schema.tables
        }
        explicit_indexes_by_entity = {
            name: {target.column for target in targets}
            for name, targets in index_targets_by_entity.items()
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
        projected_by_entity: dict[str, set[str]] = {}
        for entity, cols in bundle.mapping.lookup_projections.items():
            names: set[str] = set()
            for column, targets in cols.items():
                for target in targets:
                    names.add(f"{column}{target}")
            projected_by_entity[entity] = names
        # A lookup's picker enumerates its target list, and past the 5,000-item
        # threshold that enumeration is refused unless the displayed column is
        # indexed, so this index is not optional and it spends a real slot.
        # Folded in HERE rather than checked separately so the existing
        # 20-index ceiling counts it: a schema declaring twenty and needing a
        # twenty-first fails at validate time, before anything is deployed.
        # A cross-site ref is excluded: it is a Choice + URL pair, so no far-side
        # list is enumerated and there is no picker to buy an index for.
        display_columns = lookup_display_columns(
            schema, bundle.mapping.entities, calculated_by_entity, cross_site_pairs,
        )
        report_plans_by_role: dict[str, dict[str, ListPlan] | None] = {}
        for role in sorted({e.site_role for e in bundle.mapping.entities.values()}):
            try:
                plans = build_plans(schema, bundle, role, time_zone=VALIDATION_TIME_ZONE)
            except ValueError:
                report_plans_by_role[role] = None
            else:
                report_plans_by_role[role] = {plan.entity: plan for plan in plans}
        return cls(
            schema=schema,
            bundle=bundle,
            family=family,
            table_names={t.name for t in schema.tables},
            tables_by_name={t.name: t for t in schema.tables},
            enum_by_name={e.name: e for e in schema.enums},
            enum_members_by_name={
                enum.name: tuple(enum.members) for enum in schema.enums
            },
            cross_site_by_entity=cross_site_by_entity,
            cross_site_pairs=cross_site_pairs,
            lookup_targets=lookup_targets,
            calculated_by_entity=calculated_by_entity,
            projected_by_entity=projected_by_entity,
            index_targets_by_entity=index_targets_by_entity,
            explicit_indexes_by_entity=explicit_indexes_by_entity,
            unique_indexes_by_entity=unique_indexes_by_entity,
            display_index_by_entity=display_columns,
            report_plans_by_role=report_plans_by_role,
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

    def projected_columns(self, entity_name: str) -> set[str]:
        """Projected (dependent) field names on one entity, empty when none."""
        return self.projected_by_entity.get(entity_name, set())

    def effective_indexes(self, entity_name: str) -> set[str]:
        """Declared and implicit SharePoint indexes for one entity."""
        return self.effective_indexes_by_entity.get(entity_name, set())

    def index_targets(self, entity_name: str) -> list[IndexTarget]:
        """Every representable index one entity declares, in declaration order."""
        return self.index_targets_by_entity.get(entity_name, [])

    def report_plan(self, entity_name: str) -> ListPlan | None:
        """One entity's reporting plan, or None where no query exists for it.

        None for an entity the mapping does not declare (`_structure` reports
        that) and for one whose site role the planner refused (see
        `report_plans_by_role`).
        """
        entity = self.bundle.mapping.entities.get(entity_name)
        if entity is None:
            return None
        plans = self.report_plans_by_role.get(entity.site_role)
        return None if plans is None else plans.get(entity_name)
