import time

import pytest
import numpy as np

from ingeniamotion.exceptions import IMStatusWordError, IMMonitoringError
from ingeniamotion.enums import (
    OperationMode,
    MonitoringSoCType,
    MonitoringSoCConfig,
    MonitoringVersion,
    MonitoringProcessStage,
)


def __compare_signals(expected_signal, received_signal, fft_tol=0.05):
    fft_received = np.abs(np.fft.fft(received_signal))
    fft_expected = np.abs(np.fft.fft(expected_signal))

    # Normalization
    fft_received = fft_received / np.amax(fft_received)
    fft_expected = fft_expected / np.amax(fft_expected)

    return np.allclose(fft_received, fft_expected, rtol=0, atol=fft_tol)


def test_create_poller(motion_controller):
    registers = [{"name": "CL_CUR_Q_SET_POINT", "axis": 1}]
    sampling_time = 0.0625
    mc, alias = motion_controller
    mc.motion.set_current_quadrature(-0.2, servo=alias)
    poller = mc.capture.create_poller(registers, alias, sampling_time, buffer_size=128)
    mc.motion.set_current_quadrature(0, servo=alias)
    period = 1
    expected_signal = [0.0] * int(period / sampling_time)
    for i in range(7):
        time.sleep(1)
        mc.motion.set_current_quadrature(0.2 * (i + 1), servo=alias)
        expected_signal.extend([0.2 * (i + 1)] * int(period / sampling_time))
    time.sleep(3 * period)
    timestamp, test_data, _ = poller.data
    poller.stop()
    assert np.allclose(np.diff(timestamp), sampling_time, rtol=0.5, atol=0)

    received_signal = test_data[0]
    assert len(received_signal) == len(expected_signal)
    assert __compare_signals(expected_signal, received_signal)


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
    assert len(data[0]) == len(expected_signal)
    assert __compare_signals(expected_signal, data[0])


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
    assert len(data[0]) == len(expected_signal)
    assert __compare_signals(expected_signal, data[0])


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
    assert len(data[0]) == len(expected_signal)
    assert __compare_signals(expected_signal, data[0])


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
    assert len(data) == len(read_data)
    assert __compare_signals(data, read_data)


@pytest.mark.virtual
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


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_max_sample_size(skip_if_monitoring_not_available, motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.disturbance_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_monitoring_max_sample_size(skip_if_monitoring_not_available, motion_controller):
    mc, alias = motion_controller
    target_register = mc.capture.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER
    axis = 0
    max_sample_size = mc.capture.monitoring_max_sample_size(servo=alias)
    drive = mc.servos[alias]
    value = drive.read(target_register, subnode=axis)
    assert max_sample_size == value


@pytest.mark.smoke
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


@pytest.mark.parametrize(
    "name, axis",
    [("CL_CUR_Q_SET_POINT", "1"), (1, 1)],
)
@pytest.mark.virtual
def test_create_poller_exceptions(motion_controller, name, axis):
    sampling_time = 0.0625
    registers = [{"name": name, "axis": axis}]
    mc, alias = motion_controller
    with pytest.raises(TypeError):
        mc.capture.create_poller(registers, alias, sampling_time)


@pytest.mark.virtual
def test_create_empty_monitoring_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "_check_version", return_value=MonitoringVersion.MONITORING_V2)
    with pytest.raises(NotImplementedError):
        mc.capture.create_empty_monitoring(servo=alias)


@pytest.mark.virtual
def test_check_monitoring_version_v3(motion_controller):
    mc, alias = motion_controller
    version = mc.capture._check_version(servo=alias)
    assert version == MonitoringVersion.MONITORING_V3


@pytest.mark.virtual
def test_check_monitoring_version_v2(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "MONITORING_VERSION_REGISTER", return_value="NON_EXISTING_UID")
    version = mc.capture._check_version(servo=alias)
    assert version == MonitoringVersion.MONITORING_V2


@pytest.mark.virtual
def test_check_monitoring_version_v1(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "MONITORING_VERSION_REGISTER", return_value="NON_EXISTING_UID")
    mocker.patch.object(
        mc.capture, "MONITORING_CURRENT_NUMBER_BYTES_REGISTER", return_value="NON_EXISTING_UID"
    )
    version = mc.capture._check_version(servo=alias)
    assert version == MonitoringVersion.MONITORING_V1


@pytest.mark.virtual
def test_check_monitoring_version_not_available(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "MONITORING_VERSION_REGISTER", return_value="NON_EXISTING_UID")
    mocker.patch.object(
        mc.capture, "MONITORING_CURRENT_NUMBER_BYTES_REGISTER", return_value="NON_EXISTING_UID"
    )
    mocker.patch.object(mc.capture, "MONITORING_STATUS_REGISTER", return_value="NON_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        mc.capture._check_version(servo=alias)


@pytest.mark.virtual
def test_enable_monitoring_exception(mocker, motion_controller):
    mc, alias = motion_controller
    monitoring = mc.capture.create_empty_monitoring(alias)
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    monitoring.map_registers([{"axis": 1, "name": "CL_POS_FBK_VALUE"}])
    with pytest.raises(IMMonitoringError):
        mc.capture.enable_monitoring(servo=alias)


@pytest.mark.virtual
def test_enable_disturbance_exception(mocker, motion_controller):
    mc, alias = motion_controller
    monitoring = mc.capture.create_empty_monitoring(alias)
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    mocker.patch.object(mc.capture, "is_monitoring_enabled", return_value=False)
    monitoring.map_registers([{"axis": 1, "name": "CL_POS_FBK_VALUE"}])
    with pytest.raises(IMMonitoringError):
        mc.capture.enable_disturbance(servo=alias)


@pytest.mark.parametrize(
    "function",
    ["get_monitoring_disturbance_status", "get_monitoring_status", "get_disturbance_status"],
)
@pytest.mark.virtual
def test_get_monitoring_disturbance_status_exception(mocker, motion_controller, function):
    mc, alias = motion_controller
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        getattr(mc.capture, function)(servo=alias)


@pytest.mark.parametrize(
    "monitor_status, expected_stage",
    [
        (0x00, MonitoringProcessStage.INIT_STAGE),
        (0x02, MonitoringProcessStage.FILLING_DELAY_DATA),
        (0x04, MonitoringProcessStage.WAITING_FOR_TRIGGER),
        (0x06, MonitoringProcessStage.DATA_ACQUISITION),
        (0x08, MonitoringProcessStage.END_STAGE),
    ],
)
@pytest.mark.virtual
def test_get_monitoring_process_stage_v3(mocker, motion_controller, monitor_status, expected_stage):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "get_monitoring_status", return_value=monitor_status)
    assert mc.capture.get_monitoring_process_stage(servo=alias) == expected_stage


@pytest.mark.parametrize(
    "monitoring_status, expected_stage",
    [
        (0x00, MonitoringProcessStage.INIT_STAGE),
        (0x02, MonitoringProcessStage.FILLING_DELAY_DATA),
        (0x04, MonitoringProcessStage.WAITING_FOR_TRIGGER),
        (0x06, MonitoringProcessStage.DATA_ACQUISITION),
    ],
)
@pytest.mark.virtual
def test_get_monitoring_process_stage_v1_v2(
    mocker, motion_controller, monitoring_status, expected_stage
):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "get_monitoring_status", return_value=monitoring_status)
    assert (
        mc.capture.get_monitoring_process_stage(
            servo=alias, version=MonitoringVersion.MONITORING_V2
        )
        == expected_stage
    )


@pytest.mark.parametrize(
    "monitoring_status, monitoring_version",
    [
        (0x800, MonitoringVersion.MONITORING_V1),
        (0x800, MonitoringVersion.MONITORING_V2),
        (0x10, MonitoringVersion.MONITORING_V3),
    ],
)
@pytest.mark.virtual
def test_is_frame_available(mocker, motion_controller, monitoring_status, monitoring_version):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "get_monitoring_status", return_value=monitoring_status)
    assert mc.capture.is_frame_available(servo=alias, version=monitoring_version)


@pytest.mark.parametrize(
    "function",
    ["disturbance_max_sample_size", "monitoring_max_sample_size"],
)
@pytest.mark.virtual
def test_monitoring_disturbance_max_sample_size_exception(mocker, motion_controller, function):
    mc, alias = motion_controller
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        getattr(mc.capture, function)(servo=alias)


@pytest.mark.virtual
def test_get_frequency_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        mc.capture.get_frequency(servo=alias)
