from typing import TYPE_CHECKING

import pytest
from ingenialink import exceptions

from ingeniamotion.enums import FeedbackPolarity, SensorCategory, SensorType
from ingeniamotion.feedbacks import MAX_SIMULTANEOUS_FEEDBACKS, FeedbacksConfiguration

if TYPE_CHECKING:
    from ingeniamotion.axis import Axis

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


def skip_if_qei2_is_not_available(mc, alias, sensor=SensorType.QEI2):
    if sensor == SensorType.QEI2 and not mc.info.register_exists(
        INCREMENTAL_RESOLUTION_2_REGISTER, servo=alias
    ):
        pytest.skip("Incremental encoder 2 is not available")


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_commutation_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(
        COMMUTATION_FEEDBACK_REGISTER, servo=alias
    ).enums.values()
    try:
        mc.communication.set_register(COMMUTATION_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    test_feedback = mc.configuration.get_commutation_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_commutation_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(
        COMMUTATION_FEEDBACK_REGISTER, servo=alias
    ).enums.values()
    try:
        mc.configuration.set_commutation_feedback(sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    register_value = mc.communication.get_register(COMMUTATION_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_commutation_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_commutation_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_commutation_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_commutation_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    register_values = mc.info.register_info(
        COMMUTATION_FEEDBACK_REGISTER, servo=alias
    ).enums.values()
    try:
        mc.communication.set_register(COMMUTATION_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_commutation_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_commutation_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_reference_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(REFERENCE_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(REFERENCE_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    test_feedback = mc.configuration.get_reference_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_reference_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(REFERENCE_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.configuration.set_reference_feedback(sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    register_value = mc.communication.get_register(REFERENCE_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_reference_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_reference_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_reference_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_reference_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    register_values = mc.info.register_info(REFERENCE_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(REFERENCE_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_reference_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_reference_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_velocity_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(VELOCITY_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(VELOCITY_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    test_feedback = mc.configuration.get_velocity_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_velocity_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(VELOCITY_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.configuration.set_velocity_feedback(sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    register_value = mc.communication.get_register(VELOCITY_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_velocity_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_velocity_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_velocity_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_velocity_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    register_values = mc.info.register_info(VELOCITY_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(VELOCITY_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_velocity_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_velocity_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_position_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(POSITION_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(POSITION_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    test_feedback = mc.configuration.get_position_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_set_position_feedback(mc, alias, sensor):
    register_values = mc.info.register_info(POSITION_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.configuration.set_position_feedback(sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    register_value = mc.communication.get_register(POSITION_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
@pytest.mark.parametrize("sensor, category", SENSOR_TYPE_AND_CATEGORY)
def test_get_position_feedback_category(mc, alias, sensor, category):
    mc.configuration.set_position_feedback(sensor, servo=alias)
    test_category = mc.configuration.get_position_feedback_category(servo=alias)
    assert test_category == category


@pytest.mark.virtual
@pytest.mark.parametrize("sensor", list(SensorType))
def test_get_position_feedback_resolution(mc, alias, sensor):
    skip_if_qei2_is_not_available(mc, alias, sensor=sensor)
    register_values = mc.info.register_info(POSITION_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(POSITION_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    if sensor in [SensorType.INTGEN]:
        with pytest.raises(ValueError):
            mc.configuration.get_position_feedback_resolution(servo=alias)
    else:
        test_res_1 = mc.configuration.get_position_feedback_resolution(servo=alias)
        test_res_2 = mc.configuration.get_feedback_resolution(sensor, servo=alias)
        assert test_res_1 == test_res_2


@pytest.mark.virtual
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
    register_values = mc.info.register_info(AUXILIAR_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.communication.set_register(AUXILIAR_FEEDBACK_REGISTER, sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    test_feedback = mc.configuration.get_auxiliar_feedback(servo=alias)
    assert sensor == test_feedback


@pytest.mark.virtual
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
    register_values = mc.info.register_info(AUXILIAR_FEEDBACK_REGISTER, servo=alias).enums.values()
    try:
        mc.configuration.set_auxiliar_feedback(sensor, servo=alias)
    except exceptions.ILNACKError:
        if sensor.value in register_values:
            raise
        return
    register_value = mc.communication.get_register(AUXILIAR_FEEDBACK_REGISTER, servo=alias)
    assert sensor == register_value


@pytest.mark.virtual
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
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_absolute_encoder_1_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS1_1_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_absolute_encoder_1_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.parametrize("resolution", INCREMENTAL_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_incremental_encoder_1_resolution(mc, alias, resolution):
    mc.communication.set_register(INCREMENTAL_RESOLUTION_1_REGISTER, resolution, servo=alias)
    test_res = mc.configuration.get_incremental_encoder_1_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.parametrize("pair_poles, resolution", [(1, 6), (10, 60), (4, 24)])
def test_get_digital_halls_resolution(mc, alias, pair_poles, resolution):
    mc.communication.set_register(PAIR_POLES_REGISTER, pair_poles, servo=alias)
    test_res = mc.configuration.get_digital_halls_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_secondary_ssi_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS2_1_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_secondary_ssi_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
@pytest.mark.parametrize("single_turn, resolution", ABSOLUTE_ENCODER_RESOLUTION_TEST_VALUES)
def test_get_absolute_encoder_2_resolution(mc, alias, single_turn, resolution):
    mc.communication.set_register(ABS1_2_SINGLE_TURN_REGISTER, single_turn, servo=alias)
    test_res = mc.configuration.get_absolute_encoder_2_resolution(servo=alias)
    assert resolution == test_res


@pytest.mark.virtual
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
def test_encoder_polarity_register_uid(axis, sensor, register):
    assert register == axis.feedbacks.get_sensor(sensor).POLARITY_REGISTER_UID


@pytest.mark.virtual
def test_feedback_slot_round_trip(axis: "Axis") -> None:
    """A feedback slot reads and writes sensor types through the real virtual drive."""
    slot = axis.feedbacks.commutation
    slot.set_encoder_type(SensorType.QEI)

    assert slot.get_encoder_type() == SensorType.QEI
    assert slot.get_encoder() is axis.feedbacks.get_sensor(SensorType.QEI)

    slot.set_encoder(axis.feedbacks.get_sensor(SensorType.HALLS))

    assert slot.get_encoder_type() == SensorType.HALLS


@pytest.mark.virtual
def test_set_encoder_type_rejects_unsupported_sensor(axis: "Axis") -> None:
    """A slot rejects a sensor type the drive's dictionary does not allow for it."""
    slot = axis.feedbacks.auxiliary
    assert not slot.supports(SensorType.INTGEN)

    with pytest.raises(ValueError) as exc_info:
        slot.set_encoder_type(SensorType.INTGEN)

    assert str(exc_info.value) == (
        f"INTGEN is not a valid sensor type for {AUXILIAR_FEEDBACK_REGISTER}."
    )


@pytest.mark.virtual
def test_encoder_polarity_round_trip(axis: "Axis") -> None:
    """An encoder polarity is read and written through its real register."""
    encoder = axis.feedbacks.get_sensor(SensorType.QEI)

    encoder.set_polarity(FeedbackPolarity.NORMAL)
    assert encoder.get_polarity() == FeedbackPolarity.NORMAL

    encoder.set_polarity(FeedbackPolarity.REVERSED)
    assert encoder.get_polarity() == FeedbackPolarity.REVERSED


@pytest.mark.virtual
def test_internal_generator_has_no_resolution_or_polarity(axis: "Axis") -> None:
    """The internal generator rejects operations that require a physical encoder."""
    encoder = axis.feedbacks.get_sensor(SensorType.INTGEN)

    with pytest.raises(ValueError) as exc_info:
        encoder.get_resolution()

    assert str(exc_info.value) == "Internal generator encoder has no resolution"

    with pytest.raises(NotImplementedError) as exc_info:
        encoder.get_polarity()

    assert str(exc_info.value) == "Sensor INTGEN polarity is not implemented"


@pytest.mark.virtual
@pytest.mark.usefixtures("restore_resolution_registers")
@pytest.mark.parametrize(
    "sensor, register, raw_value, expected_resolution",
    [
        (SensorType.ABS1, ABS1_1_SINGLE_TURN_REGISTER, 22, 4194304),
        (SensorType.SSI2, ABS2_1_SINGLE_TURN_REGISTER, 22, 4194304),
        (SensorType.BISSC2, ABS1_2_SINGLE_TURN_REGISTER, 22, 4194304),
        (SensorType.QEI, INCREMENTAL_RESOLUTION_1_REGISTER, 4000, 4000),
        (SensorType.QEI2, INCREMENTAL_RESOLUTION_2_REGISTER, 4000, 4000),
        (SensorType.HALLS, PAIR_POLES_REGISTER, 4, 24),
    ],
)
def test_encoder_get_resolution_by_type(
    axis: "Axis", sensor, register, raw_value, expected_resolution
):
    """Each concrete Encoder subclass computes its resolution from its own register."""
    axis.write(register, raw_value)
    encoder = axis.feedbacks.get_sensor(sensor)
    assert encoder.get_resolution() == expected_resolution


@pytest.mark.virtual
def test_feedback_configuration_updates_are_immutable_and_ordered(axis: "Axis") -> None:
    """Configuration copies preserve the original and deduplicate encoders in order."""
    feedbacks = axis.feedbacks
    original = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.HALLS,
        velocity=SensorType.QEI,
        position=SensorType.ABS1,
        auxiliary=SensorType.HALLS,
    )
    replacement = original.with_encoder_at(
        feedbacks.reference, feedbacks.get_sensor(SensorType.SSI2)
    )
    batch_replacement = original.replace({
        feedbacks.reference: feedbacks.get_sensor(SensorType.SSI2),
        feedbacks.velocity: feedbacks.get_sensor(SensorType.QEI2),
        feedbacks.auxiliary: feedbacks.get_sensor(SensorType.ABS1),
    })

    assert original.encoder_at(feedbacks.reference).SENSOR_TYPE == SensorType.HALLS
    assert replacement.encoder_at(feedbacks.reference).SENSOR_TYPE == SensorType.SSI2
    assert batch_replacement.encoder_at(feedbacks.reference).SENSOR_TYPE == SensorType.SSI2
    assert batch_replacement.encoder_at(feedbacks.velocity).SENSOR_TYPE == SensorType.QEI2
    assert batch_replacement.encoder_at(feedbacks.auxiliary).SENSOR_TYPE == SensorType.ABS1
    assert batch_replacement.encoder_at(feedbacks.commutation).SENSOR_TYPE == SensorType.QEI
    assert batch_replacement.encoder_at(feedbacks.position).SENSOR_TYPE == SensorType.ABS1
    assert tuple(encoder.SENSOR_TYPE for encoder in original.active_encoders_in_order()) == (
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.ABS1,
    )


@pytest.mark.virtual
def test_feedback_configuration_limit_is_checked_before_each_write(axis: "Axis") -> None:
    """A fifth sensor is rejected while an already active sensor remains writable."""
    feedbacks = axis.feedbacks
    current = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.HALLS,
        velocity=SensorType.ABS1,
        position=SensorType.SSI2,
        auxiliary=SensorType.QEI,
    )

    assert len(current.active_sensors()) == MAX_SIMULTANEOUS_FEEDBACKS
    assert current.can_execute_transition(
        feedbacks.commutation, feedbacks.get_sensor(SensorType.HALLS)
    )
    assert not current.can_execute_transition(
        feedbacks.commutation, feedbacks.get_sensor(SensorType.QEI2)
    )


@pytest.mark.virtual
def test_set_configuration_reaches_target_without_exceeding_limit(axis: "Axis") -> None:
    """Safe configuration writes reach the target while keeping four sensors active."""
    feedbacks = axis.feedbacks
    current_sensors = (
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.ABS1,
        SensorType.ABS1,
        SensorType.QEI,
    )
    target_sensors = (
        SensorType.HALLS,
        SensorType.QEI,
        SensorType.INTGEN,
        SensorType.ABS1,
        SensorType.QEI,
    )
    current = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=current_sensors[0],
        reference=current_sensors[1],
        velocity=current_sensors[2],
        position=current_sensors[3],
        auxiliary=current_sensors[4],
    )
    target = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=target_sensors[0],
        reference=target_sensors[1],
        velocity=target_sensors[2],
        position=target_sensors[3],
        auxiliary=target_sensors[4],
    )
    state = current
    for slot, encoder in feedbacks.transition_order(current, target):
        assert state.can_execute_transition(slot, encoder)
        state = state.with_encoder_at(slot, encoder)
        assert len(state.active_sensors()) <= MAX_SIMULTANEOUS_FEEDBACKS

    for slot, sensor in zip(feedbacks._slots, current_sensors, strict=True):
        axis.write(slot.register_uid, sensor)
    feedbacks.set_configuration(target)

    assert tuple(axis.read(slot.register_uid) for slot in feedbacks._slots) == target_sensors


@pytest.mark.virtual
def test_feedback_transition_rejects_target_with_five_sensors(axis: "Axis") -> None:
    """A target requiring five distinct sensors cannot be applied safely."""
    feedbacks = axis.feedbacks
    current = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.QEI,
        velocity=SensorType.QEI,
        position=SensorType.QEI,
        auxiliary=SensorType.QEI,
    )
    target = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.ABS1,
        reference=SensorType.QEI,
        velocity=SensorType.HALLS,
        position=SensorType.SSI2,
        auxiliary=SensorType.BISSC2,
    )

    with pytest.raises(ValueError) as exc_info:
        list(feedbacks.transition_order(current, target))

    assert str(exc_info.value) == "Feedback configurations cannot be transitioned safely."
