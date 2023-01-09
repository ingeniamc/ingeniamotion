import ingenialogger

from enum import IntEnum
from abc import ABC, abstractmethod
from ingenialink.exceptions import ILError

from ingeniamotion.exceptions import IMRegisterNotExist, IMRegisterWrongAccess
from .stoppable import Stoppable, StopException


class TestError(Exception):
    pass


class BaseTest(ABC, Stoppable):
    WARNING_BIT_MASK = 0x0FFFFFFF

    def __init__(self):
        self.backup_registers_names = None
        self.backup_registers = {}
        self.suggested_registers = {}
        self.mc = None
        self.servo = None
        self.axis = None
        self.report = None
        self.logger = ingenialogger.get_logger(__name__)

    def save_backup_registers(self):
        self.backup_registers[self.axis] = {}
        for uid in self.backup_registers_names:
            try:
                value = self.mc.communication.get_register(uid, servo=self.servo, axis=self.axis)
                self.backup_registers[self.axis][uid] = value
            except IMRegisterNotExist as e:
                self.logger.warning(e, axis=self.axis)

    def restore_backup_registers(self):
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
    def show_error_message(self):
        error_code, axis, warning = self.mc.errors.get_last_buffer_error(
            servo=self.servo, axis=self.axis
        )
        *_, error_msg = self.mc.errors.get_error_data(error_code, servo=self.servo)
        raise TestError(error_msg)

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def loop(self):
        pass

    @abstractmethod
    def teardown(self):
        pass

    def run(self):
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

    def __generate_report(self, output):
        return {
            "result_severity": self.get_result_severity(output),
            "suggested_registers": self.suggested_registers,
            "result_message": self.get_result_msg(output),
        }

    @abstractmethod
    def get_result_msg(self, output):
        pass

    @abstractmethod
    def get_result_severity(self, output):
        pass
