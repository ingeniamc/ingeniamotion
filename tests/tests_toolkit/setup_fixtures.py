from pathlib import Path

import pytest

from tests.tests_toolkit import import_module_from_local_path
from tests.tests_toolkit.rack_service_client import RackServiceClient
from tests.tests_toolkit.setups import (
    MultiRackServiceConfigSpecifier,
    RackServiceConfigSpecifier,
    SetupSpecifier,
    descriptor_from_specifier,
)


@pytest.fixture(scope="session")
def connect_to_rack_service(request):
    rack_service_client = RackServiceClient(job_name=request.config.getoption("--job_name"))
    yield rack_service_client
    rack_service_client.teardown()


@pytest.fixture(scope="session")
def setup_specifier(request) -> SetupSpecifier:
    setup_location = Path(request.config.getoption("--setup").replace(".", "/"))
    setup_module = import_module_from_local_path(
        module_name=setup_location.parent.name,
        module_path=setup_location.parent.with_suffix(".py").resolve(),
    )
    return getattr(setup_module, setup_location.name)


@pytest.fixture(scope="session")
def setup_descriptor(setup_specifier, request) -> SetupSpecifier:
    if isinstance(setup_specifier, (RackServiceConfigSpecifier, MultiRackServiceConfigSpecifier)):
        rack_service_client = request.getfixturevalue("connect_to_rack_service")
    else:
        rack_service_client = None

    return descriptor_from_specifier(
        specifier=setup_specifier, rack_service_client=rack_service_client
    )
