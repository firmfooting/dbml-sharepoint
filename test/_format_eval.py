"""Run a column-formatting `=...` expression under Node, for parity tests only.

The functions below follow the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference).
Where that page is silent the JavaScript default applies and the test that cares says so.

A date field is a `FieldDate`, which behaves as the facts in test/_formula_facts.py record:
`Number` gives epoch milliseconds (0 when blank), `toString` is '' when blank, `== ''` is false
even when blank, `Date()` leaves it as it is, and the date parts read the browser's zone.
"""

import json
import re
from collections.abc import Mapping, Sequence

from dbml_sharepoint.testing.node import run_node

# Each function below is on the Learn page above (Operators); a function no test uses is not here.
_PRELUDE = """
const toString = String; // Unary operators: toString
const toLowerCase = (s) => s.toLowerCase(); // Unary operators: toLowerCase
const abs = Math.abs; // Unary operators: abs
const floor = Math.floor; // Unary operators: floor
const pow = Math.pow; // Binary operators: pow
const padStart = (s, n, pad) => s.padStart(n, pad); // Ternary operators: padStart
class FieldDate {
  constructor(ms) { this.ms = ms; }
  [Symbol.toPrimitive](hint) {
    if (hint === 'number') return this.ms ?? 0;
    if (hint === 'string') return this.ms === null ? '' : new Date(this.ms).toString();
    return NaN;
  }
}
const part = (name) => (d) => {
  if (!(d instanceof FieldDate)) return d[name]();
  return d.ms === null ? '' : new Date(d.ms)[name]();
};
const getDate = part('getDate'); // Unary operators: getDate
const getMonth = part('getMonth'); // Unary operators: getMonth
const getYear = part('getFullYear'); // Unary operators: getYear
// Binary operators: addDays. Measured: it adds exactly 86400000 ms per day.
const addDays = (d, n) => new Date(Number(d) + n * 86400000);
const asDate = (v) => {
  if (!(v instanceof FieldDate)) return new Date(v);
  return v.ms === null ? new Date(0) : v;
}; // Unary operators: Date()
const toUpperCase = (s) => s.toUpperCase(); // Unary operators: toUpperCase
const indexOf = (s, a) => s.indexOf(a); // Binary operators: indexOf
const substring = (s, a, b) => s.substring(a, b); // Ternary operators: substring
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


def date_field(ms: int | None) -> dict[str, int | None]:
    """A date column's value in a row: its epoch milliseconds, None when blank."""
    return {"epoch_ms": ms}


def evaluate_rows(
    expression: str, rows: Sequence[Mapping[str, object]], *, browser_tz: str, now: str
) -> list[object]:
    """The expression's value on each row, with `[$Field]` bound to the row's JSON values.

    A date field is `date_field(ms)`. The browser zone is set before any date exists.
    """
    # Learn does not say whether a blank field reaches a function as null or ''; this passes null.
    script = (
        f"process.env.TZ = {json.dumps(browser_tz)};\n{_PRELUDE}\n"
        f"const now = new Date({json.dumps(now)});\n"
        f"const rows = {json.dumps(list(rows))}.map((row) => Object.fromEntries(\n"
        "  Object.entries(row).map(([k, v]) => [\n"
        "    k, v !== null && typeof v === 'object' && 'epoch_ms' in v\n"
        "      ? new FieldDate(v.epoch_ms) : v,\n"
        "  ])));\n"
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
