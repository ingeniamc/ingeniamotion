import time
import pytest

from ingeniamotion.exceptions import IMStatusWordError
from ingeniamotion.enums import OperationMode, MonitoringSoCType, MonitoringSoCConfig


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
    poller.stop()
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


@pytest.mark.soem
@pytest.mark.eoe
def test_create_monitoring_no_trigger(motion_controller,
                                      disable_monitoring_disturbance):
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
    mc.capture.enable_monitoring_disturbance(servo=alias)
    init = time.time()
    quarter_total_time = total_time/4
    for i in range(1, 4):
        while init + i*quarter_total_time > time.time():
            pass
        mc.motion.move_to_position(1000*i, alias)
    data = monitoring.read_monitoring_data()
    assert samples == len(data[0])
    for index, value in enumerate(data[0]):
        subindex = index % 1000
        theo_value = index//1000 * 1000
        if subindex > 100:  # Ignore first 100 samples for each value change
            assert value == theo_value


@pytest.mark.soem
@pytest.mark.eoe
@pytest.mark.parametrize("trigger_mode, trigger_config, values_list", [
    (MonitoringSoCType.TRIGGER_EVENT_EDGE,
     MonitoringSoCConfig.TRIGGER_CONFIG_RISING,
     [0, 1000, 2000, 3000]),
    (MonitoringSoCType.TRIGGER_EVENT_EDGE,
     MonitoringSoCConfig.TRIGGER_CONFIG_FALLING,
     [3000, 2000, 1000, 0]),
])
def test_create_monitoring_edge_trigger(motion_controller, trigger_mode, trigger_config,
                                        values_list, disable_monitoring_disturbance):
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
        trigger_config=trigger_config,
        trigger_signal=register,
        trigger_value=1500,
        servo=alias
    )
    mc.motion.move_to_position(values_list[0], alias)
    mc.motion.motor_enable(alias)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(1)
    init = time.time()
    quarter_total_time = total_time/4
    for i in range(1, 4):
        while init + i*quarter_total_time > time.time():
            pass
        mc.motion.move_to_position(values_list[i], alias)
    data = monitoring.read_monitoring_data()
    assert samples == len(data[0])
    assert data[0][2000] == values_list[2]
    assert data[0][1999] == values_list[1]
    for index, value in enumerate(data[0]):
        subindex = index % 1000
        theo_value = values_list[index//1000]
        if 10 < subindex < 990:  # Ignore some samples near of value changes
            assert value == theo_value


@pytest.mark.soem
@pytest.mark.eoe
def test_create_disturbance(motion_controller,
                            disable_monitoring_disturbance):
    mc, alias = motion_controller
    target_register = "CL_POS_SET_POINT_VALUE"
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 20
    samples = 4000
    freq = max_frequency/divider
    period = 1/freq
    data = []
    data_subrange = 1000
    for i in range(samples//data_subrange):
        data += [i * data_subrange] * 1000
    dist = mc.capture.create_disturbance(target_register, data, divider, servo=alias)
    init_time = time.time()
    mc.capture.enable_monitoring_disturbance(servo=alias)
    while init_time + samples*period*2 > time.time():
        time_now = time.time() - init_time
        current_value = mc.communication.get_register(target_register, alias)
        sample_num = int((time_now//period) % samples)
        if sample_num % data_subrange < 10:
            continue
        assert current_value == data[sample_num]


@pytest.mark.soem
@pytest.mark.eoe
@pytest.mark.smoke
def test_mcb_synchronization(mocker, motion_controller):
    mc, alias = motion_controller
    enable_mon = mocker.patch(
        'ingeniamotion.capture.Capture.enable_monitoring')
    disable_mon = mocker.patch(
        'ingeniamotion.capture.Capture.disable_monitoring')
    mc.capture.mcb_synchronization(servo=alias)
    enable_mon.assert_called_once_with(servo=alias)
    disable_mon.assert_called_once_with(servo=alias)


@pytest.mark.soem
@pytest.mark.eoe
@pytest.mark.smoke
def test_mcb_synchronization_fail(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    with pytest.raises(IMStatusWordError):
        mc.capture.mcb_synchronization(servo=alias)


@pytest.mark.smoke
def test_disturbance_max_sample_size(motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.disturbance_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


@pytest.mark.smoke
def test_monitoring_max_sample_size(motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.monitoring_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value
