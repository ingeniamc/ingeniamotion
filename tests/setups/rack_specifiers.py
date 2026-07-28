import platform
from pathlib import Path

from ingenialink.dictionary import Interface
from summit_testing_framework.jenkins.pytest_config import PyTestConfig
from summit_testing_framework.setups.specifier_container import SpecifierContainer
from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
    VersionConfig,
)

import summit_drives_ci_configs.config_files as config_files


def dist_path(p: str) -> Path:
    """Converts a path string to a Path object, handling platform-specific nuances.

    Args:
        p: A string representing the path.

    Returns:
        A Path object corresponding to the given path string.
    """
    if platform.system().lower() == "windows":
        return Path(p)
    else:
        # Convert //server/... to /server/...
        if p.startswith("//"):
            p = "/" + p.lstrip("/")
        return Path(p)


__EXECUTION_POLICY_KEY: str = "execution_policy"
__TEST_CONFIGS_KEY: str = "test_configs"

ETH_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.ETH,
        version_configs={
            "2.4.0": VersionConfig.from_version(
                version="2.4.0",
                config_file=config_files.EVE_XCR_C_2_1_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "weekends",
                    __TEST_CONFIGS_KEY: {
                        "ETH_TEST_SESSIONS": PyTestConfig(
                            markers="ethernet",
                            run_test_stage_uid="ethernet_everest_2.4.0",
                            stage_name="Ethernet Everest - FW. 2.4.0",
                        )
                    },
                },
            ),
            "2.8.1": VersionConfig.from_version(
                version="2.8.1",
                config_file=config_files.EVE_XCR_C_2_8_1_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "weekends",
                    __TEST_CONFIGS_KEY: {
                        "ETH_TEST_SESSIONS": PyTestConfig(
                            markers="ethernet",
                            run_test_stage_uid="ethernet_everest_2.8.1",
                            stage_name="Ethernet Everest - FW. 2.8.1",
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
                config_file=config_files.CAP_XCR_C_2_2_0_CONFIG,
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
            "2.10.0": VersionConfig.from_version(
                version="2.10.0",
                config_file=config_files.CAP_XCR_C_2_2_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    # Disabled pending INGK-982
                    __EXECUTION_POLICY_KEY: "never",
                    __TEST_CONFIGS_KEY: {
                        "ETH_TEST_SESSIONS": PyTestConfig(
                            markers="ethernet",
                            run_test_stage_uid="ethernet_capitan_2.10.0",
                            stage_name="Ethernet Capitan - FW. 2.10.0",
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
                config_file=config_files.EVE_XCR_E_2_1_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "weekends",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_everest_2.6.0",
                            stage_name="EtherCAT Everest - FW. 2.6.0",
                        )
                    },
                },
            ),
            "2.8.1": VersionConfig.from_version(
                version="2.8.1",
                config_file=config_files.EVE_XCR_E_2_1_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_everest_2.8.1",
                            stage_name="EtherCAT Everest - FW. 2.8.1",
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
                config_file=config_files.CAP_XCR_E_2_2_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "weekends",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_capitan_2.6.0",
                            stage_name="EtherCAT Capitan - FW. 2.6.0",
                        )
                    },
                },
            ),
            "2.9.0": VersionConfig.from_version(
                version="2.9.0",
                config_file=config_files.CAP_XCR_E_2_9_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="soem",
                            run_test_stage_uid="ethercat_capitan_2.9.0",
                            stage_name="EtherCAT Capitan - FW. 2.9.0",
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
                __EXECUTION_POLICY_KEY: "nightly",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe",
                        run_test_stage_uid="fsoe_phase1_2.7.4",
                        stage_name="Safety Denali Phase I - FW. 2.7.4",
                    )
                },
            },
        ),
        "PHASE2": VersionConfig.from_version(
            version="2.10.0",
            config_file=None,
            dictionary_type=DictionaryType.XDF_V3,
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe or fsoe_phase2",
                        run_test_stage_uid="fsoe_phase2_2.10.0",
                        stage_name="Safety Denali Phase II - FW. 2.10.0",
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
                config_file=config_files.EVE_XCR_C_2_1_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "weekends",
                    __TEST_CONFIGS_KEY: {
                        "CAN_TEST_SESSIONS": PyTestConfig(
                            markers="canopen",
                            run_test_stage_uid="canopen_everest_2.4.0",
                            stage_name="CANopen Everest - FW. 2.4.0",
                        )
                    },
                },
            ),
            "2.8.1": VersionConfig.from_version(
                version="2.8.1",
                config_file=config_files.EVE_XCR_C_2_8_1_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "CAN_TEST_SESSIONS": PyTestConfig(
                            markers="canopen",
                            run_test_stage_uid="canopen_everest_2.8.1",
                            stage_name="CANopen Everest - FW. 2.8.1",
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
                config_file=config_files.CAP_XCR_C_2_2_0_CONFIG,
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
            "2.10.0": VersionConfig.from_version(
                version="2.10.0",
                config_file=config_files.CAP_XCR_C_2_2_0_CONFIG,
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "never",
                    __TEST_CONFIGS_KEY: {
                        "CAN_TEST_SESSIONS": PyTestConfig(
                            markers="canopen",
                            run_test_stage_uid="canopen_capitan_2.10.0",
                            stage_name="CANopen Capitan - FW. 2.10.0",
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
            identifier=PartNumber.EVE_XCR_E, version="2.8.1"
        ),
        ECAT_SETUP.get_specifier_by_identifier_with_version(
            identifier=PartNumber.CAP_XCR_E, version="2.9.0"
        ),
    ],
    extra_data={
        __EXECUTION_POLICY_KEY: "always",
        __TEST_CONFIGS_KEY: {
            "ECAT_TEST_SESSIONS": PyTestConfig(
                markers="soem_multislave",
                run_test_stage_uid="ethercat_multislave",
                stage_name="EtherCAT Multislave",
            )
        },
    },
)

SIRIUS_SETUP = RackServiceConfigSpecifier.from_version_configs(
    part_number=PartNumber.EVS_NET_E,
    interface=Interface.ECAT,
    version_configs={
        "2.10.0": VersionConfig.from_version(
            version="2.10.0",
            config_file=config_files.SIRIUS_EVS_NET_E_2_10_0_CONFIG,
            dictionary_type=DictionaryType.XDF_V3,
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "SIRIUS_TEST_SESSIONS": PyTestConfig(
                        markers="soem and biss_c_flaky",  # https://novantamotion.atlassian.net/browse/INGM-798
                        run_test_stage_uid="sirius_evs_net_e_2.10.0",
                        stage_name="SIRIUS EVS-NET-E Tests - FW. 2.10.0",
                    )
                },
                "configure_encoder_protocol": {"protocol": "ssi", "resolution": 17},
            },
        ),
        # BiSS-C tests are flaky on 2.10.0 should pass on 2.11.0
        "2.11.0.005": VersionConfig.from_files(
            version="2.11.0.005",
            firmware=dist_path(
                "//azr-srv-ingfs1//dist//products//i050_summit//i059_evs-net-e//release_candidate//2.11.0.5//evs-net-e_2.11.0.005.lfu"
            ),
            dictionary=dist_path(
                "//azr-srv-ingfs1//dist//products//i050_summit//i059_evs-net-e//release_candidate//2.11.0.5//evs-net-e_eoe_2.11.0.005_v2.xdf"
            ),
            config_file=config_files.SIRIUS_EVS_NET_E_2_11_0_CONFIG,
            dictionary_type=DictionaryType.XDF_V3,
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "INGW_SIRIUS_TEST_SESSIONS": PyTestConfig(
                        markers="soem and biss_c_flaky",
                        run_test_stage_uid="sirius_evs_net_e_2.11.0.005",
                        stage_name="SIRIUS EVS-NET-E Tests - FW. 2.11.0.005",
                    )
                },
                "configure_encoder_protocol": {"protocol": "bis3", "resolution": 17},
            },
        ),
    },
)
