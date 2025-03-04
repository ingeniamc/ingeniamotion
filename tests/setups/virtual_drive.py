from tests.conftest import dynamic_import

dictionaries = dynamic_import(module_path="tests/dictionaries/__init__", import_name=None)
VirtualDriveSetup = dynamic_import(
    module_path="tests/setups/descriptors.py", import_name="VirtualDriveSetup"
)

TESTS_SETUP = VirtualDriveSetup(
    ip="127.0.0.1", dictionary=dictionaries.VIRTUAL_DRIVE_XDF_PATH, port=1061
)
