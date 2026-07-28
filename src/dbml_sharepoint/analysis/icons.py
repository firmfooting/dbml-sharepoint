"""The fleet's Fluent icon vocabulary for form headers.

One home, for the same reason the calculated type vocabulary has one: a
name spread across a hundred formatter files drifts, and this particular
drift is invisible. SharePoint renders an unknown ``iconName`` as nothing
— no error in the build, no error in the deploy, nothing in the browser
console. The only witness is a person looking at the form.

That is not a hypothetical. The thirty-five names first proposed for this
set were chosen carefully and checked afterwards against the catalogue:
five did not exist. ``Calendar``, ``Key``, ``Flow``, ``Scales`` and
``AddFriend`` all read as obviously real and are not. The replacements
below (``CalendarDay``, ``Lock``, ``FlowChart``, ``Permissions``,
``PeopleAdd``) are.

``DocumentApproval``, ``ReportDocument`` and ``ContactLink`` were added by
the governance/risk/compliance theme branch and checked the same way — a
countersigned agreement, an acquittal report and a person's declared link
to an outside party are three things the original nine could only
approximate. ``Handshake`` and ``Signature``, the two names that came to
mind first for the contract register, do not exist.

Every member here was verified against Microsoft's published
MDL2 icon source, which is what SharePoint's ``iconName`` resolves against:
https://github.com/microsoft/fluentui/tree/master/packages/font-icons-mdl2/src

**Adding a name means checking it there first.** The test beside this
module asserts shape, not existence — an offline suite cannot check a
catalogue, which is precisely why this set is small, central and reviewed.
"""

# Grouped by the theme that reaches for them. The grouping is a reading
# aid only: any template may use any name, and the sweep checks membership
# in the whole set.
FLEET_ICONS: frozenset[str] = frozenset({
    # Governance, risk and compliance
    "Shield",
    "ComplianceAudit",
    "Certificate",
    "DocumentSet",
    "DocumentApproval",
    "ReportDocument",
    "PageLock",
    "Bank",
    "Ribbon",
    "Permissions",
    "GiftboxOpen",
    "ContactLink",
    # Operations and service
    "Package",
    "MapPin",
    "Repair",
    "Feedback",
    "Health",
    "Medical",
    "Clock",
    "Car",
    "Phone",
    "Lock",
    "Door",
    "Message",
    "ClipboardList",
    "Warning",
    # Added 2026-07-28 with the operations & service theme, each checked
    # against the same catalogue as the names above before admission:
    # a service request IS a ticket, an incident IS the triangle, and an
    # emergency code is announced rather than merely warned about.
    "Ticket",
    "IncidentTriangle",
    "Ringer",
    # People and relationships
    "Contact",
    "ContactCard",
    "ContactList",
    "People",
    "PeopleAdd",
    "Education",
    "Teamwork",
    "CalendarDay",
    "CalendarAgenda",
    "Suitcase",
    "Org",
    # Process digitisation and improvement
    "Lightbulb",
    "Rocket",
    "FlowChart",
    "WorkItem",
    "Trackers",
    "BarChartVertical",
    "LineChart",
    "TaskManager",
    "Switch",
})
