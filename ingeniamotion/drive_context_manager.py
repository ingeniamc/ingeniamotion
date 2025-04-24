from typing import Optional, Union, cast

from ingenialink.enums.register import RegAccess
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import Servo

from ingeniamotion import MotionController
from ingeniamotion.metaclass import DEFAULT_SERVO


class DriveContextManager:
    """Context used to make modifications in the drive.

    Once the modifications are not needed anymore, the drive values will be restored.
    """

    def __init__(
        self,
        motion_controller: MotionController,
        alias: str = DEFAULT_SERVO,
        axis: Optional[int] = None,
    ):
        self._mc: MotionController = motion_controller
        self._alias: str = alias
        self._axis: Optional[int] = axis

        self._original_register_values: dict[int, dict[str, Union[int, float, str]]] = {}
        self._registers_changed: dict[int, dict[str, Union[int, float, str, bytes]]] = {}

    @property
    def drive(self) -> Servo:
        """Returns the servo."""
        return self._mc._get_drive(self._alias)

    def _register_update_callback(
        self,
        alias: str,  # noqa: ARG002
        servo: Servo,  # noqa: ARG002
        register: Register,
        value: Union[int, float, str, bytes],
    ) -> None:
        """Saves the register uids that are changed.

        Args:
            alias: servo alias.
            servo: servo.
            register: register.
            value: changed value.
        """
        if register.subnode not in self._registers_changed:
            self._registers_changed[register.subnode] = {}
        self._registers_changed[register.subnode][cast("str", register.identifier)] = value

    def _store_register_data(self) -> None:
        """It saves the value of all registers and subscribes to register update callbacks."""
        drive = self.drive
        axes = list(drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            self._original_register_values[axis] = {}
            for uid, register in drive.dictionary.registers(subnode=axis).items():
                if register.access == RegAccess.WO:
                    continue
                try:
                    register_value = self._mc.communication.get_register(
                        register=uid, servo=self._alias, axis=axis
                    )
                except ILIOError:
                    continue
                self._original_register_values[axis][uid] = register_value

        self._mc.communication.subscribe_register_update(
            self._register_update_callback, servo=self._alias
        )

    def _restore_register_data(self) -> None:
        """Unsubscribes from register updates and restores the drive values."""
        self._mc.communication.unsubscribe_register_update(
            self._register_update_callback, servo=self._alias
        )

        for axis, registers in self._registers_changed.items():
            for uid, current_value in registers.items():
                restore_value = self._original_register_values[axis].get(uid, None)
                if restore_value is None or current_value == restore_value:
                    continue
                self._mc.communication.set_register(
                    uid, restore_value, servo=self._alias, axis=axis
                )

    def __enter__(self) -> None:
        """Saves the drive values."""
        self._store_register_data()

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Restores the drive values."""
        self._restore_register_data()
