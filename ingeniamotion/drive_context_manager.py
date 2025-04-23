from copy import deepcopy
from typing import Optional

from ingenialink.dictionary import Dictionary

from ingeniamotion import MotionController
from ingeniamotion.metaclass import DEFAULT_SERVO


class DriveContextManager:
    """Context used to make modifications in the drive.

    Once the modifications are not needed anymore, the drive values will be restored.
    """

    def __init__(
        self,
        motion_controller: MotionController,
        servo: str = DEFAULT_SERVO,
        axis: Optional[int] = None,
    ):
        self._mc: MotionController = motion_controller
        self._servo: str = servo
        self._axis: Optional[int] = axis

        self._original_dictionary: Dictionary

    def _save_drive_values(self) -> None:
        drive = self._mc._get_drive(self._servo)
        self._original_dictionary = deepcopy(drive.dictionary)

    def _restore_drive_values(self) -> None:
        # TODO
        return

    def __enter__(self) -> None:
        """Saves the drive values."""
        self._save_drive_values()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Restores the drive values."""
        self._restore_drive_values()
