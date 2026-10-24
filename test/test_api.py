"""`dbml_sharepoint.api` is the one surface dependents import from.

The surface is pinned by name, so removing one is a visible, breaking change.
The dependent contract in its docstring is run against a seeded package, so
the text a dependent copies is the text that is proved.
"""

import os
import pkgutil
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import dbml_sharepoint
from dbml_sharepoint import api

#: Written out rather than read from `api`: removing a name is a breaking change for dependents.
API_SURFACE = frozenset({
    # jsonvalue
    "JsonValue", "JsonObject", "JsonMap", "is_text_keyed", "is_object_list", "is_json_value",
    "as_json_object", "as_json", "loads_json", "loads_object", "as_object", "text_at",
    "opt_text", "int_at", "object_at", "rows_at", "ensure_object",
    # model.yamlio
    "safe_load", "safe_dump", "RefusedYAMLError", "TagOrDirectiveError", "PARSE_ERRORS",
    # naming
    "slug", "kebab", "file_stem",
    # analysis.list_url
    "list_url_key", "list_url_path", "list_folder",
    # model.mapping_types
    "view_url_slug", "auto_display_name", "title_display_name", "Mapping", "MappingBundle",
    "ViewDef", "WatchOn", "WatchUse", "WatchedList", "ListPermissionPolicy", "Principal",
    "DemoItem", "RETIRED_SUFFIX",
    # model.prefix
    "expand_prefix", "prefix_stem",
    # analysis.timezones
    "ZoneTable", "zone_table", "transitions", "is_known_zone", "unknown_zone_message",
    "WINDOW_START", "WINDOW_END",
    # jsrest
    "prelude", "wrap",
    # model.parser
    "parse_dbml", "Schema", "Table", "Column",
    # model.mapping_loader
    "load_mapping",
    # model.conditions
    "Condition", "Group", "Leaf",
    # model.release
    "Release", "load_release",
    # model.identities
    "IdentityError", "IdentityValue", "NAME_PATTERN", "identity_hash", "parse_values",
    # model.errors
    "MappingValueError",
    # model.form_tree
    "Banner",
    # catalogue
    "load_solution", "UnknownSolutionError", "MAPPING_RELPATH", "RELEASE_RELPATH",
    "SCHEMA_RELPATH",
    # project
    "CONFIG_ERRORS", "load_config", "resolve_identities",
    # pipeline
    "execute_build",
    # templating
    "script_env",
    # analysis.resolve
    "resolve",
    # analysis.typemap
    "map_column", "FIELD_KIND_BY_TYPE_KIND", "DATE_TYPES", "is_hyperlink", "is_person",
    # analysis.report_columns
    "DATE_ZONE_RESOLVED_COLUMN", "ITEM_URL_COLUMN", "ITEM_URL_RESOLVED_COLUMN",
    "REPORT_FIXED_COLUMNS", "REPORT_KEY_SUFFIX", "REPORT_SYSTEM_COLUMNS", "fk_key_column",
    "person_key_column", "projection_output_name",
    # analysis.reporting.plan
    "ListPlan", "build_plans", "report_column_names", "reads_zone",
    # analysis.reporting.dictionary
    "dictionary_rows", "metadata_rows", "DictionaryRow", "LOADABLE_COLUMNS", "USERS_COLUMNS",
    # analysis.condition_rendering
    "NEGATION",
    # analysis.demo_marker
    "DEMO_TITLE_PREFIX",
    # generators.report_m
    "generate_dictionary_powerquery", "generate_powerquery",
})


def test_the_api_surface_is_the_pinned_one() -> None:
    assert frozenset(api.__all__) == API_SURFACE
    assert len(api.__all__) == len(API_SURFACE), "a name is listed twice in `__all__`"


def test_every_api_name_is_public_and_resolves() -> None:
    assert all(
        not name.startswith("_") and getattr(api, name) is not None for name in api.__all__
    )


def test_the_dependent_contract_names_every_module_but_api_and_testing() -> None:
    top = {m.name for m in pkgutil.iter_modules(dbml_sharepoint.__path__)}
    assert set(api.DEPENDENT_PROTECTED_MODULES) == {
        f"dbml_sharepoint.{n}" for n in top - {"api", "testing"}
    }


def _dependent_contract() -> str:
    """The docstring's contract, with its two placeholders filled in for a seeded package."""
    block = re.search(r"```toml\n(.*?)```", api.__doc__ or "", re.DOTALL)
    assert block, "the `api` docstring shows the dependent contract as a toml block"
    modules = ", ".join(f'"{name}"' for name in api.DEPENDENT_PROTECTED_MODULES)
    text = block.group(1).replace("<dependent>", "downstream")
    text = text.replace("<DEPENDENT_PROTECTED_MODULES>", modules)
    tomllib.loads(text)  # the filled-in text must still be valid toml
    return text


def _lint_seeded_dependent(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run lint-imports with the docstring's contract over a one-module dependent."""
    package = tmp_path / "downstream"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (package / "reader.py").write_text(source, encoding="utf-8", newline="\n")
    (tmp_path / "pyproject.toml").write_text(
        _dependent_contract(), encoding="utf-8", newline="\n",
    )
    return subprocess.run(  # noqa: S603 (fixed argv, no untrusted input)
        [
            str(Path(sys.executable).parent / "lint-imports"),
            "--config",
            str(tmp_path / "pyproject.toml"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )


def test_a_dependent_contract_refuses_an_internal_import(tmp_path: Path) -> None:
    result = _lint_seeded_dependent(
        tmp_path, "from dbml_sharepoint.analysis.typemap import map_column\n",
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Core only through dbml_sharepoint.api BROKEN" in result.stdout, result.stdout
    assert "downstream.reader -> dbml_sharepoint.analysis.typemap" in result.stdout


def test_a_dependent_contract_accepts_an_api_import(tmp_path: Path) -> None:
    result = _lint_seeded_dependent(
        tmp_path,
        "from dbml_sharepoint.api import map_column\n"
        "from dbml_sharepoint.testing import sp_mock\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Core only through dbml_sharepoint.api KEPT" in result.stdout, result.stdout
