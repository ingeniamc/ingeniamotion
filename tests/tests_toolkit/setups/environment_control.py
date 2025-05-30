from abc import ABC, abstractmethod
from typing import Optional

from virtual_drive.environment import Environment as VirtualDriveEnvironment


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


class ManualUserEnvironmentController(DriveEnvironmentController):
    def __init__(self, pytestconfig):
        self.pytestconfig = pytestconfig
        self.__capsys = (
            None  # Obtain during test execution. Can not be obtain during fixture creation
        )

    @property
    def capsys(self):
        if self.__capsys is None:
            self.__capsys = self.pytestconfig.pluginmanager.getplugin("capturemanager")
        return self.__capsys

    def reset(self):
        pass

    def __request_action_to_user(self, message: str):
        self.capsys.suspend_global_capture(in_=True)
        input(f"{message} [ENTER to confirm]")
        self.capsys.resume_global_capture()

    def set_gpi(self, number: int, value: bool):
        self.__request_action_to_user(f"Please, set gpi {number} to {value}")


class RackServiceEnvironmentController(DriveEnvironmentController):
    """Controller of the environment of Rack Service Setup"""

    def __init__(self, rack_service_client_root, default_drive_idx: Optional[int] = None):
        self.service = rack_service_client_root
        self.default_drive_idx = default_drive_idx

    def reset(self):
        pass

    def set_gpi(self, number: int, value: bool, drive_idx: Optional[int] = None):
        if drive_idx is None:
            drive_idx = self.default_drive_idx
        self.service.write_drive_gpio(drive_idx, f"GPI_{number}", int(value))


class VirtualDriveEnvironmentController(DriveEnvironmentController):
    """Controller of the environment of a Virtual Drive Setup"""

    def __init__(self, virtual_drive_environment: VirtualDriveEnvironment):
        self.__env = virtual_drive_environment
        self.reset()

    def set_gpi(self, number: int, value: bool):
        if number == 1:
            self.__env.gpi_1_status.set(value)
        elif number == 2:
            self.__env.gpi_2_status.set(value)
        elif number == 3:
            self.__env.gpi_3_status.set(value)
        elif number == 4:
            self.__env.gpi_4_status.set(value)
        else:
            raise ValueError

    def reset(self):
        self.__env.gpi_1_status.set(False)
        self.__env.gpi_2_status.set(False)
        self.__env.gpi_3_status.set(False)
        self.__env.gpi_4_status.set(False)
