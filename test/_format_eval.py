"""Run a column-formatting `=...` expression under Node, for parity tests only.

The functions below follow the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference).
Where that page is silent the JavaScript default applies and the test that cares says so.
"""

import json
import re
from collections.abc import Mapping, Sequence

from _node import run_node

# Each function below is on the Learn page above (Operators); a function no test uses is not here.
_PRELUDE = """
const toString = String; // Unary operators: toString
const toLowerCase = (s) => s.toLowerCase(); // Unary operators: toLowerCase
const abs = Math.abs; // Unary operators: abs
const floor = Math.floor; // Unary operators: floor
const pow = Math.pow; // Binary operators: pow
const padStart = (s, n, pad) => s.padStart(n, pad); // Ternary operators: padStart
const getDate = (d) => d.getDate(); // Unary operators: getDate
// Binary operators: addDays. Learn does not say whether it counts calendar days or 24 hours
// across a daylight change; this counts calendar days.
const addDays = (d, n) => {
  const r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
};
const asDate = (v) => new Date(v); // Unary operators: Date()
const toUpperCase = (s) => s.toUpperCase(); // Unary operators: toUpperCase
const substring = (s, a, b) => s.substring(a, b); // Ternary operators: substring
const indexOf = (s, x) => s.indexOf(x); // Binary operators: indexOf
// Unary operators: length counts an array, else 1 when true and 0 when false.
const length = (v) => (Array.isArray(v) ? v.length : v ? 1 : 0);
const choose = (condition, yes, no) => (condition ? yes : no); // Conditional operator: if
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
    # Learn does not say whether a blank field reaches a function as null or ''; this passes null.
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
