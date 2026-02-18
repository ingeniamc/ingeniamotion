from __future__ import annotations

import warnings
from collections.abc import Iterator, MutableMapping
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any

from ingenialink.servo import Servo

from ingeniamotion.capture import Capture
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.errors import Errors
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEMaster
from ingeniamotion.information import Information
from ingeniamotion.input_output import InputsOutputs
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.motion import Motion

if TYPE_CHECKING:
    from ingenialink.network import Network


class _ServosProxy(MutableMapping[str, Servo]):
    """Proxy around MotionController._servos that warns on mutation.

    Read operations forward to the internal dict. Mutating operations
    emit a DeprecationWarning and either delegate to MotionController
    lifecycle helpers or perform the minimal compatible change.
    """

    def __init__(self, mc: MotionController) -> None:
        self._mc = mc

    def __getitem__(self, key: str) -> Servo:
        return self._mc._servos[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mc._servos)

    def __len__(self) -> int:
        return len(self._mc._servos)

    def __contains__(self, key: object) -> bool:
        return key in self._mc._servos

    def __setitem__(self, key: str, value: Servo) -> None:
        warnings.warn(
            "Mutating MotionController.servos is deprecated; use _add_motion_node",
            DeprecationWarning,
            stacklevel=2,
        )
        self._mc._add_motion_node(key, value)

    def __delitem__(self, key: str) -> None:
        warnings.warn(
            "Mutating MotionController.servos is deprecated; use _remove_motion_node",
            DeprecationWarning,
            stacklevel=2,
        )
        self._mc._remove_motion_node(key)

    def pop(self, key: str, default: Any = None) -> Any:
        warnings.warn(
            "Mutating MotionController.servos is deprecated; use _remove_motion_node",
            DeprecationWarning,
            stacklevel=2,
        )
        if key in self._mc._servos:
            val = self._mc._servos[key]
            self._mc._remove_motion_node(key)
            return val
        return default

    def popitem(self) -> tuple[str, Servo]:
        warnings.warn(
            "Mutating MotionController.servos is deprecated; use _remove_motion_node",
            DeprecationWarning,
            stacklevel=2,
        )
        # Remove an arbitrary item
        key = next(iter(self._mc._servos))
        val = self._mc._servos[key]
        self._mc._remove_motion_node(key)
        return (key, val)

    def clear(self) -> None:
        warnings.warn(
            "Mutating MotionController.servos is deprecated; use _remove_motion_node",
            DeprecationWarning,
            stacklevel=2,
        )
        # Remove all servos via lifecycle removal
        for key in list(self._mc._servos.keys()):
            self._mc._remove_motion_node(key)


class MotionController:
    """Motion Controller."""

    def __init__(self) -> None:
        self._servos: dict[str, Servo] = {}  # TODO
        self._net: dict[str, Network] = {}  # TODO
        self._servo_net: dict[str, str] = {}  # TODO
        self.__config: Configuration = Configuration(self)
        self.__motion: Motion = Motion(self)
        self.__capture: Capture = Capture(self)
        self.__comm: Communication = Communication(self)
        self.__tests: DriveTests = DriveTests(self)
        self.__errors: Errors = Errors(self)
        self.__info: Information = Information(self)
        self.__io = InputsOutputs(self)
        self.__fsoe: FSoEMaster | None = None
        if FSOE_MASTER_INSTALLED:
            self._fsoe = FSoEMaster(self)  # TODO

    def servo_name(self, servo: str = DEFAULT_SERVO) -> str:
        """Get the servo name.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            The servo name.

        """
        drive = self._get_drive(servo)
        return "{} ({})".format(drive.info["product_code"], servo)

    def get_register_enum(
        self, register: str, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> IntEnum:
        """Get a register enum.

        Args:
            register: The register UID.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            The register enum as an IntEnum.

        """
        drive = self._get_drive(servo)
        enum_dict = drive.dictionary.registers(axis)[register].enums
        return IntEnum(register, enum_dict)

    def is_alive(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the servo is alive.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            ``True`` if the servo is alive, ``False`` otherwise.

        """
        drive = self._get_drive(servo)
        return drive.is_alive()

    def _get_network(self, servo: str) -> Network:
        """Return servo network instance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Network instance of the servo.

        """
        net_key = self.servo_net[servo]
        return self.net[net_key]

    def _get_drive(self, servo: str = DEFAULT_SERVO) -> Servo:
        """Return servo drive instance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Servo instance.

        Raises:
            KeyError: If the servo is not connected.

        """
        if servo not in self.servos:
            msg = f"Servo {servo} is not connected"
            raise KeyError(msg)
        return self.servos[servo]

    def _add_motion_node(self, alias: str, servo: Servo, net_alias: str | None = None) -> None:
        """Helper to register a newly connected servo and its network.

        If ``net_alias`` is omitted the controller will register the servo
        but will not modify the internal servo->network mapping. Callers
        that need the network association must provide ``net_alias``.

        Args:
            alias: alias used to reference the servo.
            servo: the connected `ingenialink.Servo` instance.
            net_alias: optional network alias where the servo is connected.
        """
        # Always register servo instance
        self._servos[alias] = servo

        # Only set mapping when an explicit network alias is provided
        if net_alias is not None:
            self._servo_net[alias] = net_alias

    def _remove_motion_node(self, alias: str) -> None:
        """Helper to unregister a servo and cleanup its network.

        This will remove the servo from the internal registry, remove the
        servo->network mapping, delete the FSoE master handler for the
        servo if present, and delete the network entry when no more servos
        use it.

        Args:
            alias: alias used to reference the servo to remove.
        """
        if alias not in self._servos:
            return

        # Remove servo entry
        del self._servos[alias]

        # Remove servo->network mapping
        net_name = self._servo_net.pop(alias)

        # Remove FSoE handler if installed
        if self._fsoe is not None:
            self._fsoe._delete_master_handler(alias)

        # If no servos remain on this network, remove the network entry
        servo_count = list(self._servo_net.values()).count(net_name)
        if servo_count == 0 and net_name in self._net:
            del self._net[net_name]

    # Properties
    @cached_property
    def servos(self) -> MutableMapping[str, Servo]:
        """Mapping of ``ingenialink.Servo`` connected indexed by alias.

        Returns a proxy that behaves like a dict for reads but emits
        deprecation warnings when callers attempt to mutate it. Use
        `._add_motion_node` and `._remove_motion_node` for explicit
        lifecycle management.
        """
        return self._servos_proxy

    @servos.setter
    def servos(self, value: dict[str, Servo]) -> None:
        warnings.warn(
            "Direct assignment to MotionController.servos is deprecated; "
            "use MotionController._add_motion_node and MotionController._remove_motion_node instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Delegate to the proxy so mutations go through the lifecycle API.
        # Clear existing entries and update via proxy to preserve mapping
        # semantics while emitting deprecation warnings.
        proxy = self._servos_proxy
        proxy.clear()
        for alias, servo in value.items():
            proxy[alias] = servo

    @cached_property
    def _servos_proxy(self) -> MutableMapping[str, Servo]:
        return _ServosProxy(self)

    @property
    def net(self) -> dict[str, Network]:
        """Dict of ``ingenialink.Network`` connected indexed by alias."""
        return self._net

    @net.setter
    def net(self, value: dict[str, Network]) -> None:
        self._net = value

    @property
    def servo_net(self) -> dict[str, str]:
        """Get the servo network dictionary.

        Returns:
            The servo network dictionary.

        """
        return self._servo_net

    @servo_net.setter
    def servo_net(self, value: dict[str, str]) -> None:
        self._servo_net = value

    @property
    def configuration(self) -> Configuration:
        """Instance of  :class:`~ingeniamotion.configuration.Configuration` class."""
        return self.__config

    @property
    def motion(self) -> Motion:
        """Instance of  :class:`~ingeniamotion.motion.Motion` class."""
        return self.__motion

    @property
    def capture(self) -> Capture:
        """Instance of  :class:`~ingeniamotion.capture.Capture` class."""
        return self.__capture

    @property
    def communication(self) -> Communication:
        """Instance of  :class:`~ingeniamotion.communication.Communication` class."""
        return self.__comm

    @property
    def tests(self) -> DriveTests:
        """Instance of  :class:`~ingeniamotion.drive_tests.DriveTests` class."""
        return self.__tests

    @property
    def errors(self) -> Errors:
        """Instance of :class:`~ingeniamotion.errors.Errors` class."""
        return self.__errors

    @property
    def info(self) -> Information:
        """Instance of :class:`~ingeniamotion.errors.Information` class."""
        return self.__info

    @property
    def fsoe(self) -> FSoEMaster:
        """Instance of :class:`~ingeniamotion.fsoe.FSoEMaster` class."""
        if self._fsoe is None:
            raise NotImplementedError(
                "The FSoE module is not available. "
                "Install ingeniamotion with FSoE feature: "
                "pip install ingeniamotion[FSoE]"
            )
        return self._fsoe

    @property
    def fsoe_is_installed(self) -> bool:
        """Indicates if the FSoE Module is available."""
        return self._fsoe is not None

    @property
    def io(self) -> InputsOutputs:
        """Instance of :class:`~ingeniamotion.input_output.InputsOutputs` class."""
        return self.__io
