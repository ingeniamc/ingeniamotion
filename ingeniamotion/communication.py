import time
import ifaddr
import subprocess
import ingenialogger

from os import path
from enum import IntEnum
from functools import partial
from ingenialink.exceptions import ILError
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethercat.network import EthercatNetwork

from ingeniamotion.exceptions import IMRegisterWrongAccess
from ingeniamotion.enums import Protocol, CAN_BAUDRATE, REG_DTYPE, REG_ACCESS
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Communication(metaclass=MCMetaClass):
    """Communication.
    """

    FORCE_SYSTEM_BOOT_CODE_REGISTER = "DRV_BOOT_COCO_FORCE"

    class Protocol(IntEnum):
        """Communication protocol enum"""
        TCP = 1
        UDP = 2

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def connect_servo_eoe(self, ip, dict_path=None, alias=DEFAULT_SERVO,
                          protocol=Protocol.UDP, port=1061,
                          reconnection_retries=None, reconnection_timeout=None,
                          servo_status_listener=False,
                          net_status_listener=False):
        """Connect to target servo by Ethernet over EtherCAT

        Args:
            ip (str): servo IP.
            dict_path (str): servo dictionary path.
            alias (str): servo alias to reference it. ``default`` by default.
            protocol (Protocol): UDP or TCP protocol. ``UDP`` by default.
            port (int): servo port. ``1061`` by default.
            reconnection_retries (int): Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, protocol, port,
                             {"reconnection_retries": reconnection_retries,
                              "reconnection_timeout": reconnection_timeout},
                             servo_status_listener=servo_status_listener,
                             net_status_listener=net_status_listener)

    def connect_servo_ethernet(self, ip, dict_path=None, alias=DEFAULT_SERVO,
                               protocol=Protocol.UDP, port=1061,
                               reconnection_retries=None,
                               reconnection_timeout=None,
                               servo_status_listener=False,
                               net_status_listener=False
                               ):
        """Connect to target servo by Ethernet

        Args:
            ip (str): servo IP
            dict_path (str): servo dictionary path.
            alias (str): servo alias to reference it. ``default`` by default.
            protocol (Protocol): UDP or TCP protocol. ``UDP`` by default.
            port (int): servo port. ``1061`` by default.
            reconnection_retries (int): Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, protocol, port,
                             {"reconnection_retries": reconnection_retries,
                              "reconnection_timeout": reconnection_timeout},
                             servo_status_listener=servo_status_listener,
                             net_status_listener=net_status_listener)

    def __servo_connect(self, ip, dict_path, alias,
                        protocol=Protocol.UDP, port=1061,
                        reconnection=None,
                        servo_status_listener=False,
                        net_status_listener=False):
        if reconnection is None:
            reconnection = {}
        reconnection = {x: reconnection[x] for x in reconnection
                        if reconnection[x] is not None}
        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file does not exist!".format(dict_path))

        if "ethernet" not in self.mc.net:
            self.mc.net["ethernet"] = EthernetNetwork()
        net = self.mc.net["ethernet"]
        servo = net.connect_to_slave(
            ip, dict_path, port, protocol,
            **reconnection,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener
        )

        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = "ethernet"

    def connect_servo_ecat(self, ifname, dict_path, slave=1,
                           eoe_comm=True, alias=DEFAULT_SERVO,
                           reconnection_retries=None,
                           reconnection_timeout=None,
                           servo_status_listener=False,
                           net_status_listener=False):
        """Connect servo by ECAT with embedded master.

        Args:
            ifname (str): interface name. It should have format
                ``\\Device\\NPF_[...]``.
            dict_path (str): servo dictionary path.
            slave (int): slave index. ``1`` by default.
            eoe_comm (bool): use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
            reconnection_retries (int): Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: Dictionary file is not found.
        """
        reconnection = {}
        if reconnection_retries is not None:
            reconnection['reconnection_retries'] = reconnection_retries
        if reconnection_timeout is not None:
            reconnection['reconnection_timeout'] = reconnection_timeout

        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file does not exist!".format(dict_path))
        use_eoe_comms = 1 if eoe_comm else 0

        if ifname not in self.mc.net:
            self.mc.net[ifname] = EthercatNetwork(ifname)
        net = self.mc.net[ifname]
        servo = net.connect_to_slave(
            slave, dict_path,
            use_eoe_comms, **reconnection,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener)
        servo.slave = slave

        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = ifname

    def connect_servo_ecat_interface_ip(self, interface_ip, dict_path,
                                        slave=1, eoe_comm=True,
                                        alias=DEFAULT_SERVO,
                                        reconnection_retries=None,
                                        reconnection_timeout=None,
                                        servo_status_listener=False,
                                        net_status_listener=False):
        """Connect servo by ECAT with embedded master.

        Args:
            interface_ip (str): IP of the interface to be connected to.
            dict_path (str): servo dictionary path.
            slave (int): slave index. ``1`` by default.
            eoe_comm (bool): use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
            reconnection_retries (int): Number of reconnection retried before
            declaring a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.
        """
        self.connect_servo_ecat(
            self.get_ifname_from_interface_ip(interface_ip), dict_path,
            slave, eoe_comm, alias, reconnection_retries, reconnection_timeout,
            servo_status_listener, net_status_listener
        )

    @staticmethod
    def get_ifname_from_interface_ip(address):
        """Returns interface name based on the address ip of an interface.

        Args:
            address (str): ip expected adapter is expected to
            be configured with.

        Raises:
            ValueError: In case the input is not valid or the adapter
            is not found.

        Returns:
            str: Ifname of the controller.
        """
        adapter_name = None

        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if ip.is_IPv4 and ip.ip == address:
                    adapter_name = adapter.name.decode("utf-8")
                    break

            if adapter_name is not None:
                break

        if adapter_name is None:
            raise ValueError(
                f"Could not found a adapter configured as {address} "
                f"to connect as EtherCAT master")
        else:
            return "\\Device\\NPF_{}".format(adapter_name)

    @staticmethod
    def get_ifname_by_index(index):
        """Return interface name by index.

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
        """Get interface list.

        Returns:
            list of str: List with interface readable names.

        """
        return [x.nice_name for x in ifaddr.get_adapters()]

    def connect_servo_ecat_interface_index(self, if_index, dict_path, slave=1,
                                           eoe_comm=True, alias=DEFAULT_SERVO,
                                           reconnection_retries=None,
                                           reconnection_timeout=None,
                                           servo_status_listener=False,
                                           net_status_listener=False):
        """Connect servo by ECAT with embedded master.
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
            reconnection_retries (int): Number of reconnection retried before
            declaring a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        """
        self.connect_servo_ecat(self.get_ifname_by_index(if_index), dict_path,
                                slave, eoe_comm, alias,
                                reconnection_retries, reconnection_timeout,
                                servo_status_listener, net_status_listener)

    def scan_servos_ecat(self, ifname):
        """Return a list of available servos.

        Args:
            ifname (str): interface name. It should have format
                ``\\Device\\NPF_[...]``.
        Returns:
            list of int: Drives available in the target interface.

        """
        if ifname not in self.mc.net:
            self.mc.net[ifname] = EthercatNetwork(ifname)
        net = self.mc.net[ifname]
        return net.scan_slaves()

    def scan_servos_ecat_interface_index(self, if_index):
        """Return a list of available servos.

        Args:
            if_index (int): interface index in list given by function
                :func:`get_interface_name_list`.
        Returns:
            list of int: Drives available in the target interface.

        """
        return self.scan_servos_ecat(self.get_ifname_by_index(if_index))

    def connect_servo_canopen(self, can_device, dict_path, eds_file,
                              node_id, baudrate=CAN_BAUDRATE.Baudrate_1M,
                              channel=0, alias=DEFAULT_SERVO,
                              servo_status_listener=False,
                              net_status_listener=False):
        """Connect to target servo by CANOpen.

        Args:
            can_device (CAN_DEVICE): CANOpen device type.
            dict_path (str): servo dictionary path.
            eds_file (str): EDS file path.
            node_id (int): node id. It's posible scan node ids with
                :func:`scan_servos_canopen`.
            baudrate (CAN_BAUDRATE): communication baudrate.
                1 Mbit/s by default.
            channel (int): CANopen device channel. ``0`` by default.
            alias (str): servo alias to reference it. ``default`` by default.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        """

        if not path.isfile(dict_path):
            raise FileNotFoundError('Dict file {} does not exist!'.format(dict_path))

        if not path.isfile(eds_file):
            raise FileNotFoundError("EDS file {} does not exist!".format(eds_file))
        net_key = "{}_{}_{}".format(can_device, channel, baudrate)
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        servo = net.connect_to_slave(
            node_id, dict_path, eds_file,
            servo_status_listener, net_status_listener)
        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = net_key

    def scan_servos_canopen(self, can_device,
                            baudrate=CAN_BAUDRATE.Baudrate_1M, channel=0):
        """Scan CANOpen device network to get all nodes.

        Args:
            can_device (CAN_DEVICE): CANOpen device type.
            baudrate (CAN_BAUDRATE): communication baudrate.
                1 Mbit/s by default.
            channel (int): CANOpen device channel. ``0`` by default.
        Returns:
            list of int: List of node ids available in the network.

        """
        net_key = "{}_{}_{}".format(can_device, channel, baudrate)
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        if net is None:
            self.logger.warning("Could not find any nodes in the network."
                                "Device: %s, channel: %s and baudrate: %s.",
                                can_device, channel, baudrate)
            return []
        return net.scan_slaves()

    def disconnect(self, servo=DEFAULT_SERVO):
        """Disconnect servo.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        network = self.mc._get_network(servo)
        network.disconnect_from_slave(drive)
        del self.mc.servos[servo]
        del self.mc.servo_net[servo]

    def get_register(self, register, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """Return the value of a target register.

        Args:
            register (str): register UID.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int, float or str: Current register value.

        """
        drive = self.mc.servos[servo]
        register_dtype = self.mc.info.register_type(register, axis, servo=servo)
        value = drive.read(register, subnode=axis)
        if (register_dtype.value <=
                REG_DTYPE.S64.value):
            return int(value)
        return value

    def set_register(self, register, value, servo=DEFAULT_SERVO,
                     axis=DEFAULT_AXIS):
        """Set a value of a target register.

        Args:
            register (str): register UID.
            value (int, float): new value for the register.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Raises:
            TypeError: If the value is of the wrong type.
            IMRegisterNotExist: If the register doesn't exist.
            IMRegisterWrongAccess: If the register access is read-only.

        """
        drive = self.mc.servos[servo]
        register_dtype_value = self.mc.info.register_type(register, axis, servo=servo)
        register_access_type = self.mc.info.register_info(register, axis, servo=servo).access
        signed_int = [
            REG_DTYPE.S8, REG_DTYPE.S16,
            REG_DTYPE.S32, REG_DTYPE.S64
        ]
        unsigned_int = [
            REG_DTYPE.U8, REG_DTYPE.U16,
            REG_DTYPE.U32, REG_DTYPE.U64
        ]
        if register_dtype_value == REG_DTYPE.FLOAT and \
                not isinstance(value, (int, float)):
            raise TypeError("Value must be a float")
        if register_dtype_value == REG_DTYPE.STR and \
                not isinstance(value, str):
            raise TypeError("Value must be a string")
        if register_dtype_value in signed_int and \
                not isinstance(value, int):
            raise TypeError("Value must be an int")
        if register_dtype_value in unsigned_int and \
                (not isinstance(value, int) or value < 0):
            raise TypeError("Value must be an unsigned int")
        if register_access_type == REG_ACCESS.RO:
            raise IMRegisterWrongAccess("Register: {} cannot write to a read-only register".format(register))

        drive.write(register, value, subnode=axis)

    def get_sdo_register(self, index, subindex, dtype, string_size=None,
                         servo=DEFAULT_SERVO):
        """Return the value via SDO of a target register.

        Args:
            index (int): register index.
            subindex (int): register subindex.
            dtype (REG_DTYPE): register data type.
            string_size (int): if register data is a string,
                size in bytes is mandatory. ``None`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int, float or str: Current register value.

        """
        drive = self.mc.servos[servo]
        if REG_DTYPE.STR.value != dtype.value:
            return drive.read_sdo(index, subindex, dtype.value, drive.slave)
        if not isinstance(string_size, int):
            raise TypeError("string_size should be an int for data type string")
        return drive.read_string_sdo(index, subindex,
                                     string_size, drive.slave)

    def get_sdo_register_complete_access(self, index, size, servo=DEFAULT_SERVO):
        """Read register via SDO complete access, return value in bytes.

        Args:
            index (int): register index.
            size (int): size in bytes of register.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            bytes: Register value.

        """
        drive = self.mc._get_drive(servo)
        return drive.read_sdo_complete_access(index, size, drive.slave)

    def set_sdo_register(self, index, subindex, dtype, value,
                         servo=DEFAULT_SERVO):
        """Set the value via SDO of a target register.

        Args:
            index (int): register index.
            subindex (int): register subindex.
            dtype (REG_DTYPE): register data type.
            value (int or float): new value for the register.
            servo (str): servo alias to reference it. ``default`` by default.

        """
        drive = self.mc.servos[servo]
        drive.write_sdo(index, subindex, dtype.value, value, drive.slave)

    def subscribe_net_status(self, callback, servo=DEFAULT_SERVO):
        """Add a callback to net status change event.

        Args:
            callback (callable): when net status changes callback is called.
            servo (str): servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        network.subscribe_to_status(callback)

    def unsubscribe_net_status(self, callback, servo=DEFAULT_SERVO):
        """Remove net status change event callback.

        Args:
            callback (callable): callback to remove.
            servo (str): servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        network.unsubscribe_from_status(callback)

    def subscribe_servo_status(self, callback, servo=DEFAULT_SERVO):
        """Add a callback to servo status change event.

        Args:
            callback (callable): when servo status changes callback is called.
            servo (str): servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.subscribe_to_status(callback)

    def unsubscribe_servo_status(self, callback, servo=DEFAULT_SERVO):
        """Remove servo status change event callback.

        Args:
            callback (callable): callback to remove.
            servo (str): servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.unsubscribe_from_status(callback)

    def load_firmware_canopen(self, fw_file, servo=DEFAULT_SERVO,
                              status_callback=None, progress_callback=None,
                              error_enabled_callback=None):
        """Load firmware via CANopen.

        Args:
            fw_file (str): Firmware file path.
            servo (str): servo alias to reference it. ``default`` by default.
            status_callback (callable): callback with status.
            progress_callback (callable): callback with progress.
            error_enabled_callback (callable): callback with errors enabled.

        """
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        if not isinstance(net, CanopenNetwork):
            raise ValueError("Target servo is not connected via CANopen")
        if status_callback is None:
            status_callback = partial(self.logger.info, "Load firmware status: %s")
        if progress_callback is None:
            progress_callback = partial(self.logger.info, "Load firmware progress: %s")
        net.load_firmware(drive.target, fw_file, status_callback,
                          progress_callback, error_enabled_callback)

    def load_firmware_ecat(self, ifname, fw_file, slave=1, boot_in_app=True):
        """Load firmware via ECAT.

        Args:
            ifname (str): interface name. It should have format
                ``\\Device\\NPF_[...]``.
            fw_file (str): Firmware file path.
            slave (int): slave index. ``1`` by default.
            boot_in_app (bool): If summit series -> True.
                                If capitan series -> False.
                                If custom device -> Contact manufacturer.

        """
        if ifname not in self.mc.net:
            self.mc.net[ifname] = EthercatNetwork(ifname)
        net = self.mc.net[ifname]
        net.load_firmware(fw_file, slave, boot_in_app)

    def load_firmware_ecat_interface_index(self, if_index, fw_file,
                                           slave=1, boot_in_app=True):
        """Load firmware via ECAT.

        Args:
            if_index (int): interface index in list given by function
                :func:`get_interface_name_list`.
            fw_file (str): Firmware file path.
            slave (int): slave index. ``1`` by default.
            boot_in_app (bool): If summit series -> True.
                                If capitan series -> False.
                                If custom device -> Contact manufacturer.

        """
        self.load_firmware_ecat(self.get_ifname_by_index(if_index),
                                fw_file, slave, boot_in_app)

    def load_firmware_ethernet(self, ip, fw_file, ftp_user=None, ftp_pwd=None):
        """Load firmware via Ethernet. Boot mode is needed to load firmware.

        .. warning::
            After functions ends, the servo will take a moment to load firmware.
            During the process, the servo will be not operative.

        Args:
            ip (str): servo IP.
            fw_file (str): Firmware file path.
            ftp_user (str): FTP user to connect with.
            ftp_pwd (str): FTP password for the given user.

        """
        if "ethernet" not in self.mc.net:
            self.mc.net["ethernet"] = EthernetNetwork()
        net = self.mc.net["ethernet"]
        if ftp_user is None and ftp_pwd is None:
            ftp_user, ftp_pwd = "Ingenia", "Ingenia"
        net.load_firmware(fw_file, ip, ftp_user, ftp_pwd)

    @staticmethod
    def __ftp_ping(ip):
        command = ['ping', ip]
        return subprocess.call(command) == 0

    def boot_mode_and_load_firmware_ethernet(self, fw_file, servo=DEFAULT_SERVO,
                                             ftp_user=None, ftp_pwd=None):
        """Set servo to boot mode and load firmware. Servo is disconnected.

        .. warning::
            After functions ends, the servo will take a moment to load firmware.
            During the process, the servo will be not operative.

        Args:
            fw_file (str): Firmware file path.
            servo (str): servo alias to reference it. ``default`` by default.
            ftp_user (str): FTP user to connect with.
            ftp_pwd (str): FTP password for the given user.

        """
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        ip = drive.target
        if not isinstance(net, EthernetNetwork):
            raise ValueError("Target servo is not connected via Ethernet")
        self.boot_mode(servo)
        timeout = 5
        init_time = time.time()
        ftp_ready = False
        while not ftp_ready and time.time() - init_time < timeout:
            ftp_ready = self.__ftp_ping(ip)
            time.sleep(1)
        self.load_firmware_ethernet(ip, fw_file, ftp_user, ftp_pwd)

    def boot_mode(self, servo=DEFAULT_SERVO):
        """Set servo to boot mode. Servo is disconnected.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        """
        PASSWORD_FORCE_BOOT_COCO = 0x424F4F54
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        net.stop_status_listener()
        drive.stop_status_listener()
        try:
            self.mc.communication.set_register(
                self.FORCE_SYSTEM_BOOT_CODE_REGISTER,
                PASSWORD_FORCE_BOOT_COCO, servo=servo, axis=0)
        except ILError:
            pass
        self.disconnect(servo)
