# Reporting joins

Use each SharePoint lookup's numeric item key, not its displayed title or a
projected display column. Keep nullable keys as nulls when there is no related
record. That is the warehouse rule, for one site. In Power BI, join on the
`... Key` columns the reporting pack emits instead; `guide.md` in the build
lists every relationship, and `Id` repeats across sites and lists.

| Source column | Target column |
| --- | --- |
| `Activity.Workstream` | `Workstream.Id` |
| `Activity.AccountableForum` | `Stakeholder.Id` |
| `Activity.DecisionRoute` | `Stakeholder.Id` |
| `Involvement.Activity` | `Activity.Id` |
| `Involvement.Stakeholder` | `Stakeholder.Id` |
| `ServiceRequest.Workstream` | `Workstream.Id` |
| `ServiceRequest.AuthorisingDecision` | `Decision.Id` |
| `Risk.Workstream` | `Workstream.Id` |
| `Risk.ToleranceDecision` | `Decision.Id` |
| `Action.Workstream` | `Workstream.Id` |
| `Action.RelatedRisk` | `Risk.Id` |
| `Action.RelatedIssue` | `Issue.Id` |
| `Action.RelatedServiceRequest` | `ServiceRequest.Id` |
| `Action.AuthorisingDecision` | `Decision.Id` |
| `Issue.Workstream` | `Workstream.Id` |
| `Issue.RelatedRisk` | `Risk.Id` |
| `Decision.Workstream` | `Workstream.Id` |
| `Decision.Activity` | `Activity.Id` |
| `Decision.SupersedesDecision` | `Decision.Id` |
| `Decision.DecidedByForum` | `Stakeholder.Id` |
| `Decision.RecommendedByForum` | `Stakeholder.Id` |

`ServiceRequest.MinutesSpent` is the effort measure. Sum it over
`Status = Closed`, by `RequestType`, by `Workstream` and by `AssignedTo`, for
the agreement review. A request still open carries a running total that is
not yet evidence, so filter on the status rather than on the column.

## The three reconciliations these joins exist for

None of these is a save rule. SharePoint cannot compare two lookups across two
lists in a validation formula, so each is a report somebody reads.

1. **Route against outcome.** Join `Decision.Activity` to
   `Activity.Id`, then compare `Activity.DecisionRoute` with
   `Decision.DecidedByForum`. A row where they differ is a decision
   taken somewhere other than its standing route. That is sometimes correct
   and always worth seeing.
2. **Recommend then decide.** Where `RecommendedByForum` is set, it should not
   equal `DecidedByForum`. A row where one forum did both stages has recorded a
   recommendation it then accepted from itself.
3. **Decide then perform.** Count `Action` rows per
   `AuthorisingDecision`. An Approved or Ratified decision with no action
   against it either needed none or was never carried out, and only the second
   case matters.

`Decision.Activity` is nullable and blank rows are the normal case, so
reconciliation 1 covers only the decisions raised under a standing activity.
Count the blanks alongside it rather than filtering them away.

## Person columns and the users table

The mapping turns on `reporting.users_table`, so the pack also emits
`_Users.pq`: the site's user information list, one row per person, SharePoint
group or domain group the site has ever resolved, with name, email, account,
department, job title, office, a deleted flag and the principal kind. Every
person column carries a `... Key` that joins it, and `guide.md` lists each
relationship. In this programme that is:

| List | Person columns |
| --- | --- |
| `Stakeholder` | `Contact` |
| `Activity` | `Responsible`, `Accountable`, `ConfirmedBy` |
| `ServiceRequest` | `RequestedBy`, `InternalAccountable`, `AuthorisedBy`, `AssignedTo`, `EscalatedBy` |
| `Risk` | `RiskOwner` |
| `Action` | `AssignedTo` |
| `Issue` | `Owner` |
| `Decision` | `DecidedBy` |

plus `Created By` and `Modified By` on every list.

Power BI allows one active relationship between two tables, so
`Activity` gets one active relationship to `_Users` and the others
inactive. The RACI counts by person need Responsible and Accountable at the
same time, so reference `_Users` twice (right-click, *Reference*) as
`Responsible User` and `Accountable User`, each with its own active
relationship, and slice department and job title from those. Do the same on
`ServiceRequest` where a visual needs the requester and the handler
together. The remaining person columns can stay inactive and be
reached from measures with `USERELATIONSHIP`.

The reporting account must be able to read the site's user information list.
See *Enterprise reporting access* in `30-deploy/deploy.md`.

## System columns

`reporting.system_columns` puts SharePoint's Created By, Created, Modified By
and Modified on every list query and view. Two of the programme's checks read
them:

1. **An edit is not a confirmation.** On `Activity`, compare
   `LastConfirmed` with `Modified` and `ConfirmedBy` with `Modified By`. A row
   edited after it was last confirmed carries a confirmation that predates its
   current content.
2. **Who raised it.** `Created By` on `Issue` and `ServiceRequest` is
   whoever created the row, which is not always the `Owner` or `RequestedBy`
   named on it. A gap between the two is worth checking before the
   fortnightly.
