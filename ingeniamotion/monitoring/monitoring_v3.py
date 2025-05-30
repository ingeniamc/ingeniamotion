from typing import TYPE_CHECKING, Callable, Optional, Union

import ingenialogger
from ingenialink.enums.register import RegDtype
from typing_extensions import override

from ingeniamotion.enums import (
    MonitoringProcessStage,
    MonitoringSoCConfig,
    MonitoringSoCType,
    MonitoringVersion,
)
from ingeniamotion.metaclass import DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

from ingeniamotion.monitoring.base_monitoring import Monitoring, check_monitoring_disabled


class MonitoringV3(Monitoring):
    """Motoring V3 class."""

    MONITORING_REARM_REGISTER = "MON_REARM"
    MONITOR_START_CONDITION_CONFIG_REGISTER = "MON_CFG_EOC_TYPE"
    MONITORING_TRIGGER_THRESHOLD_REGISTER = "MON_CFG_RISING_CONDITION"

    def __init__(self, mc: "MotionController", servo: str = DEFAULT_SERVO) -> None:
        super().__init__(mc, servo)
        self._version = MonitoringVersion.MONITORING_V3
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))

    @check_monitoring_disabled
    @override
    def set_trigger(
        self,
        trigger_mode: MonitoringSoCType,
        edge_condition: Optional[MonitoringSoCConfig] = None,
        trigger_signal: Optional[dict[str, str]] = None,
        trigger_value: Union[int, float, None] = None,
    ) -> None:
        self.mc.communication.set_register(
            self.MONITOR_START_CONDITION_TYPE_REGISTER, trigger_mode, servo=self.servo, axis=0
        )
        if trigger_mode == MonitoringSoCType.TRIGGER_EVENT_EDGE:
            if trigger_signal is None or trigger_value is None:
                raise TypeError("trigger_signal or trigger_value are None")
            if edge_condition is None:
                raise TypeError("Edge condition is not selected")
            index_reg, level_edge = self._get_reg_index_and_edge_condition_value(
                trigger_signal, trigger_value
            )
            self.__rising_or_falling_edge_trigger(edge_condition, index_reg, level_edge)

    def __rising_or_falling_edge_trigger(
        self, edge_condition: MonitoringSoCConfig, index_reg: int, level_edge: int
    ) -> None:
        self.mc.communication.set_register(
            self.MONITOR_START_CONDITION_CONFIG_REGISTER, edge_condition, servo=self.servo, axis=0
        )
        self.mc.communication.set_register(
            self.MONITORING_TRIGGER_THRESHOLD_REGISTER, level_edge, servo=self.servo, axis=0
        )
        self.mc.communication.set_register(
            self.MONITORING_INDEX_CHECKER_REGISTER, index_reg, servo=self.servo, axis=0
        )

    @check_monitoring_disabled
    @override
    def configure_number_samples(self, total_num_samples: int, trigger_delay_samples: int) -> None:
        if trigger_delay_samples > total_num_samples:
            raise ValueError("trigger_delay_samples should be less than total_num_samples")
        if trigger_delay_samples < 0:
            raise ValueError("trigger_delay_samples should be a positive number")
        self._check_buffer_size_is_enough(
            total_num_samples, trigger_delay_samples, self.mapped_registers
        )

        self.mc.communication.set_register(
            self.MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER,
            trigger_delay_samples,
            servo=self.servo,
            axis=0,
        )
        self.mc.communication.set_register(
            self.MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER,
            total_num_samples,
            servo=self.servo,
            axis=0,
        )
        self.samples_number = total_num_samples
        self.trigger_delay_samples = trigger_delay_samples

    @override
    def _check_monitoring_is_ready(self) -> tuple[bool, Optional[str]]:
        is_enabled = self.mc.capture.is_monitoring_enabled(self.servo)
        result_text = None
        monitoring_stage = self.mc.capture.get_monitoring_process_stage(self.servo, self._version)
        is_ready = is_enabled and monitoring_stage != MonitoringProcessStage.INIT_STAGE
        if not is_ready:
            text_is_enabled = "enabled" if is_enabled else "disabled"
            result_text = (
                "Can't read monitoring data because monitoring is not ready."
                f" Monitoring stage is {monitoring_stage.name}. Monitoring is {text_is_enabled}."
            )
        return is_ready, result_text

    @override
    def read_monitoring_data(
        self,
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[MonitoringProcessStage, float], None]] = None,
    ) -> list[list[Union[int, float]]]:
        drive = self.mc.servos[self.servo]
        data_array = super().read_monitoring_data(
            timeout=timeout, progress_callback=progress_callback
        )
        drive.monitoring_remove_data()
        return data_array

    @override
    def _check_data_is_ready(self) -> bool:
        monit_nmb_blocks = self.mc.communication.get_register(
            self.MONITORING_ACTUAL_NUMBER_SAMPLES_REGISTER, servo=self.servo, axis=0
        )
        if not isinstance(monit_nmb_blocks, int):
            raise TypeError("Actual number of monitoring samples value has to be an integer")
        data_is_ready = monit_nmb_blocks > 0
        data_is_ready &= self.mc.capture.is_frame_available(self.servo, version=self._version)
        return data_is_ready

    @override
    def rearm_monitoring(self) -> None:
        self.mc.communication.set_register(
            self.MONITORING_REARM_REGISTER, 1, servo=self.servo, axis=0
        )

    @override
    def _check_buffer_size_is_enough(
        self,
        total_samples: int,
        _: int,
        registers: list[dict[str, Union[int, str, RegDtype]]],
    ) -> None:
        n_sample = total_samples
        max_size = self.max_sample_number
        self._check_samples_and_max_size(n_sample, max_size, registers)
