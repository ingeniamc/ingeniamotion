import ingenialogger

from .enums import SensorType, SeverityLevel
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import AbsoluteEncoder1
from ingeniamotion.wizard_tests.feedbacks_tests.internal_generator_test import InternalGenerator
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import DigitalIncremental1
from ingeniamotion.wizard_tests.feedbacks_tests.digital_hall_test import DigitalHall
from ingeniamotion.wizard_tests.feedbacks_tests.secondary_ssi_test import SecondarySSI
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import AbsoluteEncoder2
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental2_test import DigitalIncremental2
from ingeniamotion.wizard_tests.feedbacks_tests.smo_test import SMO
from .wizard_tests.phase_calibration import Phasing
from .wizard_tests.phasing_check import PhasingCheck
from .wizard_tests.sto import STOTest
from .wizard_tests.brake import Brake
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class DriveTests(metaclass=MCMetaClass):

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def digital_halls_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                           apply_changes=True):
        """Executes the digital halls feedback test given a target servo and
        axis. By default test will make changes in some drive registers like
        feedback polarity and others suggested registers. To avoid it, set
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

    def incremental_encoder_1_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                   apply_changes=True):
        """Executes the incremental encoder 1 feedback test given a target servo
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

    def incremental_encoder_2_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                   apply_changes=True):
        """Executes incremental encoder 2 feedback test given a target servo
        and axis. By default test will make changes in some drive registers
        like feedback polarity and other suggested registers. To avoid it,
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

    def absolute_encoder_1_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                apply_changes=True):
        """Executes absolute encoder 1 feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.ABS1, servo, axis, apply_changes)

    def absolute_encoder_2_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                                apply_changes=True):
        """Executes absolute encoder 2 feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.BISSC2, servo, axis, apply_changes)

    def secondary_ssi_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                           apply_changes=True):
        """ Executes secondary SSI feedback test given a target servo and axis.
        To know more about it see :func:`digital_halls_test`.
        """
        return self.__feedback_test(SensorType.BISSC2, servo, axis, apply_changes)

    def __feedback_test(self, feedback, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                        apply_changes=True):
        if feedback == SensorType.ABS1:
            feedbacks_test = AbsoluteEncoder1(self.mc, servo, axis)
        elif feedback == SensorType.INTGEN:
            feedbacks_test = InternalGenerator(self.mc, servo, axis)
        elif feedback == SensorType.QEI:
            feedbacks_test = DigitalIncremental1(self.mc, servo, axis)
        elif feedback == SensorType.HALLS:
            feedbacks_test = DigitalHall(self.mc, servo, axis)
        elif feedback == SensorType.SSI2:
            feedbacks_test = SecondarySSI(self.mc, servo, axis)
        elif feedback == SensorType.BISSC2:
            feedbacks_test = AbsoluteEncoder2(self.mc, servo, axis)
        elif feedback == SensorType.QEI2:
            feedbacks_test = DigitalIncremental2(self.mc, servo, axis)
        elif feedback == SensorType.SMO:
            feedbacks_test = SMO(self.mc, servo, axis)
        else:
            feedbacks_test = Feedbacks(self.mc, servo, axis, feedback)
        output = feedbacks_test.run()
        if (apply_changes and
                output["result_severity"] == SeverityLevel.SUCCESS):
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value,
                                                   servo=servo, axis=axis)
            self.logger.debug("Feedback test changes applied", axis=axis,
                              drive=self.mc.servo_name(servo))
        return output

    def commutation(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                    apply_changes=True):
        """Executes a commutation calibration given a target servo and axis.
        By default commutation will make changes in some drive registers
        like commutation angle offset and other suggested registers.
        To avoid it, set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the
                servo, if ``False`` it does not. ``True`` by default.

        Returns:
            dict: Dictionary with the result of the test::

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
        if (apply_changes and
                output["result_severity"] == SeverityLevel.SUCCESS):
            for key, value in output["suggested_registers"].items():
                self.mc.communication.set_register(key, value, servo=servo,
                                                   axis=axis)
            self.logger.debug("Commutation changes applied", axis=axis,
                              drive=self.mc.servo_name(servo))
        return output

    def phasing_check(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Checks servo phasing.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.

        Returns:
            dict: Dictionary with the result of the test::

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

    def sto_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Check STO

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.

        Returns:
            dict: Dictionary with the result of the test::

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

    def brake_test(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Run brake test.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. ``1`` by default.

        Returns:
            Brake: Instance of Brake test. Call ``Brake.finish()`` to end the test.
        """
        brake_test = Brake(self.mc, servo, axis)
        brake_test.run()
        return brake_test
