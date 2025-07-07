import json
import platform
import tempfile
import time
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from functools import partial
from os import path
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import ifaddr
import ingenialogger
from ingenialink import CanBaudrate, CanDevice, NetDevEvt, NetState
from ingenialink.canopen.network import CAN_CHANNELS, CanopenNetwork
from ingenialink.canopen.servo import CanopenServo
from ingenialink.dictionary import Interface
from ingenialink.emcy import EmergencyMessage
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.enums.servo import ServoState
from ingenialink.eoe.network import EoENetwork
from ingenialink.ethercat.network import EthercatNetwork, GilReleaseConfig
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.exceptions import ILError
from ingenialink.network import SlaveInfo
from ingenialink.register import Register
from ingenialink.servo import DictionaryFactory, Servo
from ingenialink.virtual.network import VirtualNetwork
from ping3 import ping
from virtual_drive.core import VirtualDrive

from ingeniamotion.exceptions import IMFirmwareLoadError, IMRegisterWrongAccessError

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

import contextlib

from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

RUNNING_ON_WINDOWS = platform.system() == "Windows"

if RUNNING_ON_WINDOWS:
    from ingenialink.get_adapters_addresses import (  # type: ignore [import-not-found]
        AdapterFamily,
        ScanFlags,
        get_adapters_addresses,
    )

FILE_EXT_SFU = ".sfu"
FILE_EXT_LFU = ".lfu"
FIRMWARE_FILE_FAIL_MSG = "The firmware file could not be loaded correctly"


@dataclass
class IMRegisterUpdateObserver:
    """Ingeniamotion register update observer."""

    im_callback: Callable[[str, Servo, Register, Union[int, float, str, bytes]], None]
    alias: str


@dataclass
class IMEmergencyMessageObserver:
    """Ingeniamotion emergency message observer."""

    im_callback: Callable[[str, EmergencyMessage], None]
    alias: str


@dataclass
class NetworkAdapter:
    """Class to represent a network adapter."""

    interface_index: int
    interface_name: str
    interface_guid: str


class Communication:
    """Communication."""

    FORCE_SYSTEM_BOOT_COCO_REGISTER = "DRV_BOOT_COCO_FORCE"
    FORCE_SYSTEM_BOOT_MOCO_REGISTER = "DRV_BOOT_MOCO_MODE"
    SYSTEM_RESET_MOCO_REGISTER = "DRV_BOOT_RESET"

    PASSWORD_FORCE_BOOT_COCO = 0x424F4F54
    PASSWORD_FORCE_BOOT_MOCO = 0x426F6F74
    PASSWORD_SYSTEM_RESET = 0x72657365

    ENSEMBLE_FIRMWARE_EXTENSION = ".zfu"
    ENSEMBLE_SLAVE_REV_NUM_MASK = 0x1000000

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)
        self.__virtual_drive: Optional[VirtualDrive] = None
        self.register_update_observers: dict[Servo, list[IMRegisterUpdateObserver]] = {}
        self.emergency_messages_observers: dict[Servo, list[IMEmergencyMessageObserver]] = {}

    def connect_servo_eoe(
        self,
        ip: str,
        dict_path: Optional[str] = None,
        alias: str = DEFAULT_SERVO,
        port: int = 1061,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by Ethernet over EtherCAT.

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
            is_eoe=True,
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
        """Connect to target servo by Ethernet.

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

    def connect_servo_virtual(
        self,
        dict_path: Optional[str] = None,
        alias: str = DEFAULT_SERVO,
        port: int = 1061,
        connection_timeout: int = 1,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to the virtual drive using an ethernet communication.

        Args:
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
        if dict_path is not None and not path.isfile(dict_path):
            raise FileNotFoundError(f"{dict_path} file does not exist!")

        if self.__virtual_drive is None:
            self.__virtual_drive = VirtualDrive(port, dictionary_path=dict_path)
            self.__virtual_drive.start()

        self.mc.net[alias] = VirtualNetwork()
        net = self.mc.net[alias]
        servo = net.connect_to_slave(
            self.__virtual_drive.dictionary_path,
            port,
            connection_timeout,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )

        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = alias

    def __servo_connect(
        self,
        ip: str,
        dict_path: str,
        alias: str,
        port: int = 1061,
        connection_timeout: int = 1,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        is_eoe: bool = False,
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
            is_eoe=is_eoe,
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
        r"""Connect to target servo by Ethernet over EtherCAT.

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
            NotImplementedError: If this method is run in Linux.
            FileNotFoundError: If the dict file doesn't exist.
            ValueError: ip must be a subnetwork of 192.168.3.0/24
            ingenialink.exceptions.ILError: If the EoE service is not running
            ingenialink.exceptions.ILError: If the EoE service cannot be started on the network
                                            interface.
        """
        if not RUNNING_ON_WINDOWS:
            raise NotImplementedError("EoE service only works on windows.")
        if not path.isfile(dict_path):
            raise FileNotFoundError(f"{dict_path} file does not exist!")
        if ifname not in self.mc.net:
            self.mc.net[ifname] = EoENetwork(ifname)
        net = self.mc.net[ifname]
        try:
            servo = net.connect_to_slave(
                slave,
                ip,
                dict_path,
                port,
                servo_status_listener=servo_status_listener,
                net_status_listener=net_status_listener,
            )
        except ILError as e:
            if len(net.servos) == 0:
                del self.mc.net[ifname]
            raise e
        servo.slave = slave  # type: ignore [attr-defined]
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
        """Connect to target servo by Ethernet over EtherCAT.

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
            FileNotFoundError: If the dict file doesn't exist.
            ValueError: ip must be a subnetwork of 192.168.3.0/24
            ingenialink.exceptions.ILError: If the EoE service is not running
            ingenialink.exceptions.ILError: If the EoE service cannot be started on the network
                                            interface.
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

    def connect_servo_comkit(
        self,
        ip: str,
        coco_dict_path: str,
        moco_dict_path: str,
        alias: str = DEFAULT_SERVO,
        port: int = 1061,
        connection_timeout: int = 1,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo using a COM-KIT.

        Args:
            ip : servo IP
            coco_dict_path : COCO dictionary path.
            moco_dict_path : MOCO dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            port : servo port. ``1061`` by default.
            connection_timeout: Timeout in seconds for connection.
                ``1`` seconds by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            FileNotFoundError: If a dict file doesn't exist.
            ingenialink.exceptions.ILError: If the servo's IP or port is incorrect.
        """
        for dict_path in [coco_dict_path, moco_dict_path]:
            if not path.isfile(dict_path):
                raise FileNotFoundError(f"{dict_path} file does not exist!")
        self.__servo_connect(
            ip,
            moco_dict_path,
            alias,
            port,
            connection_timeout,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
        )
        coco_dict = DictionaryFactory.create_dictionary(coco_dict_path, Interface.ETH)
        self.mc.servos[alias].dictionary += coco_dict

    @classmethod
    def __get_adapter_name(cls, index: int) -> str:
        """Returns the adapter name of an adapter based on its index.

        Args:
            index : position of interface selected in
                :func:`get_interface_name_list`.
        """
        adapter_name = cls.get_interface_name_list()[index]
        adapter_guid = cls.get_network_adapters()[adapter_name]
        if RUNNING_ON_WINDOWS:
            return f"\\Device\\NPF_{adapter_guid}"
        return adapter_name

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
        try:
            index = self._get_interface_index_by_address(address)
        except IndexError:
            raise ValueError(
                f"Could not found a adapter configured as {address} to connect as EtherCAT master"
            )
        return self.__get_adapter_name(index)

    @staticmethod
    def _get_interface_index_by_address(address: str) -> int:
        """Get the interface index by searching its IP address.

        Args:
            address: IP address of the adapter.

        Returns:
            Interface's index.

        Raises:
            IndexError: If no adapter matches the IP address.

        """
        for idx, adapter in enumerate(ifaddr.get_adapters()):
            for ip in adapter.ips:
                if ip.is_IPv4 and ip.ip == address:
                    return idx
        raise IndexError

    def get_ifname_by_index(self, index: int) -> str:
        """Return interface name by index.

        Args:
            index : position of interface selected in
                :func:`get_interface_name_list`.

        Returns:
            Real name of selected interface.
            It can be used for functions :func:`connect_servo_eoe_service` and
            :func:`connect_servo_ethercat`.

        Raises:
            IndexError: If interface index is out of range.

        """
        return self.__get_adapter_name(index)

    @classmethod
    def get_interface_name_list(cls) -> list[str]:
        """Get interface list.

        Returns:
            List with interface readable names.

        """
        network_adapters = cls.get_network_adapters()
        return list(network_adapters)

    @staticmethod
    def get_network_adapters() -> dict[str, str]:
        """Get the detected network adapters.

        Returns:
            Dictionary with interface readable names as keys and GUIDs as values.

        """
        network_adapters = []
        for adapter in ifaddr.get_adapters():
            if isinstance(adapter.name, bytes):
                adapter_guid = bytes.decode(adapter.name)
            else:
                adapter_guid = adapter.name
            network_adapters.append(NetworkAdapter(adapter.index, adapter.nice_name, adapter_guid))
        if RUNNING_ON_WINDOWS:
            ethernet_adapter_type = (
                6  # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ns-ifdef-net_luid_lh
            )
            network_adapters.extend(
                [
                    NetworkAdapter(
                        interface_index=adapter.IfIndex,
                        interface_name=adapter.Description,
                        interface_guid=adapter.AdapterName,
                    )
                    for adapter in get_adapters_addresses(
                        adapter_families=AdapterFamily.INET,
                        scan_flags=[
                            ScanFlags.INCLUDE_PREFIX,
                            ScanFlags.INCLUDE_ALL_INTERFACES,
                        ],
                    )
                    if adapter.IfType == ethernet_adapter_type and len(adapter.FirstUnicastAddress)
                ]
            )
        return {adapter.interface_name: adapter.interface_guid for adapter in network_adapters}

    def get_available_canopen_devices(self) -> dict[CanDevice, list[int]]:
        """Return the list of available CAN devices (those connected and with drivers installed).

        Returns:
            Dict of available CAN devices and channels. For example:
            {
                CanDevice.KVASER: [0, 1]
                CanDevice.PCAN: [0]
            }
        """
        available_devices: dict[CanDevice, list[int]] = {}
        can_net = None
        for net_key in self.mc.net:
            net = self.mc.net[net_key]
            if isinstance(net, CanopenNetwork):
                can_net = net
                break
        if can_net is None:
            can_net = CanopenNetwork(CanDevice.KVASER)
        for device, channel in can_net.get_available_devices():
            can_device = CanDevice(device)
            can_channel = CAN_CHANNELS[device].index(channel)
            if can_device not in available_devices:
                available_devices[can_device] = [can_channel]
            else:
                available_devices[can_device].append(can_channel)
        return available_devices

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
        """Connect to target servo by Ethernet over EtherCAT.

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
            FileNotFoundError: If the dict file doesn't exist.
            ValueError: ip must be a subnetwork of 192.168.3.0/24
            ingenialink.exceptions.ILError: If the EoE service is not running
            ingenialink.exceptions.ILError: If the EoE service cannot be started on the network
                                            interface.
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

    def scan_servos_eoe_service(self, ifname: str) -> list[int]:
        r"""Return a List of available servos.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.

        Returns:
            Drives available in the target interface.

        Raises:
            NotImplementedError: If this method is run in Linux.
            ingenialink.exceptions.ILError: If the EoE service is not running
            TypeError: If some parameter has a wrong type.
        """
        if not RUNNING_ON_WINDOWS:
            raise NotImplementedError("EoE service only works on windows.")
        net = self.mc.net[ifname] if ifname in self.mc.net else EoENetwork(ifname)
        slaves = net.scan_slaves()
        if not isinstance(slaves, list):
            raise TypeError("Slaves are not saved in a list")
        return slaves

    def scan_servos_eoe_service_interface_index(self, if_index: int) -> list[int]:
        """Return a list of available servos.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.

        Returns:
            Drives available in the target interface.

        Raises:
            IndexError: If interface index is out of range.
            ingenialink.exceptions.ILError: If the EoE service is not running

        """
        return self.scan_servos_eoe_service(self.get_ifname_by_index(if_index))

    def connect_servo_canopen(
        self,
        can_device: CanDevice,
        dict_path: str,
        node_id: int,
        baudrate: CanBaudrate = CanBaudrate.Baudrate_1M,
        channel: int = 0,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> None:
        """Connect to target servo by CANOpen.

        Args:
            can_device : CANOpen device type.
            dict_path : servo dictionary path.
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

        net_key = f"{can_device}_{channel}_{baudrate}"
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        servo = net.connect_to_slave(node_id, dict_path, servo_status_listener, net_status_listener)
        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = net_key

    def connect_servo_ethercat(
        self,
        interface_name: str,
        slave_id: int,
        dict_path: str,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ) -> None:
        r"""Connect to an EtherCAT slave - CoE.

        Args:
            interface_name : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            slave_id: EtherCAT slave ID.
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.
            gil_release_config: GIL release configuration.

        Raises:
            FileNotFoundError: If the dict file doesn't exist.

        """
        if not path.isfile(dict_path):
            raise FileNotFoundError(f"Dict file {dict_path} does not exist!")
        if interface_name not in self.mc.net:
            self.mc.net[interface_name] = EthercatNetwork(
                interface_name, gil_release_config=gil_release_config
            )
        net = self.mc.net[interface_name]
        try:
            servo = net.connect_to_slave(
                slave_id,
                dict_path,
                servo_status_listener=servo_status_listener,
                net_status_listener=net_status_listener,
            )
        except ILError as e:
            if len(net.servos) == 0:
                del self.mc.net[interface_name]
            raise e
        self.mc.servos[alias] = servo
        self.mc.servo_net[alias] = interface_name

    def connect_servo_ethercat_interface_index(
        self,
        if_index: int,
        slave_id: int,
        dict_path: str,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ) -> None:
        """Connect to an EtherCAT slave - CoE.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
            slave_id: EtherCAT slave ID.
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.
            gil_release_config: GIL release configuration.

        Raises:
            IndexError: If interface index is out of range.

        """
        self.connect_servo_ethercat(
            self.get_ifname_by_index(if_index),
            slave_id,
            dict_path,
            alias,
            servo_status_listener,
            net_status_listener,
            gil_release_config=gil_release_config,
        )

    def connect_servo_ethercat_interface_ip(
        self,
        interface_ip: str,
        slave_id: int,
        dict_path: str,
        alias: str = DEFAULT_SERVO,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ) -> None:
        """Connect to an EtherCAT slave - CoE.

        Args:
            interface_ip : IP of the interface to be connected to.
            slave_id: EtherCAT slave ID.
            dict_path : servo dictionary path.
            alias : servo alias to reference it. ``default`` by default.
            servo_status_listener : Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener : Toggle the listener of the network
                status, connection and disconnection.
            gil_release_config: GIL release configuration.

        """
        self.connect_servo_ethercat(
            self.get_ifname_from_interface_ip(interface_ip),
            slave_id,
            dict_path,
            alias,
            servo_status_listener,
            net_status_listener,
            gil_release_config=gil_release_config,
        )

    @staticmethod
    def scan_servos_ethercat_with_info(
        interface_name: str, gil_release_config: GilReleaseConfig = GilReleaseConfig()
    ) -> OrderedDict[int, SlaveInfo]:
        r"""Scan a network adapter.

         Get all connected EtherCAT slaves including slave information.

        Args:
            interface_name : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            gil_release_config: GIL release configuration.

        Returns:
            Dictionary of nodes available in the network and slave information.

        Raises:
            TypeError: If some parameter has a wrong type.
        """
        net = EthercatNetwork(interface_name, gil_release_config=gil_release_config)
        slaves_info = net.scan_slaves_info()
        return slaves_info

    def scan_servos_ethercat(
        self, interface_name: str, gil_release_config: GilReleaseConfig = GilReleaseConfig()
    ) -> list[int]:
        r"""Scan a network adapter to get all connected EtherCAT slaves.

        Args:
            interface_name : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            gil_release_config: GIL release configuration.

        Returns:
            List of EtherCAT slaves available in the network.

        Raises:
            TypeError: If some parameter has a wrong type.
        """
        net = EthercatNetwork(interface_name, gil_release_config=gil_release_config)
        slaves = net.scan_slaves()
        return slaves

    def scan_servos_ethercat_interface_ip(self, interface_ip: str) -> list[int]:
        """Scan a network adapter to get all connected EtherCAT slaves.

        Args:
            interface_ip : IP of the interface to be connected to.

        Returns:
            List of EtherCAT slaves available in the network.

        """
        return self.scan_servos_ethercat(self.get_ifname_from_interface_ip(interface_ip))

    def scan_servos_ethercat_interface_index(self, if_index: int) -> list[int]:
        """Scan a network adapter to get all connected EtherCAT slaves.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.

        Returns:
            List of EtherCAT slaves available in the network.

        Raises:
            IndexError: If interface index is out of range.

        """
        return self.scan_servos_ethercat(self.get_ifname_by_index(if_index))

    def scan_servos_canopen_with_info(
        self,
        can_device: CanDevice,
        baudrate: CanBaudrate = CanBaudrate.Baudrate_1M,
        channel: int = 0,
    ) -> OrderedDict[int, SlaveInfo]:
        """Scan CANOpen device network to get all nodes including slave information.

        Args:
            can_device : CANOpen device type.
            baudrate : communication baudrate. 1 Mbit/s by default.
            channel : CANOpen device channel. ``0`` by default.

        Returns:
            Dictionary of nodes available in the network and slave information.

        Raise:
            TypeError: If some parameter has a wrong type.
        """
        net_key = f"{can_device}_{channel}_{baudrate}"
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        if net is None:
            self.logger.warning(
                "Could not find any nodes in the network.Device: %s, channel: %s and baudrate: %s.",
                can_device,
                channel,
                baudrate,
            )
            return []
        slaves_info = net.scan_slaves_info()
        return slaves_info

    def scan_servos_canopen(
        self,
        can_device: CanDevice,
        baudrate: CanBaudrate = CanBaudrate.Baudrate_1M,
        channel: int = 0,
    ) -> list[int]:
        """Scan CANOpen device network to get all nodes.

        Args:
            can_device : CANOpen device type.
            baudrate : communication baudrate. 1 Mbit/s by default.
            channel : CANOpen device channel. ``0`` by default.

        Returns:
            List of node ids available in the network.

        Raises:
            TypeError: If some parameter has a wrong type.
        """
        net_key = f"{can_device}_{channel}_{baudrate}"
        if net_key not in self.mc.net:
            self.mc.net[net_key] = CanopenNetwork(can_device, channel, baudrate)
        net = self.mc.net[net_key]

        if net is None:
            self.logger.warning(
                "Could not find any nodes in the network.Device: %s, channel: %s and baudrate: %s.",
                can_device,
                channel,
                baudrate,
            )
            return []
        slaves = net.scan_slaves()
        return slaves

    @staticmethod
    def scan_servos_ethernet(
        subnet: str,
    ) -> list[str]:
        """Scan Ethernet device network to get all nodes.

        Args:
            subnet: The subnet in CIDR notation. For instance ``192.168.1.1/24``.

        Returns:
            List of drive IPs available in the network.

        """
        net = EthernetNetwork(subnet)
        slaves = net.scan_slaves()
        return slaves

    @staticmethod
    def scan_servos_ethernet_with_info(
        subnet: str,
    ) -> OrderedDict[str, SlaveInfo]:
        """Scan Ethernet device network to get all nodes including drive information.

        Args:
            subnet: The subnet in CIDR notation. For instance ``192.168.1.1/24``.

        Returns:
            Dictionary of nodes available in the network and drive information.

        """
        net = EthernetNetwork(subnet)
        slaves_info = net.scan_slaves_info()
        return slaves_info

    def disconnect(self, servo: str = DEFAULT_SERVO) -> None:
        """Disconnect servo.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        network = self.mc._get_network(servo)
        network.disconnect_from_slave(drive)
        if isinstance(network, VirtualNetwork) and self.__virtual_drive:
            self.__virtual_drive.stop()
            self.__virtual_drive = None
        del self.mc.servos[servo]
        net_name = self.mc.servo_net.pop(servo)
        servo_count = list(self.mc.servo_net.values()).count(net_name)
        if self.mc.fsoe_is_installed:
            self.mc.fsoe._delete_master_handler(servo)
        if servo_count == 0:
            del self.mc.net[net_name]

    def get_servo_state(self, servo: str = DEFAULT_SERVO) -> NetState:
        """Get the network state of a servo (connected/disconnected).

        The net_status_listener should be enabled for the servo in order
        for the state to be updated.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            The servo's state.

        """
        drive = self.mc._get_drive(servo)
        network = self.mc._get_network(servo)
        return network.get_servo_state(drive.target)

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
            IMRegisterNotExistError: If the register doesn't exist.
            TypeError: If some parameter has a wrong type.

        """
        drive = self.mc._get_drive(servo)
        register_dtype = self.mc.info.register_type(register, axis, servo=servo)
        value = drive.read(register, subnode=axis)
        if register_dtype.value <= RegDtype.S64.value and isinstance(value, int):
            return int(value)
        if not isinstance(value, (int, float, str)):
            raise TypeError("Register value is not a correct type of value.")
        return value

    def set_register(
        self,
        register: str,
        value: Union[int, float, str],
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
            IMRegisterNotExistError: If the register doesn't exist.
            IMRegisterWrongAccessError: If the register access is read-only.

        """
        drive = self.mc._get_drive(servo)
        register_dtype_value = self.mc.info.register_type(register, axis, servo=servo)
        register_access_type = self.mc.info.register_info(register, axis, servo=servo).access
        signed_int = [RegDtype.S8, RegDtype.S16, RegDtype.S32, RegDtype.S64]
        unsigned_int = [RegDtype.U8, RegDtype.U16, RegDtype.U32, RegDtype.U64]
        if register_dtype_value == RegDtype.FLOAT and not isinstance(value, (int, float)):
            raise TypeError("Value must be a float")
        if register_dtype_value == RegDtype.STR and not isinstance(value, str):
            raise TypeError("Value must be a string")
        if register_dtype_value in signed_int and not isinstance(value, int):
            raise TypeError("Value must be an int")
        if register_dtype_value in unsigned_int and (not isinstance(value, int) or value < 0):
            raise TypeError("Value must be an unsigned int")
        if register_access_type == RegAccess.RO:
            raise IMRegisterWrongAccessError(
                f"Register: {register} cannot write to a read-only register"
            )
        drive.write(register, value, subnode=axis)

    def subscribe_net_status(
        self, callback: Callable[[NetDevEvt], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Add a callback to net status change event.

        Args:
            callback : when net status changes callback is called.
            servo : servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        network.subscribe_to_status(drive.target, callback)

    def unsubscribe_net_status(
        self, callback: Callable[[NetDevEvt], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Remove net status change event callback.

        Args:
            callback : callback to remove.
            servo : servo alias to reference it. ``default`` by default.

        """
        network = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        network.unsubscribe_from_status(drive.target, callback)

    def subscribe_servo_status(
        self, callback: Callable[[ServoState, int], Any], servo: str = DEFAULT_SERVO
    ) -> None:
        """Add a callback to servo status change event.

        Args:
            callback : when servo status changes callback is called.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.subscribe_to_status(callback)

    def unsubscribe_servo_status(
        self, callback: Callable[[ServoState, int], Any], servo: str = DEFAULT_SERVO
    ) -> None:
        """Remove servo status change event callback.

        Args:
            callback : callback to remove.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.unsubscribe_from_status(callback)

    def subscribe_register_update(
        self,
        callback: Callable[[str, Servo, Register, Union[int, float, str, bytes]], None],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Subscribe to register updates.

        The callback will be called when a read/write operation occurs.

        Args:
            callback: Callable that takes a servo alias, Servo and Register instances
            and the register value as arguments.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)

        if drive not in self.register_update_observers:
            # Servo that has not been subscribed yet
            self.register_update_observers[drive] = []
            # Subscribe to ingenialink
            drive.register_update_subscribe(self._il_register_subscribe_callback)

        self.register_update_observers[drive].append(
            IMRegisterUpdateObserver(callback, alias=servo)
        )

    def unsubscribe_register_update(
        self,
        callback: Callable[[str, Servo, Register, Union[int, float, str, bytes]], None],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Unsubscribe from register updates.

        Args:
            callback: Subscribed callback.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        for observer in self.register_update_observers[drive]:
            if observer.im_callback == callback:
                self.register_update_observers[drive].remove(observer)
                break

        if len(self.register_update_observers[drive]) == 0:
            del self.register_update_observers[drive]
            # No observers, unsubscribe from ingenialink
            drive.register_update_unsubscribe(self._il_register_subscribe_callback)

    def _il_register_subscribe_callback(
        self, servo_instance: Servo, register: Register, value: Union[int, float, str, bytes]
    ) -> None:
        """This method will be the one subscribed to ingenialink.

        When called, the servo alias will be added to the received information.

        Args:
            servo_instance: The servo instance.
            register: The register object.
            value: The updated register value.

        """
        for observer in self.register_update_observers[servo_instance]:
            observer.im_callback(observer.alias, servo_instance, register, value)

    def subscribe_emergency_message(
        self,
        callback: Callable[[str, EmergencyMessage], None],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Subscribe to emergency messages.

        Only available for CANopen and EtherCAT CoE protocols.

        Args:
            callback :  Callable that takes a servo alias and an EmergencyMessage
            instance as arguments.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)

        if drive not in self.emergency_messages_observers:
            # Servo that has not been subscribed yet
            self.emergency_messages_observers[drive] = []
            # Subscribe to ingenialink
            drive.emcy_subscribe(self._il_emergency_message_callback)

        self.emergency_messages_observers[drive].append(
            IMEmergencyMessageObserver(callback, alias=servo)
        )

    def unsubscribe_emergency_message(
        self,
        callback: Callable[[str, EmergencyMessage], None],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Unsubscribe from emergency messages.

        Only available for CANopen and EtherCAT CoE protocols.

        Args:
            callback : Subscribed callback.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        for observer in self.emergency_messages_observers[drive]:
            if observer.im_callback == callback:
                self.emergency_messages_observers[drive].remove(observer)
                break

        if len(self.emergency_messages_observers[drive]) == 0:
            del self.emergency_messages_observers[drive]
            # No observers, unsubscribe from ingenialink
            drive.emcy_unsubscribe(self._il_emergency_message_callback)

    def _il_emergency_message_callback(self, emergency_message: EmergencyMessage) -> None:
        """This method will be the one subscribed to ingenialink.

        When called, the servo alias will be added to the received information.

        Args:
            emergency_message: The EmergencyMessage  instance.

        """
        for observer in self.emergency_messages_observers[emergency_message.servo]:
            observer.im_callback(observer.alias, emergency_message)

    def load_firmware_canopen(
        self,
        fw_file: str,
        servo: str = DEFAULT_SERVO,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        error_enabled_callback: Optional[Callable[[bool], None]] = None,
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
        if not isinstance(drive, CanopenServo):
            raise ValueError("Target servo is not a Canopen servo")
        if status_callback is None:
            status_callback = partial(self.logger.info, "Load firmware status: %s")
        if progress_callback is None:
            progress_callback = partial(self.logger.info, "Load firmware progress: %s")
        if fw_file.endswith(self.ENSEMBLE_FIRMWARE_EXTENSION):
            self.__load_ensemble_fw_canopen(
                net,
                fw_file,
                drive,
                status_callback,
                progress_callback,
                error_enabled_callback,
            )
        else:
            net.load_firmware(
                int(drive.target),
                fw_file,
                status_callback,
                progress_callback,
                error_enabled_callback,
            )

    @staticmethod
    def __get_boot_in_app(fw_file: str) -> bool:
        """Return true if the bootloader is included in the application (file extension is .sfu).

        Args:
            fw_file: Path to the FW file.

        Returns:
            True if the bootloader is included in the application.

        Raises:
            ValueError: If the firmware file has the wrong extension.
        """
        if not fw_file.endswith((FILE_EXT_SFU, FILE_EXT_LFU)):
            raise ValueError(
                f"Firmware file should have extension {FILE_EXT_SFU} or {FILE_EXT_LFU}."
            )
        return fw_file.endswith(FILE_EXT_SFU)

    def load_firmware_ecat(
        self,
        ifname: str,
        fw_file: str,
        slave: int = 1,
        boot_in_app: Optional[bool] = None,
        password: Optional[int] = None,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ) -> None:
        r"""Load firmware via ECAT.

        Args:
            ifname : interface name. It should have format
                ``\\Device\\NPF_[...]``.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.
            boot_in_app: true if the bootloader is included in the application, false otherwise.
                If None, the file extension is used to define it.
            password: Password to load the firmware file. If ``None`` the default password will be
                used.
            gil_release_config: GIL release config.

        Raises:
            FileNotFoundError: If the firmware file cannot be found.
            ValueError: If the firmware file has the wrong extension.
            ingenialink.exceptions.ILFirmwareLoadError: If no slave is detected.
            ingenialink.exceptions.ILFirmwareLoadError: If the FoE write operation fails.

        """
        net = EthercatNetwork(ifname, gil_release_config=gil_release_config)
        if fw_file.endswith(self.ENSEMBLE_FIRMWARE_EXTENSION):
            self.__load_ensemble_fw_ecat(net, fw_file, slave, boot_in_app, password)
        else:
            boot_in_app = self.__get_boot_in_app(fw_file) if boot_in_app is None else boot_in_app
            net.load_firmware(fw_file, boot_in_app, slave, password)

    def load_firmware_ecat_interface_index(
        self,
        if_index: int,
        fw_file: str,
        slave: int = 1,
        boot_in_app: Optional[bool] = None,
        password: Optional[int] = None,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ) -> None:
        """Load firmware via ECAT.

        Args:
            if_index : interface index in list given by function
                :func:`get_interface_name_list`.
            fw_file : Firmware file path.
            slave : slave index. ``1`` by default.
            boot_in_app: true if the bootloader is included in the application, false otherwise.
                If ``None``, the file extension is used to define it.
            password: Password to load the firmware file. If ``None`` the default password will be
                used.
            gil_release_config: GIL release config.

        Raises:
            IndexError: If interface index is out of range.
            FileNotFoundError: If the firmware file cannot be found.
            ingenialink.exceptions.ILFirmwareLoadError: If no slave is detected.
            ingenialink.exceptions.ILFirmwareLoadError: If the FoE write operation is not successful
            NotImplementedError: If FoE is not implemented for the current OS and architecture

        """
        self.load_firmware_ecat(
            self.get_ifname_by_index(if_index),
            fw_file,
            slave,
            boot_in_app,
            password,
            gil_release_config=gil_release_config,
        )

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
        ftp_user = ftp_user or "Ingenia"
        ftp_pwd = ftp_pwd or "Ingenia"
        net.load_firmware(fw_file, ip, ftp_user, ftp_pwd)

    @staticmethod
    def __ftp_ping(ip: str) -> bool:
        response = ping(ip, timeout=1)
        return isinstance(response, float)

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
        ip = str(drive.target)
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
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        net.stop_status_listener()
        drive.stop_status_listener()
        with contextlib.suppress(ILError):
            self.mc.communication.set_register(
                self.FORCE_SYSTEM_BOOT_COCO_REGISTER,
                self.PASSWORD_FORCE_BOOT_COCO,
                servo=servo,
                axis=0,
            )
        self.disconnect(servo)

    def load_firmware_moco(
        self,
        fw_file: str,
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Load firmware to the Motion Core.

        .. warning::
            After functions ends, the servo will take a moment to load firmware.
            During the process, the servo will be not operative.

        Args:
            fw_file : Firmware file path.
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If servo is not connected via Ethernet.

        """
        default_node = 10
        default_subnode = 1
        default_port = 1061
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        ip = str(drive.target)
        if not isinstance(net, EthernetNetwork):
            raise ValueError("Target servo is not connected via Ethernet")
        net.load_firmware_moco(default_node, default_subnode, ip, default_port, fw_file)

    def boot_mode_moco(self, servo: str = DEFAULT_SERVO) -> None:
        """Set the Motion Core to boot mode.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        net = self.mc._get_network(servo)
        drive = self.mc._get_drive(servo)
        net.stop_status_listener()
        drive.stop_status_listener()
        try:
            self.mc.communication.set_register(
                self.FORCE_SYSTEM_BOOT_MOCO_REGISTER,
                self.PASSWORD_FORCE_BOOT_MOCO,
                servo=servo,
            )
        except ILError as e:
            self.logger.debug(e)
        try:
            self.mc.communication.set_register(
                self.SYSTEM_RESET_MOCO_REGISTER,
                self.PASSWORD_FORCE_BOOT_MOCO,
                servo=servo,
            )
        except ILError as e:
            self.logger.debug(e)

    def __load_ensemble_fw_canopen(
        self,
        net: CanopenNetwork,
        fw_file: str,
        slave: CanopenServo,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        error_enabled_callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Load FW to an ensemble of servos through Canopen (in parallel).

        The FW files that are contained in the fw_file will be loaded by selecting any slave which
        is part of the ensemble.

        Args:
            net: Canopen network.
            fw_file: Path to the ensemble FW file.
            slave: Servo object.
            status_callback : callback with status.
            progress_callback : callback with progress.
            error_enabled_callback : callback with errors enabled.

        Raises:
            IMFirmwareLoadError: If the load FW process of any slave failed.
        """
        with tempfile.TemporaryDirectory() as ensemble_temp_dir:
            mapping = self.__unzip_ensemble_fw_file(fw_file, ensemble_temp_dir)
            scanned_slaves = net.scan_slaves_info()
            first_slave_in_ensemble = self.__check_ensemble(
                scanned_slaves, int(slave.target), mapping
            )
            dictionary_path = slave.dictionary.path
            connected_drives = {int(slave.target): slave for slave in net.servos}
            for slave_id_offset in mapping:
                slave_id = first_slave_in_ensemble + slave_id_offset
                if slave_id not in connected_drives:
                    net.connect_to_slave(slave_id, dictionary_path)
            try:
                for slave_id_offset, fw_file_prod_code in mapping.items():
                    slave_id = first_slave_in_ensemble + slave_id_offset
                    net.load_firmware(
                        slave_id,
                        fw_file_prod_code[0],
                        status_callback,
                        progress_callback,
                        error_enabled_callback,
                    )
            except ILError as e:
                raise IMFirmwareLoadError(
                    f"{FIRMWARE_FILE_FAIL_MSG} on node {slave_id}. Exception: {e}"
                )

    def __load_ensemble_fw_ecat(
        self,
        net: EthercatNetwork,
        fw_file: str,
        slave: int,
        boot_in_app: Optional[bool],
        password: Optional[int],
    ) -> None:
        """Load FW to an ensemble of servos through Ethercat.

        The FW files that are contained in the fw_file will be loaded by selecting any slave which
        is part of the ensemble.

        Args:
            net: Ethercat network.
            fw_file: Path to the ensemble FW file.
            slave: Slave ID (any slave in the ensemble)
            boot_in_app: true if the bootloader is included in the application, false otherwise.
                If None, the file extension is used to define it.
            password: Password to load the firmware file. If ``None`` the default password will be
                used.
        """
        with tempfile.TemporaryDirectory() as ensemble_temp_dir:
            mapping = self.__unzip_ensemble_fw_file(fw_file, ensemble_temp_dir)
            scanned_slaves = net.scan_slaves_info()
            if len(scanned_slaves) == 0:
                raise IMFirmwareLoadError(f"{FIRMWARE_FILE_FAIL_MSG}. No ECAT slave detected.")
            first_slave_in_ensemble = self.__check_ensemble(scanned_slaves, slave, mapping)
            try:
                for slave_id_offset, fw_file_prod_code in mapping.items():
                    boot_in_app_drive = (
                        self.__get_boot_in_app(fw_file_prod_code[0])
                        if boot_in_app is None
                        else boot_in_app
                    )
                    net.load_firmware(
                        fw_file_prod_code[0],
                        boot_in_app_drive,
                        first_slave_in_ensemble + slave_id_offset,
                        password,
                    )
            except ILError as e:
                raise e

    def __check_ensemble(
        self,
        scanned_slaves: OrderedDict[int, SlaveInfo],
        slave_id: int,
        mapping: dict[int, tuple[str, int, int]],
    ) -> int:
        """Check the ensemble.

        Check that a slave is part of the ensemble described in the mapping argument and the
        ensemble is complete (all drives described in the mapping are contained in the list of
        scanned slaves).

        It returns the ID of the first drive in the ensemble.

        Args:
            scanned_slaves: Scanned slaves with the respective information.
            slave_id: Slave ID to be checked.
            mapping: Mapping of the ensemble.

        Raises:
            IMFirmwareLoadError: If the slave ID is not in the scanned slaves list.
            IMFirmwareLoadError: If the ensemble described in the mapping can not be
            found in the list of the scanned slaves.

        Returns:
            The ID of the first drive in the ensemble.
        """
        if slave_id not in scanned_slaves:
            raise IMFirmwareLoadError(
                f"{FIRMWARE_FILE_FAIL_MSG}. The slave {slave_id} is not detected."
            )
        slave_id_offset = self.__check_slave_in_ensemble(scanned_slaves[slave_id], mapping)
        first_slave = slave_id - slave_id_offset
        for map_slave_id_offset in mapping:
            map_slave_id = first_slave + map_slave_id_offset
            if map_slave_id not in scanned_slaves:
                raise IMFirmwareLoadError(
                    f"{FIRMWARE_FILE_FAIL_MSG}. The slave {map_slave_id - 1} is not detected."
                )
            map_slave_info = scanned_slaves[map_slave_id]
            if (
                map_slave_info.product_code != mapping[map_slave_id_offset][1]
                or map_slave_info.revision_number is None
                or (map_slave_info.revision_number & self.ENSEMBLE_SLAVE_REV_NUM_MASK)
                != (mapping[map_slave_id_offset][2] & self.ENSEMBLE_SLAVE_REV_NUM_MASK)
            ):
                raise IMFirmwareLoadError(
                    f"{FIRMWARE_FILE_FAIL_MSG}. The slave {map_slave_id} "
                    f"has wrong product code or revision number."
                )
        return first_slave

    def __check_slave_in_ensemble(
        self, slave_info: SlaveInfo, mapping: dict[int, tuple[str, int, int]]
    ) -> int:
        """Check that a slave is part of the ensemble described in the mapping argument.

        Returns the ID offset (relative position in the ensemble) of the selected slave.

        Args:
            slave_info: Info of the slave to be checked.
            mapping: Mapping of the ensemble.

        Raises:
            IMFirmwareLoadError: If the slave is not part of the ensemble.

        Returns:
            The ID offset (relative position in the ensemble) of the selected slave.
        """
        for slave_id_offset in mapping:
            _, mapping_product_code, mapping_revision_number = mapping[slave_id_offset]
            scanned_product_code = slave_info.product_code
            scanned_revision_number = slave_info.revision_number
            if scanned_product_code is None or scanned_revision_number is None:
                continue
            if mapping_product_code == scanned_product_code and (
                mapping_revision_number & self.ENSEMBLE_SLAVE_REV_NUM_MASK
            ) == (scanned_revision_number & self.ENSEMBLE_SLAVE_REV_NUM_MASK):
                return slave_id_offset
        raise IMFirmwareLoadError(
            f"{FIRMWARE_FILE_FAIL_MSG}. The selected drive is not part of the ensemble."
        )

    def __unzip_ensemble_fw_file(
        self, fw_file: str, unzip_path: str
    ) -> dict[int, tuple[str, int, int]]:
        """Unzip the ensemble FW file and return the mapping.

        Args:
            fw_file: Ensemble FW file to be unzipped.
            unzip_path: Path where to unzip the ensemble

        Returns:
            Mapping described in the ensemble FW file.
                Dict{slave_id_offset: (fw_file, product_code, revision_number)}
        """
        with zipfile.ZipFile(fw_file, "r") as zip_ref:
            zip_ref.extractall(unzip_path)
        with open(path.join(unzip_path, "mapping.json")) as f:
            mapping_info = json.load(f)
        mapping = {}
        for drive in mapping_info["drives"]:
            slave_id_offset = drive["slave_id_offset"]
            fw_file = path.join(path.abspath(unzip_path), drive["fw_file"])
            product_code = drive["product_code"]
            revision_number = drive["revision_number"]
            mapping[slave_id_offset] = fw_file, product_code, revision_number

        return mapping
