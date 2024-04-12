from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType


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
    
    # Encoder configuration
    # If you are using only one encoder (e.g.: Incremental Encoder), set the type of sensors
    # using the sensor_type variable below.
    # If you are using more than one encoder (e.g.: Inc. Enc. and Abs. Enc.), set the type of 
    # sensors one by one.
    sensor_type = SensorType.QEI 
    mc.configuration.set_auxiliar_feedback(sensor_type)
    mc.configuration.set_commutation_feedback(sensor_type)
    mc.configuration.set_position_feedback(sensor_type)
    mc.configuration.set_velocity_feedback(sensor_type)
    mc.configuration.set_reference_feedback(sensor_type)
    
    # Run Commutation test
    result = mc.tests.commutation()
    print(result["result_message"])

    mc.communication.disconnect()


if __name__ == "__main__":
    # Before executing this example, make sure your motor is calibrated.
    main()
