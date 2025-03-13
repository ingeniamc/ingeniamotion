from tests import dictionaries
from tests.setups.descriptors import VirtualDriveSetup

TESTS_SETUP = VirtualDriveSetup(
    ip="127.0.0.1", dictionary=dictionaries.VIRTUAL_DRIVE_XDF_PATH, port=1061
)
