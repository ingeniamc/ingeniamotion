from typing import Callable

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError
from tests.dictionaries import (
    SAMPLE_SAFE_PH1_XDFV3_DICTIONARY,
    SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT,
    SAMPLE_SAFE_PH2_XDFV3_DICTIONARY,
)
from tests.fsoe.conftest import MockNetwork, MockServo

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import FSoEMasterHandler, SafeInputsFunction, STOFunction
    from tests.fsoe.conftest import MockHandler


@pytest.mark.fsoe
def test_optional_parameter_not_present():
    handler = MockHandler(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, 0x3800000)

    sto: STOFunction = next(STOFunction.for_handler(handler))

    assert sto.activate_sout is None
    assert sto.parameters == {}


@pytest.mark.fsoe
def test_optional_parameter_present():
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )

    sto: STOFunction = next(STOFunction.for_handler(handler))

    assert sto.activate_sout is not None
    assert len(sto.parameters) == 1
    metadata, parameter = next(iter(sto.parameters.items()))
    assert metadata.uid == "FSOE_STO_ACTIVATE_SOUT"
    assert metadata.display_name == "Activate SOUT"
    assert parameter is not None


def test_get_parameters_not_related_to_safety_functions():
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )
    unrelated_parameters = handler.get_parameters_not_related_to_safety_functions()
    assert {param.register.identifier for param in unrelated_parameters} == {
        *(f"ETG_COMMS_RPDO_MAP256_{i}" for i in range(1, 46)),
        "ETG_COMMS_RPDO_MAP256_TOTAL",
        *(f"ETG_COMMS_TPDO_MAP256_{i}" for i in range(1, 46)),
        "ETG_COMMS_TPDO_MAP256_TOTAL",
        "FSOE_ABS_SSI_PRIM1_BAUD",
        "FSOE_ABS_SSI_PRIM1_FSIZE",
        "FSOE_ABS_SSI_PRIM1_POL",
        "FSOE_ABS_SSI_PRIM1_POSBITS",
        "FSOE_ABS_SSI_PRIM1_STURN",
        "FSOE_ABS_SSI_PRIM1_TOUT",
        "FSOE_ABS_SSI_SECOND1_BAUD",
        "FSOE_ABS_SSI_SECOND1_FSIZE",
        "FSOE_ABS_SSI_SECOND1_PBITS",
        "FSOE_ABS_SSI_SECOND1_POL",
        "FSOE_ABS_SSI_SECOND1_STURN",
        "FSOE_ABS_SSI_SECOND1_TOUT",
        "FSOE_FEEDBACK_RATIO_MAIN_TURNS",
        "FSOE_FEEDBACK_RATIO_REDUNDANT_TURNS",
        "FSOE_FEEDBACK_SCENARIO",
        "FSOE_HALL_POLARITY",
        "FSOE_HALL_POLEPAIRS",
        "FSOE_INCREMENTAL_ENC_POLARITY",
        "FSOE_INCREMENTAL_ENC_RESOLUTION",
        "FSOE_USER_OVER_TEMPERATURE",
    }


@pytest.mark.fsoe
def test_modify_safe_parameters(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        input_map = handler.get_function_instance(SafeInputsFunction).map
        map_uid = "FSOE_SAFE_INPUTS_MAP"

        input_map.set(1)
        assert mock_servo.read(map_uid) == 1

        input_map.set_without_updating(1234)
        assert mock_servo.read(map_uid) == 1

        handler.write_safe_parameters()
        assert mock_servo.read(map_uid) == 1234

    finally:
        handler.delete()


@pytest.mark.fsoe_phase2
def test_write_safe_parameters(mc_with_fsoe):
    mc, handler = mc_with_fsoe
    expected_value = {}
    for key, param in handler.safety_parameters.items():
        old_val = mc.communication.get_register(key)

        # Remove if when SACOAPP-299 is completed
        if key == "FSOE_SSR_ERROR_REACTION_8":
            param.register._enums = {"STO": 0x66400001, "SS1": 0x66500101, "No reaction": 0x0}
        # Remove if when SACOAPP-300 is completed
        if key == "FSOE_SS2_ERROR_REACTION_1":
            param.register._enums = {"STO": 0x66400001, "No reaction": 0x0}
        if param.register.enums:
            enum_values = list(param.register.enums.values())
            enum_values.remove(old_val)
            new_val = enum_values[0]
        else:
            new_val = old_val - 1 if old_val == param.register.range[1] else old_val + 1
        param.set_without_updating(new_val)
        # Ignore RxPDO and TxPDO FSoE Map registers in write_safe_parameters
        if param.register.idx in [0x1700, 0x1B00]:
            expected_value[key] = old_val
        else:
            expected_value[key] = new_val
    handler.write_safe_parameters()
    for key, param in handler.safety_parameters.items():
        test_val = mc.communication.get_register(key)
        assert test_val == expected_value[key], f"Parameter {key} not written correctly"
