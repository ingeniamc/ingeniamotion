"""Reproduce a position-feedback failure after enabling an EtherCAT drive."""

import argparse
import time
from pathlib import Path

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode

FAULT_BIT = 0x0008


def main() -> None:
    """Connect to a drive, enable the motor, and watch for a feedback error."""
    parser = argparse.ArgumentParser(
        description="Check position feedback immediately after motor enable."
    )
    parser.add_argument(
        "--ifname",
        required=True,
        help=r"EtherCAT interface name, for example \\Device\\NPF_{...}",
    )
    parser.add_argument("--slave_id", type=int, default=1)
    parser.add_argument("--dictionary_path", required=True, type=Path)
    parser.add_argument("--configuration_file", type=Path, default=None)
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()

    mc = MotionController()
    motor_enabled = False

    try:
        mc.communication.connect_servo_ethercat(
            args.ifname,
            args.slave_id,
            str(args.dictionary_path),
        )
        print("Drive connected")

        if args.configuration_file is not None:
            mc.configuration.load_configuration(str(args.configuration_file))
            print("Configuration loaded")

        initial_errors = mc.errors.get_all_errors()

        mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION)
        initial_position = mc.motion.get_actual_position()

        # Configure the current position before enabling the motor so that an
        # old profile-position target cannot become active during motor_enable().
        mc.motion.move_to_position(initial_position, blocking=False)
        configured_target = mc.communication.get_register("CL_POS_SET_POINT_VALUE")

        print(
            f"Before enable: position={initial_position}, "
            f"target={configured_target}, errors={initial_errors}"
        )

        enable_time = time.monotonic()
        mc.motion.motor_enable()
        motor_enabled = True

        print("Motor enabled")

        while time.monotonic() - enable_time < args.duration:
            position = mc.motion.get_actual_position()
            status_word = mc.communication.get_register("DRV_STATE_STATUS")
            errors = mc.errors.get_all_errors()

            if errors != initial_errors or status_word & FAULT_BIT:
                elapsed = time.monotonic() - enable_time
                print(
                    f"Failure reproduced after {elapsed:.3f} s: "
                    f"position={position}, status={hex(status_word)}, "
                    f"errors={errors}"
                )
                return

            time.sleep(0.01)

        print(f"No failure reproduced after {args.duration:.1f} s")

    finally:
        if motor_enabled:
            try:
                mc.motion.motor_disable()
            except Exception as exception:
                print(f"Could not disable motor: {exception}")

        try:
            mc.communication.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
