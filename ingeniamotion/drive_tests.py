import ingenialogger

from .enums import SensorType, SeverityLevel
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import AbsoluteEncoder1Test
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_hall_test import DigitalHallTest
from ingeniamotion.wizard_tests.feedbacks_tests.secondary_ssi_test import SecondarySSITest
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import AbsoluteEncoder2Test
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental2_test import (
    DigitalIncremental2Test,
)
from .wizard_tests.phase_calibration import Phasing
from .wizard_tests.phasing_check import PhasingCheck
from .wizard_tests.sto import STOTest
from .wizard_tests.brake import Brake
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class DriveTests(metaclass=MCMetaClass):
    __sensors = {
        SensorType.ABS1: AbsoluteEncoder1Test,
        SensorType.QEI: DigitalIncremental1Test,
        SensorType.HALLS: DigitalHallTest,
        SensorType.SSI2: SecondarySSITest,
        SensorType.BISSC2: AbsoluteEncoder2Test,
        SensorType.QEI2: DigitalIncremental2Test,
    }

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def digital_halls_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes the digital halls feedback test given a target servo and
        axis. By default test will make changes in some drive registers like
        feedback polarity and others suggested registers. To avoid it, set
        ``apply_changes`` to ``False``.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.
            apply_changes : if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGHALL_POLARITY": 0},
                    # (str) Human readable result message
                    "result_message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(SensorType.HALLS, servo, axis, apply_changes)

    def incremental_encoder_1_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes the incremental encoder 1 feedback test given a target servo
        and axis. By default test will make changes in some drive registers
        like feedback polarity and other suggested registers. To avoid it, set
        ``apply_changes`` to ``False``.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.
            apply_changes : if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGENC1_POLARITY": 0},
                    # (str) Human readable result message
                    "result_message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(SensorType.QEI, servo, axis, apply_changes)

    def incremental_encoder_2_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes incremental encoder 2 feedback test given a target servo
        and axis. By default test will make changes in some drive registers
        like feedback polarity and other suggested registers. To avoid it,
        set ``apply_changes`` to ``False``.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.
            apply_changes : if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGENC2_POLARITY": 0},
                    # (str) Human readable result message
                    "result_message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(SensorType.QEI2, servo, axis, apply_changes)

    def absolute_encoder_1_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes absolute encoder 1 feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.ABS1, servo, axis, apply_changes)

    def absolute_encoder_2_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes absolute encoder 2 feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.BISSC2, servo, axis, apply_changes)

    def secondary_ssi_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes secondary SSI feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.SSI2, servo, axis, apply_changes)

    def get_feedback_test(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Feedbacks:
        return self.__sensors[feedback](self.mc, servo, axis)

    def __feedback_test(
        self,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        apply_changes: bool = True,
    ) -> dict:
        output = self.get_feedback_test(feedback, servo, axis).run()
        if apply_changes and output["result_severity"] == SeverityLevel.SUCCESS:
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo, axis=axis)
            self.logger.debug(
                "Feedback test changes applied", axis=axis, drive=self.mc.servo_name(servo)
            )
        return output

    def commutation(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> dict:
        """Executes a commutation calibration given a target servo and axis.
        By default commutation will make changes in some drive registers
        like commutation angle offset and other suggested registers.
        To avoid it, set ``apply_changes`` to ``False``.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.
            apply_changes : if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"COMMU_ANGLE_OFFSET": 0.12},
                    # (str) Human readable result message
                    "result_message": "Phasing process finished successfully"
                }

        Raises:
            TestError: If servo or setup configuration makes impossible
                complete the calibration.
        """
        commutation = Phasing(self.mc, servo, axis)
        output = commutation.run()
        if apply_changes and output["result_severity"] == SeverityLevel.SUCCESS:
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo, axis=axis)
            self.logger.debug(
                "Commutation changes applied", axis=axis, drive=self.mc.servo_name(servo)
            )
        return output

    def phasing_check(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> dict:
        """
        Checks servo phasing.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers": {},
                    # (str) Human readable result message
                    "result_message": "Phasing process finished successfully"
                }
        """
        phasing_check = PhasingCheck(self.mc, servo, axis)
        return phasing_check.run()

    def sto_test(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> dict:
        """
        Check STO

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (dict) Suggested register values
                    "suggested_registers": {},
                    # (str) Human readable result message
                    "result_message": "Phasing process finished successfully"
                }
        """
        sto_test = STOTest(self.mc, servo, axis)
        return sto_test.run()

    def brake_test(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> Brake:
        """
        Run brake test.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Instance of Brake test. Call ``Brake.finish()`` to end the test.
        """
        brake_test = Brake(self.mc, servo, axis)
        brake_test.run()
        return brake_test
