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

from dbml_sharepoint.analysis.sidecars import (
    CENTRAL_LOG_COLUMNS,
    EXTERNAL_LOG_DEFAULT,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
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
    """`CENTRAL_LOG_COLUMNS` is what a full stamp POSTs. A column the family
    does not declare is a field SharePoint rejects, which degrades to an INFO
    line rather than failing anything."""
    declared = {column.name for column in _table().columns}
    missing = sorted(set(CENTRAL_LOG_COLUMNS) - declared)
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
    extra = sorted(declared - set(CENTRAL_LOG_COLUMNS) - _PROVIDED)
    assert not extra, (
        f"deployment-log declares {extra}, which no stamp fills. Either add "
        "the field to CENTRAL_LOG_COLUMNS and the stamp body, or drop the "
        "column."
    )


def test_the_stamp_kinds_are_the_ones_the_deploy_sends() -> None:
    """`StampKind` is a CHOICE column, so a member the deploy does not send is
    dead, and a kind the deploy sends that is not a member is refused at save.

    Read out of the logging template rather than restated, because restating
    them here would pin this file against itself. If the extraction stops
    finding four kinds the template has been restructured, and that is a
    failure worth looking at rather than a pass worth having.
    """
    text = LOGGING_TEMPLATE.read_text(encoding="utf-8")
    sent = set(_KIND_AT_CALL.findall(text))
    for pair in _KIND_IN_TERNARY.findall(text):
        sent.update(pair)
    assert len(sent) == 4, (
        f"found {sorted(sent)} in {LOGGING_TEMPLATE.name}, not the four stamp "
        "kinds. The template has been restructured; re-read it and fix the "
        "patterns above rather than the count."
    )
    (enum,) = parse_dbml(FAMILY / "10-design" / "schema.dbml").enums
    assert set(enum.members) == sent, (
        f"deployment-log offers {sorted(enum.members)} and the deploy sends "
        f"{sorted(sent)}. A kind SharePoint does not offer is refused at save."
    )
