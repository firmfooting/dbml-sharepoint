# src/dbml_sharepoint/model/sections/_sources.py
"""`enum_sources` and `retention_policies_source`: files loaded beside the mapping.

Both resolve relative to the mapping's directory, and what they hold reaches
the bundle rather than the mapping, because it is loaded content rather
than a declaration.
"""

from pathlib import Path
from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import RetentionPolicy
from dbml_sharepoint.model.reading import load_yaml, optional_int, optional_str
from dbml_sharepoint.model.sections.context import SectionContext

_RETENTION_POLICY_KEYS = frozenset(
    {"description", "sp_label", "retain_years", "retain_days", "trigger"},
)


def read(sc: SectionContext) -> dict[str, Any]:
    enum_choices, enum_source_paths = _load_enum_choices(
        sc.base_dir, _require_mapping(sc.block("enum_sources"), "enum_sources"),
    )

    retention_source = sc.block("retention_policies_source")
    retention_path = (sc.base_dir / retention_source).resolve() if retention_source else None
    if retention_path is not None:
        retention_policies, retention_list_defaults = _load_retention(retention_path)
    else:
        retention_policies, retention_list_defaults = {}, {}

    return {
        "enum_sources": enum_source_paths,
        "enum_choices": enum_choices,
        "retention_policies_source": retention_path,
        "retention_policies": retention_policies,
        "retention_list_defaults": retention_list_defaults,
    }


def _load_enum_choices(
    base_dir: Path, enum_sources: dict[str, str],
) -> tuple[dict[str, list[str]], dict[str, Path]]:
    """Load every `enum_sources` entry into a name -> list[str] map.

    Values are `path#fragment`, where `fragment` names a
    top-level key in the target YAML and defaults to `choices` when omitted.
    Paths resolve relative to base_dir, the same rule as the other config
    sources. Returns (enum_choices, resolved_paths); the latter becomes
    Mapping.enum_sources (fragment stripped, for display/source-tracking).
    """
    choices: dict[str, list[str]] = {}
    resolved: dict[str, Path] = {}
    for name, spec in enum_sources.items():
        path_part, _, fragment = spec.partition("#")
        fragment = fragment or "choices"
        path = (base_dir / path_part).resolve()
        resolved[name] = path
        source = load_yaml(path)
        values = source.get(fragment)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(
                f"{path}: {fragment!r} must be a list of strings "
                f"(enum_sources[{name!r}])",
            )
        choices[name] = list(values)
    return choices, resolved


def _load_retention(path: Path) -> tuple[dict[str, RetentionPolicy], dict[str, str]]:
    """Load config/retention-policies.yaml; returns (policies, list_defaults).

    Guarded like every other reader in this package: unknown keys are refused,
    not ignored, and every field is type-checked before it reaches the
    dataclass -- see `_keys._reject_unknown_keys` for why a fail-open level
    here would make a typo'd file byte-identical to one with the key deleted.
    """
    raw = load_yaml(path)
    raw_policies = _require_mapping(raw.get("policies"), "policies", allow_absent=False)
    policies: dict[str, RetentionPolicy] = {}
    for name, raw_spec in raw_policies.items():
        context = f"policies.{name}"
        spec = _require_mapping(raw_spec, context, allow_absent=False)
        _reject_unknown_keys(spec, _RETENTION_POLICY_KEYS, context)
        policies[name] = RetentionPolicy(
            name=name,
            description=optional_str(spec, "description", context) or "",
            sp_label=optional_str(spec, "sp_label", context) or "",
            retain_years=optional_int(spec, "retain_years", context),
            retain_days=optional_int(spec, "retain_days", context),
            trigger=optional_str(spec, "trigger", context) or "creation",
        )
    list_defaults = dict(_require_mapping(raw.get("list_defaults"), "list_defaults"))
    return policies, list_defaults
