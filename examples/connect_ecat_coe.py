from ingeniamotion import MotionController


def connect_ethercat_coe(interface_index: int, slave_id: int, dictionary_path: str) -> None:
    mc = MotionController()

    interface_list = mc.communication.get_interface_name_list()
    print("List of interfaces:")
    for index, interface in enumerate(interface_list):
        print(f"{index}: {interface}")

    interface_selected = mc.communication.get_ifname_by_index(interface_index)
    print("Interface selected:")
    print(f"- Index interface: {interface_index}")
    print(f"- Interface identifier: {interface_selected}")
    print(f"- Interface name: {interface_list[interface_index]}")

    slave_id_list = mc.communication.scan_servos_ethercat(interface_selected)

    if not slave_id_list:
        print(f"No slave detected on interface: {interface_list[interface_index]}")
        return
    else:
        print(f"Found slaves: {slave_id_list}")

    mc.communication.connect_servo_ethercat(interface_selected, slave_id, dictionary_path)
    print("Drive is connected.")

    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    # Replace the ecat_coe_conf parameters
    interface_index = 3
    slave_id = 1
    dictionary_path = "parent_directory\\dictionary_file.xdf"
    connect_ethercat_coe(interface_index, slave_id, dictionary_path)
