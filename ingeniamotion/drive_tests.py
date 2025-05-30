from typing import TYPE_CHECKING, Optional, Union

import ingenialogger

from ingeniamotion.enums import SensorType, SeverityLevel

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.wizard_tests.brake import Brake
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import AbsoluteEncoder1Test
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import AbsoluteEncoder2Test
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_polarity_test import (
    DCFeedbacksPolarityTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_resolution_test import (
    DCFeedbacksResolutionTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_hall_test import DigitalHallTest
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental2_test import (
    DigitalIncremental2Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.wizard_tests.feedbacks_tests.secondary_ssi_test import SecondarySSITest
from ingeniamotion.wizard_tests.feedbacks_tests.sincos_encoder_test import SinCosEncoderTest
from ingeniamotion.wizard_tests.phase_calibration import Phasing
from ingeniamotion.wizard_tests.phasing_check import PhasingCheck
from ingeniamotion.wizard_tests.sto import STOTest


class DriveTests:
    """Class that contain the tests that can be performed on a drive."""

    __sensors = {
        SensorType.ABS1: AbsoluteEncoder1Test,
        SensorType.QEI: DigitalIncremental1Test,
        SensorType.HALLS: DigitalHallTest,
        SensorType.SSI2: SecondarySSITest,
        SensorType.BISSC2: AbsoluteEncoder2Test,
        SensorType.QEI2: DigitalIncremental2Test,
        SensorType.SINCOS: SinCosEncoderTest,
    }

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def digital_halls_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the digital halls test.

        Executes the digital halls feedback test given a target servo and
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
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the incremental encoder 1 test.

        Executes the incremental encoder 1 feedback test given a target servo
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
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Executes incremental encoder 2 feedback test given a target servo and axis.

        By default test will make changes in some drive registers
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
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Executes absolute encoder 1 feedback test given a target servo and axis.

        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.ABS1, servo, axis, apply_changes)

    def absolute_encoder_2_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Executes absolute encoder 2 feedback test given a target servo and axis.

        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.BISSC2, servo, axis, apply_changes)

    def secondary_ssi_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Executes secondary SSI feedback test given a target servo and axis.

        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.SSI2, servo, axis, apply_changes)

    def sincos_encoder_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the SinCos encoder test.

        Executes the SinCos feedback test given a target servo
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
                        {"FBK_SINCOS_POLARITY": 0},
                    # (str) Human readable result message
                    "result_message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(SensorType.SINCOS, servo, axis, apply_changes)

    def __get_feedback_test(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Feedbacks:
        return self.__sensors[feedback](self.mc, servo, axis)

    def __feedback_test(
        self,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        apply_changes: bool = True,
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        output = self.__get_feedback_test(feedback, servo, axis).run()
        if (
            apply_changes
            and output is not None
            and output["result_severity"] == SeverityLevel.SUCCESS
        ):
            if not isinstance(output["suggested_registers"], dict):
                raise TypeError("Suggested registers has to be a dictionary")
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo, axis=axis)
            self.logger.debug(
                "Feedback test changes applied", axis=axis, drive=self.mc.servo_name(servo)
            )
        return output

    def commutation(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, apply_changes: bool = True
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the commutation calibration test.

        Executes a commutation calibration given a target servo and axis.
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
            TypeError: If some parameter has a wrong type.
        """
        commutation = Phasing(self.mc, servo, axis)
        output = commutation.run()
        if (
            apply_changes
            and output is not None
            and output["result_severity"] == SeverityLevel.SUCCESS
        ):
            if not isinstance(output["suggested_registers"], dict):
                raise TypeError("Suggested registers have to be a dictionary")
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo, axis=axis)
            self.logger.debug(
                "Commutation changes applied", axis=axis, drive=self.mc.servo_name(servo)
            )
        return output

    def phasing_check(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Checks servo phasing.

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

    def sto_test(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Check STO.

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
        """Run brake test.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Instance of Brake test. Call ``Brake.finish()`` to end the test.
        """
        brake_test = Brake(self.mc, servo, axis)
        brake_test.run()
        return brake_test

    def polarity_feedback_single_phase_test(
        self,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        apply_changes: bool = True,
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the polarity feedback single phase test.

        Executes polarity feedback test for single phase motors given a target servo
        and axis. By default, test will make changes in feedback polarity. To avoid it,
        set ``apply_changes`` to ``False``.

        Args:
            feedback: feedback sensor type
            servo: servo alias to reference it. ``default`` by default.
            axis: axis that will run the test. ``1`` by default.
            apply_changes: if ``True``, test applies changes to the
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
            TypeError: If some parameter has a wrong type.
        """
        dc_feedback_polarity_test = DCFeedbacksPolarityTest(self.mc, feedback, servo, axis)
        output = dc_feedback_polarity_test.run()
        if (
            apply_changes
            and output is not None
            and output["result_severity"] == SeverityLevel.SUCCESS
        ):
            if not isinstance(output["suggested_registers"], dict):
                raise TypeError("Suggested registers have to be a dictionary")
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo, axis=axis)
            self.logger.debug(
                "Single phase feedback polarity test changes applied",
                axis=axis,
                drive=self.mc.servo_name(servo),
            )
        return output

    def resolution_feedback_single_phase_test(
        self,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        kp: Optional[float] = None,
        ki: Optional[float] = None,
        kd: Optional[float] = None,
    ) -> Optional[dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]]:
        """Run the resolution feedback single phase test.

        Executes resolution feedback test for single phase motors given a target servo
        and axis. This test needs a human check to ensure the feedback is well configured.
        The test will move the motor with the number of counts set in the feedback resolution,
        if the motor does not move exactly one revolution this means that
        the feedback is not configured correctly.

        Args:
            feedback: feedback sensor type
            servo: servo alias to reference it. ``default`` by default.
            axis: axis that will run the test. ``1`` by default.
            kp: overrides test velocity Kp. If ``None`` use test default Kp value.
                At the end of the test initial drive value is restored.
            ki: if ki is ``None`` is ignored, overrides test velocity Ki.
                If ``None`` use test default Ki value.
                At the end of the test initial drive value is restored.
            kd: if kd is ``None`` is ignored, overrides test velocity Kd.
                If ``None`` use test default Kd value.
                At the end of the test initial drive value is restored.

        Returns:
            Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result_severity": 0,
                    # (str) Human readable result message
                    "result_message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        dc_feedback_resolution_test = DCFeedbacksResolutionTest(
            self.mc, feedback, servo, axis, kp=kp, ki=ki, kd=kd
        )
        return dc_feedback_resolution_test.run()
