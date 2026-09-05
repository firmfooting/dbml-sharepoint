# src/dbml_sharepoint/analysis/sidecars.py
"""The tool-owned sidecar lists a deploy keeps, and their markers.

Two lists, one per site, created on every deploy, never deleted by this
tool:

- ``dbml Local Log`` records THIS run: a deployment start stamp, a
  deployment stop stamp, and provenance documentation naming what built
  the bundle, from which release, read at which time, by whom. Title
  carries the human-readable line, and ``RUN_LOG_STAMP_COLUMNS`` carries
  the same facts in columns a query can reach. A run log created before
  those columns existed is REUSED, so the deploy creates the ones it
  finds missing and degrades to a Title-only stamp if it cannot.

- ``dbml_Logs`` records CHANGES as type-2 slowly-changing-dimension rows:
  one row per change with the old value and the new value side by side,
  keyed by ``ChangeKey``. Hidden and insert-only from the deploy's point of
  view. The enterprise reader group holds Read on it so a Power Automate
  enterprise reader can pick rows up without touching the registers.

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

#: The external deployment log this tool appends to only when it already
#: exists. Probed, never created: its absence means the site does not run
#: one, and inventing it here would fight whoever owns it. Empty default:
#: nothing is probed unless the operator names a list.
EXTERNAL_LOG_DEFAULT = "dbml-deployment-log"

#: The CENTRAL logging site the external deployment log lives on, and the
#: default every build probes unless the operator names another. One site
#: per org collects every firmfooting application's deployment rows, so
#: cross-application reporting reads one list instead of visiting each
#: site. Probed, never created by a DEPLOY: a run that finds the site
#: absent notes that and carries on. Creating it is the sidecar's job,
#: because creating a whole site is a consent-shaped act, not a side
#: effect of provisioning a register.
CENTRAL_LOG_SITE_DEFAULT = "firmfooting-logging"

#: The title-only row the external log receives. The list belongs to its
#: operator and its schema is unknown, so the ONLY column every generic
#: list is guaranteed is Title. Anything richer would make this tool
#: refuse on somebody else's schema.
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


#: The central deployment log's marker. Same grammar, own name: the sidecar
#: owns the list by this Description compared whole, exactly like the
#: on-site sidecars.
def central_log_marker() -> str:
    """The exact Description the sidecar owns ``dbml-deployment-log`` by."""
    return scratch_marker_for(EXTERNAL_LOG_DEFAULT)


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
#: (no spaces in any title). ChangeKey carries the change key; EffectiveTo
#: and IsCurrent are the type-2 close; OldValue/NewValue are the payload the
#: Power Automate reader diffs.
#:
#: ``Indexed`` is part of the DECLARATION, not of the create body: the
#: template strips it before the POST and asserts it with the same field
#: MERGE `deploy/_indexes.js.j2` uses. A log created before a column was
#: declared indexed carries it unindexed, and only a MERGE reaches those.
#:
#: ChangeKey and IsCurrent are indexed because the type-2 close reads
#: ``$filter=ChangeKey eq '...' and IsCurrent eq true``, and BOTH sides of
#: an AND must be indexed for the filter to survive the 5,000-item list view
#: threshold. This list is deliberately unbounded: it gains a row per change
#: forever.
CHANGE_FIELDS: tuple[dict[str, object], ...] = (
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "ChangeKey",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Indexed": True,
        "Description": "The reporting row key this row belongs to.",
    },
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
        "__metadata": {"type": "SP.FieldBoolean"},
        "Title": "IsCurrent",
        "FieldTypeKind": 8,
        "Indexed": True,
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

#: The run log's stamp columns, in the same createField-body form as
#: `CHANGE_FIELDS` and created by the same probe/create/read-back loop.
#:
#: These exist because the run log is REUSED whenever its marker matches, and
#: the run logs already on live sites were created by a version of this phase
#: that gave the list nothing but Title. A stamp naming StampKind on one of
#: those is refused with HTTP 400 "The property 'StampKind' does not exist on
#: type 'SP.Data.Dbml_x0020_Local_x0020_LogListItem'" (live 2026-09-05).
#: The create body never carried them either, so a FRESH run log was in the
#: same state.
#:
#: The names are deliberately the central log's names minus the two that only
#: make sense across sites (SourceSite, DeployerVersion): one row shape reads
#: the same whether it was found on the site or in the central list. Nothing
#: is indexed, because this list holds two rows per run and is read by eye.
#:
#: Details is a Note to match `deployment-log`'s own `longtext` declaration,
#: with the same create-body shape jsgen builds for a Note column.
RUN_LOG_STAMP_COLUMNS: tuple[dict[str, object], ...] = (
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "StampKind",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "What this row records: deployment start, deployment stop or abort.",
    },
    {
        "__metadata": {"type": "SP.FieldDateTime"},
        "Title": "StampUtc",
        "FieldTypeKind": 4,
        "DateFormat": "DateTime",
        "Description": "When the stamp was written, in UTC.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "ReleaseTag",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The release this run deployed.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "SchemaVersion",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The schema version this run deployed.",
    },
    {
        "__metadata": {"type": "SP.FieldText"},
        "Title": "Operator",
        "FieldTypeKind": 2,
        "MaxLength": 255,
        "Description": "The account whose browser session ran the deploy.",
    },
    {
        "__metadata": {"type": "SP.FieldMultiLineText"},
        "Title": "Details",
        "FieldTypeKind": 3,
        "RichText": False,
        "NumberOfLines": 6,
        "AppendOnly": False,
        "Description": "What the run did: counts, and the site and role it ran against.",
    },
)
