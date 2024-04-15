from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType


def use_only_incremental_encoders(mc: MotionController):
    """All feedbacks are using an Incremental encoder.

    Args:
        mc: Controller to configure the type of encoder for each feedback

    """
    mc.configuration.set_auxiliar_feedback(SensorType.QEI)
    mc.configuration.set_commutation_feedback(SensorType.QEI)
    mc.configuration.set_position_feedback(SensorType.QEI)
    mc.configuration.set_velocity_feedback(SensorType.QEI)
    mc.configuration.set_reference_feedback(SensorType.QEI)


def use_only_absolute_encoders(mc: MotionController):
    """All feedbacks are using an Absolute encoder.

    Args:
        mc: Controller to configure the type of encoder for each feedback

    """
    mc.configuration.set_auxiliar_feedback(SensorType.ABS1)
    mc.configuration.set_commutation_feedback(SensorType.ABS1)
    mc.configuration.set_position_feedback(SensorType.ABS1)
    mc.configuration.set_velocity_feedback(SensorType.ABS1)
    mc.configuration.set_reference_feedback(SensorType.ABS1)


def use_incremental_encoders_and_digital_halls(mc: MotionController):
    """All feedbacks are using an incremental encoder and a digital halls.

    Args:
        mc: Controller to configure the type of encoder for each feedback

    """
    mc.configuration.set_auxiliar_feedback(SensorType.HALLS)
    mc.configuration.set_commutation_feedback(SensorType.QEI)
    mc.configuration.set_position_feedback(SensorType.HALLS)
    mc.configuration.set_velocity_feedback(SensorType.QEI)
    mc.configuration.set_reference_feedback(SensorType.QEI)


def main() -> None:
    mc = MotionController()

    interface_index = 3
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.5.1\\cap-net-e_eoe_2.5.1.xdf"
    )
    mc.communication.connect_servo_ethercat_interface_index(
        interface_index, slave_id, dictionary_path
    )

    # Feedbacks configuration:
    # Indicate the type of encoder you are using for each feedback
    # There are some examples of feedbacks configuration below.
    # Uncomment the configuration you want to try:
    # -------------------------------------------------------------
    # use_only_incremental_encoders(mc)
    # use_only_absolute_encoders(mc)
    use_incremental_encoders_and_digital_halls(mc)
    # -------------------------------------------------------------

    # Run Commutation test
    result = mc.tests.commutation()
    print(f"Commutation Result: {result['result_message']}")

    mc.communication.disconnect()


if __name__ == "__main__":
    main()
