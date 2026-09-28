"""Nothing tracked names the organisation whose material left, or a blueprint held for it.

Each name is held as the SHA-256 digest of its spelling with everything but letters and digits
removed, so this file spells none of them. A line is read as a run of tokens (words, digits and
the pieces of a CamelCase word), and every run of one to four tokens is joined and digested, so
`Some Name`, `SomeName`, `some-name` and `some_name` are the same name. CHANGELOG.md is
release-please's record of what shipped and is left as it is, and lockfiles are generated.
"""

import hashlib
import re
import subprocess
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import pytest
from _paths import REPO_ROOT

#: Where a name sits in a line: (offset, length), or None.
type Finder = Callable[[str], tuple[int, int] | None]

#: SHA-256 of each forbidden name, letters and digits only in lower case, by that length.
_FORBIDDEN: dict[int, frozenset[str]] = {
    3: frozenset({
        "1cbb68c45acd4d23ad6b40da7205efd8fde8f18035512e02d3139b69a8273e04",
    }),
    4: frozenset({
        "59c6986f26299a74ed9ec18a66816788d0001b8e6892c11b4e5ec7b7118a34ff",
        "5a098c8778e8c8f5218b94eb26c7e94af8ca1b94bd0f43ffe766919d092c44e6",
    }),
    7: frozenset({
        "7f37c953bc2cab934c2fee3a9ce97464f443fea23b10f214003f5bb9d69e7525",
        "d4d6fbb6a15937cd5b279d1361f5d8b9560b415607271014212201a4b88f3079",
    }),
    8: frozenset({
        "ec5090e0bb26cfddf2998904e9f775c845d85e49b52e42d56b0ddc7441740833",
    }),
    9: frozenset({
        "42c55ef8d0bba1e28211d5702dc5f6fe82e8c534aa91386cf1ca7bfe79b7697c",
        "993df2feb4b9d3cb19a183df649373f1ef76c9a673a66142a4853a739799f01a",
        "9dfbac27ed5d7b7a1cf218e848ef5669d167f41dca4aef52b41122d228c3cf7b",
    }),
    10: frozenset({
        "c28e6592101ac6144a1ee5a8b94b37ccde844e5bb19f9756f2035a46c200d3d5",
    }),
    11: frozenset({
        "df044e2b0b23db73dd0012f50a8355db041b946b4604b59dcfc70117bf4e997d",
    }),
    14: frozenset({
        "08f3f52cd5bef1c50f8acf8c7edc707465b0e4bad63599645e6d18ec6176bd7d",
        "668ba77ae2db2f463daf5156faf89975b191fc72ccfd7edb90562b33d06efc22",
        "6a0eb8fb9ec46fd129d1bda3d98e56c97c4025cfbc939f08e4ad5e995e4f2403",
    }),
    16: frozenset({
        "574e4737e3d0937e752b39fa391c10316d03d25c5778706ffbd1fd2e08b997f6",
        "67521ce791506a8273d7308b1bcd6e566f1b376b7a83bf4511927addd9f74678",
    }),
    17: frozenset({
        "5e550e62ffed7a2f84e0abe4cc72595c74cfa75be408546c1b1198f65dc0e8ef",
        "93075575be307a2e8e7190917ac42f2f452078653efd959b38143e4e4be66469",
    }),
    18: frozenset({
        "24fb5e9e616c6da1f8a089839e60b6aecf6e8652fb5cfc1f1707bab510afaf44",
        "520a72c3256bcf3c18827c331cf10fa997255f19e1990d6f58b01087083b59d7",
    }),
    19: frozenset({
        "05875364c44ff8215c0aee07f6c3f8c207df4a1e8fd16f53e4defe6fb2ae4c37",
        "36eadf97d36d4bb2aa4aec638ef773978e6aa5fe2d6bc2d74784ba80a5139770",
        "68184f50dd7d1a1362d55059ac77fd563adc3531e12a2b13b79866fc26d6b687",
        "7942cecc25ce476200a08711b742fadfe32a322b6ea9946527294335d90d175b",
        "94cda3b170d319c88cbd102e3d76be2a5b6e08a96c43155876c8fd11fd71832e",
    }),
    20: frozenset({
        "0ee805ff1c2986af14a66797dcc0edc1aff8c9ab519347e21b8a2c5868a01d12",
        "ba31754cd805dd9b3f57cabcfcad42ed3b5c4be903c10282bae4402980d6e075",
    }),
    21: frozenset({
        "186ed164140e2aee5436166a57118e9b1a7ad59994ad9b1f307351c93a739f10",
    }),
    23: frozenset({
        "30f91da3eb0597762fbea823c746aa70c6463073b620dd093e5636de29a2f5a6",
        "5fc44b14c7626da686f41a1a29f5f8e63bdf6e0837952e8fb706da2bb652771a",
    }),
    28: frozenset({
        "817ec694193fe85f033f1f8e44c54b7d95e3d07d63644cfeaf85db79f006dff1",
    }),
}

#: The longest forbidden name, in tokens; `Some Long Name Here` is four.
_RUN = 4

#: A token: a CamelCase piece, an upper-case run, or a run of lower-case letters and digits.
_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")

#: Not scanned: the release record, and generated lockfiles.
_LEFT_ALONE = ("CHANGELOG.md", "uv.lock", "website/package-lock.json")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _finder(forbidden: dict[int, frozenset[str]]) -> Finder:
    """Look for any forbidden name in `line`, as a run of one to `_RUN` tokens."""
    lengths = frozenset(forbidden)

    @lru_cache(maxsize=1 << 16)
    def forbidden_run(joined: str) -> bool:
        return len(joined) in lengths and _digest(joined) in forbidden[len(joined)]

    def find(line: str) -> tuple[int, int] | None:
        tokens = list(_TOKEN.finditer(line))
        for start, first in enumerate(tokens):
            joined = ""
            for last in tokens[start : start + _RUN]:
                joined += last.group(0).lower()
                if forbidden_run(joined):
                    return first.start(), last.end() - first.start()
        return None

    return find


_FIND = _finder(_FORBIDDEN)


def _tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Skipping is honest; an empty list would pass without reading a file.
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    return [name for name in result.stdout.split("\0") if name and name not in _LEFT_ALONE]


def _naming(path: Path, relative: str, find: Finder = _FIND) -> list[str]:
    """Where `path` names a forbidden name: its path, then each line, spelled as found."""
    found = []
    if (hit := find(relative)) is not None:
        found.append(f"{relative}: in the path: {relative[hit[0] : hit[0] + hit[1]]}")
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        # Binary, by git's rule: its bytes spell nothing, and a PNG once spelled a short name.
        return found
    for number, line in enumerate(data.decode("utf-8", errors="replace").split("\n"), start=1):
        if (hit := find(line)) is not None:
            found.append(f"{relative}:{number}: {line[hit[0] : hit[0] + hit[1]]}")
    return found


def test_nothing_tracked_names_the_customer_or_a_held_blueprint() -> None:
    tracked = _tracked()
    assert len(tracked) > 500, f"only {len(tracked)} files scanned, so this pins nothing"
    # A tracked file deleted but not yet staged has no content to read; its path is still judged.
    offenders = [
        hit
        for name in tracked
        for hit in (
            _naming(REPO_ROOT / name, name)
            if (REPO_ROOT / name).is_file()
            else [f"{name}: in the path"] if _FIND(name) else []
        )
    ]
    assert not offenders, (
        "This repository carries no material from its first customer and none of the "
        "blueprints held for it. Reword or remove each of these:\n" + "\n".join(offenders)
    )


def test_the_forbidden_names_are_pinned_in_number_and_shape() -> None:
    """An emptied table would pass every file, so pin its size and shape."""
    digests = [d for group in _FORBIDDEN.values() for d in group]
    assert len(digests) == 31
    assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in digests)
    assert all(3 <= length <= 40 for length in _FORBIDDEN)


#: Stand-ins for the real names, which this file may not spell.
_SEEDED = _finder({
    9: frozenset({_digest("zorkboard")}),
    13: frozenset({_digest("acmelegalcase")}),
})


@pytest.mark.parametrize(
    ("written", "reported"),
    [
        ("ZorkBoard", "ZorkBoard"),
        ("zork-board", "zork-board"),
        ("the zork board here", "zork board"),
        ("ACME_LegalCase", "ACME_LegalCase"),
        ("acme legal case", "acme legal case"),
        ("AcmeLegalCaseRow", "AcmeLegalCase"),
    ],
)
def test_the_scan_reports_a_seeded_name_however_it_is_spelled(
    tmp_path: Path, written: str, reported: str,
) -> None:
    seeded = tmp_path / "notes.md"
    seeded.write_text(f"nothing here\nsee {written} for details\n", encoding="utf-8", newline="\n")
    assert _naming(seeded, "notes.md", _SEEDED) == [f"notes.md:2: {reported}"]


def test_the_scan_reports_a_seeded_path(tmp_path: Path) -> None:
    seeded = tmp_path / "notes.md"
    seeded.write_text("nothing here\n", encoding="utf-8")
    assert _naming(seeded, "test/fixtures/zork-board-extract.json", _SEEDED) == [
        "test/fixtures/zork-board-extract.json: in the path: zork-board",
    ]


def test_a_binary_file_is_judged_by_its_path_alone(tmp_path: Path) -> None:
    seeded = tmp_path / "zork-board.png"
    seeded.write_bytes(b"\x89PNG\r\n\x1a\n\0 zork board zorkboard")
    assert _naming(seeded, "static/zork-board.png", _SEEDED) == [
        "static/zork-board.png: in the path: zork-board",
    ]


def test_a_name_inside_a_longer_word_is_not_a_hit(tmp_path: Path) -> None:
    """`zorkboards` is not `zorkboard`; a token run must end where the name ends."""
    seeded = tmp_path / "notes.md"
    seeded.write_text("zorkboards and zorkboardx\n", encoding="utf-8")
    assert _naming(seeded, "notes.md", _SEEDED) == []
