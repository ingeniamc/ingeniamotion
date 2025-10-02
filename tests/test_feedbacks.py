import pytest

from ingeniamotion.enums import SensorCategory, SensorType

COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"
PAIR_POLES_REGISTER = "FBK_DIGHALL_PAIRPOLES"
INCREMENTAL_RESOLUTION_2_REGISTER = "FBK_DIGENC2_RESOLUTION"
INCREMENTAL_RESOLUTION_1_REGISTER = "FBK_DIGENC1_RESOLUTION"
ABS1_1_SINGLE_TURN_REGISTER = "FBK_BISS1_SSI1_POS_ST_BITS"
ABS1_2_SINGLE_TURN_REGISTER = "FBK_BISS2_POS_ST_BITS"
ABS2_1_SINGLE_TURN_REGISTER = "FBK_SSI2_POS_ST_BITS"

SENSOR_TYPE_AND_CATEGORY = [
    (SensorType.ABS1, SensorCategory.ABSOLUTE),
    (SensorType.QEI, SensorCategory.INCREMENTAL),
    (SensorType.HALLS, SensorCategory.ABSOLUTE),
    (SensorType.SSI2, SensorCategory.ABSOLUTE),
    (SensorType.BISSC2, SensorCategory.ABSOLUTE),
    (SensorType.QEI2, SensorCategory.INCREMENTAL),
    (SensorType.INTGEN, SensorCategory.ABSOLUTE),
]


ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES = [(22, 4194304), (10, 1024), (15, 32768)]

INCREMENTAL_ENCODER_RESOLUTION_TEST_VALUES = [1000, 4000, 6000]


@pytest.fixture
def restore_resolution_registers(mc, alias):
    registers = [
        PAIR_POLES_REGISTER,
        INCREMENTAL_RESOLUTION_1_REGISTER,
        INCREMENTAL_RESOLUTION_2_REGISTER,
        ABS1_1_SINGLE_TURN_REGISTER,
        ABS1_2_SINGLE_TURN_REGISTER,
        ABS2_1_SINGLE_TURN_REGISTER,
    ]
    registers_values = [
        mc.communication.get_register(register, servo=alias)
        if mc.info.register_exists(register, servo=alias)
        else None
        for register in registers
    ]
    yield
    for register, register_value in zip(registers, registers_values):
        if register_value is not None:
            mc.communication.set_register(register, register_value, servo=alias)


def skip_if_qei2_is_not_available(mc, alias, sensor=SensorType.QEI2):
    if sensor == SensorType.QEI2 and not mc.info.register_exists(
        INCREMENTAL_RESOLUTION_2_REGISTER, servo=alias
    ):
        pytest.skip("Incremental encoder 2 is not available")


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_commutation_feedback(mc, alias, sensor):
    mc.communication.set_register(COMMUTATION_FEEDBACK_REGISTER, sensor, servo=alias)
    test_feedback = mc.configuration.get_commutation_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_commutation_feedback(mc, alias, sensor):
    mc.configuration.set_commutation_feedback(sensor, servo=alias)
    register_value = mc.communication.get_register(COMMUTATION_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_commutation_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_commutation_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_commutation_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_commutation_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    mc.communication.set_register(COMMUTATION_FEEDBACK_REGISTER, sensor, servo=alias)
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_commutation_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_commutation_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_reference_feedback(mc, alias, sensor):
    mc.communication.set_register(REFERENCE_FEEDBACK_REGISTER, sensor, servo=alias)
    test_feedback = mc.configuration.get_reference_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_reference_feedback(mc, alias, sensor):
    mc.configuration.set_reference_feedback(sensor, servo=alias)
    register_value = mc.communication.get_register(REFERENCE_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_reference_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_commutation_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_commutation_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_reference_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    mc.communication.set_register(REFERENCE_FEEDBACK_REGISTER, sensor, servo=alias)
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_reference_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_reference_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_velocity_feedback(mc, alias, sensor):
    mc.communication.set_register(VELOCITY_FEEDBACK_REGISTER, sensor, servo=alias)
    test_feedback = mc.configuration.get_velocity_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_velocity_feedback(mc, alias, sensor):
    mc.configuration.set_velocity_feedback(sensor, servo=alias)
    register_value = mc.communication.get_register(VELOCITY_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_velocity_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_velocity_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_velocity_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_velocity_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    mc.communication.set_register(VELOCITY_FEEDBACK_REGISTER, sensor, servo=alias)
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_velocity_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_velocity_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_position_feedback(mc, alias, sensor):
    mc.communication.set_register(POSITION_FEEDBACK_REGISTER, sensor, servo=alias)
    test_feedback = mc.configuration.get_position_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_position_feedback(mc, alias, sensor):
    mc.configuration.set_position_feedback(sensor, servo=alias)
    register_value = mc.communication.get_register(POSITION_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_position_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_position_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_position_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_position_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    mc.communication.set_register(POSITION_FEEDBACK_REGISTER, sensor, servo=alias)
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_position_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_position_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize(
    "sensor",
    [
        SensorType.ABS1,
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.SSI2,
        SensorType.BISSC2,
        SensorType.QEI2,
    ],
)
def test_get_auxiliar_feedback(mc, alias, sensor):
    mc.communication.set_register(AUXILIAR_FEEDBACK_REGISTER, sensor, servo=alias)
    test_feedback = mc.configuration.get_auxiliar_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize(
    "sensor",
    [
        SensorType.ABS1,
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.SSI2,
        SensorType.BISSC2,
        SensorType.QEI2,
    ],
)
def test_set_auxiliar_feedback(mc, alias, sensor):
    mc.configuration.set_auxiliar_feedback(sensor, servo=alias)
    register_value = mc.communication.get_register(AUXILIAR_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize(
    "sensor, category",
    [
        (SensorType.ABS1, SensorCategory.ABSOLUTE),
        (SensorType.QEI, SensorCategory.INCREMENTAL),
        (SensorType.HALLS, SensorCategory.ABSOLUTE),
        (SensorType.SSI2, SensorCategory.ABSOLUTE),
        (SensorType.BISSC2, SensorCategory.ABSOLUTE),
        (SensorType.QEI2, SensorCategory.INCREMENTAL),
    ],
)
def test_get_auxiliar_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_auxiliar_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_auxiliar_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.usefixtures("clean_and_restore_feedbacks")
@pytest.mark.parametrize(
    "sensor",
    [
        SensorType.ABS1,
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.SSI2,
        SensorType.BISSC2,
        SensorType.QEI2,
    ],
)
def test_get_auxiliar_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    mc.communication.set_register(AUXILIAR_FEEDBACK_REGISTER, sensor, servo=alias)
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_auxiliar_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_auxiliar_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_absolute_encoder_1_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS1_1_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_absolute_encoder_1_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("resolution", INCREMENTAL_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_incremental_encoder_1_resolution(mc, alias, resolution):
    mc.communication.set_register(INCREMENTAL_RESOLUTION_1_REGISTER, resolution, servo=alias)
    test_res = mc.configuration.get_incremental_encoder_1_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("pair_poles, resolution", [(1, 6), (10, 60), (4, 24)])
def test_get_digital_halls_resolution(mc, alias, pair_poles, resolution):
    mc.communication.set_register(PAIR_POLES_REGISTER, pair_poles, servo=alias)
    test_res = mc.configuration.get_digital_halls_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_secondary_ssi_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS2_1_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_secondary_ssi_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_absolute_encoder_2_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS1_2_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_absolute_encoder_2_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize("resolution", INCREMENTAL_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_incremental_encoder_2_resolution(mc, alias, resolution):
    skip_if_qei2_is_not_available(mc, alias)
    mc.communication.set_register(INCREMENTAL_RESOLUTION_2_REGISTER, resolution, servo=alias)
    test_res = mc.configuration.get_incremental_encoder_2_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
def test_instance_sensor_type(mc, alias):
    test_feedback = mc.configuration.get_commutation_feedback(servo=alias)
    assert isinstance(test_feedback, SensorType)


@pytest.mark.virtual
@pytest.mark.parametrize(
    "sensor, register",
    [
        (SensorType.ABS1, "FBK_BISS1_SSI1_POS_POLARITY"),
        (SensorType.QEI, "FBK_DIGENC1_POLARITY"),
        (SensorType.HALLS, "FBK_DIGHALL_POLARITY"),
        (SensorType.SSI2, "FBK_SSI2_POS_POLARITY"),
        (SensorType.BISSC2, "FBK_BISS2_POS_POLARITY"),
        (SensorType.QEI2, "FBK_DIGENC2_POLARITY"),
    ],
)
def test_get_feedback_polarity_register_uid(mc, sensor, register):
    assert mc.configuration.get_feedback_polarity_register_uid(sensor) == register
