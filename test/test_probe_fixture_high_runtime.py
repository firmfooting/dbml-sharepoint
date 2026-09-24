"""Execute the High-tier probes of #559 whose rows rested on an unread fixture.

Each probe runs against a mock SharePoint more than once: healthy, as the
control that shows it still measures, and once per fixture that does not hold,
which must void exactly the rows that rest on it and send none of their writes.
"""

import textwrap
from typing import Any

import pytest
from _node import NODE
from test_probe_fixture_runtime import _run_probe, _void_ids

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


# --------------------------------------------------------------------------
# Item 6: today-semantics reads both rules and the =TODAY() default back.
# --------------------------------------------------------------------------
#: A fresh scratch list. A stored rule reads back without brackets, as measured
#: on 2026-09-02, and refuses a value later than the save.
_TODAY_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    let listMade = false;
    const fields = new Map();
    const items = new Map();
    let nextItem = 1;
    const FIELD = /\\/fields\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)/;
    const ITEM = /\\/items\\((\\d+)\\)/;
    const refused = (status, value) => jsonResponse(status, { error: { message: { value } } });

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = raw ? JSON.parse(raw) : {};
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) return digestResponse();
      if (path.startsWith('web/regionalsettings/timezone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, DaylightBias: 0 } });
      }
      if (path === 'web/lists' && method === 'POST') {
        listMade = true;
        return jsonResponse(201, { d: { Id: 'list-1', Title: sent.Title } });
      }
      if (!listMade) return refused(404, 'List does not exist.');
      const named = FIELD.exec(path);
      if (named) {
        const held = fields.get(named[1]);
        if (!held) return refused(400, 'Column does not exist.');
        if (verb === 'MERGE') {
          if (!(CONFIG.dropRule || []).includes(named[1])) {
            held.ValidationFormula = sent.ValidationFormula.replace(/[[\\]]/g, '');
          }
          return jsonResponse(204, {});
        }
        if (CONFIG.ruleReadStatus) return jsonResponse(CONFIG.ruleReadStatus, { error: 'no' });
        return jsonResponse(200, { ValidationFormula: held.ValidationFormula });
      }
      if (path.endsWith('/fields')) {
        fields.set(sent.Title, { ValidationFormula: '' });
        return jsonResponse(201, { d: { Title: sent.Title } });
      }
      const item = ITEM.exec(path);
      if (item) return jsonResponse(200, items.get(Number(item[1])));
      if (path.endsWith('/items')) {
        const now = Date.now();
        for (const name of ['D', 'W']) {
          const ruled = fields.get(name).ValidationFormula && name in sent;
          if (ruled && Date.parse(sent[name]) > now) return refused(400, `${name} is after`);
        }
        const id = nextItem;
        nextItem += 1;
        const midnight = new Date();
        midnight.setHours(0, 0, 0, 0);
        items.set(id, { Id: id, Created: new Date(now).toISOString(),
          T: CONFIG.defaultFires ? midnight.toISOString() : null });
        return jsonResponse(201, { d: { Id: id } });
      }
      return jsonResponse(200, { ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' });
    };
""")

_TODAY = "today-semantics-probe.js"
_RULES = "formula.datetime.fixture-today-now-rules-stored"
_DEFAULT = "formula.datetime.today-function-default-value"
_SAVE_ROWS = {
    "formula.datetime.today-allows-two-days-ago",
    "formula.datetime.today-allows-yesterday",
    "formula.datetime.today-allows-site-midnight-today",
    "formula.datetime.today-allows-utc-midnight-today",
    "formula.datetime.today-rejects-tomorrow",
    "formula.datetime.now-function-minus-20h",
    "formula.datetime.now-function-minus-12h",
    "formula.datetime.now-function-minus-1h",
    "formula.datetime.now-function-plus-1h",
    "formula.datetime.now-function-plus-12h",
    "formula.datetime.now-function-plus-20h",
}
_TODAY_HEALTHY: dict[str, Any] = {"defaultFires": True}


def _saves(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "POST" and r["path"].endswith("/items")]


def test_today_semantics_measures_against_rules_it_read_back() -> None:
    rows, sent = _run_probe(_TODAY_MOCK, _TODAY_HEALTHY, _TODAY)

    assert rows[_RULES]["outcome"] == "PASS", rows[_RULES]
    assert rows[_DEFAULT]["outcome"] == "PASS", rows[_DEFAULT]
    assert rows["formula.datetime.today-allows-yesterday"]["outcome"] == "SAVED"
    assert rows["formula.datetime.today-rejects-tomorrow"]["outcome"] == "REFUSED"
    assert rows["formula.datetime.now-function-plus-1h"]["outcome"] == "REFUSED"
    assert not _void_ids(rows)
    assert len(_saves(sent)) == 1 + len(_SAVE_ROWS)


@pytest.mark.parametrize("dropped", ["D", "W"])
def test_today_semantics_voids_the_save_rows_when_a_rule_was_dropped(dropped: str) -> None:
    """A MERGE answered 204 for a rule never kept, and every save then read as allowed."""
    rows, sent = _run_probe(_TODAY_MOCK, {**_TODAY_HEALTHY, "dropRule": [dropped]}, _TODAY)

    assert rows[_RULES]["outcome"] == "FAIL", rows[_RULES]
    assert f"{dropped}.ValidationFormula differs" in rows[_RULES]["evidence"]
    assert _void_ids(rows) == _SAVE_ROWS
    assert all(_RULES in rows[row_id]["evidence"] for row_id in _SAVE_ROWS)
    assert len(_saves(sent)) == 1


def test_today_semantics_voids_the_save_rows_when_the_rules_do_not_read_back() -> None:
    rows, sent = _run_probe(_TODAY_MOCK, {**_TODAY_HEALTHY, "ruleReadStatus": 429}, _TODAY)

    assert rows[_RULES]["outcome"] == "FAIL", rows[_RULES]
    assert "the read was throttled (HTTP 429)" in rows[_RULES]["evidence"]
    assert _void_ids(rows) == _SAVE_ROWS
    assert len(_saves(sent)) == 1


def test_today_semantics_does_not_report_a_default_that_never_fired() -> None:
    """The row was a literal 'PASS' that printed T as null."""
    rows, _ = _run_probe(_TODAY_MOCK, {"defaultFires": False}, _TODAY)

    assert rows[_DEFAULT]["outcome"] == "NOT ESTABLISHED", rows[_DEFAULT]
    assert "T stored as null" in rows[_DEFAULT]["evidence"]
    assert rows[_RULES]["outcome"] == "PASS"


# --------------------------------------------------------------------------
# The document library probes (items 10 and 14) share one mock site.
# --------------------------------------------------------------------------
#: Lists, libraries, fields, items, files, folders and views. An item POST
#: naming a column the list lacks is refused, as a live site refuses it.
_LIBRARY_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const lists = new Map();
    const folders = new Set();
    let nextList = 1;
    const parse = (raw) => { try { return JSON.parse(raw); } catch { return null; } };
    const refusal = (status, value) =>
      jsonResponse(status, { 'odata.error': { message: { value } } });
    const newList = (title, template) => {
      const n = nextList;
      nextList += 1;
      const list = { Id: `list-${n}`, Title: title, BaseTemplate: template,
        root: `/sites/test/L${n}`, fields: new Map(), items: [], views: new Map(),
        nextItem: 1, EnableFolderCreation: true };
      folders.add(list.root);
      lists.set(title, list);
      return list;
    };
    for (const [title, shape] of Object.entries(CONFIG.existing || {})) {
      const list = newList(title, shape.template);
      for (const [view, props] of Object.entries(shape.views || {})) {
        list.views.set(view, { Title: view, ...props });
      }
    }
    const rowOf = (list, item) => {
      const row = { Id: item.Id, Title: item.Title || null, FileLeafRef: item.FileLeafRef || null };
      for (const name of list.fields.keys()) row[name] = item[name] ?? null;
      return row;
    };
    const addFile = (folder, name) => {
      const list = [...lists.values()].find((l) => folder.startsWith(l.root));
      if (!list || !folders.has(folder)) return refusal(404, 'File Not Found.');
      if ((CONFIG.failUpload || []).includes(name)) return refusal(400, 'The upload was refused.');
      if (!list.items.some((i) => i.FileLeafRef === name)) {
        list.items.push({ Id: list.nextItem, FileLeafRef: name, folder });
        list.nextItem += 1;
      }
      return jsonResponse(200, { Name: name, ServerRelativeUrl: `${folder}/${name}` });
    };
    const writeItem = (list, item, sent) => {
      const unknown = Object.keys(sent).filter((k) => k !== 'Title' && !list.fields.has(k));
      if (unknown.length) return refusal(400, `Column '${unknown[0]}' does not exist.`);
      if ((CONFIG.failMerge || []).includes(item.FileLeafRef)) return jsonResponse(500, {});
      if (!(CONFIG.dropMerge || []).includes(item.FileLeafRef)) Object.assign(item, sent);
      return jsonResponse(204, {});
    };
    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FOLDER = /^web\\/GetFolderByServerRelativeUrl\\('([^']+)'\\)(.*)$/;
    const NAMED = /^\\/(fields|views)\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)(.*)$/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = parse(raw) || {};
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) return digestResponse();
      if (path === 'web/lists' && method === 'POST') {
        const list = newList(sent.Title, sent.BaseTemplate);
        return jsonResponse(201, { Id: list.Id, Title: list.Title });
      }
      const inFolder = FOLDER.exec(path);
      if (inFolder) {
        const [, folder, rest] = inFolder;
        const file = /^\\/Files\\/add\\(url='([^']+)'/.exec(rest);
        if (file) return addFile(folder, file[1]);
        const sub = /^\\/folders\\/add\\(url='([^']+)'\\)/.exec(rest);
        if (!sub) return jsonResponse(200, { Exists: folders.has(folder) });
        if (CONFIG.folderStatus) return jsonResponse(CONFIG.folderStatus, {});
        folders.add(`${folder}/${sub[1]}`);
        return jsonResponse(200, { Name: sub[1], Exists: true });
      }
      const inList = LIST.exec(path);
      if (!inList) return refusal(404, `unmocked ${path}`);
      const list = lists.get(inList[1]);
      if (!list) return refusal(404, 'List does not exist.');
      const rest = inList[2];
      if (rest === '' || rest.startsWith('?')) {
        if (verb !== 'MERGE') {
          return jsonResponse(200, { Id: list.Id, Title: list.Title,
            BaseTemplate: list.BaseTemplate, EnableFolderCreation: list.EnableFolderCreation });
        }
        if ('EnableFolderCreation' in sent) list.EnableFolderCreation = sent.EnableFolderCreation;
        return jsonResponse(204, {});
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: list.root });
      }
      if (rest === '/fields/createfieldasxml') {
        const name = /Name="([^"]+)"/.exec(sent.parameters.SchemaXml)[1];
        list.fields.set(name, { InternalName: name, TypeAsString: 'Choice' });
        return jsonResponse(201, { InternalName: name });
      }
      if (rest === '/fields' && method === 'POST') {
        list.fields.set(sent.Title, { InternalName: sent.Title, TypeAsString: 'Text',
          DefaultFormula: sent.DefaultFormula || null, Sealed: false });
        return jsonResponse(201, { InternalName: sent.Title });
      }
      const named = NAMED.exec(rest);
      if (named) {
        const [, kind, name] = named;
        const held = (kind === 'fields' ? list.fields : list.views).get(name);
        if (!held) return refusal(400, `'${name}' does not exist.`);
        if (verb !== 'MERGE') return jsonResponse(200, held);
        const { __metadata, ...props } = sent;
        Object.assign(held, props);
        return jsonResponse(204, {});
      }
      if (rest === '/views' && method === 'POST') {
        list.views.set(sent.Title, { Title: sent.Title, Scope: sent.Scope || 0 });
        return jsonResponse(201, { Title: sent.Title });
      }
      if (rest.startsWith('/defaultview')) {
        return jsonResponse(200, { Id: 'view-0', Title: 'All', ViewQuery: '', ListViewXml: '' });
      }
      const one = /^\\/items\\((\\d+)\\)/.exec(rest);
      if (one) {
        const item = list.items.find((i) => i.Id === Number(one[1]));
        if (verb === 'MERGE') return writeItem(list, item, sent);
        return jsonResponse(200, rowOf(list, item));
      }
      if (rest.startsWith('/items') && method === 'POST') {
        const item = { Id: list.nextItem };
        const answer = writeItem(list, item, sent);
        if (!answer.ok) return answer;
        list.nextItem += 1;
        list.items.push(item);
        return jsonResponse(201, { Id: item.Id });
      }
      if (rest.startsWith('/items')) {
        return jsonResponse(200, { value: list.items.map((i) => rowOf(list, i)) });
      }
      if (rest === '/RenderListDataAsStream') {
        const xml = (sent.parameters && sent.parameters.ViewXml) || '';
        if (/NoSuchColumn|Name="Folder"/.test(xml)) return refusal(500, 'Column does not exist.');
        if (/Collapse="TRUE"/.test(xml)) return jsonResponse(200, { Row: [] });
        const atRoot = list.items.filter((i) => i.folder === list.root);
        return jsonResponse(200, { Row: atRoot.map((i) => rowOf(list, i)) });
      }
      return refusal(404, `unmocked ${path}`);
    };
""")

# --------------------------------------------------------------------------
# Item 10: a view found by title answers for no POST this run sent.
# --------------------------------------------------------------------------
_GUARDS = "library-guards-probe.js"
_GUARDS_LIB = "dbmlsp Probe Guards Library"
_SCOPE_CREATE = "library.view.scope-on-create-reads-back"
_SCOPE_CREATE_VIEW = "dbmlsp guards scope create"


def _view_creates(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "POST" and r["path"].endswith("/views")]


def test_guards_reads_scope_back_off_a_view_it_created() -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, {}, _GUARDS)

    assert rows[_SCOPE_CREATE]["outcome"] == "STICKS", rows[_SCOPE_CREATE]
    assert rows["library.view.scope-on-merge-reads-back"]["outcome"] == "STICKS"
    assert any(_SCOPE_CREATE_VIEW in r["body"] for r in _view_creates(sent))


def test_guards_voids_scope_on_create_when_the_view_was_already_present() -> None:
    """The reused view read back Scope 1 and was reported as a create that stuck."""
    existing = {_GUARDS_LIB: {"template": 101, "views": {_SCOPE_CREATE_VIEW: {"Scope": 1}}}}
    rows, sent = _run_probe(_LIBRARY_MOCK, {"existing": existing}, _GUARDS)

    row = rows[_SCOPE_CREATE]
    assert row["state"] == "void", row
    assert "already present" in row["evidence"]
    assert not any(_SCOPE_CREATE_VIEW in r["body"] for r in _view_creates(sent))
    assert rows["library.view.scope-on-merge-reads-back"]["outcome"] == "STICKS"


# --------------------------------------------------------------------------
# Item 14: library-view checks every write its grouping rows read.
# --------------------------------------------------------------------------
_VIEW = "library-view-probe.js"
_BY_METADATA = "library.view.group-by-metadata-column"
_BY_FOLDER = "library.view.group-by-folder"


def _grouping_queries(sent: list[dict[str, str]], field: str) -> list[dict[str, str]]:
    return [r for r in sent if r["path"].endswith("/RenderListDataAsStream")
            and f'GroupBy Collapse=\\"FALSE\\"><FieldRef Name=\\"{field}' in r["body"]]


def test_library_view_groups_files_it_wrote_and_read_back() -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, {}, _VIEW)

    assert rows[_BY_METADATA]["outcome"] == "SAME AS LIST", rows[_BY_METADATA]
    assert rows[_BY_FOLDER]["outcome"] == "FOLDERS ARE NOT A REST GROUPING DIMENSION"
    assert not _void_ids(rows)
    assert _grouping_queries(sent, "dbmlspDocCategory")


@pytest.mark.parametrize(
    ("config", "named"),
    [
        ({"failUpload": ["doc-beta-1.txt"]}, "the upload of 'doc-beta-1.txt' answered HTTP 400"),
        ({"failMerge": ["doc-alpha-1.txt"]},
         "the dbmlspDocCategory MERGE on 'doc-alpha-1.txt' answered HTTP 500"),
        ({"dropMerge": ["doc-beta-1.txt"]},
         "'doc-beta-1.txt' reads back dbmlspDocCategory=null, not Beta"),
    ],
    ids=["upload", "merge", "dropped-merge"],
)
def test_library_view_voids_the_metadata_row_on_a_failed_write(
    config: dict[str, Any], named: str,
) -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, config, _VIEW)

    assert _void_ids(rows) == {_BY_METADATA}
    assert named in rows[_BY_METADATA]["evidence"]
    assert not _grouping_queries(sent, "dbmlspDocCategory")
    assert rows[_BY_FOLDER]["outcome"] == "FOLDERS ARE NOT A REST GROUPING DIMENSION"


def test_library_view_voids_the_folder_row_when_the_folder_was_not_created() -> None:
    rows, sent = _run_probe(_LIBRARY_MOCK, {"folderStatus": 500}, _VIEW)

    assert _void_ids(rows) == {_BY_FOLDER}
    evidence = rows[_BY_FOLDER]["evidence"]
    assert "the create of folder 'FolderAlpha' answered HTTP 500" in evidence
    assert "the upload of 'subfolder-doc.txt' answered HTTP 404" in evidence
    assert not _grouping_queries(sent, "Folder")
    assert rows[_BY_METADATA]["outcome"] == "SAME AS LIST"
