# test/regen_golden.py
"""Regenerate the committed deploy golden, every piece of it::

    uv run python test/regen_golden.py

Its own module, and not a test one, because this entry point used to sit in
the middle of test_jsgen.py with dozens of tests after it, where the one thing
that can go wrong is somebody reading it as dead code and deleting the
documented recipe with it (#172).

It writes every piece under `expected/simple-deploy/`, the manifest that
covers the whole script, and removes a piece the script no longer emits, so
one command leaves the directory as the test expects to find it. The pieces
come from `test_jsgen_golden.split_deploy_js` and the script from
`test_jsgen._generate_simple_js`, both of which the test reads too, so the
recipe and the assertion cannot drift.

Regeneration stays a separate, explicit act rather than a `--snapshot-update`
flag on the test run; the friction is the point.
"""

from _paths import write_golden
from test_jsgen import _generate_simple_js
from test_jsgen_golden import MANIFEST, SEGMENT_DIR, manifest_text, split_deploy_js


def main() -> None:
    js = _generate_simple_js()
    pieces = split_deploy_js(js)
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in pieces.items():
        write_golden(SEGMENT_DIR / name, text)
    write_golden(MANIFEST, manifest_text(js, pieces))
    for stale in sorted(SEGMENT_DIR.glob("*.js")):
        if stale.name not in pieces:
            stale.unlink()
            print(f"removed {stale}")  # noqa: T201
    print(f"wrote {len(pieces)} pieces and the manifest under {SEGMENT_DIR}")  # noqa: T201


if __name__ == "__main__":
    main()
