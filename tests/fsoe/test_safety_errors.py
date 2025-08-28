from typing import TYPE_CHECKING

import pytest
from ingenialink.dictionary import Interface
from ingenialink.servo import DictionaryFactory

from ingeniamotion.fsoe_master.errors import MCUA_ERROR_QUEUE, Error, ServoErrorQueue
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

if TYPE_CHECKING:
    from ingenialink import Servo


def test_get_known_error():
    """Test getting a known error from the dictionary."""
    dictionary = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    error = Error.from_id(0x00007394, dictionary=dictionary)
    assert error.error_id == 0x00007394
    assert error.error_description == "Emergency position set-point not configured."


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


def test_get_last_error_no_error(mcu_error_queue_a):
    """Test getting the last error when there are no errors."""
    # Pending Can we request a power cycle to ensure no errors?

    last_error = mcu_error_queue_a.get_last_error()
    assert last_error is None


def test_get_last_error_overtemp_error(servo, mcu_error_queue_a):
    """Test getting the last error when there is an overtemperature error."""
    # Pending This error is not available until the next release

    servo.write("FSOE_USER_OVER_TEMPERATURE", 0, subnode=1)

    last_error = mcu_error_queue_a.get_last_error()

    assert isinstance(last_error, Error)
    assert last_error.error_id == 0x80020001
    assert last_error.error_description == ("Overtemperature. "
        "The local temperature of a safety core exceeds the upper limit.")
