# test/test_deploy_lists_forms_runtime.py
"""Execute the Lists forms step against a mock of a list's forms.

The shared read partial and the step are rendered on their own, like the
folder defaults step, so each branch (create, settled, update, retire, every
refusal) runs under Node. The mock answers the routes the designer itself
calls; each test names the check id whose behaviour the mock encodes. Node is
required; the module skips without it.
"""

import json
import textwrap
from collections.abc import Mapping, Sequence

import pytest
from _json_view import Json

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.templating import script_env
from dbml_sharepoint.testing.node import NODE, run_node

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_LIST = "APP_Intake"
_LIST_ID = "1b2c3d4e-0000-4000-8000-00000000000a"
_ROOT = "/sites/test/Lists/APP_Intake"
_THANKS = "Your response has been submitted!"
_NEW_ID = "9f9f9f9f-0000-4000-8000-000000000001"
_OLD_ID = "5a5a5a5a-0000-4000-8000-000000000002"
_OTHER_ID = "7c7c7c7c-0000-4000-8000-000000000003"

_FIELDS = [
    {"Id": "aaaaaaaa-0000-4000-8000-000000000001", "InternalName": "Title", "Required": False},
    {"Id": "aaaaaaaa-0000-4000-8000-000000000002", "InternalName": "Details", "Required": True},
    {"Id": "aaaaaaaa-0000-4000-8000-000000000003", "InternalName": "Due", "Required": False,
     "DisplayFormat": 0},
    {"Id": "aaaaaaaa-0000-4000-8000-000000000004", "InternalName": "Attachments",
     "Required": False},
]

_HARNESS = textwrap.dedent(r"""
    const calls = [];
    const changes = [];
    const log = (level, msg) => console.log(`[${level}] ${msg}`);
    const apiUrl = (suffix) => `https://example.sharepoint.com/sites/test/_api/${suffix}`;
    const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
    const getDigest = async () => 'digest';
    const logChange = (change) => { changes.push(change); };
    const forms = STATE.forms.map((f) => ({ ...f }));
    const deadViews = new Set(STATE.deadViews || []);
    globalThis.fetch = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      url = String(url);
      const body = opts.body === undefined ? null : opts.body;
      calls.push({ method, url, headers: opts.headers || {}, body });
      const reply = (status, body) => {
        const text = typeof body === 'string' ? body : JSON.stringify(body);
        return { ok: status < 400, status, url, headers: { get: () => null },
          json: async () => JSON.parse(text), text: async () => text };
      };
      const alias = decodeURIComponent((/[?&]@a1=([^&]*)/.exec(url) || [])[1] || '');
      if (url.includes('(@a1)') && alias !== `'${STATE.root.replace(/'/g, "''")}'`) {
        return reply(404, { error: 'wrong @a1' });
      }
      if (url.includes('web/currentuser')) return reply(200, { d: { Title: 'Deploy Operator' } });
      if (url.includes('/fields?')) return reply(200, { d: { results: STATE.fields } });
      if (url.includes('/GetListForms')) {
        if (STATE.refuseRead) return reply(500, '{}');
        return reply(200, { d: { GetListForms: { results: forms } } });
      }
      if (url.includes('/CreateListForm')) {
        const refused = { error: { message: { value: 'create refused' } } };
        if (STATE.refuseCreate) return reply(500, refused);
        const p = JSON.parse(opts.body).parameters;
        forms.push({ Id: STATE.newId, SchemaJSON: p.SchemaJSON });
        return reply(200, { d: { CreateListForm: { Id: STATE.newId } } });
      }
      if (url.includes('/UpdateListForm')) {
        const p = JSON.parse(opts.body).parameters;
        const held = forms.find((f) => f.Id === p.Id);
        if (!held) return reply(404, '{}');
        if (!STATE.ignoreUpdate) held.SchemaJSON = p.SchemaJSON;
        return reply(200, { d: { UpdateListForm: { Id: p.Id } } });
      }
      if (url.includes('GetListUsingPath(DecodedUrl=@a1)/Views(@a2)')) {
        const id = decodeURIComponent(/[?&]@a2=([^&]*)/.exec(url)[1]).replace(/'/g, '');
        if ((opts.headers || {})['X-HTTP-Method'] !== 'DELETE') return reply(400, '{}');
        if ((STATE.refuseDelete || []).includes(id)) return reply(403, '{}');
        const at = forms.findIndex((f) => f.Id === id);
        if (at >= 0) forms.splice(at, 1);
        return reply(200, '');
      }
      const view = /Views\('([^']*)'\)/.exec(url);
      if (view) {
        const present = forms.some((f) => f.Id === view[1]) && !deadViews.has(view[1]);
        return present ? reply(200, { d: { Id: view[1] } }) : reply(STATE.absentStatus, '{}');
      }
      if (url.includes('getbytitle(')) {
        const root = { ServerRelativeUrl: STATE.root };
        return reply(200, { d: { Id: STATE.listId, RootFolder: root } });
      }
      return reply(500, { error: 'unmocked' });
    };
    const summary = { errors: [] };
    const owned = [];
    const ownedListIdentity = async (title, id) => {
      owned.push([title, id]);
      if (STATE.notOwned) throw new Error('the list is not ours');
      return { Id: STATE.listId };
    };
""")


def _render_phase() -> str:
    number = phase_number("lists_forms")
    return script_env().get_template("deploy/_lists_forms.js.j2").render(phase={
        "number": number, "name": "Lists forms",
        "group_number": number.split(".")[0], "group_name": "PRESENTATION",
        "first_in_group": False,
    })


def _run(state: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> Json:
    env = script_env()
    script = (
        f"const STATE = {json.dumps(state)};\n"
        f"const SCHEMA = {json.dumps({'lists_forms': rows})};\n"
        + _HARNESS
        + env.get_template("_http.js.j2").render()
        + env.get_template("_http_write.js.j2").render()
        + env.get_template("deploy/_shape_probes.js.j2").render()
        + env.get_template("_lists_forms_read.js.j2").render()
        + "(async () => {\n" + _render_phase() + "\n})().then(() => console.log("
        "'__RESULT__' + JSON.stringify({ summary, changes, forms, calls, owned, "
        "posts: calls.filter((c) => c.method === 'POST') })));\n"
    )
    output = run_node(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None)
    assert line is not None, output
    result = Json.loads(line.removeprefix("__RESULT__"))
    assert result.is_object, result
    return result


def _state(stored: Sequence[Mapping[str, object]] = (), **overrides: object) -> dict[str, object]:
    return {
        "root": _ROOT, "listId": _LIST_ID, "newId": _NEW_ID, "fields": _FIELDS,
        "forms": [{"Id": f["Id"], "SchemaJSON": json.dumps(f["schema"])} for f in stored],
        "absentStatus": 400, **overrides,
    }


def _question(column: str, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "column": column, "label": column, "help": "", "required": column == "Details",
        "display_format": 0 if column == "Due" else None,
    }
    return {**base, **over}


def _form(title: str = "Intake", **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": title, "previous_titles": [], "description": "Tell us what happened.",
        "questions": [_question("Title"), _question("Details", help="What happened"),
                      _question("Due", label="Due date")],
        "thank_you": "Your response has been submitted!", "one_response_per_person": False,
    }
    return {**base, **over}


def _entity(*forms: Mapping[str, object], retired: Sequence[str] = ()) -> dict[str, object]:
    return {"list": _LIST, "forms": list(forms) or [_form()], "retired": list(retired)}


def _schemas(result: Json) -> dict[str, Json]:
    return {
        str(f["Id"].value): Json.loads(str(f["SchemaJSON"].value)) for f in result["forms"]
    }


def _forms(result: Json) -> list[object]:
    forms = result["forms"].value
    assert isinstance(forms, list)
    return list(forms)


def _created(form: Mapping[str, object] | None = None) -> Json:
    """The forms state after a first deploy of `form` (or the default)."""
    result = _run(_state(), [_entity(form or _form())])
    assert result["summary"]["errors"] == [], result["summary"]
    return result


def _stored_state(result: Json, **overrides: object) -> dict[str, object]:
    return {**_state(), "forms": result["forms"].value, **overrides}


def _designer_schema(title: str = "Intake", **over: object) -> dict[str, object]:
    """A form saved in the designer: no single-response, disabled, schedule or description keys."""
    schema: dict[str, object] = {
        "header": {"title": title, "description": "Tell us what happened."},
        "elements": [
            {"ID": "aaaaaaaa-0000-4000-8000-000000000001", "displayName": "Title",
             "internalName": "Title", "required": False},
            {"ID": "aaaaaaaa-0000-4000-8000-000000000002", "displayName": "Details",
             "internalName": "Details", "required": True, "description": "What happened"},
            {"ID": "aaaaaaaa-0000-4000-8000-000000000003", "displayName": "Due date",
             "internalName": "Due", "required": False},
        ],
        "selectedFields": ["Title", "Details", "Due"],
        "templateId": "EMERALDGRADIENT", "theme": {"primaryColor": "#005E50"},
        "formId": "", "listId": "{" + _LIST_ID + "}", "createdBy": "Someone",
        "listBaseType": "0",
        "settings": {"requireSignIn": True, "formSuccessMessage": _THANKS},
    }
    return {**schema, **over}


def test_first_deploy_creates_the_form_and_reads_it_back() -> None:
    """`lists-forms.api.create`, `lists-forms.storage.shape`: the minimal schema creates it."""
    result = _run(_state(), [_entity()])
    assert result["summary"]["errors"] == []
    (post,) = result["posts"]
    assert "GetList(@a1)/CreateListForm" in str(post["url"].value)
    assert post["headers"]["X-RequestDigest"] == "digest"
    params = Json.loads(str(post["body"].value))["parameters"]
    assert params["__metadata"]["type"] == "SP.ListForm"
    schema = Json.loads(str(params["SchemaJSON"].value))
    assert schema["header"]["title"] == "Intake"
    assert [e["ID"].value for e in schema["elements"]] == [f["Id"] for f in _FIELDS[:3]]
    assert schema["selectedFields"] == ["Title", "Details", "Due"]
    assert schema["elements"][1]["description"] == "What happened"
    assert "description" not in schema["elements"][0]
    assert schema["settings"]["requireSignIn"].value is True
    assert schema["settings"]["isAnonymous"].value is False
    assert schema["listId"] == "{" + _LIST_ID + "}"
    assert schema["createdBy"] == "Deploy Operator"
    assert schema["templateId"] == "EMERALDGRADIENT"
    assert schema["settings"]["formSuccessMessage"] == "Your response has been submitted!"
    assert "ensureSingleResponsePerUser" not in schema["settings"]
    assert result["changes"] == [{
        "key": f"lists-form:{_LIST}:Intake", "kind": "lists-form", "target": _LIST,
        "oldValue": "", "newValue": _NEW_ID,
    }]
    assert result["owned"] == [[_LIST, _LIST_ID]]


def test_unchanged_redeploy_makes_zero_writes() -> None:
    """`lists-forms.durability.redeploy-v2`: a settled form gets no write."""
    first = _created()
    again = _run(_stored_state(first), [_entity()])
    assert again["summary"]["errors"] == []
    assert again["posts"] == [] and again["changes"] == [] and again["owned"] == []
    assert not any("currentuser" in str(c["url"].value) for c in again["calls"])


def test_designer_form_missing_default_keys_is_adopted_without_a_write() -> None:
    """A designer form lacking default keys reads them as their defaults."""
    stored = [{"Id": _OLD_ID, "schema": _designer_schema()}]
    result = _run(_state(stored), [_entity()])
    assert result["summary"]["errors"] == []
    assert result["posts"] == []


def test_field_id_case_and_braces_are_settled() -> None:
    """A stored `ID` in upper case with braces equals the field's `Id`."""
    schema = _designer_schema()
    elements = schema["elements"]
    assert isinstance(elements, list)
    for element in elements:
        assert isinstance(element, dict)
        element["ID"] = "{" + str(element["ID"]).upper() + "}"
    result = _run(_state([{"Id": _OLD_ID, "schema": schema}]), [_entity()])
    assert result["summary"]["errors"] == []
    assert result["posts"] == []


def test_stored_time_without_milliseconds_is_settled() -> None:
    """A stored `2026-11-01T22:00:00Z` equals the declared instant."""
    settings = {
        "requireSignIn": True, "formSuccessMessage": "Your response has been submitted!",
        "formScheduleResponseInfo": {"scheduleResponsesStartDate": "2026-11-01T22:00:00Z"},
    }
    stored = [{"Id": _OLD_ID, "schema": _designer_schema(settings=settings)}]
    result = _run(_state(stored), [_entity(_form(opens="2026-11-01T22:00:00.000Z"))])
    assert result["summary"]["errors"] == []
    assert result["posts"] == []


def test_previous_title_updates_in_place_with_the_same_id() -> None:
    """`lists-forms.api.update-title`, `lists-forms.durability.link-after-edit`: same id."""
    stored = [{"Id": _OLD_ID, "schema": _designer_schema("Old intake")}]
    result = _run(_state(stored), [_entity(_form(previous_titles=["Old intake"]))])
    assert result["summary"]["errors"] == []
    (post,) = result["posts"]
    assert "GetList(@a1)/UpdateListForm" in str(post["url"].value)
    params = Json.loads(str(post["body"].value))["parameters"]
    assert params["Id"] == _OLD_ID
    assert Json.loads(str(params["SchemaJSON"].value))["header"]["title"] == "Intake"
    assert [(c["oldValue"].value, c["newValue"].value) for c in result["changes"]] == [
        (_OLD_ID, _OLD_ID),
    ]


def test_description_and_help_change_updates() -> None:
    """`lists-forms.api.update-description`, `lists-forms.designer.element-description`."""
    first = _created()
    want = _form(description="New text.", questions=[
        _question("Title", help="Short name"), _question("Details"), _question("Due"),
    ])
    result = _run(_stored_state(first), [_entity(want)])
    assert result["summary"]["errors"] == []
    assert len(result["posts"]) == 1
    schema = _schemas(result)[_NEW_ID]
    assert schema["header"]["description"] == "New text."
    assert schema["elements"][0]["description"] == "Short name"
    assert "description" not in schema["elements"][1]


def test_reorder_and_drop_a_question() -> None:
    """`lists-forms.designer.move`, `lists-forms.designer.hide`: `selectedFields` follows."""
    first = _created()
    want = _form(questions=[_question("Due"), _question("Title")])
    result = _run(_stored_state(first), [_entity(want)])
    assert result["summary"]["errors"] == []
    schema = _schemas(result)[_NEW_ID]
    assert [e["internalName"].value for e in schema["elements"]] == ["Due", "Title"]
    assert schema["selectedFields"] == ["Due", "Title"]


def test_update_keeps_unmanaged_keys() -> None:
    """`lists-forms.storage.settings`, `lists-forms.designer.send-form`: kept byte for byte."""
    share = {"isCreateOnlyLink": True, "isActive": True, "trackLinkUsers": False,
             "hasExternalGuestInvitees": False, "expiration": ""}
    schema = _designer_schema(
        "Intake", formId="form-x", createdBy="Someone Else", templateId="OTHER",
        theme={"primaryColor": "#123456"},
        header={"title": "Intake", "description": "Old.", "logo": {"imageUrl": "/x.png"}},
        settings={"requireSignIn": True, "formSuccessMessage": "Your response has been submitted!",
                  "shareInfo": share, "isAnonymous": False, "formDisabled": True},
    )
    result = _run(_state([{"Id": _OLD_ID, "schema": schema}]), [_entity()])
    assert result["summary"]["errors"] == []
    assert len(result["posts"]) == 1
    after = _schemas(result)[_OLD_ID]
    for key in ("formId", "createdBy", "templateId", "theme", "listId"):
        assert after[key] == schema[key], key
    assert after["header"]["logo"] == {"imageUrl": "/x.png"}
    assert after["settings"]["shareInfo"] == share
    assert after["settings"]["isAnonymous"].value is False
    assert after["settings"]["formDisabled"].value is True


def test_designer_rules_are_removed_and_count_as_a_difference() -> None:
    """A stored element with `branchRules` is a difference; the update drops them."""
    schema = _designer_schema()
    elements = schema["elements"]
    assert isinstance(elements, list) and isinstance(elements[0], dict)
    elements[0]["branchRules"] = [{"id": "r1", "goto": "Due"}]
    result = _run(_state([{"Id": _OLD_ID, "schema": schema}]), [_entity()])
    assert result["summary"]["errors"] == []
    assert len(result["posts"]) == 1
    assert "branchRules" not in _schemas(result)[_OLD_ID]["elements"][0]


def test_operational_keys_enforced_only_when_declared() -> None:
    """`lists-forms.designer.accept-responses`, `lists-forms.designer.schedule-end`."""
    settings = {
        "requireSignIn": True, "formSuccessMessage": "Your response has been submitted!",
        "formDisabled": True, "formDisabledMessage": "Closed.",
        "formScheduleResponseInfo": {"scheduleResponsesEndDate": "2026-12-01T00:00:00.000Z"},
    }
    stored = [{"Id": _OLD_ID, "schema": _designer_schema(settings=settings)}]
    left = _run(_state(stored), [_entity()])
    assert left["posts"] == []
    declared = _form(accepting_responses=True, closed_message="Back soon.",
                     closes="2026-12-24T13:00:00.000Z")
    result = _run(_state(stored), [_entity(declared)])
    assert result["summary"]["errors"] == []
    after = _schemas(result)[_OLD_ID]["settings"]
    assert after["formDisabled"].value is False
    assert after["formDisabledMessage"] == "Back soon."
    assert after["formScheduleResponseInfo"] == {
        "scheduleResponsesEndDate": "2026-12-24T13:00:00.000Z",
    }


def test_one_response_per_person_is_set_and_removed() -> None:
    """`ensureSingleResponsePerUser` is written true when declared and deleted when not."""
    first = _run(_state(), [_entity(_form(one_response_per_person=True))])
    assert _schemas(first)[_NEW_ID]["settings"]["ensureSingleResponsePerUser"].value is True
    result = _run(_stored_state(first), [_entity()])
    assert len(result["posts"]) == 1
    assert "ensureSingleResponsePerUser" not in _schemas(result)[_NEW_ID]["settings"]


def test_drifted_column_fails_with_no_write() -> None:
    """`lists-forms.designer.required-designer`, `lists-forms.api.required-flag`."""
    fields = [{**f, "Required": True} if f["InternalName"] == "Title" else f for f in _FIELDS]
    result = _run(_state(fields=fields), [_entity()])
    (error,) = result["summary"]["errors"]
    assert error["list"] == _LIST and "Title" in str(error["error"].value)
    assert result["posts"] == []


def test_drifted_display_format_fails_with_no_write() -> None:
    """A dated question whose column shows another `DisplayFormat` fails the entity."""
    fields = [{**f, "DisplayFormat": 1} if f["InternalName"] == "Due" else f for f in _FIELDS]
    result = _run(_state(fields=fields), [_entity()])
    (error,) = result["summary"]["errors"]
    assert "Due" in str(error["error"].value) and result["posts"] == []


def test_missing_field_fails_with_no_write() -> None:
    """`lists-forms.durability.column-deleted`."""
    fields = [f for f in _FIELDS if f["InternalName"] != "Details"]
    result = _run(_state(fields=fields), [_entity()])
    (error,) = result["summary"]["errors"]
    assert "Details" in str(error["error"].value)
    assert result["posts"] == []


def test_attachments_is_checked_for_presence_only() -> None:
    """Attachments asks no `Required` or `DisplayFormat` of its field."""
    want = _form(questions=[_question("Title"), _question("Attachments", required=True)])
    assert _run(_state(), [_entity(want)])["summary"]["errors"] == []
    fields = [f for f in _FIELDS if f["InternalName"] != "Attachments"]
    result = _run(_state(fields=fields), [_entity(want)])
    assert "Attachments" in str(result["summary"]["errors"][0]["error"].value)


def test_undeclared_form_is_untouched() -> None:
    """`lists-forms.designer.two-forms`: a form whose title is not declared is left alone."""
    stored = [{"Id": _OTHER_ID, "schema": _designer_schema("Hand made", elements=[])}]
    result = _run(_state(stored), [_entity()])
    assert result["summary"]["errors"] == []
    assert [Json.loads(str(p["body"].value))["parameters"].get("Id").value
            for p in result["posts"]] == [None]
    assert _schemas(result)[_OTHER_ID]["header"]["title"] == "Hand made"


@pytest.mark.parametrize("absent", [400, 404])
def test_retired_form_is_deleted_and_400_or_404_reads_as_gone(absent: int) -> None:
    """`lists-forms.api.delete`, `lists-forms.storage.absent`."""
    first = _created()
    stored = [*_forms(first), {"Id": _OLD_ID, "SchemaJSON": json.dumps(_designer_schema("Old"))}]
    result = _run(_stored_state(first, forms=stored, absentStatus=absent),
                  [_entity(retired=["Old"])])
    assert result["summary"]["errors"] == []
    (post,) = result["posts"]
    assert "GetListUsingPath(DecodedUrl=@a1)/Views(@a2)" in str(post["url"].value)
    assert post["headers"]["X-HTTP-Method"] == "DELETE"
    assert f"@a2='{_OLD_ID}'" in str(post["url"].value)
    assert list(_schemas(result)) == [_NEW_ID]
    assert result["changes"] == [{
        "key": f"lists-form:{_LIST}:Old", "kind": "lists-form", "target": _LIST,
        "oldValue": _OLD_ID, "newValue": "deleted",
    }]


def test_a_retired_form_whose_view_still_answers_is_an_error() -> None:
    """A deleted form must read back absent from its view too."""
    first = _created()
    stored = [*_forms(first), {"Id": _OLD_ID, "SchemaJSON": json.dumps(_designer_schema("Old"))}]
    result = _run(_stored_state(first, forms=stored, absentStatus=200), [_entity(retired=["Old"])])
    (error,) = result["summary"]["errors"]
    assert "Old" in str(error["error"].value)


def test_retirement_waits_for_the_read_back() -> None:
    """A declared form whose update reads back different stops every delete."""
    stored = [
        {"Id": _OLD_ID, "schema": _designer_schema(header={"title": "Intake", "description": "x"})},
        {"Id": _OTHER_ID, "schema": _designer_schema("Old")},
    ]
    result = _run(_state(stored, ignoreUpdate=True), [_entity(retired=["Old"])])
    (error,) = result["summary"]["errors"]
    assert "description" in str(error["error"].value)
    assert not any("Views(@a2)" in str(p["url"].value) for p in result["posts"])
    assert _OTHER_ID in _schemas(result)


def test_duplicate_titles_fail_that_form_only() -> None:
    """Two forms with one declared title fail that form; the other declared form is created."""
    stored = [{"Id": _OLD_ID, "schema": _designer_schema()},
              {"Id": _OTHER_ID, "schema": _designer_schema()}]
    result = _run(_state(stored), [_entity(_form(), _form("Second"))])
    (error,) = result["summary"]["errors"]
    assert "Intake" in str(error["error"].value)
    (post,) = result["posts"]
    params = Json.loads(str(post["body"].value))["parameters"]
    assert Json.loads(str(params["SchemaJSON"].value))["header"]["title"] == "Second"


def test_current_and_previous_title_both_present_fail_that_form() -> None:
    """A form under the title and another under a previous title is ambiguous."""
    stored = [{"Id": _OLD_ID, "schema": _designer_schema()},
              {"Id": _OTHER_ID, "schema": _designer_schema("Old intake")}]
    result = _run(_state(stored), [_entity(_form(previous_titles=["Old intake"]))])
    assert len(result["summary"]["errors"]) == 1
    assert result["posts"] == []


def test_unparseable_schema_fails_the_entity_with_no_write() -> None:
    """`lists-forms.storage.shape`: an unreadable stored schema stops the entity."""
    state = _state()
    state["forms"] = [{"Id": _OTHER_ID, "SchemaJSON": "{not json"}]
    result = _run(state, [_entity()])
    (error,) = result["summary"]["errors"]
    assert _OTHER_ID in str(error["error"].value)
    assert result["posts"] == []


def test_settled_form_whose_view_does_not_answer_is_an_error() -> None:
    """A matched form must have a view that answers 200."""
    first = _created()
    result = _run(_stored_state(first, deadViews=[_NEW_ID]), [_entity()])
    (error,) = result["summary"]["errors"]
    assert "view" in str(error["error"].value)
    assert result["posts"] == []


def test_refused_create_records_one_error() -> None:
    """A refused create is one error for the entity, and nothing is logged as changed."""
    result = _run(_state(refuseCreate=True), [_entity()])
    (error,) = result["summary"]["errors"]
    assert "create refused" in str(error["error"].value)
    assert result["changes"] == []


def test_unreadable_forms_fail_the_entity() -> None:
    """A refused `GetListForms` is an error, never an empty list of forms."""
    result = _run(_state(refuseRead=True), [_entity()])
    assert len(result["summary"]["errors"]) == 1
    assert result["posts"] == []


def test_no_lists_forms_makes_no_requests() -> None:
    """An empty `SCHEMA.lists_forms` makes no request at all."""
    result = _run(_state(), [])
    assert result["calls"] == [] and result["summary"]["errors"] == []


def test_a_stored_form_that_does_not_require_sign_in_is_updated() -> None:
    """`requireSignIn` other than true is a difference; the update writes true, then settles."""
    settings = {"requireSignIn": False, "formSuccessMessage": _THANKS}
    stored = [{"Id": _OLD_ID, "schema": _designer_schema(settings=settings)}]
    result = _run(_state(stored), [_entity()])
    assert result["summary"]["errors"] == []
    (post,) = result["posts"]
    assert "UpdateListForm" in str(post["url"].value)
    assert _schemas(result)[_OLD_ID]["settings"]["requireSignIn"].value is True
    again = _run(_stored_state(result), [_entity()])
    assert again["summary"]["errors"] == [] and again["posts"] == []


def test_a_refused_delete_still_reads_back_the_sent_ones() -> None:
    """Every sent delete is read back; the error names only the refused one."""
    first = _created()
    stored = [*_forms(first),
              {"Id": _OLD_ID, "SchemaJSON": json.dumps(_designer_schema("Old"))},
              {"Id": _OTHER_ID, "SchemaJSON": json.dumps(_designer_schema("Older"))}]
    result = _run(_stored_state(first, forms=stored, refuseDelete=[_OTHER_ID]),
                  [_entity(retired=["Old", "Older"])])
    (error,) = result["summary"]["errors"]
    message = str(error["error"].value)
    assert "retired 'Older'" in message and "'Old'" not in message
    assert _OLD_ID not in _schemas(result) and _OTHER_ID in _schemas(result)
    assert any(c["method"] == "GET" and f"Views('{_OLD_ID}')" in str(c["url"].value)
               for c in result["calls"])
    assert [c["newValue"].value for c in result["changes"]] == ["deleted"]


def test_a_list_that_is_not_ours_fails_the_entity_once() -> None:
    """A failed ownership check is one error for the entity and stops every write."""
    result = _run(_state(notOwned=True), [_entity(_form(), _form("Second"))])
    (error,) = result["summary"]["errors"]
    assert str(error["error"].value) == "the list is not ours"
    assert result["posts"] == [] and len(result["owned"]) == 1


def test_a_root_folder_url_with_an_apostrophe_and_a_space() -> None:
    """The `@a1` literal doubles the apostrophe; create and read back still agree."""
    root = "/sites/test/Lists/Bob's list"
    result = _run(_state(root=root), [_entity()])
    assert result["summary"]["errors"] == []
    (post,) = result["posts"]
    assert "@a1='%2Fsites%2Ftest%2FLists%2FBob''s%20list'" in str(post["url"].value)
    again = _run(_stored_state(result, root=root), [_entity()])
    assert again["summary"]["errors"] == [] and again["posts"] == []
