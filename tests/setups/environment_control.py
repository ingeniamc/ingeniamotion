from abc import ABC, abstractmethod

from virtual_drive.core import VirtualDrive


def set_bit(value, bit):
    return value | (1 << bit)


def clear_bit(value, bit):
    return value & ~(1 << bit)


class DriveEnvironmentController(ABC):
    """Abstract Environment Controller.

    Defines methods to control the environment state of the setup,
    which are not controlled by ingeniamotion communications, but are controlled by the user,
    or other hardware.
    """

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def set_gpi(self, number: int, value: bool):
        pass


class ManualUserEnvironmentController(ABC):
    # TODO
    def reset(self):
        pass

    def set_gpi(self):
        pass


class RackServiceEnvironmentController(DriveEnvironmentController):
    """Controller of the environment of Rack Service Setup"""

    def reset(self):
        pass

    def set_gpi(self, number: int, value: bool):
        # Test gpios in rack with rack service
        # https://novantamotion.atlassian.net/browse/INGM-514
        raise NotImplementedError


class VirtualDriveEnvironmentController(DriveEnvironmentController):
    """Controller of the environment of a Virtual Drive Setup"""

    def __init__(self, virtual_drive: VirtualDrive):
        self.virtual_drive = virtual_drive
        self.reset()

    def set_gpi(self, number: int, value: bool):
        io_value = self.virtual_drive.get_value_by_id(subnode=1, id="IO_IN_VALUE")

        if value:
            io_value = set_bit(io_value, bit=number - 1)
        else:
            io_value = clear_bit(io_value, bit=number - 1)

        self.virtual_drive.set_value_by_id(subnode=1, id="IO_IN_VALUE", value=io_value)

    def reset(self):
        self.virtual_drive.set_value_by_id(subnode=1, id="IO_IN_VALUE", value=0)
