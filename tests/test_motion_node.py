import pytest
from ingenialink.dictionary import SubnodeType

from ingeniamotion.motion_node import MotionNode


@pytest.mark.virtual
def test_axes_created_for_multi_axis_dictionary(mocker, servo, net):
    """Test that an Axis is created for each axis in the dictionary (subnodes > 0)."""
    # Mock only the subnodes to simulate multi-axis
    mocker.patch.object(
        servo.dictionary,
        "subnodes",
        {
            0: SubnodeType.COMMUNICATION,  # Communication subnode, not an axis
            1: SubnodeType.MOTION,  # Axis 1
            2: SubnodeType.MOTION,  # Axis 2
        },
    )

    # Create MotionNode with real servo and network
    motion_node = MotionNode(servo, net)

    # Collect axes
    axes = list(motion_node.axes)

    # Should have 2 axes (for subnodes 1 and 2)
    assert len(axes) == 2

    # Check axis numbers
    axis_numbers = [axis.axis_number for axis in axes]
    assert 1 in axis_numbers
    assert 2 in axis_numbers

    # Verify each axis has the correct motion_node
    for axis in axes:
        assert axis.motion_node is motion_node

    # Test get_axis method
    axis1 = motion_node.get_axis(1)
    assert axis1.axis_number == 1
    assert axis1.motion_node is motion_node

    axis2 = motion_node.get_axis(2)
    assert axis2.axis_number == 2
    assert axis2.motion_node is motion_node

    # Test KeyError for non-existent axis
    with pytest.raises(KeyError):
        motion_node.get_axis(3)
