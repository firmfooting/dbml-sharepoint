# test/_sp_mock.py
"""Make every mock GET answer only what its `$select` asked for (#574).

A live site returns the properties a request selects and nothing else. A mock
that hands back every property it holds lets a script read one it never
selected, and that read passes here and gets `undefined` on a tenant. The
two defects #574 found this way both only showed on an idempotent re-run,
where a drift check compared `undefined` with the declared value and wrote
on every run.

`PRELUDE` is loaded ahead of every script `run_node` executes. It turns
`globalThis.fetch` into an accessor, so every harness and every sabotage
wrapper that assigns it is wrapped without editing any test module. Only the
outermost call (the one the script made) is projected: a wrapper calling the
fetch beneath it runs in an AsyncLocalStorage context that passes responses
through untouched, so a harness still sees its own full rows.

A nested GET, such as a `$batch` part the batch mock redispatches, has only
its `text()` projected, since that is the body a batch envelope carries.

Projection follows the spike measured in #574: decode `$select`; keep the
first segment of each selected name, every `$expand` name, and `__metadata`;
ignore case; pass `*` through; apply to a verbose `d`, `d.results[]` and
`value[]`. Error answers and requests with no `$select` are left alone.

The tripwire does not throw inside the script, because a script's own
try/catch could swallow it and the test would pass. Each projected row is a
Proxy that RECORDS a read of a PascalCase property that was neither selected
nor assigned by the script; camelCase names are the script's own. At exit the
prelude prints the record after `SENTINEL`, and `run_node` fails the test
naming the property, the request URL and the script line that read it.

A GET of one entity that a harness answers with an empty set is answered
instead with the status SharePoint was measured giving an absent entity of
that kind: 404 for a list or a site group, the absent-400 for a field or view
by name. Other kinds, an item by id among them, keep the harness's answer
until one is measured. An empty set is never an entity, and a catch-all that
answered one made "absent" and "present with nothing in it" the same
observation (#574).
"""

import json
from dataclasses import dataclass

SENTINEL = "__DBMLSP_UNSELECTED_READS__"


@dataclass(frozen=True)
class UnselectedRead:
    """One read of a property the request that produced the row never selected."""

    prop: str
    url: str
    line: int | None
    source: str


class UnselectedReadError(AssertionError):
    """A script read a SharePoint property its request did not `$select`."""

    def __init__(self, reads: list[UnselectedRead]) -> None:
        self.reads = reads
        lines = [
            f"  {r.prop!r} from {r.url}"
            + (f"\n    at run.js:{r.line}: {r.source}" if r.line is not None else "")
            for r in reads
        ]
        super().__init__(
            "the script read properties its request did not $select; a live site "
            "answers these as undefined. Add each to the $select of its request:\n"
            + "\n".join(lines)
        )


def unselected_reads(output: str) -> list[UnselectedRead]:
    """The reads the prelude recorded in `output`, or `[]` when it recorded none."""
    reads: list[UnselectedRead] = []
    for line in output.splitlines():
        if line.startswith(SENTINEL):
            for entry in json.loads(line[len(SENTINEL):]):
                reads.append(UnselectedRead(
                    prop=entry["prop"], url=entry["url"],
                    line=entry.get("line"), source=entry.get("source", ""),
                ))
    return reads


PRELUDE = r"""
'use strict';
(() => {
  const SENTINEL = '__SENTINEL__';
  const fs = require('node:fs');
  const { AsyncLocalStorage } = require('node:async_hooks');
  const inner = new AsyncLocalStorage();
  const recorded = new Map();

  const decode = (s) => {
    try { return decodeURIComponent(s); } catch { return s; }
  };
  // Lower-cased first segments of every $select and $expand name, or null
  // when the request selects nothing (or `*`) and so is answered in full.
  const selectionOf = (url) => {
    const q = String(url).indexOf('?');
    if (q === -1) return null;
    let selected = null;
    const expanded = [];
    for (const pair of String(url).slice(q + 1).split('&')) {
      const eq = pair.indexOf('=');
      if (eq === -1) continue;
      const key = decode(pair.slice(0, eq)).toLowerCase();
      const names = decode(pair.slice(eq + 1)).split(',')
        .map((n) => n.trim().split('/')[0].toLowerCase()).filter(Boolean);
      if (key === '$select') selected = (selected || []).concat(names);
      else if (key === '$expand') expanded.push(...names);
    }
    if (selected === null || selected.includes('*')) return null;
    return new Set([...selected, ...expanded, '__metadata']);
  };

  const callerLine = () => {
    const stack = String(new Error().stack || '').split('\n');
    const script = process.argv[1];
    for (const frame of stack) {
      const at = frame.lastIndexOf(script + ':');
      if (at === -1) continue;
      const line = Number(frame.slice(at + script.length + 1).split(':')[0]);
      if (Number.isInteger(line)) return line;
    }
    return null;
  };

  const record = (prop, url) => {
    const line = callerLine();
    const key = `${prop}\u0000${url}\u0000${line}`;
    if (!recorded.has(key)) recorded.set(key, { prop, url, line });
  };

  const projectRow = (row, keep, url, trip) => {
    if (row === null || typeof row !== 'object' || Array.isArray(row)) return row;
    const copy = {};
    for (const [name, value] of Object.entries(row)) {
      if (keep.has(name.toLowerCase())) copy[name] = value;
    }
    if (!trip) return copy;
    const assigned = new Set();
    return new Proxy(copy, {
      get(target, prop, receiver) {
        if (typeof prop === 'string' && /^[A-Z]/.test(prop)
            && !(prop in target) && !keep.has(prop.toLowerCase())
            && !assigned.has(prop)) {
          record(prop, url);
        }
        return Reflect.get(target, prop, receiver);
      },
      set(target, prop, value, receiver) {
        assigned.add(prop);
        return Reflect.set(target, prop, value, receiver);
      },
      defineProperty(target, prop, desc) {
        assigned.add(prop);
        return Reflect.defineProperty(target, prop, desc);
      },
    });
  };

  // A verbose entity `d`, a verbose collection `d.results[]`, or a
  // nometadata collection `value[]`. Anything else passes through.
  const projectBody = (body, keep, url, trip) => {
    if (body === null || typeof body !== 'object') return body;
    if (Array.isArray(body.value)) {
      return { ...body, value: body.value.map((r) => projectRow(r, keep, url, trip)) };
    }
    const d = body.d;
    if (d === null || typeof d !== 'object') return body;
    if (Array.isArray(d.results)) {
      const results = d.results.map((r) => projectRow(r, keep, url, trip));
      return { ...body, d: { ...d, results } };
    }
    return { ...body, d: projectRow(d, keep, url, trip) };
  };

  // `outer` is the script's own call; a nested one projects text() only, which
  // is what a $batch envelope carries its part bodies in.
  const projectResponse = (response, keep, url, outer) => new Proxy(response, {
    get(target, prop) {
      if (prop === 'json' && outer) {
        return async () => projectBody(await target.json(), keep, url, true);
      }
      if (prop === 'text') {
        return async () => {
          const text = await target.text();
          let parsed;
          try { parsed = JSON.parse(text); } catch { return text; }
          return JSON.stringify(projectBody(parsed, keep, url, false));
        };
      }
      const value = Reflect.get(target, prop, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });

  // Absent-entity answers, measured live only; test_sp_mock.py cites each one.
  const ABSENT = [
    { at: /\/lists\/getbytitle\('((?:[^']|'')*)'\)$/i, status: 404,
      code: '-1, System.ArgumentException',
      value: (name, site) => `List '${name}' does not exist at site with URL '${site}'.` },
    { at: /\/fields\/getbyinternalnameortitle\('((?:[^']|'')*)'\)$/i, status: 400,
      code: '-2147024809, System.ArgumentException',
      value: (name) => `Column '${name}' does not exist.` },
    { at: /\/views\/getbytitle\('((?:[^']|'')*)'\)$/i, status: 400,
      code: '-2147024809, System.ArgumentException',
      value: () => 'The specified view is invalid.' },
    // Only the status is measured for a group, so its body stays empty rather than invented.
    { at: /\/sitegroups\/getbyname\('((?:[^']|'')*)'\)$/i, status: 404, value: null },
  ];
  const isEmptySet = (body) => body !== null && typeof body === 'object' && (
    (Array.isArray(body.value) && body.value.length === 0)
    || (body.d !== null && typeof body.d === 'object' && Array.isArray(body.d.results)
      && body.d.results.length === 0));
  // Read via the harness's own accessor only; some make json() and text() disagree.
  const answerAbsence = async (response, url, opts) => {
    const path = String(url).split('?')[0];
    const kind = ABSENT.find((k) => k.at.test(path));
    if (!kind) return response;
    const via = typeof response.json === 'function' ? 'json' : 'text';
    let body;
    let failure = null;
    try { body = await response[via](); } catch (err) { failure = err; }
    let parsed = body;
    if (via === 'text' && failure === null) {
      try { parsed = JSON.parse(body); } catch { parsed = undefined; }
    }
    if (failure !== null || !isEmptySet(parsed)) {
      return new Proxy(response, {
        get(target, prop) {
          if (prop === via) {
            return async () => {
              if (failure !== null) throw failure;
              return body;
            };
          }
          const value = Reflect.get(target, prop, target);
          return typeof value === 'function' ? value.bind(target) : value;
        },
      });
    }
    const name = decode(path.match(kind.at)[1]).replace(/''/g, "'");
    const site = path.split('/_api')[0];
    const headers = (opts && opts.headers) || {};
    const accept = String(headers.Accept || headers.accept || '');
    let answer = '';
    if (kind.value) {
      const message = { lang: 'en-US', value: kind.value(name, site) };
      const error = kind.code ? { code: kind.code, message } : { message };
      const verbose = accept.includes('odata=verbose');
      answer = JSON.stringify(verbose ? { error } : { 'odata.error': error });
    }
    return {
      ok: false, status: kind.status, url: String(url),
      headers: { get: () => null },
      json: async () => JSON.parse(answer),
      text: async () => answer,
    };
  };

  const wrap = (raw) => {
    if (typeof raw !== 'function') return raw;
    return async function projectedFetch(url, opts) {
      const nested = inner.getStore() === true;
      const method = String((opts && opts.method) || 'GET').toUpperCase();
      let response = await inner.run(true, () => raw.call(this, url, opts));
      if (method === 'GET' && response && typeof response === 'object' && response.ok) {
        response = await answerAbsence(response, url, opts);
      }
      if (method !== 'GET' || !response || typeof response !== 'object' || !response.ok) {
        return response;
      }
      const keep = selectionOf(url);
      return keep === null ? response : projectResponse(response, keep, String(url), !nested);
    };
  };

  let current = wrap(globalThis.fetch);
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    enumerable: false,
    get: () => current,
    set: (fn) => { current = wrap(fn); },
  });

  process.on('exit', () => {
    if (recorded.size === 0) return;
    let lines = [];
    try {
      lines = fs.readFileSync(process.argv[1], 'utf8').split('\n');
    } catch { /* reported without its source line */ }
    const reads = [...recorded.values()].map((r) => ({
      ...r, source: r.line === null ? '' : String(lines[r.line - 1] || '').trim(),
    }));
    fs.writeSync(2, `\n${SENTINEL}${JSON.stringify(reads)}\n`);
  });
})();
""".replace("__SENTINEL__", SENTINEL)
