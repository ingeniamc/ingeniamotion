import sys
import os
import time
import json
import argparse
import ingenialogger
from ping3 import ping

sys.path.append('./')

from ingeniamotion import MotionController
from ingeniamotion.exceptions import IMException
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.exceptions import ILError, ILFirmwareLoadError

logger = ingenialogger.get_logger('load_FWs')
ingenialogger.configure_logger()
dirname = os.path.dirname(__file__)


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('comm', help='communication protocol',
                        choices=['canopen', 'soem', 'eoe'])
    return parser.parse_args()


def load_can(drive_conf, mc):
    mc.communication.connect_servo_canopen(
        CAN_DEVICE(drive_conf["device"]),
        drive_conf["dictionary"],
        drive_conf["eds"],
        drive_conf["node_id"],
        CAN_BAUDRATE(drive_conf["baudrate"]),
        channel=drive_conf["channel"]
    )
    logger.info("Drive connected. %s, node: %d, baudrate: %d, channel: %d",
                drive_conf["device"],
                drive_conf["node_id"],
                drive_conf["baudrate"],
                drive_conf["channel"])
    try:
        mc.communication.load_firmware_canopen(
            drive_conf["fw_file"])
    except ILFirmwareLoadError as e:
        # TODO Remove try-except when issue INGK-438 will fix
        if str(e) != "Could not recover drive":
            raise e
    logger.info("FW updated. %s, node: %d, baudrate: %d, channel: %d",
                drive_conf["device"],
                drive_conf["node_id"],
                drive_conf["baudrate"],
                drive_conf["channel"])
    mc.communication.disconnect()


def load_ecat(drive_conf, mc):
    if_name = mc.communication.get_ifname_from_interface_ip(drive_conf["ip"])
    mc.communication.load_firmware_ecat(
        if_name,
        drive_conf["fw_file"],
        drive_conf["slave"],
        boot_in_app=drive_conf["boot_in_app"])
    logger.info("FW updated. ifname: %s, slave: %d",
                if_name,
                drive_conf["slave"])


def ping_check(target_ip):
    # TODO Stop use this function when issue INGM-104 will done
    time.sleep(5)
    initial_time = time.time()
    timeout = 180
    success_num_pings = 3
    num_pings = 0
    detected = False
    while (time.time() - initial_time) < timeout and not detected:
        aux_ping = ping(target_ip)
        if type(aux_ping) == float:
            num_pings += 1
        if num_pings >= success_num_pings:
            detected = True
        time.sleep(1)
    if not detected:
        logger.error("drive ping not detected", drive=target_ip)


def load_eth(drive_conf, mc):
    try:
        mc.communication.connect_servo_ethernet(
            drive_conf["ip"],
            drive_conf["dictionary"]
        )
        logger.info("Drive connected. IP: %s",
                    drive_conf["ip"])
        mc.communication.boot_mode_and_load_firmware_ethernet(
            drive_conf["fw_file"])
    except ILError:
        logger.warning("Drive does not respond. It may already be in boot mode.",
                       drive=drive_conf["ip"])
        mc.communication.load_firmware_ethernet(
            drive_conf["ip"],
            drive_conf["fw_file"]
        )
    ping_check(drive_conf["ip"])
    logger.info("FW updated. IP: %s",
                drive_conf["ip"])


def main(comm, config):
    mc = MotionController()
    servo_list = config[comm]
    for index, servo_conf in enumerate(servo_list):
        logger.info("Upload FW comm %s, index: %d", comm, index)
        try:
            if comm == "canopen":
                load_can(servo_conf, mc)
            if comm == "soem":
                load_ecat(servo_conf, mc)
            if comm == "eoe":
                load_eth(servo_conf, mc)
        except (ILError, IMException) as e:
            logger.exception(e)
            logger.error("Error in FW update. comm %s, index: %d", comm, index)


if __name__ == '__main__':
    args = setup_command()
    with open(os.path.join(dirname, "config.json")) as file:
        config_json = json.load(file)
    main(args.comm, config_json)
