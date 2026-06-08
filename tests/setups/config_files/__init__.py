from pathlib import Path

_CONFIG_FILES_DIR: Path = Path(__file__).parent

# EtherCAT config files
EVE_XCR_E_CONFIG: Path = _CONFIG_FILES_DIR / "ethercat" / "eve_xcr_e.xcf"
CAP_XCR_E_2_2_0_CONFIG: Path = _CONFIG_FILES_DIR / "ethercat" / "cap_xcr_e.2.2.0.xcf"
CAP_XCR_E_2_9_0_CONFIG: Path = _CONFIG_FILES_DIR / "ethercat" / "cap_xcr_e_2.9.0.xcf"

# CANopen config files
EVE_XCR_C_CONFIG: Path = _CONFIG_FILES_DIR / "canopen" / "eve_xcr_c.xcf"
CAP_XCR_C_CONFIG: Path = _CONFIG_FILES_DIR / "canopen" / "cap_xcr_c.xcf"
