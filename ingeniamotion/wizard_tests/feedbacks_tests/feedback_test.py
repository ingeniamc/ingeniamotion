from enum import IntEnum
import time
import math
from typing import TYPE_CHECKING, Optional

import ingenialogger

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.wizard_tests.base_test import BaseTest, TestError
from ingeniamotion.exceptions import IMRegisterNotExist, IMException
from ingeniamotion.enums import OperationMode, SeverityLevel, SensorType


class Feedbacks(BaseTest):
    """Feedbacks Wizard Class description."""

    class ResultType(IntEnum):
        SUCCESS = 0
        RESOLUTION_ERROR = -1
        SYMMETRY_ERROR = -2
        POS_VEL_RATIO_ERROR = -4

    class Polarity(IntEnum):
        NORMAL = 0
        REVERSED = 1

    result_description = {
        ResultType.SUCCESS: "Feedback test pass successfully",
        ResultType.RESOLUTION_ERROR: "Feedback has a resolution error",
        ResultType.SYMMETRY_ERROR: "Feedback has a symmetry error",
        ResultType.POS_VEL_RATIO_ERROR: "Position to velocity sensor ratio cannot be different "
        "than 1 when both feedback sensors are the same.",
    }

    # Aux constants
    FEEDBACK_TOLERANCE = 17
    TEST_FREQUENCY = 0.4
    TIME_BETWEEN_MOVEMENT = 0.5
    PERCENTAGE_CURRENT_USED = 0.8
    LOW_PASS_FILTER = 1

    FAIL_MSG_MISMATCH = "A mismatch in resolution has been detected."

    COMMUTATION_MODULATION_REGISTER = "MOT_COMMU_MOD"
    POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER = "PROF_POS_VEL_RATIO"
    VELOCITY_FEEDBACK_FILTER_1_TYPE_REGISTER = "CL_VEL_FBK_FILTER1_TYPE"
    VELOCITY_FEEDBACK_FILTER_1_FREQUENCY_REGISTER = "CL_VEL_FBK_FILTER1_FREQ"
    RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
    MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION = "DRV_PROT_MAN_MAX_CONT_CURRENT_VALUE"
    POSITIONING_OPTION_CODE_REGISTER = "PROF_POS_OPTION_CODE"
    MAX_POSITION_RANGE_LIMIT_REGISTER = "CL_POS_REF_MAX_RANGE"
    MIN_POSITION_RANGE_LIMIT_REGISTER = "CL_POS_REF_MIN_RANGE"

    BACKUP_REGISTERS = [
        "CL_POS_FBK_SENSOR",
        "MOT_PAIR_POLES",
        "DRV_OP_CMD",
        "CL_CUR_Q_SET_POINT",
        "CL_CUR_D_SET_POINT",
        "FBK_GEN_MODE",
        "FBK_GEN_FREQ",
        "FBK_GEN_GAIN",
        "FBK_GEN_OFFSET",
        "COMMU_ANGLE_SENSOR",
        "FBK_GEN_CYCLES",
        "FBK_SSI2_POS_POLARITY",
        "COMMU_PHASING_MODE",
        "MOT_COMMU_MOD",
        "CL_AUX_FBK_SENSOR",
        "ERROR_DIGENC_AGAINST_HALL_OPTION",
        "CL_VEL_FOLLOWING_OPTION",
        "ERROR_VEL_OUT_LIMITS_OPTION",
        "ERROR_POS_OUT_LIMITS_OPTION",
        "ERROR_POS_FOLLOWING_OPTION",
        "COMMU_ANGLE_INTEGRITY1_OPTION",
        "COMMU_ANGLE_INTEGRITY2_OPTION",
        "CL_VEL_FBK_SENSOR",
        "COMMU_ANGLE_REF_SENSOR",
        "CL_VEL_FBK_FILTER1_TYPE",
        "CL_VEL_FBK_FILTER1_FREQ",
        POSITIONING_OPTION_CODE_REGISTER,
        MAX_POSITION_RANGE_LIMIT_REGISTER,
        MIN_POSITION_RANGE_LIMIT_REGISTER,
    ]

    FEEDBACK_POLARITY_REGISTER: str

    SENSOR_TYPE_FEEDBACK_TEST: SensorType

    def __init__(self, mc: "MotionController", servo: str, axis: int) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.sensor = self.SENSOR_TYPE_FEEDBACK_TEST
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        self.feedback_resolution: Optional[int] = None
        self.pair_poles: Optional[int] = None
        self.pos_vel_same_feedback = False
        self.resolution_multiplier = 1.0
        self.test_frequency = self.TEST_FREQUENCY
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.suggested_registers = {}

    @BaseTest.stoppable
    def check_feedback_tolerance(
        self, error: float, error_msg: str, error_type: ResultType
    ) -> ResultType:
        if error > self.FEEDBACK_TOLERANCE:
            error_advice = "Please, review your feedback & motor pair poles settings"
            self.logger.error("%s %s", error_msg, error_advice)
            return error_type
        return self.ResultType.SUCCESS

    @BaseTest.stoppable
    def check_symmetry(self, positive: float, negative: float) -> ResultType:
        self.logger.info("SYMMETRY CHECK")
        if not isinstance(self.feedback_resolution, int):
            raise TypeError("Feedbacks has to be set before symetry checking.")
        error = 100 * abs(positive + negative) / self.feedback_resolution
        self.logger.info("Detected symmetry mismatch of: %.3f%%", error)
        error_msg = (
            "ERROR: A mismatch in resolution has been "
            "detected between positive and negative direction."
        )
        return self.check_feedback_tolerance(error, error_msg, self.ResultType.SYMMETRY_ERROR)

    @BaseTest.stoppable
    def check_polarity(self, displacement: float) -> Polarity:
        self.logger.info("POLARITY CHECK")
        polarity = self.Polarity.NORMAL if displacement > 0 else self.Polarity.REVERSED
        self.logger.info("Feedback polarity detected: %s", polarity.name)
        return polarity

    @BaseTest.stoppable
    def check_resolution(self, displacement: float) -> ResultType:
        if self.pair_poles is None:
            raise TypeError("Pair poles has to be set before resolution checking.")
        if self.feedback_resolution is None:
            raise TypeError("Feedback resolution has to be set before resolution checking.")
        displacement = displacement * self.pair_poles
        self.logger.info("RESOLUTION CHECK")
        self.logger.info("Theoretical resolution: %.0f", self.feedback_resolution)
        self.logger.info("Detected resolution (pos): %.0f", abs(displacement))
        displacement_value = abs(self.feedback_resolution - abs(displacement))
        error = 100 * displacement_value / self.feedback_resolution
        self.logger.info("Detected mismatch of: %.3f%%", error)
        error_msg = (
            "ERROR: The detected feedback resolution does not "
            "match with the specified in the configuration."
        )
        return self.check_feedback_tolerance(error, error_msg, self.ResultType.RESOLUTION_ERROR)

    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        # First set all feedback to feedback in test, so there won't be
        # more than 5 feedback at the same time
        self.mc.configuration.set_commutation_feedback(
            self.sensor, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_reference_feedback(self.sensor, servo=self.servo, axis=self.axis)
        self.mc.configuration.set_velocity_feedback(self.sensor, servo=self.servo, axis=self.axis)
        self.mc.configuration.set_position_feedback(self.sensor, servo=self.servo, axis=self.axis)
        self.mc.configuration.set_auxiliar_feedback(self.sensor, servo=self.servo, axis=self.axis)
        # Set Polarity to 0
        self.mc.communication.set_register(
            self.FEEDBACK_POLARITY_REGISTER, self.Polarity.NORMAL, servo=self.servo, axis=self.axis
        )
        # Depending on the type of the feedback, calculate the correct
        # feedback resolution
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )

    @BaseTest.stoppable
    def reaction_codes_to_warning(self) -> None:
        # TODO Add function in errors to disable errors
        # set velocity and position following errors to WARNING = 1
        # ignore failed writes
        following_error_uids = [
            "ERROR_DIGENC_AGAINST_HALL_OPTION",
            "ERROR_DIGHALL_SEQ_OPTION",
            "CL_VEL_FOLLOWING_OPTION",
            "ERROR_VEL_OUT_LIMITS_OPTION",
            "ERROR_POS_OUT_LIMITS_OPTION",
            "ERROR_POS_FOLLOWING_OPTION",
            "COMMU_ANGLE_INTEGRITY1_OPTION",
            "COMMU_ANGLE_INTEGRITY2_OPTION",
        ]
        for following_error_uid in following_error_uids:
            try:
                self.mc.communication.set_register(
                    following_error_uid, 1, servo=self.servo, axis=self.axis
                )
            except IMRegisterNotExist as e:
                self.logger.warning(e)

    @BaseTest.stoppable
    def suggest_polarity(self, pol: Polarity) -> None:
        if not isinstance(self.FEEDBACK_POLARITY_REGISTER, str):
            raise TypeError("Feedback polarity register has to be set before polarity suggestion.")
        polarity_uid = self.FEEDBACK_POLARITY_REGISTER
        self.suggested_registers[polarity_uid] = pol

    @BaseTest.stoppable
    def setup(self) -> None:
        # Prerequisites:
        #  - Motor & Feedbacks configured (Pair poles & rated current are used)
        #  - Current control loop tuned
        #  - Feedback reaction codes to WARNING
        # Protection to avoid any unwanted movement
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("CONFIGURATION OF THE TEST")
        # Set commutation modulation to sinusoidal
        self.mc.communication.set_register(
            self.COMMUTATION_MODULATION_REGISTER, 0, servo=self.servo, axis=self.axis
        )
        # Set positioning mode to NO LIMITS
        self.mc.communication.set_register(
            self.POSITIONING_OPTION_CODE_REGISTER, 0, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            self.MIN_POSITION_RANGE_LIMIT_REGISTER, 0, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            self.MAX_POSITION_RANGE_LIMIT_REGISTER, 0, servo=self.servo, axis=self.axis
        )
        # Default resolution multiplier
        # Change multiplier using gear ratio if feedback to check is configured
        # as position sensor (out of gear)
        position_feedback_value = self.mc.configuration.get_position_feedback(
            servo=self.servo, axis=self.axis
        )
        velocity_feedback_value = self.mc.configuration.get_velocity_feedback(
            servo=self.servo, axis=self.axis
        )

        self.pos_vel_same_feedback = position_feedback_value == velocity_feedback_value
        if position_feedback_value == self.sensor:
            resolution_multiplier = self.mc.communication.get_register(
                self.POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER, servo=self.servo, axis=self.axis
            )
            if not isinstance(resolution_multiplier, float):
                raise TypeError("Resolution multiplier has to be a float")
            self.resolution_multiplier = resolution_multiplier
        # Read pole pairs and set to 1 for an electrical revolution
        self.pair_poles = self.mc.configuration.get_motor_pair_poles(
            servo=self.servo, axis=self.axis
        )
        # For each feedback on motor side we should repeat this test using the
        # feedback as position sensor. The polarity of the feedback must be set
        # also to normal at the beginning. All feedback are set to the same,
        # in order to avoid feedback configuration
        # error (wizard_tests series can only support 4 feedback at the
        # same time)
        self.feedback_setting()

        self.mc.motion.set_internal_generator_configuration(
            OperationMode.CURRENT, servo=self.servo, axis=self.axis
        )
        self.logger.info("Set pair poles to 1")
        self.logger.info("Mode of operation set to Current mode")
        self.logger.info("Set phasing mode to No phasing")
        self.logger.info("Target quadrature current set to zero")
        self.logger.info("Target direct current set to zero")
        self.logger.info("Commutation feedback set to Internal Generator")

        # set velocity and position following errors to WARNING = 1
        self.reaction_codes_to_warning()

    def teardown(self) -> None:
        self.logger.info("Disabling motor")
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    @BaseTest.stoppable
    def wait_for_movement(self, timeout: float) -> None:
        timeout = time.time() + timeout
        while time.time() < timeout:
            time.sleep(0.1)
            if self.mc.errors.is_fault_active(servo=self.servo, axis=self.axis):
                self.show_error_message()

    @BaseTest.stoppable
    def get_current_position(self) -> float:
        position = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        if not isinstance(position, int):
            raise TypeError("Actual position register must be an integer variable")
        current_position = position / self.resolution_multiplier
        return current_position

    @BaseTest.stoppable
    def current_ramp_up(self) -> None:
        rated_current = self.mc.communication.get_register(
            self.RATED_CURRENT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(rated_current, float):
            raise TypeError("Rated current has to be a float")
        nominal_current = self.mc.communication.get_register(
            self.MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION, servo=self.servo, axis=self.axis
        )
        if not isinstance(nominal_current, float):
            raise TypeError("Nominal current has to be a float")
        dict_currents = {
            "Rated motor current": rated_current,
            "Drive nominal current": nominal_current,
        }
        max_current = min(dict_currents.values())

        self.logger.debug(
            f"The maximum current is set by: {min(dict_currents, key=dict_currents.__getitem__)}"
        )
        # Increase current progressively
        self.logger.info(
            f"Increasing current to {self.PERCENTAGE_CURRENT_USED * 100}% "
            f"rated until one electrical cycle is completed"
        )

        target_current = self.PERCENTAGE_CURRENT_USED * max_current
        cycle_time = 2 / self.test_frequency

        self.mc.motion.current_quadrature_ramp(
            target_current, cycle_time, servo=self.servo, axis=self.axis
        )

    def first_movement_and_set_current(self) -> float:
        self.mc.motion.internal_generator_saw_tooth_move(
            1, 1, self.test_frequency, servo=self.servo, axis=self.axis
        )
        self.logger.info("Generator mode set to Saw tooth")
        self.logger.info("Generator frequency set to %s Hz", self.test_frequency)
        self.logger.info("Generator gain set to 1")
        self.logger.info("Generator offset set to 0")
        self.logger.info("Generator cycle number set to 1")
        self.current_ramp_up()
        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)
        return self.get_current_position()

    @BaseTest.stoppable
    def internal_generator_move(self, polarity: Polarity) -> float:
        cycles = 1
        freq = self.test_frequency
        gain = 1 if polarity == self.Polarity.NORMAL else -1
        pol = 1 if polarity == self.Polarity.NORMAL else -1
        self.mc.motion.internal_generator_saw_tooth_move(
            pol, cycles, freq, servo=self.servo, axis=self.axis
        )
        self.logger.info("%s direction test", polarity.name)
        self.logger.info("Generator gain set to %s", gain)
        self.logger.info("Generator offset set to %s", polarity)
        self.logger.info("Generator Cycle number set to %s", cycles)
        self.logger.info("Wait until one electrical cycle is completed")
        self.wait_for_movement(cycles / freq)
        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)
        position = self.get_current_position()
        self.logger.info("Actual position: %.0f", position)
        return position

    @BaseTest.stoppable
    def check_movement(self, position_displacement: float) -> None:
        self.logger.info("Detected forward displacement: %.0f", position_displacement)

        # Check the movement displacement
        if position_displacement == 0:
            error_movement_displacement = (
                "ERROR: No movement detected. "
                "Please, review your feedback "
                "configuration & wiring"
            )
            raise TestError(error_movement_displacement)

    def check_pos_vel_ratio(self) -> Optional[ResultType]:
        pos_vel_ratio = self.mc.communication.get_register(
            self.POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(pos_vel_ratio, float):
            raise TypeError("Position to velocity sensor ratio value has to be a float")
        if self.pos_vel_same_feedback and not math.isclose(pos_vel_ratio, 1):
            return self.ResultType.POS_VEL_RATIO_ERROR
        if not self.pos_vel_same_feedback and math.isclose(pos_vel_ratio, 1):
            self.logger.warning(
                "Position and velocity feedbacks are different but"
                " the Position to velocity sensor ratio is 1."
            )
            return None
        else:
            return None

    @BaseTest.stoppable
    def loop(self) -> ResultType:
        self.logger.info("START OF THE TEST")
        check_pos_vel_output = self.check_pos_vel_ratio()
        if check_pos_vel_output is not None:
            return check_pos_vel_output
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        position_1 = self.first_movement_and_set_current()
        self.logger.info("Actual position: %.0f", position_1, axis=self.axis)
        position_2 = self.internal_generator_move(self.Polarity.NORMAL)
        position_displacement = position_2 - position_1
        self.check_movement(position_displacement)
        position_3 = self.internal_generator_move(self.Polarity.REVERSED)
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        negative_displacement = position_3 - position_2
        self.logger.info("Detected reverse displacement: %.0f", negative_displacement)
        return self.generate_output(position_displacement, negative_displacement)

    def generate_output(
        self, position_displacement: float, negative_displacement: float
    ) -> ResultType:
        test_output = 0

        test_output += self.check_symmetry(position_displacement, negative_displacement)
        test_output += self.check_resolution(position_displacement)
        test_output = self.ResultType.SUCCESS if test_output == 0 else test_output
        polarity = self.check_polarity(position_displacement)
        self.suggest_polarity(polarity)
        return self.ResultType(test_output)

    def get_result_msg(self, output: ResultType) -> str:
        if output == self.ResultType.SUCCESS:
            return self.result_description[output]
        if output < 0:
            text = [self.result_description[x] for x in self.result_description if -output & -x > 0]
            return ".".join(text)
        else:
            raise NotImplementedError("This ResultType is not implemented")

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output < self.ResultType.SUCCESS:
            return SeverityLevel.FAIL
        else:
            return SeverityLevel.SUCCESS
