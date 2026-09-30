"""Execute item-versions-payload-probe.js under node against a mock web.

The mock (`_versions_mock.py`) records a version on every item create and MERGE, and on a
file's content upload unless told not to, and answers `items(id)/versions` newest first. Each
case below reaches one branch of the probe: a healthy run, each fixture failing, the versions
read refused or throttled, the library case, and the identity masking every person value
passes through.
"""

import json
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import catalogued_dependents, run_probe, voided
from _versions_mock import VERSIONS_MOCK

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-versions-payload-probe.js"
USER = "field.version.control-current-user"
TARGET = "field.version.fixture-payload-target-list"
LIST = "field.version.fixture-payload-list"
COLUMNS = "field.version.fixture-payload-columns"
PEOPLE_COLUMN = "field.version.fixture-payload-people-column"
ITEM = "field.version.fixture-payload-item"
PEOPLE_WRITE = "field.version.fixture-payload-people-write"
READ = "field.version.control-payload-versions-read"
KINDS = ("choice", "multichoice", "person", "people", "lookup", "date", "datetime", "number",
         "boolean")
PAYLOAD = [f"field.version.payload-{kind}" for kind in KINDS]
FIELDS = "field.version.payload-version-fields"
ORDER = "field.version.versionid-follows-label"
LIBRARY = "field.version.fixture-library"
LIB_FOLDER = "field.version.fixture-library-folder"
LIB_UPLOAD = "field.version.fixture-library-upload"
LIB_READ = "field.version.control-library-versions-read"
LIB_ADDS = "field.version.library-upload-adds-version"
LIB_FIELDS = "field.version.library-upload-version-fields"
LIB_FIXTURES = (LIBRARY, "field.version.fixture-library-column", LIB_FOLDER,
                "field.version.fixture-library-file", "field.version.fixture-library-edit-first",
                LIB_UPLOAD, "field.version.fixture-library-edit-second", LIB_READ)
RECYCLED = ["web/lists/getbytitle('dbmlsp Probe VersionsLibrary')/recycle",
            "web/lists/getbytitle('dbmlsp Probe Versions')/recycle",
            "web/lists/getbytitle('dbmlsp Probe VersionsTarget')/recycle"]
OWNED = "dbml-sharepoint item-versions probe scratch list. Safe to delete."
LIST_READ_RULE = "Versions')/items(1)/versions"
TENANT_TEXT = "Refused at https://example.sharepoint.com/sites/probe/_api/web"


def _run(gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(VERSIONS_MOCK, PROBE, gates, config)


def _deps(fixture: str) -> set[str]:
    return catalogued_dependents(PROBE.name, fixture)


def _recycled(sent: list[dict[str, str]]) -> list[str]:
    return [r["path"] for r in sent if r["path"].endswith("/recycle")]


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_a_healthy_run_records_every_kind_as_each_version_carried_it() -> None:
    rows, sent, _ = _run()

    for row_id in (USER, TARGET, LIST, COLUMNS, PEOPLE_COLUMN, ITEM, PEOPLE_WRITE, READ):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    for row_id in PAYLOAD:
        assert rows[row_id]["outcome"] == "OBSERVED", rows[row_id]
        assert rows[row_id]["state"] == "settled"
    choice = rows["field.version.payload-choice"]["evidence"]
    assert choice.startswith("3 version(s) in the order answered; "
                             "properties beginning ProbeChoice: ProbeChoice; "
                             "3.0: {ProbeChoice=\"Q2\"}; 2.0: {ProbeChoice=\"Q1\"}; "
                             "1.0: {ProbeChoice=(absent)}")
    assert "ProbeNumber=2.25" in rows["field.version.payload-number"]["evidence"]
    assert _recycled(sent) == RECYCLED


def test_the_version_fields_row_counts_each_of_the_four_and_lists_the_first_entry() -> None:
    rows, _, _ = _run()

    said = rows[FIELDS]["evidence"]
    assert said.startswith("VersionId on 3 of 3; VersionLabel on 3 of 3; Editor on 3 of 3; "
                           "Modified on 3 of 3. Per version: VersionId=1536, VersionLabel=\"3.0\"")
    assert ("The first entry answered carries: Editor, IsCurrentVersion, Modified, ProbeChoice"
            in said)


@pytest.mark.parametrize(("versions", "outcome", "evidence"), [
    pytest.param({}, "INCREASES WITH LABEL",
                 "3 version(s), in label order: 1.0=512, 2.0=1024, 3.0=1536", id="rising"),
    pytest.param({"versionIds": "falling"}, "DOES NOT INCREASE WITH LABEL",
                 "3 version(s), in label order: 1.0=1536, 2.0=1024, 3.0=512", id="falling"),
    pytest.param({"versionIds": "text"}, "NOT COMPARABLE",
                 '3 version(s), in the order answered: 3.0="1536", 2.0="1024", 1.0="512"',
                 id="text"),
])
def test_how_versionids_fall_in_label_order_is_named(
        versions: dict[str, str], outcome: str, evidence: str) -> None:
    rows, _, _ = run_probe(VERSIONS_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), versions)

    assert rows[ORDER]["outcome"] == outcome
    assert rows[ORDER]["evidence"] == evidence
    assert rows[ORDER]["state"] == "settled"


def test_a_person_value_is_recorded_with_the_account_masked() -> None:
    rows, _, _ = _run()

    person = rows["field.version.payload-person"]["evidence"]
    assert '"LookupValue":"<name>"' in person
    assert '"Email":"<account>"' in person
    everything = json.dumps(rows)
    assert "ada@example.com" not in everything
    assert "Ada Probe" not in everything


def test_an_email_the_probe_did_not_learn_is_still_masked() -> None:
    rows, _, _ = _run(versionEmail="bob@example.com")

    assert rows[USER]["outcome"] == "PASS"
    person = rows["field.version.payload-person"]["evidence"]
    assert '"Email":"<account>"' in person
    assert "bob@example.com" not in json.dumps(rows)


def test_a_column_no_version_carries_is_recorded_absent_not_failed() -> None:
    rows, _, _ = _run(versionsOmit=["ProbeFlag"])

    assert rows["field.version.payload-boolean"]["outcome"] == "ABSENT"
    assert rows["field.version.payload-boolean"]["state"] == "settled"
    boolean = rows["field.version.payload-boolean"]["evidence"]
    assert "properties beginning ProbeFlag: none" in boolean
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"


def test_a_refused_multi_person_column_voids_only_its_own_row() -> None:
    rows, sent, _ = _run(rules=[{"contains": "createfieldasxml", "status": 500,
                                 "text": TENANT_TEXT}])

    assert rows[PEOPLE_COLUMN]["outcome"] == "FAIL"
    assert voided(rows) == _deps(PEOPLE_COLUMN) == {PEOPLE_WRITE, "field.version.payload-people"}
    assert rows[ITEM]["outcome"] == "PASS"
    assert rows["field.version.payload-person"]["outcome"] == "OBSERVED"
    assert not [r for r in sent if "ProbePeopleId" in r["body"]]


def test_a_refused_multi_person_write_leaves_its_question_open_and_the_probe_going() -> None:
    rows, sent, _ = _run(rules=[{"contains": "Versions')/items(1)", "verb": "MERGE",
                                 "bodyContains": "ProbePeopleId", "status": 400,
                                 "text": "Invalid data for ada@example.com"}])

    assert rows[PEOPLE_WRITE]["outcome"] == "NOT ESTABLISHED"
    assert rows[PEOPLE_WRITE]["state"] == "open"
    refusal = rows[PEOPLE_WRITE]["evidence"]
    assert "the write was refused: HTTP 400: Invalid data for <account>" in refusal
    assert rows["field.version.payload-people"]["outcome"] == "NOT ESTABLISHED"
    assert rows["field.version.payload-people"]["state"] == "open"
    assert rows[ITEM]["outcome"] == "PASS"
    assert rows[READ]["outcome"] == "PASS"
    assert rows["field.version.payload-person"]["outcome"] == "OBSERVED"
    assert "3 version(s)" in rows["field.version.payload-choice"]["evidence"]
    assert voided(rows) == set()
    merges = [r["body"] for r in sent
              if r["verb"] == "MERGE" and "Versions')/items(1)" in r["path"]]
    assert ["ProbePeopleId" in body for body in merges] == [True, False, False]


def test_a_refused_column_create_voids_what_follows_and_all_three_are_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "bodyContains": "ProbeFlag",
                                 "status": 500, "text": "This field type is not supported."}])

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert 'ProbeFlag.Read differs: read "HTTP 400: ' in rows[COLUMNS]["evidence"]
    assert voided(rows) == _deps(COLUMNS)
    assert len(_recycled(sent)) == 3


@pytest.mark.parametrize("status", [400, 500])
def test_a_refused_versions_read_voids_every_observation(status: int) -> None:
    rows, sent, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": status,
                                 "text": TENANT_TEXT}])

    assert rows[READ]["outcome"] == "FAIL"
    assert f"HTTP {status}: Refused at [TENANT]/sites/probe/_api/web" in rows[READ]["evidence"]
    assert voided(rows) == _deps(READ)
    assert _recycled(sent) == RECYCLED


@pytest.mark.parametrize("status", [429, 503, 403])
def test_a_throttled_or_denied_versions_read_leaves_the_observations_open(status: int) -> None:
    rows, sent, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": status, "text": "busy"}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    for row_id in PAYLOAD:
        assert rows[row_id]["state"] == "open", rows[row_id]
        assert "a re-run can ask it" in rows[row_id]["evidence"]
    assert _recycled(sent) == RECYCLED


def test_a_versions_answer_with_no_entries_fails_the_control() -> None:
    rows, _, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": 200,
                              "text": '{"value": []}'}])

    assert rows[READ]["outcome"] == "FAIL"
    assert "HTTP 200, 0 entries" in rows[READ]["evidence"]
    assert voided(rows) == _deps(READ)


def test_an_unread_account_voids_everything_and_writes_nothing() -> None:
    rows, sent, _ = _run(rules=[{"contains": "web/currentuser", "status": 403, "text": "denied"}])

    assert rows[USER]["outcome"] == "FAIL"
    assert voided(rows) == _deps(USER)
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_a_target_item_without_an_id_voids_what_follows_and_recycles_the_target() -> None:
    rows, sent, _ = _run(rules=[{"contains": "VersionsTarget')/items", "status": 400,
                                 "text": "no"}])

    assert rows[TARGET]["outcome"] == "FAIL"
    assert "0 of its two items answered an Id" in rows[TARGET]["evidence"]
    assert voided(rows) == _deps(TARGET)
    assert _recycled(sent) == [RECYCLED[0], RECYCLED[2]]


def test_a_refused_item_write_fails_the_item_and_voids_the_versions_rows() -> None:
    rows, _, _ = _run(rules=[{"contains": "Versions')/items(1)", "verb": "MERGE", "status": 400,
                              "text": "The property does not exist."}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 1, declared 3" in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_list_whose_versioning_does_not_stick_voids_everything_after_it() -> None:
    rows, _, _ = _run(listMerge={"EnableVersioning": False})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "EnableVersioning differs: read false, declared true" in rows[LIST]["evidence"]
    assert rows[LIBRARY]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIST) | _deps(LIBRARY)


def test_a_foreign_list_holding_the_title_is_never_written_to() -> None:
    foreign = {"Id": "x", "BaseTemplate": 100, "Description": "somebody else's", "fields": {},
               "items": []}
    rows, sent, _ = _run(lists={"dbmlsp Probe Versions": foreign})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "refusing to modify it" in rows[LIST]["evidence"]
    assert not [r for r in sent if "Probe Versions')" in r["path"] and r["verb"] != "GET"]
    assert _recycled(sent) == [RECYCLED[0], RECYCLED[2]]


def test_a_leftover_list_without_cleanup_is_refused() -> None:
    leftover = {"Id": "x", "BaseTemplate": 100, "Description": OWNED, "fields": {}, "items": []}
    rows, _, _ = _run(lists={"dbmlsp Probe Versions": leftover})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "CLEANUP is off" in rows[LIST]["evidence"]
    assert voided(rows) == _deps(LIST)


def test_with_cleanup_a_leftover_list_is_recycled_and_built_again() -> None:
    leftover = {"Id": "x", "BaseTemplate": 100, "Description": OWNED, "fields": {}, "items": []}
    rows, sent, _ = _run(("CONFIRMED", "ALLOW_WRITES", "CLEANUP"),
                         lists={"dbmlsp Probe Versions": leftover})

    assert rows[LIST]["outcome"] == "PASS"
    assert len([p for p in _recycled(sent) if "Probe Versions'" in p]) == 2


def test_a_digest_lost_mid_run_leaves_the_rest_open_and_asks_for_a_recycle_by_hand() -> None:
    rows, sent, output = _run(digestsAllowed=4)

    assert rows[TARGET]["outcome"] == "PASS"
    assert all(rows[row_id]["state"] == "open" for row_id in [*PAYLOAD, READ, ITEM])
    assert "probe aborted: contextinfo failed: HTTP 403" in output
    assert "could not recycle 'dbmlsp Probe VersionsTarget'" in output
    assert "recycle it by hand" in output
    assert _recycled(sent) == []


def test_a_refusal_quoting_the_site_url_is_recorded_without_the_tenant() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/lists", "verb": "POST", "status": 500,
                              "text": TENANT_TEXT}])

    assert rows[TARGET]["outcome"] == "FAIL"
    assert "[TENANT]/sites/probe/_api/web" in rows[TARGET]["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)


def test_a_library_file_records_whether_its_upload_added_a_version() -> None:
    rows, sent, _ = _run()

    for row_id in LIB_FIXTURES:
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED A VERSION"
    assert rows[LIB_ADDS]["evidence"] == (
        '4 version(s) for an add, two edits and an upload, after which ProbeLibChoice read "Q1"; '
        'in label order: 1.0=(absent), 2.0="Q1", 3.0="Q1", 4.0="Q2"')
    fields = rows[LIB_FIELDS]["evidence"]
    assert rows[LIB_FIELDS]["outcome"] == "OBSERVED"
    assert fields.startswith('3.0 carries: Editor={"LookupId":7,"LookupValue":"<name>",')
    assert 'ProbeLibChoice="Q1"; VersionId=1536; VersionLabel="3.0"' in fields
    upload = next(r for r in sent if r["verb"] == "PUT")
    assert upload["path"].endswith("dbmlsp-subfolder/dbmlsp-versions.txt')/$value")
    assert upload["body"] == "dbmlsp versions content 2"


def test_an_upload_that_adds_no_version_is_named_so() -> None:
    rows, _, _ = _run(uploadAddsNoVersion=True)

    assert rows[LIB_UPLOAD]["outcome"] == "PASS"
    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED NO VERSION"
    assert rows[LIB_ADDS]["evidence"].endswith('1.0=(absent), 2.0="Q1", 3.0="Q2"')
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["state"] == "settled"
    assert rows[LIB_FIELDS]["evidence"].startswith(
        "no version is the upload's alone (UPLOAD ADDED NO VERSION); the versions: ")


def test_an_upload_that_changes_the_value_is_recorded_not_failed() -> None:
    rows, _, _ = _run(uploadSetsValues={"ProbeLibChoice": "Q2"})

    assert rows[LIB_UPLOAD]["outcome"] == "PASS"
    assert rows[LIB_ADDS]["outcome"] == "UPLOAD CHANGED THE VALUE"
    assert rows[LIB_ADDS]["state"] == "settled"
    assert rows[LIB_ADDS]["evidence"] == (
        '4 version(s) for an add, two edits and an upload, after which ProbeLibChoice read "Q2"; '
        'in label order: 1.0=(absent), 2.0="Q1", 3.0="Q2", 4.0="Q2"')
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["evidence"] == (
        "the versions were not searched for the upload's version, since the head is "
        'UPLOAD CHANGED THE VALUE; the versions: 1.0=(absent), 2.0="Q1", 3.0="Q2", 4.0="Q2"')
    assert voided(rows) == set()


@pytest.mark.parametrize(("config", "head"), [
    pytest.param({}, "NOT COMPARABLE", id="kept"),
    pytest.param({"uploadSetsValues": {"ProbeLibChoice": "Q2"}}, "UPLOAD CHANGED THE VALUE",
                 id="changed"),
])
def test_labels_that_do_not_order_yield_to_a_changed_value(config: dict[str, Any], head: str,
                                                            ) -> None:
    rows, _, _ = _run(labelsUnparsed=True, **config)

    assert rows[LIB_ADDS]["outcome"] == head
    assert "in the order answered: v4=" in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["evidence"].startswith(
        f"the versions were not searched for the upload's version, since the head is {head}; ")
    assert "alone" not in rows[LIB_FIELDS]["evidence"]


def test_a_read_after_the_upload_without_the_choice_fails_the_fixture_not_the_value() -> None:
    rows, _, _ = _run(uploadDropsValues=["ProbeLibChoice"])

    assert rows[LIB_UPLOAD]["outcome"] == "FAIL"
    assert "ProbeLibChoice is absent from the payload" in rows[LIB_UPLOAD]["evidence"]
    assert voided(rows) == _deps(LIB_UPLOAD)
    assert rows[LIB_ADDS]["outcome"] != "UPLOAD CHANGED THE VALUE"


@pytest.mark.parametrize(("rule", "quoted"), [
    pytest.param({"contains": "getbyinternalnameortitle('ProbeFlag')", "status": 400,
                  "text": "Invalid data for ada@example.com"},
                 'ProbeFlag.Read differs: read "HTTP 400: Invalid data for <account>"',
                 id="column-read"),
    pytest.param({"contains": "Versions')/items(1)", "verb": "MERGE", "status": 400,
                  "text": "Invalid data for ada@example.com"},
                 "item MERGE: HTTP 400 Invalid data for <account>", id="item-merge"),
    pytest.param({"contains": "/fields", "verb": "POST", "bodyContains": "ProbeFlag", "status": 500,
                  "text": "Refused for i:0#.f|membership|ada@example.com"},
                 "create ProbeFlag: HTTP 500 Refused for <account>", id="column-create"),
])
def test_a_refusal_quoting_an_account_is_masked_everywhere_it_is_printed(
        rule: dict[str, Any], quoted: str) -> None:
    rows, _, output = _run(rules=[rule])

    assert quoted in output
    if rule["contains"].startswith("getbyinternalnameortitle"):
        assert quoted in rows[COLUMNS]["evidence"]
    assert "ada@example.com" not in output
    assert "ada@example.com" not in json.dumps(rows)


def test_a_refused_upload_voids_what_rests_on_it_and_nothing_in_the_list_case() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/$value", "verb": "PUT", "status": 500,
                                 "text": "The file is locked."}])

    assert rows[LIB_UPLOAD]["outcome"] == "FAIL"
    assert 'Uploaded differs: read "HTTP 500"' in rows[LIB_UPLOAD]["evidence"]
    assert voided(rows) == _deps(LIB_UPLOAD)
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"
    assert _recycled(sent) == RECYCLED


def test_a_folder_that_is_not_created_voids_the_file_and_everything_after() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/folders", "verb": "POST", "status": 500,
                              "text": "Access denied."}])

    assert rows[LIB_FOLDER]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIB_FOLDER)
    assert rows[ORDER]["outcome"] == "INCREASES WITH LABEL"


def test_a_library_with_minor_versions_on_is_not_used() -> None:
    rows, _, _ = _run(libraryMerge={"EnableMinorVersions": True})

    assert rows[LIBRARY]["outcome"] == "FAIL"
    assert "EnableMinorVersions differs: read true, declared false" in rows[LIBRARY]["evidence"]
    assert voided(rows) == _deps(LIBRARY)
    assert rows[LIST]["outcome"] == "PASS"


def test_a_refused_library_versions_read_voids_only_the_library_observations() -> None:
    rows, _, _ = _run(rules=[{"contains": "Library')/items(1)/versions", "status": 400,
                              "text": "no"}])

    assert rows[LIB_READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIB_READ) == {LIB_ADDS, LIB_FIELDS}
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"
