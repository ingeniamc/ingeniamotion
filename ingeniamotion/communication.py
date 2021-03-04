import logging
import ingenialink as il

from os import path
from enum import IntEnum


class Communication:
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

    def connect_servo_eoe(self, ip, dict_path=None, alias="default", protocol=Protocol.UDP, port=1061):
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

    def connect_servo_ethernet(self, ip, dict_path=None, alias="default", protocol=Protocol.UDP, port=1061):
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

    def __servo_connect(self, ip, dict_path, alias, prot, protocol=Protocol.UDP, port=1061):
        if not path.isfile(dict_path):
            raise FileNotFoundError("{} file not exist!".format(dict_path))
        try:
            net, servo = il.lucky(prot, dict_path, address_ip=ip, port_ip=port, protocol=protocol)
            self.mc.servos[alias] = servo
            self.mc.net[alias] = net
        except il.exceptions.ILError as e:
            logging.error("Error trying to connect to the servo. %s.", str(e))
