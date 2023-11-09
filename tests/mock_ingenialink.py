import os
import random

from ingenialink import EthernetNetwork
from ingenialink.dictionary import Dictionary, DictionaryCategories
from ingenialink.enums.register import REG_DTYPE
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingeniamotion.exceptions import IMRegisterNotExist


class MockDictionary(Dictionary):
    def __init__(self) -> None:
        self.part_number = "FAKE_PART_NUMBER"
        self.categories = DictionaryCategories()


class MockServo:
    def __init__(self, dictionary_path="dictionaries/mock_eth.xdf") -> None:
        self.__fake_register_values = {}

        absolute_path = os.path.dirname(__file__)
        full_path = os.path.join(absolute_path, dictionary_path)
        self.dictionary = EthernetDictionary(full_path)
        self.target = "FAKE_TARGET"
        self.name = "FAKE_NAME"
        self.subnodes = 5
        self.__initialize_register_values()
        self.__set_specific_fake_values()

    def __initialize_register_values(self):
        for axis in range(self.dictionary.subnodes):
            self.__fake_register_values[axis] = {}
            for register_uid in self.dictionary.registers(axis):
                self.__set_random_fake_register_value(axis, register_uid)

    def __set_random_fake_register_value(self, axis, register_uid):
        try:
            register = self.dictionary.registers(axis)[register_uid]
        except KeyError:
            raise IMRegisterNotExist(f"Register: {register} axis: {axis} not exist in dictionary")
        register_type = register.dtype

        if register_type == REG_DTYPE.STR:
            self.__fake_register_values[axis][register_uid] = f"FAKE_{register_uid}_VALUE"
        elif register_type == REG_DTYPE.FLOAT:
            self.__fake_register_values[axis][register_uid] = random.uniform(0, 10)
        else:
            self.__fake_register_values[axis][register_uid] = int(random.uniform(0, 10))

    def __set_specific_fake_values(self):
        fake_registers_subnode_0 = {
            "DRV_ID_PRODUCT_CODE_COCO": 12,
            "DRV_ID_REVISION_NUMBER_COCO": 123,
            "DRV_APP_COCO_VERSION": "4.3.2",
            "DRV_ID_SERIAL_NUMBER_COCO": 3456,
        }
        fake_registers_subnode_1 = {
            "DRV_ID_PRODUCT_CODE": 21,
            "DRV_ID_REVISION_NUMBER": 321,
            "DRV_ID_SOFTWARE_VERSION": "2.3.4",
            "DRV_ID_SERIAL_NUMBER": 6543,
            "DRV_ID_VENDOR_ID": 123456789,
        }
        all_fake_register_values = (fake_registers_subnode_0, fake_registers_subnode_1)
        for axis, fake_register_values in enumerate(all_fake_register_values):
            for uid, value in fake_register_values.items():
                self.__fake_register_values[axis][uid] = value

    def read(self, register: str, subnode=0):
        return self.__fake_register_values[subnode][register]

    @property
    def info(self):
        return {
            "name": self.name,
            "serial_number": self.__fake_register_values[0]["DRV_ID_SERIAL_NUMBER_COCO"],
            "firmware_version": self.__fake_register_values[0]["DRV_APP_COCO_VERSION"],
            "product_code": self.__fake_register_values[0]["DRV_ID_PRODUCT_CODE_COCO"],
            "revision_number": self.__fake_register_values[0]["DRV_ID_REVISION_NUMBER_COCO"],
            "hw_variant": "A",
        }


class MockNetwork(EthernetNetwork):
    def __init__(self) -> None:
        pass
