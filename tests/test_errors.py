import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from ingenialink.exceptions import ILError

from ingeniamotion.errors import (
    MOCO_ERROR_QUEUE,
    SYSTEM_ERROR_QUEUE,
    OperationError,
    ServoErrorQueue,
    SystemQueueError,
)
from tests.conftest import not_valid_for_all_eve_products

if TYPE_CHECKING:
    from ingenialink.servo import Servo
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingeniamotion.motion_controller import MotionController

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
