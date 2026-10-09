  // Run-scoped privilege is exit-scoped too. Keep the state and cleanup
  // outside the phase try so an unexpected throw can still remove every
  // membership this deployment added.
  const selfEnrollments = [];
  async function removeSelfEnrollments() {
    for (const enrollment of selfEnrollments.splice(0)) {
      try {
        const digestR = await getDigest();
        const removeResp = await fetchWithRetry(apiUrl(`web/sitegroups(${enrollment.groupId})/users/removebyid(${enrollment.userId})`), {
          method: 'POST',
          headers: spHeaders(digestR),
        });
        if (!removeResp.ok) {
          const text = await removeResp.text();
          throw new Error(`HTTP ${removeResp.status} ${text}`);
        }
        log('INFO', `Removed operator from '${enrollment.groupName}' (run-scoped enrolment).`);
      } catch (err) {
        log('ERROR', `Could not remove the operator from '${enrollment.groupName}': ${err.message}. Remove yourself in Site permissions > Groups.`);
      }
    }
  }
  // Identity enrolment cleanup (#213 form 1). Declared here, unconditionally,
  // because the enrolment phase is emitted only when a group enrols something
  // and the finally below would otherwise hit a ReferenceError. These accounts
  // outlive the run only if it REACHES the end: runReachedTheEnd is set once,
  // on the success path in deploy/_seeds.js.j2, after every abort gate.
  const identityEnrollments = [];
  let runReachedTheEnd = false;
  async function removeIdentityEnrollments() {
    if (runReachedTheEnd) {
      // The run reached the end: this is a permanent grant now, not
      // something to undo. Cleared rather than left for a stale reference.
      identityEnrollments.length = 0;
      return;
    }
    for (const enrollment of identityEnrollments.splice(0)) {
      try {
        const digestR = await getDigest();
        const removeResp = await fetchWithRetry(apiUrl(`web/sitegroups(${enrollment.groupId})/users/removebyid(${enrollment.userId})`), {
          method: 'POST',
          headers: spHeaders(digestR),
        });
        if (!removeResp.ok) {
          const text = await removeResp.text();
          throw new Error(`HTTP ${removeResp.status} ${text}`);
        }
        log('INFO', `Removed ${enrollment.described} this run enrolled into '${enrollment.groupName}', because the run did not reach the end.`);
      } catch (err) {
        log('ERROR', `Could not remove ${enrollment.described} from '${enrollment.groupName}': ${err.message}. Remove it in Site permissions > Groups.`);
      }
    }
  }
  // Deployment run/change logging. The shim pair is declared here,
  // unconditionally, for the same reason the reader-enrolment drain is:
  // renames (phase 1.3) run BEFORE the logging phase (1.5), so changes
  // raised there must not be lost, and the finally below must be able to
  // call finishRunLog on every build even when the logging phase never
  // emitted (abort before phase 1.5 leaves nothing to stamp into).
  // logChange buffers until _logging.js.j2 replaces it with the real
  // writer; finishRunLog stays a no-op unless that phase completed its
  // setup, because a run that died before it cannot stamp a list that
  // was never ensured.
  const DEPLOY_CHANGES = [];
  let logChange = (change) => { DEPLOY_CHANGES.push(change); };
  let finishRunLog = async () => {};

  // Every phase runs inside this try so that the finally below is reached
  // by EVERY exit: the normal `return summary` at the end of the last
  // phase, the early returns that abort a broken run, and a throw
  // nobody caught. Anything a run must hand back regardless of outcome
  // belongs in that finally and nowhere else; putting it on the success
  // path is how a failed run came to leave a Title unsealed. The phase
  // bodies keep their own indentation: they are 3,000 lines of included
  // partials, and re-indenting them to sit under this try would bury the
  // change in whitespace.
  try {
