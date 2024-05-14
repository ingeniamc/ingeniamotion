import platform

import pytest


@pytest.mark.virtual
def test_import_fsoe_master():
    if platform.system() != "Windows":
        pytest.skip("Currently it can only be tested on Windows")
    try:
        import fsoe_master
    except ModuleNotFoundError:
        pytest.fail("Cannot import the fsoe_master module.")
