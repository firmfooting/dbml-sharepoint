  let cachedDigest = null;
  let digestExpiresAt = 0;
  // `url` defaults to this web's; a cross-web write passes the other web's, since a digest only validates on its issuing web.
  async function getContextWebInformation(url = apiUrl('contextinfo')) {
    let r;
    try {
      r = await fetchWithRetry(url, {
        method: 'POST',
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
    } catch (err) {
      // fetch rejects outright on a network or CORS failure, so there is no status to report, only the operation.
      throw new Error(`contextinfo (request digest) failed: no response (${String((err && err.message) || err).slice(0, 300)})`);
    }
    return readContextWebInformation(r);
  }
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    let info;
    try {
      info = await getContextWebInformation();
    } catch (err) {
      const failure = err instanceof Error ? err : new Error(String(err));
      failure.digestFailure = true;
      throw failure;
    }
    cachedDigest = info.FormDigestValue;
    const timeoutSeconds = Number(info.FormDigestTimeoutSeconds) || 1800;
    digestExpiresAt = Date.now() + Math.max(timeoutSeconds - 60, 60) * 1000;
    return cachedDigest;
  }

