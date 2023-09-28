from typing import TYPE_CHECKING, Optional

import ingenialogger

from ingeniamotion.enums import SensorType, SensorCategory

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Feedbacks(metaclass=MCMetaClass):
    """Feedbacks Wizard Class description."""

    __feedback_type_dict = {
        SensorType.ABS1: SensorCategory.ABSOLUTE,
        SensorType.QEI: SensorCategory.INCREMENTAL,
        SensorType.HALLS: SensorCategory.ABSOLUTE,
        SensorType.SSI2: SensorCategory.ABSOLUTE,
        SensorType.BISSC2: SensorCategory.ABSOLUTE,
        SensorType.QEI2: SensorCategory.INCREMENTAL,
        SensorType.INTGEN: SensorCategory.ABSOLUTE,
    }

    COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
    REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
    VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
    POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
    AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)
        self.feedback_resolution_functions = {
            SensorType.ABS1: self.get_absolute_encoder_1_resolution,
            SensorType.QEI: self.get_incremental_encoder_1_resolution,
            SensorType.HALLS: self.get_digital_halls_resolution,
            SensorType.SSI2: self.get_secondary_ssi_resolution,
            SensorType.BISSC2: self.get_absolute_encoder_2_resolution,
            SensorType.QEI2: self.get_incremental_encoder_2_resolution,
            SensorType.INTGEN: self.__no_feedback_resolution,
        }

    # Commutation feedback
    def get_commutation_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads commutation feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        commutation_feedback = self.mc.communication.get_register(
            self.COMMUTATION_FEEDBACK_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(commutation_feedback, int):
            raise TypeError("Commutation feedback value has to be an integer")
        return SensorType(commutation_feedback)

    @MCMetaClass.check_motor_disabled
    def set_commutation_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes commutation feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc.communication.set_register(
            self.COMMUTATION_FEEDBACK_REGISTER, feedback, servo=servo, axis=axis
        )

    def get_commutation_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Reads commutation feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        commutation_feedback = self.get_commutation_feedback(servo, axis)
        return self.__feedback_type_dict[commutation_feedback]

    def get_commutation_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads commutation feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_commutation_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Reference feedback
    def get_reference_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads reference feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        reference_feedback = self.mc.communication.get_register(
            self.REFERENCE_FEEDBACK_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(reference_feedback, int):
            raise TypeError("Reference feedback has to be an integer")
        return SensorType(reference_feedback)

    @MCMetaClass.check_motor_disabled
    def set_reference_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes reference feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc.communication.set_register(
            self.REFERENCE_FEEDBACK_REGISTER, feedback, servo=servo, axis=axis
        )

    def get_reference_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Reads reference feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        reference_feedback = self.get_reference_feedback(servo, axis)
        return self.__feedback_type_dict[reference_feedback]

    def get_reference_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads reference feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_reference_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Velocity feedback
    def get_velocity_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads velocity feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        velocity_feedback = self.mc.communication.get_register(
            self.VELOCITY_FEEDBACK_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(velocity_feedback, int):
            raise TypeError("Velocity feedback has to be an integer")
        return SensorType(velocity_feedback)

    @MCMetaClass.check_motor_disabled
    def set_velocity_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes velocity feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc.communication.set_register(
            self.VELOCITY_FEEDBACK_REGISTER, feedback, servo=servo, axis=axis
        )

    def get_velocity_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Reads velocity feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        velocity_feedback = self.get_velocity_feedback(servo, axis)
        return self.__feedback_type_dict[velocity_feedback]

    def get_velocity_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads velocity feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_velocity_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Position feedback
    def get_position_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads position feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        position_feedback = self.mc.communication.get_register(
            self.POSITION_FEEDBACK_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(position_feedback, int):
            raise TypeError("Position feedback has to be an integer")
        return SensorType(position_feedback)

    @MCMetaClass.check_motor_disabled
    def set_position_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes position feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc.communication.set_register(
            self.POSITION_FEEDBACK_REGISTER, feedback, servo=servo, axis=axis
        )

    def get_position_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Reads position feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        position_feedback = self.get_position_feedback(servo, axis)
        return self.__feedback_type_dict[position_feedback]

    def get_position_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads position feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_position_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Auxiliar feedback
    def get_auxiliar_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads auxiliar feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        auxiliar_feedback = self.mc.communication.get_register(
            self.AUXILIAR_FEEDBACK_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(auxiliar_feedback, int):
            raise TypeError("Auxiliar feedback has to be an integer")
        return SensorType(auxiliar_feedback)

    @MCMetaClass.check_motor_disabled
    def set_auxiliar_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes auxiliar feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc.communication.set_register(
            self.AUXILIAR_FEEDBACK_REGISTER, feedback, servo=servo, axis=axis
        )

    def get_auxiliar_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Reads auxiliar feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        auxiliar_feedback = self.get_auxiliar_feedback(servo, axis)
        return self.__feedback_type_dict[auxiliar_feedback]

    def get_auxiliar_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads auxiliar feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_auxiliar_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    def get_absolute_encoder_1_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads ABS1 encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of ABS1 encoder.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS1_SSI1_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(single_turn_bits, int):
            raise TypeError("Single-turn bits has to be an integer")
        resolution = 2**single_turn_bits
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_incremental_encoder_1_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads incremental encoder 1 resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of incremental encoder 1.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        resolution = self.mc.communication.get_register(
            "FBK_DIGENC1_RESOLUTION", servo=servo, axis=axis
        )
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_digital_halls_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads digital halls pole pairs in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of digital halls encoder.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        pair_poles = self.mc.communication.get_register(
            "FBK_DIGHALL_PAIRPOLES", servo=servo, axis=axis
        )
        resolution = 6 * pair_poles
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_secondary_ssi_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads secondary SSI encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of secondary SSI encoder.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        secondary_single_turn_bits = self.mc.communication.get_register(
            "FBK_SSI2_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(secondary_single_turn_bits, int):
            raise TypeError("Resolution value has to be an integer")
        resolution = int(2**secondary_single_turn_bits)
        return resolution

    def get_absolute_encoder_2_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads ABS2 encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of ABS2 encoder.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        serial_slave_1_single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS2_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(serial_slave_1_single_turn_bits, int):
            raise TypeError("Single-turn bits has to be an integer")
        resolution = int(2**serial_slave_1_single_turn_bits)
        return resolution

    def get_incremental_encoder_2_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads incremental encoder 2 resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of incremental encoder 2 encoder.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        resolution = self.mc.communication.get_register(
            "FBK_DIGENC2_RESOLUTION", servo=servo, axis=axis
        )
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def __no_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Used for feedbacks that has no resolution.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            ValueError: Selected feedback does not have resolution
        """
        raise ValueError("Selected feedback does not have resolution")

    def get_feedback_resolution(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads target feedback resolution in the target servo and axis.

        Args:
            feedback : target feedback.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of target feedback.
        """
        return self.feedback_resolution_functions[feedback](servo, axis)
