  } catch (err) {
    // Convert every uncaught phase failure into the same returned summary contract (#282).
    const detail = String((err && err.message) || err).slice(0, 300);
    log('ERROR', `${currentPhaseLabel || 'Deploy'}: ${detail}`);
    summary.errors.push({ phase: currentPhaseLabel || 'deploy', error: detail });
    if (!summary.aborted) summary.aborted = 'uncaught-phase-error';
    return summary;
  } finally {
    // Each exit cleanup is guarded on its own: one throwing must not skip a
    // later one, because the operator's run-scoped membership is the LAST
    // drain and the exact thing a failed run must not leave behind. Order
    // still matters -- the stop stamp rides the run's own operator
    // enrolment (removeSelfEnrollments drains LAST), restore field
    // protection while the temporary membership still authorises the
    // write, then drain the reader before the operator.
    //
    // EVERYTHING HERE RUNS AFTER THE [DONE] LINE. That line is printed by
    // the last phase, inside the try above, so a cleanup failure lands
    // below the operator's last authoritative sentence and after the
    // summary object was logged. Seen live 2026-09-03: "errors 0" followed
    // by 56 exit errors (#384). The re-seal cannot simply move ahead of the
    // summary, because it has to run on the abort paths that never reach it
    // at all. So count what the cleanups add and correct the record.
    const errorsBeforeCleanup = summary.errors.length;
    try {
      await restoreUnsealedFields();
    } catch (err) {
      log('ERROR', `Could not restore field protection on exit: ${err.message}`);
      summary.errors.push({ phase: 'exit', error: `restore field protection: ${err.message}` });
    }
    // Beside the re-seal and for the same reason: the folder phase lifts a
    // library's save rule to create a declared folder, and a run that dies
    // in between must not leave the library accepting saves its declaration
    // forbids. Guarded separately so neither restore can skip the other.
    try {
      await restoreLiftedListValidation();
    } catch (err) {
      log('ERROR', `Could not restore list save rules on exit: ${err.message}`);
      summary.errors.push({ phase: 'exit', error: `restore list save rules: ${err.message}` });
    }
    try {
      await finishRunLog();
    } catch (err) {
      log('ERROR', `Could not write the run's stop record: ${err.message}`);
      summary.errors.push({ phase: 'exit', error: `write the run's stop record: ${err.message}` });
    }
    try {
      await removeReaderEnrollments();
    } catch (err) {
      log('ERROR', `Could not remove the enterprise reader on exit: ${err.message}`);
      summary.errors.push({ phase: 'exit', error: `remove the enterprise reader: ${err.message}` });
    }
    try {
      await removeSelfEnrollments();
    } catch (err) {
      log('ERROR', `Could not remove the operator's run-scoped enrolment on exit: ${err.message}. Remove yourself in Site permissions > Groups.`);
      summary.errors.push({ phase: 'exit', error: `remove the operator's run-scoped enrolment: ${err.message}` });
    }
    // A local, deliberately NOT a key on `summary`. The abort paths return
    // `{ ...summary, aborted }`, a shallow copy taken before this runs, so a
    // scalar set here would be on the summary of a successful run and absent
    // from the summary of an aborted one. `errors` survives every path
    // because the copy shares the array, so the errors themselves are always
    // machine-readable and only the count needs saying out loud.
    const cleanupErrors = summary.errors.length - errorsBeforeCleanup;
    if (cleanupErrors > 0) {
      // The LAST line of the run, so it is the one still on screen, and it
      // says the earlier count is out of date rather than leaving two to be
      // reconciled. The summary is re-logged because the copy the last phase
      // printed was printed before these errors existed.
      log('ERROR', `Exit cleanup failed ${cleanupErrors} time(s) AFTER the summary above, so that line's error count is out of date. This run finished with ${summary.errors.length} error(s); read the [ERROR] lines above and summary.errors.`);
      console.log(summary);
    }
  }
})();
