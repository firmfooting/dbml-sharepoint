# test/test_env_file.py
from pathlib import Path
from unittest.mock import patch

import pytest

from dbml_sharepoint.model.env_file import (
    ENV_FILENAME,
    ENV_SETTINGS,
    EnvFileSyntaxError,
    EnvSetting,
    UnknownEnvKeyError,
    read_env_file,
)


def _write(tmp_path: Path, text: str, name: str = ENV_FILENAME) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def test_env_settings_has_exactly_the_registered_fields() -> None:
    """Locks the dataclass shape: key, parameter, help and nothing else.

    An earlier draft added a `validate` field carrying the CLI validator;
    that created an import cycle and dragged typer into `model/`. This test
    exists so the field does not quietly come back.
    """
    assert {f.name for f in EnvSetting.__dataclass_fields__.values()} == {
        "key",
        "parameter",
        "help",
    }
    assert len(ENV_SETTINGS) == 1
    assert ENV_SETTINGS[0].key == "DBMLSP_ENTERPRISE_READER"
    assert ENV_SETTINGS[0].parameter == "enterprise_reader"


def test_parses_key_value_pairs(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER=svc@example.org\n")
    settings, _ = read_env_file(path)
    assert settings == {"DBMLSP_ENTERPRISE_READER": "svc@example.org"}


def test_blank_lines_and_comments_are_ignored(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "\n"
        "# a comment\n"
        "   \n"
        "  # indented comment\n"
        "DBMLSP_ENTERPRISE_READER=svc@example.org\n",
    )
    settings, _ = read_env_file(path)
    assert settings == {"DBMLSP_ENTERPRISE_READER": "svc@example.org"}


def test_matching_double_quotes_are_stripped(tmp_path: Path) -> None:
    path = _write(tmp_path, 'DBMLSP_ENTERPRISE_READER="svc@example.org"\n')
    settings, _ = read_env_file(path)
    assert settings["DBMLSP_ENTERPRISE_READER"] == "svc@example.org"


def test_matching_single_quotes_are_stripped(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER='svc@example.org'\n")
    settings, _ = read_env_file(path)
    assert settings["DBMLSP_ENTERPRISE_READER"] == "svc@example.org"


def test_mismatched_quotes_is_a_syntax_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER=\"svc@example.org'\n")
    with pytest.raises(EnvFileSyntaxError, match="mismatched quotes"):
        read_env_file(path)


def test_unterminated_quote_is_a_syntax_error(tmp_path: Path) -> None:
    path = _write(tmp_path, 'DBMLSP_ENTERPRISE_READER="svc@example.org\n')
    with pytest.raises(EnvFileSyntaxError, match="mismatched quotes"):
        read_env_file(path)


def test_no_interpolation_dollar_brace_is_a_literal(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER=${OTHER}\n")
    settings, _ = read_env_file(path)
    assert settings["DBMLSP_ENTERPRISE_READER"] == "${OTHER}"


def test_export_prefix_is_refused_naming_file_line_and_text(tmp_path: Path) -> None:
    path = _write(tmp_path, "export DBMLSP_ENTERPRISE_READER=svc@example.org\n")
    with pytest.raises(EnvFileSyntaxError) as err:
        read_env_file(path)
    message = str(err.value)
    assert str(path) in message
    assert "line 1" in message
    assert "export DBMLSP_ENTERPRISE_READER=svc@example.org" in message


def test_line_without_equals_is_refused_naming_file_line_and_text(tmp_path: Path) -> None:
    path = _write(tmp_path, "just some text\n")
    with pytest.raises(EnvFileSyntaxError) as err:
        read_env_file(path)
    message = str(err.value)
    assert str(path) in message
    assert "line 1" in message
    assert "just some text" in message


def test_repeated_key_is_refused_not_last_wins(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "DBMLSP_ENTERPRISE_READER=first@example.org\n"
        "DBMLSP_ENTERPRISE_READER=second@example.org\n",
    )
    with pytest.raises(EnvFileSyntaxError, match="repeated"):
        read_env_file(path)


def test_key_without_dbmlsp_prefix_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "ENTERPRISE_READER=svc@example.org\n")
    with pytest.raises(EnvFileSyntaxError, match="DBMLSP_"):
        read_env_file(path)


def test_unknown_dbmlsp_key_raises_with_did_you_mean(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READR=svc@example.org\n")
    with pytest.raises(UnknownEnvKeyError) as err:
        read_env_file(path)
    message = str(err.value)
    assert "DBMLSP_ENTERPRISE_READR" in message
    assert "DBMLSP_ENTERPRISE_READER" in message


def test_unknown_dbmlsp_key_with_no_close_match_has_no_suggestion(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_COMPLETELY_UNRELATED=1\n")
    with pytest.raises(UnknownEnvKeyError) as err:
        read_env_file(path)
    assert "Did you mean" not in str(err.value)


def test_digest_is_twelve_lowercase_hex_characters(tmp_path: Path) -> None:
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER=svc@example.org\n")
    _, digest = read_env_file(path)
    assert len(digest) == 12
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_digest_moves_on_a_whitespace_only_edit(tmp_path: Path) -> None:
    path_a = _write(
        tmp_path, "DBMLSP_ENTERPRISE_READER=svc@example.org\n", name="a.env",
    )
    path_b = _write(
        tmp_path, "DBMLSP_ENTERPRISE_READER=svc@example.org\n\n", name="b.env",
    )
    _, digest_a = read_env_file(path_a)
    _, digest_b = read_env_file(path_b)
    assert digest_a != digest_b


def test_read_env_file_reads_the_bytes_exactly_once(tmp_path: Path) -> None:
    """Parse and digest must describe the same bytes: a spy on `read_bytes`
    proves there is only one read for a caller to be inconsistent about."""
    path = _write(tmp_path, "DBMLSP_ENTERPRISE_READER=svc@example.org\n")
    with patch.object(Path, "read_bytes", autospec=True, wraps=Path.read_bytes) as spy:
        read_env_file(path)
    assert spy.call_count == 1
