# test/test_permissions.py
from dbml_sharepoint.analysis.permissions import (
    BUILT_IN_LEVELS,
    base_permissions_to_high_low,
)


def test_view_list_items_alone() -> None:
    hl = base_permissions_to_high_low(["ViewListItems"])
    assert hl.high == "0"
    assert hl.low == "1"


def test_manage_lists_in_low_bits() -> None:
    hl = base_permissions_to_high_low(["ManageLists"])
    assert hl.high == "0"
    assert hl.low == str(0x800)


def test_use_remote_apis_in_high_bits() -> None:
    # bit 37 → falls into High register (32..63)
    hl = base_permissions_to_high_low(["UseRemoteAPIs"])
    assert hl.low == "0"
    assert hl.high == str(0x20)  # high register sees bit 37 as bit 5 → 0x20


def test_combination_low_and_high() -> None:
    hl = base_permissions_to_high_low(["ManageLists", "UseRemoteAPIs"])
    assert hl.low == str(0x800)
    assert hl.high == str(0x20)


def test_full_mask() -> None:
    hl = base_permissions_to_high_low(["FullMask"])
    assert hl.high == str(0x7FFFFFFF)
    assert hl.low == str(0xFFFFFFFF)


def test_unknown_permission_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown base permission"):
        base_permissions_to_high_low(["NotAThing"])


def test_built_in_levels_includes_full_control() -> None:
    assert "Full Control" in BUILT_IN_LEVELS
    assert "Contribute" in BUILT_IN_LEVELS
    assert "Read" in BUILT_IN_LEVELS
