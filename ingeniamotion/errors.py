from enum import IntEnum
from ingenialink.exceptions import ILError

from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Errors(metaclass=MCMetaClass):
    """Errors
    """

    class ErrorLocation(IntEnum):
        COCO = 0
        MOCO = 1

    LAST_ERROR_COCO_REGISTER = "DRV_DIAG_ERROR_LAST_COM"
    LAST_ERROR_MOCO_REGISTER = "DRV_DIAG_ERROR_LAST"
    LAST_ERROR_REGISTER = {
        ErrorLocation.COCO: LAST_ERROR_COCO_REGISTER,
        ErrorLocation.MOCO: LAST_ERROR_MOCO_REGISTER
    }
    ERROR_TOTAL_NUMBER_COCO_REGISTER = "DRV_DIAG_ERROR_TOTAL_COM"
    ERROR_TOTAL_NUMBER_MOCO_REGISTER = "DRV_DIAG_ERROR_TOTAL"
    ERROR_TOTAL_NUMBER_REGISTER = {
        ErrorLocation.COCO: ERROR_TOTAL_NUMBER_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_TOTAL_NUMBER_MOCO_REGISTER
    }
    ERROR_LIST_INDEX_REQUEST_COCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX_COM"
    ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX"
    ERROR_LIST_INDEX_REQUEST_REGISTER = {
        ErrorLocation.COCO: ERROR_LIST_INDEX_REQUEST_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER
    }
    ERROR_LIST_REQUESTED_COCO_CODE = "DRV_DIAG_ERROR_LIST_CODE_COM"
    ERROR_LIST_REQUESTED_MOCO_CODE = "DRV_DIAG_ERROR_LIST_CODE"
    ERROR_LIST_REQUESTED_CODE = {
        ErrorLocation.COCO: ERROR_LIST_REQUESTED_COCO_CODE,
        ErrorLocation.MOCO: ERROR_LIST_REQUESTED_MOCO_CODE
    }

    STATUS_WORD_FAULT_BIT = 0x08
    STATUS_WORD_WARNING_BIT = 0x80

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def get_last_error(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return last servo error.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int: Last code error.
        """
        error_location = self.__get_error_location(servo)
        subnode = 0 if error_location == self.ErrorLocation.COCO else axis
        last_error = self.mc.communication.get_register(
            self.LAST_ERROR_REGISTER[error_location],
            servo=servo,
            axis=subnode
        )
        return last_error

    def get_number_total_errors(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return total number of drive errors.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int: Total number of errors.
        """
        error_location = self.__get_error_location(servo)
        subnode = 0 if error_location == self.ErrorLocation.COCO else axis
        num_errors = self.mc.communication.get_register(
            self.ERROR_TOTAL_NUMBER_REGISTER[error_location],
            servo=servo,
            axis=subnode
        )
        return num_errors

    def get_all_errors(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return list with all error codes.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            list of int: List of all errors.
        """
        err_list = []
        error_location = self.__get_error_location(servo)
        subnode = 0 if error_location == self.ErrorLocation.COCO else axis
        err_num = self.get_number_total_errors(servo, axis)
        for i in range(err_num):
            self.mc.communication.set_register(
                self.ERROR_LIST_INDEX_REQUEST_REGISTER[error_location],
                i,
                servo=servo,
                axis=subnode
            )
            err_code = self.mc.communication.get_register(
                self.ERROR_LIST_REQUESTED_CODE[error_location],
                servo=servo,
                axis=subnode
            )
            err_list.append(err_code)

        return err_list

    def is_fault_active(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return if fault is active.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            bool: ``True`` if fault is active, else ``False``.
        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_FAULT_BIT)

    def is_warning_active(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return if warning is active.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            bool: ``True`` if warning is active, else ``False``.
        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_WARNING_BIT)

    def __get_error_location(self, servo=DEFAULT_SERVO):
        # Try to read CoCo's last error, if it does not exist go to MoCo
        try:
            _ = self.mc.servos[servo].dict.get_regs(0)[self.LAST_ERROR_COCO_REGISTER]
            return self.ErrorLocation.COCO
        except ILError:
            return self.ErrorLocation.MOCO
