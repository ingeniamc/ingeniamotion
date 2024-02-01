import argparse
import json
import os
import time
from functools import partial

import ifaddr
import ingenialogger
from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ping3 import ping

logger = ingenialogger.get_logger("load_FWs")
ingenialogger.configure_logger(level=ingenialogger.LoggingLevel.INFO)
dirname = os.path.dirname(__file__)


def setup_command():
    parser = argparse.ArgumentParser(description="Run feedback test")
    parser.add_argument("comm", help="communication protocol", choices=["canopen", "soem", "eoe"])
    return parser.parse_args()


def connect_can(drive_conf):
    net = CanopenNetwork(
        CAN_DEVICE(drive_conf["device"]),
        drive_conf["channel"],
        CAN_BAUDRATE(drive_conf["baudrate"]),
    )
    servo = net.connect_to_slave(drive_conf["node_id"], drive_conf["dictionary"])
    return net, servo


def load_can(drive_conf):
    # Number of reattempts for trying the CAN bootloader
    BL_NUM_OF_REATTEMPTS = 4

    # Timings, in seconds
    SLEEP_TIME_AFTER_ATTEMP = 5.0
    SLEEP_TIME_AFTER_BL = 5.0
    TIMEOUT_NEW_FW_DETECT = 30.0
    SLEEP_TIME_NEW_FW_DETECT = 5.0

    for attempt in range(BL_NUM_OF_REATTEMPTS):
        logger.info(f"CAN boot attempt {attempt + 1} of {BL_NUM_OF_REATTEMPTS}")
        try:
            net, servo = connect_can(drive_conf)
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

        status_callback = partial(logger.info, "Load firmware status: %s")
        progress_callback = partial(logger.info, "Load firmware progress: %s")
        try:
            net.load_firmware(
                servo.target, drive_conf["fw_file"], status_callback, progress_callback
            )
            # Reaching this means that FW was correctly flashed
            break

        except ILFirmwareLoadError as e:
            logger.error(f"CAN boot error: {e}")
            time.sleep(SLEEP_TIME_AFTER_ATTEMP)

        finally:
            try:
                net.disconnect_from_slave(servo)
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
            net, servo = connect_can(drive_conf)
            # Reaching this point means we are connected
            detected = True
            fw_version = servo.info["firmware_version"]
            logger.info(
                f"New FW detected ({fw_version}) after: {time.perf_counter() - ini_time:.1f} s"
            )
            net.disconnect_from_slave(servo)
        except Exception as e:
            # When cannot connect
            time.sleep(SLEEP_TIME_NEW_FW_DETECT)

    if not detected:
        raise Exception("Could not connect to the drive. FW loading might have failed.")


def load_ecat(drive_conf):
    ifname = None
    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            if ip.is_IPv4 and ip.ip == drive_conf["ip"]:
                ifname = "\\Device\\NPF_{}".format(bytes.decode(adapter.name))
                break
        if ifname is not None:
            break
    net = EthercatNetwork(ifname)
    net.load_firmware(drive_conf["fw_file"], drive_conf["slave"])
    logger.info("FW updated. ifname: %s, slave: %d", drive_conf["ifname"], drive_conf["slave"])


def ping_check(target_ip, timeout=180):
    # TODO Stop use this function when issue INGM-104 will done
    time.sleep(5)
    initial_time = time.time()
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
    return detected


def connect_eth(drive_conf):
    net = EthernetNetwork()
    servo = net.connect_to_slave(drive_conf["ip"], drive_conf["dictionary"])
    return net, servo


def boot_mode(net, servo):
    PASSWORD_FORCE_BOOT_COCO = 0x424F4F54
    try:
        servo.write("DRV_BOOT_COCO_FORCE", PASSWORD_FORCE_BOOT_COCO, subnode=0)
        ftp_ready = ping_check(servo.ip_address, timeout=5)
    except ILError as e:
        logger.debug("Could not enter in boot mode.")
        raise e
    finally:
        logger.debug("Disconnecting from drive.")
        net.disconnect_from_slave(servo)
    if not ftp_ready:
        logger.debug("FTP is not ready.")
        raise ILError("FTP is not ready.")
    else:
        logger.debug("FTP is ready.")


def load_eth(drive_conf):
    net, servo = connect_eth(drive_conf)
    logger.info("Drive connected. IP: %s", drive_conf["ip"])
    try:
        boot_mode(net, servo)
    except ILError as e:
        logger.warning(
            f"Drive does not respond ({e}). It may already be in boot mode.", drive=drive_conf["ip"]
        )
    try:
        net.load_firmware(drive_conf["fw_file"], drive_conf["ip"], "Ingenia", "Ingenia")
    except ILError as e:
        raise Exception(f"Could not load the firmware: {e}")
    detected = ping_check(drive_conf["ip"])
    if not detected:
        logger.info("FW not updated. IP: %s", drive_conf["ip"])
        raise Exception("Could not detect the drive.")
    logger.info("FW updated. IP: %s", drive_conf["ip"])


def main(comm, config):
    servo_list = config[comm]
    for index, servo_conf in enumerate(servo_list):
        logger.info("Upload FW comm %s, index: %d", comm, index)
        try:
            if comm == "canopen":
                load_can(servo_conf)
            if comm == "soem":
                load_ecat(servo_conf)
            if comm == "eoe":
                load_eth(servo_conf)
        except ILError as e:
            logger.exception(e)
            logger.error("Error in FW update. comm %s, index: %d", comm, index)


if __name__ == "__main__":
    args = setup_command()
    with open(os.path.join(dirname, "config.json")) as file:
        config_json = json.load(file)
    main(args.comm, config_json)
