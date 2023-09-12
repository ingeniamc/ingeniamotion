from typing import Any, Union, Optional

import ingenialogger

from enum import IntEnum
from abc import ABC, abstractmethod
from ingenialink.exceptions import ILError

from ingeniamotion.exceptions import IMRegisterNotExist, IMRegisterWrongAccess
from .stoppable import Stoppable, StopException
from .. import MotionController
from ..enums import SeverityLevel


class TestError(Exception):
    pass

class BaseResultType(IntEnum):
    pass


class BaseTest(ABC, Stoppable):
    WARNING_BIT_MASK = 0x0FFFFFFF

    def __init__(self) -> None:
        self.backup_registers_names: list[str] = []
        self.backup_registers: dict[int, dict[str, Union[int, float, str]]] = {}
        self.suggested_registers: dict[str, Union[int, float, str]]= {}
        self.mc: MotionController
        self.servo: Optional[str] = None
        self.axis: int = 0
        self.report: Optional[dict[str, Any]] = None
        self.logger = ingenialogger.get_logger(__name__)

    def save_backup_registers(self) -> None:
        self.backup_registers[self.axis] = {}
        if not isinstance(self.backup_registers_names, list):
            return
        for uid in self.backup_registers_names:
            try:
                value = self.mc.communication.get_register(uid, servo=self.servo, axis=self.axis)
                self.backup_registers[self.axis][uid] = value
            except IMRegisterNotExist as e:
                self.logger.warning(e, axis=self.axis)

    def restore_backup_registers(self) -> None:
        """Restores the value of the registers after the test execution.

        Notes:
        This should only be called by the Wizard.
        """
        for subnode, registers in self.backup_registers.items():
            for key, value in self.backup_registers[subnode].items():
                try:
                    self.mc.communication.set_register(key, value, servo=self.servo, axis=self.axis)
                except IMRegisterNotExist as e:
                    self.logger.warning(e, axis=subnode)
                except IMRegisterWrongAccess as e:
                    self.logger.warning(e, axis=subnode)

    @Stoppable.stoppable
    def show_error_message(self) -> None:
        error_code, axis, warning = self.mc.errors.get_last_buffer_error(
            servo=self.servo, axis=self.axis
        )
        *_, error_msg = self.mc.errors.get_error_data(error_code, servo=self.servo)
        raise TestError(error_msg)

    @abstractmethod
    def setup(self) -> None:
        pass

    @abstractmethod
    def loop(self) -> Optional[BaseResultType]:
        pass

    @abstractmethod
    def teardown(self) -> None:
        pass

    def run(self) -> Optional[dict[str, Any]]:
        self.reset_stop()
        self.save_backup_registers()
        try:
            self.setup()
            output = self.loop()
            self.report = self.__generate_report(output)
        except ILError as err:
            raise err
        except StopException:
            self.logger.warning("Test has been stopped")
        finally:
            try:
                self.teardown()
            finally:
                self.restore_backup_registers()
        return self.report

    def __generate_report(self, output: Any) -> dict[str, Any]:
        return {
            "result_severity": self.get_result_severity(output),
            "suggested_registers": self.suggested_registers,
            "result_message": self.get_result_msg(output),
        }

    @abstractmethod
    def get_result_msg(self, output: Any) -> str:
        pass

    @abstractmethod
    def get_result_severity(self, output: Any) -> SeverityLevel:
        pass
