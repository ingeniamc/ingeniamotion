__all__ = [
    "FSOE_MASTER_INSTALLED",
    "FSoEApplicationParameter",
    "FSoEDataType",
    "FSoEDictionary",
    "FSoEDictionaryItem",
    "FSoEDictionaryItemInput",
    "FSoEDictionaryItemInputOutput",
    "FSoEDictionaryItemOutput",
    "FSoEDictionaryMap",
    "FSoEDictionaryMappedItem",
    "BaseMasterHandler",
    "StateData",
    "State",
    "calculate_sra_crc",
    "align_bits",
]

try:
    from fsoe_master.fsoe_master import (
        ApplicationParameter as FSoEApplicationParameter,
    )
    from fsoe_master.fsoe_master import (
        DataType as FSoEDataType,
    )
    from fsoe_master.fsoe_master import (
        Dictionary as FSoEDictionary,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItem as FSoEDictionaryItem,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemInput as FSoEDictionaryItemInput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemInputOutput as FSoEDictionaryItemInputOutput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemOutput as FSoEDictionaryItemOutput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryMap as FSoEDictionaryMap,
    )
    from fsoe_master.fsoe_master import (
        DictionaryMappedItem as FSoEDictionaryMappedItem,
    )
    from fsoe_master.fsoe_master import (
        MasterHandler as BaseMasterHandler,
    )
    from fsoe_master.fsoe_master import State, StateData, align_bits, calculate_sra_crc


except ImportError:
    FSOE_MASTER_INSTALLED = False
else:
    FSOE_MASTER_INSTALLED = True
