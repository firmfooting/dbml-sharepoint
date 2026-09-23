# test/test_seam_register_family.py
"""seam-register rules the build cannot see.

50-govern/governance.md is the family's whole rule set: save rules, which
SharePoint holds, and Friday checks, which it cannot. Review of the first
pull request kept finding the seeded rows breaking a rule, or the prose
promising one nothing held, one at a time. So every Friday check with an ID
runs here against the seed, every save rule is evaluated on every seeded
row, and the save-rule table must name every column a rule reads. A row
the seed leaves undone on purpose is declared, with the view that lists it.
"""

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote

import pytest
import yaml
from _paths import SOLUTION_TEMPLATES
from test_template_standard import _as_date, _evaluate, _load

from dbml_sharepoint.analysis.condition_rendering import normalise
from dbml_sharepoint.analysis.conditions import leaves
from dbml_sharepoint.analysis.save_rules import effective_list_validation, hoisted_columns

FAMILY = SOLUTION_TEMPLATES / "seam-register"
MAPPING = FAMILY / "20-configure" / "mapping.yaml"
GOVERNANCE = FAMILY / "50-govern" / "governance.md"
PROVIDER_SIDES = {"Provider", "Third party", "Shared"}

Row = dict[str, Any]
Seed = dict[str, dict[str, Row]]
Offenders = set[tuple[str, str]]


def _mapping() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
    return loaded


def _seed() -> Seed:
    """{entity: {key: values}}, schema defaults filled in as SharePoint would."""
    loaded = _load("seam-register")
    defaults = {
        table.name: {
            column.name: (
                column.default.strip("'") if isinstance(column.default, str) else column.default
            )
            for column in table.columns
            if column.default is not None
        }
        for table in loaded.schema.tables
    }
    return {
        entity: {item.key: {**defaults.get(entity, {}), **item.values} for item in items}
        for entity, items in loaded.mapping.demo_items.items()
    }


def _ref(value: Any) -> str | None:
    return value["demo_ref"] if isinstance(value, dict) else None


def _refs(value: Any) -> set[str]:
    return {item["demo_ref"] for item in value or []}


def _blank(value: Any) -> bool:
    return value is None or value == [] or (isinstance(value, str) and not value.strip())


def _evidence(seed: Seed, service: str) -> list[Row]:
    return [e for _, e in _evidence_items(seed, service)]


def _evidence_items(seed: Seed, service: str) -> list[tuple[str, Row]]:
    return [(k, e) for k, e in seed["Evidence"].items() if _ref(e["Service"]) == service]


# === The Friday checks, one predicate per ID in the governance table =========


# An unresolved seam of one of these types is a disagreement, so F1 fails.
DISPUTE_TYPES = {"Disputed owner", "Disputed support", "Contradicts document"}


# The two columns the seam map draws, which Verified corroborates.
CORROBORATED = ("Run by", "Support")


def _corroborated(seed: Seed, rows: list[Row]) -> bool:
    """Two known sides, or one System data row with its export, none flagged."""
    agreeing = [e for e in rows if not e["Contradicts"]]
    system = any(
        e["EvidenceType"] == "System data" and _ref(e.get("Artefact")) is not None
        and seed["Artefact"][_ref(e["Artefact"]) or ""]["ArtefactType"] == "System export"
        for e in agreeing
    )
    return system or len({e["SourceSide"] for e in agreeing} - {"Unknown"}) >= 2


def _verified_without_two_sources(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, service in seed["Service"].items():
        if service["Confidence"] != "Verified":
            continue
        rows = _evidence(seed, key)
        corroborated = {
            field: _corroborated(seed, [e for e in rows if e["SupportsField"] == field])
            for field in CORROBORATED if FILLS[field](service)
        }
        settled = {
            ref for seam in seed["Seam"].values() if seam["Status"] == "Resolved"
            for ref in _refs(seam.get("EvidenceInConflict"))
        }
        # A contradiction a resolved seam closed no longer blocks Verified.
        open_flags = any(
            e["Contradicts"] and k not in settled for k, e in _evidence_items(seed, key)
        )
        contradicted = open_flags or any(
            _ref(seam["Service"]) == key and seam["Status"] != "Resolved"
            and seam["SeamType"] in DISPUTE_TYPES
            for seam in seed["Seam"].values()
        )
        if contradicted or not all(corroborated.values()):
            bad.add(("Service", key))
    return bad


def _above_assumed_without_evidence(seed: Seed) -> Offenders:
    return {
        ("Service", key) for key, s in seed["Service"].items()
        if s["Confidence"] != "Assumed" and not _evidence(seed, key)
    }


def _first_pass_without_evidence(seed: Seed) -> Offenders:
    return {
        ("Service", key) for key, s in seed["Service"].items()
        if s["FirstPass"] and not _evidence(seed, key)
    }


def _contradiction_not_in_a_seam(seed: Seed) -> Offenders:
    cited = {ref for seam in seed["Seam"].values() for ref in _refs(seam.get("EvidenceInConflict"))}
    return {
        ("Evidence", key) for key, e in seed["Evidence"].items()
        if e["Contradicts"] and key not in cited
    }


def _seam_cites_another_services_evidence(seed: Seed) -> Offenders:
    return {
        ("Seam", key) for key, seam in seed["Seam"].items()
        if any(_ref(seed["Evidence"][ref]["Service"]) != _ref(seam["Service"])
               for ref in _refs(seam.get("EvidenceInConflict")))
    }


def _held_without_a_link(seed: Seed) -> Offenders:
    return {
        ("Service", key) for key, s in seed["Service"].items()
        if s["Documentation"] in {"Held", "Verified"} and _blank(s.get("DocumentationLink"))
    }


def _provider_not_named(seed: Seed) -> Offenders:
    """Keyed by row and lookup, since a service has two."""
    return {
        (entity, f"{key}:{lookup}")
        for entity, lookups in PROVIDER_LOOKUPS.items()
        for key, row in seed[entity].items()
        for lookup, side in lookups.items()
        if row[side] in PROVIDER_SIDES and _blank(row.get(lookup))
    }


def _evidence_file_for_another_service(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, e in seed["Evidence"].items():
        artefact = _ref(e.get("Artefact"))
        if artefact is not None and _ref(e["Service"]) not in _refs(
            seed["Artefact"][artefact].get("Services"),
        ):
            bad.add(("Evidence", key))
    return bad


def _file_without_a_title(seed: Seed) -> Offenders:
    return {("Artefact", key) for key, a in seed["Artefact"].items() if _blank(a.get("Title"))}


def _resolved_without_a_resolution(seed: Seed) -> Offenders:
    return {
        ("Seam", key) for key, seam in seed["Seam"].items()
        if seam["Status"] == "Resolved" and _blank(seam.get("Resolution"))
    }


def _answer_without_a_summary(seed: Seed) -> Offenders:
    return {
        ("DocumentRequest", key) for key, d in seed["DocumentRequest"].items()
        if d["Status"] in {"Received", "Refused", "Not found"} and _blank(d.get("Summary"))
    }


def _failure_half_recorded(seed: Seed) -> Offenders:
    return {
        ("Service", key) for key, s in seed["Service"].items()
        if _blank(s.get("LastFailureDate")) != _blank(s.get("LastFailure"))
    }


def _received_without_a_file(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, d in seed["DocumentRequest"].items():
        if d["Status"] != "Received":
            continue
        wanted = "Invoice extract" if d["DocumentType"] == "Invoice" else "Document copy"
        if not any(
            _ref(a.get("Request")) == key and a["ArtefactType"] == wanted
            for a in seed["Artefact"].values()
        ):
            bad.add(("DocumentRequest", key))
    return bad


def _before(row: Row, later: str, earlier: str) -> bool:
    first, second = _as_date(row.get(earlier)), _as_date(row.get(later))
    return first is not None and second is not None and second < first


def _dates_out_of_order(seed: Seed) -> Offenders:
    seams = {
        ("Seam", key) for key, seam in seed["Seam"].items()
        if _before(seam, "ResolveBy", "RaisedOn") or _before(seam, "ResolvedOn", "RaisedOn")
    }
    asks = {
        ("DocumentRequest", key) for key, d in seed["DocumentRequest"].items()
        if _before(d, "DueOn", "AskedOn") or _before(d, "AnsweredOn", "AskedOn")
    }
    return seams | asks


def _completed(seed: Seed) -> dict[str, Row]:
    return {key: i for key, i in seed["Interview"].items() if i["Status"] == "Completed"}


QUESTIONS = [
    "Q1Runs", "Q2Uses", "Q3Call", "Q4Decides",
    "Q5AskProvider", "Q6AskedProvider", "Q7Auditor", "Q8Saturday",
]


def _unanswered_question(seed: Seed) -> Offenders:
    return {
        ("Interview", key) for key, i in _completed(seed).items()
        if any(_blank(i.get(q)) for q in QUESTIONS)
    }


def _completed_without_notes(seed: Seed) -> Offenders:
    return {
        ("Interview", key) for key, i in _completed(seed).items()
        if _ref(i.get("NotesFile")) is None
        or seed["Artefact"][_ref(i["NotesFile"]) or ""]["ArtefactType"] != "Interview notes"
    }


def _title_names_another_week(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, week in seed["WeeklyUpdate"].items():
        named = re.search(r"\bWeek (\d+)\b", week["Title"])
        if named is None or int(named.group(1)) != week["WeekNo"]:
            bad.add(("WeeklyUpdate", key))
    return bad


# The Bears on columns each dispute type is about.
DISPUTED_FIELDS = {"Disputed support": {"Support"}, "Disputed owner": {"Run by", "Decided by"}}


def _dispute_without_both_sides(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, seam in seed["Seam"].items():
        fields = DISPUTED_FIELDS.get(seam["SeamType"])
        if fields is None:
            continue
        picked = [
            seed["Evidence"][ref] for ref in _refs(seam.get("EvidenceInConflict"))
            if seed["Evidence"][ref]["Contradicts"]
        ]
        # Unknown names no side, so it cannot be one side of a dispute.
        sides = {
            field: {e["SourceSide"] for e in picked if e["SupportsField"] == field} - {"Unknown"}
            for field in fields
        }
        if not any(len(found) >= 2 for found in sides.values()):
            bad.add(("Seam", key))
    return bad


def _file_titles_repeat(seed: Seed) -> Offenders:
    titles = [a.get("Title") for a in seed["Artefact"].values()]
    return {
        ("Artefact", key) for key, a in seed["Artefact"].items()
        if titles.count(a.get("Title")) > 1
    }


def _seam_without_its_evidence(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, seam in seed["Seam"].items():
        if seam["SeamType"] == "No owner" and seam["Status"] != "Resolved":
            continue
        picked = [seed["Evidence"][ref] for ref in _refs(seam.get("EvidenceInConflict"))]
        by_field: dict[str, set[bool]] = {}
        for e in picked:
            if e["Contradicts"]:
                by_field.setdefault(e["SupportsField"], set()).add(e["EvidenceType"] == "Document")
        # Both a Document row and another row, about the same column.
        both = any(kinds == {True, False} for kinds in by_field.values())
        if not picked or (seam["SeamType"] == "Contradicts document" and not both):
            bad.add(("Seam", key))
    return bad


def _seams_found_miscounted(seed: Seed) -> Offenders:
    bad: Offenders = set()
    raised = [_as_date(seam["RaisedOn"]) for seam in seed["Seam"].values()]
    for key, week in seed["WeeklyUpdate"].items():
        end = _as_date(week["WeekEnding"])
        assert end is not None, key
        found = sum(1 for day in raised if day is not None and 0 <= (end - day).days < 7)
        if found != week["SeamsFound"]:
            bad.add(("WeeklyUpdate", key))
    return bad


# {Bears on value: whether the service row fills that column}.
FILLS: dict[str, Callable[[Row], bool]] = {
    "Run by": lambda s: s["RunBySide"] != "Unknown",
    "Support": lambda s: s["SupportSide"] != "Unknown",
    "Decided by": lambda s: not _blank(s.get("DecidedBy")),
    "Runs where": lambda s: not _blank(s.get("Hosting")),
    "Documentation": lambda s: s["Documentation"] != "Not asked",
    "Last failure": lambda s: not _blank(s.get("LastFailureDate")),
    "Dependency": lambda s: not _blank(s.get("Dependency")),
    "Out of hours": lambda s: not _blank(s.get("OutOfHours")),
    "Single person": lambda s: bool(s.get("SinglePerson")),
}


def _verified_fact_without_evidence(seed: Seed) -> Offenders:
    bad: Offenders = set()
    for key, service in seed["Service"].items():
        if service["Confidence"] != "Verified":
            continue
        # A flagged row may be the claim that lost, so it covers nothing.
        covered = {e["SupportsField"] for e in _evidence(seed, key) if not e["Contradicts"]}
        for field, fills in FILLS.items():
            if fills(service) and field not in covered:
                bad.add(("Service", f"{key}:{field}"))
    return bad


def _fractional_rows_verified(seed: Seed) -> Offenders:
    return {
        ("WeeklyUpdate", key) for key, w in seed["WeeklyUpdate"].items()
        if float(w["RowsVerified"]) != int(w["RowsVerified"])
    }


def _open_seam_without_an_owner(seed: Seed) -> Offenders:
    return {
        ("Seam", key) for key, seam in seed["Seam"].items()
        if seam["Status"] != "Resolved" and _blank(seam.get("ResolveOwner"))
    }


CHECKS: dict[str, Callable[[Seed], Offenders]] = {
    "F1": _verified_without_two_sources,
    "F2": _above_assumed_without_evidence,
    "F3": _first_pass_without_evidence,
    "F4": _contradiction_not_in_a_seam,
    "F5": _seam_cites_another_services_evidence,
    "F6": _held_without_a_link,
    "F7": _provider_not_named,
    "F8": _evidence_file_for_another_service,
    "F9": _file_without_a_title,
    "F10": _resolved_without_a_resolution,
    "F11": _answer_without_a_summary,
    "F12": _failure_half_recorded,
    "F13": _received_without_a_file,
    "F14": _dates_out_of_order,
    "F15": _unanswered_question,
    "F16": _completed_without_notes,
    "F18": _title_names_another_week,
    "F20": _dispute_without_both_sides,
    "F21": _file_titles_repeat,
    "F22": _open_seam_without_an_owner,
    "F23": _seam_without_its_evidence,
    "F24": _seams_found_miscounted,
    "F25": _verified_fact_without_evidence,
    "F26": _fractional_rows_verified,
}

# Checks no predicate can make over the seed, and why.
UNEXECUTABLE = {
    "F17": "No column links an evidence row to the interview it came from",
    "F19": "A reading check; nothing marks a string as a person's name",
}

# The seed is the end of week two, so some Friday checks are still work to
# do. Each such row is declared with the view that lists it.
OPEN_WORK: dict[str, dict[tuple[str, str], str]] = {
    "F3": {
        ("Service", "svc-citrix"): "Assumed",
        ("Service", "svc-sso"): "Assumed",
    },
    "F7": {
        ("Service", "svc-badges:RunByProvider"): "Provider not named",
        ("Service", "svc-phones:SupportProvider"): "Provider not named",
        ("DocumentRequest", "doc-attestation:HolderProvider"): "Provider not named",
        ("Interview", "int-declined:IntervieweeProvider"): "Provider not named",
        ("Incident", "inc-desktop-1:ResolverProvider"): "Provider not named",
    },
    "F22": {
        ("Seam", "seam-backup-support"): "Open seams",
    },
}


def _governance_table(heading: str) -> list[list[str]]:
    """The rows of the first table under a `### heading`, header and rule dropped."""
    text = GOVERNANCE.read_text(encoding="utf-8")
    section = text.split(f"### {heading}\n", 1)[1].split("\n#", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def test_every_friday_check_is_executed_or_explained() -> None:
    ids = [row[0] for row in _governance_table("Friday checks")]
    assert ids == [f"F{n}" for n in range(1, len(ids) + 1)], ids
    assert not set(CHECKS) & set(UNEXECUTABLE)
    assert set(ids) == set(CHECKS) | set(UNEXECUTABLE)
    assert set(OPEN_WORK) <= set(CHECKS)


def _number(check: str) -> int:
    return int(check[1:])


CHECK_IDS: list[str] = sorted(CHECKS.keys(), key=_number)


@pytest.mark.parametrize("check", CHECK_IDS)
def test_the_seed_passes_every_friday_check_but_its_declared_open_work(check: str) -> None:
    assert CHECKS[check](_seed()) == set(OPEN_WORK.get(check, {}))


def test_every_open_row_is_listed_by_its_view() -> None:
    loaded = _load("seam-register")
    seed = _seed()
    for (entity, key), title in (item for work in OPEN_WORK.values() for item in work.items()):
        view = next(v for v in loaded.mapping.views[entity] if v.title == title)
        assert view.where is not None, (entity, title)
        types = loaded.column_types(entity)
        row = seed[entity][key.split(":")[0]]
        assert _evaluate(normalise(view.where), row, types) is True, (entity, key, title)


def test_every_seeded_row_passes_its_save_rules() -> None:
    loaded = _load("seam-register")
    seed = _seed()
    refused: list[str] = []
    for entity, rows in seed.items():
        types = loaded.column_types(entity)
        rule = effective_list_validation(loaded.mapping, entity, types)
        section = loaded.mapping.column_validation.get(entity)
        hoisted = {column for column, _ in hoisted_columns(section, types)}
        declared = section.columns.items() if section else []
        columns = [(c, r) for c, r in declared if c not in hoisted]
        for key, row in rows.items():
            if rule is not None and _evaluate(normalise(rule.when), row, types) is not True:
                refused.append(f"{entity}/{key}: {rule.message}")
            for column, column_rule in columns:
                # A column rule does not fire on a blank.
                if _blank(row.get(column)):
                    continue
                if _evaluate(normalise(column_rule.when), row, types) is not True:
                    refused.append(f"{entity}/{key}: {column}")
    assert not refused, refused


def test_the_save_rule_table_names_every_column_a_rule_reads() -> None:
    """The table is the only place the save rules are written in prose, so
    a rule that gains a column must say so there."""
    loaded = _load("seam-register")
    table = {row[0]: row[1] for row in _governance_table("Save rules")}
    expected: dict[str, set[str]] = {}
    for entity, rule in loaded.mapping.list_validation.items():
        expected.setdefault(entity, set()).update(leaf.field for leaf in leaves(rule.when))
    for entity, section in loaded.mapping.column_validation.items():
        expected.setdefault(entity, set()).update(section.columns)
    for schema_table in loaded.schema.tables:
        unique = {column.name for column in schema_table.columns if column.unique}
        if unique:
            expected.setdefault(schema_table.name, set()).update(unique)
    assert set(table) == set(expected)
    missing = [
        f"{entity}: **{loaded.mapping.display_name_for(entity, field)}**"
        for entity, fields in expected.items()
        for field in fields
        if f"**{loaded.mapping.display_name_for(entity, field)}**" not in table[entity]
    ]
    assert not missing, missing


# {entity: {provider lookup: the side column that shows it}}.
PROVIDER_LOOKUPS = {
    "Service": {"RunByProvider": "RunBySide", "SupportProvider": "SupportSide"},
    "DocumentRequest": {"HolderProvider": "HolderSide"},
    "Interview": {"IntervieweeProvider": "IntervieweeSide"},
    "Incident": {"ResolverProvider": "ResolverSide"},
}


def _not_named_branches(view: dict[str, Any]) -> dict[str, set[str]]:
    """{provider column: sides} from a Provider not named view's filter."""
    where = view["where"]
    branches = where[0].get("any_of", [{"all_of": where}])
    found: dict[str, set[str]] = {}
    for branch in branches:
        side, provider = branch["all_of"]
        assert provider["op"] == "is_null", provider
        found[provider["field"]] = set(side["value"])
    return found


def test_every_provider_lookup_has_a_not_named_view_over_its_shown_sides() -> None:
    mapping = _mapping()
    for entity, columns in PROVIDER_LOOKUPS.items():
        rules = mapping["form_visibility"][entity]["columns"]
        shown = {column: set(rules[column]["when"][0]["value"]) for column in columns}
        views = [v for v in mapping["views"][entity] if v["title"] == "Provider not named"]
        assert len(views) == 1, f"{entity} has no Provider not named view"
        assert _not_named_branches(views[0]) == shown == dict.fromkeys(columns, PROVIDER_SIDES)


def _leaves(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        return [leaf for item in node for leaf in _leaves(item)]
    if isinstance(node, dict) and "field" in node:
        return [node]
    if isinstance(node, dict):
        return [leaf for group in node.values() for leaf in _leaves(group)]
    return []


def test_no_save_rule_requires_a_hidden_field_to_be_empty() -> None:
    """A field a status or side hides keeps its old value when the row moves
    back, by design: the form stays uncluttered and reporting filters by
    status. So no save rule may test such a field for blank, or that row
    could never be saved again."""
    mapping = _mapping()
    problems: list[str] = []
    for entity, rules in mapping["form_visibility"].items():
        hidden = {c for c, r in rules["columns"].items() if isinstance(r, dict) and "when" in r}
        rule = mapping.get("list_validation", {}).get(entity)
        for leaf in _leaves(rule["when"] if rule else []):
            if leaf["field"] in hidden and leaf["op"] == "is_null":
                problems.append(f"{entity}.{leaf['field']}")
    assert not problems, problems


def test_every_seeded_link_into_the_library_names_a_seeded_file() -> None:
    """A link to a file the seed never uploads made a row look Held."""
    demo = _mapping()["demo_items"]
    seeded = {
        f"{row['file']['folder']}/{row['file']['name']}" for row in demo["Artefact"]
    }
    marker = "/SEAM_Artefact/"
    links = [
        value["url"]
        for rows in demo.values()
        for row in rows
        for value in row["values"].values()
        if isinstance(value, dict) and marker in value.get("url", "")
    ]
    assert links, "no seeded row links into the library"
    missing = [u for u in links if unquote(u.split(marker, 1)[1]) not in seeded]
    assert not missing, missing



def _values(leaf: dict[str, Any]) -> set[Any]:
    value = leaf["value"]
    return set(value) if isinstance(value, list) else {value}


def test_no_view_shows_a_stale_hidden_value_unexplained() -> None:
    """A field hidden by status keeps its old value, so a view showing it
    must list only the statuses that show it. A provider hidden by side may
    instead sit beside its side, which is the current answer."""
    mapping = _mapping()
    problems: list[str] = []
    for entity, rules in mapping["form_visibility"].items():
        shown = {
            column: rule["when"][0] for column, rule in rules["columns"].items()
            if isinstance(rule, dict) and "when" in rule
        }
        for view in mapping["views"].get(entity, []):
            where = [leaf for leaf in view.get("where") or [] if "field" in leaf]
            displayed = set(view["fields"]) | {view.get("group_by", {}).get("field")}
            for column in set(view["fields"]) & set(shown):
                condition = shown[column]
                filtered = any(
                    leaf["field"] == condition["field"] and leaf["op"] in ("eq", "in")
                    and _values(leaf) <= _values(condition)
                    for leaf in where
                )
                beside = condition["field"] != "Status" and condition["field"] in displayed
                if not (filtered or beside):
                    problems.append(f"{entity}/{view['title']}: {column}")
    assert not problems, problems


# A lookup picker shows the target's Title and nothing else. The library's
# uniqueness is unmeasured, so a Friday check holds it instead.
PICKER_TITLES_BY_CHECK = {"Artefact": "F21"}


def test_every_lookup_target_shows_a_unique_title() -> None:
    loaded = _load("seam-register")
    tables = {table.name: table for table in loaded.schema.tables}
    targets = {
        column.ref.target_table
        for table in loaded.schema.tables
        for column in table.columns
        if column.ref is not None
    }
    assert targets, "no lookups found; the ref attribute has moved"
    problems = [
        target for target in sorted(targets)
        if target not in PICKER_TITLES_BY_CHECK
        and not any(c.name == "Title" and c.unique for c in tables[target].columns)
    ]
    assert not problems, problems
    ids = {row[0] for row in _governance_table("Friday checks")}
    assert set(PICKER_TITLES_BY_CHECK.values()) <= ids


def test_a_flagged_row_covers_no_verified_fact() -> None:
    """Direct, because flagging any seeded row also trips F4 first."""
    seed = _seed()
    assert ("Service", "svc-accounts:Decided by") not in _verified_fact_without_evidence(seed)
    seed["Evidence"]["evd-accounts-decides"]["Contradicts"] = True
    assert ("Service", "svc-accounts:Decided by") in _verified_fact_without_evidence(seed)
