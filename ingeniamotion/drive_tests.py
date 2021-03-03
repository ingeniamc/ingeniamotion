from .wizard_tests.feedback_test import Feedbacks
from .wizard_tests.phase_calibration import Phasing


class DriveTests:

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def digital_halls_test(self, servo="default", subnode=1, apply_changes=True):
        """
        Pass digital halls feedback test to a target servo and axis.
        By default test will make changes in some drive registers as feedback polarity and more suggested change.
        To avoid it set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the servo, if ``False`` it does not.
                ``True`` by default.

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
            TestError: If servo or setup configuration makes impossible complete the test
        """
        return self.__feedback_test(Feedbacks.SensorType.HALLS, servo, subnode, apply_changes)

    def incremental_encoder_1_test(self, servo="default", subnode=1, apply_changes=True):
        """
        Pass incremental encoder 1 feedback test to a target servo and axis.
        By default test will make changes in some drive registers as feedback polarity and more suggested change.
        To avoid it set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the servo, if ``False`` it does not.
                ``True`` by default.

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
            TestError: If servo or setup configuration makes impossible complete the test
        """
        return self.__feedback_test(Feedbacks.SensorType.QEI, servo, subnode, apply_changes)

    def incremental_encoder_2_test(self, servo="default", subnode=1, apply_changes=True):
        """
        Pass incremental encoder 2 feedback test to a target servo and axis.
        By default test will make changes in some drive registers as feedback polarity and more suggested change.
        To avoid it set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the servo, if ``False`` it does not.
                ``True`` by default.

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
            TestError: If servo or setup configuration makes impossible complete the test
        """
        return self.__feedback_test(Feedbacks.SensorType.QEI2, servo, subnode, apply_changes)

    def __feedback_test(self, feedback, servo="default", subnode=1, apply_changes=True):
        feedbacks_test = Feedbacks(self.mc.servos[servo], subnode, feedback)
        output = feedbacks_test.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.servos[servo].raw_write(key, value, subnode=subnode)
        return output

    def commutation(self, servo="default", subnode=1, apply_changes=True):
        """
        Commutation calibration to a target servo and axis.
        By default commutation will make changes in some drive registers as commutation angle offset and
        more suggested change. To avoid it set ``apply_changes`` to ``False``.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. ``1`` by default.
            apply_changes (bool): if ``True``, test applies changes to the servo, if ``False`` it does not.
                ``True`` by default.

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
            TestError: If servo or setup configuration makes impossible complete the calibration
        """
        commutation = Phasing(self.mc.servos[servo], subnode)
        output = commutation.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.servos[servo].raw_write(key, value, subnode=subnode)
        return output
