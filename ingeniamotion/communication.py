import logging
import ingenialink as il

from os import path
from enum import IntEnum


class Communication(object):
    """Connect.

    Parameters:

    Returns:

    """

    class Protocol(IntEnum):
        UDP = 2
        TCP = 1

    def __init__(self, mc):
        self.mc = mc

    def connect_servo_eoe(self, ip, dict_path=None, alias="default", protocol=Protocol.UDP, port=1061):
        """
            Connect to target servo by Ethernet over EtherCAT

            :param alias: Driver alias
            :param dict_path: servo dictionary path.
            :param ip: servo IP. 192.168.2.22 by default.
            :param protocol: UDP or TCP protocol. UDP by default
            :param port: servo port. 1061 by default
            :return: servo instance
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, il.NET_PROT.ETH, protocol, port)

    def connect_servo_ethernet(self, ip, dict_path=None, alias="default", protocol=Protocol.UDP, port=1061):
        """
            Connect to target driver by Ethernet

            :param alias: Driver alias
            :param dict_path: servo dictionary path.
            :param ip: servo IP. 192.168.2.22 by default.
            :param protocol: UDP or TCP protocol. UDP by default
            :param port: servo port. 1061 by default
            :return: servo instance
        """
        if not dict_path:
            raise TypeError("dict_path argument is missing")
        self.__servo_connect(ip, dict_path, alias, il.NET_PROT.ETH, protocol, port)

    def __servo_connect(self, ip, dict_path, alias, prot, protocol=Protocol.UDP, port=1061):
        if not path.isfile(dict_path):
            logging.error("%s file not exist!", dict_path)
            return
        try:
            net, servo = il.lucky(prot, dict_path, address_ip=ip, port_ip=port, protocol=protocol)
            self.mc.servos[alias] = servo
            self.mc.net[alias] = net
        except Exception as e:
            logging.error("Error trying to connect to the servo.", str(e))
