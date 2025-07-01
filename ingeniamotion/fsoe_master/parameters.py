from typing import TYPE_CHECKING, Union

from ingenialink.utils._utils import dtype_value
from typing_extensions import override

from ingeniamotion.fsoe_master.fsoe import FSoEApplicationParameter

if TYPE_CHECKING:
    from ingenialink.ethercat.register import EthercatRegister
    from ingenialink.ethercat.servo import EthercatServo

__all__ = ["SafetyParameter", "SafetyParameterDirectValidation"]


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

    def get(self) -> Union[int, float, str, bytes]:
        """Get the value of the safety parameter."""
        return self.__value

    def set(self, value: Union[int, float, str, bytes]) -> None:
        """Set the value of the safety parameter."""
        self.__servo.write(self.__register, value)
        self.__value = value


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
            # https://novantamotion.atlassian.net/browse/INGK-1104
            n_bytes=dtype_value[register.dtype][0],
        )

    @override
    def set(self, value: Union[int, float, str, bytes]) -> None:
        super().set(value)
        self.fsoe_application_parameter.set(value)
