# test/_batch_mock.py
"""A mock SharePoint's `$batch` endpoint, for the runtime harnesses.

The write phases that batch (seal, ACL adds, indexes, field defaults) send
one multipart `$batch` request where they used to send one write each. A
harness that does not unpack it sees a single opaque POST and every
assertion about what was written stops meaning anything.

`BATCH_MOCK` splices in after a harness has defined `globalThis.fetch`. It
unpacks each ChangeSet part back into the single request it stands for and
dispatches it through `globalThis.fetch` again, so the mock underneath
answers, applies and records it exactly as it did before the phase batched,
and a sabotage wrapper installed later still sees the individual operation.
"""

BATCH_MOCK = r"""
// A ChangeSet part addresses SharePoint the way a single write does, so the
// mock underneath never has to learn the transport: unpack, redispatch,
// and answer with one status line per part.
{
  const _underBatch = globalThis.fetch;
  const _batches = [];
  const _partMarker =
    '\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n\r\n';
  const _parseParts = (text) => {
    const inner = (String(text).match(/boundary=([^\r\n;]+)/) || [])[1];
    const ops = [];
    for (const chunk of String(text).split(`--${inner}`)) {
      const at = chunk.indexOf(_partMarker);
      if (at === -1) continue;  // the envelope's own header block
      const rest = chunk.slice(at + _partMarker.length);
      const headEnd = rest.indexOf('\r\n\r\n');
      const [requestLine, ...headerLines] = rest.slice(0, headEnd).split('\r\n');
      const payload = rest.slice(headEnd + 4).replace(/\r\n$/, '');
      const headers = {};
      for (const line of headerLines) {
        const colon = line.indexOf(': ');
        if (colon !== -1) headers[line.slice(0, colon)] = line.slice(colon + 2);
      }
      const [method, url] = requestLine.split(' ');
      // Back to the tunnelled spelling the single writes use. SharePoint
      // takes a part's verb from its request line; this mock's fiction is
      // that the two spellings mean the same write, which is the one thing
      // here that a live tenant has to confirm rather than a test.
      const tunnelled = method !== 'POST' && method !== 'GET';
      ops.push({
        method: tunnelled ? 'POST' : method,
        url,
        headers: tunnelled ? { ...headers, 'X-HTTP-Method': method } : headers,
        body: payload === '' ? undefined : payload,
      });
    }
    return ops;
  };
  globalThis.fetch = async (url, opts = {}) => {
    if (!/\/_api\/\$batch$/.test(String(url))) return _underBatch(url, opts);
    const ops = _parseParts(opts.body);
    const statuses = [];
    for (const op of ops) {
      const r = await globalThis.fetch(op.url, {
        method: op.method, headers: op.headers, body: op.body,
      });
      statuses.push(r.status);
    }
    // The parts AS SENT, verb and all, so a test can assert what travelled
    // as a ChangeSet rather than inferring it from the redispatched calls.
    _batches.push({ statuses, ops: ops.map((op) => ({
      method: op.headers['X-HTTP-Method'] || op.method,
      url: op.url,
      body: op.body === undefined ? null : op.body,
    })) });
    // Bodyless on purpose: the writer counts every 'HTTP/1.1 nnn' in the
    // response text, so a part payload here would be counted as a status.
    const text = statuses.map((status) =>
      `--batchresponse_1\r\nContent-Type: application/http\r\n\r\n`
      + `HTTP/1.1 ${status} Mocked\r\n\r\n`).join('') + '--batchresponse_1--\r\n';
    return {
      ok: true, status: 200, url: String(url),
      headers: { get: () => null },
      text: async () => text,
      json: async () => ({}),
    };
  };
  globalThis.__batches = _batches;
}
"""
