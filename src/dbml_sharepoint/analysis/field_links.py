# src/dbml_sharepoint/analysis/field_links.py
"""Which calculated columns a mapping hides from the form through the content type.

A calculated column cannot be hidden by ShowIn*Form or a formatter, only by
`Hidden` on its content type's field link, so the deploy and the assessment
both read this one answer.
"""

from dbml_sharepoint.model.mapping_types import FormVisibility, Mapping


def is_hidden(declared: FormVisibility) -> bool:
    return not declared.new and not declared.existing and declared.when is None


def hidden_field_links(mapping: Mapping, entity: str) -> dict[str, bool]:
    """Calculated column -> the `Hidden` its field link must carry.

    Only an entity with a `form_visibility` block is managed. Inside one, an
    undeclared column is un-hidden (so removing a declaration reverts it),
    unless the block reconciles only what it lists.
    """
    section = mapping.form_visibility.get(entity)
    if section is None:
        return {}
    return {
        column: column in section.columns and is_hidden(section.columns[column])
        for column in mapping.calculated_formulas.get(entity, {})
        if section.reconcile == "exact" or column in section.columns
    }
