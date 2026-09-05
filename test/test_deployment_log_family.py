# test/test_deployment_log_family.py
"""The contract between the deployment-log family and every other deploy.

Every family's deploy stamps a central log it never creates. The address it
writes to is a list TITLE and a set of column INTERNAL NAMES, both literal
strings held in `analysis/sidecars.py` and rendered into the logging phase.
The `deployment-log` family is what provisions that list.

Nothing in a build can see the two sides disagree. A renamed column here
still deploys, the stamp still POSTs, and SharePoint answers 400 for a field
it does not know, which the logging phase degrades to an INFO line by design.
The result is a central log that quietly stops recording, on a surface whose
whole purpose is to notice things quietly stopping.

So the join is pinned here rather than trusted: the family declares the
columns the fleet writes, under the title the fleet writes to, with the
StampKind members the fleet sends.
"""

import re

from _paths import JINJA_TEMPLATES, SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.permissions import BUILT_IN_LEVELS
from dbml_sharepoint.analysis.sidecars import (
    CENTRAL_CHANGE_COLUMNS,
    CENTRAL_LOG_COLUMNS,
    EXTERNAL_LOG_DEFAULT,
)
from dbml_sharepoint.model.mapping_loader import expand_prefix, load_mapping
from dbml_sharepoint.model.mapping_types import PermissionsConfig
from dbml_sharepoint.model.parser import Table, parse_dbml

FAMILY = SOLUTION_TEMPLATES / "deployment-log"
LOGGING_TEMPLATE = JINJA_TEMPLATES / "deploy" / "_logging.js.j2"

#: The columns SharePoint provides on any list, so the family declares them
#: without them being part of the contract: `Id` is the identity column and
#: `Title` is the one column a Title-only stamp can rely on.
_PROVIDED = frozenset({"Id", "Title"})

#: `stampExternal('provenance', ...)` and its siblings: the stamp kinds the
#: logging phase names as literals at the call site.
_KIND_AT_CALL = re.compile(r"stamp(?:External|RunLog)\(\s*'([^']+)'")

#: `const kind = summary.errors.length > 0 ? 'abort' : 'deployment stop';`
#: The finish path chooses its kind and passes it as a variable, so the two
#: literals are only visible here.
_KIND_IN_TERNARY = re.compile(r"const kind = [^;]*\? '([^']+)' : '([^']+)'")

#: `const CHANGE_STAMP_KIND = 'change';` A central change row is a row on the
#: same list, told apart by StampKind, so the kind is a named constant the
#: writer reads rather than a literal at a call site.
_KIND_AS_CONSTANT = re.compile(r"const CHANGE_STAMP_KIND = '([^']+)'")

#: What a stamp row fills and a change row does not, and the reverse. The two
#: shapes share the stamp half; neither fills all eighteen columns, so the
#: contract is the UNION.
_ALL_CENTRAL_COLUMNS = frozenset(CENTRAL_LOG_COLUMNS) | frozenset(CENTRAL_CHANGE_COLUMNS)


def _table() -> Table:
    schema = parse_dbml(FAMILY / "10-design" / "schema.dbml")
    (table,) = schema.tables
    return table


def test_the_family_deploys_the_list_the_fleet_stamps() -> None:
    """The list title is `prefix + entity name`, and the fleet probes the
    literal. An empty prefix is a contract here, not a preference: a prefix
    renames the one list every other deploy is pointed at."""
    mapping = load_mapping(FAMILY / "20-configure" / "mapping.yaml").mapping
    (entity,) = mapping.entities
    assert mapping.prefix == "", (
        "deployment-log declares a prefix, so its list would deploy as "
        f"{mapping.prefix + entity!r} while every other family's deploy "
        f"probes {EXTERNAL_LOG_DEFAULT!r}."
    )
    assert mapping.prefix + entity == EXTERNAL_LOG_DEFAULT


def test_the_family_declares_every_column_the_fleet_writes() -> None:
    """`CENTRAL_LOG_COLUMNS` is what a full stamp POSTs and
    `CENTRAL_CHANGE_COLUMNS` is what a central change row POSTs. A column the
    family does not declare is a field SharePoint rejects, which degrades to an
    INFO line rather than failing anything -- and for the change columns it
    costs the whole feed, since the run refuses to write it to the site
    instead."""
    declared = {column.name for column in _table().columns}
    missing = sorted(_ALL_CENTRAL_COLUMNS - declared)
    assert not missing, (
        f"the fleet stamps {missing}, which deployment-log does not declare. "
        "Every stamp carrying one of those fields is refused by SharePoint "
        "and skipped with an INFO line."
    )


def test_the_family_declares_nothing_the_fleet_does_not_write() -> None:
    """The other direction, and it is not symmetry for its own sake.

    A column here that no stamp fills is a column that is always empty in the
    one list somebody reads to find out what happened. It would read as
    missing data rather than as a column nothing writes.
    """
    declared = {column.name for column in _table().columns}
    extra = sorted(declared - _ALL_CENTRAL_COLUMNS - _PROVIDED)
    assert not extra, (
        f"deployment-log declares {extra}, which no row fills. Either add "
        "the field to CENTRAL_LOG_COLUMNS or CENTRAL_CHANGE_COLUMNS and the "
        "body that writes it, or drop the column."
    )


def test_the_stamp_kinds_are_the_ones_the_deploy_sends() -> None:
    """`StampKind` is a CHOICE column, so a member the deploy does not send is
    dead, and a kind the deploy sends that is not a member is refused at save.

    Read out of the logging template rather than restated, because restating
    them here would pin this file against itself. If the extraction stops
    finding five kinds the template has been restructured, and that is a
    failure worth looking at rather than a pass worth having.

    Three extraction shapes, because the template spells its kinds three ways:
    at the call site, in the finish path's ternary, and as the named constant
    a central change row carries.
    """
    text = LOGGING_TEMPLATE.read_text(encoding="utf-8")
    sent = set(_KIND_AT_CALL.findall(text))
    for pair in _KIND_IN_TERNARY.findall(text):
        sent.update(pair)
    sent.update(_KIND_AS_CONSTANT.findall(text))
    assert len(sent) == 5, (
        f"found {sorted(sent)} in {LOGGING_TEMPLATE.name}, not the five stamp "
        "kinds. The template has been restructured; re-read it and fix the "
        "patterns above rather than the count."
    )
    (enum,) = parse_dbml(FAMILY / "10-design" / "schema.dbml").enums
    assert set(enum.members) == sent, (
        f"deployment-log offers {sorted(enum.members)} and the deploy sends "
        f"{sorted(sent)}. A kind SharePoint does not offer is refused at save."
    )


# --- The drop box: what a fleet operator may do to the log it writes to -----
#
# Every other family's deploy writes here as an ordinary Member of a site it
# does not own. That makes the level granted to the associated member group
# part of the SAME fleet contract as the column names above: widen it and
# every site in the fleet can rewrite the record of every other site.


def _permissions() -> PermissionsConfig:
    perms = load_mapping(FAMILY / "20-configure" / "mapping.yaml").mapping.permissions
    assert perms is not None
    return perms


#: The submit-only set, spelled out. Eight permissions, and the two that are
#: NOT here are the posture: without EditListItems and DeleteListItems a
#: contributor cannot change or remove a row, including one it wrote itself.
_SUBMIT_ONLY = frozenset({
    "AddListItems", "ViewListItems", "ViewVersions", "ViewFormPages",
    "Open", "ViewPages", "BrowseUserInfo", "UseRemoteAPIs",
})


def test_the_submit_only_level_grants_adding_and_no_changing() -> None:
    """The level is what the fleet writes through, so its shape is a contract.

    Asserted as an EQUALITY over the whole set rather than as two absences: a
    permission added here is one every site in the fleet gains over every
    other site's rows, and `not in` assertions would not see it.
    """
    (level,) = _permissions().levels
    assert set(level.base_permissions) == _SUBMIT_ONLY, (
        f"the submit-only level grants {sorted(set(level.base_permissions))}"
    )
    assert "EditListItems" not in level.base_permissions
    assert "DeleteListItems" not in level.base_permissions


def test_the_submit_only_level_expands_to_a_name_of_its_own() -> None:
    """`{prefix}` is mandatory on a declared level and this family has none.

    So the placeholder expands away and the level ships as a bare name, which
    has to be one no built-in level already uses -- a custom level colliding
    with a built-in cannot be created, and the deploy would fail on a site
    that is otherwise correct.

    The declaration is read from the file because the loader has already
    expanded it by the time it reaches the model, and `expand_prefix` strips
    the leading space rather than leaving one.
    """
    raw = (FAMILY / "20-configure" / "mapping.yaml").read_text(encoding="utf-8")
    assert '- name: "{prefix} dbml Log Submit Only"' in raw

    (level,) = _permissions().levels
    assert level.name == expand_prefix(
        "{prefix} dbml Log Submit Only", "", "permission_levels")
    assert level.name == "dbml Log Submit Only"
    assert level.name not in BUILT_IN_LEVELS


def test_the_member_binding_is_the_submit_only_level_and_a_replacement() -> None:
    """Members hold submit-only HERE and Edit everywhere else on the site.

    `reconcile: exact` is what makes that a replacement: the declared pairs
    are the allowlist and every other direct binding on the list is removed,
    so an Edit inherited from the site cannot survive alongside the grant that
    is supposed to narrow it. Without the exact mode the deploy would add
    submit-only and leave Edit in place, and the more permissive of two
    bindings is what SharePoint applies.
    """
    policy = _permissions().default_policy
    assert policy is not None
    assert policy.break_inheritance is True
    assert policy.reconcile_mode == "exact"
    members = [
        a for a in policy.assignments if a.principal.kind == "associated_member_group"
    ]
    (level,) = _permissions().levels
    assert [a.level for a in members] == [level.name]


def test_the_list_trims_reads_and_writes_to_the_caller_s_own_items() -> None:
    """The half a role assignment cannot express.

    ViewListItems is list-wide: without ReadSecurity 2 the submit-only level
    lets every contributor read the whole fleet's deployment history. The
    level and the setting are one posture and neither is meaningful alone.
    """
    mapping = load_mapping(FAMILY / "20-configure" / "mapping.yaml").mapping
    security = mapping.item_security_for("dbml-deployment-log")
    assert (security.read, security.write) == ("own", "own")
    assert (security.read_security, security.write_security) == (2, 2)
    assert mapping.declares_item_read_trimming()
