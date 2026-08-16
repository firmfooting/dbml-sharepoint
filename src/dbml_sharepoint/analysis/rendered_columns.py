# src/dbml_sharepoint/analysis/rendered_columns.py
"""Which columns a provisioned SharePoint list actually has.

Seven modules outside `validator.py` read `rendered_columns`, and
`analysis/joins.py` (which a generator may import, unlike `analysis/checks/`)
is one of them, so this is a shared fact rather than a private helper of the
orchestrator that happened to define it first. `checks/_views.py:965-988`
records what a second copy of the same three-term union cost: a dropped term
left the other spelling's callers unaffected and nothing compared them.

Nothing here may import from `analysis/checks/` or `analysis/validator.py`.
Both import this, so an edge back would move the cycle rather than close it.
"""

from dbml_sharepoint.model.parser import Table

# SharePoint system columns that exist on every list. Formatter [$Field]
# references and view/form field lists may name them; they are never
# DBML-declared. Deployer-managed sets (views, form_visibility,
# display_names) stay strict, as do list-validation formulas (SP support
# for system columns there is not relied on, so fail closed).
SYSTEM_COLUMNS = frozenset({"ID", "Created", "Modified", "Author", "Editor"})

# Columns that never reach the per-field deploy loop, so a per-field
# declaration on one is validated, reported and never written.
#
# The built-in Title is provisioned through its own patch object (jsgen
# routes it there and continues BEFORE the formula and formatter keys are
# attached), and the system columns are not DBML columns, so they are
# never in the field list at all. A declaration on any of them validated
# clean, the manifest reported "(none declared)", and the deploy wrote
# nothing: an asserted, validated, silently unenforced guarantee, which is
# the worst shape a data-quality rule can take.
#
# Supporting Title properly means threading the formulas through the patch
# path, a larger change than these sections warrant. Fail closed instead,
# and say why.
UNDEPLOYABLE_DECLARATION_COLUMNS = frozenset({"Title"}) | SYSTEM_COLUMNS


def undeployable(context: str, column: str) -> str:
    """The message for a declaration on a column the deploy never writes."""
    reason = (
        "the built-in Title column is provisioned through its own patch"
        if column == "Title"
        else f"{column} is a SharePoint system column, not a deployed field"
    )
    return (
        f"{context}: {column!r} cannot carry a per-column declaration -- "
        f"{reason}, so it never receives these properties. Declaring it here "
        f"would validate clean and deploy nothing."
    )


def rendered_columns(table: Table, cross_site_cols: set[str]) -> set[str]:
    """Column names that will actually exist on the provisioned SP list:
    auto-increment Id is skipped at render time, cross-site logical columns
    expand to <col>Abbreviation / <col>SiteUrl and never exist themselves."""
    rendered: set[str] = set()
    for col in table.columns:
        if col.name == "Id" and col.is_pk and col.is_auto_increment:
            # Skipped because SharePoint provides the identity column itself,
            # so the deploy must not create one. This used to add "SP indexes
            # Id natively" and was dropped, because nothing here has measured that
            # and Microsoft documents it nowhere; the 2026-07-30 native-index
            # probe found SP.Field.Indexed FALSE for ID on every list it read.
            # Nothing branches on the claim, which is why it was easy to leave
            # standing unexamined. See analysis/checks/_views.py.
            continue
        if col.name in cross_site_cols:
            rendered.add(col.name + "Abbreviation")
            rendered.add(col.name + "SiteUrl")
        else:
            rendered.add(col.name)
    return rendered
