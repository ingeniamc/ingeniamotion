from pathlib import Path

__dictionaries_root_path = absolute_module_path = Path(__file__).parent
PATH = __dictionaries_root_path.as_posix()
VIRTUAL_DRIVE_XDF_PATH = (__dictionaries_root_path / "virtual_drive.xdf").as_posix()
SAMPLE_SAFE_DICTIONARY = (__dictionaries_root_path / "den-s-net-e_dev34d1f2_v3.xdf").as_posix()
