from pathlib import Path

__dictionaries_root_path = absolute_module_path = Path(__file__).parent
PATH = __dictionaries_root_path.as_posix()
VIRTUAL_DRIVE_XDF_PATH = (__dictionaries_root_path / "virtual_drive.xdf").as_posix()
SAMPLE_SAFE_PH1_XDFV3_DICTIONARY = (
    __dictionaries_root_path / "den-s-net-e_devf13ab4_v3.xdf"
).as_posix()
SAMPLE_SAFE_PH2_XDFV3_DICTIONARY = (
    __dictionaries_root_path / "evs-s-net-e_2.9.0.006_v3.xdf"
).as_posix()
SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT = 0x3B00003
