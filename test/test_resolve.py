# test/test_resolve.py
"""`resolve()` builds every enum-sourced answer once, and never raises.

The strict resolvers in `analysis/folders.py` and `analysis/groups.py` still
exist and still raise; `resolve()` is the lenient path the checks always
needed, plus `require_resolved()` for the generator side that must not
silently omit a declared group or folder.
"""

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _model import enum as make_enum
from _model import mapping as make_mapping
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, pack
from _paths import FIXTURES

import dbml_sharepoint
from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.folders import UnknownFolderEnumError
from dbml_sharepoint.analysis.groups import UnknownGroupEnumError
from dbml_sharepoint.analysis.resolve import (
    MismatchedResolutionError,
    ResolvedMapping,
    UnresolvedEnum,
    guards_resolution,
    require_matching_resolution,
    resolve,
)
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.model.mapping_types import (
    EntityMapping,
    FoldersFromEnum,
    GroupsFromEnum,
    ListPermissionPolicy,
    MappingBundle,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    SiteGroup,
)
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import load_release


def _group(name: str, owner_group: str = "Site Owners") -> SiteGroup:
    """A SiteGroup with the membership controls every declaration must set."""
    return SiteGroup(
        name=name,
        description="Declared by a test.",
        owner_group=owner_group,
        allow_members_edit_membership=False,
        allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False,
        only_allow_members_view_membership=False,
    )


def test_resolve_expands_groups_folders_and_policies_once() -> None:
    """The happy path: every enum source resolved, nothing unresolved."""
    schema = make_schema(
        make_table("Risk", "Title"),
        enums=[make_enum("division", "North", "South")],
    )
    perms = PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        group_sources=(GroupsFromEnum(enum="division", template=_group("{member} Owners")),),
        folder_policies={"Risk": ListPermissionPolicy(
            break_inheritance=True,
            assignments=[RoleAssignment(
                principal=Principal(kind="group", name="{member} Owners"),
                level="Read",
            )],
        )},
    )
    mapping = make_mapping(
        entities={"Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="division"),
        )},
        permissions=perms,
    )

    resolved = resolve(schema, mapping)

    assert resolved.enum_members == {"division": ("North", "South")}
    assert resolved.folders == {"Risk": ("North", "South")}
    assert [name for name, _policy in resolved.folder_policies["Risk"]] == ["North", "South"]
    assert [g.name for g in resolved.groups] == ["North Owners", "South Owners"]
    assert resolved.unresolved == ()
    # Nothing unresolved: the generator-side call is a no-op, not a raise.
    resolved.require_resolved()


def test_resolve_keeps_the_declaration_order_the_strict_resolver_uses() -> None:
    """Generated groups sit where their `from_enum` entry was written.

    The deploy creates groups in this order and resolves a custom
    `owner_group` right after creating the group that names it, so this
    order is a contract and not a presentation choice.
    """
    schema = make_schema(enums=[make_enum("division", "Clinical")])
    owner = _group("{member} Owners")
    literal = _group("Coordinators", owner_group="Clinical Owners")
    perms = PermissionsConfig(
        levels=[], groups=[literal], default_policy=None, overrides={},
        # Declared BEFORE the literal group, which is what `after=0` records.
        group_sources=(GroupsFromEnum(enum="division", template=owner, after=0),),
    )
    mapping = make_mapping(permissions=perms)

    resolved = resolve(schema, mapping)

    assert [g.name for g in resolved.groups] == ["Clinical Owners", "Coordinators"]


def test_resolve_records_an_unknown_enum_rather_than_raising() -> None:
    """A check must still see every OTHER group and folder.

    One misspelled `from_enum` used to stop the whole resolution, and the
    checks then silently stopped judging groups and folders that had
    resolved.
    """
    schema = make_schema(
        make_table("Risk", "Title"),
        make_table("Action", "Title"),
        enums=[make_enum("division", "North")],
    )
    perms = PermissionsConfig(
        levels=[], groups=[_group("Coordinators")], default_policy=None, overrides={},
        group_sources=(
            GroupsFromEnum(enum="not_a_real_enum", template=_group("{member} Owners")),
        ),
    )
    mapping = make_mapping(
        entities={
            "Risk": EntityMapping(
                name="Risk", kind="DocumentLibrary", base_template=101,
                site_role="default",
                folder_source=FoldersFromEnum(enum="not_a_real_enum"),
            ),
            "Action": EntityMapping(
                name="Action", kind="DocumentLibrary", base_template=101,
                site_role="default", folder_source=FoldersFromEnum(enum="division"),
            ),
        },
        permissions=perms,
    )

    resolved = resolve(schema, mapping)

    # The misspelled folder source is absent, not silently empty; the other
    # entity's folders still resolve.
    assert "Risk" not in resolved.folders
    assert "Risk" not in resolved.folder_policies
    assert resolved.folders["Action"] == ("North",)
    # The literal group still resolves although the generated source did not.
    assert [g.name for g in resolved.groups] == ["Coordinators"]
    assert UnresolvedEnum(enum="not_a_real_enum", entity="Risk") in resolved.unresolved
    assert UnresolvedEnum(enum="not_a_real_enum", entity=None) in resolved.unresolved


def test_require_resolved_raises_the_named_error_for_a_generator() -> None:
    """A build must not silently omit a declared group or folder.

    The error type and its `.enum` must match what `declared_groups` and
    `declared_folders` raise today, because `_library.py` formats its
    finding off `err.enum` and the message has to keep agreeing with the
    deploy's tuple.
    """
    schema = make_schema(make_table("Risk", "Title"))
    folder_mapping = make_mapping(entities={
        "Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="missing"),
        ),
    })

    with pytest.raises(UnknownFolderEnumError) as folder_excinfo:
        resolve(schema, folder_mapping).require_resolved()
    assert folder_excinfo.value.enum == "missing"

    group_mapping = make_mapping(permissions=PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        group_sources=(GroupsFromEnum(enum="missing", template=_group("{member} Owners")),),
    ))

    with pytest.raises(UnknownGroupEnumError) as group_excinfo:
        resolve(schema, group_mapping).require_resolved()
    assert group_excinfo.value.enum == "missing"


def test_resolve_carries_the_mapping_it_resolved() -> None:
    """A consumer takes one parameter, not a ResolvedMapping and a Mapping.

    Every signature this piece changes drops `enum_members` in favour of a
    ResolvedMapping, and most of what those consumers then read off the
    mapping has nothing to do with enums. Handing them both would leave two
    things that can disagree about which mapping is being deployed.
    """
    schema = make_schema(make_table("Risk", "Title"))
    mapping = make_mapping(
        entities={"Risk": EntityMapping(
            name="Risk", kind="List", base_template=100, site_role="default",
        )},
    )

    resolved = resolve(schema, mapping)

    assert resolved.mapping is mapping
    # An entity that never writes a `folders:` key resolved, and declares
    # none. Absent would mean unresolved, which is a different answer.
    assert resolved.folders == {"Risk": ()}
    assert resolved.unresolved == ()


def test_require_folders_names_the_enum_rather_than_answering_a_key_error() -> None:
    """A `KeyError` is a `LookupError` and not a `ValueError`.

    `pipeline.execute_report` catches `ValueError` to clear a previously
    generated pack before it exits, so a bare `KeyError` from a direct
    subscript escapes that handler and leaves the last run's pack on disk
    looking current. `UnknownFolderEnumError` declares both bases for
    exactly this, and the strict accessor is what raises it.
    """
    schema = make_schema(make_table("Risk", "Title"), make_table("Action", "Title"))
    mapping = make_mapping(entities={
        "Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="divison"),
        ),
        "Action": EntityMapping(
            name="Action", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=("North",),
        ),
    })

    resolved = resolve(schema, mapping)

    with pytest.raises(UnknownFolderEnumError) as excinfo:
        resolved.require_folders("Risk")
    assert excinfo.value.enum == "divison"
    assert isinstance(excinfo.value, ValueError)
    # The entity that resolved still answers, and an entity this mapping
    # never declared is a KeyError about a name, not a claim about an enum.
    assert resolved.require_folders("Action") == ("North",)
    with pytest.raises(KeyError):
        resolved.require_folders("NoSuchEntity")


def test_require_folder_policies_keeps_the_scope_the_old_resolver_had() -> None:
    """No folder policy means no folder assignments, whatever the enum does.

    `folders.py::folder_policies` returned `()` for an entity with no
    `list_permissions.folders` entry BEFORE it resolved anything, so such an
    entity never reached the raising resolver. Subscripting
    `resolved.folder_policies` instead raises for every unresolved entity,
    which moved a build's failure from `folder_enum_unknown` with its
    findings manifest to a bare `KeyError` at the reader gate.
    """
    schema = make_schema(make_table("Risk", "Title"), make_table("Docs", "Title"))
    perms = PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        folder_policies={"Docs": ListPermissionPolicy(
            break_inheritance=True,
            assignments=[RoleAssignment(
                principal=Principal(kind="group", name="Librarians"), level="Read",
            )],
        )},
    )
    library = {
        name: EntityMapping(
            name=name, kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="divison"),
        )
        for name in ("Risk", "Docs")
    }
    resolved = resolve(schema, make_mapping(entities=library, permissions=perms))

    # Unresolved and no folder policy: the answer does not depend on the enum.
    assert resolved.require_folder_policies("Risk") == ()
    # Unresolved and a folder policy: it does, so it fails closed by name.
    with pytest.raises(UnknownFolderEnumError) as excinfo:
        resolved.require_folder_policies("Docs")
    assert excinfo.value.enum == "divison"


def _pair(tmp_path: Path, folder: str, member: str) -> tuple[Schema, MappingBundle]:
    """One self-consistent pack: `folder` is its library's only root folder.

    Both packs name the SAME entity, deliberately. Two packs naming different
    entities answer a stale resolution with a `KeyError`, and a test built on
    that pair would pass for a reason that has nothing to do with the defect:
    a stale resolution whose entity names all match answers every read.
    """
    return pack(
        tmp_path,
        dbml=blocks(
            f'Enum division {{\n  "{member}"\n}}',
            table("Risk", ID_PK, TITLE, "Division division"),
        ),
        mapping=f'''
            entities:
              Risk:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: ["{folder}"]
        ''',
        dbml_name=f"{folder}-{member}.dbml",
        mapping_name=f"{folder}-{member}.yaml",
    )


def test_a_resolution_built_from_another_pack_is_refused_by_name(tmp_path: Path) -> None:
    """`require_resolved()` asks only whether anything was unresolved.

    A resolution of an UNRELATED mapping has nothing unresolved, so it walked
    straight through that gate, and the build then combined this schema's
    lists and fields with that mapping's folders, groups and ACL policies. It
    would deploy clean and read back clean, which is why the guard has to be
    a refusal rather than a warning.
    """
    schema_a, bundle_a = _pair(tmp_path, "North", "Shared")
    schema_b, bundle_b = _pair(tmp_path, "South", "Shared")
    foreign = resolve(schema_a, bundle_a.mapping)
    # Nothing unresolved, and every read pack B would make is answered -- with
    # pack A's folder. This is what nothing downstream could have seen.
    assert foreign.unresolved == ()
    assert foreign.require_folders("Risk") == ("North",)

    with pytest.raises(MismatchedResolutionError) as excinfo:
        build_schema_json(schema_b, bundle_b, "default", resolved=foreign)
    assert excinfo.value.detail == "its mapping is a different object"

    # The same refusal at the other public entry point, which takes the
    # bundle under the same name but the schema only as rendered JSON.
    with pytest.raises(MismatchedResolutionError):
        generate_manifest(
            schema_json=build_schema_json(
                schema_b, bundle_b, "default",
                resolved=resolve(schema_b, bundle_b.mapping),
            ),
            resolved=foreign,
            findings=[],
            bundle=bundle_b,
            release=load_release(FIXTURES / "release.yaml"),
            site_url="https://example.sharepoint.com/sites/test",
            site_role="default",
            source_dbml="b.dbml",
            source_mtime="2026-05-04T00:00:00Z",
            generated_at="2026-05-04T00:00:00Z",
        )


def test_a_resolution_of_this_mapping_against_another_schema_is_refused(
    tmp_path: Path,
) -> None:
    """Identity on the mapping alone would pass this one.

    `ResolvedMapping` carries no schema, so the schema is checked on
    `enum_members`, which is the whole of what a resolution takes from one.
    """
    other_schema, _other_bundle = _pair(tmp_path, "North", "Clinical")
    schema, bundle = _pair(tmp_path, "North", "Corporate")

    with pytest.raises(MismatchedResolutionError) as excinfo:
        build_schema_json(
            schema, bundle, "default",
            resolved=resolve(other_schema, bundle.mapping),
        )
    assert excinfo.value.detail == "its enum members are not this schema's"


def test_a_mapping_edited_after_it_was_resolved_is_refused(tmp_path: Path) -> None:
    """Identity survives an edit, because `Mapping` is not frozen.

    A caller that resolves, edits the same object and then builds passes the
    pointer compare while `folders`, `folder_policies` and `groups` still
    answer with the pre-edit values, so the deploy would provision this
    mapping's lists with the folders the resolution took before the edit.
    """
    schema, bundle = _pair(tmp_path, "North", "Shared")
    resolved = resolve(schema, bundle.mapping)
    bundle.mapping.entities["Risk"] = replace(
        bundle.mapping.entities["Risk"], folder_source=("Restricted",),
    )
    # The edit is invisible to every comparison the guard made before this.
    assert resolved.mapping is bundle.mapping
    assert resolved.require_folders("Risk") == ("North",)

    with pytest.raises(MismatchedResolutionError) as excinfo:
        build_schema_json(schema, bundle, "default", resolved=resolved)
    assert excinfo.value.detail == "its folder sources changed after it was resolved"


def test_a_permissions_edit_after_resolution_is_refused_by_name() -> None:
    """The stale half a build would otherwise pair with current lists.

    `resolve()` reads `folder_policies` through `folders.py`, so a block
    edited afterwards leaves `resolved.folder_policies` holding the ACLs as
    they were while every other field the generator reads is current.
    """
    schema = make_schema(make_table("Risk", "Title"))
    policy = ListPermissionPolicy(
        break_inheritance=True,
        assignments=[RoleAssignment(
            principal=Principal(kind="group", name="Librarians"), level="Read",
        )],
    )
    perms = PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        folder_policies={"Risk": policy},
    )
    mapping = make_mapping(
        entities={"Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=("Shared",),
        )},
        permissions=perms,
    )
    bundle = MappingBundle(
        mapping=mapping, enum_choices={}, retention_policies={},
        retention_list_defaults={},
    )
    resolved = resolve(schema, mapping)
    perms.folder_policies["Risk"] = replace(policy, break_inheritance=False)

    with pytest.raises(MismatchedResolutionError) as excinfo:
        require_matching_resolution(resolved, bundle, schema)
    assert excinfo.value.detail == "its folder policies changed after it was resolved"


def test_an_edit_the_resolution_cannot_see_is_not_refused(tmp_path: Path) -> None:
    """A guard that refuses edits it has no view of gets suppressed instead.

    `seal_columns` is not an enum source and no resolved field derives from
    one, so a resolution taken before it changed still describes this
    mapping exactly.
    """
    schema, bundle = _pair(tmp_path, "North", "Shared")
    resolved = resolve(schema, bundle.mapping)
    bundle.mapping.seal_columns = not bundle.mapping.seal_columns

    build_schema_json(schema, bundle, "default", resolved=resolved)


def test_a_hand_built_validation_context_is_refused_the_same_way(tmp_path: Path) -> None:
    """`ValidationContext.build` resolves its own, but the class is a dataclass.

    A hand-built one pairing another pack's resolution with this bundle would
    judge a mapping that is not the one deployed, and report its findings
    against this one's locations.
    """
    schema_a, bundle_a = _pair(tmp_path, "North", "Shared")
    schema_b, bundle_b = _pair(tmp_path, "South", "Shared")

    with pytest.raises(MismatchedResolutionError):
        ValidationContext(
            schema=schema_b, bundle=bundle_b,
            resolved=resolve(schema_a, bundle_a.mapping),
        )
    # The supported constructor still works, and resolves from its own inputs.
    assert ValidationContext.build(schema_b, bundle_b).resolved.mapping is bundle_b.mapping


def test_a_guarded_call_with_no_bundle_fails_closed(tmp_path: Path) -> None:
    """A guard that quietly stops guarding is worse than no guard.

    The decorator matches its arguments by type, so a consumer that takes a
    resolution and no bundle has nothing to check it against. That is a
    decoration mistake, and it refuses rather than passing the call through.
    """
    schema, bundle = _pair(tmp_path, "North", "Shared")

    @guards_resolution
    def takes_no_bundle(resolved: ResolvedMapping) -> int:
        return len(resolved.groups)

    with pytest.raises(MismatchedResolutionError) as excinfo:
        takes_no_bundle(resolve(schema, bundle.mapping))
    assert "takes_no_bundle" in str(excinfo.value)


def _public_consumers() -> list[tuple[str, Callable[..., object]]]:
    """Every public function in the package taking a resolution AND a bundle.

    Annotations are compared as TEXT because `bundle.py` quotes its own
    (`ResolvedMapping` is a TYPE_CHECKING import there), and `typing`'s
    resolvers cannot evaluate those at runtime.
    """
    found: list[tuple[str, Callable[..., object]]] = []
    for info in pkgutil.walk_packages(dbml_sharepoint.__path__, "dbml_sharepoint."):
        # Its own guard takes both and is what everything else calls.
        if info.name == "dbml_sharepoint.analysis.resolve":
            continue
        module = importlib.import_module(info.name)
        for name, fn in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(fn):
                continue
            if fn.__module__ != info.name:
                continue
            annotations = [
                str(p.annotation) for p in inspect.signature(fn).parameters.values()
            ]
            if any("ResolvedMapping" in a for a in annotations) and any(
                "MappingBundle" in a for a in annotations
            ):
                found.append((f"{info.name}.{name}", fn))
    return found


def test_every_public_consumer_taking_both_is_guarded() -> None:
    """A new consumer must not be able to skip the guard by being added.

    Private helpers are left out: they are reached only through a public
    entry point that has already refused a foreign resolution.
    """
    consumers = _public_consumers()
    # The eleven this piece threads a resolution through. A bare `> 0` would
    # pass on an import failure that found nothing at all.
    assert len(consumers) >= 11, [name for name, _fn in consumers]
    unguarded = [
        name for name, fn in consumers
        if not getattr(fn, "__resolution_guarded__", False)
    ]
    assert unguarded == []
