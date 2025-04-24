def pytest_addoption(parser):
    parser.addoption(
        "--setup",
        action="store",
        default="tests.tests_setup.TESTS_SETUP",
        help="Module and location from which to import the setup."
        "It will default to a file that you can create on"
        "tests_setup.py inside of the folder setups with a variable called TESTS_SETUP"
        "This variable must define, or must be assigned to a Setup instance",
    )
    parser.addoption(
        "--job_name",
        action="store",
        default="test-toolkit Unknown",
        help="Name of the executing job. Will be set to rack service to have more info of the logs",
    )
