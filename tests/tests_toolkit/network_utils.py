from ingenialink import CanBaudrate, CanDevice

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


def load_firmware_with_protocol(mc: MotionController, descriptor: SetupDescriptor):
    if isinstance(descriptor, DriveEcatSetup):
        mc.communication.load_firmware_ecat(
            ifname=descriptor.ifname,
            fw_file=descriptor.fw_file,
            slave=descriptor.slave,
            boot_in_app=descriptor.boot_in_app,
        )
    elif isinstance(descriptor, DriveCanOpenSetup):
        mc.communication.load_firmware_canopen(fw_file=descriptor.fw_file)
    elif isinstance(descriptor, DriveEthernetSetup):
        mc.communication.load_firmware_ethernet(ip=descriptor.ip, fw_file=descriptor.fw_file)
    else:
        raise NotImplementedError(
            f"Firmware loading not implemented for descriptor {type(descriptor)}"
        )
