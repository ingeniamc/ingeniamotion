import pytest


@pytest.mark.virtual
def test_fsoe_master_not_installed():
    try:
        import fsoe_master  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("fsoe_master is installed")
    import ingeniamotion

    mc = ingeniamotion.MotionController()
    with pytest.raises(NotImplementedError):
        mc.fsoe
