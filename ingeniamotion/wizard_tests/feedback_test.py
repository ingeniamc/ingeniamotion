import time
import logging
import ingenialink as il

from enum import IntEnum
from ingenialink.exceptions import ILError

from .base_test import BaseTest, TestError


class Feedbacks(BaseTest):
    """
    Feedbacks Wizard Class description.
    """

    # Available feedbacks
    class SensorType(IntEnum):
        ABS1 = 1  # ABSOLUTE ENCODER 1
        QEI = 4  # DIGITAL/INCREMENTAL ENCODER 1
        HALLS = 5  # DIGITAL HALLS
        SSI2 = 6  # SECONDARY SSI
        BISSC2 = 7  # ABSOLUTE ENCODER 2
        QEI2 = 8  # DIGITAL/INCREMENTAL ENCODER 2

    class ResultType(IntEnum):
        SUCCESS = 0
        RESOLUTION_ERROR = -2**0
        SYMMETRY_ERROR = -2**1

    result_description = {
        ResultType.SUCCESS: "Feedback test pass successfully",
        ResultType.RESOLUTION_ERROR: "Feedback has a resolution error",
        ResultType.SYMMETRY_ERROR: "Feedback has a symmetry error"
    }

    # Aux constants
    FEEDBACK_TOLERANCE = 17
    TEST_FREQUENCY = 0.4
    CYCLES = 10
    TIME_BETWEEN_MOVEMENT = 0.5
    PERCENTAGE_CURRENT_USED = 0.8
    LOW_PASS_FILTER = 1
    HALLS_FILTER_CUTOFF_FREQUENCY = 10
    WARNING_BIT_MASK = 0x0FFFFFFF
    FAIL_MSG_MISMATCH = "A mismatch in resolution has been detected."

    BACKUP_REGISTERS = ['CL_POS_FBK_SENSOR',
                        'FBK_BISS1_SSI1_POS_POLARITY',
                        'FBK_BISS2_POS_POLARITY',
                        'FBK_DIGENC1_POLARITY',
                        'FBK_DIGENC2_POLARITY',
                        'FBK_DIGHALL_POLARITY',
                        'FBK_DIGHALL_PAIRPOLES',
                        'MOT_PAIR_POLES',
                        'DRV_OP_CMD',
                        'CL_CUR_Q_SET_POINT',
                        'CL_CUR_D_SET_POINT',
                        'FBK_GEN_MODE',
                        'FBK_GEN_FREQ',
                        'FBK_GEN_GAIN',
                        'FBK_GEN_OFFSET',
                        'COMMU_ANGLE_SENSOR',
                        'FBK_GEN_CYCLES',
                        'FBK_SSI2_POS_POLARITY',
                        'COMMU_PHASING_MODE',
                        'MOT_COMMU_MOD',
                        'CL_AUX_FBK_SENSOR',
                        'ERROR_DIGENC_AGAINST_HALL_OPTION',
                        'ERROR_DIGHALL_SEQ_OPTION',
                        'CL_VEL_FOLLOWING_OPTION',
                        'ERROR_VEL_OUT_LIMITS_OPTION',
                        'ERROR_POS_OUT_LIMITS_OPTION',
                        'ERROR_POS_FOLLOWING_OPTION',
                        'COMMU_ANGLE_INTEGRITY1_OPTION',
                        'COMMU_ANGLE_INTEGRITY2_OPTION',
                        'CL_VEL_FBK_SENSOR',
                        'COMMU_ANGLE_REF_SENSOR',
                        'CL_VEL_FBK_FILTER1_TYPE',
                        'CL_VEL_FBK_FILTER1_FREQ']

    def __init__(self, servo, subnode, sensor):
        super().__init__()
        self.servo = servo
        self.subnode = subnode
        self.sensor = sensor
        self.feedback_resolution_functions = {
            self.SensorType.ABS1: self.absolute_encoder_1_resolution,
            self.SensorType.QEI: self.incremental_encoder_1_resolution,
            self.SensorType.HALLS: self.digital_halls_resolution,
            self.SensorType.SSI2: self.secondary_ssi_resolution,
            self.SensorType.BISSC2: self.absolute_encoder_2_resolution,
            self.SensorType.QEI2: self.incremental_encoder_2_resolution
        }
        self.feedback_resolution = None
        self.pair_poles = None
        self.resolution_multiplier = 1.0
        self.test_frequency = self.TEST_FREQUENCY
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.suggested_registers = {}

    def check_feedback_tolerance(self, error, error_msg, error_type):
        if error > self.FEEDBACK_TOLERANCE:
            error_advice = "Please, review your feedback & motor pair poles settings"
            logging.error("%s %s", error_msg, error_advice)
            return error_type
        return 0

    def check_symmetry(self, positive, negative):
        logging.info("SYMMETRY CHECK")
        error = 100 * abs(positive + negative) / self.feedback_resolution
        logging.info(
            "Detected symmetry mismatch of: {:.3f}%".format(error)
        )
        error_msg = "ERROR: A mismatch in resolution has been " \
                    "detected between positive and negative direction."
        return self.check_feedback_tolerance(error, error_msg, self.ResultType.SYMMETRY_ERROR)

    def check_polarity(self, displacement):
        logging.info("POLARITY CHECK")
        polarity = 0 if displacement > 0 else 1
        polarity_str = "NORMAL" if polarity == 0 else "REVERSED"
        logging.info("Feedback polarity detected: {}".format(polarity_str))
        return polarity

    def check_resolution(self, displacement):
        displacement = displacement * self.pair_poles
        logging.info("RESOLUTION CHECK")
        logging.info(
            "Theoretical resolution: {:.0f}".format(self.feedback_resolution)
        )
        logging.info(
            "Detected resolution (pos): {:.0f}".format(abs(displacement))
        )
        displacement_value = abs(self.feedback_resolution - abs(displacement))
        error = 100 * displacement_value / self.feedback_resolution
        logging.info("Detected mismatch of: {:.3f}%".format(error))
        error_msg = "ERROR: The detected feedback resolution does not " \
                    "match with the specified in the configuration."
        return self.check_feedback_tolerance(error, error_msg, self.ResultType.RESOLUTION_ERROR)

    def feedback_setting(self):
        if self.sensor == self.SensorType.HALLS:
            self.halls_extra_settings()
        # First set all feedback to feedback in test, so there won't be
        # more than 5 feedback at the same time
        self.servo.raw_write(
            "COMMU_ANGLE_REF_SENSOR",
            self.sensor,
            subnode=self.subnode
        )
        self.servo.raw_write(
            "COMMU_ANGLE_SENSOR",
            self.sensor,
            subnode=self.subnode
        )
        self.servo.raw_write(
            "CL_VEL_FBK_SENSOR",
            self.sensor,
            subnode=self.subnode
        )
        if self.sensor == self.SensorType.BISSC2:
            self.servo.raw_write(
                "CL_AUX_FBK_SENSOR",
                self.SensorType.ABS1,
                subnode=self.subnode
            )
        else:
            self.servo.raw_write(
                "CL_AUX_FBK_SENSOR",
                self.sensor,
                subnode=self.subnode
            )
        self.servo.raw_write(
            "CL_POS_FBK_SENSOR",
            self.sensor,
            subnode=self.subnode
        )
        # Depending on the type of the feedback, calculate the correct
        # feedback resolution
        self.feedback_resolution = self.feedback_resolution_functions[self.sensor]()

    def halls_extra_settings(self):
        # Read velocity feedback
        velocity_feedback = self.servo.raw_read("CL_VEL_FBK_SENSOR", subnode=self.subnode)
        # Read velocity feedback, if is HALLS set filter to 10 Hz
        # TODO: set filter depending on motors rated velocity by the
        #  following formula: f_halls = w_mechanical * pp * 6
        if velocity_feedback == self.SensorType.HALLS:
            filter_type_uid = 'CL_VEL_FBK_FILTER1_TYPE'
            filter_freq_uid = "CL_VEL_FBK_FILTER1_FREQ"
            self.suggested_registers[filter_type_uid] = self.LOW_PASS_FILTER
            self.suggested_registers[filter_freq_uid] = self.HALLS_FILTER_CUTOFF_FREQUENCY

            logging.info(
                "Setting a velocity low pass filter at 10 Hz as "
                "velocity feedback is set to Halls"
            )
            del self.backup_registers[self.subnode][
                "CL_VEL_FBK_FILTER1_TYPE"
            ]
            del self.backup_registers[self.subnode][
                "CL_VEL_FBK_FILTER1_FREQ"
            ]

    def absolute_encoder_1_resolution(self):
        logging.info("BiSS-C/SSI polarity set to Normal")
        self.servo.raw_write(
            "FBK_BISS1_SSI1_POS_POLARITY",
            0,
            subnode=self.subnode
        )
        single_turn_bits = self.servo.raw_read(
            "FBK_BISS1_SSI1_POS_ST_BITS",
            subnode=self.subnode
        )
        feedback_resolution = 2 ** single_turn_bits
        return feedback_resolution

    def incremental_encoder_1_resolution(self):
        logging.info("Incremental Encoder polarity set to Normal")
        self.servo.raw_write(
            "FBK_DIGENC1_POLARITY",
            0,
            subnode=self.subnode
        )
        feedback_resolution = self.servo.raw_read(
            "FBK_DIGENC1_RESOLUTION",
            subnode=self.subnode
        )
        return feedback_resolution

    def digital_halls_resolution(self):
        self.servo.raw_write(
            'CL_VEL_FBK_FILTER1_TYPE',
            self.LOW_PASS_FILTER,
            subnode=self.subnode
        )
        self.servo.write(
            "CL_VEL_FBK_FILTER1_FREQ",
            self.HALLS_FILTER_CUTOFF_FREQUENCY,
            subnode=self.subnode
        )
        self.servo.raw_write(
            "FBK_DIGHALL_POLARITY",
            0,
            subnode=self.subnode
        )
        logging.info("Halls pair poles set to {}".format(self.pair_poles))
        self.servo.raw_write(
            "FBK_DIGHALL_PAIRPOLES",
            self.pair_poles,
            subnode=self.subnode
        )
        # Update the frequency for Halls feedback
        self.test_frequency = 0.2
        feedback_resolution = 6 * self.pair_poles
        return feedback_resolution

    def secondary_ssi_resolution(self):
        logging.info("Secondary SSI polarity set to Normal")
        self.servo.raw_write(
            "FBK_SSI2_POS_POLARITY",
            0,
            subnode=self.subnode
        )
        secondary_single_turn_bits = self.servo.raw_read(
            "FBK_SSI2_POS_ST_BITS",
            subnode=self.subnode
        )
        feedback_resolution = 2 ** secondary_single_turn_bits
        return feedback_resolution

    def absolute_encoder_2_resolution(self):
        logging.info("BiSS-C slave 2 polarity set to Normal")
        self.servo.raw_write(
            "FBK_BISS2_POS_POLARITY",
            0,
            subnode=self.subnode
        )
        logging.info("Auxiliar feedback set to BiSS-C slave 1")
        serial_slave_1_single_turn_bits = self.servo.raw_read(
            "FBK_BISS2_POS_ST_BITS",
            subnode=self.subnode
        )
        feedback_resolution = 2 ** serial_slave_1_single_turn_bits
        return feedback_resolution

    def incremental_encoder_2_resolution(self):
        logging.info("Incremental Encoder 2 polarity set to Normal")
        self.servo.raw_write(
            "FBK_DIGENC2_POLARITY",
            0,
            subnode=self.subnode
        )
        feedback_resolution = self.servo.raw_read(
            "FBK_DIGENC2_RESOLUTION",
            subnode=self.subnode
        )
        return feedback_resolution

    def reaction_codes_to_warning(self):
        # set velocity and position following errors to WARNING = 1
        # ignore failed writes
        following_error_uids = [
            'ERROR_DIGENC_AGAINST_HALL_OPTION',
            'ERROR_DIGHALL_SEQ_OPTION',
            'CL_VEL_FOLLOWING_OPTION',
            'ERROR_VEL_OUT_LIMITS_OPTION',
            'ERROR_POS_OUT_LIMITS_OPTION',
            'ERROR_POS_FOLLOWING_OPTION',
            'COMMU_ANGLE_INTEGRITY1_OPTION',
            'COMMU_ANGLE_INTEGRITY2_OPTION'
        ]
        for following_error_uid in following_error_uids:
            try:
                self.servo.raw_write(following_error_uid, 1, subnode=self.subnode)
            except ILError as e:
                logging.warning(e)

    def suggest_polarity(self, pol):
        feedbacks_polarity_register = {
            self.SensorType.HALLS: "FBK_DIGHALL_POLARITY",
            self.SensorType.QEI: "FBK_DIGENC1_POLARITY",
            self.SensorType.QEI2: "FBK_DIGENC2_POLARITY",
            self.SensorType.ABS1: "FBK_BISS1_SSI1_POS_POLARITY",
            self.SensorType.SSI2: "FBK_SSI2_POS_POLARITY",
            self.SensorType.BISSC2: "FBK_BISS2_POS_POLARITY"

        }
        polarity_uid = feedbacks_polarity_register[self.sensor]
        if self.sensor == self.SensorType.HALLS:
            pair_poles_uid = "FBK_DIGHALL_PAIRPOLES"
            self.suggested_registers[pair_poles_uid] = self.pair_poles
        self.suggested_registers[polarity_uid] = pol

    def setup(self):
        # Prerequisites:
        #  - Motor & Feedbacks configured (Pair poles & rated current are used)
        #  - Current control loop tuned
        #  - Feedback reaction codes to WARNING
        # Protection to avoid any unwanted movement
        self.servo.disable(subnode=self.subnode)
        logging.info("-------------------------")
        logging.info("CONFIGURATION OF THE TEST")
        logging.info("-------------------------")
        # Set commutation modulation to sinusoidal
        self.servo.raw_write(
            "MOT_COMMU_MOD",
            0,
            subnode=self.subnode
        )
        # Read pole pairs and set to 1 for an electrical revolution
        self.pair_poles = self.servo.raw_read(
            "MOT_PAIR_POLES", subnode=self.subnode
        )
        self.servo.raw_write(
            "MOT_PAIR_POLES",
            1,
            subnode=self.subnode
        )
        # Default resolution multiplier
        # Change multiplier using gear ratio if feedback to check is configured
        # as position sensor (out of gear)
        position_feedback_value = self.servo.raw_read(
            'CL_POS_FBK_SENSOR', subnode=self.subnode
        )
        if position_feedback_value == self.sensor:
            self.resolution_multiplier = self.servo.raw_read(
                'PROF_POS_VEL_RATIO',
                subnode=self.subnode
            )
        # For each feedback on motor side we should repeat this test using the
        # feedback as position sensor. The polarity of the feedback must be set
        # also to normal at the beginning. All feedback are set to the same,
        # in order to avoid feedback configuration
        # error (wizard_tests series can only support 4 feedback at the
        # same time)
        self.feedback_setting()

        logging.info("Mode of operation set to Current mode")
        self.servo.raw_write(
            "DRV_OP_CMD",
            2,
            subnode=self.subnode
        )

        logging.info("Set phasing mode to No phasing")
        self.servo.raw_write(
            "COMMU_PHASING_MODE",
            2,
            subnode=self.subnode
        )

        logging.info("Target quadrature current set to zero")
        logging.info("Target direct current set to zero")
        self.servo.raw_write(
            "CL_CUR_Q_SET_POINT",
            0,
            subnode=self.subnode
        )
        self.servo.raw_write(
            "CL_CUR_D_SET_POINT",
            0,
            subnode=self.subnode
        )

        logging.info("Commutation feedback set to Internal Generator")
        self.servo.raw_write(
            "COMMU_ANGLE_SENSOR",
            3,
            subnode=self.subnode
        )

        logging.info("Generator mode set to Saw tooth")
        self.servo.raw_write(
            "FBK_GEN_MODE",
            1,
            subnode=self.subnode
        )

        logging.info(
            "Generator frequency set to {} Hz".format(self.test_frequency)
        )
        self.servo.raw_write(
            "FBK_GEN_FREQ",
            self.test_frequency,
            subnode=self.subnode
        )

        logging.info("Generator gain set to 1")
        self.servo.raw_write(
            "FBK_GEN_GAIN",
            1,
            subnode=self.subnode
        )

        logging.info("Generator offset set to 0")
        self.servo.raw_write(
            "FBK_GEN_OFFSET",
            0,
            subnode=self.subnode
        )

        logging.info("Generator cycle number set to 1")
        self.servo.raw_write(
            "FBK_GEN_CYCLES",
            1,
            subnode=self.subnode
        )

        # set velocity and position following errors to WARNING = 1
        self.reaction_codes_to_warning()

    def teardown(self):
        logging.debug("Disabling motor")
        self.servo.disable(subnode=self.subnode)

    def show_error_message(self):
        self.servo.write(
            'DRV_DIAG_ERROR_LIST_IDX',
            0,
            subnode=self.subnode
        )
        error_code = int(self.servo.read(
            'DRV_DIAG_ERROR_LIST_CODE',
            subnode=self.subnode
        ))
        error_code_cleaned = error_code & self.WARNING_BIT_MASK
        error_msg = "An error occurred during test."
        if error_code_cleaned in self.servo.errors:
            error_msg = self.servo.errors[error_code][3]
        raise TestError(error_msg)

    def force_displacement(self):
        logging.info(
            "Set Generator rearm to 1 again to force a new displacement"
        )
        self.servo.raw_write(
            "FBK_GEN_REARM",
            1,
            subnode=self.subnode
        )

    def wait_for_movement(self, timeout):
        timeout = time.time() + timeout
        while time.time() < timeout:
            time.sleep(0.1)
            state = self.servo.get_state(subnode=self.subnode)[0]
            if state != il.SERVO_STATE.ENABLED:
                self.show_error_message()

    def get_current_position(self):
        position = self.servo.raw_read(
            "CL_POS_FBK_VALUE",
            subnode=self.subnode
        )
        position = position / self.resolution_multiplier
        return position

    def loop(self):
        logging.info("-----------------")
        logging.info("START OF THE TEST")
        logging.info("-----------------")

        self.servo.enable(subnode=self.subnode)
        self.force_displacement()

        max_current = self.servo.raw_read(
            "MOT_RATED_CURRENT",
            subnode=self.subnode
        )

        # Increase current progressively
        logging.info(
            "Increasing current to {}% rated until one electrical cycle "
            "is completed".format(self.PERCENTAGE_CURRENT_USED * 100)
        )
        time_elapsed = 0
        current = 0
        time_division = 1 / self.test_frequency
        time_per_iteration = time_division / self.CYCLES
        max_time = 1 / self.test_frequency
        incremental_current = self.PERCENTAGE_CURRENT_USED * max_current
        incremental_current = incremental_current / self.CYCLES
        while time_elapsed < max_time:
            self.servo.raw_write(
                "CL_CUR_Q_SET_POINT",
                current,
                subnode=self.subnode
            )
            time.sleep(time_per_iteration)
            time_elapsed = time_elapsed + time_per_iteration
            current = current + incremental_current

        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)
        position_1 = self.get_current_position()
        logging.info("Actual position: {:.0f}".format(position_1))
        self.force_displacement()
        logging.info("Wait until one electrical cycle is completed")

        self.wait_for_movement(max_time)
        position_2 = self.get_current_position()
        position_displacement = position_2 - position_1
        logging.info("Actual position: {:.0f}".format(position_2))
        logging.info(
            "Detected forward displacement: {:.0f}".format(
                position_displacement
            )
        )

        # Check the movement displacement
        if position_displacement == 0:
            error_movement_displacement = "ERROR: No movement detected." \
                                          " Please, review your feedback configuration & wiring"
            raise TestError(error_movement_displacement)

        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)

        logging.info("-----------------")
        logging.info("Reversing direction test")
        logging.info("Generator gain set to -1")
        self.servo.raw_write(
            "FBK_GEN_GAIN",
            -1,
            subnode=self.subnode
        )
        logging.info("Generator offset set to 1")
        self.servo.raw_write(
            "FBK_GEN_OFFSET",
            1,
            subnode=self.subnode
        )
        logging.info("Generator Cycle number set to 1")
        self.servo.raw_write(
            "FBK_GEN_CYCLES",
            1,
            subnode=self.subnode
        )

        self.force_displacement()
        logging.info("Wait until one electrical cycle is completed")
        self.wait_for_movement(max_time)
        logging.info("Wait between movements")
        self.wait_for_movement(self.TIME_BETWEEN_MOVEMENT)

        position_3 = self.get_current_position()
        logging.info("Actual position: {:.0f}".format(position_3))

        self.servo.disable(subnode=self.subnode)

        negative_displacement = position_3 - position_2
        logging.info(
            "Detected reverse displacement: {:.0f}".format(
                negative_displacement
            )
        )

        test_output = 0

        test_output += self.check_symmetry(position_displacement, negative_displacement)
        test_output += self.check_resolution(position_displacement)

        test_output = self.ResultType.SUCCESS if test_output == 0 else test_output

        polarity = self.check_polarity(position_displacement)
        self.suggest_polarity(polarity)
        return test_output

    def get_result_msg(self, output):
        if output == self.ResultType.SUCCESS:
            return self.result_description[output]
        if output < 0:
            text = [self.result_description[x] for x in self.result_description if -output & x > 0]
            return ".".join(text)
