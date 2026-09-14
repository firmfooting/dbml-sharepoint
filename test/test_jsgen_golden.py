# test/test_jsgen_golden.py
"""The deploy script, byte for byte, in pieces small enough to read.

`simple-deploy.js` reached 428,632 bytes under one assertion. AGENTS.md asks
for the fixture diff to be reviewed like code, and the reason it asks is
recorded in `test_deploy_runtime.py`: a bug shipped inside this golden and was
asserted as correct. Nobody reviews a 400KB blob line by line, so the golden
is committed as one file per piece of the script under
`expected/simple-deploy/`, and the pieces are the units the script is
assembled from: one for each `{% include %}` in `deploy.js.j2`, one for each
phase step in `analysis/phases.py`, and one for each region the root template
emits itself. A template change then moves one named file.

Three checks, which close over each other:

* every piece matches its committed bytes (one case per piece, so a failure
  names the piece),
* the pieces concatenate back to the generated script, so nothing can fall
  between them and no piece can be left behind,
* the script's length and sha256 match the manifest, which is the cheap
  whole-file statement that the pieces above are the whole of it.

A nested include rides inside its parent's piece (`_http_batch_read` inside
`_http_batch`, `_formula_canonical` inside `_field_reconcile`); the table
below names top-level includes, and a test holds it equal to the template.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from pathlib import Path

import pytest
from _paths import EXPECTED, JINJA_TEMPLATES
from test_jsgen import _generate_simple_js

from dbml_sharepoint.analysis.phases import phases_context

#: One file per piece, plus the manifest.
SEGMENT_DIR = EXPECTED / "simple-deploy"
MANIFEST = SEGMENT_DIR / "manifest.json"

_DEPLOY_TEMPLATE = "deploy.js.j2"

#: The top-level includes that run before the schema literal, in template
#: order. Held equal to `deploy.js.j2` by
#: test_every_include_in_the_deploy_template_names_a_piece.
_BEFORE_SCHEMA = (
    "_site_guard.js.j2",
    "_http.js.j2",
    "_http_write.js.j2",
    "_http_batch.js.j2",
    "_digest_cached.js.j2",
    "_assess_body.js.j2",
    "deploy/_shape_probes.js.j2",
    "deploy/_helpers.js.j2",
)

#: `_provenance.js.j2` renders inside the header's block comment and every one
#: of its lines is an interpolation, so it has no literal line to cut at and
#: rides inside the header piece. Pinned rather than skipped quietly: a second
#: entry here is a region nobody named.
UNANCHORABLE = ("_provenance.js.j2",)

#: The three regions `deploy.js.j2` emits itself have no template of their own
#: to read a first line from, so their anchors are written out. Each is the
#: first line of its region in that file; reword one there and the anchor has
#: to move with it, which is what the assertion in `_cut` reports. The exit
#: anchor takes a second line because `} catch (err) {` at this indent also
#: occurs inside phase bodies.
_SCHEMA_ANCHOR = "  // === Schema definition (rendered from DBML + mapping) ==="
_EXIT_CLEANUP_ANCHOR = "  // Run-scoped privilege is exit-scoped too. Keep the state and cleanup"
_EXIT_ANCHOR = (
    "  } catch (err) {\n"
    "    // Convert every uncaught phase failure into the same returned summary contract (#282)."
)


@dataclass(frozen=True)
class Segment:
    """One committed piece of the script, and the emitted line it starts at."""

    name: str
    anchor: str
    #: The include this piece came from, or None for a region of the root
    #: template and for the phase steps.
    template: str | None = None


def _first_emitted_line(template: str) -> str | None:
    """The first line an included template emits verbatim, or None if it has
    no such line and so cannot be cut at."""
    text = (JINJA_TEMPLATES / template).read_text(encoding="utf-8")
    for line in re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL).splitlines():
        if line.strip() and "{{" not in line and "{%" not in line:
            return line
    return None


def _from_template(template: str) -> Segment:
    anchor = _first_emitted_line(template)
    assert anchor is not None, (
        f"{template} emits no literal line, so it cannot start a piece of the "
        f"golden. Either give it one or add it to UNANCHORABLE with the reason."
    )
    name = Path(template).name.removesuffix(".js.j2").lstrip("_").replace("_", "-")
    return Segment(name, anchor, template)


def _phase_segments() -> list[Segment]:
    return [
        Segment(
            f"phase-{step['key'].replace('_', '-')}",
            f"  markPhase('Phase {step['number']}: {step['name']}');",
        )
        for group in phases_context()
        for step in group["steps"]
    ]


def deploy_segments() -> tuple[Segment, ...]:
    """Every piece of the deploy script, in the order it is emitted."""
    return (
        Segment("header", ""),
        *(_from_template(template) for template in _BEFORE_SCHEMA),
        Segment("schema", _SCHEMA_ANCHOR),
        _from_template("deploy/_field_reconcile.js.j2"),
        Segment("exit-cleanup", _EXIT_CLEANUP_ANCHOR),
        *_phase_segments(),
        Segment("exit", _EXIT_ANCHOR),
    )


def _cut(js: str, segment: Segment, after: int) -> int:
    """Where a piece starts. Anchors are unique and strictly increasing, so a
    moved boundary fails here rather than silently re-cutting the script."""
    if not segment.anchor:
        return 0
    found = js.count(segment.anchor)
    source = segment.template or _DEPLOY_TEMPLATE
    assert found == 1, (
        f"the anchor for golden piece '{segment.name}' occurs {found} times in "
        f"the deploy script; it must occur exactly once. It is the first line "
        f"{source} emits, so reconcile the two.\n  anchor: {segment.anchor!r}"
    )
    start = js.index(segment.anchor)
    assert start > after, (
        f"golden piece '{segment.name}' starts at {start}, before the piece "
        f"above it ends at {after}. The pieces must be in emitted order."
    )
    return start


#: The committed file names, in the order the script emits them. The index
#: prefix is what makes the directory listing read as the script does.
SEGMENT_NAMES = tuple(
    f"{index:02d}-{segment.name}.js" for index, segment in enumerate(deploy_segments())
)


def split_deploy_js(js: str) -> dict[str, str]:
    """The script cut into its committed pieces, keyed by file name."""
    starts: list[int] = []
    after = -1
    for segment in deploy_segments():
        after = _cut(js, segment, after)
        starts.append(after)
    bounds = [*starts[1:], len(js)]
    return {
        name: js[start:end]
        for name, start, end in zip(SEGMENT_NAMES, starts, bounds, strict=True)
    }


def manifest_text(js: str, pieces: dict[str, str]) -> str:
    """The whole-file check, and the inventory of what the pieces are."""
    return json.dumps(
        {
            "bytes": len(js.encode("utf-8")),
            "sha256": sha256(js.encode("utf-8")).hexdigest(),
            "segments": list(pieces),
        },
        indent=2,
    ) + "\n"


@cache
def _script() -> str:
    """Generated once per process: every case below reads the same bytes."""
    return _generate_simple_js()


def _manifest() -> dict[str, object]:
    return dict(json.loads(MANIFEST.read_text(encoding="utf-8")))


_REGENERATE = (
    "If the change is intentional, regenerate the golden: "
    "uv run python test/regen_golden.py. Review the diff like code. It is."
)


def test_simple_deploy_js_matches_golden() -> None:
    """The whole-file check: the deploy script from simple.dbml is the golden,
    byte for byte.

    Cheap, and deliberately over the WHOLE script rather than over the pieces,
    so that no defect can live in the cutting. The per-piece cases below are
    what makes a failure reviewable; this one is what makes it complete.

    To regenerate the golden after a legitimate template change::

        uv run python test/regen_golden.py

    That writes every piece and the manifest through the same
    `_generate_simple_js()` this test reads, so the two cannot drift.
    Regeneration is a separate, explicit act rather than a `--snapshot-update`
    flag on the test run; the friction is the point.
    """
    js = _script()
    manifest = _manifest()
    assert len(js.encode("utf-8")) == manifest["bytes"], (
        f"the deploy script is {len(js.encode('utf-8'))} bytes and the golden "
        f"manifest says {manifest['bytes']}. {_REGENERATE}"
    )
    assert sha256(js.encode("utf-8")).hexdigest() == manifest["sha256"], (
        f"the deploy script output has changed. {_REGENERATE}"
    )


@pytest.mark.parametrize("name", SEGMENT_NAMES)
def test_each_deploy_piece_matches_its_golden(name: str) -> None:
    """One case per piece, so a template change fails against the file that
    carries that template's output and nothing else."""
    piece = SEGMENT_DIR / name
    assert piece.exists(), f"golden piece missing: {piece}. {_REGENERATE}"
    assert split_deploy_js(_script())[name] == piece.read_text(encoding="utf-8"), (
        f"the deploy script has changed in {name}. {_REGENERATE}"
    )


def test_the_pieces_are_the_whole_script_and_nothing_else() -> None:
    """Nothing falls between the pieces, and nothing is left over.

    The per-piece cases prove each committed file is right; this proves the
    files are all of it. Without it a moved boundary could drop a region from
    every piece, and every other assertion here would still pass.
    """
    js = _script()
    pieces = split_deploy_js(js)
    assert "".join(pieces.values()) == js, (
        "the golden pieces do not concatenate back to the deploy script, so a "
        "region of it is committed nowhere."
    )
    committed = sorted(path.name for path in SEGMENT_DIR.glob("*.js"))
    assert committed == sorted(pieces), (
        f"the committed pieces are not the pieces the script splits into. "
        f"{_REGENERATE}"
    )
    assert _manifest()["segments"] == list(pieces), (
        f"the manifest lists the pieces in a different order than the script "
        f"emits them. {_REGENERATE}"
    )


#: An `{% include %}` and the path it names. Both quote styles, because Jinja
#: takes both and a pattern narrower than Jinja skips the include silently.
INCLUDE = re.compile(r"""{%\s*include\s*(["'])(?P<path>[^"']+)\1\s*%}""")


def test_the_include_pattern_reads_a_template_the_way_jinja_does() -> None:
    """Single quotes included, since matching only double ones would let a new
    include fold into the piece above it while this file still reported
    agreement. No template spells one that way today, which is exactly why
    the case is pinned here rather than left to the real template to catch."""
    both = """{% include "deploy/_a.js.j2" %}\n{% include 'deploy/_b.js.j2' %}"""
    assert [m.group("path") for m in INCLUDE.finditer(both)] == [
        "deploy/_a.js.j2", "deploy/_b.js.j2",
    ]


def test_every_include_in_the_deploy_template_names_a_piece() -> None:
    """An include added to deploy.js.j2 and not named here would land inside
    the piece above it, unreviewed under another template's name. The whole
    script is still covered either way, so nothing else would report it.
    """
    template = (JINJA_TEMPLATES / _DEPLOY_TEMPLATE).read_text(encoding="utf-8")
    included = [m.group("path") for m in INCLUDE.finditer(template)]
    named = [segment.template for segment in deploy_segments() if segment.template]
    assert [path for path in included if path not in UNANCHORABLE] == named, (
        "deploy.js.j2's includes and the pieces named here have diverged. Give "
        "the new include a piece in deploy_segments(), in template order, or "
        "name it in UNANCHORABLE with the reason it cannot start one."
    )
