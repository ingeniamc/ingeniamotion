import time
from functools import partial
from threading import Thread

import pytest

from ingeniamotion.enums import MonitoringSoCConfig, MonitoringSoCType
from ingeniamotion.exceptions import IMMonitoringError

MONITOR_START_CONDITION_TYPE_REGISTER = "MON_CFG_SOC_TYPE"


class ThreadWithReturnValue(Thread):
    def __init__(self, *init_args, **init_kwargs):
        Thread.__init__(self, *init_args, **init_kwargs)
        self._return = None

    def run(self):
        self._return = self._target(*self._args, **self._kwargs)

    def join(self):
        Thread.join(self)
        return self._return


@pytest.fixture
def monitoring(skip_if_monitoring_not_available, motion_controller, alias):  # noqa: ARG001
    mc = motion_controller
    return mc.capture.create_empty_monitoring(alias)


@pytest.fixture
def mon_set_freq(skip_if_monitoring_not_available, monitoring):  # noqa: ARG001
    monitoring.set_frequency(10)


@pytest.fixture
def mon_map_registers(skip_if_monitoring_not_available, monitoring):  # noqa: ARG001
    monitoring.map_registers([{"axis": 1, "name": "CL_POS_FBK_VALUE"}])


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "trigger_type",
    [
        MonitoringSoCType.TRIGGER_EVENT_AUTO,
        MonitoringSoCType.TRIGGER_EVENT_FORCED,
        MonitoringSoCType.TRIGGER_EVENT_EDGE,
        4,  # Invalid value
    ],
)
def test_get_trigger_type(motion_controller, alias, monitoring, trigger_type):
    mc = motion_controller
    mc.communication.set_register(
        MONITOR_START_CONDITION_TYPE_REGISTER, trigger_type, servo=alias, axis=0
    )
    test_trigger = monitoring.get_trigger_type()
    assert test_trigger == trigger_type


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
@pytest.mark.parametrize(
    "block, timeout, sample_t, wait, result",
    [
        (False, 5, 0.8, 2, True),
        (True, 6, 0.8, 0, True),
        (False, 5, 0.8, 0, False),
        (True, 0.1, 0.8, 0, False),
    ],
)
def test_raise_forced_trigger(
    motion_controller,
    alias,
    monitoring,
    block,
    timeout,
    sample_t,
    wait,
    result,
):
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(wait)
    test_output = monitoring.raise_forced_trigger(blocking=block, timeout=timeout)
    assert test_output == result
    time.sleep(1)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_raise_forced_trigger_fail(motion_controller, alias, monitoring):
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_AUTO)
    monitoring.configure_sample_time(0.8, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    with pytest.raises(IMMonitoringError):
        monitoring.raise_forced_trigger()


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
@pytest.mark.parametrize(
    "timeout, sample_t, result",
    [
        (5, 0.8, True),
        (0.1, 0.8, False),
    ],
)
def test_read_monitoring_data_forced_trigger(
    motion_controller, alias, monitoring, timeout, sample_t, result
):
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    test_output = monitoring.read_monitoring_data_forced_trigger(timeout)
    if result:
        assert len(test_output[0]) == monitoring.samples_number
    else:
        assert len(test_output[0]) == 0


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("prescaler", list(range(2, 11, 2)))
def test_set_monitoring_frequency(motion_controller, alias, monitoring, prescaler):
    mc = motion_controller
    monitoring.set_frequency(prescaler)
    value = mc.communication.get_register(
        monitoring.MONITORING_FREQUENCY_DIVIDER_REGISTER, servo=alias, axis=0
    )
    assert value == prescaler


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_set_monitoring_frequency_exception(monitoring):
    prescaler = 0.5
    with pytest.raises(ValueError):
        monitoring.set_frequency(prescaler)


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_size_exception(monitoring):
    registers = [{"axis": 1, "name": "CL_POS_FBK_VALUE"}]
    monitoring.samples_number = monitoring.max_sample_number
    with pytest.raises(IMMonitoringError):
        monitoring.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_fail(monitoring):
    registers = []
    with pytest.raises(IMMonitoringError):
        monitoring.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_wrong_cyclic(monitoring):
    registers = [{"axis": 1, "name": "DRV_STATE_CONTROL"}]
    with pytest.raises(IMMonitoringError):
        monitoring.map_registers(registers)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.parametrize(
    "trigger_type, edge_condition, trigger_signal, trigger_value",
    [
        (MonitoringSoCType.TRIGGER_EVENT_AUTO, None, None, None),
        (MonitoringSoCType.TRIGGER_EVENT_FORCED, None, None, None),
        (
            MonitoringSoCType.TRIGGER_EVENT_EDGE,
            MonitoringSoCConfig.TRIGGER_CONFIG_RISING,
            {"axis": 1, "name": "CL_POS_FBK_VALUE"},
            0.5,
        ),
    ],
)
def test_monitoring_set_trigger(
    motion_controller,
    alias,
    monitoring,
    trigger_type,
    edge_condition,
    trigger_signal,
    trigger_value,
):
    mc = motion_controller
    monitoring.set_trigger(trigger_type, edge_condition, trigger_signal, trigger_value)
    value = mc.communication.get_register(
        MONITOR_START_CONDITION_TYPE_REGISTER, servo=alias, axis=0
    )
    assert value == trigger_type


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.parametrize(
    "trigger_type, edge_condition, trigger_signal, trigger_value",
    [
        (MonitoringSoCType.TRIGGER_EVENT_EDGE, None, {"axis": 1, "name": "CL_POS_FBK_VALUE"}, 0.5),
        (
            MonitoringSoCType.TRIGGER_EVENT_EDGE,
            MonitoringSoCConfig.TRIGGER_CONFIG_RISING,
            None,
            0.5,
        ),
        (
            MonitoringSoCType.TRIGGER_EVENT_EDGE,
            MonitoringSoCConfig.TRIGGER_CONFIG_RISING,
            {"axis": 1, "name": "CL_POS_FBK_VALUE"},
            None,
        ),
    ],
)
def test_monitoring_set_trigger_exceptions(
    monitoring, trigger_type, edge_condition, trigger_signal, trigger_value
):
    with pytest.raises(TypeError):
        monitoring.set_trigger(trigger_type, edge_condition, trigger_signal, trigger_value)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_configure_number_samples(motion_controller, alias, monitoring):
    mc = motion_controller
    total_num_samples = 500
    trigger_delay_samples = 100
    monitoring.configure_number_samples(total_num_samples, trigger_delay_samples)
    value = mc.communication.get_register(
        monitoring.MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER, servo=alias, axis=0
    )
    assert value == total_num_samples
    value = mc.communication.get_register(
        monitoring.MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER, servo=alias, axis=0
    )
    assert value == trigger_delay_samples


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("total_num_samples, trigger_delay_samples", [(500, 510), (510, -500)])
def test_configure_number_samples_exceptions(monitoring, total_num_samples, trigger_delay_samples):
    with pytest.raises(ValueError):
        monitoring.configure_number_samples(total_num_samples, trigger_delay_samples)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_configure_sample_time(motion_controller, alias, monitoring):
    mc = motion_controller
    total_time = 5
    sampling_freq = 1e4
    monitoring.sampling_freq = sampling_freq
    trigger_delay = total_time // 2
    total_num_samples = int(sampling_freq * total_time)
    trigger_delay_samples = int(((total_time / 2) - trigger_delay) * sampling_freq)
    monitoring.configure_sample_time(total_time, trigger_delay)
    value = mc.communication.get_register(
        monitoring.MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER, servo=alias, axis=0
    )
    assert value == total_num_samples
    value = mc.communication.get_register(
        monitoring.MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER, servo=alias, axis=0
    )
    assert value == trigger_delay_samples


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("total_time, sign", [(5, 1), (5, -1)])
def test_configure_sample_time_exception(monitoring, total_time, sign):
    trigger_delay = sign * ((total_time // 2) + 1)
    with pytest.raises(ValueError):
        monitoring.configure_sample_time(total_time, trigger_delay)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("skip_if_monitoring_not_available")
def test_enable_monitoring_no_mapped_registers(motion_controller, alias):
    mc, alias, _ = motion_controller
    mc.capture.clean_monitoring(alias)
    with pytest.raises(IMMonitoringError) as exc:
        mc.capture.enable_monitoring(servo=alias)
    assert str(exc.value) == "There are no registers mapped for monitoring."


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
def test_read_monitoring_data_disabled(monitoring):
    monitoring.configure_sample_time(0.8, 0)
    with pytest.raises(IMMonitoringError) as exc:
        monitoring.read_monitoring_data()
    assert str(exc.value) == "Cannot read monitoring data. Monitoring is disabled."


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_read_monitoring_data_timeout(motion_controller, alias, monitoring):
    timeout = 2
    sample_t = 0.8
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    test_output = monitoring.read_monitoring_data(timeout)
    assert len(test_output[0]) == 0


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_read_monitoring_data_no_rearm(motion_controller, alias, monitoring):
    sample_t = 0.8
    timeout = 2
    block = True
    wait = 2
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(wait)
    trigger_raised = monitoring.raise_forced_trigger(block, timeout)
    assert trigger_raised
    test_output = monitoring.read_monitoring_data()
    assert len(test_output[0]) > 0
    trigger_raised = monitoring.raise_forced_trigger(block, timeout)
    assert not trigger_raised
    test_output = monitoring.read_monitoring_data()
    assert len(test_output[0]) == 0


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_rearm_monitoring(motion_controller, alias, monitoring):
    sample_t = 0.8
    timeout = 2
    block = True
    wait = 2
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(wait)
    for _ in range(3):
        trigger_raised = monitoring.raise_forced_trigger(block, timeout)
        assert trigger_raised
        test_output = monitoring.read_monitoring_data()
        assert len(test_output[0]) > 0
        monitoring.rearm_monitoring()
        time.sleep(wait // 2)


def run_read_monitoring_data_and_stop(monitoring, timeout):
    # Set the flag to true to check that the read_monitoring_data
    # clears it
    monitoring._read_process_finished = True
    read_monitoring_data_timeout = partial(monitoring.read_monitoring_data, timeout=timeout)
    test_thread = ThreadWithReturnValue(target=read_monitoring_data_timeout)
    test_thread.start()
    # Wait for read_monitoring_data to clear the flag, indicating that the thread has started
    while monitoring._read_process_finished:
        pass
    # Now the stop reading data set the flag again and the thread stop on the next cycle
    monitoring.stop_reading_data()
    return test_thread.join()


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("mon_set_freq")
@pytest.mark.usefixtures("mon_map_registers")
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_stop_reading_data(motion_controller, alias, monitoring):
    sample_t = 0.8
    timeout = 10
    mc = motion_controller
    monitoring.set_trigger(MonitoringSoCType.TRIGGER_EVENT_FORCED)
    monitoring.configure_sample_time(sample_t, 0)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    init_time = time.time()
    test_output = run_read_monitoring_data_and_stop(monitoring, timeout)
    assert len(test_output[0]) == 0
    assert (time.time() - init_time) < timeout


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.usefixtures("skip_if_monitoring_not_available")
def test_monitoring_max_sample_size(motion_controller, alias):
    mc = motion_controller
    target_register = mc.capture.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.monitoring_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_invalid_subnode(mocker, motion_controller, alias, monitoring):
    registers = [{"axis": "1", "name": "DRV_AXIS_NUMBER"}]
    mc = motion_controller
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    with pytest.raises(TypeError):
        monitoring.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_invalid_register(mocker, motion_controller, alias, monitoring):
    registers = [{"axis": 1, "name": 1}]
    mc = motion_controller
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    with pytest.raises(TypeError):
        monitoring.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_map_registers_invalid_number_mapped_registers(
    mocker, motion_controller, alias, monitoring
):
    registers = [{"axis": 1, "name": "CL_POS_FBK_VALUE"}]
    mc = motion_controller
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        monitoring.map_registers(registers)


@pytest.mark.parametrize(
    "trigger_delay, expected_exception",
    [
        (3, ValueError),
        (2.5, TypeError),
    ],
)
@pytest.mark.virtual
@pytest.mark.smoke
def test_configure_sample_time_exceptions(
    mocker, motion_controller, alias, monitoring, trigger_delay, expected_exception
):
    mc = motion_controller
    total_time = 5
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    with pytest.raises(expected_exception):
        monitoring.configure_sample_time(total_time, trigger_delay)


@pytest.mark.virtual
def test_get_trigger_type_exception(mocker, motion_controller, alias, monitoring):
    mc = motion_controller
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        monitoring.get_trigger_type()


@pytest.mark.skip("Check INGM-584")
def test_dummy():
    pass
