from .wizard_tests.feedback_test import Feedbacks
from .wizard_tests.phase_calibration import Phasing


class DriveTests:

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def digital_halls_test(self, servo="default", subnode=1, apply_changes=True):
        return self.feedback_test(Feedbacks.SensorType.HALLS, servo, subnode, apply_changes)

    def incremental_encoder_1_test(self, servo="default", subnode=1, apply_changes=True):
        return self.feedback_test(Feedbacks.SensorType.QEI, servo, subnode, apply_changes)

    def incremental_encoder_2_test(self, servo="default", subnode=1, apply_changes=True):
        return self.feedback_test(Feedbacks.SensorType.QEI2, servo, subnode, apply_changes)

    def feedback_test(self, feedback, servo="default", subnode=1, apply_changes=True):
        feedbacks_test = Feedbacks(self.mc.servos[servo], subnode, feedback)
        output = feedbacks_test.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.servos[servo].raw_write(key, value, subnode=subnode)
        return output

    def commutation(self, servo="default", subnode=1, apply_changes=True):
        commutation = Phasing(self.mc.servos[servo], subnode)
        output = commutation.run()
        if apply_changes:
            for key, value in output["suggested_registers"].items():
                self.mc.servos[servo].raw_write(key, value, subnode=subnode)
        return output
