"""Package-import smoke test. Real tool tests land alongside their
implementations (Day 4+) -- this just confirms the package builds and
imports cleanly, so CI's package-dependent steps have something real to run
against from the moment pyproject.toml exists.
"""

import continuum


def test_package_has_version():
    assert continuum.__version__ == "0.1.0"
