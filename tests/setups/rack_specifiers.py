from pathlib import Path

from ingenialink.dictionary import Interface
from summit_testing_framework.jenkins.pytest_config import PyTestConfig
from summit_testing_framework.pytest_helpers.import_helpers import import_module_from_local_path
from summit_testing_framework.setups.specifier_container import SpecifierContainer
from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
    VersionConfig,
)

# This file is used to export the specifiers to a JSON. Since tests is not a package,
# we need to import the config files using a helper function to be able to access them
_config_files = import_module_from_local_path(
    module_name="config_files", module_path=Path(__file__).parent / "config_files"
)
assert _config_files is not None

__EXECUTION_POLICY_KEY: str = "execution_policy"
__TEST_CONFIGS_KEY: str = "test_configs"

ETH_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.ETH,
        version_configs={
            "2.4.0": VersionConfig.from_version(
                version="2.4.0",
                config_file=_config_files.EVE_XCR_C_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ETH_TEST_SESSIONS": PyTestConfig(
                            markers="ethernet",
                            run_test_stage_uid="ethernet_everest_2.4.0",
                            stage_name="Ethernet Everest - FW. 2.4.0",
                        )
                    },
                },
            ),
        },
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.ETH,
        version_configs={
            "2.4.0": VersionConfig.from_version(
                version="2.4.0",
                config_file=_config_files.CAP_XCR_C_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    # Disabled pending INGK-982
                    __EXECUTION_POLICY_KEY: "never",
                    __TEST_CONFIGS_KEY: {
                        "ETH_TEST_SESSIONS": PyTestConfig(
                            markers="ethernet",
                            run_test_stage_uid="ethernet_capitan_2.4.0",
                            stage_name="Ethernet Capitan - FW. 2.4.0",
                        )
                    },
                },
            ),
        },
    ),
})

ECAT_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_E: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.EVE_XCR_E,
        interface=Interface.ECAT,
        version_configs={
            "2.6.0": VersionConfig.from_version(
                version="2.6.0",
                config_file=_config_files.EVE_XCR_E_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_everest_2.6.0",
                            stage_name="EtherCAT Everest - FW. 2.6.0",
                        )
                    },
                },
            ),
        },
    ),
    PartNumber.CAP_XCR_E: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.CAP_XCR_E,
        interface=Interface.ECAT,
        version_configs={
            "2.6.0": VersionConfig.from_version(
                version="2.6.0",
                config_file=_config_files.CAP_XCR_E_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_capitan_2.6.0",
                            stage_name="EtherCAT Capitan - FW. 2.6.0",
                        )
                    },
                },
            ),
        },
    ),
})

ECAT_DEN_S_NET_E_SETUP = RackServiceConfigSpecifier.from_version_configs(
    part_number=PartNumber.DEN_S_NET_E,
    interface=Interface.ECAT,
    version_configs={
        "PHASE1": VersionConfig.from_version(
            version="2.7.4",
            config_file=None,
            dictionary_type=DictionaryType.XDF_V2,
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe",
                        run_test_stage_uid="fsoe_phase1_2.7.4",
                        stage_name="Safety Denali Phase I - FW. 2.7.4",
                    )
                },
            },
        ),
        "PHASE2": VersionConfig.from_files(
            version="2.9.0.16",
            config_file=None,
            firmware=Path(
                "//azr-srv-ingfs1/dist/products/i050_summit/i056_den-s-net-e/release_candidate/2.9.0.16/den-s-net-e_2.9.0.lfu"
            ),
            dictionary=Path(
                "//azr-srv-ingfs1/dist/products/i050_summit/i056_den-s-net-e/release_candidate/2.9.0.16/den-s-net-e_2.9.0.016.xdf3"
            ),
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe or fsoe_phase2",
                        run_test_stage_uid="fsoe_phase2_2.9.0",
                        stage_name="Safety Denali Phase II - FW. 2.9.0",
                    )
                },
            },
        ),
    },
)


CAN_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.CAN,
        version_configs={
            "2.4.0": VersionConfig.from_version(
                version="2.4.0",
                config_file=_config_files.EVE_XCR_C_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "CAN_TEST_SESSIONS": PyTestConfig(
                            markers="canopen",
                            run_test_stage_uid="canopen_everest_2.4.0",
                            stage_name="CANopen Everest - FW. 2.4.0",
                        )
                    },
                },
            ),
        },
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.CAN,
        version_configs={
            "2.4.0": VersionConfig.from_version(
                version="2.4.0",
                config_file=_config_files.CAP_XCR_C_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "CAN_TEST_SESSIONS": PyTestConfig(
                            markers="canopen",
                            run_test_stage_uid="canopen_capitan_2.4.0",
                            stage_name="CANopen Capitan - FW. 2.4.0",
                        )
                    },
                },
            ),
        },
    ),
})


ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier.create(
    identifier="ECAT_MULTISLAVE",
    specifiers=[
        ECAT_SETUP.get_specifier_by_identifier_with_version(
            identifier=PartNumber.EVE_XCR_E, version="2.6.0"
        ),
        ECAT_SETUP.get_specifier_by_identifier_with_version(
            identifier=PartNumber.CAP_XCR_E, version="2.6.0"
        ),
    ],
    extra_data={
        __EXECUTION_POLICY_KEY: "always",
        __TEST_CONFIGS_KEY: {
            "ECAT_TEST_SESSIONS": PyTestConfig(
                markers="soem_multislave",
                run_test_stage_uid="ethercat_multislave_2.6.0",
                stage_name="EtherCAT Multislave - FW. 2.6.0",
            )
        },
    },
)
