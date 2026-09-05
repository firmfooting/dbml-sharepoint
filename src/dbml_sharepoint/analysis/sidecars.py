# src/dbml_sharepoint/analysis/sidecars.py
"""The tool-owned sidecar lists a deploy keeps, and their markers.

Two lists, one per site, created on every deploy, never deleted by this
tool:

- ``dbml Local Log`` records THIS run: a deployment start stamp, a
  deployment stop stamp, and provenance documentation naming what built
  the bundle, from which release, read at which time, by whom. Free text,
  no schema beyond Title, so the stamps stay human-readable in list
  settings and reporting. The STRUCTURED form of the same stamps is the
  central deployment log, which is a shipped template family rather than
  a hand-rolled sidecar.

- ``dbml_Logs`` records CHANGES as type-2 slowly-changing-dimension rows:
  one row per change with the old value and the new value side by side.
  Hidden and insert-only from the deploy's point of view. The enterprise
  reader group holds Read on it so a Power Automate enterprise reader can
  pick rows up without touching the registers.

Both follow the verify scratch list's ownership pattern: the marker in the
Description compared WHOLE, tool-owned (no family), fail closed on a list
of the same title that is not this tool's.
"""

from dbml_sharepoint.analysis import provenance

#: The run log. Unprefixed so it is greppable in the SharePoint UI exactly
#: as spelled, with the space: operators see "dbml Local Log" in list
#: settings next to every other list.
RUN_LOG_TITLE = "dbml Local Log"

#: The change log. Dotted so its REST identity is distinct from the run
#: log's, and so the Power Automate reader convention (one list per feed)
#: has a name that survives a copy between environments.
CHANGE_LOG_TITLE = "dbml_Logs"

#: The CENTRAL deployment log every deploy stamps when it can reach one.
#: Not created by a deploy: the list is what the `deployment-log` template
#: family provisions, so it exists because somebody deployed that family
#: to the central site. A deploy of any OTHER family probes this title and
#: appends; it never creates it, and never creates the site it sits on.
EXTERNAL_LOG_DEFAULT = "dbml-deployment-log"

#: The CENTRAL logging site the deployment log lives on, and the default
#: every build probes unless the operator names another. One site per org
#: collects every firmfooting application's deployment rows, so
#: cross-application reporting reads one list instead of visiting each
#: site. The SITE is created by hand (SharePoint start page, Create site):
#: this tool provisions lists, never sites. A deploy that finds the site
#: absent says so once and carries on.
CENTRAL_LOG_SITE_DEFAULT = "firmfooting-logging"

#: The prefix every stamp's Title carries, so a row is recognisable as this
#: tool's in a list somebody is reading by eye.
EXTERNAL_LOG_ROW_PREFIX = "dbml-sharepoint"

#: The stamp columns the `deployment-log` family declares on the central
#: list, and the ones a cross-web stamp fills when its probe finds them
#: all. Title alone is written when they are not: the operator may point
#: DBMLSP_DEPLOY_LOG_LIST at a list this tool did not provision, and Title
#: is the one column every generic SharePoint list has.
#:
#: Pinned against the family's own `schema.dbml` by
#: `test/test_deployment_log_family.py`, so the emitted stamp cannot drift
#: from the list it writes into.
CENTRAL_LOG_COLUMNS: tuple[str, ...] = (
    "StampKind", "StampUtc", "SourceSite", "ReleaseTag",
    "SchemaVersion", "DeployerVersion", "Operator", "Details",
)

#: `Hidden` on both sidecars. The run log exists so the stamps survive the
#: console closing; the change log exists for the reader. Neither belongs
#: in the site nav next to the registers people work in.
SIDECAR_HIDDEN = True


def run_log_marker() -> str:
    """The exact Description the deploy owns ``dbml Local Log`` by."""
    return provenance.marker_for_object(
        kind=provenance.SCRATCH_KIND, name=RUN_LOG_TITLE, family=None,
    )


def change_log_marker() -> str:
    """The exact Description the deploy owns ``dbml_Logs`` by."""
    return scratch_marker_for(CHANGE_LOG_TITLE)


def scratch_marker_for(title: str) -> str:
    """The tool-owned marker for a sidecar titled ``title``.

    ``--change-log-list`` renames the change log, and its marker has to
    follow: the marker is what the deploy compares WHOLE to decide the list
    is this tool's, so a renamed log owned by the default title's marker
    would be refused by the very next deploy.
    """
    return provenance.marker_for_object(
        kind=provenance.SCRATCH_KIND, name=title, family=None,
    )


def run_log_title() -> str:
    """The run log's title, for templates and tests to share."""
    return RUN_LOG_TITLE


def change_log_title() -> str:
    """The change log's title, for templates and tests to share."""
    return CHANGE_LOG_TITLE


#: The change log's columns, as createField bodies the logging phase POSTs
#: when the list is first created. Single source of truth: the template
#: renders these, so the runtime column set cannot drift from this
#: declaration. Internal names follow from the titles SharePoint assigns
#: (no spaces in any title). Title carries the change key; EffectiveTo and
#: IsCurrent are the type-2 close; OldValue/NewValue are the payload the
#: Power Automate reader diffs.
#:
#: The __metadata type names are load-bearing, measured live 2026-09-05
#: against dbml_Logs on firmfooting-logging: the verbose OData parser
#: refuses a metadata-less entry ("An entry without a type name was
#: found") and resolves only the type names its model knows. SP.FieldText
#: and SP.FieldDateTime resolve; SP.FieldBoolean does NOT (FieldTypeKind 8
#: must be announced as the base SP.Field); SP.Field resolves for anything
#: else. Change the type name and the field create 400s.
CHANGE_FIELDS: tuple[dict[str, object], ...] = (
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "ChangeKind",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "What changed: rename, create, permission.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "TargetName",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The list, level or group the change lands on.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "OldValue",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The value before the change; empty for a create.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "NewValue",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The value after the change.",
    },
    {
        "__metadata": {"type": "SP.FieldDateTime"},
        "Title": "EffectiveFrom",
        "FieldTypeKind": 4,
        "DateFormat": "DateTime",
        "Description": "When the change took effect.",
    },
    {
        "__metadata": {"type": "SP.FieldDateTime"},
        "Title": "EffectiveTo",
        "FieldTypeKind": 4,
        "DateFormat": "DateTime",
        "Description": "When the next change for this key took effect.",
    },
    {
        "__metadata": {"type": "SP.Field"},
        "Title": "IsCurrent",
        "FieldTypeKind": 8,
        "Description": "Whether this row is the current one for its key.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "ReleaseTag",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The release that made the change.",
    },
)
