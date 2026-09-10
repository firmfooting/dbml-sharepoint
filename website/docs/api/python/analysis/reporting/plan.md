---
title: plan
sidebar_position: 31
---

# `dbml_sharepoint.analysis.reporting.plan`

*the reporting plan: what each list's queries carry, as data*

The reporting plan: what each list's queries carry, as data.

Everything here is a pure derivation of ``(schema, bundle, site_role)``
that returns data. Text written to a file, or a fragment of one such as a
line of M, a SQL statement or a markdown row, belongs to a renderer under
``generators/``, and those are split by the escaping function the text
needs. That rule decides where a function lives. A type token such as
``"type text"`` or ``"NVARCHAR(255)"`` is data and sits on a plan; a line of
a query is not.

The plan lives under ``analysis/`` so a validator check can read the same
derivation the renderers do rather than keep its own copy in step with
them. ``AGENTS.md`` names ``analysis/joins.py`` as the worked example of a
fact both sides need, and a generator must never import from
``analysis/checks/``.

### `DerivedStep`

```python
@dataclass
class DerivedStep:
    kind: str
    name: str = ''
    m_type: str = ''
    m: str = ''
    replace: bool = False
    hidden: bool = False
    description: str = ''
    source_query: str = ''
    source_entity: str = ''
    own_key: str = ''
    other_key: str = ''
    picks: tuple[tuple[str, str, str], ...] = ()
    aggregate: str = ''
    column: str = ''
    where: str = ''
```

One derived column, with every name already resolved.

Built in a POST-PASS over the plans, because a join has to translate the
columns it reads through the TARGET query's own rename map, and that map
only exists once the target's plan does. Reading the map rather than
re-deriving the display title is the point: it is the rename the target
query actually performs, so the two cannot disagree.

### `ListPlan`

```python
@dataclass
class ListPlan:
    entity: str
    list_title: str
    selects: list[str] = field(default_factory=list)
    expands: list[str] = field(default_factory=list)
    record_expands: list[tuple[str, str, str, str]] = field(default_factory=list)
    m_types: list[tuple[str, str]] = field(default_factory=list)
    multi_value_joins: list[tuple[str, bool]] = field(default_factory=list)
    output_columns: list[str] = field(default_factory=list)
    sql_columns: list[tuple[str, str]] = field(default_factory=list)
    joins: list[tuple[str, str, str, tuple[str, ...]]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    item_url_path: str = ''
    item_url_suffix: str = ''
    renames: list[tuple[str, str]] = field(default_factory=list)
    field_internal_names: list[str] = field(default_factory=list)
    person_columns: list[str] = field(default_factory=list)
    users_table: bool = False
    zone: dbml_sharepoint.analysis.timezones.ZoneTable | None = None
    derived: list[dbml_sharepoint.analysis.reporting.plan.DerivedStep] = field(default_factory=list)
```

Everything the renderers need for one list, in DBML column order.

### `tables_for_role`

```python
def tables_for_role(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> list[dbml_sharepoint.model.parser.Table]
```

Schema-order tables mapped to the requested site role.

The MEMBERSHIP question is `ordering.is_deployed_here`, shared with the
generators that deploy: an entity absent from the mapping or belonging to
another role is not provisioned at this site, so it must not be reported
there either. Only the ORDER differs (declaration order here, dependency
order there), and a report has no creation sequence to respect.

This used to re-implement the predicate and say "same filter as jsgen" in
its docstring, which is a claim nothing checked.

### `refuse_ambiguous_members`

```python
def refuse_ambiguous_members(column: str, members: list[str]) -> None
```

Refuse a choice set the joined cell could not be split back into.

A BACKSTOP, not the primary control. `MULTI_VALUE_MEMBER_CONTAINS_THE_
EXPORT_SEPARATOR` is the rule an author should meet, and `build` reaches
it before this can fire.

This exists because `report` does not validate. It is a supported
command with no site URL, it renders straight from the schema, and
without this guard it emits a Power Query cell joined on `"; "` from
members that themselves contain `"; "` -- while the data dictionary
beside it tells the reader to split on that string. The artifact is
well-formed, the command exits 0, and any count taken from the export
is wrong with nothing able to notice.

So do NOT delete this on the reasoning that the validator now covers it.
It was deleted once for exactly that reason and `report` silently
started shipping the lossy bundle; the deletion was reverted with a test
(`test_report_refuses_a_member_the_export_cannot_split_back`) that fails
when it goes again. The knowledge is not duplicated -- both this and the
validator ask `analysis/exports.ambiguous_members`, which is the one
place the rule is written.

### `build_plans`

```python
def build_plans(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> list[dbml_sharepoint.analysis.reporting.plan.ListPlan]
```

### `TOLERANT_DATE_TYPES`

```python
TOLERANT_DATE_TYPES = frozenset({'type date'})
```

### `grouped_record_expands`

```python
def grouped_record_expands(plan: dbml_sharepoint.analysis.reporting.plan.ListPlan) -> list[tuple[str, list[tuple[str, str, str]]]]
```

`record_expands` gathered by source record column, first appearance
first. See `_render_m` for why one step per record is not optional.

### `tolerant_date_columns`

```python
def tolerant_date_columns(plan: dbml_sharepoint.analysis.reporting.plan.ListPlan) -> list[str]
```

The columns `AsDate` converts, and so whether the query reads the
site's time zone at all. Asked by the planner (which decides whether
`DateZoneResolved` is one of this list's columns) and by the renderer
(which writes the steps), so it cannot be answered differently twice.

### `reads_zone`

```python
def reads_zone(plan: dbml_sharepoint.analysis.reporting.plan.ListPlan) -> bool
```

Whether the query reads the site's zone, and so carries
`DateZoneResolved`: for a date-only column, or for a declared zone,
whose agreement check has nowhere else to surface. Asked by the planner
and by the renderer; `analysis/derived.py` answers the same for the
column list, and the family sweep in `test_derived_columns` holds the
two together.

