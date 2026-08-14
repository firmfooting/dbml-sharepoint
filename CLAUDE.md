# Claude Code

@AGENTS.md

`AGENTS.md` above is the canonical instruction file, shared with every other
agent. Keep project instructions there, not here. This file exists so Claude
Code reads them, since it looks for `CLAUDE.md` rather than `AGENTS.md`.

An import is used rather than a symlink deliberately: this repository is
developed on Windows, where creating a symlink needs Administrator rights or
Developer Mode.

Claude-specific notes:

- Prefer plan mode for anything touching `src/dbml_sharepoint/analysis/checks/`
  or `src/dbml_sharepoint/templates/`. A wrong validator rule and a wrong
  emitted formatter both ship silently. See the evidence rule in `AGENTS.md`.
- The shell is PowerShell. The Bash tool is available for POSIX scripts, but
  each takes its own syntax; `git` output paths use backslashes.
