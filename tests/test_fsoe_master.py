import time
from threading import Thread
from typing import Callable

import pytest
from fsoe_master import fsoe_master

from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.fsoe import FSoEMasterHandler


@pytest.mark.virtual
def test_fsoe_master_not_installed():
    try:
        import fsoe_master
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("fsoe_master is installed")

    mc = ingeniamotion.MotionController()
    with pytest.raises(NotImplementedError):
        mc.fsoe


@pytest.fixture()
def master_handler():
    return FSoEMasterHandler(
        slave_address=1,
        connection_id=2,
        watchdog_timeout=1,
        application_parameters=[],
        report_error_callback=lambda transition_name, error_description: print(
            transition_name, error_description
        ),
    )


@pytest.mark.virtual
def test_wait_for_state_data(master_handler):
    class WaiterThread(Thread):
        def __init__(self, func: Callable[[], None]):
            super().__init__()
            self.time_elapsed = 0
            self.exception_raised = None
            self.__master_handler = master_handler
            self.__func = func

        def run(self):
            initial_time = time.time()
            try:
                self.__func()
            except Exception as ex:
                self.exception_raised = ex
            finally:
                self.time_elapsed = time.time() - initial_time

    TOTAL_TIME_TO_DATA = 0.3
    TIME_ABS_TOLERANCE = 0.01

    wait_indenfinetely = WaiterThread(lambda: master_handler.wait_for_data_state())
    wait_with_timeout_reached = WaiterThread(
        lambda: master_handler.wait_for_data_state(timeout=TOTAL_TIME_TO_DATA - 0.2)
    )
    wait_with_timeout_not_reached = WaiterThread(
        lambda: master_handler.wait_for_data_state(timeout=TOTAL_TIME_TO_DATA + 0.2)
    )

    wait_indenfinetely.start()
    wait_with_timeout_reached.start()
    wait_with_timeout_not_reached.start()

    time.sleep(0.1)
    master_handler._FSoEMasterHandler__state_change_callback(fsoe_master.StateSession)
    time.sleep(0.1)
    master_handler._FSoEMasterHandler__state_change_callback(fsoe_master.StateParameter)
    time.sleep(0.1)
    master_handler._FSoEMasterHandler__state_change_callback(fsoe_master.StateData)
    time.sleep(0.1)
    master_handler._FSoEMasterHandler__state_change_callback(fsoe_master.StateReset)

    assert wait_indenfinetely.time_elapsed == pytest.approx(
        TOTAL_TIME_TO_DATA, abs=TIME_ABS_TOLERANCE
    )
    assert wait_indenfinetely.exception_raised is None

    assert wait_with_timeout_reached.time_elapsed == pytest.approx(
        TOTAL_TIME_TO_DATA - 0.2, abs=TIME_ABS_TOLERANCE
    )
    assert isinstance(wait_with_timeout_reached.exception_raised, IMTimeoutError)

    assert wait_with_timeout_not_reached.time_elapsed == pytest.approx(
        TOTAL_TIME_TO_DATA, abs=TIME_ABS_TOLERANCE
    )
    assert wait_with_timeout_not_reached.exception_raised is None
