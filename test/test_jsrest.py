"""The comment stripper for emitted JavaScript, on literals and on the shared partials."""

import subprocess

import pytest
from _node import NODE

from dbml_sharepoint.jsrest import strip_js_comments
from dbml_sharepoint.templating import script_env


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
