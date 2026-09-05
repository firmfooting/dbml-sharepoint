"""The column-history family's key contract, pinned to its two authorities.

`_row_key_m` is THE definition of the reporting row key
(`generators/reportgen.py`, "THE ONE definition of the key format"); the
family's deploy.md and governance.md document it for flow authors, and the
demo rows hand-type it. The whole Power BI value of the family rests on
those three staying byte-identical. `_row_key_m` has already changed format
once (2026-08-11, site+id -> site+list+id); a second change must not be able
to leave the docs teaching an unjoinable key.
"""

from pathlib import Path

import pytest

from dbml_sharepoint.generators.reportgen import _row_key_m

_FAMILY = (
    Path(__file__).resolve().parents[1]
    / "src" / "dbml_sharepoint" / "solutions" / "column-history"
)


def _row_key_literal() -> str:
    """The key format EXACTLY as `_row_key_m` builds it for a real row."""
    return _row_key_m("RR_Risk", "[Id]")


def test_the_reportgen_key_shape() -> None:
    # Guard the guard: if this fails, `_row_key_m` changed shape and every
    # assertion below is testing the OLD format against NEW docs.
    key = _row_key_literal()
    assert key == 'SiteRoot & "|" & "RR_Risk" & "|" & Number.ToText([Id])', (
        "_row_key_m changed format. Update BOTH docs (see the failures that "
        "follow) AND this literal in the same commit."
    )


@pytest.mark.parametrize(
    ("doc", "fragment"),
    [
        ("30-deploy/deploy.md", 'Number.ToText([Id])'),
        ("30-deploy/deploy.md", '"|" &'),
        ("50-govern/governance.md", 'Number.ToText([Id])'),
        ("50-govern/governance.md", 'Number.ToText([Id])'),
    ],
)
def test_the_docs_teach_the_real_key_shape(doc: str, fragment: str) -> None:
    text = (_FAMILY / doc).read_text(encoding="utf-8")
    assert fragment in text, (
        f"{doc} no longer documents the key shape `_row_key_m` builds "
        f"(missing {fragment!r}). Flows written from it would produce keys "
        "that join to nothing in Power BI."
    )


def test_every_demo_change_key_is_the_real_key_of_its_own_row() -> None:
    """Demo rows are the shape operators copy. Each must satisfy
    ChangeKey == SiteUrl|ListTitle|ItemId exactly."""
    import yaml  # the repo ships it via website/tooling; fallback below

    mapping = yaml.safe_load(
        (_FAMILY / "20-configure" / "mapping.yaml").read_text(encoding="utf-8")
    )
    demos = (mapping.get("demo_items") or {}).get("ColumnHistory") or []
    assert demos, "column-history lost its demo rows"
    for row in demos:
        name = row.get("key", "?")
        values = row["values"]
        site, list_title, item_id = (
            values["SiteUrl"], values["ListTitle"], values["ItemId"],
        )
        assert values["ChangeKey"] == f"{site}|{list_title}|{item_id}", (
            f"demo row {name!r}: ChangeKey {values['ChangeKey']!r} is not "
            f"{site}|{list_title}|{item_id}"
        )
