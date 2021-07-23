import ifaddr
import ingenialink as il
import ingenialogger

from os import path
from enum import IntEnum
from ingenialink.canopen import CAN_BAUDRATE, CAN_DEVICE

from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Communication(metaclass=MCMetaClass):
    """Communication.
    """

    class Protocol(IntEnum):
        """
        Communication protocol enum
        """
        TCP = 1
        UDP = 2

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def connect_servo_eoe(self, ip, dict_path=None, alias=DEFAULT_SERVO,
                          protocol=Protocol.UDP, port=1061):
        """
        Connect to target servo by Ethernet over EtherCAT

        Args:
            ip (str): servo IP.
            dict_path (str): servo dictionary path.
            alias (str): servo alias to reference it. ``default`` by default.
            protocol (Protocol): UDP or TCP protocol. ``UDP`` by default.
            port (int): servo port. ``1061`` by default.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, il.NET_PROT.ETH, protocol, port)

    def connect_servo_ethernet(self, ip, dict_path=None, alias=DEFAULT_SERVO,
                               protocol=Protocol.UDP, port=1061):
        """
        Connect to target servo by Ethernet

        Args:
            ip (str): servo IP
            dict_path (str): servo dictionary path.
            alias (str): servo alias to reference it. ``default`` by default.
            protocol (Protocol): UDP or TCP protocol. ``UDP`` by default.
            port (int): servo port. ``1061`` by default.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, il.NET_PROT.ETH, protocol, port)

    def __servo_connect(self, ip, dict_path, alias, prot,
                        protocol=Protocol.UDP, port=1061):
        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file does not exist!".format(dict_path))
        try:
            net, servo = il.lucky(prot, dict_path, address_ip=ip,
                                  port_ip=port, protocol=protocol)
            self.mc.servos[alias] = servo
            self.mc.net[alias] = net
        except il.exceptions.ILError as e:
            raise Exception("Error trying to connect to the servo. {}.".format(e))

    def connect_servo_ecat(self, ifname, dict_path, slave=1,
                           eoe_comm=True, alias=DEFAULT_SERVO):
        """
        Connect servo by ECAT with embedded master.

        Args:
            ifname (str): interface name. It should have format
                ``\\Device\\NPF_[...]``.
            dict_path (str): servo dictionary path.
            slave (int): slave index. ``1`` by default.
            eoe_comm (bool): use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
        """
        use_eoe_comms = 1 if eoe_comm else 0
        try:
            servo, net = il.servo.connect_ecat(ifname, dict_path,
                                               slave, use_eoe_comms)
            self.mc.servos[alias] = servo
            net.slave = slave
            self.mc.net[alias] = net
        except il.exceptions.ILError as e:
            raise Exception("Error trying to connect to the servo. {}."
                            .format(e))

    @staticmethod
    def get_ifname_by_index(index):
        """
        Return interface name by index.

        Args:
            index (int): position of interface selected in
                :func:`get_interface_name_list`.

        Returns:
            str: real name of selected interface.
                It can be used for function :func:`connect_servo_ecat`.
        """
        return "\\Device\\NPF_{}".format(
            ifaddr.get_adapters()[index].name.decode("utf-8")
        )

    @staticmethod
    def get_interface_name_list():
        """
        Get interface list.

        Returns:
            list of str: List with interface readable names.
        """
        return [x.nice_name for x in ifaddr.get_adapters()]

    def connect_servo_ecat_interface_index(self, if_index, dict_path, slave=1,
                                           eoe_comm=True, alias=DEFAULT_SERVO):
        """
        Connect servo by ECAT with embedded master.
        Interface should be selected by index of list given in
        :func:`get_interface_name_list`.

        Args:
            if_index (int): interface index in list given by function
                :func:`get_interface_name_list`.
            dict_path (str): servo dictionary path.
            slave (int): slave index. ``1`` by default.
            eoe_comm (bool): use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
        """
        self.connect_servo_ecat(self.get_ifname_by_index(if_index), dict_path,
                                slave, eoe_comm, alias)

    def connect_servo_canopen(self, can_device, dict_path, eds_file,
                              node_id, baudrate=CAN_BAUDRATE.Baudrate_1M,
                              channel=0, alias=DEFAULT_SERVO):
        """
        Connect to target servo by CANOpen.

        Args:
            can_device (ingenialink.canopen.net.CAN_DEVICE): CANOpen device type.
            dict_path (str): servo dictionary path.
            eds_file (str): EDS file path.
            node_id (int): node id. It's posible scan node ids with
                :func:`scan_servos_canopen`.
            baudrate (ingenialink.canopen.net.CAN_BAUDRATE): communication baudrate.
                1 Mbit/s by default.
            channel (int): CANOpen device channel. ``0`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
        """

        if not path.isfile(dict_path):
            raise FileNotFoundError('Dict file {} does not exist!'.format(dict_path))

        if not path.isfile(eds_file):
            raise FileNotFoundError("EDS file {} does not exist!".format(eds_file))
        net = il.CANOpenNetwork(device=can_device, channel=channel, baudrate=baudrate)
        try:
            net.connect_through_node(eds_file, dict_path, node_id, heartbeat=False)
            drives_connected = net.servos
            if len(drives_connected) > 0:
                servo = drives_connected[0]
            else:
                raise Exception("Error trying to connect to the servo.")
            self.mc.servos[alias] = servo
            self.mc.net[alias] = net
        except Exception as e:
            net.disconnect()
            raise e

    def scan_servos_canopen(self, can_device,
                            baudrate=CAN_BAUDRATE.Baudrate_1M, channel=0):
        """
        Scan CANOpen device network to get all nodes.

        Args:
            can_device (ingenialink.canopen.net.CAN_DEVICE): CANOpen device type.
            baudrate (ingenialink.canopen.net.CAN_BAUDRATE): communication baudrate.
                1 Mbit/s by default.
            channel (int): CANOpen device channel. ``0`` by default.
        Returns:
            list of int: List of node ids available in the network.
        """
        net = il.canopen.net.Network(can_device, baudrate=baudrate,
                                     channel=channel)
        if net is None:
            self.logger.warning("Could not find any nodes in the network."
                                "Device: %s, channel: %s and baudrate: %s.",
                                can_device, channel, baudrate)
            return []
        nodes = net.detect_nodes()
        net.disconnect()
        return nodes

    def disconnect_canopen(self, servo=DEFAULT_SERVO):
        network = self.mc.net[servo]
        network.disconnect()

    def get_register(self, register, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return the value of a target register.

        Args:
            register (str): register UID.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int, float or str: Current register value.
        """
        drive = self.mc.servos[servo]
        value = drive.read(register, subnode=axis)
        if (drive.dict.get_regs(axis).get(register).dtype.value <=
                il.registers.REG_DTYPE.S64.value):
            return int(value)
        return value

    def set_register(self, register, value, servo=DEFAULT_SERVO,
                     axis=DEFAULT_AXIS):
        """
        Set a value of a target register.

        Args:
            register (str): register UID.
            value (int, float): new value for the register.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        drive = self.mc.servos[servo]
        register_instance = drive.dict.get_regs(axis).get(register)
        register_dtype_value = None
        if register_instance:
            register_dtype_value = register_instance.dtype.value
        signed_int = [
            il.registers.REG_DTYPE.S8.value, il.registers.REG_DTYPE.S16.value,
            il.registers.REG_DTYPE.S32.value, il.registers.REG_DTYPE.S64.value
        ]
        unsigned_int = [
            il.registers.REG_DTYPE.U8.value, il.registers.REG_DTYPE.U16.value,
            il.registers.REG_DTYPE.U32.value, il.registers.REG_DTYPE.U64.value
        ]
        if register_dtype_value == il.registers.REG_DTYPE.FLOAT.value and \
                not isinstance(value, (int, float)):
            raise TypeError("Value must be a float")
        if register_dtype_value == il.registers.REG_DTYPE.STR.value and \
                not isinstance(value, str):
            raise TypeError("Value must be a string")
        if register_dtype_value in signed_int and \
                not isinstance(value, int):
            raise TypeError("Value must be an int")
        if register_dtype_value in unsigned_int and \
                (not isinstance(value, int) or value < 0):
            raise TypeError("Value must be an unsigned int")
        drive.write(register, value, subnode=axis)

    def get_sdo_register(self, index, subindex, dtype, string_size=None,
                         servo=DEFAULT_SERVO):
        """
        Return the value via SDO of a target register.

        Args:
            index (int): register index.
            subindex (int): register subindex.
            dtype (ingenialink.registers.REG_DTYPE): register data type.
            string_size (int): if register data is a string,
                size in bytes is mandatory. ``None`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int, float or str: Current register value.
        """
        network = self.mc.net[servo]
        if il.registers.REG_DTYPE.STR.value == dtype.value:
            if not isinstance(string_size, int):
                raise TypeError("string_size should be an int for data type string")
            return network.read_string_sdo(index, subindex,
                                           string_size, network.slave)
        else:
            return network.read_sdo(index, subindex, dtype.value, network.slave)

    def set_sdo_register(self, index, subindex, dtype, value,
                         servo=DEFAULT_SERVO):
        """
        Set the value via SDO of a target register.

        Args:
            index (int): register index.
            subindex (int): register subindex.
            dtype (ingenialink.registers.REG_DTYPE): register data type.
            value (int or float): new value for the register.
            servo (str): servo alias to reference it. ``default`` by default.
        """
        network = self.mc.net[servo]
        network.write_sdo(index, subindex, dtype.value, value, network.slave)
