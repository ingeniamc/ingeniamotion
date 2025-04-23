from ingeniamotion.drive_context_manager import DriveContextManager


def test_drive_context_manager(motion_controller):
    mc, alias, environment = motion_controller
    context = DriveContextManager(motion_controller=mc)

    with context:
        aa = 0
