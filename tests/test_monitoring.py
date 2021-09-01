import time

import pytest

from ingeniamotion.monitoring import Monitoring, IMMonitoringError
from ingeniamotion.enums import MonitoringSoCType

MONITOR_START_CONDITION_TYPE_REGISTER = "MON_CFG_SOC_TYPE"


@pytest.fixture
def monitoring(motion_controller):
    mc, alias = motion_controller
    monitoring = Monitoring(mc, alias)
    return monitoring


@pytest.fixture
def mon_set_freq(monitoring):
    monitoring.set_frequency(10)


@pytest.fixture
def mon_map_registers(monitoring):
    monitoring.map_registers([{"axis": 1, "name": "CL_POS_FBK_VALUE"}])


@pytest.mark.smoke
@pytest.mark.parametrize("trigger_type", [
    MonitoringSoCType.TRIGGER_EVENT_NONE,
    MonitoringSoCType.TRIGGER_EVENT_FORCED,
    MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE,
    MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE,
])
def test_get_trigger_type(motion_controller, monitoring, trigger_type):
    mc, alias = motion_controller
    mc.communication.set_register(
        MONITOR_START_CONDITION_TYPE_REGISTER, trigger_type, servo=alias, axis=0)
    test_trigger = monitoring.get_trigger_type()
    assert test_trigger == trigger_type


@pytest.mark.smoke
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
@pytest.mark.parametrize("block, timeout, sample_t, wait, result", [
    (False, 5, 2, 2, True),
    (True, 5, 2, 0, True),
    (False, 5, 2, 0, False),
    (True, 1, 3, 0, False),
])
def test_raise_forced_trigger(motion_controller, monitoring, block,
                              timeout, sample_t, wait, result):
    mc, alias = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(wait)
    test_output = monitoring.raise_forced_trigger(blocking=block, timeout=timeout)
    assert test_output == result


@pytest.mark.smoke
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_raise_forced_trigger_fail(motion_controller, monitoring):
    mc, alias = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_NONE)
    monitoring.configure_sample_time(2, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    with pytest.raises(IMMonitoringError):
        monitoring.raise_forced_trigger()


@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
@pytest.mark.parametrize("timeout, sample_t, result", [
    (5, 2, True),
    (1, 3, False),
])
def test_read_monitoring_data_forced_trigger(motion_controller, monitoring,
                                             timeout, sample_t, result):
    mc, alias = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    test_output = monitoring.read_monitoring_data_forced_trigger(timeout)
    if result:
        assert len(test_output[0]) == monitoring.samples_number
    else:
        assert len(test_output[0]) == 0
