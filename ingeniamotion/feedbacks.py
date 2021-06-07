import ingenialogger
from enum import IntEnum


class Feedbacks:
    """
    Feedbacks Wizard Class description.
    """

    # Available feedbacks
    class SensorName(IntEnum):
        """
        Summit series feedback type enum
        """
        ABS1 = 1  # ABSOLUTE ENCODER 1
        QEI = 4  # DIGITAL/INCREMENTAL ENCODER 1
        HALLS = 5  # DIGITAL HALLS
        SSI2 = 6  # SECONDARY SSI
        BISSC2 = 7  # ABSOLUTE ENCODER 2
        QEI2 = 8  # DIGITAL/INCREMENTAL ENCODER 2
        SMO = 9  # SMO
        INTGEN = 3  # INTERNAL GENERATOR

    class SensorType(IntEnum):
        """
        Feedback type enum
        """
        ABSOLUTE = 0
        INCREMENTAL = 1

    feedbackType = {
        SensorName.ABS1: SensorType.ABSOLUTE,
        SensorName.QEI: SensorType.INCREMENTAL,
        SensorName.HALLS: SensorType.ABSOLUTE,
        SensorName.SSI2: SensorType.ABSOLUTE,
        SensorName.BISSC2: SensorType.ABSOLUTE,
        SensorName.QEI2: SensorType.INCREMENTAL,
        SensorName.INTGEN: SensorType.ABSOLUTE,
        SensorName.SMO: SensorType.ABSOLUTE
    }

    COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
    REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
    VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
    POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
    AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    # Commutation feedback
    def get_commutation_feedback(self, servo="default", axis=1):
        """
        Reads commutation feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.

        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        self.mc.check_servo(servo)
        commutation_feedback = self.mc.communication.get_register(
            self.COMMUTATION_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorName(commutation_feedback)
        return sensor_name

    def set_commutation_feedback(self, feedback,  servo="default", axis=1):
        """
        Writes commutation feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            feedback (int): feedback sensor number
        """
        raise NotImplementedError("This function has not been implemented yet")

    def get_commutation_feedback_type(self, servo="default", axis=1):
        """
        Reads commutation feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        commutation_feedback = self.get_commutation_feedback(servo, axis)
        sensor_type = self.feedbackType[commutation_feedback]
        return sensor_type

    def get_commutation_feedback_resolution(self, servo="default", axis=1):
        """
        Reads commutation feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        raise NotImplementedError("This function has not been implemented yet")

    # Reference feedback
    def get_reference_feedback(self, servo="default", axis=1):
        """
        Reads reference feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.check_servo(servo)
        reference_feedback = self.mc.communication.get_register(
            self.REFERENCE_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorName(reference_feedback)
        return sensor_name

    def set_reference_feedback(self, feedback,  servo="default", axis=1):
        """
        Writes reference feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            feedback (int): feedback sensor number
        """
        raise NotImplementedError("This function has not been implemented yet")

    def get_reference_feedback_type(self, servo="default", axis=1):
        """
        Reads reference feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        reference_feedback = self.get_reference_feedback(servo, axis)
        sensor_type = self.feedbackType[reference_feedback]
        return sensor_type

    def get_reference_feedback_resolution(self, servo="default", axis=1):
        """
        Reads reference feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        raise NotImplementedError("This function has not been implemented yet")

    # Velocity feedback
    def get_velocity_feedback(self, servo="default", axis=1):
        """
        Reads velocity feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.check_servo(servo)
        velocity_feedback = self.mc.communication.get_register(
            self.VELOCITY_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorName(velocity_feedback)
        return sensor_name

    def set_velocity_feedback(self, feedback,  servo="default", axis=1):
        """
        Writes velocity feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            feedback (int): feedback sensor number
        """
        raise NotImplementedError("This function has not been implemented yet")

    def get_velocity_feedback_type(self, servo="default", axis=1):
        """
        Reads velocity feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        velocity_feedback = self.get_velocity_feedback(servo, axis)
        sensor_type = self.feedbackType[velocity_feedback]
        return sensor_type

    def get_velocity_feedback_resolution(self, servo="default", axis=1):
        """
        Reads velocity feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        raise NotImplementedError("This function has not been implemented yet")

    # Position feedback
    def get_position_feedback(self, servo="default", axis=1):
        """
        Reads position feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.check_servo(servo)
        position_feedback = self.mc.communication.get_register(
            self.POSITION_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorName(position_feedback)
        return sensor_name

    def set_position_feedback(self, feedback,  servo="default", axis=1):
        """
        Writes position feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            feedback (int): feedback sensor number
        """
        raise NotImplementedError("This function has not been implemented yet")

    def get_position_feedback_type(self, servo="default", axis=1):
        """
        Reads position feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        position_feedback = self.get_position_feedback(servo, axis)
        sensor_type = self.feedbackType[position_feedback]
        return sensor_type

    def get_position_feedback_resolution(self, servo="default", axis=1):
        """
        Reads position feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        raise NotImplementedError("This function has not been implemented yet")

    # Auxiliar feedback
    def get_auxiliar_feedback(self, servo="default", axis=1):
        """
        Reads auxiliar feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        """
        self.mc.check_servo(servo)
        auxiliar_feedback = self.mc.communication.get_register(
            self.AUXILIAR_FEEDBACK_REGISTER,
            servo=servo,
            axis=axis
        )
        sensor_name = self.SensorName(auxiliar_feedback)
        return sensor_name

    def set_auxiliar_feedback(self, feedback,  servo="default", axis=1):
        """
        Writes auxiliar feedbacks value in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            feedback (int): feedback sensor number
        """
        raise NotImplementedError("This function has not been implemented yet")

    def get_auxiliar_feedback_type(self, servo="default", axis=1):
        """
        Reads auxiliar feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            Feedbacks.SensorType: Type {ABSOLUTE, INCREMENTAL} of the the
            selected feedback.
        """
        auxiliar_feedback = self.get_auxiliar_feedback(servo, axis)
        sensor_type = self.feedbackType[auxiliar_feedback]
        return sensor_type

    def get_auxiliar_feedback_resolution(self, servo="default", axis=1):
        """
        Reads auxiliar feedbacks resolution in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
        Returns:
            int: Resolution of the selected feedback.
        """
        raise NotImplementedError("This function has not been implemented yet")
