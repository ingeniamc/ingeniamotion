from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType


def set_feedbacks(mc: MotionController):
    """Feedbacks configuration.

    All feedbacks can be set either the same encoder or different encoders.
    In this example we are using an Incremental Encoder (SensorType.QEI) and
    a Digital Halls (SensorType.HALLS).

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

    interface_ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = "test_directory/dictionary_file.xdf"
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dictionary_path)

    set_feedbacks(mc)
    # -------------------------------------------------------------

    # Run Commutation test
    result = mc.tests.commutation()
    print(f"Commutation Result: {result['result_message']} - {result['result_severity']}")

    mc.communication.disconnect()


if __name__ == "__main__":
    main()
