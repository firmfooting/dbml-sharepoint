"""The comment stripper, and the shared prelude it strips, in every flavour."""

import hashlib
import itertools
import re
import subprocess

import pytest
from _paths import GOLDEN_DEPLOYER_VERSION

from dbml_sharepoint import jsrest
from dbml_sharepoint.jsrest import Site, prelude, strip_js_comments, wrap
from dbml_sharepoint.templating import script_env
from dbml_sharepoint.testing.node import NODE


@pytest.mark.parametrize(("source", "expected"), [
    ("const a = 'https://x'; // tail\n", "const a = 'https://x';\n"),
    ("  // whole line\nconst b = 1;\n", "const b = 1;\n"),
    ("const t = `${'//'} //`;\n", "const t = `${'//'} //`;\n"),
    ("const R = /\\/_layouts\\/15\\/throttle\\.htm(\\?|$)/i;\n",
     "const R = /\\/_layouts\\/15\\/throttle\\.htm(\\?|$)/i;\n"),
    ("const c = 1 /* x */ + 2;\n", "const c = 1  + 2;\n"),
    ("const d = a / b / c; // ratio\n", "const d = a / b / c;\n"),
    ('const e = "a // b /* c */";\n', 'const e = "a // b /* c */";\n'),
    ("const f = `${`${{ a: '//' }.a}`} /* k */`; // x\n",
     "const f = `${`${{ a: '//' }.a}`} /* k */`;\n"),
    ("  /* one\n     two */\nconst g = 1;\n", "const g = 1;\n"),
    ("a = 1 /*\n*/ b = 2;\n", "a = 1\n b = 2;\n"),
    ("return/**/x;\n", "return x;\n"),
    ("if (x) return /[/]\\//.test(s); // y\n", "if (x) return /[/]\\//.test(s);\n"),
    ("const h = (a + b) / 2 / c;\n", "const h = (a + b) / 2 / c;\n"),
    ("const i = 'it\\'s // here';\n", "const i = 'it\\'s // here';\n"),
    ("\nconst j = 1;\n\n", "\nconst j = 1;\n\n"),
    ("if (x) /\\/\\//.test(s) && go();\n", "if (x) /\\/\\//.test(s) && go();\n"),
    ("a = n-- / 2 + `a/b`;\nconst u = `https://x/${p}`;\n",
     "a = n-- / 2 + `a/b`;\nconst u = `https://x/${p}`;\n"),
    ("i++ / 2; // half\n", "i++ / 2;\n"),
    ("arr.of / 2; // c\n", "arr.of / 2;\n"),
    ("f(x) / 2; // c\n", "f(x) / 2;\n"),
    ("throw /https?:\\/\\//; // c\n", "throw /https?:\\/\\//;\n"),
    ("await /a:\\/\\//.exec(s); // c\n", "await /a:\\/\\//.exec(s);\n"),
    ("yield /a:\\/\\//; // c\n", "yield /a:\\/\\//;\n"),
    ("new /a:\\/\\//; // c\n", "new /a:\\/\\//;\n"),
    ("delete /a:\\/\\//.x; // c\n", "delete /a:\\/\\//.x;\n"),
    ("x instanceof /a:\\/\\//; // c\n", "x instanceof /a:\\/\\//;\n"),
])
def test_comments_go_and_literals_stay(source: str, expected: str) -> None:
    assert strip_js_comments(source) == expected


def test_an_unterminated_string_is_refused() -> None:
    with pytest.raises(ValueError, match="line 1"):
        strip_js_comments("const a = 'open;\n")


@pytest.mark.parametrize("source", [
    "const a = 1;\nconst t = `open ${x}\n",
    "const a = 1;\nconst r = /open;\n",
    "const a = 1;\nconst s = \"open\nnext\";\n",
    "const a = 1;\n/* open\n",
])
def test_an_unterminated_literal_or_comment_names_its_line(source: str) -> None:
    with pytest.raises(ValueError, match="line 2"):
        strip_js_comments(source)


def no_comment_remains(stripped: str) -> None:
    assert strip_js_comments(stripped) == stripped
    assert not [line for line in stripped.splitlines() if line.lstrip().startswith("//")]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("partial", ["_http.js.j2", "_digest_cached.js.j2", "_odata_read.js.j2",
                                     "_http_batch.js.j2", "_site_guard.js.j2",
                                     "_http_write.js.j2", "_download.js.j2", "_ensure_user.js.j2"])
def test_every_prelude_partial_strips_to_code_node_accepts(partial: str) -> None:
    assert NODE is not None
    stripped = strip_js_comments(script_env().get_template(partial).render())
    # Wrapped in an async function so the site guard's return parses; node --check is the arbiter.
    proc = subprocess.run(  # noqa: S603
        [NODE, "--check", "--input-type=commonjs"],
        input=f"(async () => {{\n{stripped}\n}})();\n",
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    no_comment_remains(stripped)


def test_the_throttle_page_regex_survives_the_transport_partial() -> None:
    stripped = strip_js_comments(script_env().get_template("_http.js.j2").render())
    assert "const THROTTLE_PAGE = /\\/_layouts\\/15\\/throttle\\.htm(\\?|$)/i;" in stripped


WRITE_VERB = re.compile(r"\b(POST|MERGE|PATCH|PUT|DELETE)\b")
SITE_URL = "https://t.example/sites/T"
SITES: list[Site] = ["page-context", "pathname"]
type Flavour = tuple[bool, bool, Site, str | None]
#: Every legal (writes, batch) pair, under both site modes, with and without an expected site.
FLAVOURS: list[Flavour] = [
    (writes, batch, site, expected)
    for (writes, batch), site, expected in itertools.product(
        [(False, False), (True, False), (True, True)], SITES, [None, SITE_URL])
]


def between_sentinels(text: str) -> str:
    return "\n".join(text.strip("\n").split("\n")[1:-1])


@pytest.mark.parametrize("site", SITES)
def test_the_read_flavour_has_no_write_verb_and_no_contextinfo(site: Site) -> None:
    text = prelude(writes=False, site=site, expected_site=SITE_URL)
    assert not WRITE_VERB.search(text)
    assert not re.search(r"contextinfo|X-RequestDigest|X-HTTP-Method|getDigest|spHeaders", text)


def test_a_read_flavour_cannot_batch() -> None:
    with pytest.raises(ValueError, match="batch needs writes=True"):
        prelude(writes=False, batch=True)
    with pytest.raises(ValueError, match="batch needs writes=True"):
        wrap("", writes=False, batch=True)


def test_the_sentinels_name_the_version_and_the_body_hash() -> None:
    text = prelude(writes=True)
    first, *body, last = text.strip("\n").split("\n")
    digest = hashlib.sha256("\n".join(body).encode()).hexdigest()[:12]
    assert first == f"// sp-rest {GOLDEN_DEPLOYER_VERSION} sha256:{digest} begin"
    assert last == f"// sp-rest {GOLDEN_DEPLOYER_VERSION} sha256:{digest} end"


@pytest.mark.parametrize("flavour", FLAVOURS)
def test_the_prelude_is_comment_free_between_the_sentinels(flavour: Flavour) -> None:
    writes, batch, site, expected = flavour
    no_comment_remains(between_sentinels(
        prelude(writes=writes, batch=batch, site=site, expected_site=expected)))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("flavour", FLAVOURS)
def test_every_flavour_wrapped_passes_node_check(flavour: Flavour) -> None:
    assert NODE is not None
    writes, batch, site, expected = flavour
    proc = subprocess.run(  # noqa: S603
        [NODE, "--check", "--input-type=commonjs"],
        input=wrap("log('INFO', 'body');", writes=writes, batch=batch, site=site,
                   expected_site=expected),
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_wrap_hands_a_rejection_to_the_caller() -> None:
    text = wrap("body();", writes=False)
    assert text.startswith("(async () => {\n// sp-rest ")
    assert text.endswith("\nbody();\n})();\n")
    assert ".catch" not in text


@pytest.mark.parametrize("url", [
    "http://t.example/sites/T", "/sites/T", "https:///sites/T", "t.example/sites/T", "",
])
def test_an_expected_site_that_is_not_https_is_refused(url: str) -> None:
    with pytest.raises(ValueError, match="absolute https:// URL"):
        prelude(writes=False, expected_site=url)


def test_the_expected_site_is_a_json_literal() -> None:
    text = prelude(writes=False, expected_site="https://t.example/sites/It's")
    assert 'const SITE_URL = "https://t.example/sites/It\\u0027s";' in text


def test_the_documented_identifiers_are_the_declared_ones() -> None:
    assert jsrest.__doc__ is not None
    documented = set(re.findall(r"`([\w$]+)`", jsrest.__doc__.split("must not redeclare", 1)[1]))
    declared = {
        name
        for writes, batch, site, expected in FLAVOURS
        for name in re.findall(
            r"^  (?:const|let|var|class|(?:async )?function) ([\w$]+)",
            prelude(writes=writes, batch=batch, site=site, expected_site=expected), re.MULTILINE)
    }
    assert {"log", "fetchWithRetry", "getDigest", "BatchWriter"} <= declared
    assert documented == declared


def test_the_prelude_is_deterministic() -> None:
    assert prelude(writes=True, batch=True) == prelude(writes=True, batch=True)
