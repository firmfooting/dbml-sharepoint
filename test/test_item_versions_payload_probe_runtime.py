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
from _probe_runs import catalogued_dependents, ended_with_report, run_probe, voided
from _versions_mock import VERSIONS_MOCK, mock_list_id

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-versions-payload-probe.js"
USER = "field.version.control-current-user"
TARGET = "field.version.fixture-payload-target-list"
TARGET_ITEMS = "field.version.fixture-payload-target-items"
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
TITLES = ("dbmlsp Probe VersionsLibrary", "dbmlsp Probe Versions", "dbmlsp Probe VersionsTarget")
RECYCLED = [f"web/lists(guid'{mock_list_id(title)}')/recycle" for title in TITLES]
LEFTOVER_ID = "00000000-0000-4000-8000-00000000abcd"
OWNED = "dbml-sharepoint item-versions probe scratch list. Safe to delete."
# Where the mock serves each scratch list by the Id it gave it, which is how the probe writes to it.
LIST_AT = f"{mock_list_id('dbmlsp Probe Versions')}')"
TARGET_AT = f"{mock_list_id('dbmlsp Probe VersionsTarget')}')"
LIB_AT = f"{mock_list_id('dbmlsp Probe VersionsLibrary')}')"
LIST_READ_RULE = f"{LIST_AT}/items(1)/versions"
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

    for row_id in (USER, TARGET, TARGET_ITEMS, LIST, COLUMNS, PEOPLE_COLUMN, ITEM, PEOPLE_WRITE,
                   READ):
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


def test_the_version_fields_row_counts_each_of_the_four_and_names_the_greatest_label() -> None:
    rows, _, _ = _run()

    said = rows[FIELDS]["evidence"]
    assert said.startswith("VersionId on 3 of 3; VersionLabel on 3 of 3; Editor on 3 of 3; "
                           "Modified on 3 of 3. Per version: VersionId=1536, VersionLabel=\"3.0\"")
    assert ("The entry with the greatest VersionLabel, 3.0, carries: Editor, IsCurrentVersion, "
            "Modified, ProbeChoice" in said)


def test_an_oldest_first_answer_still_names_the_greatest_label() -> None:
    rows, _, _ = _run(versionsAscending=True)

    said = rows[FIELDS]["evidence"]
    assert "Per version: VersionId=512, VersionLabel=\"1.0\"" in said
    assert "The entry with the greatest VersionLabel, 3.0, carries: " in said


def test_labels_that_do_not_order_name_no_entry_the_greatest() -> None:
    rows, _, _ = _run(labelsUnparsed=True)

    said = rows[FIELDS]["evidence"]
    assert rows[FIELDS]["outcome"] == "OBSERVED"
    assert ("Not every VersionLabel is major.minor, so no entry is named the greatest; the entries "
            "together carry: Editor, IsCurrentVersion, Modified, ProbeChoice") in said


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
    rows, sent, output = _run(rules=[{"contains": f"{LIST_AT}/items(1)", "verb": "MERGE",
                                      "bodyContains": "ProbePeopleId", "status": 400,
                                      "text": "Invalid data for ada@example.com"}])

    # The resend's 2xx is not reported as the values written; the read-back decides that.
    assert "the set was sent again without it and is read back before it counts" in output
    assert "were written without it" not in output

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
              if r["verb"] == "MERGE" and f"{LIST_AT}/items(1)" in r["path"]]
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


def test_an_account_read_back_with_no_id_voids_everything_and_writes_nothing() -> None:
    rows, sent, _ = _run(rules=[{"contains": "web/currentuser", "status": 200,
                                 "text": '{"Id": 0}'}])

    assert rows[USER]["outcome"] == "FAIL"
    assert voided(rows) == _deps(USER)
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_an_unauthorised_account_read_leaves_everything_open_and_writes_nothing() -> None:
    rows, sent, _ = _run(rules=[{"contains": "web/currentuser", "status": 403, "text": "denied"}])

    assert rows[USER]["outcome"] == "NOT ESTABLISHED"
    assert "the account read answered HTTP 403" in rows[USER]["evidence"]
    assert voided(rows) == set()
    assert all(rows[row_id]["state"] == "open" for row_id in _deps(USER))
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_a_target_item_without_an_id_voids_what_follows_and_recycles_the_target() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{TARGET_AT}/items", "status": 400,
                                 "text": "no"}])

    # The list itself stood; what failed is the two items the lookup is written to.
    assert rows[TARGET]["outcome"] == "PASS"
    assert rows[TARGET_ITEMS]["outcome"] == "FAIL"
    assert "Seeded differs: read 0, declared 2" in rows[TARGET_ITEMS]["evidence"]
    assert "dbmlsp versions target A: HTTP 400" in rows[TARGET_ITEMS]["evidence"]
    assert voided(rows) == _deps(TARGET_ITEMS)
    assert _recycled(sent) == [RECYCLED[0], RECYCLED[2]]


def test_a_refused_item_write_fails_the_item_and_voids_the_versions_rows() -> None:
    rows, _, _ = _run(rules=[{"contains": f"{LIST_AT}/items(1)", "verb": "MERGE", "status": 400,
                              "text": "The property does not exist."}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 1, declared 3" in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_first_set_answered_2xx_that_did_not_land_fails_the_item_before_the_second() -> None:
    # The rule answers 204 and never reaches the mock's store, so set A is never stored.
    rows, sent, _ = _run(rules=[{"contains": f"{LIST_AT}/items(1)", "verb": "MERGE",
                                 "bodyContains": '"ProbeChoice":"Q1"', "status": 204, "text": ""}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 1, declared 3" in rows[ITEM]["evidence"]
    assert "set A: HTTP 204, but ProbeChoice reads back (absent)" in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)
    merges = [r for r in sent if r["verb"] == "MERGE" and f"{LIST_AT}/items(1)" in r["path"]]
    assert len(merges) == 1


def test_a_first_set_whose_read_back_went_unanswered_is_not_built_on() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{LIST_AT}/items(1)?$select=Id,ProbeChoice",
                                 "nth": 1, "status": 429, "text": "busy"}])

    # An unanswered read-back is no answer about the item, so it and its dependents are left open.
    assert rows[ITEM]["outcome"] == "NOT ESTABLISHED"
    assert "was throttled (HTTP 429)" in rows[ITEM]["evidence"]
    assert voided(rows) == set()
    assert all(rows[row_id]["state"] == "open" for row_id in _deps(ITEM))
    merges = [r for r in sent if r["verb"] == "MERGE" and f"{LIST_AT}/items(1)" in r["path"]]
    assert len(merges) == 1


@pytest.mark.parametrize(("status", "text", "said"), [
    (201, "{}", "the create: HTTP 201 carried no numeric Id"),
    (500, "Denied for ada@example.com", "the create: HTTP 500: Denied for <account>"),
])
def test_an_item_create_that_answered_no_id_sends_no_set(status: int, text: str,
                                                         said: str) -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{LIST_AT}/items", "verb": "POST",
                                 "status": status, "text": text}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert said in rows[ITEM]["evidence"]
    assert "ada@example.com" not in json.dumps(rows)
    assert voided(rows) == _deps(ITEM)
    assert not [r for r in sent if r["verb"] == "MERGE" and f"{LIST_AT}/items(" in r["path"]]


def test_a_list_whose_versioning_does_not_stick_voids_everything_after_it() -> None:
    rows, _, _ = _run(listMerge={"EnableVersioning": False})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "EnableVersioning differs: read false, declared true" in rows[LIST]["evidence"]
    assert rows[LIBRARY]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIST) | _deps(LIBRARY)


def test_a_foreign_list_holding_the_title_is_never_written_to() -> None:
    foreign = {"Id": LEFTOVER_ID, "BaseTemplate": 100, "Description": "somebody else's",
               "fields": {}, "items": []}
    rows, sent, _ = _run(lists={"dbmlsp Probe Versions": foreign})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "refusing to modify it" in rows[LIST]["evidence"]
    assert not [r for r in sent if ("Probe Versions')" in r["path"] or LEFTOVER_ID in r["path"])
                and r["verb"] != "GET"]
    assert _recycled(sent) == [RECYCLED[0], RECYCLED[2]]


@pytest.mark.parametrize("gates", [("CONFIRMED", "ALLOW_WRITES"),
                                   ("CONFIRMED", "ALLOW_WRITES", "CLEANUP")])
def test_a_list_already_holding_the_title_is_never_recycled_even_with_cleanup(
        gates: tuple[str, ...]) -> None:
    leftover = {"Id": LEFTOVER_ID, "BaseTemplate": 100, "Description": OWNED, "fields": {},
                "items": []}
    rows, sent, _ = _run(gates, lists={"dbmlsp Probe Versions": leftover})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "with this probe's description; refusing to modify it" in rows[LIST]["evidence"]
    assert voided(rows) == _deps(LIST)
    assert not [r for r in sent if LEFTOVER_ID in r["path"]]


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
        "before the upload 2 version(s) (2.0=1024, 1.0=512), after it 3 (3.0=1536, 2.0=1024, "
        '1.0=512); new: 3.0=1536; ProbeLibChoice read "Q1" after the upload; after the second '
        'edit, in label order: 1.0=(absent), 2.0="Q1", 3.0="Q1", 4.0="Q2"')
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
    assert "new: none;" in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_ADDS]["evidence"].endswith('1.0=(absent), 2.0="Q1", 3.0="Q2"')
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["state"] == "settled"
    assert rows[LIB_FIELDS]["evidence"] == (
        "no version is the upload's alone (UPLOAD ADDED NO VERSION)")


def test_an_upload_that_changes_the_value_is_still_found_by_the_reads_around_it() -> None:
    rows, _, _ = _run(uploadSetsValues={"ProbeLibChoice": "Q2"})

    assert rows[LIB_UPLOAD]["outcome"] == "PASS"
    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED A VERSION"
    assert 'new: 3.0=1536; ProbeLibChoice read "Q2" after the upload' in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_FIELDS]["outcome"] == "OBSERVED"
    assert 'ProbeLibChoice="Q2"; VersionId=1536' in rows[LIB_FIELDS]["evidence"]
    assert voided(rows) == set()


def test_labels_that_do_not_order_still_find_the_upload_by_its_entry() -> None:
    rows, _, _ = _run(labelsUnparsed=True)

    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED A VERSION"
    assert "new: v3=1536;" in rows[LIB_ADDS]["evidence"]
    assert "after the second edit, in the order answered: v4=" in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_FIELDS]["evidence"].startswith("v3 carries: ")


# The file's versions are read before the upload, after it, and after the second edit.
LIB_VERSIONS = f"{LIB_AT}/items(1)/versions"


def test_an_earlier_version_gone_after_the_upload_is_not_compared() -> None:
    renumbered = json.dumps({"value": [
        {"VersionId": 1536, "VersionLabel": "3.0"}, {"VersionId": 1025, "VersionLabel": "2.0"},
        {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, _ = _run(rules=[{"contains": LIB_VERSIONS, "nth": 2, "status": 200,
                              "text": renumbered}])

    assert rows[LIB_ADDS]["outcome"] == "NOT COMPARABLE"
    assert "new: 3.0=1536, 2.0=1025; gone: 2.0=1024;" in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"


def test_an_entry_with_no_versionid_around_the_upload_is_not_compared() -> None:
    rows, _, output = _run(rules=[{"contains": LIB_VERSIONS, "nth": 1, "status": 200,
                                   "text": '{"value": [{"VersionLabel": "1.0"}]}'}])

    assert rows[LIB_ADDS]["outcome"] == "NOT COMPARABLE"
    assert rows[LIB_ADDS]["evidence"].startswith(
        "the versions read before the upload answered an entry with no VersionId; after the "
        "second edit, in label order: ")
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert ended_with_report(output)


@pytest.mark.parametrize(("nth", "when", "status", "text", "said"), [
    (1, "before", 429, "busy for ada@example.com", "was not answered"),
    (2, "after", 429, "busy for ada@example.com", "was not answered"),
    (1, "before", 200, '{"d": "x"}', "answered HTTP 200 that carried no value array"),
    (2, "after", 200, '{"d": "x"}', "answered HTTP 200 that carried no value array"),
], ids=["before-throttled", "after-throttled", "before-no-array", "after-no-array"])
def test_an_unanswered_read_around_the_upload_leaves_both_rows_open(
        nth: int, when: str, status: int, text: str, said: str) -> None:
    rows, _, output = _run(rules=[{"contains": LIB_VERSIONS, "nth": nth, "status": status,
                                   "text": text}])

    assert rows[LIB_READ]["outcome"] == "PASS"
    for row_id in (LIB_ADDS, LIB_FIELDS):
        assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert f"the versions read {when} the upload {said}" in rows[row_id]["evidence"]
    assert "ada@example.com" not in json.dumps(rows)
    assert ended_with_report(output)


def test_an_upload_that_adds_two_entries_is_named_so_and_names_no_version() -> None:
    four = json.dumps({"value": [
        {"VersionId": 2048, "VersionLabel": "4.0"}, {"VersionId": 1536, "VersionLabel": "3.0"},
        {"VersionId": 1024, "VersionLabel": "2.0"}, {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, output = _run(rules=[{"contains": LIB_VERSIONS, "nth": 2, "status": 200,
                                   "text": four}])

    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED MORE THAN ONE VERSION"
    assert "new: 4.0=2048, 3.0=1536;" in rows[LIB_ADDS]["evidence"]
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["evidence"] == (
        "no version is the upload's alone (UPLOAD ADDED MORE THAN ONE VERSION)")
    assert ended_with_report(output)


def test_a_read_around_the_upload_with_a_continuation_link_is_not_compared() -> None:
    paged = json.dumps({"value": [{"VersionId": 512, "VersionLabel": "1.0"}],
                        "odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/x"})
    rows, _, _ = _run(rules=[{"contains": LIB_VERSIONS, "nth": 1, "status": 200, "text": paged}])

    for row_id in (LIB_ADDS, LIB_FIELDS):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "open"
    assert rows[LIB_ADDS]["evidence"].startswith(
        "the versions read before the upload: the answer carried a continuation link ([TENANT]")


def test_a_read_after_the_upload_without_the_choice_fails_the_fixture_not_the_value() -> None:
    rows, _, _ = _run(uploadDropsValues=["ProbeLibChoice"])

    assert rows[LIB_UPLOAD]["outcome"] == "FAIL"
    assert "ProbeLibChoice is absent from the payload" in rows[LIB_UPLOAD]["evidence"]
    assert voided(rows) == _deps(LIB_UPLOAD)
    assert rows[LIB_ADDS]["state"] == "void"


@pytest.mark.parametrize(("rule", "quoted"), [
    pytest.param({"contains": "getbyinternalnameortitle('ProbeFlag')", "status": 400,
                  "text": "Invalid data for ada@example.com"},
                 'ProbeFlag.Read differs: read "HTTP 400: Invalid data for <account>"',
                 id="column-read"),
    pytest.param({"contains": f"{LIST_AT}/items(1)", "verb": "MERGE", "status": 400,
                  "text": "Invalid data for ada@example.com"},
                 "set A: HTTP 400: Invalid data for <account>", id="item-merge"),
    pytest.param({"contains": "/fields", "verb": "POST", "bodyContains": "ProbeFlag", "status": 500,
                  "text": "Refused for i:0#.f|membership|ada@example.com"},
                 "create ProbeFlag: HTTP 500 Refused for i:0#.f|membership|<account>",
                 id="column-create"),
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
    rows, _, _ = _run(rules=[{"contains": f"{LIB_AT}/items(1)/versions", "status": 400,
                              "text": "no"}])

    assert rows[LIB_READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIB_READ) == {LIB_ADDS, LIB_FIELDS}
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"


@pytest.mark.parametrize(("rule", "fixture", "said"), [
    pytest.param({"contains": f"{LIB_AT}/fields", "verb": "POST", "status": 500,
                  "text": "no"}, "field.version.fixture-library-column",
                 'Read differs: read "HTTP 400', id="column"),
    pytest.param({"contains": f"{LIB_AT}/RootFolder", "status": 400, "text": "no"},
                 LIB_FOLDER, 'RootRead differs: read "HTTP 400', id="root-folder"),
    pytest.param({"contains": "/Files/add", "verb": "POST", "status": 500, "text": "no"},
                 "field.version.fixture-library-file", 'Added differs: read "HTTP 500"', id="file"),
    pytest.param({"contains": f"{LIB_AT}/items(1)", "verb": "MERGE", "bodyContains": "Q1",
                  "status": 500, "text": "no"}, "field.version.fixture-library-edit-first",
                 'Written differs: read "HTTP 500"', id="first-edit"),
    pytest.param({"contains": "/$value", "verb": "GET", "status": 500, "text": "no"},
                 LIB_UPLOAD, 'Content differs: read "HTTP 500"', id="content-read"),
    pytest.param({"contains": f"{LIB_AT}/items(1)", "verb": "MERGE", "bodyContains": "Q2",
                  "status": 500, "text": "no"}, "field.version.fixture-library-edit-second",
                 'Written differs: read "HTTP 500"', id="second-edit"),
])
def test_a_failed_library_fixture_voids_what_rests_on_it_and_the_list_case_stands(
        rule: dict[str, Any], fixture: str, said: str) -> None:
    rows, sent, output = _run(rules=[rule])

    assert rows[fixture]["outcome"] == "FAIL"
    assert said in rows[fixture]["evidence"]
    assert voided(rows) == _deps(fixture)
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"
    assert _recycled(sent) == RECYCLED
    assert ended_with_report(output)


NEXT = {"odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"}


def test_a_list_versions_read_with_a_continuation_link_leaves_the_observations_open() -> None:
    rows, _, output = _run(versionsNext=NEXT, versionsNextFor=f"{LIST_AT}/items(1)")

    assert rows[READ]["outcome"] == "PASS"
    for row_id in (*PAYLOAD, FIELDS, ORDER):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert "which this probe does not follow" in rows[row_id]["evidence"]
    assert rows[LIB_ADDS]["outcome"] == "UPLOAD ADDED A VERSION"
    assert ended_with_report(output)


def test_a_library_versions_read_with_a_continuation_link_leaves_its_rows_open() -> None:
    rows, _, output = _run(versionsNext=NEXT, versionsNextFor=f"{LIB_AT}/items(1)")

    for row_id in (LIB_ADDS, LIB_FIELDS):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "open"
    assert rows["field.version.payload-choice"]["outcome"] == "OBSERVED"
    assert ended_with_report(output)


def test_every_request_after_the_claim_goes_by_the_list_id() -> None:
    _, sent, _ = _run()

    titled = [r["path"] for r in sent if "getbytitle" in r["path"]]
    assert titled
    assert all("?$select=Id,Description" in path or "?$select=Id,BaseTemplate" in path
               for path in titled), titled


def test_a_set_a_people_value_that_was_never_stored_fails_only_the_people_write() -> None:
    rows, _, _ = _run(mergeDrops={"1": ["ProbePeopleId"]})

    assert rows[ITEM]["outcome"] == "PASS"
    assert rows[PEOPLE_WRITE]["outcome"] == "FAIL"
    assert 'Missed differs: read "set A: ProbePeopleId reads back (absent)"' in (
        rows[PEOPLE_WRITE]["evidence"])
    assert voided(rows) == {"field.version.payload-people"}


@pytest.mark.parametrize("name", ["ProbeDate", "ProbeStamp"])
def test_a_set_b_date_left_at_set_a_value_fails_the_item(name: str) -> None:
    rows, _, _ = _run(mergeDrops={"2": [name]})

    assert rows[ITEM]["outcome"] == "FAIL"
    assert f"set B: HTTP 204, but {name} reads back " in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_target_seed_that_does_not_read_back_its_title_fails_the_target() -> None:
    rows, _, _ = _run(rules=[{"contains": f"{TARGET_AT}/items(1)?$select=Id,Title", "status": 200,
                              "text": json.dumps({"Id": 1, "Title": "another title"})}])

    assert rows[TARGET]["outcome"] == "PASS"
    assert rows[TARGET_ITEMS]["outcome"] == "FAIL"
    assert "Seeded differs: read 1, declared 2" in rows[TARGET_ITEMS]["evidence"]
    assert voided(rows) == _deps(TARGET_ITEMS)


def test_a_list_versions_read_answered_2xx_with_no_value_array_is_left_open() -> None:
    rows, _, output = _run(rules=[{"contains": LIST_READ_RULE, "status": 200,
                                   "text": '{"d": "x"}'}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    for row_id in (READ, *PAYLOAD, FIELDS, ORDER):
        assert rows[row_id]["state"] == "open", rows[row_id]
    assert "HTTP 200 carried no value array" in rows[FIELDS]["evidence"]
    assert ended_with_report(output)


@pytest.mark.parametrize(("name", "sent", "took"), [("ProbeDate", 0, 1), ("ProbeStamp", 1, 0)])
def test_a_date_column_that_did_not_take_its_display_format_voids_the_list_rows(
        name: str, sent: int, took: int) -> None:
    rows, _, _ = _run(fieldsTake={name: {"DisplayFormat": took}})

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert f"{name}.DisplayFormat differs: read {took}, declared {sent}" in (
        rows[COLUMNS]["evidence"])
    assert voided(rows) == _deps(COLUMNS)


def test_the_columns_fixture_reads_back_each_date_column_display_format() -> None:
    rows, _, _ = _run()

    assert "ProbeDate.DisplayFormat=0" in rows[COLUMNS]["evidence"]
    assert "ProbeStamp.DisplayFormat=1" in rows[COLUMNS]["evidence"]


def test_a_versionid_repeated_after_the_upload_is_not_compared_as_a_set() -> None:
    repeated = json.dumps({"value": [
        {"VersionId": 1024, "VersionLabel": "2.0"}, {"VersionId": 1024, "VersionLabel": "2.0"},
        {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, _ = _run(rules=[{"contains": LIB_VERSIONS, "nth": 2, "status": 200,
                              "text": repeated}])

    assert rows[LIB_ADDS]["outcome"] == "NOT COMPARABLE"
    assert ("the versions read after the upload answered VersionId 1024 more than once"
            in rows[LIB_ADDS]["evidence"])
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"


def test_two_entries_at_the_greatest_label_leave_no_entry_named() -> None:
    tied = json.dumps({"value": [
        {"VersionId": 1536, "VersionLabel": "3.0", "A": 1},
        {"VersionId": 1537, "VersionLabel": "3.0", "B": 1},
        {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": 200, "text": tied}])

    evidence = rows[FIELDS]["evidence"]
    assert ("2 entries carry the greatest VersionLabel, 3.0, so no entry is named the greatest"
            in evidence)
    assert "The entry with the greatest VersionLabel" not in evidence


@pytest.mark.parametrize(("entries", "why"), [
    pytest.param([(1536, "3.0"), (1537, "3.0"), (512, "1.0")],
                 "more than one entry carries VersionLabel 3.0", id="same-label"),
    pytest.param([(1536, "3.0"), (1537, "03.0"), (512, "1.0")],
                 "more than one entry carries VersionLabel 3.0", id="same-pair-spelled-apart"),
    pytest.param([(512, "1.0"), (512, "2.0"), (1536, "3.0")],
                 "VersionId 512 answered more than once", id="same-versionid"),
])
def test_a_tie_in_label_or_versionid_leaves_the_order_not_comparable(
        entries: list[tuple[int, str]], why: str) -> None:
    body = json.dumps({"value": [{"VersionId": v, "VersionLabel": label} for v, label in entries]})
    rows, _, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": 200, "text": body}])

    assert rows[ORDER]["outcome"] == "NOT COMPARABLE", rows[ORDER]
    assert rows[ORDER]["state"] == "settled"
    assert f"{why}, so the order among them is not measured" in rows[ORDER]["evidence"]


def test_a_greatest_label_spelled_two_ways_names_no_entry() -> None:
    tied = json.dumps({"value": [
        {"VersionId": 1536, "VersionLabel": "3.0", "A": 1},
        {"VersionId": 1537, "VersionLabel": "03.0", "B": 1},
        {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, _ = _run(rules=[{"contains": LIST_READ_RULE, "status": 200, "text": tied}])

    evidence = rows[FIELDS]["evidence"]
    assert "2 entries carry the greatest VersionLabel" in evidence
    assert "The entry with the greatest VersionLabel" not in evidence


def test_an_unpinned_run_titles_all_three_lists_with_one_token_of_its_own() -> None:
    rows, sent, _ = run_probe(VERSIONS_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), {}, pin=False)

    titles = [json.loads(r["body"])["Title"] for r in sent
              if r["path"] == "web/lists" and r["verb"] == "POST"]
    tokens = {title.rsplit(" ", 1)[1] for title in titles}
    assert [title.rsplit(" ", 1)[0] for title in titles] == [
        "dbmlsp Probe VersionsTarget", "dbmlsp Probe Versions", "dbmlsp Probe VersionsLibrary"]
    assert len(tokens) == 1
    assert rows[LIST]["outcome"] == "PASS"


def test_the_target_list_is_not_passed_before_its_items_read_back() -> None:
    _, _, output = _run()

    # The claim's PASS names only the list; the items' PASS follows their read-backs.
    claimed = output.index(f"{TARGET}: PASS")
    seeded = output.index(f"{TARGET_ITEMS}: PASS")
    assert claimed < seeded
    assert output.index("seed dbmlsp versions target B") < seeded


def test_an_item_create_whose_title_does_not_read_back_is_not_counted() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{LIST_AT}/items(1)?$select=Id,Title", "status": 200,
                                 "text": '{"Id": 1, "Title": "another item"}'}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 0, declared 3" in rows[ITEM]["evidence"]
    assert 'the create: HTTP 201, but Title reads back \\"another item\\"' in rows[ITEM]["evidence"]
    assert not [r for r in sent if r["verb"] == "MERGE" and f"{LIST_AT}/items(1)" in r["path"]]
    assert voided(rows) == _deps(ITEM)


def test_a_site_path_with_an_apostrophe_is_doubled_inside_every_path_literal() -> None:
    rows, sent, _ = _run(siteRoot="/sites/O'Brien")

    for row_id in LIB_FIXTURES:
        assert rows[row_id]["outcome"] == "PASS", (row_id, rows[row_id])
    literal = [r["path"] for r in sent if "ServerRelativeUrl('" in r["path"]]
    assert literal
    assert all("/sites/O''Brien/" in path for path in literal), literal


def test_two_target_seeds_answered_one_id_fail_the_target_items() -> None:
    # The second seed's create answers the first one's Id, and overwrites it.
    rows, _, _ = _run(itemIds=[1, 1], sameIdReplaces=True)

    assert rows[TARGET_ITEMS]["outcome"] == "FAIL"
    assert "Distinct differs: read false, declared true" in rows[TARGET_ITEMS]["evidence"]
    assert voided(rows) == _deps(TARGET_ITEMS)


def test_a_list_create_answering_another_list_id_is_refused() -> None:
    target = mock_list_id("dbmlsp Probe VersionsTarget")
    rows, sent, output = _run(listIds={"dbmlsp Probe Versions": target})

    assert rows[TARGET]["outcome"] == "PASS"
    assert rows[LIST]["outcome"] == "FAIL"
    assert "the Id of another list this run created" in rows[LIST]["evidence"]
    assert voided(rows) == _deps(LIST)
    assert "recycle it by hand" in output
    assert _recycled(sent).count(f"web/lists(guid'{target}')/recycle") == 1


def test_a_multichoice_stored_as_one_joined_value_is_not_the_two_sent() -> None:
    # Joined with the delimiter a string comparison used, one stored value read as the two sent.
    rows, _, _ = _run(mergeTakes={"2": {"ProbeMulti": ["Q1|Q2"]}})

    assert rows[ITEM]["outcome"] == "FAIL"
    assert 'ProbeMulti reads back [\\"Q1|Q2\\"]' in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_person_id_stored_as_text_is_not_this_account() -> None:
    rows, _, _ = _run(mergeTakes={"1": {"ProbePeopleId": ["7"]}, "2": {"ProbePeopleId": ["7"]}})

    assert rows[PEOPLE_WRITE]["outcome"] == "FAIL"
    assert 'ProbePeopleId reads back [\\"7\\"]' in rows[PEOPLE_WRITE]["evidence"]


def test_a_version_whose_label_turns_from_null_to_absent_is_not_kept() -> None:
    before = json.dumps({"value": [{"VersionId": 512, "VersionLabel": None}]})
    after = json.dumps({"value": [{"VersionId": 512},
                                  {"VersionId": 1024, "VersionLabel": "2.0"}]})
    # The first rule answers the read before the upload; the second counts what the first let by.
    rows, _, _ = _run(rules=[
        {"contains": LIB_VERSIONS, "nth": 1, "status": 200, "text": before},
        {"contains": LIB_VERSIONS, "nth": 1, "status": 200, "text": after}])

    assert rows[LIB_ADDS]["outcome"] == "NOT COMPARABLE", rows[LIB_ADDS]
    assert "gone: null=512" in rows[LIB_ADDS]["evidence"]


@pytest.mark.parametrize("status", [429, 503, 403])
def test_a_list_create_that_goes_unanswered_is_left_open(status: int) -> None:
    rows, _, output = _run(rules=[{"contains": "web/lists", "verb": "POST", "nth": 1,
                                   "status": status, "text": "busy"}])

    assert rows[TARGET]["outcome"] == "NOT ESTABLISHED"
    assert "so a list 'dbmlsp Probe VersionsTarget' may now exist" in rows[TARGET]["evidence"]
    assert all(rows[row_id]["state"] == "open" for row_id in _deps(TARGET))
    assert "'dbmlsp Probe VersionsTarget' never answered a list Id" in output


def test_a_throttled_seed_leaves_the_target_items_open() -> None:
    rows, _, _ = _run(rules=[{"contains": f"{TARGET_AT}/items", "verb": "POST", "nth": 2,
                              "status": 429, "text": "busy"}])

    assert rows[TARGET_ITEMS]["outcome"] == "NOT ESTABLISHED"
    assert "was throttled (HTTP 429)" in rows[TARGET_ITEMS]["evidence"]
    assert voided(rows) == set()


def test_an_unavailable_content_read_leaves_the_upload_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "/$value", "verb": "GET", "status": 503, "text": "busy"}])

    assert rows[LIB_UPLOAD]["outcome"] == "NOT ESTABLISHED"
    assert all(rows[row_id]["state"] == "open" for row_id in (LIB_READ, LIB_ADDS, LIB_FIELDS))


def test_a_column_read_back_with_no_json_leaves_the_columns_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "getbyinternalnameortitle('ProbeFlag')", "status": 200,
                              "text": "not json"}])

    assert rows[COLUMNS]["outcome"] == "NOT ESTABLISHED"
    assert "the read answered HTTP 200 with no JSON" in rows[COLUMNS]["evidence"]


def test_a_versions_read_with_a_malformed_entry_passes_nothing() -> None:
    rows, _, output = _run(rules=[{"contains": LIST_READ_RULE, "status": 200,
                                   "text": '{"value": [null, {"VersionId": 512}]}'}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    assert "entry 1 of its value array as null" in rows[READ]["evidence"]
    assert all(rows[row_id]["state"] == "open" for row_id in (*PAYLOAD, FIELDS, ORDER))
    assert ended_with_report(output)


def test_an_upload_content_read_that_throws_leaves_the_upload_open() -> None:
    rows, _, output = _run(rules=[{"contains": "/$value", "verb": "GET", "reject": True}])

    assert rows[LIB_UPLOAD]["outcome"] == "NOT ESTABLISHED"
    assert "the read never answered (Failed to fetch)" in rows[LIB_UPLOAD]["evidence"]
    assert ended_with_report(output)


def test_a_list_create_answered_2xx_with_no_json_is_left_open() -> None:
    rows, _, output = _run(rules=[{"contains": "web/lists", "verb": "POST", "nth": 1,
                                   "status": 201, "text": "created"}])

    assert rows[TARGET]["outcome"] == "NOT ESTABLISHED"
    assert "answered HTTP 201 with no JSON object" in rows[TARGET]["evidence"]
    assert "'dbmlsp Probe VersionsTarget' never answered a list Id" in output


@pytest.mark.parametrize(("status", "text"), [
    (200, "Signed in as Ada Probe"), (403, "Ada Probe may not read this"),
    (500, "Ada Probe could not be read"),
], ids=["no-json", "unauthorised", "refused"])
def test_an_account_read_that_fails_quotes_nothing_of_its_body(status: int, text: str) -> None:
    # The display name is not known yet, so nothing could mask it; only the status is said.
    rows, _, output = _run(rules=[{"contains": "web/currentuser", "status": status, "text": text}])

    assert f"the account read answered HTTP {status}" in rows[USER]["evidence"]
    assert "Ada Probe" not in output.split("__SENT__")[0]


def test_a_refused_versions_read_around_the_upload_is_settled_and_named() -> None:
    rows, _, _ = _run(rules=[{"contains": LIB_VERSIONS, "nth": 1, "status": 500,
                              "text": "Unexpected."}])

    assert rows[LIB_ADDS]["outcome"] == "REFUSED"
    assert rows[LIB_ADDS]["state"] == "settled"
    assert "the versions read before the upload was refused: HTTP 500: Unexpected." in (
        rows[LIB_ADDS]["evidence"])
    assert rows[LIB_FIELDS]["outcome"] == "NOT IDENTIFIED"
    assert rows[LIB_FIELDS]["state"] == "settled"


def test_a_refused_column_create_beside_a_throttled_read_back_still_fails_the_columns() -> None:
    rows, _, _ = _run(rules=[
        {"contains": "/fields", "verb": "POST", "bodyContains": "ProbeFlag", "status": 500,
         "text": "Refused."},
        {"contains": "getbyinternalnameortitle('ProbeNumber')", "status": 429, "text": "busy"}])

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert voided(rows) == _deps(COLUMNS)


def test_a_refused_people_write_resent_without_it_is_not_the_items_refusal() -> None:
    # The people refusal is the people write's own answer, so a later throttle leaves the item open.
    rows, _, _ = _run(rules=[
        {"contains": f"{LIST_AT}/items(1)", "verb": "MERGE", "bodyContains": "ProbePeopleId",
         "status": 400, "text": "Invalid data"},
        {"contains": f"{LIST_AT}/items(1)?$select=Id,ProbeChoice", "nth": 2, "status": 429,
         "text": "busy"}])

    assert rows[ITEM]["outcome"] == "NOT ESTABLISHED"
    assert voided(rows) == set()


def test_a_refused_versions_read_voids_the_people_row_its_fixture_left_open() -> None:
    rows, _, _ = _run(rules=[
        {"contains": "createfieldasxml", "status": 429, "text": "busy"},
        {"contains": LIST_READ_RULE, "status": 500, "text": "Refused."}])

    assert rows[PEOPLE_COLUMN]["state"] == "open"
    assert rows[READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(READ)
