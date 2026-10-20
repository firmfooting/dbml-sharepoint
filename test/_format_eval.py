"""Run a column-formatting `=...` expression under Node, for parity tests only.

The functions below follow the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference).
Where that page is silent the JavaScript default applies and the test that cares says so.
"""

import json
import re
from collections.abc import Mapping, Sequence

from _node import run_node

# Learn documents each of these by name and example; padStart, addDays and substring follow it too.
_PRELUDE = """
const toString = String;
const toLowerCase = (s) => s.toLowerCase();
const toUpperCase = (s) => s.toUpperCase();
const abs = Math.abs;
const floor = Math.floor;
const ceiling = Math.ceil;
const pow = Math.pow;
const indexOf = (s, needle) => s.indexOf(needle);
const lastIndexOf = (s, needle) => s.lastIndexOf(needle);
const startsWith = (s, needle) => s.startsWith(needle);
const endsWith = (s, needle) => s.endsWith(needle);
const substring = (s, a, b) => s.substring(a, b);
const replace = (s, a, b) => s.replace(a, b);
const replaceAll = (s, a, b) => s.replaceAll(a, b);
const padStart = (s, n, pad) => s.padStart(n, pad);
const padEnd = (s, n, pad) => s.padEnd(n, pad);
const getDate = (d) => d.getDate();
const getMonth = (d) => d.getMonth();
const getYear = (d) => d.getFullYear();
// Learn does not say whether addDays counts calendar days or 24 hours across a daylight change.
const addDays = (d, n) => {
  const r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
};
const addMinutes = (d, n) => new Date(d.getTime() + n * 60000);
const asDate = (v) => new Date(v);
const choose = (condition, yes, no) => (condition ? yes : no);
"""


def _compile(expression: str) -> str:
    """Rewrite a formatting expression as JavaScript: strings, fields, @now and if/Date calls."""
    assert expression.startswith("=")
    parts = re.split(r"('(?:[^']|'')*')", expression[1:])
    for i, part in enumerate(parts):
        if i % 2:
            parts[i] = json.dumps(part[1:-1].replace("''", "'"))
            continue
        swapped = part.replace("@now", "now")
        swapped = re.sub(r"\[\$([^\]]+)\]", lambda m: "fields[" + json.dumps(m[1]) + "]", swapped)
        swapped = re.sub(r"\bif\(", "choose(", swapped)
        parts[i] = re.sub(r"\bDate\(", "asDate(", swapped)
    return "".join(parts)


def evaluate_rows(
    expression: str, rows: Sequence[Mapping[str, object]], *, browser_tz: str, now: str
) -> list[object]:
    """The expression's value on each row, with `[$Field]` bound to the row's JSON values.

    Dates in a row are strings, as a list read returns them; a date result comes back as an ISO
    instant. The browser zone is set before any date exists.
    """
    script = (
        f"process.env.TZ = {json.dumps(browser_tz)};\n{_PRELUDE}\n"
        f"const now = new Date({json.dumps(now)});\n"
        f"const rows = {json.dumps(list(rows))};\n"
        f"const run = (fields) => ({_compile(expression)});\n"
        "console.log('RESULT ' + JSON.stringify(rows.map((fields) => {\n"
        "  try { const v = run(fields); return v === undefined ? null : v; }\n"
        "  catch (e) { return { error: String(e) }; }\n"
        "})));\n"
    )
    out = run_node(script)
    line = next(ln for ln in out.splitlines() if ln.startswith("RESULT "))
    return list(json.loads(line.removeprefix("RESULT ")))


def evaluate_expression(
    expression: str, row: Mapping[str, object], *, browser_tz: str, now: str
) -> object:
    return evaluate_rows(expression, [row], browser_tz=browser_tz, now=now)[0]
