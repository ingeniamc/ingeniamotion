import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import PDUMaps
    from ingeniamotion.fsoe_master.safety_functions import (
        SLIFunction,
        SLPFunction,
        SLSFunction,
        SOSFunction,
        SOutFunction,
        SS2Function,
        SSRFunction,
    )
    from tests.test_fsoe_master import MockHandler


@pytest.mark.fsoe_phase2
def test_ss2_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    maps = PDUMaps.empty(handler.dictionary)
    ss2_instance = handler.get_function_instance(SS2Function)
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(3)
    assert ss2_instance.activated_by(handler, maps) is si_instance
    si_instance.map.set(0)
    assert ss2_instance.activated_by(handler, maps) is None
    for slp_func in handler.get_all_function_instances(SLPFunction):
        maps.insert_safety_function(slp_func)
        slp_func.error_reaction.set(0x66700101)
        assert ss2_instance.activated_by(handler, maps) is slp_func
        slp_func.error_reaction.set(0)
        assert ss2_instance.activated_by(handler, maps) is None


@pytest.mark.fsoe_phase2
def test_sos_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    maps = PDUMaps.empty(handler.dictionary)
    sos_instance = handler.get_function_instance(SOSFunction)
    ss2_instance = handler.get_function_instance(SS2Function)
    assert sos_instance.activated_by(handler, maps) is None
    maps.insert_safety_function(ss2_instance)
    assert sos_instance.activated_by(handler, maps) is ss2_instance


@pytest.mark.fsoe_phase2
def test_sout_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    maps = PDUMaps.empty(handler.dictionary)
    sout_instance = handler.get_function_instance(SOutFunction)
    sto_instance = handler.sto_function()
    ss1_instance = handler.ss1_function()
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(0)
    sto_instance.activate_sout.set(0)
    assert sout_instance.activated_by(handler, maps) is None
    sto_instance.activate_sout.set(1717567489)
    assert sout_instance.activated_by(handler, maps) is sto_instance
    sto_instance.activate_sout.set(0)
    assert sout_instance.activated_by(handler, maps) is None
    si_instance.map.set(4)
    assert sout_instance.activated_by(handler, maps) is si_instance
    si_instance.map.set(0)
    assert sout_instance.activated_by(handler, maps) is None
    ss1_instance.activate_sout.set(1717567489)
    maps.insert_safety_function(ss1_instance)
    assert sout_instance.activated_by(handler, maps) is ss1_instance
    ss1_instance.activate_sout.set(0)
    assert sout_instance.activated_by(handler, maps) is None


@pytest.mark.fsoe_phase2
def test_ss1_activated_by():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    maps = PDUMaps.empty(handler.dictionary)
    ss1_instance = handler.ss1_function()
    si_instance = handler.safe_inputs_function()
    si_instance.map.set(2)
    assert ss1_instance.activated_by(handler, maps) is si_instance
    si_instance.map.set(0)
    assert ss1_instance.activated_by(handler, maps) is None
    activate_value = 0x66500101
    all_sfs = [
        *handler.get_all_function_instances(SLPFunction),
        *handler.get_all_function_instances(SSRFunction),
        *handler.get_all_function_instances(SLSFunction),
        *handler.get_all_function_instances(SLIFunction),
    ]
    for sf in all_sfs:
        maps.insert_safety_function(sf)
        sf.error_reaction.set(activate_value)
        assert ss1_instance.activated_by(handler, maps) is sf
        sf.error_reaction.set(0)
        assert ss1_instance.activated_by(handler, maps) is None
