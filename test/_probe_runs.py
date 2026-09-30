"""Run a rendered probe under node behind a mock, and read back its result table.

Shared by the runtime tests of the item-versions and batch item-create probes, which each
open the probe's gates, splice a dump of RESULTS into report(), and compare what a failed
fixture voided with what the catalogue says rests on it.
"""

import json
from pathlib import Path
from typing import Any

from _node import run_node
from _paths import MANUAL


def probe_js(path: Path, gates: tuple[str, ...], swaps: dict[str, str] | None = None) -> str:
    """The rendered probe with `gates` set true, each swap applied once, and RESULTS dumped."""
    js = path.read_text(encoding="utf-8")
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    for old, new in (swaps or {}).items():
        swapped = js.replace(old, new, 1)
        assert swapped != js, f"{old!r} is not in the probe"
        js = swapped
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def run_probe(
    mock: str, path: Path, gates: tuple[str, ...], config: dict[str, Any],
    swaps: dict[str, str] | None = None,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    """Rows by id, the requests the mock saw, and the whole console output."""
    output = run_node(mock.replace("__CONFIG__", json.dumps(config)) + "\n"
                      + probe_js(path, gates, swaps))
    sent_line = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    rows_line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    rows = {} if rows_line is None else {
        row["id"]: row for row in json.loads(rows_line.removeprefix("__ROWS__"))}
    return rows, json.loads(sent_line.removeprefix("__SENT__")), output


def catalogued_dependents(probe: str, fixture: str) -> set[str]:
    """Every check the catalogue says rests on `fixture`, which is what a failure of it voids."""
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    [entry] = [p for p in catalog["probes"] if p["file"] == probe]
    return {finding["id"] for scenario in entry["scenarios"] for finding in scenario["findings"]
            if fixture in finding["depends_on"]}


def voided(rows: dict[str, dict[str, str]]) -> set[str]:
    """The ids a run recorded void."""
    return {row_id for row_id, row in rows.items() if row["state"] == "void"}


def ended_with_report(output: str) -> bool:
    """Whether a run printed its whole report and nothing escaped the probe's own handling."""
    return ("Copy this whole block back verbatim." in output and "ReferenceError" not in output
            and "Node.js v" not in output)


def recycled_last(sent: list[dict[str, str]]) -> bool:
    """Whether a run ended with a list recycle and the by-Id read that confirms it."""
    return (len(sent) >= 2 and sent[-2]["path"].endswith("/recycle")
            and sent[-1]["path"].endswith("')?$select=Id"))
