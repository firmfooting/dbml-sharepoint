# test/test_mapping_loader.py
import ast
import inspect
from pathlib import Path

import pytest

from dbml_sharepoint.model import mapping_loader
from dbml_sharepoint.model.mapping_loader import (
    FormVisibility,
    ListPermissionPolicy,
    RetiredColumn,
    load_mapping,
)


def test_unknown_entity_kind_is_a_load_error(tmp_path: Path) -> None:
    """kind is a Literal-typed closed vocabulary; the loader is its one
    admission gate. A typo'd kind must fail the build here — before this
    gate existed it flowed into schema_json and silently missed
    downstream comparisons like kind == "DocumentLibrary"."""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Policy: { kind: DocLibrary, base_template: 101, site_role: default }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as err:
        load_mapping(tmp_path / "m.yaml")
    assert "entities.Policy.kind" in str(err.value)
    assert "DocumentLibrary" in str(err.value)


def test_column_formatting_style_specs_expand_to_formatters(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Status: { style: severity, map: { Open: low, Closed: good } }\n",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    expanded = bundle.mapping.column_formatting["Risk"]["Status"]
    assert expanded["elmType"] == "div"
    assert "sp-field-severity--good" in expanded["attributes"]["class"]
    assert bundle.mapping.column_style_specs["Risk"]["Status"]["style"] == "severity"


def test_style_theme_applies_and_rejects_unknown_tokens(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "style_theme:\n"
        "  good: { classes: [brand-good] }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Status: { style: severity, map: { Closed: good } }\n",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    expanded = bundle.mapping.column_formatting["Risk"]["Status"]
    assert "brand-good" in expanded["attributes"]["class"]
    (tmp_path / "bad.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "style_theme:\n"
        "  shiny: { classes: [x] }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="style_theme"):
        load_mapping(tmp_path / "bad.yaml")


def test_invalid_style_spec_is_a_load_error(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Status: { style: severity }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"column_formatting\.Risk\.Status"):
        load_mapping(tmp_path / "m.yaml")

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_mapping_resolves_relative_config_paths() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.prefix == "APP_"
    assert "Strategy" in bundle.enum_choices["topic"]
    assert "Standard7Y" in bundle.retention_policies


def test_entity_lookup_returns_kind_and_template() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    project = bundle.mapping.entity("Project")
    assert project.kind == "List"
    assert project.base_template == 100


def test_unknown_entity_raises() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    with pytest.raises(KeyError):
        bundle.mapping.entity("DoesNotExist")


def test_permissions_section_loaded() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    assert len(perms.levels) == 1
    assert perms.levels[0].name == "Schema Manager"
    assert "ViewListItems" in perms.levels[0].base_permissions
    assert len(perms.groups) == 1
    assert perms.groups[0].name == "List Maintainer"
    assert perms.groups[0].owner_group == "Site Owners"
    assert perms.groups[0].require_empty_at_deploy is True
    assert perms.default_policy is not None
    assert perms.default_policy.break_inheritance is True
    assert perms.default_policy.reconcile_mode == "exact"
    assert len(perms.default_policy.assignments) == 3


def test_site_group_empty_gate_defaults_to_false(tmp_path: Path) -> None:
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "APP_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
groups:
  - name: "Existing members allowed"
""",
        encoding="utf-8",
    )

    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.permissions is not None
    assert bundle.mapping.permissions.groups[0].require_empty_at_deploy is False


def test_site_group_empty_gate_requires_boolean(tmp_path: Path) -> None:
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "APP_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
groups:
  - name: "Ambiguous gate"
    require_empty_at_deploy: "false"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="require_empty_at_deploy must be a boolean"):
        load_mapping(tmp_path / "mapping.yaml")


def test_invalid_permission_reconcile_mode_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "APP_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
list_permissions:
  default:
    reconcile: best-effort
    assignments: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reconcile must be"):
        load_mapping(tmp_path / "mapping.yaml")


def test_exact_reconcile_requires_broken_inheritance(tmp_path: Path) -> None:
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "APP_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
list_permissions:
  default:
    break_inheritance: false
    reconcile: exact
    assignments: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires break_inheritance: true"):
        load_mapping(tmp_path / "mapping.yaml")


def test_permissions_for_entity_returns_default() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    policy = bundle.mapping.permissions_for_entity("Project")
    assert policy is not None
    assert policy.break_inheritance is True


def test_permissions_for_entity_returns_none_when_no_permissions() -> None:
    """When no permissions section exists, permissions_for_entity returns None."""
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    # Remove permissions to test None path.
    bundle.mapping.permissions = None
    policy = bundle.mapping.permissions_for_entity("Project")
    assert policy is None


def test_default_policy_site_role_parsed_from_yaml() -> None:
    """list_permissions.default.site_role scopes the default policy to one
    site role (the fixture declares default)."""
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    assert perms.default_policy_site_role == "default"


def test_default_policy_not_applied_to_other_site_role() -> None:
    """Regression: a role-scoped default policy must NOT fall back onto
    hub entities. Previously permissions_for_entity ignored site_role, so a
    build for another role would re-ACL its lists with the wrong groups/levels."""
    from dbml_sharepoint.model.mapping_loader import EntityMapping

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    perms.default_policy_site_role = "default"
    bundle.mapping.entities["Task"] = EntityMapping(
        name="Task", kind="HubOnlyList", base_template=100, site_role="admin",
    )

    assert bundle.mapping.permissions_for_entity("Task") is None
    # Entities of the scoped role still receive the default.
    assert bundle.mapping.permissions_for_entity("Project") is not None
    # Explicit overrides remain per-entity and are not scope-filtered.
    hub_policy = ListPermissionPolicy(break_inheritance=True, assignments=[])
    perms.overrides["Task"] = hub_policy
    assert bundle.mapping.permissions_for_entity("Task") is hub_policy


def test_default_policy_without_site_role_applies_to_all() -> None:
    """When no site_role scope is declared the default applies to every
    entity, preserving pre-scope behaviour."""
    from dbml_sharepoint.model.mapping_loader import EntityMapping

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    perms.default_policy_site_role = None
    bundle.mapping.entities["Task"] = EntityMapping(
        name="Task", kind="HubOnlyList", base_template=100, site_role="admin",
    )
    assert bundle.mapping.permissions_for_entity("Task") is not None


# === Generalization: enum_sources, optional retention,
# extension key ===


def test_minimal_mapping_loads_with_empty_extras(tmp_path: Path) -> None:
    """A mapping with only prefix + entities (no config files, no extension
    declared) must load cleanly with every optional section defaulting to
    empty — the generic core has no required config beyond the mapping
    itself."""
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.prefix == "MIN_"
    assert bundle.mapping.extension is None
    assert bundle.enum_choices == {}
    assert bundle.retention_policies == {}
    assert bundle.retention_list_defaults == {}
    assert bundle.extension_configs == {}
    assert bundle.extension_config_for("my_org") == {}
    assert bundle.extension_config_for(None) == {}
    assert bundle.mapping.polymorphic_patterns == []


def test_enum_sources_loads_choices_with_explicit_fragment(tmp_path: Path) -> None:
    """enum_sources values are `path#fragment`; the fragment names the
    top-level key to read from the target YAML."""
    (tmp_path / "topics.yaml").write_text(
        'topics:\n  - "Strategy"\n  - "Other"\n',
        encoding="utf-8",
    )
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
enum_sources:
  topic: "topics.yaml#topics"
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.enum_choices["topic"] == ["Strategy", "Other"]
    assert bundle.mapping.enum_sources["topic"] == (tmp_path / "topics.yaml").resolve()


def test_enum_sources_fragmentless_value_defaults_to_choices_key(tmp_path: Path) -> None:
    """A fragmentless enum_sources value reads the 'choices' top-level key."""
    (tmp_path / "statuses.yaml").write_text(
        'choices:\n  - "Open"\n  - "Closed"\n',
        encoding="utf-8",
    )
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
enum_sources:
  status: "statuses.yaml"
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.enum_choices["status"] == ["Open", "Closed"]


def test_extension_config_for_selects_block_by_name(tmp_path: Path) -> None:
    """extension_config_for(name) returns exactly the named extension's block —
    another extension's block must not leak into it."""
    (tmp_path / "reg.yaml").write_text("units: []\n", encoding="utf-8")
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
extension: my_org
extensions:
  my_org:
    org_register_source: "reg.yaml"
  other_ext:
    some_key: "ignored"
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.extension == "my_org"
    assert bundle.extension_configs == {
        "my_org": {"org_register_source": "reg.yaml"},
        "other_ext": {"some_key": "ignored"},
    }
    assert bundle.extension_config_for("my_org") == {"org_register_source": "reg.yaml"}
    assert bundle.extension_config_for("other_ext") == {"some_key": "ignored"}
    assert bundle.extension_config_for("unknown") == {}


def test_extension_config_for_honors_cli_override_when_mapping_key_absent(
    tmp_path: Path,
) -> None:
    """Regression: config selection must honor the RESOLVED
    extension name, not mapping.extension. A core-CLI run with
    `--extension my_org` against a mapping WITHOUT an `extension:` key must
    still see the extensions.my_org block."""
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
extensions:
  my_org:
    org_register_source: "reg.yaml"
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.extension is None
    assert bundle.extension_config_for("my_org") == {"org_register_source": "reg.yaml"}


def test_extension_config_for_override_wins_over_other_selected_extension(
    tmp_path: Path,
) -> None:
    """Regression: a mapping selecting `extension: other_ext`
    overridden at the CLI with `--extension my_org` must yield my_org's
    block for the resolved extension, not other_ext's."""
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
extension: other_ext
extensions:
  my_org:
    org_register_source: "reg.yaml"
  other_ext:
    some_key: "other"
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.extension == "other_ext"
    assert bundle.extension_config_for("my_org") == {"org_register_source": "reg.yaml"}


def test_entity_display_column_parsed(tmp_path: Path) -> None:
    """A1: a target entity may declare display_column; lookups into it render
    that field instead of the built-in Title. Absent, it defaults to None."""
    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Membership: { kind: List, base_template: 100, site_role: default, display_column: DisplayName }
  Meeting:    { kind: List, base_template: 100, site_role: default }
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.entity("Membership").display_column == "DisplayName"
    assert bundle.mapping.entity("Meeting").display_column is None


def test_polymorphic_patterns_parsed(tmp_path: Path) -> None:
    """`polymorphic_patterns` is a list of
    {list, field, discriminator} triples, parsed into PolymorphicPattern
    objects (replaces manifestgen's hardcoded gov-hub list)."""
    from dbml_sharepoint.model.mapping_loader import PolymorphicPattern

    (tmp_path / "mapping.yaml").write_text(
        """
prefix: "MIN_"
entities:
  Project: { kind: List, base_template: 100, site_role: default }
polymorphic_patterns:
  - { list: StatusChange, field: EntityId, discriminator: EntityType }
  - { list: Escalation,   field: SourceId, discriminator: SourceType }
""",
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "mapping.yaml")
    assert bundle.mapping.polymorphic_patterns == [
        PolymorphicPattern(list="StatusChange", field="EntityId", discriminator="EntityType"),
        PolymorphicPattern(list="Escalation", field="SourceId", discriminator="SourceType"),
    ]


def test_calculated_formulas_loaded() -> None:
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    formulas = bundle.mapping.calculated_formulas
    assert formulas["Risk"]["RiskScore"].startswith("=IF(")
    assert formulas["Risk"]["RiskBand"].startswith("=IF(")


def test_calculated_formulas_default_empty_when_absent() -> None:
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.calculated_formulas == {}


def test_enroll_operator_during_deploy_defaults_false_and_parses_true(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        (FIXTURES / "calculated-mapping.yaml").read_text(encoding="utf-8")
        + (
            "\ngroups:\n"
            "  - name: GH List Administrators\n"
            "    description: Test admin group\n"
            "    owner_group: Site Owners\n"
            "    allow_members_edit_membership: false\n"
            "    allow_request_to_join_leave: false\n"
            "    auto_accept_request_to_join_leave: false\n"
            "    only_allow_members_view_membership: false\n"
            "    enroll_operator_during_deploy: true\n"
            "  - name: GH Automation\n"
            "    description: Test automation group\n"
            "    owner_group: Site Owners\n"
            "    allow_members_edit_membership: false\n"
            "    allow_request_to_join_leave: false\n"
            "    auto_accept_request_to_join_leave: false\n"
            "    only_allow_members_view_membership: true\n"
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    groups = {g.name: g for g in perms.groups}
    assert groups["GH List Administrators"].enroll_operator_during_deploy is True
    assert groups["GH Automation"].enroll_operator_during_deploy is False


# --- Declared views ---------------------------------------------------------


def _views_yaml(views_block: str) -> str:
    return (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        + views_block
    )


def test_views_section_parsed(tmp_path: Path) -> None:
    from dbml_sharepoint.model.conditions import Group, Leaf
    from dbml_sharepoint.model.mapping_loader import ViewGroupBy, ViewSort

    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open projects\n"
            "      default: true\n"
            "      fields: [Title, Status]\n"
            "      where:\n"
            "        - { field: Status, op: neq, value: Closed }\n"
            "      sort:\n"
            "        - { field: SortOrder, direction: asc }\n"
            "      group_by: { field: Status, collapsed: true }\n"
            "      row_limit: 100\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    views = bundle.mapping.views["Project"]
    assert len(views) == 1
    view = views[0]
    assert view.title == "Open projects"
    assert view.default is True
    assert view.fields == ["Title", "Status"]
    assert view.where == Group("all_of", (Leaf("Status", "neq", "Closed"),))
    assert view.sort == [ViewSort(field="SortOrder", direction="asc")]
    assert view.group_by == ViewGroupBy(field="Status", collapsed=True)
    assert view.row_limit == 100


def test_views_optional_parts_default(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Everything\n"
            "      fields: [Title]\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    view = bundle.mapping.views["Project"][0]
    assert view.default is False
    assert view.where is None
    assert view.sort == []
    assert view.group_by is None
    assert view.row_limit is None


def test_views_absent_defaults_empty() -> None:
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert bundle.mapping.views == {}


def test_view_requires_title_and_fields(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml("views:\n  Project:\n    - fields: [Title]\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="title"):
        load_mapping(tmp_path / "m.yaml")
    (tmp_path / "m2.yaml").write_text(
        _views_yaml("views:\n  Project:\n    - title: No fields\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fields"):
        load_mapping(tmp_path / "m2.yaml")


def test_view_sort_direction_must_be_asc_or_desc(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Bad sort\n"
            "      fields: [Title]\n"
            "      sort:\n"
            "        - { field: Title, direction: down }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"'asc' or 'desc'"):
        load_mapping(tmp_path / "m.yaml")


def test_view_widths_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Sized\n"
            "      fields: [Title, Status]\n"
            "      widths:\n"
            "        Title: 240\n"
            "        Status: 110\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.views["Project"][0].widths == {"Title": 240, "Status": 110}


def test_view_widths_default_empty(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Unsized\n"
            "      fields: [Title]\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.views["Project"][0].widths == {}


def test_view_widths_values_must_be_integer_pixels(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Bad width\n"
            "      fields: [Title]\n"
            "      widths:\n"
            "        Title: wide\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integer pixel"):
        load_mapping(tmp_path / "m.yaml")
    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Bad shape\n"
            "      fields: [Title]\n"
            "      widths: [Title]\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mapping of column name"):
        load_mapping(tmp_path / "m2.yaml")


def test_demo_items_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "demo_items:\n"
            "  Project:\n"
            "    - key: p1\n"
            "      values:\n"
            '        Title: "[DEMO] Sample"\n'
            "        SortOrder: 3\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    items = bundle.mapping.demo_items["Project"]
    assert items[0].key == "p1"
    assert items[0].values == {"Title": "[DEMO] Sample", "SortOrder": 3}


def test_demo_items_require_key_and_values(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "demo_items:\n"
            "  Project:\n"
            "    - values: { Title: x }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'key' is required"):
        load_mapping(tmp_path / "m.yaml")
    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            "demo_items:\n"
            "  Project:\n"
            "    - key: p1\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-empty mapping"):
        load_mapping(tmp_path / "m2.yaml")


def test_view_url_slug_derivation() -> None:
    """A view's .aspx name is fixed at creation, so views are created with a
    URL-safe slug title and renamed to the declared title afterwards (same
    trick as field internal/display names)."""
    from dbml_sharepoint.model.mapping_loader import view_url_slug

    assert view_url_slug("Open by score") == "OpenByScore"
    assert view_url_slug("Resolved or closed") == "ResolvedOrClosed"
    assert view_url_slug("ERM review") == "ERMReview"
    assert view_url_slug("Everything") == "Everything"
    assert view_url_slug("A+B") == "AB"
    assert view_url_slug("!!!") == ""


# --- Display names ----------------------------------------------------------


def test_display_names_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "display_names:\n"
            "  mode: auto\n"
            "  overrides:\n"
            "    Project:\n"
            '      RiskManReference: "RiskMan Reference"\n',
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.display_name_mode == "auto"
    assert bundle.mapping.display_name_overrides == {
        "Project": {"RiskManReference": "RiskMan Reference"},
    }


def test_display_names_absent_defaults_off() -> None:
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert bundle.mapping.display_name_mode is None
    assert bundle.mapping.display_name_overrides == {}


def test_display_names_unknown_mode_rejected(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml("display_names:\n  mode: fancy\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="auto"):
        load_mapping(tmp_path / "m.yaml")


def test_auto_display_name_splits_pascal_case() -> None:
    from dbml_sharepoint.model.mapping_loader import auto_display_name

    cases = {
        "ResidualRiskRating": "Residual Risk Rating",
        "ToleranceEndDate": "Tolerance End Date",
        "RiskIDNumber": "Risk ID Number",   # acronym run keeps its last capital
        "DueDate": "Due Date",
        "Status": "Status",                 # single word unchanged
        "Take5Assessment": "Take5 Assessment",  # digit→upper boundary
    }
    for internal, display in cases.items():
        assert auto_display_name(internal) == display, internal


# --- Column formatting ------------------------------------------------------


def test_column_formatting_inline_and_path(tmp_path: Path) -> None:
    (tmp_path / "pill.json").write_text(
        '{"elmType": "div", "txtContent": "@currentField"}', encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "column_formatting:\n"
            "  Project:\n"
            "    Status: pill.json\n"
            "    SortOrder: { elmType: span }\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    formatting = bundle.mapping.column_formatting["Project"]
    assert formatting["Status"] == {"elmType": "div", "txtContent": "@currentField"}
    assert formatting["SortOrder"] == {"elmType": "span"}


def test_column_formatting_absent_defaults_empty() -> None:
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert bundle.mapping.column_formatting == {}


def test_column_formatting_bad_path_and_bad_json(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "m.yaml").write_text(
        _views_yaml("column_formatting:\n  Project:\n    Status: missing.json\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"missing\.json"):
        load_mapping(tmp_path / "m.yaml")

    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "m2.yaml").write_text(
        _views_yaml("column_formatting:\n  Project:\n    Status: bad.json\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"bad\.json"):
        load_mapping(tmp_path / "m2.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml("column_formatting:\n  Project:\n    Status: 42\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Status"):
        load_mapping(tmp_path / "m3.yaml")


def test_view_formatting_parsed_inline_and_path(tmp_path: Path) -> None:
    (tmp_path / "row.json").write_text('{"additionalRowClass": "x"}', encoding="utf-8")
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: A\n"
            "      fields: [Title]\n"
            "      formatting: row.json\n"
            "    - title: B\n"
            "      fields: [Title]\n"
            "      formatting: { additionalRowClass: y }\n"
            "    - title: C\n"
            "      fields: [Title]\n",
        ),
        encoding="utf-8",
    )
    views = load_mapping(tmp_path / "m.yaml").mapping.views["Project"]
    assert views[0].formatting == {"additionalRowClass": "x"}
    assert views[1].formatting == {"additionalRowClass": "y"}
    assert views[2].formatting is None


def test_form_formatting_parsed_and_requires_a_part(tmp_path: Path) -> None:
    (tmp_path / "body.json").write_text(
        '{"sections": [{"displayname": "Core", "fields": ["Title"]}]}',
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "form_formatting:\n"
            "  Project:\n"
            "    body: body.json\n"
            "    header: { elmType: div }\n",
        ),
        encoding="utf-8",
    )
    form = load_mapping(tmp_path / "m.yaml").mapping.form_formatting["Project"]
    assert form.body == {"sections": [{"displayname": "Core", "fields": ["Title"]}]}
    assert form.header == {"elmType": "div"}
    assert form.footer is None

    (tmp_path / "m2.yaml").write_text(
        _views_yaml("form_formatting:\n  Project: {}\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least one"):
        load_mapping(tmp_path / "m2.yaml")


def test_form_formatting_absent_defaults_empty() -> None:
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert bundle.mapping.form_formatting == {}


def test_list_validation_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_validation:\n"
            "  Project:\n"
            "    when:\n"
            "      any_of:\n"
            "        - none_of:\n"
            "            - { field: Status, op: eq, value: Closed }\n"
            "        - { field: Title, op: is_not_null }\n"
            "    message: Closing needs a title.\n",
        ),
        encoding="utf-8",
    )
    rule = load_mapping(tmp_path / "m.yaml").mapping.list_validation["Project"]
    assert rule.when is not None
    assert rule.message == "Closing needs a title."

    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            "list_validation:\n  Project:\n"
            "    when:\n      - { field: Title, op: is_not_null }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="message"):
        load_mapping(tmp_path / "m2.yaml")



# --- Nested unknown keys ----------------------------------------------------
#
# The top-level guard covers exactly one level. Every case below was
# verified fail-open: a typo'd build was byte-identical to one with the key
# deleted, and reported zero findings.


def test_entity_sub_keys_are_checked(tmp_path: Path) -> None:
    """`display_colum` — one character — silently fell back to
    LookupField: "Title", so every lookup into that list renders blank. The
    validator has a dedicated guard for exactly that, and it never fired
    because the key was never seen."""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Membership: { kind: List, base_template: 100, site_role: default, "
        "display_colum: DisplayName }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"entities\.Membership") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "display_colum" in str(err.value)


def test_versioning_sub_keys_are_checked(tmp_path: Path) -> None:
    """A typo'd `enable_versioning: false` deploys versioning ON — the
    opposite of the declaration, on a list the author meant to keep flat."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml("versioning:\n  default:\n    enable_versionin: false\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"versioning\.default") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "enable_versionin" in str(err.value)

    (tmp_path / "m2.yaml").write_text(
        _views_yaml("versioning:\n  overides:\n    Project: {}\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="overides"):
        load_mapping(tmp_path / "m2.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml(
            "versioning:\n  overrides:\n    Project:\n      enable_versionin: false\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"versioning\.overrides\.Project"):
        load_mapping(tmp_path / "m3.yaml")


def test_view_sub_keys_are_checked(tmp_path: Path) -> None:
    """`deafult` never becomes the default view; a filter under `wheres:`
    deploys an UNFILTERED view, which is the one that leaks rows."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            "      deafult: true\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deafult"):
        load_mapping(tmp_path / "m.yaml")

    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            "      wheres:\n"
            "        - { field: Status, op: neq, value: Closed }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wheres"):
        load_mapping(tmp_path / "m2.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            "      sort:\n"
            "        - { field: Title, dirction: desc }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="dirction"):
        load_mapping(tmp_path / "m3.yaml")

    (tmp_path / "m4.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            "      group_by: { field: Status, colapsed: true }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="colapsed"):
        load_mapping(tmp_path / "m4.yaml")


def test_group_sub_keys_are_checked(tmp_path: Path) -> None:
    """A misspelled `require_empty_at_deploy` disables the clean-provision
    gate — the check that proves a reconciled group has no members before
    list creation."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "groups:\n"
            "  - name: Register Editors\n"
            "    require_empty_at_deployy: true\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"groups\[0\]") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "require_empty_at_deployy" in str(err.value)


def test_permission_level_sub_keys_are_checked(tmp_path: Path) -> None:
    """A misspelled `base_permissions` yields a custom level with NO bits —
    created, granted, and permitting nothing."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "permission_levels:\n"
            "  - name: Contribute No Delete\n"
            "    base_permission: [ViewListItems]\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="base_permission"):
        load_mapping(tmp_path / "m.yaml")


def test_list_permissions_sub_keys_are_checked(tmp_path: Path) -> None:
    """A typo in a policy degrades the list to inherited permissions with
    an empty allowlist — the fail-open direction on the security surface."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  default:\n"
            "    break_inheritence: true\n"
            "    assignments: []\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="break_inheritence"):
        load_mapping(tmp_path / "m.yaml")

    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  defualt:\n"
            "    break_inheritance: true\n"
            "    assignments: []\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="defualt"):
        load_mapping(tmp_path / "m2.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  default:\n"
            "    break_inheritance: true\n"
            "    assignments:\n"
            "      - principal: { kind: group, nmae: Register Editors }\n"
            "        level: Contribute\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nmae"):
        load_mapping(tmp_path / "m3.yaml")

    (tmp_path / "m4.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  default:\n"
            "    break_inheritance: true\n"
            "    assignments:\n"
            "      - principal: { kind: associated_owner_group }\n"
            "        levl: Contribute\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="levl"):
        load_mapping(tmp_path / "m4.yaml")


def test_demo_item_sub_keys_are_checked(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "demo_items:\n"
            "  Project:\n"
            "    - key: p1\n"
            "      values: { Title: '[DEMO] x' }\n"
            "      colums: [Title]\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"demo_items\.Project\[0\]") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "colums" in str(err.value)


def test_watched_lists_and_polymorphic_patterns_are_checked(tmp_path: Path) -> None:
    """Neither section is validated anywhere downstream, so a typo'd key
    was simply dropped. (The entity and column NAMES are checked against
    the schema in the validator, alongside every other section's.)"""
    (tmp_path / "m.yaml").write_text(
        _views_yaml("watched_lists:\n  - { entity: Project, colum: Status }\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="colum"):
        load_mapping(tmp_path / "m.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml(
            "polymorphic_patterns:\n"
            "  - { list: Project, field: EntityId, discriminater: EntityType }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="discriminater"):
        load_mapping(tmp_path / "m3.yaml")

    (tmp_path / "m4.yaml").write_text(
        _views_yaml(
            "cross_site_reference_columns:\n  - { entity: Project, colmn: OrgUnit }\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="colmn"):
        load_mapping(tmp_path / "m4.yaml")


def test_display_names_sub_keys_are_checked(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml("display_names:\n  mode: auto\n  overides:\n    Project: {}\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="overides"):
        load_mapping(tmp_path / "m.yaml")


# --- The top-level allow-list -----------------------------------------------


def test_unknown_top_level_section_is_a_load_error(tmp_path: Path) -> None:
    """The guard itself had no test. A misspelled section used to be
    ignored outright: `form_visibilty:` built clean, the manifest reported
    "(none declared)" and nothing deployed."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml("form_visibilty:\n  Project:\n    columns: {}\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown mapping section") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "form_visibilty" in str(err.value)


def test_documented_permissions_block_is_rejected_not_ignored(tmp_path: Path) -> None:
    """`permissions:` was allow-listed and never read. A build of the
    documented block was byte-identical to a mapping with no permissions at
    all: no group, no level, no broken inheritance, no allowlist
    reconciliation — and a green build. The reader lives at the top level,
    under permission_levels / groups / list_permissions."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "permissions:\n"
            "  levels:\n"
            '    - name: "Contribute No Delete"\n'
            "      base_permissions: [ViewListItems, AddListItems]\n"
            "  groups:\n"
            '    - name: "Register Editors"\n'
            "  default_policy:\n"
            "    break_inheritance: true\n"
            "    reconcile: exact\n"
            "    assignments: []\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown mapping section") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "permissions" in str(err.value)


def test_documented_retention_policies_block_is_rejected_not_ignored(tmp_path: Path) -> None:
    """Same shape as `permissions:` — allow-listed, never read. Policies are
    loaded from the file named by `retention_policies_source`."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "retention_policies:\n"
            "  Standard7Y:\n"
            "    sp_label: Standard 7 Year\n"
            "    retain_years: 7\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown mapping section") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "retention_policies" in str(err.value)


_TOP_LEVEL_READERS = ("load_mapping", "_parse_permissions")


def _sections_read_by_the_loader() -> set[str]:
    """Every top-level mapping key the loader actually reads, derived from
    the loader's own source.

    Derived rather than restated, because restating it is how two dead keys
    got whitelisted: KNOWN_SECTIONS was populated by reading the reference
    docs, and neither `permissions:` nor `retention_policies:` has ever had
    a reader.
    """
    tree = ast.parse(inspect.getsource(mapping_loader))
    keys: set[str] = set(mapping_loader._REMOVED_SECTIONS)
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef) or func.name not in _TOP_LEVEL_READERS:
            continue
        for node in ast.walk(func):
            # raw["key"]
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == "raw"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                keys.add(node.slice.value)
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            # raw.get("key")
            if (
                isinstance(called, ast.Attribute)
                and isinstance(called.value, ast.Name)
                and called.value.id == "raw"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
            # helper(raw, "key", ...) — _optional_bool and friends
            if (
                len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "raw"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                keys.add(node.args[1].value)
    return keys


def test_every_allow_listed_section_has_a_reader() -> None:
    """KNOWN_SECTIONS is an admission gate, so an entry with no reader is
    worse than no gate: it makes a section that deploys nothing look
    supported. `permissions:` and `retention_policies:` were both
    allow-listed from the reference docs and read by nothing."""
    read = _sections_read_by_the_loader()
    # Sanity: the derivation must actually find the loader's readers.
    assert {"prefix", "entities", "form_visibility", "list_permissions"} <= read
    orphans = mapping_loader.KNOWN_SECTIONS - read
    assert not orphans, (
        f"allow-listed with no reader: {sorted(orphans)} — either wire a reader "
        f"or drop the entry; an allow-listed key that nothing reads deploys nothing"
    )


def test_hardening_flags_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml("seal_columns: true\nprevent_list_deletion: true\n"),
        encoding="utf-8",
    )
    mapping = load_mapping(tmp_path / "m.yaml").mapping
    assert mapping.seal_columns is True
    assert mapping.prevent_list_deletion is True
    off = load_mapping(FIXTURES / "calculated-mapping.yaml").mapping
    assert off.seal_columns is False
    assert off.prevent_list_deletion is False




# --- Quoted booleans --------------------------------------------------------
#
# `bool("false")` is True. Every site below read the value with bool()
# BEFORE the guard that tests it, so the cautious spelling — a quoted YAML
# boolean — silently meant its opposite and the guard never fired.


def test_quoted_break_inheritance_is_rejected_not_inverted(tmp_path: Path) -> None:
    """The worst instance. `break_inheritance: "false"` coerced to True, so
    the guard that refuses `reconcile: exact` on an inherited ACL tested
    the COERCED value and passed. deploy.js then called
    breakroleinheritance(copyRoleAssignments=false), dropping every
    inherited grant, and exact reconciliation removed every non-declared
    role binding. The author declared the opposite of what deployed, and
    the build reported no findings."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  default:\n"
            '    break_inheritance: "false"\n'
            "    reconcile: exact\n"
            "    assignments: []\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="break_inheritance"):
        load_mapping(tmp_path / "m.yaml")


def test_quoted_group_flags_are_rejected(tmp_path: Path) -> None:
    """These fail OPEN: a quoted "false" on allow_members_edit_membership
    grants members the right to change the group's membership."""
    for flag in (
        "allow_members_edit_membership",
        "allow_request_to_join_leave",
        "auto_accept_request_to_join_leave",
        "only_allow_members_view_membership",
    ):
        (tmp_path / "m.yaml").write_text(
            _views_yaml(f'groups:\n  - name: Editors\n    {flag}: "false"\n'),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=flag):
            load_mapping(tmp_path / "m.yaml")


def test_quoted_versioning_flags_are_rejected(tmp_path: Path) -> None:
    """A quoted "false" deploys versioning ON — and the override path
    reaches jsgen as a raw dict, so nothing checked it at all."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml('versioning:\n  default:\n    enable_versioning: "false"\n'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="enable_versioning"):
        load_mapping(tmp_path / "m.yaml")

    (tmp_path / "m2.yaml").write_text(
        _views_yaml(
            'versioning:\n  overrides:\n    Project:\n      enable_versioning: "false"\n',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"versioning\.overrides\.Project"):
        load_mapping(tmp_path / "m2.yaml")

    (tmp_path / "m3.yaml").write_text(
        _views_yaml("versioning:\n  overrides:\n    Project:\n      major_version_limit: many\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="major_version_limit"):
        load_mapping(tmp_path / "m3.yaml")


def test_quoted_view_default_is_rejected(tmp_path: Path) -> None:
    """`default: "false"` coerced to True and stole the list's default
    view — the one every link into the list lands on."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            '      default: "false"\n',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="default"):
        load_mapping(tmp_path / "m.yaml")


def test_quoted_group_by_collapsed_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "views:\n"
            "  Project:\n"
            "    - title: Open\n"
            "      fields: [Title]\n"
            '      group_by: { field: Status, collapsed: "false" }\n',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="collapsed"):
        load_mapping(tmp_path / "m.yaml")


def test_quoted_singleton_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        '  Project: { kind: List, base_template: 100, site_role: default, singleton: "false" }\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="singleton"):
        load_mapping(tmp_path / "m.yaml")


# --- Migration messages -----------------------------------------------------


def _example_from(message: str) -> str:
    """The indented YAML block a migration error offers as the replacement."""
    lines = [ln[4:] for ln in message.splitlines() if ln.startswith("    ")]
    assert lines, f"no example block in: {message}"
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("removed", ["hidden_on_forms", "hidden_on_display"])
def test_removed_section_message_offers_an_example_that_loads(
    tmp_path: Path, removed: str,
) -> None:
    """An error that names a replacement is only useful if the replacement
    parses. The `hidden_on_forms` message offered `Column: hidden` without
    the mandatory `columns:` level, so an author who followed it verbatim
    hit a second error."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(f"{removed}:\n  Project: [Status]\n"), encoding="utf-8",
    )
    with pytest.raises(ValueError) as err:
        load_mapping(tmp_path / "m.yaml")
    example = _example_from(str(err.value))
    assert "columns:" in example
    (tmp_path / "fixed.yaml").write_text(
        _views_yaml(example.replace("<Entity>", "Project").replace("<Column>", "Status")),
        encoding="utf-8",
    )
    mapping = load_mapping(tmp_path / "fixed.yaml").mapping
    assert mapping.form_visibility["Project"].columns["Status"].new is False


def test_list_validation_formula_message_offers_an_example_that_loads(
    tmp_path: Path,
) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_validation:\n"
            "  Project:\n"
            '    formula: \'=[Status]<>""\'\n'
            "    message: Needs a status.\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as err:
        load_mapping(tmp_path / "m.yaml")
    example = _example_from(str(err.value))
    (tmp_path / "fixed.yaml").write_text(
        _views_yaml(example.replace("<Entity>", "Project").replace("<Column>", "Status")),
        encoding="utf-8",
    )
    rule = load_mapping(tmp_path / "fixed.yaml").mapping.list_validation["Project"]
    assert rule.message


def test_site_role_on_a_permission_override_is_rejected(tmp_path: Path) -> None:
    """`site_role` scopes the DEFAULT policy — which entities it applies to
    — and is read only there. On an override it was parsed and silently
    discarded, so an author who had seen it work on the default reasonably
    expected it to narrow an override too, and got a list that was not
    scoped at all. On the security surface, believing a policy is scoped
    when it is not is the wrong direction to be wrong in.

    Rejected rather than implemented: an override is already per-entity, so
    a site-role scope on one is either redundant or contradicts the entity
    it is keyed by."""
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  overrides:\n"
            "    Project:\n"
            "      break_inheritance: true\n"
            "      site_role: default\n"
            "      assignments: []\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="site_role") as err:
        load_mapping(tmp_path / "m.yaml")
    assert "list_permissions.overrides.Project" in str(err.value)


def test_site_role_on_the_default_policy_is_still_accepted(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml(
            "list_permissions:\n"
            "  default:\n"
            "    break_inheritance: true\n"
            "    site_role: default\n"
            "    assignments: []\n",
        ),
        encoding="utf-8",
    )
    perms = load_mapping(tmp_path / "m.yaml").mapping.permissions
    assert perms is not None
    assert perms.default_policy_site_role == "default"


# --- Retired columns and field sets ------------------------------------------


def _board_yaml(block: str) -> str:
    return (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        + block
    )


def test_retired_columns_parse_both_declaration_forms(tmp_path: Path) -> None:
    """The full mapping form carries the lifecycle facts; the bare list is
    the minimal case. An unquoted YAML date scalar must normalise to ISO
    text, not leak a datetime.date into the mapping."""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "  Escalation: { kind: List, base_template: 100, site_role: default }\n"
        "retired_columns:\n"
        "  Board:\n"
        "    OperationsStatus:\n"
        "      retired: 2026-09-01\n"
        "      superseded_by: SiteServicesStatus\n"
        '      reason: "Merged into Site Services at the September review"\n'
        "      hide_existing: true\n"
        "  Escalation: [LegacyRoute]\n",
        encoding="utf-8",
    )

    mapping = load_mapping(tmp_path / "m.yaml").mapping

    ops = mapping.retired_columns["Board"]["OperationsStatus"]
    assert ops.column == "OperationsStatus"
    assert ops.retired == "2026-09-01"
    assert ops.superseded_by == "SiteServicesStatus"
    assert ops.reason == "Merged into Site Services at the September review"
    assert ops.hide_existing is True
    assert mapping.retired_columns["Escalation"]["LegacyRoute"] == RetiredColumn(
        column="LegacyRoute",
    )
    assert mapping.is_retired("Board", "OperationsStatus") is True
    assert mapping.is_retired("Board", "SiteServicesStatus") is False
    assert mapping.is_retired("Nope", "Anything") is False


def test_retired_columns_reject_malformed_declarations(tmp_path: Path) -> None:
    """Structural mistakes fail at load with a message naming the exact
    declaration — the same fail-closed contract as every other section."""
    header = _board_yaml("retired_columns:\n  Board:\n")
    (tmp_path / "no-date.yaml").write_text(
        header + '    OperationsStatus:\n      reason: "gone"\n', encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"retired_columns\.Board\.OperationsStatus"):
        load_mapping(tmp_path / "no-date.yaml")

    (tmp_path / "unknown-key.yaml").write_text(
        header + "    OperationsStatus:\n      retired: 2026-09-01\n      when: soon\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown key"):
        load_mapping(tmp_path / "unknown-key.yaml")

    (tmp_path / "bad-bool.yaml").write_text(
        header
        + "    OperationsStatus:\n      retired: 2026-09-01\n      hide_existing: yep\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hide_existing must be a boolean"):
        load_mapping(tmp_path / "bad-bool.yaml")

    (tmp_path / "bad-list.yaml").write_text(
        _board_yaml("retired_columns:\n  Board: [123]\n"), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bare-list entries must be column names"):
        load_mapping(tmp_path / "bad-list.yaml")


def test_apply_retirement_folds_into_every_target_structure(tmp_path: Path) -> None:
    """Retirement adds no deploy-time capability: it resolves into the
    structures deploy.js already implements. The calculated column (Route)
    is the carve-out — it must NEVER reach form_visibility, which the
    validator rejects for calculated columns."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "display_names:\n"
            "  mode: auto\n"
            "  overrides:\n"
            "    Board:\n"
            '      OperationsNote: "Ops commentary"\n'
            "calculated_formulas:\n"
            "  Board:\n"
            "    Route: '=[BoardDate]'\n"
            "views:\n"
            "  Board:\n"
            '    - title: "Last 14 days"\n'
            "      fields: [BoardDate, OperationsStatus, SiteServicesStatus]\n"
            "      widths: { OperationsStatus: 120, BoardDate: 140 }\n"
            "retired_columns:\n"
            "  Board:\n"
            "    OperationsStatus:\n"
            "      retired: 2026-09-01\n"
            "      superseded_by: SiteServicesStatus\n"
            "    OperationsNote:\n"
            "      retired: 2026-09-01\n"
            "      hide_existing: true\n"
            "    Route:\n"
            "      retired: 2026-09-01\n",
        ),
        encoding="utf-8",
    )

    mapping = load_mapping(tmp_path / "m.yaml").mapping

    # 1. form_visibility — hidden from the New form, but never the
    #    calculated column, and `declared` so retiring one column does not
    #    start clearing formulas on every other column of the list.
    section = mapping.form_visibility["Board"]
    assert section.reconcile == "declared"
    assert section.columns["OperationsStatus"] == FormVisibility(new=False, existing=True)
    # 2. hide_existing additionally hides it from Edit — and so from Display.
    assert section.columns["OperationsNote"] == FormVisibility(new=False, existing=False)
    assert "Route" not in section.columns
    # 3. The suffix composes with the auto name AND with an explicit override.
    assert mapping.display_name_for("Board", "OperationsStatus") == (
        "Operations Status (retired)"
    )
    assert mapping.display_name_for("Board", "OperationsNote") == (
        "Ops commentary (retired)"
    )
    assert mapping.display_name_for("Board", "Route") == "Route (retired)"
    # 4. Views lose the retired column from fields and from widths.
    view = mapping.views["Board"][0]
    assert view.fields == ["BoardDate", "SiteServicesStatus"]
    assert view.widths == {"BoardDate": 140}
    # ...and each removal is recorded for the validator to warn from.
    assert [(s.column, s.context) for s in mapping.retirement_strips] == [
        ("OperationsStatus", "views[Board].Last 14 days fields"),
        ("OperationsStatus", "views[Board].Last 14 days widths"),
    ]
    # The authoritative record survives the fold.
    assert mapping.retired_columns["Board"]["OperationsStatus"].superseded_by == (
        "SiteServicesStatus"
    )


def test_apply_retirement_replaces_a_declared_form_visibility_entry(
    tmp_path: Path,
) -> None:
    """Retirement owns a retired column's form behaviour outright. A
    hand-written declaration is replaced rather than merged — a `when`
    predicate on a column nobody may enter is unreachable, and merging
    would leave the author's `existing: true` fighting hide_existing. The
    replacement is recorded so the validator can say so.
    """
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "form_visibility:\n"
            "  Board:\n"
            "    reconcile: exact\n"
            "    columns:\n"
            "      OperationsStatus:\n"
            "        new: true\n"
            "        existing: true\n"
            "        when:\n"
            "          - { field: BoardDate, op: is_not_null }\n"
            "      Chair: hidden\n"
            "retired_columns:\n"
            "  Board:\n"
            "    OperationsStatus:\n"
            "      retired: 2026-09-01\n",
        ),
        encoding="utf-8",
    )

    mapping = load_mapping(tmp_path / "m.yaml").mapping

    section = mapping.form_visibility["Board"]
    # The author's reconcile mode is theirs; retirement does not change it.
    assert section.reconcile == "exact"
    assert section.columns["OperationsStatus"] == FormVisibility(new=False, existing=True)
    # An unrelated declaration is untouched.
    assert section.columns["Chair"] == FormVisibility(new=False, existing=False)
    assert [(s.column, s.context) for s in mapping.retirement_strips] == [
        ("OperationsStatus", "form_visibility[Board].columns"),
    ]


def test_apply_retirement_strips_retired_fields_from_form_sections(
    tmp_path: Path,
) -> None:
    """Retirement's contract is that the column leaves the entry
    experience. A body section that still lists a retired field would rely
    on SharePoint honouring a hiding formula over an explicit section
    placement — an interaction untested against live SharePoint, and an
    inconsistency next to the view and widths strips.

    Only sections[].fields is touched: it is the one shape in the formatter
    JSON with a known meaning and the one the validator already walks.
    Every other key is left exactly as authored, and a section left with an
    empty fields list is KEPT — an empty section is the author's layout to
    clean up, and dropping it would be a second-order rewrite of their JSON.
    """
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "form_formatting:\n"
            "  Board:\n"
            "    body:\n"
            "      sections:\n"
            '        - displayname: "Header"\n'
            "          fields: [BoardDate, OperationsStatus]\n"
            '        - displayname: "Streams"\n'
            "          fields: [OperationsStatus]\n"
            "      unrelatedKey:\n"
            '        nested: "left exactly as authored"\n'
            "retired_columns:\n"
            "  Board:\n"
            "    OperationsStatus:\n"
            "      retired: 2026-09-01\n",
        ),
        encoding="utf-8",
    )

    mapping = load_mapping(tmp_path / "m.yaml").mapping

    body = mapping.form_formatting["Board"].body
    assert body is not None
    # The retired field is gone; its live sibling survives, in place.
    assert body["sections"][0] == {"displayname": "Header", "fields": ["BoardDate"]}
    # A section left with no fields is KEPT, not dropped.
    assert body["sections"][1] == {"displayname": "Streams", "fields": []}
    # Nothing else in the formatter JSON is rewritten.
    assert body["unrelatedKey"] == {"nested": "left exactly as authored"}
    # Recorded once — a column listed under two sections is one retirement.
    assert [
        (s.column, s.context) for s in mapping.retirement_strips
        if "form_formatting" in s.context
    ] == [("OperationsStatus", "form_formatting[Board].body sections")]


def test_field_sets_section_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    header:   [BoardDate, Chair]\n"
            "    statuses: [OperationsStatus, WorkforceStatus]\n",
        ),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.field_sets == {
        "Board": {
            "header": ["BoardDate", "Chair"],
            "statuses": ["OperationsStatus", "WorkforceStatus"],
        },
    }


def test_field_sets_absent_defaults_empty(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(_board_yaml(""), encoding="utf-8")
    assert load_mapping(tmp_path / "m.yaml").mapping.field_sets == {}


def test_field_sets_entity_block_must_be_a_mapping(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _board_yaml("field_sets:\n  Board: [BoardDate, Chair]\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"field_sets\.Board"):
        load_mapping(tmp_path / "m.yaml")


def test_field_set_must_be_a_list_of_column_names(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _board_yaml("field_sets:\n  Board:\n    header: BoardDate\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"field_sets\.Board\.header"):
        load_mapping(tmp_path / "m.yaml")


def test_view_fields_expand_field_sets_in_declaration_order(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    header:   [BoardDate, Chair]\n"
            "    statuses: [OperationsStatus, WorkforceStatus]\n"
            "views:\n"
            "  Board:\n"
            "    - title: Heat grid\n"
            '      fields: ["@header", "@statuses"]\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == [
        "BoardDate", "Chair", "OperationsStatus", "WorkforceStatus",
    ]
    assert view.expanded_sets == ["header", "statuses"]


def test_field_set_expansion_dedupes_keeping_first_position(tmp_path: Path) -> None:
    """["@header", BoardDate] is a no-op, not an error: the spec removes
    duplicates keeping FIRST position, so BoardDate stays where the set put
    it rather than moving to the end."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    header: [BoardDate, Chair]\n"
            "    audit:  [Chair, OverallStatus]\n"
            "views:\n"
            "  Board:\n"
            "    - title: Today\n"
            '      fields: ["@header", BoardDate, "@audit", "@header"]\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["BoardDate", "Chair", "OverallStatus"]
    assert view.expanded_sets == ["header", "audit"]


def test_field_sets_do_not_nest(tmp_path: Path) -> None:
    """One level only, deliberately: a member that looks like a reference is
    left literal, which the validator then reports as an unresolved set."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            '    outer: ["@inner", BoardDate]\n'
            "    inner: [Chair]\n"
            "views:\n"
            "  Board:\n"
            "    - title: Nested\n"
            '      fields: ["@outer"]\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["@inner", "BoardDate"]
    assert view.expanded_sets == ["outer"]


def test_unresolved_field_set_reference_is_left_in_place(tmp_path: Path) -> None:
    """Nothing is silently dropped: the validator names the bad reference and
    cli.py aborts before jsgen is ever reached."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    header: [BoardDate]\n"
            "views:\n"
            "  Board:\n"
            "    - title: Typo\n"
            '      fields: ["@headr", Chair]\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["@headr", "Chair"]
    assert view.expanded_sets == []


def test_field_set_expansion_applies_to_fields_only(tmp_path: Path) -> None:
    """widths, sort, group_by and where name columns directly; a set has no
    meaningful expansion there, so an '@' entry stays literal."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    header: [BoardDate, Chair]\n"
            "views:\n"
            "  Board:\n"
            "    - title: Literal elsewhere\n"
            '      fields: ["@header"]\n'
            "      sort:\n"
            '        - { field: "@header", direction: asc }\n'
            '      group_by: { field: "@header" }\n'
            "      where:\n"
            '        - { field: "@header", op: is_null }\n'
            "      widths:\n"
            '        "@header": 120\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["BoardDate", "Chair"]
    assert view.sort[0].field == "@header"
    assert view.group_by is not None
    assert view.group_by.field == "@header"
    assert view.widths == {"@header": 120}


def test_views_without_field_sets_are_unchanged(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "views:\n"
            "  Board:\n"
            "    - title: Plain\n"
            "      fields: [BoardDate, Chair]\n",
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["BoardDate", "Chair"]
    assert view.expanded_sets == []


def test_field_sets_expand_before_retirement_filters_them(tmp_path: Path) -> None:
    """Expansion must run BEFORE _apply_retirement, so retirement filters the
    already-expanded list. If the order inverted, "@statuses" would survive
    retirement untouched and WorkforceStatus would still be a view field."""
    (tmp_path / "m.yaml").write_text(
        _board_yaml(
            "field_sets:\n"
            "  Board:\n"
            "    statuses: [OperationsStatus, WorkforceStatus]\n"
            "retired_columns:\n"
            "  Board:\n"
            "    WorkforceStatus:\n"
            '      retired: "2026-09-01"\n'
            "views:\n"
            "  Board:\n"
            "    - title: Heat grid\n"
            '      fields: ["@statuses"]\n',
        ),
        encoding="utf-8",
    )
    view = load_mapping(tmp_path / "m.yaml").mapping.views["Board"][0]
    assert view.fields == ["OperationsStatus"]
    assert view.expanded_sets == ["statuses"]
