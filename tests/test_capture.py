import time
import pytest

from ingeniamotion.enums import OperationMode, MonitoringSoCType


def test_create_poller(motion_controller):
    registers = [{
        "name": "CL_CUR_Q_SET_POINT",
        "axis": 1
    }]
    sampling_time = 0.05
    mc, alias = motion_controller
    mc.motion.set_current_quadrature(-0.2, servo=alias)
    poller = mc.capture.create_poller(registers, alias, sampling_time)
    mc.motion.set_current_quadrature(0, servo=alias)
    for i in range(5):
        time.sleep(1)
        mc.motion.set_current_quadrature(0.2 * (i + 1), servo=alias)
    timestamp, test_data, _ = poller.data
    first_zero = None
    for index, ts in enumerate(timestamp):
        value = test_data[0][index]
        if first_zero is None and abs(value) < 0.00001:
            first_zero = ts
        if first_zero is None:
            continue
        tared_ts = ts-first_zero
        if pytest.approx(round(tared_ts), abs=sampling_time) == tared_ts:
            continue  # Values near on changes are not check
        assert pytest.approx(tared_ts // 1 * 0.2) == value


def test_create_monitoring_no_trigger(motion_controller):
    registers = [{
        "name": "CL_POS_REF_VALUE",
        "axis": 1
    }]
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.VELOCITY, alias)
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 20
    samples = 4000
    freq = max_frequency/divider
    total_time = samples/freq
    monitoring = mc.capture.create_monitoring(registers, divider,
                                              total_time, servo=alias)
    mc.motion.move_to_position(0, alias)
    mc.motion.motor_enable(alias)
    monitoring.enable_monitoring()
    init = time.time()
    for i in range(3):
        while init + (i+1)*total_time/4 > time.time():
            pass
        mc.motion.move_to_position(1000*(i+1), alias)
    data = monitoring.read_monitoring_data()
    assert samples == len(data[0])
    for index, value in enumerate(data[0]):
        subindex = index % 1000
        theo_value = index//1000 * 1000
        if 100 < subindex:  # Ignore first 100 samples for each value change
            assert value == theo_value


@pytest.mark.develop
@pytest.mark.parametrize("trigger_mode, values_list", [
    #(MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE, [0, 1000, 2000, 3000]),
    (MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE, [3000, 2000, 1000, 0]),
])
def test_create_monitoring_edge_trigger(motion_controller, trigger_mode, values_list):
    register = {
        "name": "CL_POS_REF_VALUE",
        "axis": 1
    }
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.VELOCITY, alias)
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 20
    samples = 4000
    freq = max_frequency/divider
    total_time = samples/freq
    monitoring = mc.capture.create_monitoring(
        [register], divider, total_time,
        trigger_delay=0,
        trigger_mode=trigger_mode,
        trigger_signal=register,
        trigger_value=1500,
        servo=alias
    )
    mc.motion.move_to_position(values_list[0], alias)
    mc.motion.motor_enable(alias)
    monitoring.enable_monitoring()
    time.sleep(1)
    init = time.time()
    for i in range(3):
        while init + (i+1)*total_time/4 > time.time():
            pass
        mc.motion.move_to_position(values_list[i+1], alias)
    data = monitoring.read_monitoring_data()
    assert samples == len(data[0])
    assert data[0][2000] == values_list[2]
    assert data[0][1999] == values_list[1]
    for index, value in enumerate(data[0]):
        subindex = index % 1000
        theo_value = values_list[index//1000]
        print(index, value)
        if 10 < subindex < 990:  # Ignore some samples near of value changes
            assert value == theo_value


def test_create_disturbance(motion_controller):
    assert False
