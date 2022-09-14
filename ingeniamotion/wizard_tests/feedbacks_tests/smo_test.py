from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.enums import SensorType


class SMO(Feedbacks):
    BACKUP_REGISTERS_SMO = []

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.SMO

    def __init__(self, mc, servo, axis):
        super().__init__(mc, servo, axis, SensorType.SMO)
        self.backup_registers_names += self.BACKUP_REGISTERS_SMO
