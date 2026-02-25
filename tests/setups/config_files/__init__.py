from pathlib import Path

_CONFIG_FILES_DIR: Path = Path(__file__).parent

# EtherCAT config files
EVE_XCR_E_CONFIG: Path = _CONFIG_FILES_DIR / "ethercat" / "eve_xcr_e.xcf"
CAP_XCR_E_CONFIG: Path = _CONFIG_FILES_DIR / "ethercat" / "cap_xcr_e.xcf"

# CANopen config files
EVE_XCR_C_CONFIG: Path = _CONFIG_FILES_DIR / "canopen" / "eve_xcr_c.xcf"
CAP_XCR_C_CONFIG: Path = _CONFIG_FILES_DIR / "canopen" / "cap_xcr_c.xcf"
