"""The JavaScript runtime core shares with a downstream paste-in prelude.

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
"""

import hashlib
from typing import Literal
from urllib.parse import urlsplit

import dbml_sharepoint
from dbml_sharepoint.templating import script_env

type Site = Literal["page-context", "pathname"]


def prelude(
    *, writes: bool, batch: bool = False, site: Site = "page-context",
    expected_site: str | None = None,
) -> str:
    """The shared prelude as a function-body fragment; the site guard may `return` from it.

    `writes` adds the write headers, the cached request digest and ensureUser;
    `batch` adds BatchWriter and needs `writes`. With `expected_site`, the site
    guard refuses any other site; `site` picks whether the page's site comes
    from `_spPageContextInfo` or from the page path.
    """
    if batch and not writes:
        raise ValueError("batch needs writes=True: $batch is a POST carrying a request digest")
    if expected_site is not None:
        parts = urlsplit(expected_site)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError(
                f"expected_site {expected_site!r} must be an absolute https:// URL with a host")
    text = script_env().get_template("_sp_rest_prelude.js.j2").render(
        writes=writes, batch=batch, expected_site=expected_site,
        require_site_match=expected_site is not None, site_resolution=site,
    )
    body = strip_js_comments(text).strip("\n")
    stamp = f"// sp-rest {dbml_sharepoint.__version__} sha256:"
    stamp += hashlib.sha256(body.encode()).hexdigest()[:12]
    return f"{stamp} begin\n{body}\n{stamp} end\n"


def wrap(
    body: str, *, writes: bool, batch: bool = False, site: Site = "page-context",
    expected_site: str | None = None,
) -> str:
    """`body` behind the prelude in an async arrow, called at once.

    No `.catch` is attached, so a caller that awaits the script sees its rejection.
    """
    fragment = prelude(writes=writes, batch=batch, site=site, expected_site=expected_site)
    return f"(async () => {{\n{fragment}{body}\n}})();\n"


# shortcut: a `/` after a block `}` reads as a regex, so node --check; track blocks if one divides.
_REGEX_AFTER_CHARS = frozenset("(,=:[!&|?{};+-*%<>~^")
_REGEX_AFTER_WORDS = frozenset({"return", "typeof", "case", "do", "else", "in", "of", "void"})
_CONTROL_WORDS = frozenset({"if", "while", "for", "with"})  # `if (x) /re/` holds a regex


def strip_js_comments(text: str) -> str:
    """Remove `//` and `/* */` comments from JavaScript, leaving every literal as it was.

    A line that held only a comment is dropped, and a block comment that spanned a
    line break leaves one behind so automatic semicolon insertion reads the same.
    An unterminated string, template, regex or block comment raises `ValueError`
    naming the line it opened on.
    """
    scanner = _Scanner(text)
    while scanner.i < len(text):
        if scanner.frames and scanner.frames[-1][0] == "`":
            scanner.template_text()
        else:
            scanner.code()
    for kind, start in reversed(scanner.frames):
        if kind == "`":
            raise scanner.unterminated("template literal", start)
    return "".join(scanner.out)


def _is_ident(char: str) -> bool:
    return char.isalnum() or char in "_$"


class _Scanner:
    """One pass over the source, in code or template-text mode."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0
        self.out: list[str] = []
        # Open "`", "${" and "{" frames, each with the offset it opened at.
        self.frames: list[tuple[str, int]] = []
        self.parens: list[bool] = []  # per open `(`, whether a control keyword led it
        self.prev = ""  # the last code character that is not whitespace
        self.word = ""  # the last identifier, kept across whitespace
        self.in_word = False
        self.dotted = False  # the word follows a `.`, so it is a property, not a keyword
        self.regex_ok = True  # whether a `/` here starts a regex literal

    def unterminated(self, what: str, start: int) -> ValueError:
        return ValueError(f"unterminated {what} at line {self.text.count(chr(10), 0, start) + 1}")

    def code(self) -> None:
        text, i = self.text, self.i
        char = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            self._drop(len(text) if end < 0 else end, spans_lines=False)
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise self.unterminated("block comment", i)
            self._drop(end + 2, spans_lines="\n" in text[i:end])
        elif char in "'\"":
            self._literal(self._quoted_end(i))
        elif char == "/" and self.regex_ok:
            self._literal(self._regex_end(i))
        elif char == "`":
            self.frames.append(("`", i))
            self._literal(i + 1)
        else:
            self._code_char(char)

    def template_text(self) -> None:
        text, j = self.text, self.i
        while j < len(text):
            if text[j] == "\\":
                j += 2
            elif text[j] == "`":
                self.frames.pop()
                self._literal(j + 1)
                return
            elif text.startswith("${", j):
                self.frames.append(("${", j))
                self.out.append(text[self.i:j + 2])
                self.i, self.prev, self.word, self.in_word = j + 2, "{", "", False
                self.regex_ok = True
                return
            else:
                j += 1
        raise self.unterminated("template literal", self.frames[-1][1])

    def _code_char(self, char: str) -> None:
        self.i += 1
        if char.isspace():
            self.out.append(char)
            self.in_word = False
            return
        if _is_ident(char):
            if not self.in_word:
                self.word, self.dotted = "", self.prev == "."
            self.word += char
            self.regex_ok = self._keyword() in _REGEX_AFTER_WORDS
        else:
            self.regex_ok = self._punctuator(char)
            self.word = ""
        self.in_word = _is_ident(char)
        self.prev = char
        self.out.append(char)

    def _keyword(self) -> str:
        return "" if self.dotted else self.word

    def _punctuator(self, char: str) -> bool:
        """Track brackets, and say whether a `/` straight after `char` starts a regex."""
        if char == "{":
            self.frames.append(("{", self.i - 1))
        elif char == "}" and self.frames:
            self.frames.pop()  # closing a "${" hands the scan back to its template
        elif char == "(":
            self.parens.append(self._keyword() in _CONTROL_WORDS)
        elif char == ")":
            return bool(self.parens) and self.parens.pop()
        elif char in "+-" and self.out and self.out[-1] == char:
            return False  # `i++ / 2` divides
        return char in _REGEX_AFTER_CHARS

    def _literal(self, end: int) -> None:
        self.out.append(self.text[self.i:end])
        self.prev, self.word, self.in_word = self.text[end - 1], "", False
        self.regex_ok = False
        self.i = end

    def _quoted_end(self, start: int) -> int:
        text, quote, j = self.text, self.text[start], start + 1
        while j < len(text) and text[j] != "\n":
            if text[j] == "\\":
                j += 2
            elif text[j] == quote:
                return j + 1
            else:
                j += 1
        raise self.unterminated("string literal", start)

    def _regex_end(self, start: int) -> int:
        text, j, in_class = self.text, start + 1, False
        while j < len(text) and text[j] != "\n":
            char = text[j]
            if char == "\\":
                j += 1
            elif char == "/" and not in_class:
                return j + 1
            elif char in "[]":
                in_class = char == "["
            j += 1
        raise self.unterminated("regex literal", start)

    def _drop(self, end: int, *, spans_lines: bool) -> None:
        """Skip the comment that ends at `end`, tidying the whitespace it leaves."""
        text, rest = self.text, end
        while rest < len(text) and text[rest] in " \t":
            rest += 1
        self.i = end
        if rest < len(text) and text[rest] != "\n":
            if spans_lines:
                self._trim()
                if self.out and self.out[-1] != "\n":
                    self.out.append("\n")  # a comment holding a line break still ends the line
            elif rest == end and self.out and not self.out[-1][-1].isspace():
                self.out.append(" ")  # keeps `return/**/x` two tokens
            return
        self._trim()
        self.i = rest + 1 if not self.out or self.out[-1] == "\n" else rest

    def _trim(self) -> None:
        while self.out and self.out[-1] in {" ", "\t"}:
            self.out.pop()
