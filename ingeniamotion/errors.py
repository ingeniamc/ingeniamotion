from enum import IntEnum

from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Errors(metaclass=MCMetaClass):
    """Errors.
    """

    class ErrorLocation(IntEnum):
        COCO = 0
        MOCO = 1
        SYSTEM = 2

    LAST_ERROR_COCO_REGISTER = "DRV_DIAG_ERROR_LAST_COM"
    LAST_ERROR_MOCO_REGISTER = "DRV_DIAG_ERROR_LAST"
    LAST_ERROR_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_LAST"
    LAST_ERROR_REGISTER = {
        ErrorLocation.COCO: LAST_ERROR_COCO_REGISTER,
        ErrorLocation.MOCO: LAST_ERROR_MOCO_REGISTER,
        ErrorLocation.SYSTEM: LAST_ERROR_SYSTEM_REGISTER
    }
    ERROR_TOTAL_NUMBER_COCO_REGISTER = "DRV_DIAG_ERROR_TOTAL_COM"
    ERROR_TOTAL_NUMBER_MOCO_REGISTER = "DRV_DIAG_ERROR_TOTAL"
    ERROR_TOTAL_NUMBER_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_TOTAL_COM"
    ERROR_TOTAL_NUMBER_REGISTER = {
        ErrorLocation.COCO: ERROR_TOTAL_NUMBER_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_TOTAL_NUMBER_MOCO_REGISTER,
        ErrorLocation.SYSTEM: ERROR_TOTAL_NUMBER_SYSTEM_REGISTER
    }
    ERROR_LIST_INDEX_REQUEST_COCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX_COM"
    ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX"
    ERROR_LIST_INDEX_REQUEST_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_LIST_IDX_COM"
    ERROR_LIST_INDEX_REQUEST_REGISTER = {
        ErrorLocation.COCO: ERROR_LIST_INDEX_REQUEST_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER,
        ErrorLocation.SYSTEM: ERROR_LIST_INDEX_REQUEST_SYSTEM_REGISTER
    }
    ERROR_LIST_REQUESTED_COCO_CODE = "DRV_DIAG_ERROR_LIST_CODE_COM"
    ERROR_LIST_REQUESTED_MOCO_CODE = "DRV_DIAG_ERROR_LIST_CODE"
    ERROR_LIST_REQUESTED_SYSTEM_CODE = "DRV_DIAG_SYS_ERROR_LIST_CODE_COM"
    ERROR_LIST_REQUESTED_CODE = {
        ErrorLocation.COCO: ERROR_LIST_REQUESTED_COCO_CODE,
        ErrorLocation.MOCO: ERROR_LIST_REQUESTED_MOCO_CODE,
        ErrorLocation.SYSTEM: ERROR_LIST_REQUESTED_SYSTEM_CODE
    }

    MAXIMUM_ERROR_INDEX = 32

    STATUS_WORD_FAULT_BIT = 0x08
    STATUS_WORD_WARNING_BIT = 0x80

    ERROR_CODE_BITS = 0xFFFF
    ERROR_SUBNODE_BITS = 0xF00000
    ERROR_SUBNODE_SHIFT = 20
    ERROR_WARNING_BIT = 0x10000000
    ERROR_WARNING_SHIFT = 28

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def __parse_error_to_tuple(self, error, location, subnode=None):
        error_code = error & self.ERROR_CODE_BITS
        if error_code == 0:
            return error_code, None, None
        if subnode is None:
            if location == self.ErrorLocation.MOCO:
                subnode = DEFAULT_AXIS
            else:
                subnode = (error & self.ERROR_SUBNODE_BITS) >> self.ERROR_SUBNODE_SHIFT
        is_warning = (error & self.ERROR_WARNING_BIT) >> self.ERROR_WARNING_SHIFT
        return error_code, subnode, bool(is_warning)

    def __get_error_location(self, servo=DEFAULT_SERVO):
        if self.mc.info.register_exists(
                self.LAST_ERROR_SYSTEM_REGISTER, axis=0, servo=servo):
            # Check System last error, if it does not exist check to CoCo
            return self.ErrorLocation.SYSTEM
        if self.mc.info.register_exists(
                self.LAST_ERROR_COCO_REGISTER, axis=0, servo=servo):
            # Check CoCo last error, if it does not exist use MoCo
            return self.ErrorLocation.COCO
        return self.ErrorLocation.MOCO

    def __get_error_subnode(self, location, subnode):
        if location == self.ErrorLocation.SYSTEM:
            if subnode is None:
                return 0, location
            if subnode == 0:
                location = self.ErrorLocation.COCO
            if subnode > 0:
                location = self.ErrorLocation.MOCO
        if location == self.ErrorLocation.MOCO:
            return subnode or DEFAULT_AXIS, self.ErrorLocation.MOCO
        if location == self.ErrorLocation.COCO:
            return 0, self.ErrorLocation.COCO

    def get_last_error(self, servo=DEFAULT_SERVO, axis=None):
        """
        Return last servo error.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis force read errors in target axis. ``None`` by default.

        Returns:
            (int, int, bool): Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        """
        error_version = self.__get_error_location(servo)
        subnode, error_location = self.__get_error_subnode(error_version, axis)
        error = self.mc.communication.get_register(
            self.LAST_ERROR_REGISTER[error_location],
            servo=servo,
            axis=subnode
        )
        return self.__parse_error_to_tuple(error, error_version, axis)

    def get_last_buffer_error(self, servo=DEFAULT_SERVO, axis=None):
        """
        Get error code from error buffer last position.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis force read errors in target axis. ``None`` by default.

        Returns:
            (int, int, bool): Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        """
        return self.get_buffer_error_by_index(0, servo=servo, axis=axis)

    def get_buffer_error_by_index(self, index, servo=DEFAULT_SERVO,
                                  axis=None):
        """
        Get error code from buffer error target index.

        Args:
            index (int): buffer error index. It must be less than ``32``.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis force read errors in target axis. ``None`` by default.

        Returns:
            (int, int, bool): Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        """
        if index >= self.MAXIMUM_ERROR_INDEX:
            raise ValueError('index must be less than 32')
        error_version = self.__get_error_location(servo)
        subnode, error_location = self.__get_error_subnode(error_version, axis)
        self.mc.communication.set_register(
            self.ERROR_LIST_INDEX_REQUEST_REGISTER[error_location],
            index,
            servo=servo,
            axis=subnode
        )
        error = self.mc.communication.get_register(
            self.ERROR_LIST_REQUESTED_CODE[error_location],
            servo=servo,
            axis=subnode
        )
        return self.__parse_error_to_tuple(error, error_version, axis)

    def get_number_total_errors(self, servo=DEFAULT_SERVO, axis=None):
        """
        Return total number of drive errors.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis force read errors in target axis. ``None`` by default.

        Returns:
            int: Total number of errors.

        """
        error_version = self.__get_error_location(servo)
        subnode, error_location = self.__get_error_subnode(error_version, axis)
        return self.mc.communication.get_register(
            self.ERROR_TOTAL_NUMBER_REGISTER[error_location],
            servo=servo,
            axis=subnode
        )

    def get_all_errors(self, servo=DEFAULT_SERVO, axis=None):
        """
        Return list with all error codes.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis force read errors in target axis. ``None`` by default.

        Returns:
            list of tuple: List of all errors.

        """
        err_list = []
        err_num = self.get_number_total_errors(servo, axis)
        err_num = min(err_num, self.MAXIMUM_ERROR_INDEX)
        for i in range(err_num):
            error = self.get_buffer_error_by_index(i, servo=servo, axis=axis)
            err_list.append(error)
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

    def get_error_data(self, error_code, servo=DEFAULT_SERVO):
        """
        Return error info from target error_code.

        Args:
            error_code (int): target error code.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            (str, str, str, str): Returns error info.

            id (str):
                Error Id
            affected_module (str):
                Error affected module
            error_type (str):
                Error type
            error_message (str):
                Error message

        """
        drive = self.mc.servos[servo]
        return tuple(drive.errors[error_code & self.ERROR_CODE_BITS])
