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
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE, REG_DTYPE, REG_ACCESS
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
        port: int = 1061,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet over EtherCAT

        Args:
            ip : servo IP.
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            port : servo port. ``1061`` by default.
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
            port,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

    def connect_servo_ethernet(
        self,
        ip: str,
        dict_path: str,
        alias: str = DEFAULT_SERVO,
        port: int = 1061,
        connection_timeout: int = 1,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet

        Args:
            ip : servo IP
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            port : servo port. ``1061`` by default.
            connection_timeout: Timeout in seconds for connection.
                ``1`` seconds by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: If the dict file doesn't exist.
            ingenialink.exceptions.ILError: If the servo's IP or port is incorrect.
        """
        if not path.isfile(dict_path):
            raise FileNotFoundError(f"{dict_path} file does not exist!")
        self.__servo_connect(
            ip,
            dict_path,
            alias,
            port,
            connection_timeout,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

    def __servo_connect(
        self,
        ip: str,
        dict_path: str,
        alias: str,
        port: int = 1061,
        connection_timeout: int = 1,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        if not path.isfile(dict_path):
            raise FileNotFoundError(f"{dict_path} file does not exist!")

        self.mc.net[alias] = EthernetNetwork()
        net = self.mc.net[alias]
        servo = net.connect_to_slave(
            ip,
            dict_path,
            port,
            connection_timeout,
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
            FileNotFoundError: If the dict file doesn't exist.
        """
        if not path.isfile(dict_path):
            raise FileNotFoundError(f"{dict_path} file does not exist!")
        if ifname not in self.mc.net:
            self.mc.net[ifname] = EoENetwork(ifname)
        net = self.mc.net[ifname]
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
        self.mc.servo_net[alias] = ifname

    def connect_servo_eoe_service_interface_ip(
        self,
        interface_ip: str,
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
            interface_ip : IP of the interface to be connected to.
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
            IndexError: If interface index is out of range.
        """
        self.connect_servo_eoe_service(
            self.get_ifname_from_interface_ip(interface_ip),
            dict_path,
            ip,
            slave,
            port,
            alias,
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
            It can be used for function :func:`connect_servo_eoe_service`.

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

    def connect_servo_eoe_service_interface_index(
        self,
        if_index: int,
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
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
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
            IndexError: If interface index is out of range.
        """
        self.connect_servo_eoe_service(
            self.get_ifname_by_index(if_index),
            dict_path,
            ip,
            slave,
            port,
            alias,
            servo_status_listener,
            net_status_listener,
        )

    def scan_servos_eoe_service(self, ifname: str) -> List[int]:
        """Return a list of available servos.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
        Returns:
            Drives available in the target interface.

        """
        if ifname in self.mc.net:
            net = self.mc.net[ifname]
        else:
            net = EoENetwork(ifname)
        return net.scan_slaves()

    def scan_servos_eoe_service_interface_index(self, if_index: int) -> List[int]:
        """Return a list of available servos.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
        Returns:
            Drives available in the target interface.

        Raises:
            IndexError: If interface index is out of range.

        """
        return self.scan_servos_eoe_service(self.get_ifname_by_index(if_index))

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
            raise FileNotFoundError(f"Dict file {dict_path} does not exist!")

        if not path.isfile(eds_file):
            raise FileNotFoundError(f"EDS file {eds_file} does not exist!")
        net_key = f"{can_device}_{channel}_{baudrate}"
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
        net_key = f"{can_device}_{channel}_{baudrate}"
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
        net_name = self.mc.servo_net.pop(servo)
        servo_count = list(self.mc.servo_net.values()).count(net_name)
        if servo_count == 0:
            del self.mc.net[net_name]

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
                f"Register: {register} cannot write to a read-only register"
            )
        drive.write(register, value, subnode=axis)

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

    def load_firmware_ecat(self, ifname: str, fw_file: str, slave: int = 1) -> None:
        """Load firmware via ECAT.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.

        """
        net = EthercatNetwork(ifname)
        net.load_firmware(fw_file, slave)

    def load_firmware_ecat_interface_index(
        self, if_index: int, fw_file: str, slave: int = 1
    ) -> None:
        """Load firmware via ECAT.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.

        """
        self.load_firmware_ecat(self.get_ifname_by_index(if_index), fw_file, slave)

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
