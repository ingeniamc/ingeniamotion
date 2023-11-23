import pytest


@pytest.mark.eoe
def test_disturbance_example(read_config, script_runner):
    script_path = "examples/disturbance_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(
        [script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}"]
    )
    assert result.returncode == 0
