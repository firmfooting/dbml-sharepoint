  let cachedDigest = null;
  let digestExpiresAt = 0;
  // Every digest getDigest() handed out, so a cross-web or caller-built digest is never refreshed.
  const issuedDigests = new Set();
  // The one pending refresh that every lane refused together waits on.
  let digestRefresh = null;
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
    issuedDigests.add(cachedDigest);
    const timeoutSeconds = Number(info.FormDigestTimeoutSeconds) || 1800;
    digestExpiresAt = Date.now() + Math.max(timeoutSeconds - 60, 60) * 1000;
    return cachedDigest;
  }
  // A 403 "security validation" is the measured answer to a refused digest (cross-web digest finding); any other 403 goes back as is.
  onDigestRefused = async (init, r) => {
    const refused = init.headers?.['X-RequestDigest'];
    if (!issuedDigests.has(refused)) return null;
    if (!/security validation/i.test(await r.clone().text())) return null;
    if (refused === cachedDigest) {
      cachedDigest = null;
      digestRefresh = getDigest().finally(() => { digestRefresh = null; });
    }
    const fresh = await (digestRefresh || getDigest());
    log('INFO', 'HTTP 403 security validation on a write; retrying once with a fresh request digest.');
    return { ...init, headers: { ...init.headers, 'X-RequestDigest': fresh } };
  };

