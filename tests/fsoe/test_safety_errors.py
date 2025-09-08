import time
from typing import TYPE_CHECKING

import pytest
from ingenialink.dictionary import Interface
from ingenialink.servo import DictionaryFactory

from ingeniamotion.fsoe_master import (
    PDUMaps,
    SLPFunction,
    SPFunction,
    STOFunction,
    SVFunction,
)
from ingeniamotion.fsoe_master.errors import (
    MCUA_ERROR_QUEUE,
    MCUB_ERROR_QUEUE,
    Error,
    ServoErrorQueue,
)
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY
from tests.test_fsoe_master import TIMEOUT_FOR_DATA_SRA

if TYPE_CHECKING:
    from ingenialink import Servo


@pytest.mark.fsoe_phase2
def test_get_known_error():
    """Test getting a known error from the dictionary."""
    dictionary = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    error = Error.from_id(0x00007394, dictionary=dictionary)
    assert error.error_id == 0x00007394
    assert error.error_description == "Emergency position set-point not configured."
    assert (
        repr(error) == f"<Error object at {hex(id(error))} error_id=29588"
        f" error_description='Emergency position set-point not configured.'>"
    )


@pytest.mark.fsoe_phase2
def test_get_error_with_id_not_in_dict():
    """Test getting an error with an unknown ID."""
    dictionary = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    error = Error.from_id(0x1234, dictionary=dictionary)
    assert error.error_id == 0x1234
    assert error.error_description == "Unknown error 4660 / 0x1234"


@pytest.fixture
def mcu_error_queue_a(servo: "Servo") -> ServoErrorQueue:
    return ServoErrorQueue(MCUA_ERROR_QUEUE, servo)


@pytest.fixture
def mcu_error_queue_b(servo: "Servo") -> ServoErrorQueue:
    return ServoErrorQueue(MCUB_ERROR_QUEUE, servo)


@pytest.mark.fsoe_phase2
def test_no_errors(mcu_error_queue_a, environment):
    """Test methods when there are no errors"""
    # Clear any existing errors by power cycling
    environment.power_cycle(wait_for_drives=True)

    assert mcu_error_queue_a.get_number_total_errors() == 0

    last_error = mcu_error_queue_a.get_last_error()
    assert last_error is None

    mcu_error_queue_a.get_pending_errors() == []


@pytest.mark.skip(reason="FSOE Over temperature error was not available in release 2.8.1")
@pytest.mark.fsoe_phase2
def test_get_last_error_overtemp_error(servo, mcu_error_queue_a, environment):
    """Test getting the last error when there is an overtemperature error."""
    # Clear any existing errors by power cycling
    environment.power_cycle(wait_for_drives=True)

    servo.write("FSOE_USER_OVER_TEMPERATURE", 0, subnode=1)

    last_error = mcu_error_queue_a.get_last_error()

    assert isinstance(last_error, Error)
    assert last_error.error_id == 0x80020001
    assert last_error.error_description == (
        "Overtemperature. The local temperature of a safety core exceeds the upper limit."
    )


@pytest.mark.fsoe_phase2
def test_get_last_error_feedback_combination(
    mcu_error_queue_a, mcu_error_queue_b, mc_with_fsoe_factory, environment
):
    environment.power_cycle(wait_for_drives=True)
    """Test getting the last error when there is a feedback combination error."""
    mc, handler = mc_with_fsoe_factory(use_sra=True, fail_on_fsoe_errors=False)

    # Add a function that uses safe position to handler
    # and select feedback scenario invalid
    handler.safety_parameters["FSOE_FEEDBACK_SCENARIO"].set(0)  # No feedbacks

    sto = handler.get_function_instance(STOFunction)
    slp_1 = handler.get_function_instance(SLPFunction, instance=1)

    handler.get_function_instance(SPFunction)
    handler.get_function_instance(SVFunction)

    maps = PDUMaps.empty(handler.dictionary)

    maps.inputs.add(sto.command)

    maps.outputs.add(sto.command)
    maps.outputs.add(slp_1.command)

    handler.set_maps(maps)

    mc.fsoe.configure_pdos(start_pdos=True)
    time.sleep(TIMEOUT_FOR_DATA_SRA)

    assert mcu_error_queue_a.get_number_total_errors() == 1
    assert mcu_error_queue_b.get_number_total_errors() == 1
    assert mcu_error_queue_a.get_last_error().error_id == 0x90090701
    assert mcu_error_queue_b.get_last_error().error_id == 0x90090701

    errors_a, errors_losts = mcu_error_queue_a.get_pending_errors()
    assert len(errors_a) == 1
    assert errors_a[0].error_id == 0x90090701

    assert not errors_losts


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize(
    "last_total_errors, current_total_errors, expected_pending_error_indexes, expected_errors_lost",
    [
        (0, 5, (0, 1, 2, 3, 4), False),
        (7, 11, (7, 8, 9, 10), False),
        (29, 35, (29, 30, 31, 0, 1, 2), False),
        (17, 17 + 32, tuple(range(17, 32)) + tuple(range(17)), False),
        (17, 17 + 33, tuple(range(18, 32)) + tuple(range(18)), True),
    ],
)
def test_get_pending_error_indexes(
    last_total_errors: int,
    current_total_errors: int,
    expected_pending_error_indexes: tuple[int, ...],
    expected_errors_lost: bool,
    mcu_error_queue_a,
):
    mcu_error_queue_a._ServoErrorQueue__last_read_total_errors_pending = last_total_errors
    pending_error_indexes, errors_lost = (
        mcu_error_queue_a._ServoErrorQueue__get_pending_error_indexes(current_total_errors)
    )

    assert pending_error_indexes == expected_pending_error_indexes
    assert errors_lost == expected_errors_lost
