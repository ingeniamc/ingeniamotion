import contextlib
from collections import Counter
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from ingenialink.exceptions import ILError

from ingeniamotion.errors import (
    COCO_ERROR_QUEUE,
    FSOE_MCUA_ERROR_QUEUE,
    FSOE_MCUB_ERROR_QUEUE,
    MOCO_ERROR_QUEUE,
    SYSTEM_ERROR_QUEUE,
    ErrorQueueDescriptor,
    OperationError,
    ServoErrorQueue,
    SystemQueueError,
)
from ingeniamotion.exceptions import IMErrorQueueNotExistsError
from tests.conftest import not_valid_for_all_eve_products

if TYPE_CHECKING:
    from ingenialink.servo import Servo
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
    from ingeniamotion.motion_node import MotionNode

USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER = "ERROR_PROT_UNDER_VOLT_OPTION"
USER_UNDER_VOLTAGE_LEVEL_REGISTER = "DRV_PROT_USER_UNDER_VOLT"
UNDER_TEMP_ERROR_CODE = 0x4304
UNDER_TEMP_ERROR_OPTION_REGISTER = "ERROR_PROT_UNDER_TEMP_OPTION"
UNDER_TEMP_REGISTER = "DRV_PROT_USER_UNDER_TEMP"
OPTION_DO_NOTHING = 1


@pytest.fixture
def error_number(mc: "MotionController", alias: str) -> int:
    return mc.errors.get_number_total_errors(servo=alias)


@pytest.fixture
def generate_drive_errors(mc: "MotionController", alias: str) -> Iterator[list[int]]:
    errors_list = [
        {"code": 0x3241, "register": "DRV_PROT_USER_UNDER_VOLT", "value": 100},
        {"code": 0x4303, "register": "DRV_PROT_USER_OVER_TEMP", "value": 1},
        {"code": 0x3231, "register": "DRV_PROT_USER_OVER_VOLT", "value": 1},
        {"code": 0x4304, "register": "DRV_PROT_USER_UNDER_TEMP", "value": 200},
    ]
    error_code_list = []
    for item in errors_list:
        mc.motion.fault_reset(servo=alias)
        old_value = mc.communication.get_register(item["register"], servo=alias)
        mc.communication.set_register(item["register"], item["value"], servo=alias)
        with contextlib.suppress(ILError):
            mc.motion.motor_enable(servo=alias)
        error_code_list.append(item["code"])
        try:
            mc.communication.set_register(item["register"], old_value, servo=alias)
        except ILError:
            # Sometimes fails with EVE-XCR-E
            mc.communication.set_register(item["register"], old_value, servo=alias)
    yield error_code_list[::-1]
    mc.motion.fault_reset(servo=alias)


@pytest.fixture
def generate_drive_warning(mc: "MotionController", alias: str) -> Iterator[int]:
    """Generate an under-temperature warning.

    Yields:
        The error code of the generated warning.

    """
    mc.communication.set_register(UNDER_TEMP_ERROR_OPTION_REGISTER, OPTION_DO_NOTHING, servo=alias)
    mc.communication.set_register(UNDER_TEMP_REGISTER, 100, servo=alias)
    mc.motion.motor_enable(servo=alias)
    yield UNDER_TEMP_ERROR_CODE
    mc.motion.motor_disable(servo=alias)


@pytest.fixture
def force_warning(mc: "MotionController", alias: str) -> Iterator[None]:
    mc.communication.set_register(USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER, 1, servo=alias)
    mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 100, servo=alias)
    mc.motion.motor_enable(servo=alias)
    yield
    mc.communication.set_register(USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER, 0, servo=alias)
    mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 10, servo=alias)


@pytest.mark.parametrize(
    "error_id, expected_error_code, expected_axis, expected_is_warning",
    [
        (0x103241, 0x3241, 1, False),  # axis=1, no warning
        (0x203241, 0x3241, 2, False),  # axis=2, no warning
        (0x10103241, 0x3241, 1, True),  # axis=1, warning bit set
        (0x10203241, 0x3241, 2, True),  # axis=2, warning bit set
        (0x000ABCD, 0xABCD, 0, False),  # axis=0, no warning
    ],
)
def test_operation_error_class_properties(
    error_id: int,
    expected_error_code: int,
    expected_axis: int,
    expected_is_warning: bool,
) -> None:
    """Test OperationError class error_code, axis, and is_warning properties."""
    error = SystemQueueError.from_id(error_id)
    assert error.error_code == expected_error_code
    assert error.axis == expected_axis
    assert error.is_warning is expected_is_warning


class TestErrorQueue:
    @pytest.mark.virtual
    def test_servo_error_queue_missing_register_raises(self, servo: "Servo") -> None:
        """If the dictionary doesn't contain the register UID,
        constructing the queue should raise IMRegisterNotExistError."""
        # Create a descriptor with a non-existent UID
        fake_descriptor = ErrorQueueDescriptor(
            name="error_non_existing",
            last_error_reg_uid="NON_EXISTENT_UID",
            total_error_reg_uid="DRV_DIAG_ERROR_TOTAL",
            error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX",
            error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE",
            max_index_request=31,
            error_type=OperationError,
        )

        with pytest.raises(IMErrorQueueNotExistsError) as excinfo:
            ServoErrorQueue(fake_descriptor, servo)

            assert excinfo.value.args[0] == (
                "One or more registers for error queue not found in servo dictionary."
                "Missing registers: [('NON_EXISTENT_UID', None), ('DRV_DIAG_ERROR_TOTAL', None),"
                " ('DRV_DIAG_ERROR_LIST_IDX', None), ('DRV_DIAG_ERROR_LIST_CODE', None)]"
            )

    @pytest.mark.virtual
    def test_servo_error_queue_obtains_registers_with_axis(
        self, mocker: "pytest.MockFixture", servo: "Servo"
    ) -> None:
        """Test that ServoErrorQueue obtains register objects with correct axis."""
        mock_get_register = mocker.patch.object(servo.dictionary, "get_register")
        mock_register = mocker.Mock()
        mock_get_register.return_value = mock_register

        # Create queue with axis=2
        q = ServoErrorQueue(MOCO_ERROR_QUEUE, servo, axis=2)
        # Name should include axis
        assert q.name == "MoCo Axis 2 Error Queue"

        # Verify get_register was called with axis=2
        expected_calls = [
            mocker.call("DRV_DIAG_ERROR_LAST", axis=2),
            mocker.call("DRV_DIAG_ERROR_TOTAL", axis=2),
            mocker.call("DRV_DIAG_ERROR_LIST_IDX", axis=2),
            mocker.call("DRV_DIAG_ERROR_LIST_CODE", axis=2),
        ]
        mock_get_register.assert_has_calls(expected_calls)


class TestErrors:
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_last_error(
        self, mc: "MotionController", alias: str, generate_drive_errors: list[int]
    ) -> None:
        # Axis 1 needs to be selected due to a bug in EVE-XCR. For more info check INGM-376.
        last_error, subnode, warning = mc.errors.get_last_error(servo=alias, axis=1)
        assert last_error == generate_drive_errors[0]
        mc.motion.fault_reset(servo=alias)
        last_error, subnode, warning = mc.errors.get_last_error(servo=alias, axis=1)
        assert last_error == 0
        assert subnode is None
        assert warning is None

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_last_buffer_error(
        self, mc: "MotionController", alias: str, generate_drive_errors: list[int]
    ) -> None:
        last_error, _subnode, _warning = mc.errors.get_last_buffer_error(servo=alias)
        assert last_error == generate_drive_errors[0]

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_buffer_error_by_index(
        self, mc: "MotionController", alias: str, generate_drive_errors: list[int]
    ):
        index_list = [2, 1, 3, 0]
        for i in index_list:
            last_error, _subnode, _warning = mc.errors.get_buffer_error_by_index(
                i, servo=alias, axis=1
            )
            assert last_error == generate_drive_errors[i]

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("generate_drive_errors")
    def test_get_buffer_error_by_index_exception(self, mc: "MotionController", alias: str) -> None:
        with pytest.raises(ValueError):
            mc.errors.get_buffer_error_by_index(33, servo=alias)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_number_total_errors(
        self,
        mc: "MotionController",
        alias: str,
        error_number: int,
        generate_drive_errors: list[int],
    ) -> None:
        test_error_number = mc.errors.get_number_total_errors(servo=alias)
        assert test_error_number == error_number + len(generate_drive_errors)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_all_errors(
        self, mc: "MotionController", alias: str, generate_drive_errors: list[int]
    ) -> None:
        test_all_errors = mc.errors.get_all_errors(servo=alias, axis=1)
        for i, code_error in enumerate(generate_drive_errors):
            test_code_error, _axis, _warning = test_all_errors[i]
            assert test_code_error == code_error

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("generate_drive_errors")
    def test_is_fault_active(self, mc: "MotionController", alias: str) -> None:
        assert mc.errors.is_fault_active(servo=alias)
        mc.motion.fault_reset(servo=alias)
        assert not mc.errors.is_fault_active(servo=alias)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("force_warning")
    def test_is_warning_active(self, mc: "MotionController", alias: str) -> None:
        assert mc.errors.is_warning_active(servo=alias)
        mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 10, servo=alias)
        assert not mc.errors.is_warning_active(servo=alias)

    @pytest.mark.virtual
    @pytest.mark.parametrize(
        "error_code, affected_module, error_type, error_msg",
        [
            (0x3241, "Power stage", "Cyclic", "User Under-voltage detected"),
            (0x4303, "Power stage", "Cyclic", "Over-temperature detected (user limit)"),
            (0x3231, "Power stage", "Cyclic", "User Over-voltage detected"),
            (0x4304, "Power stage", "Cyclic", "Under-temperature detected (user limit)"),
        ],
    )
    def test_get_error_data(
        self,
        mc: "MotionController",
        alias: str,
        error_code: int,
        affected_module: str,
        error_type: str,
        error_msg: str,
    ) -> None:
        test_id, test_aff_mod, test_type, test_msg = mc.errors.get_error_data(
            error_code, servo=alias
        )
        assert error_code == int(test_id, base=16)
        assert test_aff_mod == affected_module
        assert test_type == error_type
        assert test_msg == error_msg

    @pytest.mark.parametrize(
        "function",
        [
            "get_last_error",
            "get_buffer_error_by_index",
            "get_number_total_errors",
        ],
    )
    @pytest.mark.virtual
    def test_wrong_type_exception(
        self,
        mocker: "pytest.MockFixture",
        mc: "MotionController",
        servo: "Servo",
        alias: str,
        function: str,
    ) -> None:
        mocker.patch.object(servo, "read", return_value="invalid_value", autospec=True)
        with pytest.raises(TypeError):
            getattr(mc.errors, function)(servo=alias)
        mocker.stopall()

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_no_errors(
        self,
        mc: "MotionController",
        servo: "Servo",
        alias: str,
        environment: "DriveEnvironmentController",
    ) -> None:
        """Test ServoErrorQueue with no errors present."""
        environment.power_cycle(wait_for_drives=False, reconnect_drives=True, reconnect_timeout=20)

        mc.motion.fault_reset(servo=alias)
        error_queue = ServoErrorQueue(MOCO_ERROR_QUEUE, servo)
        pending_errors, errors_lost = error_queue.get_pending_errors()
        assert pending_errors == []
        assert errors_lost is False

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_with_errors(
        self, servo: "Servo", generate_drive_errors: list[int]
    ) -> None:
        """Test ServoErrorQueue correctly retrieves pending errors."""
        # generate_drive_errors fixture already power cycled and cleared errors
        error_queue = ServoErrorQueue(MOCO_ERROR_QUEUE, servo)
        pending_errors, errors_lost = error_queue.get_pending_errors()

        # Should have all the generated errors
        assert len(pending_errors) == len(generate_drive_errors)
        assert errors_lost is False

        # Verify error IDs match (newest first)
        for error, expected_code in zip(pending_errors, generate_drive_errors):
            assert error.error_id == expected_code

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_tracks_state(
        self,
        mc: "MotionController",
        servo: "Servo",
        alias: str,
        environment: "DriveEnvironmentController",
    ) -> None:
        """Test that ServoErrorQueue only reports new errors after first call."""
        environment.power_cycle(wait_for_drives=False, reconnect_drives=True, reconnect_timeout=20)

        error_queue = ServoErrorQueue(MOCO_ERROR_QUEUE, servo)

        # First call - no errors
        pending_errors, _ = error_queue.get_pending_errors()
        assert len(pending_errors) == 0

        # Generate an error
        old_value = mc.communication.get_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, servo=alias)
        mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 100, servo=alias)
        with contextlib.suppress(ILError):
            mc.motion.motor_enable(servo=alias)

        # Second call - should see the new error
        pending_errors, _ = error_queue.get_pending_errors()
        assert len(pending_errors) == 1
        assert pending_errors[0].error_id == 0x3241

        # Third call - no new errors
        pending_errors, _ = error_queue.get_pending_errors()
        assert len(pending_errors) == 0

        # Cleanup
        mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, old_value, servo=alias)
        mc.motion.fault_reset(servo=alias)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_get_last_error_moco(
        self,
        mc: "MotionController",
        servo: "Servo",
        alias: str,
        generate_drive_errors: list[int],
    ) -> None:
        """Test ServoErrorQueue.get_last_error() method with MOCO queue."""
        # generate_drive_errors fixture already power cycled and cleared errors
        error_queue = ServoErrorQueue(MOCO_ERROR_QUEUE, servo)
        last_error = error_queue.get_last_error()

        assert last_error is not None
        assert isinstance(last_error, OperationError)
        assert last_error.error_code == generate_drive_errors[0]
        assert last_error.is_warning is False
        assert last_error.error_description is not None

        # After fault reset, should return None
        mc.motion.fault_reset(servo=alias)
        last_error = error_queue.get_last_error()
        assert last_error is None

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_get_error_by_index_moco_warning(
        self, servo: "Servo", generate_drive_warning: int
    ) -> None:
        """Test ServoErrorQueue.get_error_by_index() method with MOCO queue and a warning."""
        error_queue = ServoErrorQueue(MOCO_ERROR_QUEUE, servo)
        last_buffer_error = error_queue.get_error_by_index(0)

        assert last_buffer_error is not None
        assert isinstance(last_buffer_error, OperationError)
        assert last_buffer_error.error_code == generate_drive_warning
        assert last_buffer_error.is_warning is True
        assert last_buffer_error.error_description == "Under-temperature detected (user limit)"

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_error_queue_get_last_error_system(
        self,
        mc: "MotionController",
        servo: "Servo",
        alias: str,
        generate_drive_errors: list[int],
    ) -> None:
        """Test ServoErrorQueue.get_last_error() method with System queue."""
        # generate_drive_errors fixture already power cycled and cleared errors
        error_queue = ServoErrorQueue(SYSTEM_ERROR_QUEUE, servo, axis=0)
        last_error = error_queue.get_last_error()

        assert last_error is not None
        assert isinstance(last_error, SystemQueueError)
        assert last_error.error_code == generate_drive_errors[0]
        assert last_error.axis == 1
        assert last_error.is_warning is False
        assert last_error.error_description is not None

        # After fault reset, should return None
        mc.motion.fault_reset(servo=alias)
        last_error = error_queue.get_last_error()
        assert last_error is None

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @not_valid_for_all_eve_products
    def test_error_queue_get_error_by_index_system_warning(
        self, servo: "Servo", generate_drive_warning: int
    ) -> None:
        """Test ServoErrorQueue.get_error_by_index() method with System queue and a warning."""
        error_queue = ServoErrorQueue(SYSTEM_ERROR_QUEUE, servo, axis=0)
        last_buffer_error = error_queue.get_error_by_index(0)

        assert last_buffer_error is not None
        assert isinstance(last_buffer_error, SystemQueueError)
        assert last_buffer_error.error_code == generate_drive_warning
        assert last_buffer_error.axis == 1
        assert last_buffer_error.is_warning is True
        assert last_buffer_error.error_description == "Under-temperature detected (user limit)"


class TestErrorMotionNode:
    """Test NodeErrors class functionality."""

    @pytest.mark.virtual
    def test_node_errors_get_queue_returns_none_when_no_registers(
        self, motion_node: "MotionNode"
    ) -> None:
        """Test that NodeErrors.get_queue returns None when registers not found."""

        # Create a descriptor with a non-existent register UID
        fake_descriptor = ErrorQueueDescriptor(
            name="error_non_existing",
            last_error_reg_uid="NON_EXISTENT_UID",
            total_error_reg_uid="DRV_DIAG_ERROR_TOTAL",
            error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX",
            error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE",
            max_index_request=31,
            error_type=OperationError,
        )

        result = motion_node.errors.get_queue(fake_descriptor)
        assert result is None

    @pytest.mark.virtual
    def test_node_errors_system_and_coco_properties(self, motion_node: "MotionNode") -> None:
        """Test NodeErrors.system and coco properties on virtual drives."""

        # both system and coco queues are available
        system_queue = motion_node.errors.system
        assert system_queue is not None
        assert isinstance(system_queue, ServoErrorQueue)
        assert system_queue.descriptor == SYSTEM_ERROR_QUEUE
        assert system_queue.name == "System Error Queue"

        # repeated access returns the same instance (cached)
        system_queue2 = motion_node.errors.system
        assert system_queue2 is system_queue
        assert motion_node.errors.get_queue(SYSTEM_ERROR_QUEUE) is system_queue

        coco_queue = motion_node.errors.coco
        assert coco_queue is not None
        assert isinstance(coco_queue, ServoErrorQueue)
        assert coco_queue.descriptor == COCO_ERROR_QUEUE
        assert coco_queue.name == "CoCo Error Queue"

        # repeated access returns the same instance (cached)
        coco_queue2 = motion_node.errors.coco
        assert coco_queue2 is coco_queue
        assert motion_node.errors.get_queue(COCO_ERROR_QUEUE) is coco_queue

    @pytest.mark.virtual
    def test_node_errors_get_all_queues(self, motion_node: "MotionNode") -> None:
        """Test NodeErrors.get_all_queues method."""

        all_queues = list(motion_node.errors.get_all_queues())

        # Extract descriptors for easier checking
        descriptors = [queue.descriptor for queue in all_queues]

        expected_descriptors = [SYSTEM_ERROR_QUEUE, COCO_ERROR_QUEUE, MOCO_ERROR_QUEUE]
        assert Counter(descriptors) == Counter(expected_descriptors)

    @pytest.mark.virtual
    def test_node_errors_get_all_queues_with_exclude(self, motion_node: "MotionNode") -> None:
        """Test NodeErrors.get_all_queues with exclude parameter."""

        # Get queues excluding SYSTEM_ERROR_QUEUE
        filtered_queues = list(motion_node.errors.get_all_queues(exclude=[SYSTEM_ERROR_QUEUE]))

        descriptors = [queue.descriptor for queue in filtered_queues]

        assert Counter(descriptors) == Counter([COCO_ERROR_QUEUE, MOCO_ERROR_QUEUE])


class TestErrorAxis:
    """Test AxisErrors class functionality."""

    @pytest.mark.virtual
    def test_axis_errors_get_queue_returns_none_when_no_registers(self, axis: "Axis") -> None:
        """Test that AxisErrors.get_queue returns None when registers not found."""

        # Create a descriptor with a non-existent register UID
        fake_descriptor = ErrorQueueDescriptor(
            name="error_non_existing",
            last_error_reg_uid="NON_EXISTENT_UID",
            total_error_reg_uid="DRV_DIAG_ERROR_TOTAL",
            error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX",
            error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE",
            max_index_request=31,
            error_type=OperationError,
        )

        result = axis.errors.get_queue(fake_descriptor)
        assert result is None

    @pytest.mark.virtual
    def test_axis_errors_all_queues_on_virtual_drive(self, axis: "Axis") -> None:
        """Test that on standard virtual drives, MOCO is available but safety queues are not."""
        moco_queue = axis.errors.moco

        # MOCO queue should be available
        assert moco_queue is not None
        assert isinstance(moco_queue, ServoErrorQueue)
        assert moco_queue.descriptor == MOCO_ERROR_QUEUE
        assert moco_queue.name == "MoCo Axis 1 Error Queue"

        # repeated access returns the same instance (cached)
        moco_queue2 = axis.errors.moco
        assert moco_queue2 is moco_queue
        assert axis.errors.get_queue(MOCO_ERROR_QUEUE) is moco_queue

        # Safety queues should not be available on standard virtual drives
        assert axis.errors.safety_a is None
        assert axis.errors.safety_b is None

        filtered_queues = list(axis.errors.get_all_queues(exclude=[SYSTEM_ERROR_QUEUE]))
        descriptors = [queue.descriptor for queue in filtered_queues]
        assert Counter(descriptors) == Counter([MOCO_ERROR_QUEUE])

    @pytest.mark.fsoe_phase2
    def test_axis_errors_all_queues_safety_on_phase_2(self, axis: "Axis") -> None:
        """Test that on safety phase II virtual drives, all three queues
        (MOCO, MCUA, MCUB) are available."""
        # All three queues should be available on safety phase II drives
        moco_queue = axis.errors.moco
        assert moco_queue is not None
        assert isinstance(moco_queue, ServoErrorQueue)
        assert moco_queue.descriptor == MOCO_ERROR_QUEUE

        safety_a_queue = axis.errors.safety_a
        assert safety_a_queue is not None
        assert isinstance(safety_a_queue, ServoErrorQueue)
        assert safety_a_queue.descriptor == FSOE_MCUA_ERROR_QUEUE
        assert safety_a_queue.name == "Safety A Error Queue"

        safety_b_queue = axis.errors.safety_b
        assert safety_b_queue is not None
        assert isinstance(safety_b_queue, ServoErrorQueue)
        assert safety_b_queue.descriptor == FSOE_MCUB_ERROR_QUEUE
        assert safety_b_queue.name == "Safety B Error Queue"

        filtered_queues = list(axis.errors.get_all_queues(exclude=[FSOE_MCUA_ERROR_QUEUE]))
        descriptors = [queue.descriptor for queue in filtered_queues]
        assert Counter(descriptors) == Counter([MOCO_ERROR_QUEUE, FSOE_MCUB_ERROR_QUEUE])
