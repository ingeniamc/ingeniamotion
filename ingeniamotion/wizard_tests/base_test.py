import ingenialogger

from abc import ABC, abstractmethod
from ingenialink.exceptions import ILError

from .stoppable import Stoppable, StopException


class TestError(Exception):
    pass


class BaseTest(ABC, Stoppable):

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
                value = self.mc.communication.get_register(
                    uid, servo=self.servo, axis=self.axis
                )
                self.backup_registers[self.axis][uid] = value
            except ILError as e:
                self.logger.warning(e, axis=self.axis)

    def restore_backup_registers(self):
        """ Restores the value of the registers after the test execution.

        Notes:
        This should only be called by the Wizard.
        """
        for subnode, registers in self.backup_registers.items():
            for key, value in self.backup_registers[subnode].items():
                try:
                    self.mc.communication.set_register(
                        key, value, servo=self.servo, axis=self.axis
                    )
                except ILError as e:
                    self.logger.warning(e, axis=subnode)

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
        drive_disconnected = False
        self.save_backup_registers()
        try:
            self.setup()
            output = self.loop()
            self.report = self.__generate_report(output)
        except ILError as err:
            drive_disconnected = True
            raise err
        except StopException:
            self.logger.warning("Test has been stopped")
        finally:
            try:
                if not drive_disconnected:
                    self.teardown()
            finally:
                self.restore_backup_registers()
        return self.report

    def __generate_report(self, output):
        return {
            "result": output,
            "suggested_registers": self.suggested_registers,
            "message": self.get_result_msg(output)
        }

    @abstractmethod
    def get_result_msg(self, output):
        pass
