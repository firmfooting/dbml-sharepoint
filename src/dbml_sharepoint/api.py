"""The names dependents import from this package, each re-exported from its home.

This is the one module exempt from the one-home rule in the package
docstring. Inside this package, and for extension authors, the defining
modules stay the canonical paths; nothing inside the package imports this
module. A dependent imports from here and from `dbml_sharepoint.testing`
only, and holds itself to that with a protected import-linter contract over
`DEPENDENT_PROTECTED_MODULES`:

```toml
[tool.importlinter]
root_packages = ["<dependent>", "dbml_sharepoint"]
[[tool.importlinter.contracts]]
name = "Core only through dbml_sharepoint.api"
type = "protected"
protected_modules = [<DEPENDENT_PROTECTED_MODULES>]
allowed_importers = ["dbml_sharepoint"]
```

Removing a name from `__all__` is a breaking change for dependents.
"""

import pkgutil
from typing import Final

import dbml_sharepoint
from dbml_sharepoint.analysis.condition_rendering import NEGATION
from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.list_url import list_folder, list_url_key, list_url_path
from dbml_sharepoint.analysis.report_columns import (
    DATE_ZONE_RESOLVED_COLUMN,
    ITEM_URL_COLUMN,
    ITEM_URL_RESOLVED_COLUMN,
    REPORT_FIXED_COLUMNS,
    REPORT_KEY_SUFFIX,
    REPORT_SYSTEM_COLUMNS,
    fk_key_column,
    person_key_column,
    projection_output_name,
)
from dbml_sharepoint.analysis.reporting.dictionary import (
    LOADABLE_COLUMNS,
    USERS_COLUMNS,
    DictionaryRow,
    dictionary_rows,
    metadata_rows,
)
from dbml_sharepoint.analysis.reporting.plan import (
    ListPlan,
    build_plans,
    reads_zone,
    report_column_names,
)
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.timezones import (
    WINDOW_END,
    WINDOW_START,
    ZoneTable,
    is_known_zone,
    transitions,
    unknown_zone_message,
    zone_table,
)
from dbml_sharepoint.analysis.typemap import (
    DATE_TYPES,
    FIELD_KIND_BY_TYPE_KIND,
    is_hyperlink,
    is_person,
    map_column,
)
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
    UnknownSolutionError,
    load_solution,
)
from dbml_sharepoint.generators.report_m import (
    generate_dictionary_powerquery,
    generate_powerquery,
)
from dbml_sharepoint.jsonvalue import (
    JsonMap,
    JsonObject,
    JsonValue,
    as_json,
    as_json_object,
    as_object,
    ensure_object,
    int_at,
    is_json_value,
    is_object_list,
    is_text_keyed,
    loads_json,
    loads_object,
    object_at,
    opt_text,
    rows_at,
    text_at,
)
from dbml_sharepoint.jsrest import prelude, wrap
from dbml_sharepoint.model.conditions import Condition, Group, Leaf
from dbml_sharepoint.model.errors import MappingValueError
from dbml_sharepoint.model.form_tree import Banner
from dbml_sharepoint.model.identities import (
    NAME_PATTERN,
    IdentityError,
    IdentityValue,
    identity_hash,
    parse_values,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    RETIRED_SUFFIX,
    DemoItem,
    ListPermissionPolicy,
    Mapping,
    MappingBundle,
    Principal,
    ViewDef,
    WatchedList,
    WatchOn,
    WatchUse,
    auto_display_name,
    title_display_name,
    view_url_slug,
)
from dbml_sharepoint.model.parser import Column, Schema, Table, parse_dbml
from dbml_sharepoint.model.prefix import expand_prefix, prefix_stem
from dbml_sharepoint.model.release import Release, load_release
from dbml_sharepoint.model.yamlio import (
    PARSE_ERRORS,
    RefusedYAMLError,
    TagOrDirectiveError,
    safe_dump,
    safe_load,
)
from dbml_sharepoint.naming import file_stem, kebab, slug
from dbml_sharepoint.pipeline import execute_build
from dbml_sharepoint.project import CONFIG_ERRORS, load_config, resolve_identities
from dbml_sharepoint.templating import script_env

#: Every top-level module and package but this one and the test kit, for a dependent's contract.
DEPENDENT_PROTECTED_MODULES: Final[tuple[str, ...]] = tuple(
    sorted(
        f"dbml_sharepoint.{module.name}"
        for module in pkgutil.iter_modules(dbml_sharepoint.__path__)
        if module.name not in {"api", "testing"}
    )
)

__all__ = (
    "CONFIG_ERRORS",
    "DATE_TYPES",
    "DATE_ZONE_RESOLVED_COLUMN",
    "DEMO_TITLE_PREFIX",
    "FIELD_KIND_BY_TYPE_KIND",
    "ITEM_URL_COLUMN",
    "ITEM_URL_RESOLVED_COLUMN",
    "LOADABLE_COLUMNS",
    "MAPPING_RELPATH",
    "NAME_PATTERN",
    "NEGATION",
    "PARSE_ERRORS",
    "RELEASE_RELPATH",
    "REPORT_FIXED_COLUMNS",
    "REPORT_KEY_SUFFIX",
    "REPORT_SYSTEM_COLUMNS",
    "RETIRED_SUFFIX",
    "SCHEMA_RELPATH",
    "USERS_COLUMNS",
    "WINDOW_END",
    "WINDOW_START",
    "Banner",
    "Column",
    "Condition",
    "DemoItem",
    "DictionaryRow",
    "Group",
    "IdentityError",
    "IdentityValue",
    "JsonMap",
    "JsonObject",
    "JsonValue",
    "Leaf",
    "ListPermissionPolicy",
    "ListPlan",
    "Mapping",
    "MappingBundle",
    "MappingValueError",
    "Principal",
    "RefusedYAMLError",
    "Release",
    "Schema",
    "Table",
    "TagOrDirectiveError",
    "UnknownSolutionError",
    "ViewDef",
    "WatchOn",
    "WatchUse",
    "WatchedList",
    "ZoneTable",
    "as_json",
    "as_json_object",
    "as_object",
    "auto_display_name",
    "build_plans",
    "dictionary_rows",
    "ensure_object",
    "execute_build",
    "expand_prefix",
    "file_stem",
    "fk_key_column",
    "generate_dictionary_powerquery",
    "generate_powerquery",
    "identity_hash",
    "int_at",
    "is_hyperlink",
    "is_json_value",
    "is_known_zone",
    "is_object_list",
    "is_person",
    "is_text_keyed",
    "kebab",
    "list_folder",
    "list_url_key",
    "list_url_path",
    "load_config",
    "load_mapping",
    "load_release",
    "load_solution",
    "loads_json",
    "loads_object",
    "map_column",
    "metadata_rows",
    "object_at",
    "opt_text",
    "parse_dbml",
    "parse_values",
    "person_key_column",
    "prefix_stem",
    "prelude",
    "projection_output_name",
    "reads_zone",
    "report_column_names",
    "resolve",
    "resolve_identities",
    "rows_at",
    "safe_dump",
    "safe_load",
    "script_env",
    "slug",
    "text_at",
    "title_display_name",
    "transitions",
    "unknown_zone_message",
    "view_url_slug",
    "wrap",
    "zone_table",
)
