from .feedback_test import Feedbacks
from .base_test import BaseTest
from ingeniamotion.enums import SensorType


class AbsoluteEncoder2(Feedbacks):
    def __init__(self, mc, servo, axis):
        super().__init__()
        self.sensor = SensorType.BISSC2

    @BaseTest.stoppable
    def feedback_setting(self):
        # First set all feedback to feedback in test, so there won't be
        # more than 5 feedback at the same time
        self.mc.configuration.set_commutation_feedback(self.sensor,
                                                       servo=self.servo,
                                                       axis=self.axis)
        self.mc.configuration.set_reference_feedback(self.sensor,
                                                     servo=self.servo,
                                                     axis=self.axis)
        self.mc.configuration.set_velocity_feedback(self.sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        self.mc.configuration.set_position_feedback(self.sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        auxiliary_sensor = SensorType.ABS1
        self.mc.configuration.set_auxiliar_feedback(auxiliary_sensor,
                                                    servo=self.servo,
                                                    axis=self.axis)
        # Set Polarity to 0
        polarity_register = self.__feedbacks_polarity_register[self.sensor]
        self.mc.communication.set_register(
            polarity_register, self.Polarity.NORMAL,
            servo=self.servo, axis=self.axis
        )
        # Depending on the type of the feedback, calculate the correct
        # feedback resolution
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )
