import time
import ifaddr
import subprocess
from os import path
from functools import partial
from typing import Optional, Union, Callable, List

import ingenialogger
from ingenialink.exceptions import ILError
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.eoe.network import EoENetwork

from ingeniamotion.exceptions import IMRegisterWrongAccess
from ingeniamotion.enums import Protocol, CAN_BAUDRATE, CAN_DEVICE, REG_DTYPE, REG_ACCESS
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Communication(metaclass=MCMetaClass):
    """Communication."""

    FORCE_SYSTEM_BOOT_CODE_REGISTER = "DRV_BOOT_COCO_FORCE"

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def connect_servo_eoe(
        self,
        ip: str,
        dict_path: Optional[str] = None,
        alias: str = DEFAULT_SERVO,
        protocol: Protocol = Protocol.UDP,
        port: int = 1061,
        reconnection_retries: Optional[int] = None,
        reconnection_timeout: Optional[int] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet over EtherCAT

        Args:
            ip : servo IP.
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            protocol : UDP or TCP protocol. ``UDP`` by default.
            port : servo port. ``1061`` by default.
            reconnection_retries : Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout : Time in ms of the reconnection timeout.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            TypeError: If the dict_path argument is missing.
            FileNotFoundError: If the dict file doesn't exist.
            ingenialink.exceptions.ILError: If the servo's IP or port is incorrect.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(
            ip,
            dict_path,
            alias,
            protocol,
            port,
            {
                "reconnection_retries": reconnection_retries,
                "reconnection_timeout": reconnection_timeout,
            },
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

    def connect_servo_ethernet(
        self,
        ip: str,
        dict_path: Optional[str] = None,
        alias: str = DEFAULT_SERVO,
        protocol: Protocol = Protocol.UDP,
        port: int = 1061,
        reconnection_retries: Optional[int] = None,
        reconnection_timeout: Optional[int] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet

        Args:
            ip : servo IP
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            protocol : UDP or TCP protocol. ``UDP`` by default.
            port : servo port. ``1061`` by default.
            reconnection_retries : Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout : Time in ms of the reconnection timeout.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            TypeError: If the dict_path argument is missing.
            FileNotFoundError: If the dict file doesn't exist.
            ingenialink.exceptions.ILError: If the servo's IP or port is incorrect.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(
            ip,
            dict_path,
            alias,
            protocol,
            port,
            {
                "reconnection_retries": reconnection_retries,
                "reconnection_timeout": reconnection_timeout,
            },
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

    def __servo_connect(
        self,
        ip: str,
        dict_path: str,
        alias: str,
        protocol: Protocol = Protocol.UDP,
        port: int = 1061,
        reconnection: Optional[dict] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        if reconnection is None:
            reconnection = {}
        reconnection = {x: reconnection[x] for x in reconnection if reconnection[x] is not None}
        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file does not exist!".format(dict_path))

        self.mc.net[alias] = EthernetNetwork()
        net = self.mc.net[alias]
        servo = net.connect_to_slave(
            ip,
            dict_path,
            port,
            protocol,
            **reconnection,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = alias

    def connect_servo_eoe_service(
        self,
        ifname: str,
        dict_path: str,
        ip: str = "192.168.3.22",
        slave: int = 1,
        port: int = 1061,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet over EtherCAT

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            dict_path : servo dictionary path.
            ip : IP address to be assigned to the servo.
            slave : slave index. ``1`` by default.
            port : servo port. ``1061`` by default.
            alias : servo alias to reference it. ``default`` by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            TypeError: If the dict_path argument is missing.
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.mc.net[alias] = EoENetwork(ifname)
        net = self.mc.net[alias]
        servo = net.connect_to_slave(
            slave,
            ip,
            dict_path,
            port,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )
        servo.slave = slave
        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = alias

    def connect_servo_ecat(
        self,
        ifname: str,
        dict_path: str,
        slave: int = 1,
        eoe_comm: bool = True,
        alias: str = DEFAULT_SERVO,
        reconnection_retries: Optional[int] = None,
        reconnection_timeout: Optional[int] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect servo by ECAT with embedded master.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            dict_path : servo dictionary path.
            slave : slave index. ``1`` by default.
            eoe_comm : use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias : servo alias to reference it. ``default`` by default.
            reconnection_retries : Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout : Time in ms of the reconnection timeout.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: If the dict file doesn't exist.
            ingenialink.exceptions.ILError: If the interface name or the slave index is incorrect.
        """
        reconnection = {}
        if reconnection_retries is not None:
            reconnection["reconnection_retries"] = reconnection_retries
        if reconnection_timeout is not None:
            reconnection["reconnection_timeout"] = reconnection_timeout

        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file does not exist!".format(dict_path))
        use_eoe_comms = 1 if eoe_comm else 0

        self.mc.net[alias] = EthercatNetwork(ifname)
        net = self.mc.net[alias]
        servo = net.connect_to_slave(
            slave,
            dict_path,
            use_eoe_comms,
            **reconnection,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )
        servo.slave = slave

        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = alias

    def connect_servo_ecat_interface_ip(
        self,
        interface_ip: str,
        dict_path: str,
        slave: int = 1,
        eoe_comm: bool = True,
        alias: str = DEFAULT_SERVO,
        reconnection_retries: Optional[int] = None,
        reconnection_timeout: Optional[int] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect servo by ECAT with embedded master.

        Args:
            interface_ip : IP of the interface to be connected to.
            dict_path : servo dictionary path.
            slave : slave index. ``1`` by default.
            eoe_comm : use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias : servo alias to reference it. ``default`` by default.
            reconnection_retries : Number of reconnection retried before
            declaring a connected or disconnected stated.
            reconnection_timeout : Time in ms of the reconnection timeout.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.
        Raises:
            FileNotFoundError: Dictionary file is not found.
            ValueError: In case the input is not valid or the adapter
            is not found.
        """
        self.connect_servo_ecat(
            self.get_ifname_from_interface_ip(interface_ip),
            dict_path,
            slave,
            eoe_comm,
            alias,
            reconnection_retries,
            reconnection_timeout,
            servo_status_listener,
            net_status_listener,
        )

    @staticmethod
    def __get_adapter_name(address: str) -> Optional[str]:
        """Returns the adapter name of an adapter based on its address.

        Args:
            address : ip expected adapter is expected to
            be configured with.
        """
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if ip.is_IPv4 and ip.ip == address:
                    return adapter.name.decode("utf-8")
        return None

    def get_ifname_from_interface_ip(self, address: str) -> str:
        """Returns interface name based on the address ip of an interface.

        Args:
            address : ip expected adapter is expected to
            be configured with.

        Raises:
            ValueError: In case the input is not valid or the adapter
            is not found.

        Returns:
            Ifname of the controller.
        """
        adapter_name = self.__get_adapter_name(address)

        if adapter_name is None:
            raise ValueError(
                f"Could not found a adapter configured as {address} "
                f"to connect as EtherCAT master"
            )
        else:
            return "\\Device\\NPF_{}".format(adapter_name)

    @staticmethod
    def get_ifname_by_index(index: int) -> str:
        """Return interface name by index.

        Args:
            index : position of interface selected in
                :func:`get_interface_name_list`.

        Returns:
            Real name of selected interface.
            It can be used for function :func:`connect_servo_ecat`.

        Raises:
            IndexError: If interface index is out of range.

        """
        return "\\Device\\NPF_{}".format(ifaddr.get_adapters()[index].name.decode("utf-8"))

    @staticmethod
    def get_interface_name_list() -> List[str]:
        """Get interface list.

        Returns:
            List with interface readable names.

        """
        return [x.nice_name for x in ifaddr.get_adapters()]

    def connect_servo_ecat_interface_index(
        self,
        if_index: int,
        dict_path: str,
        slave: int = 1,
        eoe_comm: bool = True,
        alias: str = DEFAULT_SERVO,
        reconnection_retries: Optional[int] = None,
        reconnection_timeout: Optional[int] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect servo by ECAT with embedded master.
        Interface should be selected by index of list given in
        :func:`get_interface_name_list`.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
            dict_path : servo dictionary path.
            slave : slave index. ``1`` by default.
            eoe_comm : use eoe communications if ``True``,
                if ``False`` use SDOs. ``True`` by default.
            alias : servo alias to reference it. ``default`` by default.
            reconnection_retries : Number of reconnection retried before
            declaring a connected or disconnected stated.
            reconnection_timeout : Time in ms of the reconnection timeout.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: If the dict file doesn't exist.
            IndexError: If interface index is out of range.

        """
        self.connect_servo_ecat(
            self.get_ifname_by_index(if_index),
            dict_path,
            slave,
            eoe_comm,
            alias,
            reconnection_retries,
            reconnection_timeout,
            servo_status_listener,
            net_status_listener,
        )

    def scan_servos_ecat(self, ifname: str) -> List[int]:
        """Return a list of available servos.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
        Returns:
            Drives available in the target interface.

        """
        net = EthercatNetwork(ifname)
        return net.scan_slaves()

    def scan_servos_ecat_interface_index(self, if_index: int) -> List[int]:
        """Return a list of available servos.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
        Returns:
            Drives available in the target interface.

        Raises:
            IndexError: If interface index is out of range.

        """
        return self.scan_servos_ecat(self.get_ifname_by_index(if_index))

    def connect_servo_canopen(
        self,
        can_device: CAN_DEVICE,
        dict_path: str,
        eds_file: str,
        node_id: int,
        baudrate: CAN_BAUDRATE = CAN_BAUDRATE.Baudrate_1M,
        channel: int = 0,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by CANOpen.

        Args:
            can_device : CANOpen device type.
            dict_path : servo dictionary path.
            eds_file : EDS file path.
            node_id : node id. It's posible scan node ids with
                :func:`scan_servos_canopen`.
            baudrate : communication baudrate. 1 Mbit/s by default.
            channel : CANopen device channel. ``0`` by default.
            alias : servo alias to reference it. ``default`` by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: If either of the dict files doesn't exist.
            ingenialink.exceptions.ILError: If CANOpen device type, node id or channel is incorrect.

        """

        if not path.isfile(dict_path):
            raise FileNotFoundError("Dict file {} does not exist!".format(dict_path))

        if not path.isfile(eds_file):
            raise FileNotFoundError("EDS file {} does not exist!".format(eds_file))
        net_key = "{}_{}_{}".format(can_device, channel, baudrate)
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        servo = net.connect_to_slave(
            node_id, dict_path, eds_file, servo_status_listener, net_status_listener
        )
        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = net_key

    def scan_servos_canopen(
        self,
        can_device: CAN_DEVICE,
        baudrate: CAN_BAUDRATE = CAN_BAUDRATE.Baudrate_1M,
        channel: int = 0,
    ) -> List[int]:
        """Scan CANOpen device network to get all nodes.

        Args:
            can_device : CANOpen device type.
            baudrate : communication baudrate. 1 Mbit/s by default.
            channel : CANOpen device channel. ``0`` by default.
        Returns:
            List of node ids available in the network.

        """
        net_key = "{}_{}_{}".format(can_device, channel, baudrate)
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        if net is None:
            self.logger.warning(
                "Could not find any nodes in the network."
                "Device: %s, channel: %s and baudrate: %s.",
                can_device,
                channel,
                baudrate,
            )
            return []
        return net.scan_slaves()

    def disconnect(self, servo: str = DEFAULT_SERVO) -> None:
        """Disconnect servo.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        network = self.mc._get_network(servo)
        network.disconnect_from_slave(drive)
        del self.mc.servos[servo]
        del self.mc.servo_net[servo]

    def get_register(
        self, register: str, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Union[int, float, str]:
        """Return the value of a target register.

        Args:
            register : register UID.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Current register value.

        Raises:
            ingenialink.exceptions.ILAccessError: If the register access is write-only.
            IMRegisterNotExist: If the register doesn't exist.

        """
        drive = self.mc.servos[servo]
        register_dtype = self.mc.info.register_type(register, axis, servo=servo)
        value = drive.read(register, subnode=axis)
        if register_dtype.value <= REG_DTYPE.S64.value:
            return int(value)
        return value

    def set_register(
        self,
        register: str,
        value: Union[int, float],
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set a value of a target register.

        Args:
            register : register UID.
            value : new value for the register.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If the value is of the wrong type.
            IMRegisterNotExist: If the register doesn't exist.
            IMRegisterWrongAccess: If the register access is read-only.

        """
        drive = self.mc.servos[servo]
        register_dtype_value = self.mc.info.register_type(register, axis, servo=servo)
        register_access_type = self.mc.info.register_info(register, axis, servo=servo).access
        signed_int = [REG_DTYPE.S8, REG_DTYPE.S16, REG_DTYPE.S32, REG_DTYPE.S64]
        unsigned_int = [REG_DTYPE.U8, REG_DTYPE.U16, REG_DTYPE.U32, REG_DTYPE.U64]
        if register_dtype_value == REG_DTYPE.FLOAT and not isinstance(value, (int, float)):
            raise TypeError("Value must be a float")
        if register_dtype_value == REG_DTYPE.STR and not isinstance(value, str):
            raise TypeError("Value must be a string")
        if register_dtype_value in signed_int and not isinstance(value, int):
            raise TypeError("Value must be an int")
        if register_dtype_value in unsigned_int and (not isinstance(value, int) or value < 0):
            raise TypeError("Value must be an unsigned int")
        if register_access_type == REG_ACCESS.RO:
            raise IMRegisterWrongAccess(
                "Register: {} cannot write to a read-only register".format(register)
            )

        drive.write(register, value, subnode=axis)

    def get_sdo_register(
        self,
        index: int,
        subindex: int,
        dtype: REG_DTYPE,
        string_size: Optional[int] = None,
        servo: str = DEFAULT_SERVO,
    ) -> Union[int, float, str]:
        """Return the value via SDO of a target register.

        Args:
            index : register index.
            subindex : register subindex.
            dtype : register data type.
            string_size : if register data is a string,
                size in bytes is mandatory. ``None`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Current register value.

        Raises:
            TypeError: If string_size is not an int.

        """
        drive = self.mc.servos[servo]
        if REG_DTYPE.STR.value != dtype.value:
            return drive.read_sdo(index, subindex, dtype.value, drive.slave)
        if not isinstance(string_size, int):
            raise TypeError("string_size should be an int for data type string")
        return drive.read_string_sdo(index, subindex, string_size, drive.slave)

    def get_sdo_register_complete_access(
        self, index: int, size: int, servo: str = DEFAULT_SERVO
    ) -> bytes:
        """Read register via SDO complete access, return value in bytes.

        Args:
            index : register index.
            size : size in bytes of register.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register value.

        """
        drive = self.mc._get_drive(servo)
        return drive.read_sdo_complete_access(index, size, drive.slave)

    def set_sdo_register(
        self,
        index: int,
        subindex: int,
        dtype: REG_DTYPE,
        value: Union[int, float],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Set the value via SDO of a target register.

        Args:
            index : register index.
            subindex : register subindex.
            dtype : register data type.
            value : new value for the register.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc.servos[servo]
        drive.write_sdo(index, subindex, dtype.value, value, drive.slave)

    def subscribe_net_status(self, callback: Callable, servo: str = DEFAULT_SERVO) -> None:
        """Add a callback to net status change event.

        Args:
            callback : when net status changes callback is called.
            servo : servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        network.subscribe_to_status(callback)

    def unsubscribe_net_status(self, callback: Callable, servo: str = DEFAULT_SERVO) -> None:
        """Remove net status change event callback.

        Args:
            callback : callback to remove.
            servo : servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        network.unsubscribe_from_status(callback)

    def subscribe_servo_status(self, callback: Callable, servo: str = DEFAULT_SERVO) -> None:
        """Add a callback to servo status change event.

        Args:
            callback : when servo status changes callback is called.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.subscribe_to_status(callback)

    def unsubscribe_servo_status(self, callback: Callable, servo: str = DEFAULT_SERVO) -> None:
        """Remove servo status change event callback.

        Args:
            callback : callback to remove.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.unsubscribe_from_status(callback)

    def load_firmware_canopen(
        self,
        fw_file: str,
        servo: str = DEFAULT_SERVO,
        status_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        error_enabled_callback: Optional[Callable] = None,
    ) -> None:
        """Load firmware via CANopen.

        Args:
            fw_file : Firmware file path.
            servo : servo alias to reference it. ``default`` by default.
            status_callback : callback with status.
            progress_callback : callback with progress.
            error_enabled_callback : callback with errors enabled.

        Raises:
            ValueError: If servo is not connected via CANopen.

        """
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        if not isinstance(net, CanopenNetwork):
            raise ValueError("Target servo is not connected via CANopen")
        if status_callback is None:
            status_callback = partial(self.logger.info, "Load firmware status: %s")
        if progress_callback is None:
            progress_callback = partial(self.logger.info, "Load firmware progress: %s")
        net.load_firmware(
            drive.target, fw_file, status_callback, progress_callback, error_enabled_callback
        )

    def load_firmware_ecat(
        self, ifname: str, fw_file: str, slave: int = 1, boot_in_app: bool = True
    ) -> None:
        """Load firmware via ECAT.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.
            boot_in_app : If summit series -> True.
                                If capitan series -> False.
                                If custom device -> Contact manufacturer.

        """
        net = EthercatNetwork(ifname)
        net.load_firmware(fw_file, slave, boot_in_app)

    def load_firmware_ecat_interface_index(
        self, if_index: int, fw_file: str, slave: int = 1, boot_in_app: bool = True
    ) -> None:
        """Load firmware via ECAT.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.
            boot_in_app : If summit series -> True.
                                If capitan series -> False.
                                If custom device -> Contact manufacturer.

        """
        self.load_firmware_ecat(self.get_ifname_by_index(if_index), fw_file, slave, boot_in_app)

    def load_firmware_ethernet(
        self, ip: str, fw_file: str, ftp_user: Optional[str] = None, ftp_pwd: Optional[str] = None
    ) -> None:
        """Load firmware via Ethernet. Boot mode is needed to load firmware.

        .. warning::
            After functions ends, the servo will take a moment to load firmware.
            During the process, the servo will be not operative.

        Args:
            ip : servo IP.
            fw_file : Firmware file path.
            ftp_user : FTP user to connect with.
            ftp_pwd : FTP password for the given user.

        """
        net = EthernetNetwork()
        if ftp_user is None and ftp_pwd is None:
            ftp_user, ftp_pwd = "Ingenia", "Ingenia"
        net.load_firmware(fw_file, ip, ftp_user, ftp_pwd)

    @staticmethod
    def __ftp_ping(ip):
        command = ["ping", ip]
        return subprocess.call(command) == 0

    def boot_mode_and_load_firmware_ethernet(
        self,
        fw_file: str,
        servo: str = DEFAULT_SERVO,
        ftp_user: Optional[str] = None,
        ftp_pwd: Optional[str] = None,
    ) -> None:
        """Set servo to boot mode and load firmware. Servo is disconnected.

        .. warning::
            After functions ends, the servo will take a moment to load firmware.
            During the process, the servo will be not operative.

        Args:
            fw_file : Firmware file path.
            servo : servo alias to reference it. ``default`` by default.
            ftp_user : FTP user to connect with.
            ftp_pwd : FTP password for the given user.

        Raises:
            ValueError: If servo is not connected via Ethernet.

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

    def boot_mode(self, servo: str = DEFAULT_SERVO) -> None:
        """Set servo to boot mode. Servo is disconnected.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        PASSWORD_FORCE_BOOT_COCO = 0x424F4F54
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        net.stop_status_listener()
        drive.stop_status_listener()
        try:
            self.mc.communication.set_register(
                self.FORCE_SYSTEM_BOOT_CODE_REGISTER, PASSWORD_FORCE_BOOT_COCO, servo=servo, axis=0
            )
        except ILError:
            pass
        self.disconnect(servo)
