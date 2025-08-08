from typing import TYPE_CHECKING, Union

from ingenialink import RegDtype
from typing_extensions import override

from ingeniamotion.fsoe_master.fsoe import FSoEApplicationParameter, FSoEDataType

if TYPE_CHECKING:
    from ingenialink.ethercat.register import EthercatRegister
    from ingenialink.ethercat.servo import EthercatServo

__all__ = ["SafetyParameter", "SafetyParameterDirectValidation"]

PARAM_VALUE_TYPE = Union[int, float, str, bytes]


class SafetyParameter:
    """Safety Parameter.

    Represents a parameter that modifies how the safety application works.

    Base class is used for modules that use SRA CRC Check mechanism.
    """

    def __init__(self, register: "EthercatRegister", servo: "EthercatServo"):
        self.__register = register
        self.__servo = servo

        self.__value = servo.read(register)

    @property
    def register(self) -> "EthercatRegister":
        """Get the register associated with the safety parameter."""
        return self.__register

    def get(self) -> PARAM_VALUE_TYPE:
        """Get the value of the safety parameter.

        Returns:
            The value of the safety parameter.
        """
        return self.__value

    def set(self, value: PARAM_VALUE_TYPE) -> None:
        """Set the value of the safety parameter."""
        self.__servo.write(self.__register, value)
        self.__value = value

    def is_mismatched(self) -> tuple[bool, PARAM_VALUE_TYPE, PARAM_VALUE_TYPE]:
        """Check if the safety parameter value is mismatched.

        Returns:
            A tuple with a boolean indicating if the value is mismatched,
            the master parameter value, and the value on the slave,
        """
        slave_value = self.__servo.read(self.__register)
        return self.__value != slave_value, self.__value, slave_value

    def set_without_updating(self, value: PARAM_VALUE_TYPE) -> None:
        """Set the value of the safety parameter without updating the drive internal value."""
        self.__value = value

    def set_to_slave(self) -> None:
        """Set the value of the safety parameter to the slave."""
        self.__servo.write(self.__register, self.__value)


IL_TO_FSOE_DATATYPES = {
    RegDtype.BOOL: FSoEDataType.BOOL,
    RegDtype.FLOAT: FSoEDataType.FLOAT,
    RegDtype.U8: FSoEDataType.UINT8,
    RegDtype.U16: FSoEDataType.UINT16,
    RegDtype.U32: FSoEDataType.UINT32,
    RegDtype.S8: FSoEDataType.INT8,
    RegDtype.S16: FSoEDataType.INT16,
    RegDtype.S32: FSoEDataType.INT32,
}


class SafetyParameterDirectValidation(SafetyParameter):
    """Safety Parameter with direct validation via FSoE.

    Safety Parameter that is validated directly via FSoE in application
     state instead of SRA CRC Check
    """

    def __init__(self, register: "EthercatRegister", drive: "EthercatServo"):
        super().__init__(register, drive)

        self.fsoe_application_parameter = FSoEApplicationParameter(
            name=register.identifier,
            initial_value=self.get(),
            data_type=IL_TO_FSOE_DATATYPES[register.dtype],
        )

    @override
    def set(self, value: Union[int, float, str, bytes]) -> None:
        super().set(value)
        self.fsoe_application_parameter.set(value)
