# test/test_mapping_loader.py
from pathlib import Path

import pytest

from dbml_sharepoint.model.mapping_loader import ListPermissionPolicy, load_mapping


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
    from dbml_sharepoint.model.mapping_loader import ViewCondition, ViewGroupBy, ViewSort

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
    assert view.where == [ViewCondition(field="Status", op="neq", value="Closed")]
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
    assert view.where == []
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
            "    formula: '=IF([Status]==\"Closed\",NOT(ISBLANK([Title])),TRUE)'\n"
            "    message: Closing needs a title.\n",
        ),
        encoding="utf-8",
    )
    rule = load_mapping(tmp_path / "m.yaml").mapping.list_validation["Project"]
    assert rule.formula.startswith("=IF")
    assert rule.message == "Closing needs a title."

    (tmp_path / "m2.yaml").write_text(
        _views_yaml("list_validation:\n  Project:\n    formula: '=TRUE'\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="message"):
        load_mapping(tmp_path / "m2.yaml")


def test_hidden_on_forms_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml("hidden_on_forms:\n  Project: [SortOrder, Status]\n"),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.hidden_on_forms == {"Project": ["SortOrder", "Status"]}
    assert load_mapping(FIXTURES / "calculated-mapping.yaml").mapping.hidden_on_forms == {}


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


def test_hidden_on_display_parsed(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        _views_yaml("hidden_on_display:\n  Project: [SortOrder]\n"),
        encoding="utf-8",
    )
    bundle = load_mapping(tmp_path / "m.yaml")
    assert bundle.mapping.hidden_on_display == {"Project": ["SortOrder"]}
    assert load_mapping(FIXTURES / "calculated-mapping.yaml").mapping.hidden_on_display == {}
