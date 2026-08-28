# test/test_probes.py
"""Gates over the manual probe scripts.

A probe is pasted into a live tenant's browser console by a person, so
nothing about it is exercised by the rest of this suite. These are the
only automated checks it gets, and each one exists because of something
that actually went wrong in this repository.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest
from _paths import MANUAL, REPO_ROOT

TEMPLATES = MANUAL / "templates"

# Everything except tab, newline and carriage return.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
PLACEHOLDER_HOSTS = re.compile(r"https://(example|contoso|tenant|yourtenant|x)\.")
# Matches the whole id, not a leading run of it: check ids are dotted lowercase
# (`text.list-desc.ampersand`) since the surface grammar landed, and the legacy
# mnemonics that remain can carry an underscore. A class that stopped at the
# first `.` or `_` would report an id no probe actually registers.
RECORD_CALL = re.compile(r"^\s*record\(\s*'([A-Za-z0-9][A-Za-z0-9._-]*)'", re.MULTILINE)
EXPECT_CALL = re.compile(r"^\s*expect\(\s*'([A-Za-z0-9][A-Za-z0-9._-]*)'", re.MULTILINE)


def _load_renderer() -> ModuleType:
    """Import render_probes by path.

    NOT ``from test.manual import render_probes``: ``test`` is a CPython
    stdlib package name, so importing through it is a collision waiting to
    happen on someone else's machine.
    """
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _probe_scripts() -> list[Path]:
    return sorted(MANUAL.glob("*.js"))


def _all_probe_sources() -> list[Path]:
    return _probe_scripts() + sorted(TEMPLATES.glob("*.js.j2"))


# Floors for the sweeps below, each well under what is committed today so that
# retiring a probe stays an ordinary edit, and far enough above zero that a
# glob finding nothing fails.
#
# EVERY SWEEP ASSERTS ITS OWN, rather than one check covering the module.
# `_probe_scripts` globs `test/manual/*.js` and is not recursive, so moving the
# probes down one directory empties it, and an empty `for` loop passes every
# guard in this file: the write-guard check, the question registration check,
# `node --check`, and the verbose-OData check all went green that way when it
# was measured. These are the checks keeping tenant identifiers and live
# credentials out of tracked files, so each states separately how much it saw.
#
# Counted where each sweep actually reaches its assertion, not at the top of
# the loop. Three of them skip files by content, and a floor on files SCANNED
# would stay green if every probe stopped matching the filter.
_MIN_SCRIPTS = 15
_MIN_SOURCES = 30
_MIN_TEMPLATES = 12
# Its own floor: only the probes that send `__metadata` reach that assertion,
# and they are a minority of the scripts.
_MIN_METADATA_PROBES = 8


def test_rendered_probes_match_their_templates() -> None:
    """An operator pastes the .js, so a stale .js is a probe that does not
    match the template anyone reviewed."""
    render = _load_renderer()
    stale = []
    compared = 0
    for template in render.probe_templates():
        compared += 1
        target = render.target_for(template)
        actual = target.read_text(encoding="utf-8") if target.exists() else ""
        if render.render_one(template) != actual:
            stale.append(target.name)
    assert compared >= _MIN_TEMPLATES, (
        f"only {compared} probe templates compared, so this pins nothing"
    )
    assert not stale, (
        f"Stale rendered probe(s): {stale}. Run: "
        f".venv/Scripts/python.exe test/manual/render_probes.py"
    )


def test_probe_revision_hashes_only_its_transitive_template_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    render = _load_renderer()
    monkeypatch.setattr(render, "TEMPLATES", tmp_path)
    probe = tmp_path / "probe.js.j2"
    used = tmp_path / "_used.js.j2"
    nested = tmp_path / "_nested.js.j2"
    unrelated = tmp_path / "_unrelated.js.j2"
    probe.write_text('{% include "_used.js.j2" %}\nprobe\n', encoding="utf-8")
    used.write_text('{% include "_nested.js.j2" %}\nused\n', encoding="utf-8")
    nested.write_text("nested\n", encoding="utf-8")
    unrelated.write_text("unrelated\n", encoding="utf-8")

    initial = render.revision_of(probe)
    unrelated.write_text("changed but unused\n", encoding="utf-8")
    assert render.revision_of(probe) == initial

    nested.write_text("changed and used\n", encoding="utf-8")
    assert render.revision_of(probe) != initial


def test_probes_carry_no_tenant_url() -> None:
    """A tenant URL committed here has leaked twice, both times through a
    SITE_URL field an operator edited. Probes read the site they are pasted
    into and must never carry one."""
    sources = _all_probe_sources()
    offenders = [
        f"{path.name}: {host}"
        for path in sources
        for host in re.findall(
            r"https://[a-z0-9-]+\.sharepoint\.com", path.read_text(encoding="utf-8"),
        )
        if not PLACEHOLDER_HOSTS.match(host)
    ]
    assert len(sources) >= _MIN_SOURCES, (
        f"only {len(sources)} probe sources scanned, so this pins nothing"
    )
    assert not offenders, f"Tenant URL in probe(s): {offenders}"


# A probe's OUTPUT is as sensitive as its source. test_probes_carry_no_tenant_url
# globs *.js and templates/*.js.j2, so a transcript committed beside them is
# invisible to it, and a transcript carries the tenant host, the operator's UPN
# and real item ids. A tenant URL has leaked out of this repo twice.
#
# .gitignore covers the filenames; this catches a force-add, a rename, or console
# output pasted into any other tracked file in that directory.
#
# TRACKED files, not files on disk: a transcript sitting locally is the normal
# and intended state. The operator has to keep it to quote findings from. Only
# committing one is the failure. Scoped to test/manual/ because that is where
# probes run and where their output lands; it is not a repo-wide secret scan.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PLACEHOLDER_EMAIL = re.compile(
    r"@(example|contoso|tenant|yourtenant)\.", re.IGNORECASE,
)


def _tracked_manual_files() -> list[Path]:
    """Every file under test/manual that git is actually tracking."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "test/manual"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Skipping is honest; returning [] would make the test vacuously pass
        # and it would stay green forever without checking anything.
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


def test_no_tracked_file_under_manual_names_a_tenant() -> None:
    """No committed file in test/manual may carry a real tenant host or a
    real address, which is what a probe transcript is made of."""
    offenders = []
    for path in _tracked_manual_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        offenders += [
            f"{path.name}: {host}"
            for host in re.findall(r"https://[a-z0-9-]+\.sharepoint\.com", text)
            if not PLACEHOLDER_HOSTS.match(host)
        ]
        offenders += [
            f"{path.name}: {address}"
            for address in EMAIL.findall(text)
            if not PLACEHOLDER_EMAIL.search(address)
        ]
    assert not offenders, (
        f"Tenant host or address in tracked probe file(s): {offenders}. Probe "
        f"transcripts must stay untracked. Quote findings into code comments "
        f"instead of committing the raw console output."
    )


WRITE_CALL = re.compile(r"""method:\s*['"](POST|MERGE|DELETE|PUT)['"]""")

# Flags that must ship off. CLEANUP is here because it is the most
# destructive of the three (it recycles the probe's list and its items
# before the run), and a probe committed with it on would do that to
# whoever pasted the file. CLEANUP_AT_END is the legacy probe's separate,
# opposite-timing flag; it is guarded for the same reason.
GUARD_FLAGS = ("CONFIRMED", "ALLOW_WRITES", "CLEANUP", "CLEANUP_AT_END")


def test_a_probe_that_writes_defaults_to_read_only() -> None:
    """A probe that can write must describe what it would do and stop,
    until the operator opts in.

    Both guards are checked as committed, not as designed: this repository
    has twice committed an operator's local run-edit, and a probe whose
    guard ships flipped to true writes to the tenant of whoever pastes it.

    A read-only probe needs no guard, so the requirement is conditional on
    the script actually containing a write call.
    """
    guarded = 0
    for path in _probe_scripts():
        text = path.read_text(encoding="utf-8")
        if not WRITE_CALL.search(text):
            continue
        guarded += 1
        declared = {
            flag: value
            for flag in GUARD_FLAGS
            if (m := re.search(rf"^\s*(?:const|let|var)\s+{flag}\s*=\s*(\w+)", text, re.MULTILINE))
            and (value := m.group(1))
        }
        assert declared, (
            f"{path.name} performs writes but declares no guard. It needs at "
            f"least one of {', '.join(sorted(GUARD_FLAGS))}."
        )
        # How many guards a probe needs is its own business. One flag
        # gating everything is fine for a probe whose whole purpose is to
        # write. What is not negotiable is that each one ships off.
        for flag, value in declared.items():
            consequence = (
                "delete a list and its items on"
                if flag.startswith("CLEANUP")
                else "write to"
            )
            assert value == "false", (
                f"{path.name}: {flag} is committed as {value!r}. Pasting this "
                f"file would {consequence} the tenant of whoever ran it, "
                f"without asking. It must be committed as false."
            )
    assert guarded >= _MIN_SCRIPTS, (
        f"only {guarded} writing probes checked, so this pins nothing"
    )


def test_every_recorded_question_is_registered_up_front() -> None:
    """A probe's summary must not be able to lie by omission.

    If questions are appended as they are answered, a probe that aborts
    early reports only what it reached, and prints "0 not established"
    while most of its questions were never asked. Registering every
    question with expect() up front makes an abort report the truth.
    """
    reporting = 0
    for path in _probe_scripts():
        text = path.read_text(encoding="utf-8")
        recorded = set(RECORD_CALL.findall(text))
        if not recorded:
            continue  # a probe using its own reporting style
        reporting += 1
        registered = set(EXPECT_CALL.findall(text))
        # BOOT-style ids report a bootstrap failure rather than answering a
        # declared question, so they are not expected to be pre-registered.
        missing = {q for q in recorded - registered if not q.startswith("BOOT")}
        assert not missing, (
            f"{path.name}: question(s) {sorted(missing)} can be recorded but are "
            f"never registered with expect(). If the run aborts before reaching "
            f"them, the summary will not report them as unanswered."
        )
    assert reporting >= _MIN_SCRIPTS, (
        f"only {reporting} probes using record() checked, so this pins nothing"
    )


def test_question_call_detector_ignores_comments_and_strings() -> None:
    text = """\
      // record('COMMENT', 'not a call')
      const example = "record('STRING', 'not a call')";
      record('REAL', 'a call');
      expect('REAL', 'a call');
    """
    assert RECORD_CALL.findall(text) == ["REAL"]
    assert EXPECT_CALL.findall(text) == ["REAL"]


def test_probes_carry_no_control_characters() -> None:
    """A NUL byte reached generated deploy.js on this branch and was
    invisible to ruff, mypy, j2lint, the golden comparison and the whole
    suite. Only git showed it, as 'Bin N -> M bytes'."""
    sources = _all_probe_sources()
    assert len(sources) >= _MIN_SOURCES, (
        f"only {len(sources)} probe sources scanned, so this pins nothing"
    )
    for path in sources:
        found = CONTROL_CHARS.findall(path.read_text(encoding="utf-8"))
        assert not found, (
            f"{path.name}: control character(s) {[hex(ord(c)) for c in found]}"
        )


def test_rendered_probes_are_syntactically_valid() -> None:
    """Without this, an operator discovers a probe does not parse by
    pasting it into a live tenant."""
    scripts = _probe_scripts()
    assert len(scripts) >= _MIN_SCRIPTS, (
        f"only {len(scripts)} probes parsed, so this pins nothing"
    )
    for path in scripts:
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"{path.name} does not parse:\n{result.stderr}"


# === The threshold fixture's two halves must agree ==========================

THRESHOLD_PROBE = MANUAL / "threshold-index-probe.js"


def _threshold_rows() -> ModuleType:
    """The row generator, loaded the same by-path way as render_probes."""
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_threshold_rows_gate", MANUAL / "make_threshold_rows.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_probe_provisions_every_column_the_csv_supplies() -> None:
    """Two files have to agree on one column set. A column written to the CSV
    but never provisioned loads into nothing; one provisioned but never written
    is silently always blank. Either way the fixture stops testing what it
    claims to, and the probe would report a confident SERVED about an empty
    column."""
    rows = _threshold_rows()
    probe = THRESHOLD_PROBE.read_text(encoding="utf-8")
    for header in rows.HEADERS:
        if header == "Title":
            continue  # the platform provides it
        # Person and Lookup arrive as OwnerId/ParentId in the CSV, because that
        # is what the REST body needs, but are provisioned as Owner/Parent.
        provisioned = header.removesuffix("Id") if header.endswith("Id") else header
        assert f"'{provisioned}'" in probe, (
            f"{header!r} is written to the CSV but {provisioned!r} never appears "
            f"in {THRESHOLD_PROBE.name}. One of the two files is wrong."
        )


def test_the_probe_and_the_generator_agree_on_the_checkpoints() -> None:
    """The probe asserts the live ItemCount against these. A drift files every
    observation under a row count the list never held."""
    rows = _threshold_rows()
    probe = THRESHOLD_PROBE.read_text(encoding="utf-8")
    expected = f"const CHECKPOINTS = [{', '.join(str(c) for c in rows.CHECKPOINTS)}];"
    assert expected in probe, f"expected {expected!r} in {THRESHOLD_PROBE.name}"


def test_the_probe_and_the_generator_agree_on_the_fixture_size() -> None:
    """The probe divides ItemCount by TOTAL/MATCHING_ROWS to get the expected
    match count for every selectivity-matched filter. If either constant drifts
    from the generator, every one of those filters compares its result against
    the wrong number and reports NOT ESTABLISHED across the board."""
    rows = _threshold_rows()
    probe = THRESHOLD_PROBE.read_text(encoding="utf-8")
    assert f"const FIXTURE_TOTAL = {rows.TOTAL};" in probe
    assert f"const MATCHING_ROWS = {rows.MATCHING_ROWS};" in probe
    assert f"const RARE_BUCKET = '{rows.RARE_BUCKET}';" in probe


def test_every_selectivity_matched_population_divides_every_checkpoint() -> None:
    """The probe's expected match count is ItemCount / (TOTAL / MATCHING_ROWS),
    floored. That is only EXACT at every checkpoint while each checkpoint is a
    whole multiple of that ratio. Otherwise the count is off by one at some
    checkpoints and every matched filter there reads NOT ESTABLISHED for
    arithmetic reasons rather than SharePoint ones."""
    rows = _threshold_rows()
    per_hundred = rows.TOTAL // rows.MATCHING_ROWS
    for checkpoint in rows.CHECKPOINTS:
        assert checkpoint % per_hundred == 0, (
            f"checkpoint {checkpoint} is not a multiple of {per_hundred}, so the "
            f"probe's expected match count is not exact there"
        )
        # And the offsets must all fall below the ratio, or a population is not
        # evenly spread across the prefix the checkpoint cuts.
        for offset in (rows._Z_OFFSET, rows._NULL_OFFSET,
                       rows._OWNER_OFFSET, rows._PARENT_OFFSET):
            assert 0 < offset < per_hundred, f"offset {offset} is outside 1..{per_hundred - 1}"


def test_the_js_and_python_row_generators_agree() -> None:
    """One row composition, two implementations, and drift between them is
    invisible.

    The probe can now build its own fixture in the browser, so the rows exist
    in JavaScript as well as in make_threshold_rows.py. Every expected match
    count in the probe is computed from these offsets, so a divergence does
    not fail loudly, it reports NOT ESTABLISHED across the whole table and
    reads like a SharePoint finding.

    Executes the partial under node over all 6,000 rows and compares field by
    field. Not a spot check: an offset that drifts by one still produces 60
    matches, so only whole-row identity catches it.
    """
    render = _load_renderer()
    rows = _threshold_rows()
    partial = (TEMPLATES / "_threshold_rows.js.j2").read_text(encoding="utf-8")
    # Render it alone, wrapped in a driver. The partial is written to be valid
    # on its own for exactly this. A fragment buried in the probe's async IIFE
    # could not be executed without the whole tenant-facing script around it.
    driver = (
        f"{render._env().from_string(partial).render()}\n"
        "const out = [];\n"
        f"for (let r = 1; r <= {rows.TOTAL}; r += 1) "
        "out.push(thresholdRow(r, 11, 1));\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "rows.js"
        script.write_text(driver, encoding="utf-8")
        result = subprocess.run(
            ["node", str(script)], capture_output=True, text=True, check=False,
        )
    assert result.returncode == 0, f"the JS generator did not run:\n{result.stderr}"
    from_js = json.loads(result.stdout)
    from_py = rows.as_json_rows(
        rows.build_rows(owner_id="11", parent_id="1"),
    )
    assert len(from_js) == len(from_py) == rows.TOTAL
    mismatches = [
        f"row {i + 1}: js={js!r} py={py!r}"
        for i, (js, py) in enumerate(zip(from_js, from_py, strict=True))
        if js != py
    ]
    assert not mismatches, (
        f"{len(mismatches)} row(s) differ between _threshold_rows.js.j2 and "
        f"make_threshold_rows.py. First three: {mismatches[:3]}"
    )


def test_a_probe_sending_metadata_uses_verbose_odata() -> None:
    """`__metadata` is a VERBOSE OData construct. Sent with the harness's
    default `odata=nometadata` content type, SharePoint rejects the whole
    request with HTTP 400.

    Not hypothetical: the threshold probe's first live run failed all four of
    its index MERGEs exactly this way. Its body was byte-identical to the
    deployer's proven patchField (same URL, same IF-MATCH, same
    X-HTTP-Method, same __metadata), and the only difference was that
    _http_write.js.j2 sends odata=verbose and _probe_harness.js.j2 sends
    odata=nometadata.

    Asserts on CONTENT-TYPE specifically, not on the string "odata=verbose".
    The first version of this test looked for the latter and passed on a probe
    with the bug, because the harness's getDigest sets an `Accept` of
    `application/json;odata=verbose`, so that string is in every probe here
    whether or not any write uses it. What decides how SharePoint parses a
    request BODY is Content-Type.
    """
    verbose_content_type = "'Content-Type': 'application/json;odata=verbose'"
    # The object-literal form, not the bare word. Two probes explain in prose
    # why they do NOT send __metadata, and "__metadata: the harness sends..."
    # matched a looser pattern, flagging the files that got this right.
    sends_metadata = re.compile(r"__metadata\s*:\s*\{")
    checked = 0
    for path in _probe_scripts():
        text = path.read_text(encoding="utf-8")
        if not sends_metadata.search(text):
            continue
        checked += 1
        assert verbose_content_type in text, (
            f"{path.name} sends __metadata but never sets a verbose "
            f"Content-Type. SharePoint answers 400, __metadata is meaningless "
            f"to a nometadata endpoint. Override Content-Type in that call's "
            f"spPost extraHeaders, as _http_write.js.j2 does."
        )
    assert checked >= _MIN_METADATA_PROBES, (
        f"only {checked} probes sending __metadata checked, so this pins nothing"
    )
