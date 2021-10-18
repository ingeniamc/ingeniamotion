import time
import math
import ingenialogger

from enum import IntEnum

from .base_test import BaseTest, TestError
from ingeniamotion.exceptions import IMRegisterNotExist
from ingeniamotion.enums import SensorType, OperationMode


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
        ResultType.POS_VEL_RATIO_ERROR:
            "Position to velocity sensor ratio cannot be different "
            "than 1 when both feedback sensors are the same."
    }

    # Aux constants
    FEEDBACK_TOLERANCE = 17
    TEST_FREQUENCY = 0.4
    TIME_BETWEEN_MOVEMENT = 0.5
    PERCENTAGE_CURRENT_USED = 0.8
    LOW_PASS_FILTER = 1
    HALLS_FILTER_CUTOFF_FREQUENCY = 10
    WARNING_BIT_MASK = 0x0FFFFFFF
    FAIL_MSG_MISMATCH = "A mismatch in resolution has been detected."

    COMMUTATION_MODULATION_REGISTER = "MOT_COMMU_MOD"
    POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER = "PROF_POS_VEL_RATIO"
    VELOCITY_FEEDBACK_FILTER_1_TYPE_REGISTER = "CL_VEL_FBK_FILTER1_TYPE"
    VELOCITY_FEEDBACK_FILTER_1_FREQUENCY_REGISTER = "CL_VEL_FBK_FILTER1_FREQ"
    DIG_HALL_POLE_PAIRS_REGISTER = "FBK_DIGHALL_PAIRPOLES"
    RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"

    BACKUP_REGISTERS = ["CL_POS_FBK_SENSOR",
                        "FBK_BISS1_SSI1_POS_POLARITY",
                        "FBK_BISS2_POS_POLARITY",
                        "FBK_DIGENC1_POLARITY",
                        "FBK_DIGENC2_POLARITY",
                        "FBK_DIGHALL_POLARITY",
                        "FBK_DIGHALL_PAIRPOLES",
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
                        "ERROR_DIGHALL_SEQ_OPTION",
                        "CL_VEL_FOLLOWING_OPTION",
                        "ERROR_VEL_OUT_LIMITS_OPTION",
                        "ERROR_POS_OUT_LIMITS_OPTION",
                        "ERROR_POS_FOLLOWING_OPTION",
                        "COMMU_ANGLE_INTEGRITY1_OPTION",
                        "COMMU_ANGLE_INTEGRITY2_OPTION",
                        "CL_VEL_FBK_SENSOR",
                        "COMMU_ANGLE_REF_SENSOR",
                        "CL_VEL_FBK_FILTER1_TYPE",
                        "CL_VEL_FBK_FILTER1_FREQ"]

    __feedbacks_polarity_register = {
        SensorType.HALLS: "FBK_DIGHALL_POLARITY",
        SensorType.QEI: "FBK_DIGENC1_POLARITY",
        SensorType.QEI2: "FBK_DIGENC2_POLARITY",
        SensorType.ABS1: "FBK_BISS1_SSI1_POS_POLARITY",
        SensorType.SSI2: "FBK_SSI2_POS_POLARITY",
        SensorType.BISSC2: "FBK_BISS2_POS_POLARITY"
    }

    def __init__(self, mc, servo, axis, sensor):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.sensor = sensor
        self.logger = ingenialogger.get_logger(__name__, axis=axis,
                                               drive=mc.servo_name(servo))
        self.feedback_resolution = None
        self.pair_poles = None
        self.pos_vel_same_feedback = None
        self.resolution_multiplier = 1.0
        self.test_frequency = self.TEST_FREQUENCY
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.suggested_registers = {}

    @BaseTest.stoppable
    def check_feedback_tolerance(self, error, error_msg, error_type):
        if error > self.FEEDBACK_TOLERANCE:
            error_advice = "Please, review your feedback & motor pair poles settings"
            self.logger.error("%s %s", error_msg, error_advice)
            return error_type
        return 0

    @BaseTest.stoppable
    def check_symmetry(self, positive, negative):
        self.logger.debug("SYMMETRY CHECK")
        error = 100 * abs(positive + negative) / self.feedback_resolution
        self.logger.info(
            "Detected symmetry mismatch of: %.3f%%",
            error
        )
        error_msg = "ERROR: A mismatch in resolution has been " \
                    "detected between positive and negative direction."
        return self.check_feedback_tolerance(error, error_msg,
                                             self.ResultType.SYMMETRY_ERROR)

    @BaseTest.stoppable
    def check_polarity(self, displacement):
        self.logger.debug("POLARITY CHECK")
        polarity = self.Polarity.NORMAL if displacement > 0 \
            else self.Polarity.REVERSED
        self.logger.info("Feedback polarity detected: %s",
                         polarity.name)
        return polarity

    @BaseTest.stoppable
    def check_resolution(self, displacement):
        displacement = displacement * self.pair_poles
        self.logger.debug("RESOLUTION CHECK")
        self.logger.debug(
            "Theoretical resolution: %.0f",
            self.feedback_resolution
        )
        self.logger.info("Detected resolution (pos): %.0f", abs(displacement))
        displacement_value = abs(self.feedback_resolution - abs(displacement))
        error = 100 * displacement_value / self.feedback_resolution
        self.logger.info("Detected mismatch of: %.3f%%", error)
        error_msg = "ERROR: The detected feedback resolution does not " \
                    "match with the specified in the configuration."
        return self.check_feedback_tolerance(
            error, error_msg, self.ResultType.RESOLUTION_ERROR)

    @BaseTest.stoppable
    def feedback_setting(self):
        if self.sensor == SensorType.HALLS:
            self.halls_extra_settings()
        # First set all feedback to feedback in test, so there won't be
        # more than 5 feedback at the same time
        self.mc.configuration.set_commutation_feedback(self.sensor,
                                                       servo=self.servo,
                                                       axis=self.axis)
        self.mc.configuration.set_reference_feedback(self.sensor,
                                                     servo=self.servo,
                                                     axis=self.axis)
        self.mc.configuration.set_velocity_feedback(self.sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        self.mc.configuration.set_position_feedback(self.sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        auxiliary_sensor = self.sensor
        if self.sensor == SensorType.BISSC2:
            auxiliary_sensor = SensorType.ABS1
        self.mc.configuration.set_auxiliar_feedback(auxiliary_sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        # Set Polarity to 0
        polarity_register = self.__feedbacks_polarity_register[self.sensor]
        self.mc.communication.set_register(
            polarity_register, self.Polarity.NORMAL,
            servo=self.servo, axis=self.axis
        )
        # Depending on the type of the feedback, calculate the correct
        # feedback resolution
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )

    @BaseTest.stoppable
    def halls_extra_settings(self):
        self.mc.communication.set_register(
            self.DIG_HALL_POLE_PAIRS_REGISTER, self.pair_poles,
            servo=self.servo, axis=self.axis
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
            self.suggested_registers[filter_freq_uid] = \
                self.HALLS_FILTER_CUTOFF_FREQUENCY

            self.logger.info(
                "Setting a velocity low pass filter at 10 Hz as "
                "velocity feedback is set to Halls"
            )
            del self.backup_registers[self.axis][
                self.VELOCITY_FEEDBACK_FILTER_1_TYPE_REGISTER
            ]
            del self.backup_registers[self.axis][
                self.VELOCITY_FEEDBACK_FILTER_1_FREQUENCY_REGISTER
            ]

    @BaseTest.stoppable
    def reaction_codes_to_warning(self):
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
            "COMMU_ANGLE_INTEGRITY2_OPTION"
        ]
        for following_error_uid in following_error_uids:
            try:
                self.mc.communication.set_register(
                    following_error_uid, 1,
                    servo=self.servo, axis=self.axis
                )
            except IMRegisterNotExist as e:
                self.logger.warning(e)

    @BaseTest.stoppable
    def suggest_polarity(self, pol):
        polarity_uid = self.__feedbacks_polarity_register[self.sensor]
        if self.sensor == SensorType.HALLS:
            pair_poles_uid = self.DIG_HALL_POLE_PAIRS_REGISTER
            self.suggested_registers[pair_poles_uid] = self.pair_poles
        self.suggested_registers[polarity_uid] = pol

    @BaseTest.stoppable
    def setup(self):
        # Prerequisites:
        #  - Motor & Feedbacks configured (Pair poles & rated current are used)
        #  - Current control loop tuned
        #  - Feedback reaction codes to WARNING
        # Protection to avoid any unwanted movement
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("CONFIGURATION OF THE TEST")
        # Set commutation modulation to sinusoidal
        self.mc.communication.set_register(
            self.COMMUTATION_MODULATION_REGISTER, 0,
            servo=self.servo, axis=self.axis
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
            self.resolution_multiplier = self.mc.communication.get_register(
                self.POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER,
                servo=self.servo, axis=self.axis
            )

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
        self.logger.debug("Set pair poles to 1")
        self.logger.debug("Mode of operation set to Current mode")
        self.logger.debug("Set phasing mode to No phasing")
        self.logger.debug("Target quadrature current set to zero")
        self.logger.debug("Target direct current set to zero")
        self.logger.debug("Commutation feedback set to Internal Generator")

        # set velocity and position following errors to WARNING = 1
        self.reaction_codes_to_warning()

    def teardown(self):
        self.logger.debug("Disabling motor")
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    @BaseTest.stoppable
    def show_error_message(self):
        error_code, axis, warning= self.mc.errors.get_last_buffer_error(
            servo=self.servo, axis=self.axis)
        # TODO check if clan warning bit is necessary
        error_code_cleaned = error_code & self.WARNING_BIT_MASK
        _, _, _, error_msg = self.mc.errors.get_error_data(
            error_code, servo=self.servo
        )
        raise TestError(error_msg)

    @BaseTest.stoppable
    def wait_for_movement(self, timeout):
        timeout = time.time() + timeout
        while time.time() < timeout:
            time.sleep(0.1)
            if self.mc.errors.is_fault_active(
                servo=self.servo, axis=self.axis
            ):
                self.show_error_message()

    @BaseTest.stoppable
    def get_current_position(self):
        position = self.mc.motion.get_actual_position(servo=self.servo,
                                                      axis=self.axis)
        position = position / self.resolution_multiplier
        return position

    @BaseTest.stoppable
    def current_ramp_up(self):
        max_current = self.mc.communication.get_register(
            self.RATED_CURRENT_REGISTER,
            servo=self.servo, axis=self.axis
        )
        # Increase current progressively
        self.logger.info(
            "Increasing current to %s%% rated until"
            " one electrical cycle is completed",
            self.PERCENTAGE_CURRENT_USED * 100
        )
        target_current = self.PERCENTAGE_CURRENT_USED * max_current
        cycle_time = 2 / self.test_frequency

        self.mc.motion.current_quadrature_ramp(
            target_current, cycle_time,
            servo=self.servo, axis=self.axis
        )

    def first_movement_and_set_current(self):
        self.mc.motion.internal_generator_saw_tooth_move(
            1, 1, self.test_frequency,
            servo=self.servo, axis=self.axis
        )
        self.logger.debug("Generator mode set to Saw tooth")
        self.logger.debug("Generator frequency set to %s Hz",
                          self.test_frequency)
        self.logger.debug("Generator gain set to 1")
        self.logger.debug("Generator offset set to 0")
        self.logger.debug("Generator cycle number set to 1")
        self.current_ramp_up()
        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)
        return self.get_current_position()

    @BaseTest.stoppable
    def internal_generator_move(self, polarity):
        cycles = 1
        freq = self.test_frequency
        gain = 1 if polarity == self.Polarity.NORMAL else -1
        pol = 1 if polarity == self.Polarity.NORMAL else -1
        self.mc.motion.internal_generator_saw_tooth_move(
            pol, cycles, freq,
            servo=self.servo, axis=self.axis
        )
        self.logger.debug("%s direction test", polarity.name)
        self.logger.debug("Generator gain set to %s", gain)
        self.logger.debug("Generator offset set to %s", polarity)
        self.logger.debug("Generator Cycle number set to %s", cycles)
        self.logger.debug("Wait until one electrical cycle is completed")
        self.wait_for_movement(cycles/freq)
        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)
        position = self.get_current_position()
        self.logger.debug("Actual position: %.0f", position)
        return position

    @BaseTest.stoppable
    def check_movement(self, position_displacement):
        self.logger.info("Detected forward displacement: %.0f",
                         position_displacement)

        # Check the movement displacement
        if position_displacement == 0:
            error_movement_displacement = "ERROR: No movement detected. " \
                                          "Please, review your feedback " \
                                          "configuration & wiring"
            raise TestError(error_movement_displacement)

    def check_pos_vel_ratio(self):
        pos_vel_ratio = self.mc.communication.get_register(
            self.POSITION_TO_VELOCITY_SENSOR_RATIO_REGISTER,
            servo=self.servo, axis=self.axis
        )
        if self.pos_vel_same_feedback and not math.isclose(pos_vel_ratio, 1):
            return self.ResultType.POS_VEL_RATIO_ERROR
        if not self.pos_vel_same_feedback and math.isclose(pos_vel_ratio, 1):
            self.logger.warning("Position and velocity feedbacks are different but"
                                " the Position to velocity sensor ratio is 1.")

    @BaseTest.stoppable
    def loop(self):
        self.logger.info("START OF THE TEST")
        check_pos_vel_output = self.check_pos_vel_ratio()
        if check_pos_vel_output is not None:
            return check_pos_vel_output
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        position_1 = self.first_movement_and_set_current()
        self.logger.debug("Actual position: %.0f",
                          position_1, axis=self.axis)
        position_2 = self.internal_generator_move(self.Polarity.NORMAL)
        position_displacement = position_2 - position_1
        self.check_movement(position_displacement)
        position_3 = self.internal_generator_move(self.Polarity.REVERSED)
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        negative_displacement = position_3 - position_2
        self.logger.info(
            "Detected reverse displacement: %.0f", negative_displacement
        )
        return self.generate_output(position_displacement,
                                    negative_displacement)

    def generate_output(self, position_displacement, negative_displacement):
        test_output = 0

        test_output += self.check_symmetry(position_displacement,
                                           negative_displacement)
        test_output += self.check_resolution(position_displacement)
        test_output = self.ResultType.SUCCESS if test_output == 0 \
            else test_output
        polarity = self.check_polarity(position_displacement)
        self.suggest_polarity(polarity)
        return test_output

    def get_result_msg(self, output):
        if output == self.ResultType.SUCCESS:
            return self.result_description[output]
        if output < 0:
            text = [self.result_description[x]
                    for x in self.result_description if -output & -x > 0]
            return ".".join(text)

    def get_result_severity(self, output):
        if output < self.ResultType.SUCCESS:
            return self.SeverityLevel.FAIL
        else:
            return self.SeverityLevel.SUCCESS
