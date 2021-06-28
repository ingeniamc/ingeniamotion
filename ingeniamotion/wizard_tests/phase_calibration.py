import time
import ingenialogger

from enum import IntEnum
from ingenialink.exceptions import ILError

from .base_test import BaseTest, TestError


class Phasing(BaseTest):
    INTERNAL_GENERATOR_VALUE = 3
    INITIAL_ANGLE = 180
    INITIAL_ANGLE_HALLS = 240
    PHASING_CURRENT_PERCENTAGE = 0.8
    PHASING_TIMEOUT_DEFAULT = 1000
    PHASING_ACCURACY_HALLS_DEFAULT = 60000
    PHASING_ACCURACY_DEFAULT = 3600

    PHA_NON_FORCED = 0
    PHA_FORCED = 1
    PHA_NO_PHASING = 2

    PHA_BIT = 14

    ABSOLUTE = 0
    INCREMENTAL = 1

    class SensorType(IntEnum):
        ABS1 = 1  # ABSOLUTE ENCODER 1
        QEI = 4  # DIGITAL/INCREMENTAL ENCODER 1
        HALLS = 5  # DIGITAL HALLS
        SSI2 = 6  # SECONDARY SSI
        BISSC2 = 7  # ABSOLUTE ENCODER 2
        QEI2 = 8  # DIGITAL/INCREMENTAL ENCODER 2

    feedbackType = {
        SensorType.ABS1: ABSOLUTE,
        SensorType.QEI: INCREMENTAL,
        SensorType.HALLS: ABSOLUTE,
        SensorType.SSI2: ABSOLUTE,
        SensorType.BISSC2: ABSOLUTE,
        SensorType.QEI2: INCREMENTAL
    }

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
        "COMMU_ANGLE_INTEGRITY2_OPTION"
    ]

    class ResultType(IntEnum):
        SUCCESS = 0
        FAIL = -1

    result_description = {
        ResultType.SUCCESS: "Phasing process finished successfully",
        ResultType.FAIL: "Phasing process has failed.  Review your motor configuration.",
    }

    def __init__(self, mc, servo, axis, default_current=True,
                 default_timeout=True, default_accuracy=True):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.drive = mc.servos[servo]
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.comm = None
        self.ref = None
        self.logger = ingenialogger.get_logger(__name__)

        self.default_phasing_current = default_current
        self.default_phasing_timeout = default_timeout
        self.default_phasing_accuracy = default_accuracy

        self.pha_current = None
        self.pha_timeout = None
        self.pha_accuracy = None

    def check_input_data(self):
        if self.default_phasing_current:
            rated_curr = self.drive.raw_read("MOT_RATED_CURRENT", subnode=self.axis)
            phasing_current = self.PHASING_CURRENT_PERCENTAGE * rated_curr
            self.drive.write("COMMU_PHASING_MAX_CURRENT", phasing_current, subnode=self.axis)
        if self.default_phasing_timeout:
            self.drive.write("COMMU_PHASING_TIMEOUT", self.PHASING_TIMEOUT_DEFAULT, subnode=self.axis)
        if self.default_phasing_accuracy:
            if self.SensorType.HALLS in [self.comm, self.ref]:
                self.drive.write("COMMU_PHASING_ACCURACY",
                                 self.PHASING_ACCURACY_HALLS_DEFAULT,
                                 subnode=self.axis)
            else:
                self.drive.write("COMMU_PHASING_ACCURACY",
                                 self.PHASING_ACCURACY_DEFAULT,
                                 subnode=self.axis)

    def setup(self):
        # Prerequisites:
        #  - Motor & Feedbacks configured (Pair poles & rated current are used)
        #  - Current control loop tuned
        #  - Feedbacks polarity checked
        # This test should be only executed for the reference sensor
        # Protection to avoid any unwanted movement
        self.drive.disable(subnode=self.axis)

        self.logger.info("CONFIGURATION OF THE TEST", axis=self.axis)

        self.comm = self.drive.raw_read("COMMU_ANGLE_SENSOR", subnode=self.axis)
        self.ref = self.drive.raw_read("COMMU_ANGLE_REF_SENSOR", subnode=self.axis)

        if self.ref == self.INTERNAL_GENERATOR_VALUE:
            raise TestError('Reference feedback sensor is set to internal generator')
        if self.comm == self.INTERNAL_GENERATOR_VALUE:
            raise TestError('Commutation feedback sensor is set to internal generator')

        # selection of commutation sensor
        if self.feedbackType[self.ref] == self.INCREMENTAL:
            # Delete commutation feedback from backup registers list as commutation feedback is kept the same
            fb = self.comm
        else:
            # Need to restore commutation feedback as in commutation feedback is set the one in reference
            fb = self.ref

        # Check phasing registers mode
        self.logger.debug("Checking input data", axis=self.axis)
        self.check_input_data()

        # Set sinusoidal commutation modulation
        self.drive.raw_write("MOT_COMMU_MOD", 0, subnode=self.axis)

        self.logger.debug("Mode of operation set to Current mode", axis=self.axis)
        self.drive.raw_write("DRV_OP_CMD", 2, subnode=self.axis)

        self.logger.debug("Target quadrature current set to zero", axis=self.axis)
        self.logger.debug("Target direct current set to zero", axis=self.axis)
        self.drive.raw_write("CL_CUR_Q_SET_POINT", 0, subnode=self.axis)
        self.drive.raw_write("CL_CUR_D_SET_POINT", 0, subnode=self.axis)

        self.logger.debug("Reset phasing status by setting again commutation sensor", axis=self.axis)
        self.drive.raw_write("COMMU_ANGLE_SENSOR", fb, subnode=self.axis)

        self.pha_current = self.drive.raw_read("COMMU_PHASING_MAX_CURRENT", subnode=self.axis)
        self.logger.debug("Set phasing current to %.2f A",
                          self.pha_current,
                          axis=self.axis)

        self.pha_timeout = self.drive.raw_read("COMMU_PHASING_TIMEOUT",
                                               subnode=self.axis)  # value in ms
        self.logger.debug("Set phasing timeout to %s s",
                          self.pha_timeout / 1000,
                          axis=self.axis)

        self.pha_accuracy = self.drive.raw_read("COMMU_PHASING_ACCURACY", subnode=self.axis)
        self.logger.debug("Set phasing accuracy to %s mº", self.pha_accuracy, axis=self.axis)

        self.logger.debug("Set phasing mode to Forced", axis=self.axis)
        self.drive.raw_write("COMMU_PHASING_MODE", self.PHA_FORCED, subnode=self.axis)

        self.reaction_codes_to_warning()

    def reaction_codes_to_warning(self):
        try:
            self.drive.raw_write("COMMU_ANGLE_INTEGRITY1_OPTION", 1, subnode=self.axis)
        except ILError:
            self.logger.warning('Could not write COMMU_ANGLE_INTEGRITY1_OPTION', axis=self.axis)

        try:
            self.drive.raw_write("COMMU_ANGLE_INTEGRITY2_OPTION", 1, subnode=self.axis)
        except ILError:
            self.logger.warning('Could not write COMMU_ANGLE_INTEGRITY2_OPTION', axis=self.axis)

    def define_phasing_steps(self):
        # Doc: Last step is defined as the first angle delta smaller than 3 times the phasing accuracy
        delta = (3 * self.pha_accuracy / 1000)

        # If reference feedback are Halls
        if self.ref == self.SensorType.HALLS:
            actual_angle = self.INITIAL_ANGLE_HALLS
            num_of_steps = 1
            while actual_angle > delta:
                actual_angle = actual_angle / 2
                num_of_steps = num_of_steps + 1
        else:
            actual_angle = self.INITIAL_ANGLE
            num_of_steps = 1
            while actual_angle > delta:
                actual_angle = actual_angle / 2
                num_of_steps = num_of_steps + 1
        return num_of_steps

    def set_phasing_mode(self):
        # Check if reference feedback is incremental
        if self.feedbackType[self.ref] == self.INCREMENTAL:
            # In that if commutation feedback is incremental also
            if self.comm == self.INTERNAL_GENERATOR_VALUE:
                raise TestError('Commutation feedback sensor is set to internal generator')
            elif self.feedbackType[self.comm] == self.INCREMENTAL:
                # Set forced mode
                return self.PHA_FORCED
            else:
                # Set a forced and then a No-Phasing
                return self.PHA_NO_PHASING
        else:
            if self.comm == self.ref:
                # Set a forced and then a No-Phasing
                return self.PHA_NO_PHASING
            else:
                # Set a forced and then a Non forced
                return self.PHA_NON_FORCED

    def loop(self):
        self.logger.info("START OF THE TEST", axis=self.axis)

        num_of_steps = self.define_phasing_steps()

        self.logger.debug("Enabling motor", axis=self.axis)
        self.drive.enable(subnode=self.axis)

        self.logger.info("Wait until phasing is executed", axis=self.axis)

        phasing_bit_latched = False
        timeout = time.time() + (num_of_steps * self.pha_timeout / 1000)
        while time.time() < timeout:
            sw = int(self.drive.raw_read("DRV_STATE_STATUS", subnode=self.axis))
            time.sleep(0.1)
            if sw & 2**self.PHA_BIT > 0:
                phasing_bit_latched = True
                break

        if not phasing_bit_latched:
            return self.ResultType.FAIL

        self.drive.disable(subnode=self.axis)
        pha = self.set_phasing_mode()
        ang = self.drive.raw_read("COMMU_ANGLE_OFFSET", subnode=self.axis)

        self.suggested_registers = {
            "COMMU_PHASING_MODE": pha,
            "COMMU_PHASING_TIMEOUT": self.pha_timeout,
            "COMMU_PHASING_ACCURACY": self.pha_accuracy,
            "COMMU_PHASING_MAX_CURRENT": self.pha_current,
            "COMMU_ANGLE_OFFSET": ang
        }
        return self.ResultType.SUCCESS

    def teardown(self):
        self.logger.debug("Disabling motor", axis=self.axis)
        self.drive.disable(subnode=self.axis)

    def get_result_msg(self, output):
        return self.result_description[output]
