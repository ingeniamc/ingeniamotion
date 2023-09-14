import os

from ingenialink import EthernetNetwork
from ingenialink.dictionary import Dictionary, DictionaryCategories
from ingenialink.ethernet.dictionary import EthernetDictionary


class MockDictionary(Dictionary):
    
    def __init__(self) -> None:
        self.part_number = "FAKE_PART_NUMBER"
        self.categories = DictionaryCategories()
        
        
class MockServo():
    
    def __init__(self) -> None:
        self.__fake_registers_subnode_0 = {
            "DRV_ID_PRODUCT_CODE_COCO": 12,
            "DRV_ID_REVISION_NUMBER_COCO": 123,
            "DRV_APP_COCO_VERSION": "4.3.2",
            "DRV_ID_SERIAL_NUMBER_COCO": 3456,
            
        }
        self.__fake_registers_subnode_1 = {
            "DRV_ID_PRODUCT_CODE": 21,
            "DRV_ID_REVISION_NUMBER": 321,
            "DRV_ID_SOFTWARE_VERSION": "2.3.4",
            "DRV_ID_SERIAL_NUMBER": 6543,
        }
        self.__fake_register_values = (
            self.__fake_registers_subnode_0, 
            self.__fake_registers_subnode_1
        )
        
        absolute_path = os.path.dirname(__file__)
        relative_path = "dictionaries/mock_eth.xdf"
        full_path = os.path.join(absolute_path, relative_path)
        self.dictionary = EthernetDictionary(full_path)
        self.target = "FAKE_TARGET"
        self.name = "FAKE_NAME"
        self.subnodes = 5
        
    def read(self, register: str, subnode=0):
        return self.__fake_register_values[subnode][register]
        
        
class MockNetwork(EthernetNetwork):
    
    def __init__(self) -> None:
        pass
