import time
from enum import IntEnum
from typing import TYPE_CHECKING, Optional

import ingenialogger

from ingeniamotion.enums import (
    CommutationMode,
    OperationMode,
    PhasingMode,
    SensorCategory,
    SensorType,
    SeverityLevel,
)
from ingeniamotion.exceptions import IMRegisterNotExist
from ingeniamotion.wizard_tests.base_test import BaseTest, DictReportType, TestError

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class Phasing(BaseTest[DictReportType]):
    INTERNAL_GENERATOR_VALUE = 3
    INITIAL_ANGLE = 180.0
    INITIAL_ANGLE_HALLS = 240.0
    PHASING_CURRENT_PERCENTAGE = 0.4
    PHASING_CURRENT_PERCENTAGE_GEAR = 0.8
    PHASING_TIMEOUT_DEFAULT = 2000
    PHASING_ACCURACY_HALLS_DEFAULT = 60000
    PHASING_ACCURACY_DEFAULT = 3600

    MAX_CURRENT_REGISTER = "CL_CUR_REF_MAX"
    RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
    PHASING_ACCURACY_REGISTER = "COMMU_PHASING_ACCURACY"
    PHASING_TIMEOUT_REGISTER = "COMMU_PHASING_TIMEOUT"
    MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER = "COMMU_PHASING_MAX_CURRENT"
    COMMUTATION_ANGLE_OFFSET_REGISTER = "COMMU_ANGLE_OFFSET"

    BACKUP_REGISTERS = [
        "CL_POS_FBK_SENSOR",
        "DRV_OP_CMD",
        "CL_CUR_Q_SET_POINT",
        "CL_CUR_D_SET_POINT",
        "FBK_GEN_MODE",
        "FBK_GEN_FREQ",
        "FBK_GEN_GAIN",
        "FBK_GEN_OFFSET",
        "COMMU_ANGLE_SENSOR",
        "FBK_GEN_CYCLES",
        "COMMU_PHASING_MAX_CURRENT",
        "COMMU_PHASING_TIMEOUT",
        "COMMU_PHASING_ACCURACY",
        "COMMU_PHASING_MODE",
        "MOT_COMMU_MOD",
        "COMMU_ANGLE_INTEGRITY1_OPTION",
        "COMMU_ANGLE_INTEGRITY2_OPTION",
    ]

    class ResultType(IntEnum):
        SUCCESS = 0
        FAIL = -1

    result_description = {
        ResultType.SUCCESS: "Phasing process finished successfully",
        ResultType.FAIL: "Phasing process has failed.  Review your motor configuration.",
    }

    def __init__(
        self,
        mc: "MotionController",
        servo: str,
        axis: int,
        default_current: bool = True,
        default_timeout: bool = True,
        default_accuracy: bool = True,
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.comm: Optional[SensorType] = None
        self.ref: Optional[SensorType] = None
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))

        self.default_phasing_current = default_current
        self.default_phasing_timeout = default_timeout
        self.default_phasing_accuracy = default_accuracy

        self.pha_current: float = 0.0
        self.pha_timeout: float = 0.0
        self.pha_accuracy: float = 0.0

    @BaseTest.stoppable
    def check_input_data(self) -> None:
        max_current_drive = self.mc.communication.get_register(
            self.MAX_CURRENT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(max_current_drive, float):
            raise TypeError("Max. current of the drive has to be a float")
        max_current_motor = self.mc.communication.get_register(
            self.RATED_CURRENT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(max_current_motor, float):
            raise TypeError("Rated current has to be a float")
        max_test_current = min(max_current_drive, max_current_motor)

        if self.default_phasing_current:
            pos_vel_ratio = self.mc.configuration.get_pos_to_vel_ratio(
                servo=self.servo, axis=self.axis
            )
            if pos_vel_ratio == 1:
                self.pha_current = self.PHASING_CURRENT_PERCENTAGE * max_test_current
            else:
                self.pha_current = self.PHASING_CURRENT_PERCENTAGE_GEAR * max_test_current
            self.mc.communication.set_register(
                self.MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER,
                value=self.pha_current,
                servo=self.servo,
                axis=self.axis,
            )
        else:
            pha_current = self.mc.communication.get_register(
                self.MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER, servo=self.servo, axis=self.axis
            )
            if not isinstance(pha_current, float):
                raise TypeError(
                    f"{self.MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER} has to be a float"
                )
            self.pha_current = pha_current
            if self.pha_current > max_test_current:
                raise TestError("Defined phasing current is higher than configured maximum current")
        if self.default_phasing_timeout:
            self.mc.communication.set_register(
                self.PHASING_TIMEOUT_REGISTER,
                self.PHASING_TIMEOUT_DEFAULT,
                servo=self.servo,
                axis=self.axis,
            )
        if self.default_phasing_accuracy:
            if SensorType.HALLS in [self.comm, self.ref]:
                self.mc.communication.set_register(
                    self.PHASING_ACCURACY_REGISTER,
                    self.PHASING_ACCURACY_HALLS_DEFAULT,
                    servo=self.servo,
                    axis=self.axis,
                )
            else:
                self.mc.communication.set_register(
                    self.PHASING_ACCURACY_REGISTER,
                    self.PHASING_ACCURACY_DEFAULT,
                    servo=self.servo,
                    axis=self.axis,
                )

    @BaseTest.stoppable
    def setup(self) -> None:
        # Prerequisites:
        #  - Motor & Feedbacks configured (Pair poles & rated current are used)
        #  - Current control loop tuned
        #  - Feedbacks polarity checked
        # This test should be only executed for the reference sensor
        # Protection to avoid any unwanted movement
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("CONFIGURATION OF THE TEST", axis=self.axis)

        self.comm = self.mc.configuration.get_commutation_feedback(servo=self.servo, axis=self.axis)
        self.ref = self.mc.configuration.get_reference_feedback(servo=self.servo, axis=self.axis)

        if self.ref == self.INTERNAL_GENERATOR_VALUE:
            raise TestError("Reference feedback sensor is set to internal generator")
        if self.comm == self.INTERNAL_GENERATOR_VALUE:
            raise TestError("Commutation feedback sensor is set to internal generator")

        # selection of commutation sensor
        if (
            self.mc.configuration.get_reference_feedback_category(servo=self.servo, axis=self.axis)
            == SensorCategory.INCREMENTAL
        ):
            # Delete commutation feedback from backup registers list as
            # commutation feedback is kept the same
            fb = self.comm
        else:
            # Need to restore commutation feedback as in commutation feedback
            # is set the one in reference
            fb = self.ref

        # Check phasing registers mode
        self.logger.debug("Checking input data")
        self.check_input_data()

        # Set sinusoidal commutation modulation
        self.mc.configuration.set_commutation_mode(
            CommutationMode.SINUSOIDAL, servo=self.servo, axis=self.axis
        )
        self.logger.info("Commutation modulation set to Sinusoidal")

        self.mc.motion.set_operation_mode(OperationMode.CURRENT, servo=self.servo, axis=self.axis)
        self.logger.info("Mode of operation set to Current mode")

        self.mc.motion.set_current_quadrature(0, servo=self.servo, axis=self.axis)
        self.mc.motion.set_current_direct(0, servo=self.servo, axis=self.axis)
        self.logger.info("Target quadrature current set to zero", axis=self.axis)
        self.logger.info("Target direct current set to zero", axis=self.axis)

        self.mc.configuration.set_commutation_feedback(fb, servo=self.servo, axis=self.axis)
        self.logger.info("Reset phasing status by setting again commutation sensor")

        self.mc.configuration.set_phasing_mode(PhasingMode.FORCED, servo=self.servo, axis=self.axis)
        self.logger.info("Set phasing mode to Forced")

        self.logger.info("Set phasing current to %.2f A", self.pha_current)

        pha_timeout = self.mc.communication.get_register(
            self.PHASING_TIMEOUT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(pha_timeout, int):
            raise TypeError(f"{self.PHASING_TIMEOUT_REGISTER} has to be a integer")
        self.pha_timeout = pha_timeout
        self.logger.info(f"Set phasing timeout to {self.pha_timeout / 1000} s")

        pha_accuracy = self.mc.communication.get_register(
            self.PHASING_ACCURACY_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(pha_accuracy, int):
            raise TypeError(f"{self.PHASING_ACCURACY_REGISTER} has to be a integer")
        self.pha_accuracy = pha_accuracy
        self.logger.info(f"Set phasing accuracy to {self.pha_accuracy} mº")

        self.reaction_codes_to_warning()

    @BaseTest.stoppable
    def reaction_codes_to_warning(self) -> None:
        try:
            self.mc.communication.set_register(
                "COMMU_ANGLE_INTEGRITY1_OPTION", 1, servo=self.servo, axis=self.axis
            )
        except IMRegisterNotExist:
            self.logger.warning("Could not write COMMU_ANGLE_INTEGRITY1_OPTION")

        try:
            self.mc.communication.set_register(
                "COMMU_ANGLE_INTEGRITY2_OPTION", 1, servo=self.servo, axis=self.axis
            )
        except IMRegisterNotExist:
            self.logger.warning("Could not write COMMU_ANGLE_INTEGRITY2_OPTION")

    @BaseTest.stoppable
    def define_phasing_steps(self) -> int:
        # Doc: Last step is defined as the first angle delta smaller than 3 times
        # the phasing accuracy
        delta = 3 * self.pha_accuracy / 1000

        # If reference feedback are Halls
        if self.ref == SensorType.HALLS:
            actual_angle = self.INITIAL_ANGLE_HALLS
        else:
            actual_angle = self.INITIAL_ANGLE
        num_of_steps = 1
        while actual_angle > delta:
            actual_angle = actual_angle / 2
            num_of_steps += 1
        return num_of_steps

    @BaseTest.stoppable
    def set_phasing_mode(self) -> PhasingMode:
        ref_category = self.mc.configuration.get_reference_feedback_category(
            servo=self.servo, axis=self.axis
        )
        comm_category = self.mc.configuration.get_commutation_feedback_category(
            servo=self.servo, axis=self.axis
        )
        # Check if reference feedback is incremental
        if ref_category == SensorCategory.INCREMENTAL:
            # In that if commutation feedback is incremental also
            if self.comm == SensorType.INTGEN:
                raise TestError("Commutation feedback sensor is set to internal generator")
            elif comm_category == SensorCategory.INCREMENTAL:
                # Set forced mode
                return PhasingMode.FORCED
            else:
                # Set a forced and then a No-Phasing
                return PhasingMode.NO_PHASING
        elif self.comm == self.ref:
            # Set a forced and then a No-Phasing
            return PhasingMode.NO_PHASING
        else:
            # Set a forced and then a Non forced
            return PhasingMode.NON_FORCED

    @BaseTest.stoppable
    def loop(self) -> ResultType:
        self.logger.info("START OF THE TEST", axis=self.axis)

        num_of_steps = self.define_phasing_steps()

        self.logger.info("Enabling motor", axis=self.axis)
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)

        self.logger.info("Wait until phasing is executed", axis=self.axis)

        phasing_bit_latched = False
        timeout = time.time() + (num_of_steps * self.pha_timeout / 1000)
        while time.time() < timeout:
            self.stoppable_sleep(0.1)
            if self.mc.configuration.is_commutation_feedback_aligned(
                servo=self.servo, axis=self.axis
            ):
                phasing_bit_latched = True
                break

        if not phasing_bit_latched:
            self.logger.info("ERROR: Phasing process has failed. Review your motor configuration.")
            return self.ResultType.FAIL

        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        pha = self.set_phasing_mode()
        ang = self.mc.communication.get_register(
            self.COMMUTATION_ANGLE_OFFSET_REGISTER, servo=self.servo, axis=self.axis
        )

        self.suggested_registers = {
            "COMMU_PHASING_MODE": pha,
            "COMMU_PHASING_TIMEOUT": self.pha_timeout,
            "COMMU_PHASING_ACCURACY": self.pha_accuracy,
            "COMMU_PHASING_MAX_CURRENT": self.pha_current,
            "COMMU_ANGLE_OFFSET": ang,
        }
        return self.ResultType.SUCCESS

    def teardown(self) -> None:
        self.logger.info("Disabling motor")
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def get_result_msg(self, output: ResultType) -> str:
        return self.result_description[output]

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output < self.ResultType.SUCCESS:
            return SeverityLevel.FAIL
        else:
            return SeverityLevel.SUCCESS
