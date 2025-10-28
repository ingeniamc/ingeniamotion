from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier
from tests.dictionaries import VIRTUAL_DRIVE_XDF_PATH

TESTS_SETUP = VirtualDriveSpecifier(
    ip="127.0.0.1", port=1061, dictionary_path=VIRTUAL_DRIVE_XDF_PATH
)
