# src/dbml_sharepoint/analysis/provenance.py
"""The one marker prefix every provisioned object opens with.

Three surfaces record provenance in a description: a site group, a list, and
a permission level. Each composes a different marker for its own
description budget, but all three must open with the same text, because that
text is what a human greps for to find everything this tool provisioned, and
what the deploy tests before deciding whether adopting an existing object is
safe. A second spelling of it would fail no build; it would just make one
object type invisible to a search that found the other two.
"""

#: The text every marker opens with. See `group_description.MARKER_PREFIX`
#: and `list_description.MARKER_TEMPLATE` for how each surface builds on it,
#: and why changing this string is not a cosmetic edit.
MARKER_PREFIX = "Provisioned by dbml-sharepoint"
