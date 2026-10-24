# test/test_yamlio_key_lines.py
"""`yamlio._key_lines`, which finds the line each key of a mapping file is written on."""

from dbml_sharepoint.model.yamlio import _key_lines


def test_top_level_and_second_level_keys_have_their_lines() -> None:
    text = "# head\nprefix: X\nviews:\n  Action:\n    - title: A\n  Risk: []\n"
    assert _key_lines(text) == {
        ("prefix",): 2, ("views",): 3, ("views", "Action"): 4, ("views", "Risk"): 6,
    }


def test_depth_one_stops_at_the_top() -> None:
    assert _key_lines("a:\n  b: 1\n", depth=1) == {("a",): 1}


def test_merge_keys_and_sequences_are_skipped() -> None:
    text = "base: &b {x: 1}\nviews:\n  <<: *b\n  L:\n    - k: 1\n"
    assert ("views", "<<") not in _key_lines(text)
    assert ("views", "L", "k") not in _key_lines(text, depth=3)


def test_empty_document_has_no_keys() -> None:
    assert _key_lines("") == {}
    assert _key_lines("# only a comment\n") == {}


def test_a_key_that_is_not_text_is_left_out() -> None:
    assert _key_lines("1: a\nb: 2\n") == {("b",): 2}
