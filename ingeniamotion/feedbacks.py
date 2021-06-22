import ingenialogger
from enum import IntEnum

from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Feedbacks(metaclass=MCMetaClass):
    """
    Feedbacks Wizard Class description.
    """

    # Available feedbacks
    class SensorType(IntEnum):
        """
        Summit series feedback type enum
        """
        ABS1 = 1
        """ Absolute encoder 1 """
        QEI = 4
        """ Digital/Incremental encoder 1 """
        HALLS = 5
        """ Digital halls """
        SSI2 = 6
        """ Secondary SSI """
        BISSC2 = 7
        """ Absolute encoder 2 """
        QEI2 = 8
        """ Digital/Incremental encoder 2 """
        SMO = 9
        """ SMO """
        INTGEN = 3
        """ Internal generator """

    class SensorCategory(IntEnum):
        """
        Feedback category enum
        """
        ABSOLUTE = 0
        INCREMENTAL = 1

    __feedback_type_dict = {
        SensorType.ABS1: SensorCategory.ABSOLUTE,
        SensorType.QEI: SensorCategory.INCREMENTAL,
        SensorType.HALLS: SensorCategory.ABSOLUTE,
        SensorType.SSI2: SensorCategory.ABSOLUTE,
        SensorType.BISSC2: SensorCategory.ABSOLUTE,
        SensorType.QEI2: SensorCategory.INCREMENTAL,
        SensorType.INTGEN: SensorCategory.ABSOLUTE,
        SensorType.SMO: SensorCategory.ABSOLUTE
    }

    COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
    REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
    VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
    POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
    AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)
        self.feedback_resolution_functions = {
            self.SensorType.ABS1: self.get_absolute_encoder_1_resolution,
            self.SensorType.QEI: self.get_incremental_encoder_1_resolution,
            self.SensorType.HALLS: self.get_digital_halls_resolution,
            self.SensorType.SSI2: self.get_secondary_ssi_resolution,
            self.SensorType.BISSC2: self.get_absolute_encoder_2_resolution,
            self.SensorType.QEI2: self.get_incremental_encoder_2_resolution,
            self.SensorType.INTGEN: self.__no_feedback_resolution,
            self.SensorType.SMO: self.__no_feedback_resolution
        }

    # Commutation feedback
    def get_commutation_feedback(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads commutation feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.

        Returns:
            SensorType: Type of feedback configured.
        """
        commutation_feedback = self.mc.communication.get_register(
            self.COMMUTATION_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorType(commutation_feedback)
        return sensor_name

    @MCMetaClass.check_motor_enable
    def set_commutation_feedback(self, feedback,  servo=DEFAULT_SERVO,
                                 axis=DEFAULT_AXIS):
        """
        Writes commutation feedbacks value in the target servo and axis.

        Args:
            feedback (SensorType): feedback sensor number
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.COMMUTATION_FEEDBACK_REGISTER,
            feedback,
            servo=servo,
            axis=axis
        )

    def get_commutation_feedback_category(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads commutation feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorCategory: Category {ABSOLUTE, INCREMENTAL} of the
            selected feedback.
        """
        commutation_feedback = self.get_commutation_feedback(servo, axis)
        sensor_category = self.__feedback_type_dict[commutation_feedback]
        return sensor_category

    def get_commutation_feedback_resolution(self, servo=DEFAULT_SERVO,
                                            axis=DEFAULT_AXIS):
        """
        Reads commutation feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        sensor_type = self.get_commutation_feedback(servo, axis)
        feedback_resolution = self.feedback_resolution_functions[sensor_type] \
            (servo, axis)
        return feedback_resolution

    # Reference feedback
    def get_reference_feedback(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads reference feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorType: Type of feedback configured
        """
        reference_feedback = self.mc.communication.get_register(
            self.REFERENCE_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorType(reference_feedback)
        return sensor_name

    @MCMetaClass.check_motor_enable
    def set_reference_feedback(self, feedback,  servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Writes reference feedbacks value in the target servo and axis.

        Args:
            feedback (SensorType): feedback sensor number
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.REFERENCE_FEEDBACK_REGISTER,
            feedback,
            servo=servo,
            axis=axis
        )

    def get_reference_feedback_category(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads reference feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorCategory: Category {ABSOLUTE, INCREMENTAL} of the
            selected feedback.
        """
        reference_feedback = self.get_reference_feedback(servo, axis)
        sensor_category = self.__feedback_type_dict[reference_feedback]
        return sensor_category

    def get_reference_feedback_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads reference feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        sensor_type = self.get_reference_feedback(servo, axis)
        feedback_resolution = self.feedback_resolution_functions[sensor_type] \
            (servo, axis)
        return feedback_resolution

    # Velocity feedback
    def get_velocity_feedback(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads velocity feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorType: Type of feedback configured
        """
        velocity_feedback = self.mc.communication.get_register(
            self.VELOCITY_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorType(velocity_feedback)
        return sensor_name

    @MCMetaClass.check_motor_enable
    def set_velocity_feedback(self, feedback,  servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Writes velocity feedbacks value in the target servo and axis.

        Args:
            feedback (SensorType): feedback sensor number
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.VELOCITY_FEEDBACK_REGISTER,
            feedback,
            servo=servo,
            axis=axis
        )

    def get_velocity_feedback_category(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads velocity feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorCategory: Category {ABSOLUTE, INCREMENTAL} of the
            selected feedback.
        """
        velocity_feedback = self.get_velocity_feedback(servo, axis)
        sensor_category = self.__feedback_type_dict[velocity_feedback]
        return sensor_category

    def get_velocity_feedback_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads velocity feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        sensor_type = self.get_velocity_feedback(servo, axis)
        feedback_resolution = self.feedback_resolution_functions[sensor_type] \
            (servo, axis)
        return feedback_resolution

    # Position feedback
    def get_position_feedback(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads position feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorType: Type of feedback configured
        """
        position_feedback = self.mc.communication.get_register(
            self.POSITION_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorType(position_feedback)
        return sensor_name

    @MCMetaClass.check_motor_enable
    def set_position_feedback(self, feedback,  servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Writes position feedbacks value in the target servo and axis.

        Args:
            feedback (SensorType): feedback sensor number
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.POSITION_FEEDBACK_REGISTER,
            feedback,
            servo=servo,
            axis=axis
        )

    def get_position_feedback_category(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads position feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorCategory: Category {ABSOLUTE, INCREMENTAL} of the
            selected feedback.
        """
        position_feedback = self.get_position_feedback(servo, axis)
        sensor_category = self.__feedback_type_dict[position_feedback]
        return sensor_category

    def get_position_feedback_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads position feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        sensor_type = self.get_position_feedback(servo, axis)
        feedback_resolution = self.feedback_resolution_functions[sensor_type] \
            (servo, axis)
        return feedback_resolution

    # Auxiliar feedback
    def get_auxiliar_feedback(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads auxiliar feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorType: Type of feedback configured
        """
        auxiliar_feedback = self.mc.communication.get_register(
            self.AUXILIAR_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorType(auxiliar_feedback)
        return sensor_name

    @MCMetaClass.check_motor_enable
    def set_auxiliar_feedback(self, feedback,  servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Writes auxiliar feedbacks value in the target servo and axis.

        Args:
            feedback (SensorType): feedback sensor number
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.AUXILIAR_FEEDBACK_REGISTER,
            feedback,
            servo=servo,
            axis=axis
        )

    def get_auxiliar_feedback_category(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads auxiliar feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            SensorCategory: Category {ABSOLUTE, INCREMENTAL} of the
            selected feedback.
        """
        auxiliar_feedback = self.get_auxiliar_feedback(servo, axis)
        sensor_category = self.__feedback_type_dict[auxiliar_feedback]
        return sensor_category

    def get_auxiliar_feedback_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads auxiliar feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        sensor_type = self.get_auxiliar_feedback(servo, axis)
        feedback_resolution = self.feedback_resolution_functions[sensor_type] \
            (servo, axis)
        return feedback_resolution

    def get_absolute_encoder_1_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads ABS1 encoder resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of ABS1 encoder.
        """
        single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS1_SSI1_POS_ST_BITS",
            servo=servo,
            axis=axis
        )
        feedback_resolution = 2 ** single_turn_bits
        return feedback_resolution

    def get_incremental_encoder_1_resolution(self, servo=DEFAULT_SERVO,
                                             axis=DEFAULT_AXIS):
        """
        Reads incremental encoder 1 resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of incremental encoder 1.
        """
        feedback_resolution = self.mc.communication.get_register(
            "FBK_DIGENC1_RESOLUTION",
            servo=servo,
            axis=axis
        )
        return feedback_resolution

    def get_digital_halls_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads digital halls pole pairs in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of digital halls encoder.
        """
        pair_poles = self.mc.communication.get_register(
            "FBK_DIGHALL_PAIRPOLES",
            servo=servo,
            axis=axis
        )
        feedback_resolution = 6 * pair_poles
        return feedback_resolution

    def get_secondary_ssi_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads secondary SSI encoder resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of secondary SSI encoder.
        """
        secondary_single_turn_bits = self.mc.communication.get_register(
            "FBK_SSI2_POS_ST_BITS",
            servo=servo,
            axis=axis
        )
        feedback_resolution = 2 ** secondary_single_turn_bits
        return feedback_resolution

    def get_absolute_encoder_2_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Reads ABS2 encoder resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of ABS2 encoder.
        """
        serial_slave_1_single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS2_POS_ST_BITS",
            servo=servo,
            axis=axis
        )
        feedback_resolution = 2 ** serial_slave_1_single_turn_bits
        return feedback_resolution

    def get_incremental_encoder_2_resolution(self, servo=DEFAULT_SERVO,
                                             axis=DEFAULT_AXIS):
        """
        Reads incremental encoder 2 resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of incremental encoder 2 encoder.
        """
        feedback_resolution = self.mc.communication.get_register(
            "FBK_DIGENC2_RESOLUTION",
            servo=servo,
            axis=axis
        )
        return feedback_resolution

    def __no_feedback_resolution(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Used for feedbacks that has no resolution.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution Value error.
        """
        raise ValueError('Selected feedback does not have resolution')
