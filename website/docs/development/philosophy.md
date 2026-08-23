---
title: Philosophy
sidebar_position: 1
---

# Development philosophy

These are the rules the codebase is actually built by. They exist
because each one was paid for. Several encode a specific live failure
and its correction. Follow them when contributing; change them only with
the same rigour they demand of everything else.

## 1. Fail closed, verify by readback

The generated scripts operate on other people's production sites with
no undo. Any action whose correctness the script cannot *prove* (an
existing object of uncertain shape, a readback that does not match a
write, a server answer it cannot classify) stops that unit of work with
a named error. "Probably fine" is not a state this project recognises.

Corollary: every write is followed by a read that verifies it took
effect as declared. A write without a readback is a bug even when it
works.

## 2. The declaration is the contract, and only the declaration

deploy.js.txt reconciles exactly what the DBML + mapping declare, and
touches nothing else. Undeclared views, user rows and user-added columns
are user property. Destructive scope (ACL `reconcile: exact`) exists
only where the mapping explicitly opts in. This line is what makes
rerunning safe and what makes the tool trustable on a shared site.

## 3. Live findings are law

When live behaviour contradicts an assumption, even a documented one,
the live finding wins, immediately:

- The finding is encoded in the code path it corrects, with a dated
  comment (`live finding 2026-07-24`) so the *why* survives.
- A test pins the corrected behaviour so it cannot regress.
- The design doc gains a revision recording both the wrong reading and
  the correction. The mistake is part of the record, not overwritten.

Examples in the tree: view width bindings use display names because
internal names silently reset live; rollback recycles items before list
deletes because retention refuses only non-empty lists; per-item comment
seeding was withdrawn the day the endpoint 400'd.

## 4. Undocumented surfaces earn extra guards, or nothing

Reverse-engineering what SharePoint's own UI does is legitimate, but an
undocumented surface gets the strictest treatment in the codebase:
proven live before productionising, wrapped in
read-splice-diff-write-verify, and withdrawn without sentiment the
moment the wire disagrees. Claims about Microsoft 365 behaviour are
verified on learn.microsoft.com and cited in design docs before code is
built on them.

## 5. The console transcript is the product

Operators experience this project as console output. Noise is a defect:
probes whose "absent" answer paints a red 404/400 are replaced with
always-200 enumerations; errors carry the server's own
`error.message.value`; every script ends with a machine-readable
summary and an unambiguous `DONE` line. If a blocked run cannot be
diagnosed from its transcript, the transcript is the bug.

## 6. The lane rule

Concurrency is per-list, never per-item: SharePoint serialises schema
writes within a list (concurrent same-list writes race into save
conflicts), while different lists are independent. Work is grouped into
lanes keyed by list; a lane is strictly sequential; lanes run
concurrently, bounded. Caches are invalidated per-list so lanes never
thrash each other.

## 7. The partial-earning rule

A template partial is shared only when **every** including script needs
it **identically**: identity/provenance, site guard, digest, HTTP
transport. Phase and domain logic stays with its phase even when
fragments look similar, because forcing divergent logic through a shared
partial couples scripts that must be able to evolve apart. The
read-only assess script is the proof case: write helpers live in a
separate partial precisely so assess.js.txt never includes them.

## 8. The public-name rule

Underscore-prefixed names are module-private. Anything imported across
modules is public and drops the prefix, no exceptions, no "internal but
shared". If a private helper earns a second caller, renaming it public
is part of that change.

## 9. One source of truth per fact

Phase numbers derive from the phases manifest; display names derive from
internal names plus overrides; style JSON derives from tokens; the API
docs derive from the source. Where a fact appears in two places, one of
them is generated from the other, never maintained in parallel.

## 10. Byte-golden discipline

deploy.js.txt generation is pinned by a byte-exact golden fixture. Any
template change fails the golden test until the fixture is regenerated
*deliberately*. Template drift is always a reviewed decision, never an
accident. Checksums hash LF-normalised content so the discipline holds
across platforms.

## 11. Scale honesty

Anything bounded says so: paging loops have safety stops, truncation is
logged, "not assessable" is printed rather than implied as covered, and
rollback treats an earlier item count as information rather than deletion
authority and confirms each target list separately.
Silent caps that read as full coverage are defects.
