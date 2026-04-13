from pathlib import Path

from ingenialink.dictionary import Interface
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

ETH_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.ETH,
        config_file=_config_files.EVE_XCR_C_CONFIG,
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.ETH,
        config_file=_config_files.CAP_XCR_C_CONFIG,
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
    ),
})

ECAT_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_E: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_E,
        interface=Interface.ECAT,
        config_file=_config_files.EVE_XCR_E_CONFIG,
        version="2.6.0",
        dictionary_type=DictionaryType.XDF_V2,
    ),
    PartNumber.CAP_XCR_E: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_E,
        interface=Interface.ECAT,
        config_file=_config_files.CAP_XCR_E_CONFIG,
        version="2.6.0",
        dictionary_type=DictionaryType.XDF_V2,
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
        ),
    },
)


CAN_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.CAN,
        config_file=_config_files.EVE_XCR_C_CONFIG,
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.CAN,
        config_file=_config_files.CAP_XCR_C_CONFIG,
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
    ),
})


ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier.create(
    specifiers=[
        ECAT_SETUP.get_specifier_by_identifier(PartNumber.EVE_XCR_E),
        ECAT_SETUP.get_specifier_by_identifier(PartNumber.CAP_XCR_E),
    ],
)
