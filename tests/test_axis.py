from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_node import MotionNode


@pytest.mark.virtual
def test_axis_delegates_register_access_to_its_subnode(axis: "Axis") -> None:
    """Axis register access uses the axis subnode on the real servo."""
    register_uid = "CL_VEL_FBK_SENSOR"
    expected_value = axis.motion_node.servo.read(register_uid, subnode=axis.axis_number)

    assert axis.read(register_uid) == expected_value
    axis.write(register_uid, expected_value)


@pytest.mark.virtual
def test_axis_feedback_and_error_containers_are_cached(axis: "Axis") -> None:
    """Axis helper containers are created lazily and reused per axis."""
    assert axis.feedbacks is axis.feedbacks
    assert axis.errors is axis.errors


@pytest.mark.virtual
def test_motion_node_error_container_is_cached(motion_node: "MotionNode") -> None:
    """MotionNode constructs its error container lazily and only once."""
    assert motion_node.errors is motion_node.errors
