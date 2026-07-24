---
title: Manifests & provenance
sidebar_position: 6
---

# Manifests and provenance

The bundle documents itself. Nothing in `build/` requires tribal
knowledge to interpret.

## deploy-manifest.md

The operator-facing run book: supported deployment mode, step-by-step
run instructions, the validator's findings (**must show 0 errors**), and
the full inventory — list creation order, deferred lookups, indexes,
views, formatting and permissions — with phase numbers taken from the
same phases manifest deploy.js uses.

## assess-manifest.md

The companion to [assess.js](assess.md): what each tier probes and how
to read the `COMPATIBLE / DEGRADED / BLOCKED` verdict.

## INDEX.md and checksums.txt

`INDEX.md` lists every artifact in the bundle with its purpose (including
whether demo data was emitted); `checksums.txt` carries SHA-256 hashes
so a bundle can be verified after transfer. Hashes are computed over
LF-normalised content, so checking out on Windows does not break
verification.

## Provenance headers

Every generated script and manifest opens with the same provenance
block: source schema (and its modification time), target site, site
role, release tag, schema version and generation timestamp. A pasted
console transcript therefore records exactly which release produced it.
Interpolated values are comment-escaped so a crafted string in an input
file cannot break out of the header comment.

## Stale clearing

`emit_bundle` deletes every file it owns before writing — a bundle never
contains a stale artifact from a previous build with different flags
(for example, a `demo-data.js` left behind after a build without
`--seed`).
