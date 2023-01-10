import time

import pytest
import numpy as np

from ingeniamotion.exceptions import IMStatusWordError
from ingeniamotion.enums import OperationMode, MonitoringSoCType, MonitoringSoCConfig


def __compare_signals(expected_signal, received_signal, length_tol=None, fft_tol=0.05):
    if length_tol is not None:
        assert pytest.approx(len(received_signal), length_tol) == len(expected_signal)

        if len(received_signal) < len():
            expected_signal = expected_signal[: len(received_signal)]

    assert len(received_signal) == len(expected_signal)

    fft_received = np.abs(np.fft.fft(received_signal))
    fft_expected = np.abs(np.fft.fft(expected_signal))

    # Normalization
    fft_received = fft_received / np.amax(fft_received)
    fft_expected = fft_expected / np.amax(fft_expected)

    assert np.allclose(fft_received, fft_expected, rtol=0, atol=fft_tol)


def test_create_poller(motion_controller):
    registers = [{"name": "CL_CUR_Q_SET_POINT", "axis": 1}]
    sampling_time = 0.0625
    mc, alias = motion_controller
    mc.motion.set_current_quadrature(-0.2, servo=alias)
    poller = mc.capture.create_poller(registers, alias, sampling_time, buffer_size=128)
    mc.motion.set_current_quadrature(0, servo=alias)
    period = 1
    expected_signal = [0] * int(period / sampling_time)
    for i in range(7):
        time.sleep(1)
        mc.motion.set_current_quadrature(0.2 * (i + 1), servo=alias)
        expected_signal.extend([0.2 * (i + 1)] * int(period / sampling_time))
    time.sleep(3 * period)
    timestamp, test_data, _ = poller.data
    poller.stop()
    assert np.allclose(np.diff(timestamp), sampling_time, rtol=0.5, atol=0)

    received_signal = test_data[0]
    __compare_signals(expected_signal, received_signal)


def test_create_monitoring_no_trigger(
    skip_if_monitoring_not_available, motion_controller, disable_monitoring_disturbance
):
    registers = [{"name": "CL_POS_REF_VALUE", "axis": 1}]
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.VELOCITY, alias)
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 40
    samples = 2000
    quarter_num_samples = samples // 4
    freq = max_frequency / divider
    total_time = samples / freq
    quarter_total_time = total_time / 4
    mc.motion.move_to_position(0, alias)
    mc.motion.motor_enable(alias)
    monitoring = mc.capture.create_monitoring(registers, divider, total_time, servo=alias)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    # Dummy reading
    monitoring.read_monitoring_data()
    monitoring.rearm_monitoring()
    init = time.time()
    expected_signal = [0] * quarter_num_samples
    for i in range(1, 4):
        while init + i * quarter_total_time > time.time():
            pass
        mc.motion.move_to_position(quarter_num_samples * i, alias)
        expected_signal.extend([i * quarter_num_samples] * quarter_num_samples)
    data = monitoring.read_monitoring_data()
    __compare_signals(expected_signal, data[0])


@pytest.mark.parametrize(
    "trigger_mode, trigger_config, values_list",
    [
        (
            MonitoringSoCType.TRIGGER_EVENT_EDGE,
            MonitoringSoCConfig.TRIGGER_CONFIG_RISING,
            [0, 0.25, 0.5, 0.75],
        ),
        (
            MonitoringSoCType.TRIGGER_EVENT_EDGE,
            MonitoringSoCConfig.TRIGGER_CONFIG_FALLING,
            [0.75, 0.5, 0.25, 0],
        ),
    ],
)
def test_create_monitoring_edge_trigger(
    skip_if_monitoring_not_available,
    motion_controller,
    trigger_mode,
    trigger_config,
    values_list,
    disable_monitoring_disturbance,
):
    register = {"name": "CL_POS_REF_VALUE", "axis": 1}
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.VELOCITY, alias)
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 40
    samples = 2000
    quarter_num_samples = samples // 4
    trigger_value = ((values_list[1] + values_list[2]) / 2) * samples
    freq = max_frequency / divider
    total_time = samples / freq
    monitoring = mc.capture.create_monitoring(
        [register],
        divider,
        total_time,
        trigger_delay=0,
        trigger_mode=trigger_mode,
        trigger_config=trigger_config,
        trigger_signal=register,
        trigger_value=trigger_value,
        servo=alias,
    )
    mc.motion.move_to_position(int(values_list[0] * samples), alias)
    mc.motion.motor_enable(alias)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(1)
    init = time.time()
    quarter_total_time = total_time / 4
    expected_signal = np.zeros(samples)
    expected_signal[:quarter_num_samples] = int(values_list[0] * samples)
    for i in range(1, 4):
        while init + i * quarter_total_time > time.time():
            pass
        value = int(values_list[i] * samples)
        mc.motion.move_to_position(value, alias)
        expected_signal[i * quarter_num_samples : (i + 1) * quarter_num_samples] = value

    data = monitoring.read_monitoring_data()
    __compare_signals(expected_signal, data[0])


@pytest.mark.parametrize("trigger_delay_rate", [-1 / 4, 1 / 4])
def test_create_monitoring_trigger_delay(
    skip_if_monitoring_not_available,
    motion_controller,
    trigger_delay_rate,
):
    trigger_mode = MonitoringSoCType.TRIGGER_EVENT_EDGE
    trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING
    values_list = [0, 0.25, 0.5, 0.75]
    register = {"name": "CL_POS_REF_VALUE", "axis": 1}
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.VELOCITY, alias)
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 40
    samples = 2000
    quarter_num_samples = samples // 4
    trigger_value = ((values_list[1] + values_list[2]) / 2) * samples
    freq = max_frequency / divider
    total_time = samples / freq
    trigger_delay = total_time * trigger_delay_rate
    trigger_delay_samples = int(samples * trigger_delay_rate) + 1
    monitoring = mc.capture.create_monitoring(
        [register],
        divider,
        total_time,
        trigger_delay=trigger_delay,
        trigger_mode=trigger_mode,
        trigger_config=trigger_config,
        trigger_signal=register,
        trigger_value=trigger_value,
        servo=alias,
    )
    mc.motion.move_to_position(int(values_list[0] * samples), alias)
    mc.motion.motor_enable(alias)
    mc.capture.enable_monitoring_disturbance(servo=alias)
    time.sleep(1)
    init = time.time()
    quarter_total_time = total_time / 4
    expected_signal = np.zeros(samples)
    expected_signal[:quarter_num_samples] = int(values_list[0] * samples)
    for i in range(1, 4):
        while init + i * quarter_total_time > time.time():
            pass
        value = int(values_list[i] * samples)
        mc.motion.move_to_position(value, alias)
        expected_signal[i * quarter_num_samples : (i + 1) * quarter_num_samples] = value

    expected_signal = np.roll(expected_signal, -trigger_delay_samples)
    if trigger_delay_samples < 0:
        expected_signal[:-trigger_delay_samples] = 0
    else:
        expected_signal[-trigger_delay_samples:] = value
    data = monitoring.read_monitoring_data()
    __compare_signals(expected_signal, data[0])


def test_create_disturbance(
    skip_if_monitoring_not_available, motion_controller, disable_monitoring_disturbance
):
    mc, alias = motion_controller
    target_register = "CL_POS_SET_POINT_VALUE"
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 40
    samples = 2000
    freq = max_frequency / divider
    period = 1 / freq
    data = []
    data_subrange = samples // 4
    for i in range(samples // data_subrange):
        data += [i * data_subrange] * data_subrange
    dist = mc.capture.create_disturbance(target_register, data, divider, servo=alias)
    init_time = time.time()
    mc.capture.enable_monitoring_disturbance(servo=alias)
    read_data = []
    dist_timestamp = np.arange(samples) * period
    read_timestamp = []
    while time.time() < init_time + samples * period:
        read_timestamp.append(time.time() - init_time)
        current_value = mc.communication.get_register(target_register, alias)
        read_data.append(current_value)
        time.sleep(period)

    read_data = np.interp(dist_timestamp, read_timestamp, read_data)
    __compare_signals(data, read_data)


@pytest.mark.smoke
def test_mcb_synchronization(mocker, motion_controller):
    mc, alias = motion_controller
    enable_mon = mocker.patch("ingeniamotion.capture.Capture.enable_monitoring")
    disable_mon = mocker.patch("ingeniamotion.capture.Capture.disable_monitoring")
    mc.capture.mcb_synchronization(servo=alias)
    enable_mon.assert_called_once_with(servo=alias)
    disable_mon.assert_called_once_with(servo=alias)


@pytest.mark.smoke
def test_mcb_synchronization_fail(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    with pytest.raises(IMStatusWordError):
        mc.capture.mcb_synchronization(servo=alias)


@pytest.mark.smoke
def test_disturbance_max_sample_size(skip_if_monitoring_not_available, motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.disturbance_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


@pytest.mark.smoke
def test_monitoring_max_sample_size(skip_if_monitoring_not_available, motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.monitoring_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


def test_get_frequency(
    skip_if_monitoring_not_available, motion_controller, disable_monitoring_disturbance
):
    mc, alias = motion_controller
    registers = [{"name": "CL_POS_REF_VALUE", "axis": 1}]
    max_frequency = mc.configuration.get_position_and_velocity_loop_rate(alias)
    divider = 40
    samples = 2000
    freq = max_frequency / divider
    total_time = samples / freq
    monitoring = mc.capture.create_monitoring(registers, divider, total_time, servo=alias)
    assert mc.capture.get_frequency(servo=alias) == freq
    new_divider = 2
    monitoring.set_frequency(new_divider)
    assert mc.capture.get_frequency(servo=alias) == max_frequency / new_divider
