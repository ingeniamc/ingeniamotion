from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks


class DigitalHallTest(Feedbacks):
    HALLS_FILTER_CUTOFF_FREQUENCY = 10
    DIG_HALL_POLE_PAIRS_REGISTER = "FBK_DIGHALL_PAIRPOLES"

    BACKUP_REGISTERS_HALLS: List[str] = [
        "FBK_DIGHALL_POLARITY",
        "FBK_DIGHALL_PAIRPOLES",
        "ERROR_DIGHALL_SEQ_OPTION",
    ]

    FEEDBACK_POLARITY_REGISTER = "FBK_DIGHALL_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.HALLS

    def __init__(self, mc: "MotionController", servo: str, axis: int) -> None:
        super().__init__(mc, servo, axis)
        self.backup_registers_names.extend(self.BACKUP_REGISTERS_HALLS)

    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        self.halls_extra_settings()
        super().feedback_setting()

    @BaseTest.stoppable
    def halls_extra_settings(self) -> None:
        if self.pair_poles is None:
            raise TypeError("Pair poles has to be an integer")
        self.mc.communication.set_register(
            self.DIG_HALL_POLE_PAIRS_REGISTER, self.pair_poles, servo=self.servo, axis=self.axis
        )

        # Read velocity feedback
        velocity_feedback = self.mc.configuration.get_velocity_feedback(
            servo=self.servo, axis=self.axis
        )
        # Read velocity feedback, if is HALLS set filter to 10 Hz
        # TODO: set filter depending on motors rated velocity by the
        #  following formula: f_halls = w_mechanical * pp * 6
        if velocity_feedback == SensorType.HALLS:
            filter_type_uid = self.VELOCITY_FEEDBACK_FILTER_1_TYPE_REGISTER
            filter_freq_uid = self.VELOCITY_FEEDBACK_FILTER_1_FREQUENCY_REGISTER
            self.suggested_registers[filter_type_uid] = self.LOW_PASS_FILTER
            self.suggested_registers[filter_freq_uid] = self.HALLS_FILTER_CUTOFF_FREQUENCY

            self.logger.info(
                "Setting a velocity low pass filter at 10 Hz as "
                "velocity feedback is set to Halls"
            )
            del self.backup_registers[self.axis][self.VELOCITY_FEEDBACK_FILTER_1_TYPE_REGISTER]
            del self.backup_registers[self.axis][self.VELOCITY_FEEDBACK_FILTER_1_FREQUENCY_REGISTER]

    @BaseTest.stoppable
    def suggest_polarity(self, pol: Feedbacks.Polarity) -> None:
        polarity_uid = self.FEEDBACK_POLARITY_REGISTER
        pair_poles_uid = self.DIG_HALL_POLE_PAIRS_REGISTER
        if self.pair_poles is None:
            raise TypeError("Pair poles has to be set before polarity suggestion.")
        self.suggested_registers[pair_poles_uid] = self.pair_poles
        self.suggested_registers[polarity_uid] = pol
