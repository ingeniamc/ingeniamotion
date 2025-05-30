import re
from pathlib import Path

from ingenialink import CanBaudrate, CanDevice
from packaging import version

from ingeniamotion import MotionController
from tests.tests_toolkit.setups import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    SetupDescriptor,
)


def connect_ethernet(mc: MotionController, config: DriveEthernetSetup, alias: str):
    mc.communication.connect_servo_ethernet(config.ip, config.dictionary, alias=alias)


def connect_canopen(mc: MotionController, config: DriveCanOpenSetup, alias: str):
    device = CanDevice(config.device)
    baudrate = CanBaudrate(config.baudrate)
    mc.communication.connect_servo_canopen(
        device,
        config.dictionary,
        config.node_id,
        baudrate,
        config.channel,
        alias=alias,
    )


def connect_soem(mc: MotionController, config: DriveEcatSetup, alias: str):
    mc.communication.connect_servo_ethercat(
        config.ifname,
        config.slave,
        config.dictionary,
        alias,
    )


def connect_to_servo_with_protocol(mc: MotionController, descriptor: SetupDescriptor, alias: str):
    if isinstance(descriptor, DriveEcatSetup):
        connect_soem(mc, descriptor, alias)
    elif isinstance(descriptor, DriveCanOpenSetup):
        connect_canopen(mc, descriptor, alias)
    elif isinstance(descriptor, DriveEthernetSetup):
        connect_ethernet(mc, descriptor, alias)
    else:
        raise NotImplementedError


def _read_fw_version(alias: str, motion_controller: MotionController):
    _, _, fw_version, _ = motion_controller.configuration.get_drive_info_coco_moco(servo=alias)
    return fw_version


def is_fw_already_uploaded(alias: str, mc: MotionController, firmware_file: Path) -> bool:
    current_fw_version = _read_fw_version(alias=alias, motion_controller=mc)[0]
    match = re.search(r"_(\d+\.\d+\.\d+)", firmware_file.stem)
    if match is None:
        return False
    file_fw_version = match.group(1)
    try:
        return version.parse(file_fw_version) == version.parse(current_fw_version)
    except version.InvalidVersion:
        return False


def load_firmware_with_protocol(mc: MotionController, descriptor: SetupDescriptor, alias: str):
    if is_fw_already_uploaded(alias=alias, mc=mc, firmware_file=descriptor.fw_file):
        return
    if isinstance(descriptor, DriveEcatSetup):
        mc.communication.load_firmware_ecat(
            ifname=descriptor.ifname,
            fw_file=descriptor.fw_file.as_posix(),
            slave=descriptor.slave,
            boot_in_app=descriptor.boot_in_app,
        )
    elif isinstance(descriptor, DriveCanOpenSetup):
        mc.communication.load_firmware_canopen(fw_file=descriptor.fw_file.as_posix(), servo=alias)
    elif isinstance(descriptor, DriveEthernetSetup):
        mc.communication.load_firmware_ethernet(
            ip=descriptor.ip, fw_file=descriptor.fw_file.as_posix()
        )
    else:
        raise NotImplementedError(
            f"Firmware loading not implemented for descriptor {type(descriptor)}"
        )
