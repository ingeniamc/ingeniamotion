from ingenialink.ethernet.network import VIRTUAL_DRIVE_DICTIONARY

from tests.setups.descriptors import VirtualDriveSetup

TESTS_SETUP = VirtualDriveSetup(ip="127.0.0.1", dictionary=VIRTUAL_DRIVE_DICTIONARY, port=1061)
