"""Shared pytest configuration for dbml-sharepoint tests."""

import os

from hypothesis import HealthCheck, settings

# Hypothesis's default 200ms-per-example deadline is wall-clock, and this suite
# runs under `-n auto` with up to eight workers competing for the same cores.
# An example that takes 30ms alone can exceed 200ms while seven siblings run,
# so the deadline would fail on LOAD rather than on a slow property -- a flake
# that looks like a real failure and does not reproduce. Nothing here is being
# guarded by it; the properties are cheap.
settings.register_profile(
    "default",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# CI searches harder than the local loop does. Measured on the property file
# alone, serially: 2.0s at the default 100 examples, 3.7s at 200, 8.1s at 500.
# The search space is small -- fourteen operators over shallow trees -- so 500
# buys little for four extra seconds. Under `-n auto` the whole suite goes from
# 6.05s to 6.63s with this profile, which is the number that actually matters.
settings.register_profile("ci", parent=settings.get_profile("default"), max_examples=200)

settings.load_profile("ci" if os.environ.get("CI") else "default")
