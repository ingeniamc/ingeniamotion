import ingenialogger

from .wizard_tests.feedback_test import Feedbacks
from .wizard_tests.phase_calibration import Phasing
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class DriveTests(metaclass=MCMetaClass):

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def digital_halls_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                           apply_changes=True):
        """
        Executes the digital halls feedback test given a target servo and
        axis. By default test will make changes in some drive registers like
        feedback polarity and others suggested registers. To avoid it, set
        ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the
                servo , if ``False`` it does not. ``True`` by default.

        Returns:
            dict: Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGHALL_POLARITY": 0},
                    # (str) Human readable result message
                    "message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(Feedbacks.SensorType.HALLS, servo, axis,
                                    apply_changes)

    def incremental_encoder_1_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                   apply_changes=True):
        """
        Executes the incremental encoder 1 feedback test given a target servo
        and axis. By default test will make changes in some drive registers
        like feedback polarity and other suggested registers. To avoid it, set
        ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            dict: Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGENC1_POLARITY": 0},
                    # (str) Human readable result message
                    "message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible  fulfilling the test.
        """
        return self.__feedback_test(Feedbacks.SensorType.QEI, servo,
                                    axis, apply_changes)

    def incremental_encoder_2_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                   apply_changes=True):
        """
        Executes incremental encoder 2 feedback test given a target servo
        and axis. By default test will make changes in some drive registers
        like feedback polarity and other suggested registers. To avoid it,
        set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the servo
                , if ``False`` it does not. ``True`` by default.

        Returns:
            dict: Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"FBK_DIGENC2_POLARITY": 0},
                    # (str) Human readable result message
                    "message": "Feedback test pass successfully"
                }

        Raises:
            TestError: In case the servo or setup configuration makes
                impossible fulfilling the test
        """
        return self.__feedback_test(Feedbacks.SensorType.QEI2, servo, axis,
                                    apply_changes)

    def __feedback_test(self, feedback, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                        apply_changes=True):
        feedbacks_test = Feedbacks(self.mc.servos[servo], axis, feedback)
        output = feedbacks_test.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value,
                                                   servo=servo, axis=axis)
            self.logger.debug("Feedback test changes applied", axis=axis,
                              drive=self.mc.servo_name(servo))
        return output

    def commutation(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                    apply_changes=True):
        """
        Executes a commutation calibration given a target servo and axis.
        By default commutation will make changes in some drive registers like
        commutation angle offset and other suggested registers. To avoid it,
        set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            dict: Dictionary with the result of the test::

                {
                    # (int) Result code
                    "result": 0,
                    # (dict) Suggested register values
                    "suggested_registers":
                        {"COMMU_ANGLE_OFFSET": 0.12},
                    # (str) Human readable result message
                    "message": "Phasing process finished successfully"
                }

        Raises:
            TestError: If servo or setup configuration makes impossible
                complete the calibration.
        """
        commutation = Phasing(self.mc.servos[servo], axis)
        output = commutation.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo,
                                                   axis=axis)
            self.logger.debug("Commutation changes applied", axis=axis,
                              drive=self.mc.servo_name(servo))
        return output
