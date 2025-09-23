from typing import TYPE_CHECKING

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from tests.dictionaries import (
    SAMPLE_SAFE_PH1_XDFV3_DICTIONARY,
    SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT,
    SAMPLE_SAFE_PH2_XDFV3_DICTIONARY,
)

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        ProcessImage,
        SafeHomingFunction,
        SafeInputsFunction,
        SafetyFunction,
        SDIFunction,
        SLIFunction,
        SLPFunction,
        SLSFunction,
        SOSFunction,
        SOutFunction,
        SPFunction,
        SS1Function,
        SS2Function,
        SSRFunction,
        STOFunction,
        SVFunction,
    )
    from ingeniamotion.fsoe_master.fsoe import (
        FSoEDictionaryItemInput,
        FSoEDictionaryItemInputOutput,
    )
    from tests.fsoe.conftest import MockHandler


@pytest.mark.fsoe
def test_detect_safety_functions_ph1() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, 0x3800000)

    sf = list(SafetyFunction.for_handler(handler))
    sf_types = [type(sf) for sf in sf]

    assert sf_types == [STOFunction, SS1Function, SafeInputsFunction]

    # STO
    sto = sf[0]
    assert isinstance(sto, STOFunction)
    assert sto.n_instance is None
    assert sto.name == "Safe Torque Off"
    assert isinstance(sto.command, FSoEDictionaryItemInputOutput)
    assert sto.parameters == {}
    assert len(sto.ios) == 1
    for metadata, io in sto.ios.items():
        assert io == sto.command
        assert metadata.display_name == "Command"
        assert metadata.uid == "FSOE_STO"

    # SS1
    ss1 = sf[1]
    assert isinstance(ss1, SS1Function)
    assert ss1.n_instance == 1
    assert ss1.name == "Safe Stop 1"
    assert isinstance(ss1.command, FSoEDictionaryItemInputOutput)
    assert len(ss1.parameters) == 1
    for metadata, parameter in ss1.parameters.items():
        assert parameter == ss1.time_to_sto
        assert metadata.display_name == "Time to STO"
        assert metadata.uid == "FSOE_SS1_TIME_TO_STO_1"
    assert len(ss1.ios) == 1
    for metadata, io in ss1.ios.items():
        assert io == ss1.command
        assert metadata.display_name == "Command"
        assert metadata.uid == "FSOE_SS1_1"

    # Safe inputs
    si = sf[2]
    assert isinstance(si, SafeInputsFunction)
    assert si.n_instance is None
    assert si.name == "Safe Inputs"
    assert isinstance(si.value, FSoEDictionaryItemInput)
    assert len(si.parameters) == 1
    for metadata, parameter in si.parameters.items():
        assert parameter == si.map
        assert metadata.display_name == "Map"
        assert metadata.uid == "FSOE_SAFE_INPUTS_MAP"
    assert len(si.ios) == 1
    for metadata, io in si.ios.items():
        assert io == si.value
        assert metadata.display_name == "Value"
        assert metadata.uid == "FSOE_SAFE_INPUTS_VALUE"


@pytest.mark.fsoe
def test_detect_safety_functions_ph2() -> None:
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )

    sf_types = [type(sf) for sf in SafetyFunction.for_handler(handler)]

    assert sf_types == [
        STOFunction,
        SS1Function,
        SafeInputsFunction,
        SOSFunction,
        SS2Function,
        SOutFunction,
        SPFunction,
        SVFunction,
        SafeHomingFunction,
        # SLS
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        # SSR
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        # SLP
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SDIFunction,
        SLIFunction,
    ]


@pytest.mark.fsoe
def test_mandatory_safety_functions(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    _, handler = mc_with_fsoe

    safety_functions_by_types = handler.safety_functions_by_type()

    sto_instances = safety_functions_by_types[STOFunction]
    assert len(sto_instances) == 1

    ss1_instances = safety_functions_by_types[SS1Function]
    assert len(ss1_instances) >= 1

    si_instances = safety_functions_by_types[SafeInputsFunction]
    assert len(si_instances) == 1


@pytest.mark.fsoe
def test_getter_of_safety_functions(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    _, handler = mc_with_fsoe

    sto_function = STOFunction(
        n_instance=None,
        name="Dummy",
        command=None,
        activate_sout=None,
        ios=None,
        parameters=None,
        handler=handler,
    )
    ss1_function_1 = SS1Function(
        n_instance=None,
        name="Dummy",
        ios=None,
        parameters=None,
        command=None,
        time_to_sto=None,
        velocity_zero_window=None,
        time_for_velocity_zero=None,
        time_delay_for_deceleration=None,
        deceleration_limit=None,
        activate_sout=None,
        handler=handler,
    )
    ss1_function_2 = SS1Function(
        n_instance=None,
        name="Dummy",
        ios=None,
        parameters=None,
        command=None,
        time_to_sto=None,
        velocity_zero_window=None,
        time_for_velocity_zero=None,
        time_delay_for_deceleration=None,
        deceleration_limit=None,
        activate_sout=None,
        handler=handler,
    )

    handler.safety_functions = (sto_function, ss1_function_1, ss1_function_2)
    handler.get_function_instance.cache_clear()

    # Single instance of STOFunction
    assert handler.get_function_instance(STOFunction) is sto_function
    assert handler.get_function_instance(STOFunction, instance=1) is sto_function

    # Multiple instances of SS1Function
    with pytest.raises(ValueError) as error:
        # Must specify the instance
        handler.get_function_instance(SS1Function)
    assert (
        error.value.args[0]
        == "Multiple SS1Function instances found (2). Specify the instance number."
    )

    with pytest.raises(IndexError) as error:
        # Instance 0 does not exist
        handler.get_function_instance(SS1Function, instance=0)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 0"
    assert handler.get_function_instance(SS1Function, instance=1) is ss1_function_1
    assert handler.get_function_instance(SS1Function, instance=2) is ss1_function_2
    with pytest.raises(IndexError) as error:
        # Instance 3 does not exist
        handler.get_function_instance(SS1Function, instance=3)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 3"


@pytest.mark.fsoe_phase2
def test_ss2_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    process_image = ProcessImage.empty(handler.dictionary)
    handler.set_process_image(process_image)
    ss2_instance = handler.get_function_instance(SS2Function)
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(3)
    assert ss2_instance.activated_by() is si_instance
    si_instance.map.set(0)
    assert ss2_instance.activated_by() is None
    for slp_func in handler.safety_functions_by_type()[SLPFunction]:
        process_image.insert_safety_function(slp_func)
        slp_func.error_reaction.set(0x66700101)
        assert ss2_instance.activated_by() is slp_func
        slp_func.error_reaction.set(0)
        assert ss2_instance.activated_by() is None


@pytest.mark.fsoe_phase2
def test_sos_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    process_image = ProcessImage.empty(handler.dictionary)
    handler.set_process_image(process_image)
    sos_instance = handler.get_function_instance(SOSFunction)
    ss2_instance = handler.get_function_instance(SS2Function)
    assert sos_instance.activated_by() is None
    process_image.insert_safety_function(ss2_instance)
    assert sos_instance.activated_by() is ss2_instance


@pytest.mark.fsoe_phase2
def test_sout_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    process_image = ProcessImage.empty(handler.dictionary)
    handler.set_process_image(process_image)
    sout_instance = handler.get_function_instance(SOutFunction)
    sto_instance = handler.sto_function()
    ss1_instance = handler.ss1_function()
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(0)
    sto_instance.activate_sout.set(0)
    assert sout_instance.activated_by() is None
    sto_instance.activate_sout.set(1717567489)
    assert sout_instance.activated_by() is sto_instance
    sto_instance.activate_sout.set(0)
    assert sout_instance.activated_by() is None
    si_instance.map.set(4)
    assert sout_instance.activated_by() is si_instance
    si_instance.map.set(0)
    assert sout_instance.activated_by() is None
    ss1_instance.activate_sout.set(1717567489)
    process_image.insert_safety_function(ss1_instance)
    assert sout_instance.activated_by() is ss1_instance
    ss1_instance.activate_sout.set(0)
    assert sout_instance.activated_by() is None


@pytest.mark.fsoe_phase2
def test_ss1_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    process_image = ProcessImage.empty(handler.dictionary)
    handler.set_process_image(process_image)
    ss1_instance = handler.ss1_function()
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(2)
    assert ss1_instance.activated_by() is si_instance
    si_instance.map.set(0)
    assert ss1_instance.activated_by() is None
    activate_value = 0x66500101
    all_sfs = [
        *handler.safety_functions_by_type()[SLPFunction],
        *handler.safety_functions_by_type()[SSRFunction],
        *handler.safety_functions_by_type()[SLSFunction],
        *handler.safety_functions_by_type()[SLIFunction],
    ]
    for sf in all_sfs:
        process_image.insert_safety_function(sf)
        sf.error_reaction.set(activate_value)
        assert ss1_instance.activated_by() is sf
        sf.error_reaction.set(0)
        assert ss1_instance.activated_by() is None
