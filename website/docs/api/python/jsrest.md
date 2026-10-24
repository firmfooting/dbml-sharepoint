---
title: jsrest
sidebar_position: 58
---

# `dbml_sharepoint.jsrest`

*the shared SharePoint REST prelude a paste-in script runs behind*

The JavaScript runtime core shares with a downstream paste-in prelude.

`prelude()` renders the shared SharePoint REST transport, comment-free and
between version sentinels, in a read flavour that carries no write helper or a
write flavour with the request digest; `wrap()` puts a body behind it. The
comment stripper shortens the text without touching a string, template or
regex literal.

A body runs in the prelude's own scope, so it must not redeclare any of the
names the prelude declares in one flavour or another:

- every flavour: `log`, `WEB`, `apiUrl`, `odataName`, `DEBUG`, `MAX_WAIT_SECONDS`, `dbg`,
  `requestCount`, `onDigestRefused`, `sleep`, `spError`, `isAbsent400`, `THROTTLE_PAGE`,
  `isThrottled`, `throttleGate`, `passThrottleGate`, `holdEveryLane`, `retryAfterSeconds`,
  `fetchWithRetry`, `verbose`, `getOne`, `getAll`, `download`;
- the site guard, by mode: `SITE_URL`, `actualPath`, `expectedOrigin`, `expectedPath`,
  `actualOrigin`, `siteHome`, `sitePath`, `expectedSite`;
- writes: `spHeaders`, `readContextWebInformation`, `cachedDigest`, `digestExpiresAt`,
  `issuedDigests`, `digestRefresh`, `getContextWebInformation`, `getDigest`, `ensureUser`;
- batch: `BATCH_BODY_BUDGET_BYTES`, `BATCH_ENVELOPE_BYTES`, `BATCH_BOUNDARY_SAMPLE`,
  `batchBoundary`, `utf8Bytes`, `BatchReader`, `BatchWriter`.

### `prelude`

```python
def prelude(*, writes: bool, batch: bool = False, site: Site = 'page-context', expected_site: str | None = None) -> str
```

The shared prelude as a function-body fragment; the site guard may `return` from it.

`writes` adds the write headers, the cached request digest and ensureUser;
`batch` adds BatchWriter and needs `writes`. With `expected_site`, the site
guard refuses any other site; `site` picks whether the page's site comes
from `_spPageContextInfo` or from the page path.

### `wrap`

```python
def wrap(body: str, *, writes: bool, batch: bool = False, site: Site = 'page-context', expected_site: str | None = None) -> str
```

`body` behind the prelude in an async arrow, called at once.

No `.catch` is attached, so a caller that awaits the script sees its rejection.

### `strip_js_comments`

```python
def strip_js_comments(text: str) -> str
```

Remove `//` and `/* */` comments from JavaScript, leaving every literal as it was.

A line that held only a comment is dropped, and a block comment that spanned a
line break leaves one behind so automatic semicolon insertion reads the same.
An unterminated string, template, regex or block comment raises `ValueError`
naming the line it opened on.

