from typing import TYPE_CHECKING, Optional, Union
import ingenialogger

from ingeniamotion.metaclass import DEFAULT_SERVO
from ingeniamotion.exceptions import IMException, IMStatusWordError
from ingeniamotion.enums import MonitoringVersion, MonitoringSoCType, MonitoringSoCConfig

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

from ingeniamotion.monitoring.base_monitoring import Monitoring, check_monitoring_disabled


class MonitoringV1(Monitoring):
    EOC_TRIGGER_NUMBER_SAMPLES = 3

    TRIGGER_CYCLIC_RISING_EDGE = 2
    TRIGGER_CYCLIC_FALLING_EDGE = 4

    MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER = "MON_CFG_TRIGGER_REPETITIONS"
    MONITOR_END_CONDITION_TYPE_REGISTER = "MON_CFG_EOC_TYPE"

    EDGE_CONDITION_REGISTER = {
        MonitoringSoCConfig.TRIGGER_CONFIG_RISING: "MON_CFG_RISING_CONDITION",
        MonitoringSoCConfig.TRIGGER_CONFIG_FALLING: "MON_CFG_FALLING_CONDITION",
    }

    def __init__(self, mc: "MotionController", servo: str = DEFAULT_SERVO) -> None:
        super().__init__(mc, servo)
        self._version = mc.capture._check_version(servo)
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        try:
            self.mc.capture.mcb_synchronization(servo=servo)
        except IMStatusWordError:
            self.logger.warning(
                "MCB could not be synchronized. Motor is enabled.", drive=mc.servo_name(servo)
            )

    def __get_old_soc_type(self, edge_condition: MonitoringSoCConfig) -> int:
        if edge_condition == MonitoringSoCConfig.TRIGGER_CONFIG_RISING:
            return self.TRIGGER_CYCLIC_RISING_EDGE
        if edge_condition == MonitoringSoCConfig.TRIGGER_CONFIG_FALLING:
            return self.TRIGGER_CYCLIC_FALLING_EDGE
        raise NotImplementedError("Edge condition is not implementedfor this FW version")

    @check_monitoring_disabled
    def set_trigger(
        self,
        trigger_mode: Union[MonitoringSoCType, int],
        edge_condition: Optional[MonitoringSoCConfig] = None,
        trigger_signal: Optional[dict[str, str]] = None,
        trigger_value: Union[int, float, None] = None,
    ) -> None:
        self.rearm_monitoring()
        if trigger_mode == MonitoringSoCType.TRIGGER_EVENT_EDGE:
            if trigger_signal is None or trigger_value is None:
                raise TypeError("trigger_signal or trigger_value are None")
            if edge_condition is None:
                raise TypeError("Edge condition is not selected")
            trigger_mode = self.__get_old_soc_type(edge_condition)
            index_reg, level_edge = self._get_reg_index_and_edge_condition_value(
                trigger_signal, trigger_value
            )
            self.__rising_or_falling_edge_trigger(edge_condition, index_reg, level_edge)
        self.mc.communication.set_register(
            self.MONITOR_START_CONDITION_TYPE_REGISTER, trigger_mode, servo=self.servo, axis=0
        )

    def __rising_or_falling_edge_trigger(
        self, edge_condition: MonitoringSoCConfig, index_reg: int, level_edge: int
    ) -> None:
        self.mc.communication.set_register(
            self.MONITORING_INDEX_CHECKER_REGISTER, index_reg, servo=self.servo, axis=0
        )
        self.mc.communication.set_register(
            self.EDGE_CONDITION_REGISTER[edge_condition], level_edge, servo=self.servo, axis=0
        )

    @check_monitoring_disabled
    def configure_number_samples(self, total_num_samples: int, trigger_delay_samples: int) -> None:
        if trigger_delay_samples > total_num_samples:
            raise ValueError("trigger_delay_samples should be less than total_num_samples")
        if trigger_delay_samples < 0:
            raise ValueError("trigger_delay_samples should be a positive number")
        self._check_buffer_size_is_enough(
            total_num_samples, trigger_delay_samples, self.mapped_registers
        )
        if trigger_delay_samples == 0:
            trigger_delay_samples = 1
        if trigger_delay_samples == total_num_samples:
            trigger_delay_samples = total_num_samples - 1
        window_samples = total_num_samples - trigger_delay_samples
        self.mc.communication.set_register(
            self.MONITOR_END_CONDITION_TYPE_REGISTER,
            self.EOC_TRIGGER_NUMBER_SAMPLES,
            servo=self.servo,
            axis=0,
        )
        self.mc.communication.set_register(
            self.MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER,
            trigger_delay_samples,
            servo=self.servo,
            axis=0,
        )
        self.mc.communication.set_register(
            self.MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER, window_samples, servo=self.servo, axis=0
        )
        self.samples_number = total_num_samples
        self.trigger_delay_samples = trigger_delay_samples

    def _check_monitoring_is_ready(self) -> tuple[bool, Optional[str]]:
        is_enabled = self.mc.capture.is_monitoring_enabled(self.servo)
        result_text = None
        trigger_repetitions = self.mc.communication.get_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER, servo=self.servo, axis=0
        )
        is_ready = is_enabled and trigger_repetitions != 0
        if not is_ready:
            text_is_enabled = "enabled" if is_enabled else "disabled"
            result_text = (
                "Can't read monitoring data because monitoring is not ready."
                " MON_CFG_TRIGGER_REPETITIONS is {}. Monitoring is {}.".format(
                    trigger_repetitions, text_is_enabled
                )
            )
        return is_ready, result_text

    def _check_data_is_ready(self) -> bool:
        monit_nmb_blocks = self.mc.communication.get_register(
            self.MONITORING_ACTUAL_NUMBER_SAMPLES_REGISTER, servo=self.servo, axis=0
        )
        if not isinstance(monit_nmb_blocks, int):
            raise IMException("Actual number of monitoring samples value has to be an integer")
        data_is_ready = monit_nmb_blocks > 0
        if self._version == MonitoringVersion.MONITORING_V2:
            data_is_ready &= self.mc.capture.is_frame_available(self.servo, version=self._version)
        return data_is_ready

    def rearm_monitoring(self) -> None:
        self.mc.communication.set_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER, 1, servo=self.servo, axis=0
        )

    def _check_buffer_size_is_enough(
        self, total_samples: int, trigger_delay_samples: int, registers: list[dict[str, str]]
    ) -> None:
        n_sample = max(total_samples - trigger_delay_samples, trigger_delay_samples)
        max_size = self.max_sample_number // 2
        self._check_samples_and_max_size(n_sample, max_size, registers)
