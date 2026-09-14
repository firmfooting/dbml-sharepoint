  markPhase('Phase 1.7: deployment run and change logs');
  // --no-sidecars with no central log named: no run log, no change log, no
  // external stamps. The shim logChange still buffers whatever renames
  // raise, and nothing drains it: a build that declines every sink records
  // nothing.
