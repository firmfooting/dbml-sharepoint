"""The two env keys that switch on help links, and the map they name."""

from pathlib import Path

import pytest

from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.model.help_guides import HelpGuides, HelpSettings, load_help_guides
from dbml_sharepoint.project import resolve_env_settings

BASE = "https://hub.fabrikam.net/sites/help/SitePages/"


def _load(
    tmp_path: Path, base: str | None, text: str | None = None, name: str = "guides.yaml",
) -> tuple[HelpGuides | None, list[Finding]]:
    if text is not None:
        (tmp_path / "guides.yaml").write_text(text, encoding="utf-8", newline="\n")
    return load_help_guides(HelpSettings(base, name, tmp_path))


def _only(result: tuple[HelpGuides | None, list[Finding]]) -> tuple[FindingCode, str]:
    guides, findings = result
    assert guides is None
    assert len(findings) == 1
    assert findings[0].severity == "error"
    return findings[0].code, findings[0].message


def test_both_keys_unset_is_off_with_no_findings() -> None:
    assert load_help_guides(HelpSettings(None, None, None)) == (None, [])


def test_a_valid_pair_joins_each_leaf_to_the_base(tmp_path: Path) -> None:
    guides, findings = _load(tmp_path, BASE, "risk-open: Review-risk-controls.aspx\n")
    assert findings == []
    assert isinstance(guides, HelpGuides)
    assert guides.urls == {"risk-open": BASE + "Review-risk-controls.aspx"}


def test_a_base_without_a_trailing_slash_is_joined_with_exactly_one(tmp_path: Path) -> None:
    guides, _ = _load(tmp_path, BASE.rstrip("/"), "k: a.aspx\n")
    assert guides is not None
    assert guides.urls == {"k": BASE + "a.aspx"}


def test_a_relative_guides_path_resolves_against_the_env_file_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    guides, findings = _load(tmp_path, BASE, "k: a.aspx\n")
    assert findings == []
    assert guides is not None
    assert guides.urls == {"k": BASE + "a.aspx"}


def test_a_leaf_is_percent_encoded(tmp_path: Path) -> None:
    guides, _ = _load(tmp_path, BASE, "a: Review a risk.aspx\nb: A'B#C.aspx\n")
    assert guides is not None
    assert guides.urls["a"] == BASE + "Review%20a%20risk.aspx"
    assert "'" not in guides.urls["b"]
    assert "#" not in guides.urls["b"]


@pytest.mark.parametrize(("base", "guides_file", "missing"), [
    (BASE, None, "DBMLSP_HELP_GUIDES"),
    (None, "guides.yaml", "DBMLSP_HELP_BASE_URL"),
])
def test_only_one_key_set_is_refused_naming_the_other(
    tmp_path: Path, base: str | None, guides_file: str | None, missing: str,
) -> None:
    code, message = _only(load_help_guides(HelpSettings(base, guides_file, tmp_path)))
    assert code is FindingCode.FORM_HELP_SETTING_INCOMPLETE
    assert missing in message


@pytest.mark.parametrize("base", [
    "http://hub.fabrikam.net/", "https://<tenant>/p/", "https://x/REPLACE-ME/",
    "https://hub.example.com/p/", "https://hub.contoso.invalid/p/", "hub.fabrikam.net/p/",
    "https:///p/", "https://hub.fabrikam.net/p/?a=1", "https://hub.fabrikam.net/p/#overview",
])
def test_a_bad_base_url_is_refused(tmp_path: Path, base: str) -> None:
    code, message = _only(_load(tmp_path, base, "k: a.aspx\n"))
    assert code is FindingCode.FORM_HELP_BASE_URL_INVALID
    assert "DBMLSP_HELP_BASE_URL" in message


@pytest.mark.parametrize(
    "page", ["a/b.aspx", "/a.aspx", "https://x/a.aspx", "mailto:a@b", "''", "3", "null"],
)
def test_a_bad_page_is_refused_naming_the_map_key(tmp_path: Path, page: str) -> None:
    code, message = _only(_load(tmp_path, BASE, f"bad-key: {page}\n"))
    assert code is FindingCode.FORM_HELP_PAGE_INVALID
    assert "bad-key" in message


@pytest.mark.parametrize("text", ["", "- a\n- b\n", "a: 1\na: 2\n", "{}: x\n", "a: [\n"])
def test_a_malformed_map_file_is_refused_with_its_path(tmp_path: Path, text: str) -> None:
    code, message = _only(_load(tmp_path, BASE, text))
    assert code is FindingCode.FORM_HELP_PAGE_INVALID
    assert "guides.yaml" in message


def test_a_missing_map_file_is_refused_with_its_path(tmp_path: Path) -> None:
    code, message = _only(_load(tmp_path, BASE, None, name="absent.yaml"))
    assert code is FindingCode.FORM_HELP_PAGE_INVALID
    assert "absent.yaml" in message


def test_resolve_env_settings_returns_help_settings_from_the_file(tmp_path: Path) -> None:
    env = tmp_path / "dbml-sharepoint.env"
    env.write_text(
        f"DBMLSP_HELP_BASE_URL={BASE}\nDBMLSP_HELP_GUIDES=guides.yaml\n",
        encoding="utf-8", newline="\n",
    )
    *_, help_settings = resolve_env_settings(env, None, None, None, None, None, None)
    assert help_settings == HelpSettings(BASE, "guides.yaml", tmp_path)


def test_a_flag_free_run_with_no_file_returns_empty_help_settings() -> None:
    *_, help_settings = resolve_env_settings(None, None, None, None, None, None, None)
    assert help_settings == HelpSettings(None, None, None)
