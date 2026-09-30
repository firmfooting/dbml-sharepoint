"""Execute batch-item-create-probe.js under node against a mock web.

The mock unpacks each `$batch` ChangeSet, creates or refuses each item, and answers in a
nested batch and ChangeSet envelope with a status line, headers and a body per part. An
AddValidateUpdateItemUsingPath call answers a per-field list shaped like Learn's example.
Which parts it refuses is set per test; that the refusals match a site is the probe's
question, not this mock's claim.
"""

import json
import re
import textwrap
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import (
    catalogued_dependents,
    ended_with_report,
    recycled_last,
    run_probe,
    voided,
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "batch-item-create-probe.js"
LIST = "transport.batch.fixture-item-batch-list"
SINGLE = "transport.batch.control-single-item-create"
UNKNOWN = "transport.batch.control-single-item-unknown-property-refused"
PARTS = "transport.batch.changeset-item-creates-per-part"
FAILED = "transport.batch.changeset-item-create-failed-part"
VERBOSE = "transport.batch.changeset-item-create-untyped-verbose"
NOMETADATA = "transport.batch.changeset-item-create-untyped-nometadata"
OBSERVED = (PARTS, FAILED, VERBOSE, NOMETADATA)
COLUMNS = "transport.batch.fixture-item-batch-columns"
USER = "transport.batch.control-current-user"
ADDVALIDATE = "transport.batch.control-single-addvalidate-create"
AV_UNKNOWN = "transport.batch.control-single-addvalidate-unknown-field-refused"
AV_FAILED = "transport.batch.changeset-addvalidate-failed-part"
FOLDER = "transport.batch.changeset-addvalidate-folderpath-omitted"
CLAIMS = "transport.batch.changeset-addvalidate-person-claims"
ISO = "transport.batch.changeset-addvalidate-date-iso"
ADDVALIDATED = (FOLDER, CLAIMS, ISO)
OWNED = "dbml-sharepoint batch-item-create probe scratch list. Safe to delete."
CONTROL_CALL = "')/AddValidateUpdateItemUsingPath"
FIELD = {"FieldName": "Title", "ErrorMessage": None, "FieldValue": "x"}
NO_COLUMN = "Column 'dbmlspNoSuchColumn' does not exist."
ID_FIELD = {"FieldName": "Id", "FieldValue": "6", "HasException": False, "ErrorMessage": None}
CREATED_ID = "00000000-0000-4000-8000-000000000001"
LEFTOVER_ID = "00000000-0000-4000-8000-00000000abcd"

_MOCK = textwrap.dedent(r"""
    const CONFIG = __CONFIG__;
    // Node rereads TZ when it is assigned, so a test can run the probe in the zone it names.
    if (CONFIG.tz) process.env.TZ = CONFIG.tz;
    console.log('__LOCAL__' + new Date('2026-01-15T09:30:00').toISOString());
    globalThis.window = { _spPageContextInfo: {
      webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe' } };
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const answer = (status, payload) => {
      const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
      return { ok: status >= 200 && status < 300, status, headers: { get: () => null },
        text: async () => text, json: async () => JSON.parse(text) };
    };
    const LIST = "web/lists/getbytitle('dbmlsp Probe BatchItems')";
    const CREATED_ID = '00000000-0000-4000-8000-000000000001';
    const ME = { Id: 7, Email: 'ada@example.com', LoginName: 'i:0#.f|membership|ada@example.com',
      Title: 'Ada Probe' };
    let list = CONFIG.list || null;
    const items = [];
    const fields = {};
    let digests = 0;
    const refuse = (value) => ({ status: 400, reason: 'Bad Request',
      body: { error: { code: '-1, Microsoft.SharePoint.Client.InvalidClientQueryException',
        message: { lang: 'en-US', value } } } });
    // One item create answered as this mock chooses; `odata` is the content type it came in.
    const createItem = (sent, odata) => {
      const typed = sent.__metadata && sent.__metadata.type === list.ListItemEntityTypeFullName;
      const unknown = Object.keys(sent).find((key) => !['__metadata', 'Title'].includes(key));
      if (unknown && !CONFIG.acceptUnknown) {
        const type = list.ListItemEntityTypeFullName;
        return refuse(`The property '${unknown}' does not exist on type '${type}'.`);
      }
      const refuseUntyped = odata === 'verbose' ? CONFIG.refuseUntypedVerbose
        : CONFIG.refuseUntypedNometadata;
      if (!typed && refuseUntyped) return refuse('A type is required.');
      items.push({ Id: items.length + 1, Title: sent.Title });
      const row = { Id: items.length, Title: sent.Title };
      return { status: 201, reason: 'Created',
        body: odata === 'verbose'
          ? { d: { __metadata: { type: list.ListItemEntityTypeFullName }, ...row } } : row };
    };
    // One AddValidateUpdateItemUsingPath call answered as this mock chooses, per field.
    const addValidate = (sent) => {
      const values = Object.fromEntries(sent.formValues.map((v) => [v.FieldName, v.FieldValue]));
      const noFolder = !sent.listItemCreateInfo.FolderPath;
      if (noFolder && CONFIG.refuseNoFolderPath) {
        return refuse('The parameter listItemCreateInfo.FolderPath is required.');
      }
      const answers = sent.formValues.map((v) => ({ ErrorMessage: null, FieldName: v.FieldName,
        FieldValue: v.FieldValue, HasException: false, ItemId: 0 }));
      const bad = (name, message) => answers.filter((a) => a.FieldName === name)
        .forEach((a) => { a.HasException = true; a.ErrorMessage = message; });
      if (values.ProbeWho !== undefined && CONFIG.refuseClaims) {
        bad('ProbeWho', 'The user ada@example.com does not exist or is not unique.');
      }
      if (values.ProbeWhen !== undefined && CONFIG.refuseIsoDate) {
        bad('ProbeWhen', 'Invalid date/time value.');
      }
      const known = ['Title', ...Object.keys(fields)];
      for (const name of Object.keys(values).filter((n) => !known.includes(n))) {
        if (!CONFIG.acceptUnknown) bad(name, `Column '${name}' does not exist.`);
      }
      if (answers.some((a) => a.HasException)) {
        return { status: 200, reason: 'OK', body: { value: answers } };
      }
      items.push({ Id: items.length + 1, Title: values.Title,
        ProbeWhoId: values.ProbeWho === undefined ? null
          : 'storedWhoId' in CONFIG ? CONFIG.storedWhoId : ME.Id,
        ProbeWhen: values.ProbeWhen === undefined ? null
          : 'storedWhen' in CONFIG ? CONFIG.storedWhen : values.ProbeWhen });
      answers.push({ ErrorMessage: null, FieldName: 'Id', FieldValue: String(items.length),
        HasException: false, ItemId: 0 });
      return { status: 200, reason: 'OK', body: { value: answers } };
    };
    const batch = (raw) => {
      const parts = [];
      for (const chunk of raw.split(/--changeset_[a-z0-9]+/)) {
        const at = chunk.indexOf('POST ');
        if (at === -1) continue;
        const [head, body] = chunk.slice(at).split('\r\n\r\n');
        const odata = /odata=nometadata/.test(head) ? 'nometadata' : 'verbose';
        const rule = (CONFIG.partRules || []).find((r) => body.includes(r.bodyContains));
        const sent = rule ? null : JSON.parse(body.trim());
        const made = rule ? { status: rule.status, reason: rule.reason, body: rule.text }
          : /AddValidateUpdateItemUsingPath HTTP/.test(head) ? addValidate(sent)
            : createItem(sent, odata);
        // A part can be applied and still go unanswered, or be the only one answered.
        const dropped = (CONFIG.dropAnswers || []).some((s) => body.includes(s));
        const kept = !CONFIG.onlyAnswers || CONFIG.onlyAnswers.some((s) => body.includes(s));
        if (!dropped && kept) parts.push(made);
      }
      if (CONFIG.reverseAnswers) parts.reverse();
      return '--batchresponse_1\r\n'
        + 'Content-Type: multipart/mixed; boundary=changesetresponse_1\r\n\r\n'
        + parts.map((part) => '--changesetresponse_1\r\nContent-Type: application/http\r\n'
          + 'Content-Transfer-Encoding: binary\r\n\r\n'
          + `HTTP/1.1 ${part.status} ${part.reason}\r\n`
          + 'CONTENT-TYPE: application/json;odata=verbose;charset=utf-8\r\n\r\n'
          + `${typeof part.body === 'string' ? part.body : JSON.stringify(part.body)}\r\n`).join('')
        + '--changesetresponse_1--\r\n--batchresponse_1--\r\n';
    };
    globalThis.fetch = async (url, opts = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
      const raw = opts.body ? String(opts.body) : '';
      SENT.push({ verb, path, body: raw });
      for (const rule of CONFIG.rules || []) {
        if (!path.includes(rule.contains)) continue;
        if (rule.verb && rule.verb !== verb) continue;
        if (rule.bodyContains && !raw.includes(rule.bodyContains)) continue;
        if (rule.reject) throw new TypeError('Failed to fetch');
        return answer(rule.status, rule.text);
      }
      if (path === 'contextinfo') {
        digests += 1;
        if (CONFIG.digestsAllowed !== undefined && digests > CONFIG.digestsAllowed) {
          return answer(403, 'denied');
        }
        return answer(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (path === '$batch') {
        return answer(CONFIG.batchStatus || 200, CONFIG.batchText || batch(raw));
      }
      if (path.startsWith('web/currentuser')) return answer(200, ME);
      if (path === 'web/lists' && verb === 'POST') {
        const sent = JSON.parse(raw);
        list = { Id: CREATED_ID, BaseTemplate: sent.BaseTemplate, Description: sent.Description,
          ListItemEntityTypeFullName: 'SP.Data.dbmlspProbeBatchItemsListItem' };
        return answer(201, { Id: CREATED_ID });
      }
      // The list answers by its title, and by its Id while it stands.
      const byId = list === null ? null : `web/lists(guid'${list.Id}')`;
      const prefix = path.startsWith(LIST) ? LIST : byId && path.startsWith(byId) ? byId : null;
      if (prefix === null) {
        return /^web\/lists\(guid'/.test(path) ? answer(404, 'List does not exist.')
          : answer(404, 'no such endpoint in the mock: ' + path);
      }
      const rest = path.slice(prefix.length);
      if (list === null) return answer(404, 'List does not exist.');
      if (rest === '' || rest.startsWith('?')) return answer(200, list);
      if (rest === '/recycle') { list = null; return answer(200, {}); }
      if (rest === '/fields' && verb === 'POST') {
        const sent = JSON.parse(raw);
        // `whenTakes`: the DisplayFormat the date column stores in place of the one sent.
        fields[sent.Title] = { InternalName: sent.Title,
          TypeAsString: sent.FieldTypeKind === 20 ? 'User' : 'DateTime',
          ...(sent.DisplayFormat === undefined ? {} : {
            DisplayFormat: 'whenTakes' in CONFIG ? CONFIG.whenTakes : sent.DisplayFormat }) };
        return answer(201, { Title: sent.Title });
      }
      const field = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)/.exec(rest);
      if (field) {
        return fields[field[1]] ? answer(200, fields[field[1]])
          : answer(400, { 'odata.error': { message: { value: 'Column does not exist.' } } });
      }
      if (rest.startsWith('/RootFolder')) {
        return answer(200, { ServerRelativeUrl: '/sites/probe/Lists/dbmlsp Probe BatchItems' });
      }
      if (rest === '/AddValidateUpdateItemUsingPath' && verb === 'POST') {
        const made = addValidate(JSON.parse(raw));
        return answer(made.status, made.body);
      }
      if (rest === '/items' && verb === 'POST') {
        const made = createItem(JSON.parse(raw), 'verbose');
        const last = items[items.length - 1];
        return answer(made.status,
          made.status === 201 ? { Id: items.length, Title: last.Title } : made.body);
      }
      if (rest.startsWith('/items?')) return answer(200, { value: items });
      const one = /^\/items\((\d+)\)/.exec(rest);
      if (one) return answer(200, items[Number(one[1]) - 1] || {});
      return answer(404, 'no such endpoint in the mock: ' + path);
    };
""")


# The run's token is pinned so the mock can answer for the title; one test runs it unpinned.
PINNED = {"  const LIST = `dbmlsp Probe BatchItems ${RUN}`;":
          "  const LIST = 'dbmlsp Probe BatchItems';"}


def _run(gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(_MOCK, PROBE, gates, config, PINNED)


def _deps(fixture: str) -> set[str]:
    return catalogued_dependents(PROBE.name, fixture)


def _batches(sent: list[dict[str, str]]) -> list[str]:
    return [r["body"] for r in sent if r["path"] == "$batch"]


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_each_part_answer_is_recorded_with_what_landed() -> None:
    rows, sent, _ = _run()

    for row_id in (LIST, SINGLE, UNKNOWN, COLUMNS, USER, ADDVALIDATE, AV_UNKNOWN):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    parts = rows[PARTS]["evidence"]
    assert rows[PARTS]["outcome"] == "RECORDED"
    assert parts.startswith("outer HTTP 200, 3 part answer(s) matched by Title: part 1 (answer 1): "
                            "HTTP 201 Created; headers "
                            "CONTENT-TYPE: application/json;odata=verbose;charset=utf-8; body ")
    assert "part 2 (answer 2): HTTP 400 Bad Request" in parts
    assert "answer 2 names no Title and is part 2's as the one part left" in parts
    assert parts.endswith("landed A yes, B no, C yes")
    assert rows[FAILED]["outcome"] == "PART REFUSED"
    assert rows[FAILED]["evidence"].startswith("answer 2: HTTP 400 Bad Request")
    assert "The property 'dbmlspNoSuchColumn' does not exist" in rows[FAILED]["evidence"]
    assert "neighbours landed A yes, C yes" in rows[FAILED]["evidence"]
    assert rows[VERBOSE]["outcome"] == "PART ANSWERED 2XX"
    assert rows[NOMETADATA]["outcome"] == "PART ANSWERED 2XX"
    assert "landed yes" in rows[NOMETADATA]["evidence"]
    assert len(_batches(sent)) == 4
    assert recycled_last(sent)


def test_each_addvalidate_part_is_recorded_with_its_fields_and_what_reads_back() -> None:
    rows, _, _ = _run()

    for row_id in ADDVALIDATED:
        assert rows[row_id]["outcome"] == "WRITTEN", rows[row_id]
        assert rows[row_id]["state"] == "settled"
        assert rows[row_id]["evidence"].startswith("HTTP 200 OK; fields Title HasException=false")
    claims = rows[CLAIMS]["evidence"]
    assert 'ProbeWho HasException=false ErrorMessage=null FieldValue="[{\\"Key\\":' in claims
    assert "ProbeWhoId reads back 7, this account's Id: yes" in claims
    failed = rows[AV_FAILED]["evidence"]
    assert rows[AV_FAILED]["outcome"] == "FIELD REFUSED"
    assert "dbmlspNoSuchColumn HasException=true" in failed
    assert failed.endswith("landed no; neighbours landed dbmlsp addvalidate no folder yes, "
                           "dbmlsp addvalidate claims yes, dbmlsp addvalidate iso date yes")
    assert 'ProbeWhen reads back "2026-01-15T09:30:00Z"' in rows[ISO]["evidence"]
    everything = json.dumps(rows)
    assert "ada@example.com" not in everything
    assert "Ada Probe" not in everything


def test_the_addvalidate_parts_are_sent_as_the_history_write_sends_them() -> None:
    _, sent, _ = _run()

    control = next(r for r in sent if r["path"].endswith("')/AddValidateUpdateItemUsingPath"))
    assert ('"FolderPath":{"DecodedUrl":"https://example.sharepoint.com/sites/probe/Lists/'
            in control["body"])
    parts = _batches(sent)[3].split("--changeset_")[1:-1]
    assert len(parts) == 4
    assert all("/AddValidateUpdateItemUsingPath HTTP/1.1" in part for part in parts)
    assert all("getbytitle('dbmlsp%20Probe%20BatchItems')/AddValidateUpdateItemUsingPath" in part
               for part in parts)
    assert all("Content-Type: application/json;odata=nometadata" in part for part in parts)
    assert '"listItemCreateInfo":{"UnderlyingObjectType":0}' in parts[0]
    assert all('"FolderPath":{"DecodedUrl":' in part for part in parts[1:])
    assert '"FieldName":"dbmlspNoSuchColumn"' in parts[1]
    assert '"FieldValue":"[{\\"Key\\":\\"i:0#.f|membership|ada@example.com\\"}]"' in parts[2]
    assert '"FieldName":"ProbeWhen","FieldValue":"2026-01-15T09:30:00Z"' in parts[3]


@pytest.mark.parametrize("stored", [None, 9], ids=["empty", "another-person"])
def test_a_person_accepted_but_not_read_back_as_this_account_is_named_so(
        stored: int | None) -> None:
    rows, _, _ = _run(storedWhoId=stored)

    assert rows[CLAIMS]["outcome"] == "ACCEPTED, NOT STORED"
    assert rows[CLAIMS]["state"] == "settled"
    assert (f"ProbeWhoId reads back {json.dumps(stored)}, this account's Id: no "
            "(the account read back Id 7)") in rows[CLAIMS]["evidence"]
    assert rows[ISO]["outcome"] == "WRITTEN"
    assert voided(rows) == set()


@pytest.mark.parametrize(("stored", "instant"), [
    ("2026-01-15T19:30:00Z", "2026-01-15T19:30:00.000Z"),
    ("2026-01-15T09:30:00+01:00", "2026-01-15T08:30:00.000Z"),
    (None, "(not a zoned date and time)"),
    ("15/01/2026 09:30", "(not a zoned date and time)"),
])
def test_a_date_accepted_but_read_back_as_another_instant_is_named_so(
        stored: str | None, instant: str) -> None:
    rows, _, _ = _run(storedWhen=stored)

    assert rows[ISO]["outcome"] == "ACCEPTED, STORED DIFFERENTLY"
    assert rows[ISO]["state"] == "settled"
    assert (f"ProbeWhen reads back {json.dumps(stored)}; as a UTC instant {instant} against the "
            "sent 2026-01-15T09:30:00.000Z: different") in rows[ISO]["evidence"]
    assert rows[CLAIMS]["outcome"] == "WRITTEN"
    assert voided(rows) == set()


def test_a_date_read_back_with_an_offset_is_compared_as_an_instant() -> None:
    rows, _, _ = _run(storedWhen="2026-01-15T20:30:00+11:00")

    assert rows[ISO]["outcome"] == "WRITTEN"
    assert ("as a UTC instant 2026-01-15T09:30:00.000Z against the sent "
            "2026-01-15T09:30:00.000Z: same") in rows[ISO]["evidence"]


@pytest.mark.parametrize(("stored", "same"), [("2026-01-15", "same"), ("2026-01-16", "different")])
def test_a_date_read_back_without_its_time_is_compared_as_a_date(stored: str, same: str) -> None:
    rows, _, _ = _run(storedWhen=stored)

    assert rows[ISO]["outcome"] == "ACCEPTED, STORED DIFFERENTLY"
    assert (f'ProbeWhen reads back "{stored}", a date with no time; as a date against the sent '
            f"2026-01-15: {same}") in rows[ISO]["evidence"]


def test_a_date_and_time_without_a_zone_gets_the_same_head_in_every_zone() -> None:
    runs = [_run(storedWhen="2026-01-15T09:30:00", tz=tz) for tz in ("UTC", "Australia/Sydney")]

    local = {next(ln for ln in output.splitlines() if ln.startswith("__LOCAL__"))
             for _, _, output in runs}
    assert len(local) == 2, "the two runs did not read a zone-less time in different zones"
    for rows, _, _ in runs:
        assert rows[ISO]["outcome"] == "STORED WITHOUT A ZONE"
        assert ('ProbeWhen reads back "2026-01-15T09:30:00", a date and time with no zone; '
                "not compared") in rows[ISO]["evidence"]
    assert runs[0][0][ISO] == runs[1][0][ISO]


def test_an_answer_missing_from_a_batch_leaves_every_part_row_unmatched() -> None:
    rows, _, _ = _run(dropAnswers=["part B", "addvalidate part missing column"])

    for row_id in (PARTS, FAILED):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert rows[row_id]["evidence"].startswith(
            "3 part(s) sent, 2 answer(s); answer 1: HTTP 201")
        assert "part 2" not in rows[row_id]["evidence"]
        assert rows[row_id]["evidence"].endswith("landed A yes, B no, C yes")
    for row_id in (FOLDER, AV_FAILED, CLAIMS, ISO):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert rows[row_id]["evidence"].startswith(
            "4 part(s) sent, 3 answer(s); answer 1: HTTP 200")
        assert rows[row_id]["evidence"].endswith(
            "landed dbmlsp addvalidate no folder yes, dbmlsp addvalidate part missing column no, "
            "dbmlsp addvalidate claims yes, dbmlsp addvalidate iso date yes")
    assert rows[VERBOSE]["outcome"] == "PART ANSWERED 2XX"
    assert voided(rows) == set()


def test_a_batch_answering_only_its_failed_part_leaves_every_part_row_unmatched() -> None:
    rows, _, _ = _run(onlyAnswers=["part B", "addvalidate part missing column"])

    for row_id in (PARTS, FAILED):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["evidence"].startswith(
            "3 part(s) sent, 1 answer(s); answer 1: HTTP 400 Bad Request")
    for row_id in (FOLDER, AV_FAILED, CLAIMS, ISO):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert "4 part(s) sent, 1 answer(s); answer 1: HTTP 200 OK" in rows[row_id]["evidence"]
        refused = '"FieldName":"dbmlspNoSuchColumn","FieldValue":"x","HasException":true'
        assert refused in rows[row_id]["evidence"]


def test_item_create_answers_in_another_order_are_matched_by_their_titles() -> None:
    rows, _, output = _run(reverseAnswers=True)

    parts = rows[PARTS]["evidence"]
    assert rows[PARTS]["outcome"] == "RECORDED"
    assert "part 1 (answer 3): HTTP 201 Created" in parts
    assert "part 2 (answer 2): HTTP 400 Bad Request" in parts
    assert "part 3 (answer 1): HTTP 201 Created" in parts
    assert rows[FAILED]["outcome"] == "PART REFUSED"
    assert rows[FAILED]["evidence"].startswith("answer 2: HTTP 400 Bad Request")
    assert ended_with_report(output)


@pytest.mark.parametrize(("part", "said"), [
    pytest.param({"bodyContains": "part A", "status": 201, "reason": "Created", "text": "{}"},
                 "2 answers name no Title, so which part each answers is unknown",
                 id="two-untitled"),
    pytest.param({"bodyContains": "part A", "status": 201, "reason": "Created",
                  "text": '{"d": {"Title": "dbmlsp batch part C"}}'},
                 "answers 1 and 3 both name part 3", id="one-title-twice"),
    pytest.param({"bodyContains": "part A", "status": 201, "reason": "Created",
                  "text": '{"d": {"Title": "another item"}}'},
                 'answer 1 names Title "another item", which no part sent', id="unsent-title"),
])
def test_item_create_answers_that_cannot_be_paired_by_title_are_not_matched(
        part: dict[str, Any], said: str) -> None:
    rows, _, output = _run(partRules=[part])

    for row_id in (PARTS, FAILED):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert rows[row_id]["evidence"].startswith(said)
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_answers_naming_other_fields_than_their_parts_are_not_matched() -> None:
    rows, _, _ = _run(reverseAnswers=True)

    for row_id in (FOLDER, AV_FAILED, CLAIMS, ISO):
        assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert rows[row_id]["evidence"].startswith(
            'answer 1 names ["Title","ProbeWhen"] where part 1 sent ["Title"]')
    assert voided(rows) == set()


def test_a_failed_part_refused_on_another_field_is_not_called_field_refused() -> None:
    other = json.dumps({"value": [
        {"FieldName": "Title", "HasException": True, "ErrorMessage": "no", "FieldValue": "x"},
        {"FieldName": "dbmlspNoSuchColumn", "HasException": False, "ErrorMessage": None,
         "FieldValue": "x"}]})
    rows, _, _ = _run(partRules=[{"bodyContains": "addvalidate part missing column", "status": 200,
                                  "reason": "OK", "text": other}])

    assert rows[AV_FAILED]["outcome"] == "PART ANSWERED 2XX"


def test_a_throttled_single_create_keeps_what_an_earlier_fixture_voided() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/currentuser", "status": 403, "text": "denied"},
                             {"contains": f"{CREATED_ID}')/items", "verb": "POST", "status": 429,
                              "text": "busy"}])

    assert rows[SINGLE]["outcome"] == "NOT ESTABLISHED"
    assert voided(rows) == {CLAIMS}
    assert rows[ISO]["state"] == "open"


@pytest.mark.parametrize(("setting", "row_id", "said"), [
    ("refuseNoFolderPath", FOLDER, "the write was refused: HTTP 400 Bad Request"),
    ("refuseClaims", CLAIMS, "a field was refused: HTTP 200 OK"),
    ("refuseIsoDate", ISO, "a field was refused: HTTP 200 OK"),
])
def test_a_refused_addvalidate_write_is_not_established_and_the_probe_goes_on(
        setting: str, row_id: str, said: str) -> None:
    rows, sent, _ = run_probe(_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), {setting: True}, PINNED)

    assert rows[row_id]["outcome"] == "NOT ESTABLISHED"
    assert rows[row_id]["state"] == "open"
    assert rows[row_id]["evidence"].startswith(said)
    assert "landed no" in rows[row_id]["evidence"]
    assert all(rows[other]["outcome"] == "WRITTEN" for other in ADDVALIDATED if other != row_id)
    assert voided(rows) == set()
    assert "ada@example.com" not in json.dumps(rows)
    assert recycled_last(sent)


def test_an_addvalidate_control_that_is_refused_voids_every_addvalidate_row() -> None:
    rows, sent, _ = _run(rules=[{"contains": "')/AddValidateUpdateItemUsingPath", "status": 500,
                                 "text": "no"}])

    assert rows[ADDVALIDATE]["outcome"] == "FAIL"
    assert voided(rows) == _deps(ADDVALIDATE) == {AV_UNKNOWN, AV_FAILED, *ADDVALIDATED}
    assert rows[PARTS]["outcome"] == "RECORDED"
    assert len(_batches(sent)) == 3


def test_a_throttled_addvalidate_control_leaves_every_addvalidate_row_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "')/AddValidateUpdateItemUsingPath", "status": 429,
                              "text": "busy"}])

    assert rows[ADDVALIDATE]["outcome"] == "NOT ESTABLISHED"
    for row_id in (AV_UNKNOWN, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open"
        assert "a re-run can ask it" in rows[row_id]["evidence"]


def test_columns_that_do_not_read_back_void_the_claims_and_date_parts_only() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "bodyContains": "ProbeWho",
                                 "status": 500, "text": "This field type is not supported."}])

    assert rows[COLUMNS]["outcome"] == "FAIL"
    created = 'ProbeWho.Create="HTTP 500: This field type is not supported."'
    assert created in rows[COLUMNS]["evidence"]
    assert voided(rows) == _deps(COLUMNS) == {CLAIMS, ISO}
    assert rows[FOLDER]["outcome"] == "WRITTEN"
    assert len(_batches(sent)[3].split("--changeset_")[1:-1]) == 2


def test_an_unread_account_voids_only_the_claims_part() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/currentuser", "status": 403, "text": "denied"}])

    assert rows[USER]["outcome"] == "FAIL"
    assert voided(rows) == _deps(USER) == {CLAIMS}
    assert rows[ISO]["outcome"] == "WRITTEN"


def test_the_parts_carry_the_type_only_where_the_question_does() -> None:
    _, sent, _ = _run()

    three, untyped_verbose, untyped_nometadata, _ = _batches(sent)
    assert three.count('"__metadata":{"type":"SP.Data.dbmlspProbeBatchItemsListItem"}') == 3
    assert "__metadata" not in untyped_verbose
    assert "Content-Type: application/json;odata=verbose" in untyped_verbose
    assert "__metadata" not in untyped_nometadata
    assert "Content-Type: application/json;odata=nometadata" in untyped_nometadata
    assert "POST https://example.sharepoint.com/sites/probe/_api/web/lists/getbytitle(" in three


@pytest.mark.parametrize(("setting", "row_id"), [
    ("refuseUntypedVerbose", VERBOSE), ("refuseUntypedNometadata", NOMETADATA),
])
def test_a_refused_untyped_part_is_recorded_with_its_answer(setting: str, row_id: str) -> None:
    rows, _, _ = run_probe(_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), {setting: True},
                           PINNED)

    assert rows[row_id]["outcome"] == "PART REFUSED"
    assert "A type is required." in rows[row_id]["evidence"]
    assert "landed no" in rows[row_id]["evidence"]


@pytest.mark.parametrize(("status", "sent", "row_id"), [
    (429, "untyped verbose", VERBOSE), (503, "untyped verbose", VERBOSE),
    (429, "part B", FAILED), (429, "addvalidate part missing column", AV_FAILED),
])
def test_a_part_throttled_inside_the_batch_is_left_open(
        status: int, sent: str, row_id: str) -> None:
    rows, _, _ = _run(partRules=[{"bodyContains": sent, "status": status,
                                  "reason": "Too Many Requests", "text": "busy"}])

    assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
    assert rows[row_id]["state"] == "open", rows[row_id]
    assert f"HTTP {status} Too Many Requests" in rows[row_id]["evidence"]


@pytest.mark.parametrize(("status", "outcome"), [(400, "OUTER REQUEST REFUSED"),
                                                 (429, "NOT ESTABLISHED")])
def test_a_whole_batch_that_is_not_answered_part_by_part_is_named_so(
        status: int, outcome: str) -> None:
    rows, _, _ = _run(batchStatus=status, batchText="The request is not a batch.")

    for row_id in OBSERVED:
        assert rows[row_id]["outcome"] == outcome, rows[row_id]
        assert "The request is not a batch." in rows[row_id]["evidence"]
    for row_id in ADDVALIDATED:
        assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
        assert f"{outcome}: " in rows[row_id]["evidence"]
    assert rows[AV_FAILED]["outcome"] == outcome


def test_a_batch_that_never_answered_is_a_row_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "$batch", "reject": True}])

    assert rows[PARTS]["outcome"] == "NOT ESTABLISHED"
    assert "no response: Failed to fetch" in rows[PARTS]["evidence"]
    assert recycled_last(sent)


def test_a_2xx_batch_with_no_parts_is_named_so() -> None:
    rows, _, _ = _run(batchText="nothing here")

    assert rows[PARTS]["outcome"] == "NO PART STATUS"
    for row_id in (*OBSERVED, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open", rows[row_id]


def test_a_missing_column_the_site_accepts_voids_the_failed_part_row() -> None:
    rows, _, _ = _run(acceptUnknown=True)

    assert rows[UNKNOWN]["outcome"] == "FAIL"
    assert rows[AV_UNKNOWN]["outcome"] == "FAIL"
    assert _deps(UNKNOWN) == {FAILED}
    assert voided(rows) == _deps(UNKNOWN) | _deps(AV_UNKNOWN) == {FAILED, AV_FAILED}
    assert rows[PARTS]["outcome"] == "RECORDED"


def test_a_throttled_missing_column_control_leaves_the_failed_part_row_open() -> None:
    rows, _, _ = _run(rules=[{"contains": f"{CREATED_ID}')/items", "verb": "POST",
                              "bodyContains": "dbmlspNoSuchColumn", "status": 429, "text": "busy"}])

    assert rows[UNKNOWN]["outcome"] == "NOT ESTABLISHED"
    assert rows[FAILED]["state"] == "open"
    assert "a re-run can ask it" in rows[FAILED]["evidence"]
    assert rows[PARTS]["outcome"] == "RECORDED"


def test_a_throttled_single_create_leaves_every_batch_row_open() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{CREATED_ID}')/items", "verb": "POST", "status": 429,
                                 "text": "busy"}])

    assert rows[SINGLE]["outcome"] == "NOT ESTABLISHED"
    for row_id in (UNKNOWN, *OBSERVED, ADDVALIDATE, AV_UNKNOWN, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open"
    assert _batches(sent) == []


def test_a_single_create_that_does_not_land_voids_every_batch_row() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{CREATED_ID}')/items(1)", "status": 200,
                                 "text": "{}"}])

    assert rows[SINGLE]["outcome"] == "FAIL"
    assert voided(rows) == _deps(SINGLE)
    assert _batches(sent) == []


@pytest.mark.parametrize(("status", "said"), [(500, "HTTP 500: no"), (429, "the request ")])
def test_an_items_read_back_that_fails_leaves_every_row_it_informs_open(
        status: int, said: str) -> None:
    rows, _, _ = _run(rules=[{"contains": "items?$select=Id,Title", "status": status,
                              "text": "no"}])

    assert "landed A unknown" in rows[PARTS]["evidence"]
    assert f"the items read-back failed: {said}" in rows[PARTS]["evidence"]
    for row_id in (*OBSERVED, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open", rows[row_id]
    # The part's own answer still heads the row; only its state waits for a read of what landed.
    assert rows[VERBOSE]["outcome"] == "PART ANSWERED 2XX"


def test_a_single_create_whose_read_back_carried_no_json_leaves_the_batch_rows_open() -> None:
    rows, sent, _ = _run(rules=[{"contains": f"{CREATED_ID}')/items(1)", "status": 200,
                                 "text": "not json"}])

    assert rows[SINGLE]["outcome"] == "NOT ESTABLISHED"
    assert voided(rows) == set()
    assert _batches(sent) == []


def test_a_foreign_list_holding_the_title_is_never_written_to() -> None:
    rows, sent, _ = _run(list={"Id": LEFTOVER_ID, "BaseTemplate": 100,
                               "Description": "somebody else's"})

    assert rows[LIST]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIST)
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_with_cleanup_a_leftover_list_is_recycled_and_built_again() -> None:
    rows, sent, _ = _run(("CONFIRMED", "ALLOW_WRITES", "CLEANUP"),
                         list={"Id": LEFTOVER_ID, "BaseTemplate": 100, "Description": OWNED,
                               "ListItemEntityTypeFullName": "SP.Data.old"})

    assert rows[LIST]["outcome"] == "PASS"
    assert len([r for r in sent if r["path"].endswith("/recycle")]) == 2


@pytest.mark.parametrize(("rule", "row_id"), [
    ({"contains": "web/currentuser"}, USER),
    ({"contains": "')/AddValidateUpdateItemUsingPath"}, ADDVALIDATE),
    ({"contains": "/fields", "verb": "POST", "bodyContains": "ProbeWhen"}, COLUMNS),
])
def test_an_account_named_in_a_refusal_is_masked(rule: dict[str, str], row_id: str) -> None:
    rows, _, output = _run(rules=[{**rule, "status": 403,
                                   "text": "i:0#.f|membership|bob@example.org may not"}])

    assert "<account> may not" in rows[row_id]["evidence"]
    printed = [ln for ln in output.splitlines() if not ln.startswith(("__SENT__", "__ROWS__"))]
    assert "bob@example.org" not in json.dumps(rows) + "\n".join(printed)


def test_the_evidence_never_names_the_tenant() -> None:
    rows, _, _ = _run(partRules=[{"bodyContains": "part B", "status": 400, "reason": "Bad Request",
                                  "text": "Refused at https://example.sharepoint.com/sites/probe/_api"}])

    assert "[TENANT]/sites/probe/_api" in rows[FAILED]["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)


@pytest.mark.parametrize(("rule", "outcome", "said"), [
    pytest.param({"contains": "/RootFolder", "status": 400, "text": "no"}, "FAIL",
                 "the root folder read: HTTP 400: no", id="root-refused"),
    pytest.param({"contains": "/RootFolder", "status": 200, "text": '{"ServerRelativeUrl": null}'},
                 "FAIL", "the root folder read: HTTP 200 carried no ServerRelativeUrl",
                 id="root-without-url"),
    pytest.param({"contains": "/RootFolder", "status": 429, "text": "busy"}, "NOT ESTABLISHED",
                 "the root folder read: the request ", id="root-throttled"),
    pytest.param({"contains": CONTROL_CALL, "status": 200,
                  "text": json.dumps({"value": [{**FIELD, "HasException": True}, ID_FIELD]})},
                 "FAIL", "the call answered HTTP 200: ", id="field-exception"),
    pytest.param({"contains": CONTROL_CALL, "status": 200,
                  "text": json.dumps({"value": [{**FIELD, "HasException": False}]})},
                 "FAIL", "the call answered HTTP 200: ", id="no-id"),
    pytest.param({"contains": CONTROL_CALL, "status": 200, "text": '{"d": 1}'},
                 "FAIL", 'the call answered HTTP 200: {"d": 1}', id="no-field-list"),
    pytest.param({"contains": f"{CREATED_ID}')/items(6)", "status": 500, "text": "no"}, "FAIL",
                 "created Id 6; the read-back: HTTP 500: no", id="read-back-refused"),
    pytest.param({"contains": f"{CREATED_ID}')/items(6)", "status": 503, "text": "busy"},
                 "NOT ESTABLISHED", "created Id 6; the read-back: the request ",
                 id="read-back-throttled"),
    pytest.param({"contains": f"{CREATED_ID}')/items(6)", "status": 200, "text": "not json"},
                 "NOT ESTABLISHED", "created Id 6; the read-back answered HTTP 200 with no JSON",
                 id="read-back-no-json"),
    pytest.param({"contains": "/RootFolder", "status": 200, "text": "not json"},
                 "NOT ESTABLISHED", "the root folder read: HTTP 200 carried no ServerRelativeUrl",
                 id="root-no-json"),
    pytest.param({"contains": f"{CREATED_ID}')/items(6)", "status": 200,
                  "text": '{"Id": 6, "Title": "another title"}'},
                 "FAIL", 'created Id 6; it reads back Title "another title"', id="other-title"),
])
def test_an_addvalidate_control_that_does_not_hold_leaves_no_addvalidate_row_asked(
        rule: dict[str, Any], outcome: str, said: str) -> None:
    rows, sent, output = _run(rules=[rule])

    assert rows[ADDVALIDATE]["outcome"] == outcome
    assert rows[ADDVALIDATE]["evidence"].startswith(said)
    if outcome == "FAIL":
        assert voided(rows) == _deps(ADDVALIDATE)
    else:
        assert voided(rows) == set()
        for row_id in (AV_UNKNOWN, AV_FAILED, *ADDVALIDATED):
            assert rows[row_id]["state"] == "open"
            assert "a re-run can ask it" in rows[row_id]["evidence"]
    assert rows[PARTS]["outcome"] == "RECORDED"
    assert len(_batches(sent)) == 3
    assert recycled_last(sent)
    assert ended_with_report(output)


def test_a_missing_field_refused_by_status_passes_the_control() -> None:
    rows, _, output = _run(rules=[{"contains": CONTROL_CALL, "bodyContains": "dbmlspNoSuchColumn",
                                   "status": 400, "text": NO_COLUMN}])

    assert rows[ADDVALIDATE]["outcome"] == "PASS"
    assert rows[AV_UNKNOWN]["outcome"] == "PASS"
    assert rows[AV_UNKNOWN]["evidence"] == f"HTTP 400: {NO_COLUMN}"
    assert rows[AV_FAILED]["outcome"] == "FIELD REFUSED"
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_a_missing_field_control_answered_with_no_field_list_voids_the_failed_part() -> None:
    rows, _, output = _run(rules=[{"contains": CONTROL_CALL, "bodyContains": "dbmlspNoSuchColumn",
                                   "status": 200, "text": '{"d": 1}'}])

    assert rows[AV_UNKNOWN]["outcome"] == "FAIL"
    assert rows[AV_UNKNOWN]["evidence"] == 'HTTP 200: {"d": 1}'
    assert voided(rows) == _deps(AV_UNKNOWN) == {AV_FAILED}
    assert ended_with_report(output)


def test_a_failing_addvalidate_part_answered_400_is_part_refused() -> None:
    rows, _, output = _run(partRules=[{"bodyContains": "addvalidate part missing column",
                                       "status": 400, "reason": "Bad Request", "text": NO_COLUMN}])

    assert rows[AV_FAILED]["outcome"] == "PART REFUSED"
    assert rows[AV_FAILED]["state"] == "settled"
    assert rows[AV_FAILED]["evidence"].startswith(f"HTTP 400 Bad Request; body {NO_COLUMN}")
    assert rows[AV_FAILED]["evidence"].endswith(
        "neighbours landed dbmlsp addvalidate no folder yes, dbmlsp addvalidate claims yes, "
        "dbmlsp addvalidate iso date yes")
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_a_throttled_missing_field_control_leaves_the_failed_addvalidate_part_open() -> None:
    rows, _, output = _run(rules=[{"contains": CONTROL_CALL, "bodyContains": "dbmlspNoSuchColumn",
                                   "status": 429, "text": "busy"}])

    assert rows[AV_UNKNOWN]["outcome"] == "NOT ESTABLISHED"
    assert rows[AV_FAILED]["outcome"] == "NOT ESTABLISHED"
    assert rows[AV_FAILED]["state"] == "open"
    assert rows[AV_FAILED]["evidence"] == (
        "not asked: the missing-column control was not established; a re-run can ask it")
    for row_id in ADDVALIDATED:
        assert rows[row_id]["outcome"] == "WRITTEN", rows[row_id]
    assert voided(rows) == set()
    assert ended_with_report(output)


def _answers(*statuses: int) -> str:
    """A $batch answer carrying one bodyless part per status."""
    return "".join(f"--batchresponse_1\r\nContent-Type: application/http\r\n\r\n"
                   f"HTTP/1.1 {status} Created\r\n\r\n" for status in statuses
                   ) + "--batchresponse_1--\r\n"


@pytest.mark.parametrize(("title", "row_id"), [
    ("dbmlsp batch untyped verbose", VERBOSE), ("dbmlsp batch untyped nometadata", NOMETADATA),
])
def test_an_untyped_batch_answering_more_parts_than_it_sent_is_not_matched(
        title: str, row_id: str) -> None:
    rows, _, output = _run(rules=[{"contains": "$batch", "bodyContains": title, "status": 200,
                                   "text": _answers(201, 201)}])

    assert rows[row_id]["outcome"] == "ANSWERS NOT MATCHED"
    assert rows[row_id]["state"] == "open"
    assert rows[row_id]["evidence"].startswith(
        "1 part(s) sent, 2 answer(s); answer 1: HTTP 201 Created")
    assert rows[row_id]["evidence"].endswith("landed no")
    assert rows[PARTS]["outcome"] == "RECORDED"
    assert voided(rows) == set()
    assert ended_with_report(output)


@pytest.mark.parametrize(("part", "row_id", "said"), [
    pytest.param({"bodyContains": "addvalidate claims", "status": 503,
                  "reason": "Service Unavailable", "text": "busy"}, CLAIMS,
                 "the part was not answered; a re-run can ask it: HTTP 503 Service Unavailable; "
                 "body busy; landed no", id="not-answered"),
    pytest.param({"bodyContains": "addvalidate no folder", "status": 200, "reason": "OK",
                  "text": "{}"}, FOLDER,
                 "the part answered with no per-field list: HTTP 200 OK; body {}; landed no",
                 id="no-field-list"),
])
def test_an_addvalidate_part_answered_without_a_verdict_is_left_open(
        part: dict[str, Any], row_id: str, said: str) -> None:
    rows, _, output = _run(partRules=[part])

    assert rows[row_id]["outcome"] == "NOT ESTABLISHED"
    assert rows[row_id]["state"] == "open"
    assert rows[row_id]["evidence"].startswith(said)
    assert all(rows[other]["outcome"] == "WRITTEN" for other in ADDVALIDATED if other != row_id)
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_a_digest_lost_mid_run_is_caught_and_the_rest_left_open() -> None:
    rows, sent, output = _run(digestsAllowed=4)

    assert rows[SINGLE]["outcome"] == "PASS"
    assert "probe aborted: contextinfo failed: HTTP 403. The unasked rows stay open." in output
    for row_id in (*OBSERVED, ADDVALIDATE, AV_UNKNOWN, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open", rows[row_id]
    assert "recycle it by hand" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]
    assert ended_with_report(output)


def test_the_writes_after_the_claim_go_by_the_created_list_id() -> None:
    _, sent, _ = _run()

    after = [r for r in sent
             if r["verb"] != "GET" and r["path"] not in ("contextinfo", "web/lists")]
    titled = [r["path"] for r in after if "getbytitle" in r["path"]]
    assert titled == []
    assert all(r["path"] == "$batch" or f"guid'{CREATED_ID}')" in r["path"] for r in after), after


@pytest.mark.parametrize("answer", [
    {"status": 200, "text": json.dumps({"Id": LEFTOVER_ID, "Title": "dbmlsp Probe BatchItems"})},
    {"status": 429, "text": "busy"},
], ids=["rebound", "throttled"])
def test_a_title_that_no_longer_names_the_claimed_list_sends_no_batch(
        answer: dict[str, Any]) -> None:
    rows, sent, output = _run(rules=[{"contains": "BatchItems')?$select=Id,Title", **answer}])

    assert _batches(sent) == []
    for row_id in (*OBSERVED, AV_FAILED, *ADDVALIDATED):
        assert rows[row_id]["state"] == "open", rows[row_id]
        assert "not sent: the title read " in rows[row_id]["evidence"]
    assert ended_with_report(output)


def test_a_date_column_that_did_not_take_date_and_time_voids_the_iso_row() -> None:
    rows, _, _ = _run(whenTakes=0)

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert "ProbeWhen.DisplayFormat differs: read 0, declared 1" in rows[COLUMNS]["evidence"]
    assert rows[ISO]["state"] == "void"


def test_each_run_names_its_list_with_a_title_no_other_run_uses() -> None:
    titles = []
    for _ in range(2):
        _, sent, _ = run_probe(_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), {})
        [create] = [r for r in sent if r["path"] == "web/lists" and r["verb"] == "POST"]
        titles.append(json.loads(create["body"])["Title"])
    for title in titles:
        # The space stays, so the parts still send it as %20 (ruling D18 in the watch-flow plans).
        assert re.fullmatch(r"dbmlsp Probe BatchItems [a-z0-9]{6,}", title), title
    assert titles[0] != titles[1]
