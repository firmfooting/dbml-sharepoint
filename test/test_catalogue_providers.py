"""Pack providers: installed distributions that register a solution root."""

import io
import zipfile
from collections.abc import Iterator
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from _catalogue_fixtures import CORE_LICENSE, Provider, install, write_family, write_journey

from dbml_sharepoint import catalogue
from dbml_sharepoint.catalogue import (
    BLUEPRINT_ROOTS_GROUP,
    CORE_DISTRIBUTION,
    BlueprintRootError,
    Shadowed,
    available_solutions,
    blueprint_roots,
    load_solution,
    notices,
    read_catalogue,
)


def test_providers_are_found_under_the_documented_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def spy(*, group: str) -> list[EntryPoint]:
        asked.append(group)
        return []

    monkeypatch.setattr(catalogue, "entry_points", spy)
    blueprint_roots()
    assert asked == ["dbml_sharepoint.blueprint_roots"]


def test_with_no_provider_only_core_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site")
    assert [r.distribution for r in blueprint_roots()] == [CORE_DISTRIBUTION]


def test_a_provider_s_packs_follow_core_s_with_its_package_and_licence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    solutions = available_solutions()
    assert solutions[-1].id == "acme-thing"
    assert (solutions[-1].distribution, solutions[-1].license) == ("acme-packs", "BUSL-1.1")
    assert {s.distribution for s in solutions[:-1]} == {CORE_DISTRIBUTION}


def test_a_provider_pack_must_carry_its_distribution_s_licence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_family(packs, "acme-thing")  # core's licence, inside a BUSL-1.1 distribution
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert "acme-thing" not in {s.id for s in found.solutions}
    assert [(r.distribution, r.path.name) for r in found.refused] == [
        ("acme-packs", "acme-thing"),
    ]
    assert f"license '{CORE_LICENSE}' differs from 'BUSL-1.1'" in found.refused[0].reason


def test_a_provider_without_a_licence_expression_is_refused_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    packs.mkdir()
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs, licence=None))
    with pytest.raises(BlueprintRootError, match="acme-packs declares no License-Expression"):
        read_catalogue()


def test_a_provider_root_inside_a_zip_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Packs are copied and built as real files, so a zipped install fails closed."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("packs/acme-thing/blueprint.toml", "")
    with zipfile.ZipFile(buffer) as archive:
        zipped = zipfile.Path(archive, "packs/")
        install(monkeypatch, tmp_path / "site", Provider("acme-packs", zipped))
        with pytest.raises(BlueprintRootError, match=r"acme-packs: .* not a directory on disk"):
            read_catalogue()


def test_a_provider_root_that_does_not_exist_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", tmp_path / "missing"))
    with pytest.raises(BlueprintRootError, match="is not a directory"):
        read_catalogue()


def test_an_entry_point_outside_any_distribution_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    point = EntryPoint(
        name="packs", value="_catalogue_fixtures:first_root", group=BLUEPRINT_ROOTS_GROUP,
    )
    monkeypatch.setattr(catalogue, "entry_points", lambda *, group: [point])
    with pytest.raises(BlueprintRootError, match="belongs to no distribution"):
        read_catalogue()


def test_core_wins_a_duplicate_id_and_the_loser_is_named_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every id repeats while a provider and core both ship the same packs."""
    packs = tmp_path / "packs"
    for pack_id in ("risk-register", "visitor-log"):
        write_family(packs, pack_id, {"license": "BUSL-1.1"})
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert load_solution("risk-register").distribution == CORE_DISTRIBUTION
    assert set(found.shadowed) == {
        Shadowed("blueprint", "risk-register", "acme-packs", CORE_DISTRIBUTION),
        Shadowed("blueprint", "visitor-log", "acme-packs", CORE_DISTRIBUTION),
    }
    assert [line for line in notices(found) if line.startswith("Hidden:")] == [
        (
            "Hidden: 2 blueprints from acme-packs share an id with one from dbml-sharepoint, "
            "which is offered instead: risk-register, visitor-log"
        ),
    ]


def test_between_providers_the_first_by_name_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    later, earlier = tmp_path / "b", tmp_path / "a"
    write_family(later, "acme-thing", {"license": "BUSL-1.1"})
    write_family(earlier, "acme-thing", {"license": "BUSL-1.1"})
    install(
        monkeypatch, tmp_path / "site",
        Provider("b-packs", later), Provider("a-packs", earlier),
    )

    assert [r.distribution for r in blueprint_roots()] == [
        CORE_DISTRIBUTION, "a-packs", "b-packs",
    ]
    assert load_solution("acme-thing").distribution == "a-packs"


def test_a_provider_s_journeys_are_offered_and_core_wins_a_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_journey(packs, "acme-journey", ["acme-thing"])
    write_journey(packs, "the-front-desk", ["acme-thing"])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    by_id = {j.id: j for j in found.journeys}
    assert by_id["acme-journey"].distribution == "acme-packs"
    assert by_id["the-front-desk"].distribution == CORE_DISTRIBUTION
    assert Shadowed("journey", "the-front-desk", "acme-packs", CORE_DISTRIBUTION) in found.shadowed


def test_a_provider_whose_entry_point_raises_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial install or a renamed module should read as a named line, not a traceback."""
    broken = ImportError("No module named 'acme_packs.data'")
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", broken))
    with pytest.raises(
        BlueprintRootError,
        match=r"^acme-packs: .* failed to load: ImportError: No module named 'acme_packs.data'",
    ):
        read_catalogue()


def test_a_provider_journey_that_will_not_parse_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    (packs / "journeys").mkdir(parents=True)
    (packs / "journeys" / "broken.md").write_text("no front matter\n", encoding="utf-8")
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    expected = r"^acme-packs: .*broken\.md: no YAML front matter"
    with pytest.raises(BlueprintRootError, match=expected):
        read_catalogue()


def test_a_provider_journey_that_is_not_utf8_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    (packs / "journeys").mkdir(parents=True)
    (packs / "journeys" / "latin.md").write_bytes(b"---\ntitle: caf\xe9\n---\n")
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    with pytest.raises(BlueprintRootError, match=r"^acme-packs: "):
        read_catalogue()


def test_a_provider_journey_a_console_cannot_print_is_refused_by_codepoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Journey text reaches the same terminal table as pack text, so it meets the same rule."""
    packs = tmp_path / "packs"
    path = write_journey(packs, "acme-journey", ["acme-thing"])
    path.write_text(
        path.read_text(encoding="utf-8").replace("A journey for a test.", "Caf" + chr(0xE9) + "."),
        encoding="utf-8", newline="\n",
    )
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    with pytest.raises(BlueprintRootError, match=r"'summary' carries .* U\+00E9"):
        read_catalogue()


def test_typography_in_a_journey_is_still_folded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    path = write_journey(packs, "acme-journey", ["acme-thing"])
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "for a test", "for a test " + chr(0x2014) + " folded",
        ),
        encoding="utf-8", newline="\n",
    )
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    by_id = {j.id: j for j in read_catalogue().journeys}
    assert by_id["acme-journey"].summary == "A journey for a test -- folded."


def test_a_provider_pack_missing_its_release_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offered without it, the wizard would copy it and print a rebuild command naming no file."""
    packs = tmp_path / "packs"
    family = write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    (family / "20-configure" / "release.yaml").unlink()
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert "acme-thing" not in {s.id for s in found.solutions}
    assert [(r.distribution, r.path.name) for r in found.refused] == [("acme-packs", "acme-thing")]
    assert "20-configure/release.yaml" in found.refused[0].reason


def test_a_provider_pack_with_a_manifest_but_no_schema_is_refused_not_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    family = write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    (family / "10-design" / "schema.dbml").unlink()
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert [(r.distribution, r.path.name) for r in found.refused] == [("acme-packs", "acme-thing")]
    assert "10-design/schema.dbml" in found.refused[0].reason


def test_a_provider_journey_id_a_console_cannot_print_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_journey(packs, "caf" + chr(0x00E9), ["acme-thing"])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    with pytest.raises(BlueprintRootError, match=r"'id' carries .* U\+00E9"):
        read_catalogue()


def test_a_provider_root_that_cannot_be_listed_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory denied to this user globs as empty, which would hide every blueprint in it."""
    packs = tmp_path / "packs"
    write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    real = Path.iterdir

    def denied(self: Path) -> Iterator[Path]:
        if self == packs:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(BlueprintRootError, match=r"^acme-packs: .* cannot be listed: .*denied"):
        read_catalogue()


def test_a_provider_journey_that_cannot_be_read_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    write_journey(packs, "locked", ["acme-thing"])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    real = Path.read_text

    def locked(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self.name == "locked.md":
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(BlueprintRootError, match=r"^acme-packs: .*Permission denied"):
        read_catalogue()


def test_a_provider_journey_sharing_a_blueprint_s_id_is_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One prompt takes both, and a blueprint id wins it, so the journey could never be chosen."""
    packs = tmp_path / "packs"
    write_journey(packs, "visitor-log", ["visitor-log"])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert "visitor-log" not in {j.id for j in found.journeys}
    assert Shadowed("journey", "visitor-log", "acme-packs", CORE_DISTRIBUTION) in found.shadowed


def test_no_core_journey_shares_a_core_blueprint_s_id() -> None:
    found = read_catalogue()
    assert not {j.id for j in found.journeys} & {s.id for s in found.solutions}


def test_a_provider_mapping_a_console_cannot_print_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prefix and list names are printed when the blueprint is chosen, before any load."""
    packs = tmp_path / "packs"
    family = write_family(packs, "acme-thing", {"license": "BUSL-1.1"})
    (family / "20-configure" / "mapping.yaml").write_text(
        'prefix: "X\\e[2J"\nentities:\n  "Thing\\a": {}\n', encoding="utf-8", newline="\n",
    )
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))

    found = read_catalogue()
    assert "acme-thing" not in {s.id for s in found.solutions}
    assert "U+001B" in found.refused[0].reason


def test_a_provider_journey_member_a_console_cannot_print_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A member that is not installed is printed back in the wizard's hint."""
    packs = tmp_path / "packs"
    write_journey(packs, "acme-journey", ["acme-thing", '"\\e[2J"'])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    with pytest.raises(BlueprintRootError, match=r"'solutions' carries .* U\+001B"):
        read_catalogue()


def test_a_provider_journey_named_all_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wizard reads `all` as "show everything", so a journey by that name could never open."""
    packs = tmp_path / "packs"
    write_journey(packs, "all", ["acme-thing"])
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    with pytest.raises(BlueprintRootError, match=r"^acme-packs: .*'all' is reserved"):
        read_catalogue()


def test_a_provider_whose_metadata_cannot_be_decoded_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = tmp_path / "packs"
    packs.mkdir()
    install(monkeypatch, tmp_path / "site", Provider("acme-packs", packs))
    (tmp_path / "site" / "acme_packs-1.0.dist-info" / "METADATA").write_bytes(b"Name: acme\xe9\n")
    expected = r"\(_catalogue_fixtures:first_root\).* metadata cannot be read: UnicodeDecodeError"
    with pytest.raises(BlueprintRootError, match=expected):
        read_catalogue()
