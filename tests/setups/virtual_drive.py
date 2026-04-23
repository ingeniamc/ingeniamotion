from summit_testing_framework.jenkins.pytest_config import PyTestConfig
from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

from tests.dictionaries import VIRTUAL_DRIVE_XDF_PATH

VIRTUAL_DRIVE_ETHERNET_SETUP = VirtualDriveSpecifier.from_ethernet(
    dictionary=VIRTUAL_DRIVE_XDF_PATH,
    extra_data={
        "execution_policy": "always",
        "test_configs": {
            "LINUX_DOCKER_TEST_SESSIONS": PyTestConfig(
                markers="virtual",
                run_test_stage_uid="virtual_linux",
                stage_name="Virtual Drive Tests (Linux)",
            ),
            "WIN_DOCKER_TEST_SESSIONS": PyTestConfig(
                markers="virtual",
                run_test_stage_uid="virtual_win",
                stage_name="Virtual Drive Tests (Windows)",
            ),
        },
    },
)
