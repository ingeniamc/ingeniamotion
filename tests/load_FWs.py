import sys
import os
import time
import json
import argparse
import ingenialogger
from ping3 import ping

sys.path.append("./")

from ingeniamotion import MotionController
from ingeniamotion.exceptions import IMException
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.exceptions import ILError, ILFirmwareLoadError

logger = ingenialogger.get_logger("load_FWs")
ingenialogger.configure_logger(level=ingenialogger.LoggingLevel.INFO)
dirname = os.path.dirname(__file__)


def setup_command():
    parser = argparse.ArgumentParser(description="Run feedback test")
    parser.add_argument("comm", help="communication protocol", choices=["canopen", "soem", "eoe"])
    return parser.parse_args()


def load_can(drive_conf, mc):
    # Number of reattempts for trying the CAN bootloader
    BL_NUM_OF_REATTEMPTS = 2

    # Timings, in seconds
    SLEEP_TIME_AFTER_ATTEMP = 5.0
    SLEEP_TIME_AFTER_BL = 5.0
    TIMEOUT_NEW_FW_DETECT = 30.0
    SLEEP_TIME_NEW_FW_DETECT = 5.0

    for attempt in range(BL_NUM_OF_REATTEMPTS):
        logger.info(f"CAN boot attempt {attempt + 1} of {BL_NUM_OF_REATTEMPTS}")
        try:
            mc.communication.connect_servo_canopen(
                CAN_DEVICE(drive_conf["device"]),
                drive_conf["dictionary"],
                drive_conf["eds"],
                drive_conf["node_id"],
                CAN_BAUDRATE(drive_conf["baudrate"]),
                channel=drive_conf["channel"],
            )
            logger.info(
                "Drive connected. %s, node: %d, baudrate: %d, channel: %d",
                drive_conf["device"],
                drive_conf["node_id"],
                drive_conf["baudrate"],
                drive_conf["channel"],
            )
        except Exception as e:
            logger.info(f"Couldn't connect to the drive: {e}")
            continue

        try:
            mc.communication.load_firmware_canopen(drive_conf["fw_file"])

            # Reaching this means that FW was correctly flashed
            break

        except ILFirmwareLoadError as e:
            logger.error(f"CAN boot error: {e}")
            time.sleep(SLEEP_TIME_AFTER_ATTEMP)

        finally:
            try:
                mc.communication.disconnect()
            except Exception as e:
                logger.error(f"Error when disconnection from drive: {e}")

    logger.info(
        "FW updated. %s, node: %d, baudrate: %d, channel: %d",
        drive_conf["device"],
        drive_conf["node_id"],
        drive_conf["baudrate"],
        drive_conf["channel"],
    )

    logger.info(f"Waiting {SLEEP_TIME_AFTER_BL} seconds for trying to connect")
    time.sleep(SLEEP_TIME_AFTER_BL)

    # Check whether the new FW is present
    detected = False
    ini_time = time.perf_counter()
    while (time.perf_counter() - ini_time) <= TIMEOUT_NEW_FW_DETECT and not detected:
        try:
            mc.communication.connect_servo_canopen(
                CAN_DEVICE(drive_conf["device"]),
                drive_conf["dictionary"],
                drive_conf["eds"],
                drive_conf["node_id"],
                CAN_BAUDRATE(drive_conf["baudrate"]),
                channel=drive_conf["channel"],
            )
            # Reaching this point means we are connected
            detected = True
            logger.info("New FW detected after: {:.1f} s".format(time.perf_counter() - ini_time))
            mc.communication.disconnect()
        except Exception as e:
            # When cannot connect
            time.sleep(SLEEP_TIME_NEW_FW_DETECT)

    if not detected:
        raise Exception("New FW not detected")


def load_ecat(drive_conf, mc):
    if_name = mc.communication.get_ifname_from_interface_ip(drive_conf["ip"])
    mc.communication.load_firmware_ecat(
        if_name, drive_conf["fw_file"], drive_conf["slave"], boot_in_app=drive_conf["boot_in_app"]
    )
    logger.info("FW updated. ifname: %s, slave: %d", if_name, drive_conf["slave"])


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
        mc.communication.connect_servo_ethernet(drive_conf["ip"], drive_conf["dictionary"])
        logger.info("Drive connected. IP: %s", drive_conf["ip"])
        mc.communication.boot_mode_and_load_firmware_ethernet(drive_conf["fw_file"])
    except ILError:
        logger.warning(
            "Drive does not respond. It may already be in boot mode.", drive=drive_conf["ip"]
        )
        mc.communication.load_firmware_ethernet(drive_conf["ip"], drive_conf["fw_file"])
    ping_check(drive_conf["ip"])
    logger.info("FW updated. IP: %s", drive_conf["ip"])


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


if __name__ == "__main__":
    args = setup_command()
    with open(os.path.join(dirname, "config.json")) as file:
        config_json = json.load(file)
    main(args.comm, config_json)
