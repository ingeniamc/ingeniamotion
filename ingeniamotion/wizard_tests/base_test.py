import logging

from abc import ABC, abstractmethod
from ingenialink.exceptions import ILError


class TestError(Exception):
    pass


class BaseTest(ABC):

    def __init__(self):
        self.backup_registers_names = None
        self.backup_registers = {}
        self.suggested_registers = {}
        self.servo = None
        self.subnode = None

    def save_backup_registers(self):
        self.backup_registers[self.subnode] = {}
        for uid in self.backup_registers_names:
            try:
                self.backup_registers[self.subnode][uid] = self.servo.read(uid, subnode=self.subnode)
            except ILError as e:
                logging.warning(e)

    def restore_backup_registers(self):
        """ Restore the value of the registers after the test execution.

        Notes:
        This should only be called by the Wizard.
        """
        for subnode, registers in self.backup_registers.items():
            for key, value in self.backup_registers[subnode].items():
                try:
                    self.servo.raw_write(key, value, subnode=subnode)
                except ILError as e:
                    logging.warning(e)

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
        self.save_backup_registers()
        try:
            self.setup()
            output = self.loop()
            self.teardown()
        except TestError as e:
            logging.error(e)
            return -1
        finally:
            self.restore_backup_registers()

        return {
            "result": output,
            "suggested_registers": self.suggested_registers,
            "message": self.get_result_msg(output)
        }

    @abstractmethod
    def get_result_msg(self, output):
        pass
