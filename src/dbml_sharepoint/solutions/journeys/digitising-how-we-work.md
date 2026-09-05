---
title: Digitising how we work
summary: Inventory what the organisation actually does, then work down that list by how much it hurts.
solutions:
  - process-register
  - measures-register
  - improvement-register
  - project-pipeline
  - change-register
  - opportunities-register
  - deployment-log
---

# Digitising how we work

Start with the inventory, because effort otherwise chases whoever asked most
recently. `process-register` ranks every process by criticality multiplied by
pain, and that ranking is the worklist.

Decide how you will know a change worked before making it, which is what
`measures-register` is for. Small fixes then run as improvement cycles; larger
ones go through `project-pipeline` for a gate decision and `change-register`
for the approval trail. `opportunities-register` catches the problems a
delivery team finds but cannot fix itself, so they reach this chain rather than
being lost.

`deployment-log` is last and is different in kind: it records what this tool
itself did, rather than what the organisation decided. Deploy it once, to a
site you keep, and every other deploy in the estate stamps it with what was
provisioned, where, by whom and whether the run finished. It is worth having
by the time you are deploying to several sites and can no longer remember
which of them is current.
