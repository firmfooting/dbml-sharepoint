# test/test_yaml_scanner_drift.py
"""Pins the ruamel.yaml method that `_Scanner.scan_flow_scalar_non_spaces` copies."""

import hashlib
import inspect

from dbml_sharepoint.model.yamlio import _Scanner

# The copy marks a surrogate escape exactly; on failure, re-diff it against the new source.
_UPSTREAM_SHA256 = "e4731d7dfdfb215602b5073342a8772ba823c18e02e5b9fe66ae2ccc1fd2f2a8"


def test_the_copied_scanner_method_still_matches_ruamel_yaml() -> None:
    source = inspect.getsource(_Scanner.__mro__[1].scan_flow_scalar_non_spaces)
    assert hashlib.sha256(source.encode()).hexdigest() == _UPSTREAM_SHA256
