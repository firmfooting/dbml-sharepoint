# Copilot instructions

**Read [`AGENTS.md`](../AGENTS.md) at the repository root.** It is the canonical
instruction file for all coding agents here, and it is kept current; this file is
a pointer so that Copilot picks the same instructions up. Do not duplicate its
contents here. A second copy drifts.

The points that matter most when reviewing a pull request in this repository:

- **Never accept an assertion about SharePoint behaviour that is not backed by a
  Microsoft Learn citation or a live probe under `test/manual/`.** This project
  exists to close the failure class where a rule saves, reads back
  byte-identical, passes every deploy phase, and does nothing on the rendered
  page. Plausibility is not evidence. Flag any new claim about platform
  behaviour that cites neither.
- **Commit messages must be conventional** (`feat:`, `fix:`, `docs:`, ...).
  `release-please` builds the changelog by parsing them, so a non-conventional
  commit is silently omitted from the release notes.
- **A generator must never import from `analysis/checks/`.** Shared facts belong
  in a module both sides import; `analysis/joins.py` is the worked example.
- **Anything that writes must read back and verify**, and anything uncertain must
  fail closed with a named error.
- Generated files under `website/docs/api/` are committed. Line-ending-only
  churn there is a known artifact of the generator on Windows, not a real change.
