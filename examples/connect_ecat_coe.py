from typing import Any, Dict

from ingeniamotion import MotionController


def connect_ethercat_coe(ecat_coe_conf: Dict[str, Any]):
    mc = MotionController()

    interface_list_human_format = mc.communication.get_interface_name_list()
    print("List of interfaces - Human-readable format:")
    for index, interface in enumerate(interface_list_human_format):
        print(f"{index}: {interface}")

    interface_selected = mc.communication.get_ifname_by_index(ecat_coe_conf["interface_index"])
    print("Interface selected:")
    print(f"- Index interface: {ecat_coe_conf['interface_index']}")
    print(f"- Real name: {interface_selected}")
    print(
        f"- Human-readable format name: {interface_list_human_format[ecat_coe_conf['interface_index']]}"
    )

    try:
        slave_id_list = mc.communication.scan_servos_ethercat(interface_selected)
    except ConnectionError as e:
        print(e)
        return

    if not slave_id_list:
        print(
            f"Any slave is detected using the interface: {interface_list_human_format[ecat_coe_conf['interface_index']]}."
        )
        return
    else:
        print(f"Found slaves: {slave_id_list}")

    try:
        mc.communication.connect_servo_ethercat(
            interface_selected, ecat_coe_conf["slave_id"], ecat_coe_conf["dictionary"]
        )
    except FileNotFoundError as e:
        print(e)
        return
    if "default" not in mc.servos:
        print("Drive is not connected.")
        return
    else:
        print("Drive is connected.")

    mc.communication.disconnect()
    if "default" in mc.servos:
        print("Drive disconnection failed.")
    else:
        print("The drive has been disconnected.")


if __name__ == "__main__":
    # Replace the ecat_coe_conf parameters
    ecat_coe_conf = {
        "interface_index": 3,
        "slave_id": 1,
        "dictionary": "parent_directory\\dictionary_file.xdf",
    }
    connect_ethercat_coe(ecat_coe_conf)
