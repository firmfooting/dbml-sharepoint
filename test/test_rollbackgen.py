# test/test_rollbackgen.py
import re
from typing import Any

from _paths import FIXTURES

from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.generators.rollbackgen import generate_rollback_js
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import Release, load_release

_COMMON_ARGS: dict[str, Any] = dict(
    site_url="https://example.sharepoint.com/sites/test",
    site_role="default",
    source_dbml="simple.dbml",
    generated_at="2026-05-04T00:00:00Z",
)


def _load_fixtures() -> tuple[Schema, MappingBundle, Release]:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    return schema, bundle, release


def test_rollback_includes_typed_confirmation_and_target_lists() -> None:
    schema, bundle, release = _load_fixtures()

    js = generate_rollback_js(
        schema=schema,
        bundle=bundle,
        release=release,
        **_COMMON_ARGS,
    )
    assert "APP_Project" in js
    assert "APP_Task" in js
    assert "DELETE NON-EMPTY" in js
    assert "site leaf" in js.lower()


def test_rollback_prompts_per_non_empty_list() -> None:
    """A6: each non-empty list requires its own DELETE NON-EMPTY confirmation.
    The old single global `allowNonEmpty` latch (one confirmation authorised
    deleting EVERY remaining non-empty list) is removed — a coarse blast radius
    for a live site."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "allowNonEmpty" not in js
    assert "DELETE NON-EMPTY" in js


def test_rollback_uses_odata_name_escaping() -> None:
    """A6/A5: rollback resolves lists via odataName (doubles embedded
    apostrophes) rather than bare encodeURIComponent."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "const odataName" in js
    assert "getbytitle('${odataName(" in js
    assert "getbytitle('${encodeURIComponent(" not in js


def test_rollback_uses_web_prefixed_api_urls() -> None:
    """Same regression guard as deploy.js: every SP REST endpoint must
    be prefixed with the current web's server-relative URL. A bare
    '/_api/...' would target the tenant root web and silently DELETE
    lists from the wrong site."""
    schema, bundle, release = _load_fixtures()

    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )

    assert "const WEB = actualPath" in js
    assert "const apiUrl = (suffix) =>" in js
    assert "${WEB}/_api/${suffix}" in js

    code_lines = [
        line for line in js.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    ]
    lines_with_bare_api = [
        line for line in code_lines
        if ("'/_api/" in line or "`/_api/" in line) and "apiUrl" not in line
    ]
    assert lines_with_bare_api == [], (
        "rollback.js contains bare '/_api/' URL literals in code (which "
        "would target the tenant root web on sub-sites). Use apiUrl(suffix). "
        "Offending lines:\n" + "\n".join(lines_with_bare_api)
    )


def test_rollback_refreshes_digest_per_delete() -> None:
    """Regression: the request digest must be refreshed inside the delete loop.
    A single pre-loop FormDigestValue expires (~30 min), so a rollback that
    pauses at confirmation prompts or processes many lists would start
    returning 403s mid-run and leave the site partially rolled back."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    loop_idx = js.index("for (const name of TARGET_LISTS)")
    # The digest is fetched within the loop body, not only before it.
    assert "const digest = await getDigest();" in js[loop_idx:]


def test_rollback_order_is_reverse_of_deploy_order() -> None:
    """Children must be deleted before parents to satisfy SP's referential
    integrity check (SP refuses to delete a list that a lookup column
    in another list still references). The rollback TARGET_LISTS must be
    the reverse of the deploy list_creation_order."""
    schema, bundle, release = _load_fixtures()

    deploy_js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        source_mtime="2026-05-04T00:00:00Z",
        **_COMMON_ARGS,
    )
    rollback_js = generate_rollback_js(
        schema=schema,
        bundle=bundle,
        release=release,
        **_COMMON_ARGS,
    )

    # Extract the ordered list titles from the SCHEMA.lists array in deploy.js.
    # Each list entry has a "title": "APP_..." key.
    deploy_titles = re.findall(r'"title":\s*"(APP_[^"]+)"', deploy_js)
    # Keep only the first occurrence of each (the list-level title, not column titles).
    seen: set[str] = set()
    deploy_order: list[str] = []
    for t in deploy_titles:
        if t not in seen:
            seen.add(t)
            deploy_order.append(t)

    # Extract TARGET_LISTS from rollback.js (the JSON array assigned to TARGET_LISTS).
    m = re.search(r'TARGET_LISTS\s*=\s*(\[.*?\]);', rollback_js, re.DOTALL)
    assert m, "TARGET_LISTS not found in rollback.js"
    import json
    rollback_order: list[str] = json.loads(m.group(1))

    assert deploy_order, "No lists found in deploy.js"
    assert rollback_order, "TARGET_LISTS is empty in rollback.js"

    # The fixture has APP_Project (parent) before APP_Task (child) in deploy order.
    # Rollback must have APP_Task before APP_Project.
    assert rollback_order == list(reversed(deploy_order)), (
        f"Rollback order {rollback_order} is not the reverse of deploy order {deploy_order}"
    )


def test_rollback_unlocks_deletion_blocked_lists_before_delete() -> None:
    """prevent_list_deletion deploys AllowDeletion=false, which blocks the
    list DELETE on every surface (REST included). Rollback must probe the
    ACTUAL state per list — only after that list's deletion is authorised,
    so skipped lists keep their protection — and MERGE AllowDeletion=true
    (readback-verified) before attempting the DELETE."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )

    assert "async function readAllowDeletion" in js
    assert "async function setAllowDeletion" in js
    assert "$select=AllowDeletion" in js
    assert "'X-HTTP-Method': 'MERGE'" in js

    # Ordering inside the loop: non-empty confirmation, then unlock probe,
    # then the DELETE verb.
    loop_idx = js.index("for (const name of TARGET_LISTS)")
    confirm_idx = js.index("DELETE NON-EMPTY", loop_idx)
    unlock_idx = js.index("await readAllowDeletion(name)", loop_idx)
    delete_idx = js.index("'X-HTTP-Method': 'DELETE'", loop_idx)
    assert loop_idx < confirm_idx < unlock_idx < delete_idx


def test_rollback_probe_failure_does_not_block_delete() -> None:
    """A dead AllowDeletion probe must never silently block teardown: on
    probe failure rollback logs a WARN and attempts the DELETE anyway (a
    list that really is protected then fails into summary.errors)."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "attempting delete anyway" in js


def test_rollback_relocks_when_delete_fails_after_unlock() -> None:
    """If rollback unlocked a deletion-blocked list and the DELETE still
    failed, it must best-effort restore AllowDeletion=false rather than
    leave the list unprotected on a partially rolled-back site."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "unlockedForDelete" in js
    relock_idx = js.index("setAllowDeletion(name, false)")
    throw_idx = js.index("throw new Error(`HTTP ${r.status}${detail ? ` — ${detail}` : ''}`)")
    assert relock_idx < throw_idx


def test_rollback_documents_why_sealed_columns_need_no_unseal() -> None:
    """Sealed columns get NO unseal pass (SP.Field.Sealed guards the field
    object — its schema edits and its own deletion — not deletion of the
    containing list). The generated script carries the rationale so a later
    maintainer doesn't 'fix' rollback by adding one."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "Do NOT add an unseal pass" in js


def test_rollback_header_carries_full_provenance() -> None:
    """A loose copy of rollback.js must be traceable to its exact build:
    release tag + schema/deployer versions + generation timestamp (same
    field set as deploy.js's header)."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "Release tag:  0.1.0-test" in js
    assert "Schema:       v0.8" in js
    assert "Deployer:     vdbml-sharepoint/0.1.0" in js
    assert "Generated at: 2026-05-04T00:00:00Z" in js


def test_rollback_demo_aware_non_empty_gate() -> None:
    """Demo cycle contract: a list whose items are ALL '[DEMO] '-prefixed
    deletes without the DELETE NON-EMPTY prompt (deploy, demonstrate,
    delete); any unmarked item keeps the per-list refusal, and unreadable
    or >100-item lists are treated as real."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "const DEMO_PREFIX = '[DEMO] ';" in js
    assert "allItemsAreDemo" in js
    assert "count > 100" in js
    assert "row.Title.startsWith(DEMO_PREFIX)" in js
    # The refusal prompt survives for real content.
    assert "DELETE NON-EMPTY" in js


def test_rollback_recycles_items_before_list_delete() -> None:
    """Live findings 2026-07-24 (two teardowns): retention refuses to
    delete a list that still CONTAINS items, while an emptied list deletes
    fine. Demo-only lists recycle their rows automatically (marker
    re-checked per row, fail closed); the DELETE NON-EMPTY override path
    recycles EVERY item — the operator just authorised deleting the list
    with its contents, and emptying first is what makes the delete
    succeed. recycle(), never a permanent DELETE."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "async function recycleItems(name, requireDemoMarker)" in js
    assert "/recycle()" in js
    assert "unmarked item" in js
    # Demo path: marker-enforced. Override path: everything, post-consent.
    assert "await recycleItems(name, true);" in js
    assert "await recycleItems(name, false);" in js
    override_idx = js.index("DELETE NON-EMPTY to delete THIS list")
    assert js.index("await recycleItems(name, false);") > override_idx


def test_rollback_surfaces_server_error_detail() -> None:
    """A bare 'HTTP 500' left a blocked teardown undiagnosable (live).
    The thrown error now carries SharePoint's error.message.value."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "error?.message?.value" in js
    assert "detail ? ` — ${detail}` : ''" in js


def test_rollback_retention_block_gets_targeted_advisory() -> None:
    """Live-confirmed 2026-07-24: retention blocks deleting a list that
    still contains items (an emptied list deletes fine); an EMPTY list
    still refused means a site-level hold. The advisory explains both;
    the script never bypasses compliance enforcement."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "/hold or retention policy/i.test(detail)" in js
    assert "compliance admin must release it" in js
    assert "learn.microsoft.com/purview/retention-policies-sharepoint" in js


def test_rollback_counts_ride_one_lists_enumeration() -> None:
    """A by-title ItemCount GET on an absent list answers 404 — painted
    red in the console and read as a failure (live, 2026-07-24). Counts
    now come from ONE always-200 lists enumeration."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "web/lists?$select=Title,ItemCount" in js
    assert "listCountsByTitle" in js
    assert "/ItemCount`" not in js


def test_rollback_rides_shared_transport() -> None:
    """All REST traffic goes through the shared _http partial: throttle
    retries (429/503 Retry-After), spHeaders for digest-bearing writes,
    spError for server error detail. No bare fetch() remains."""
    schema, bundle, release = _load_fixtures()
    js = generate_rollback_js(
        schema=schema, bundle=bundle, release=release, **_COMMON_ARGS,
    )
    assert "async function fetchWithRetry(" in js
    assert "const spHeaders = (digest, extra = {})" in js
    assert "const spError = (text)" in js
    assert "await fetch(apiUrl" not in js
