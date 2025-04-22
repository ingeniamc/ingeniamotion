from tests.setups.rack_service_client import RackServiceClient
from tests.setups.rack_specifiers import ECAT_CAP_SETUP
from tests.setups.specifiers import RackServiceConfigSpecifier

if __name__ == "__main__":
    specifier: RackServiceConfigSpecifier = ECAT_CAP_SETUP
    client: RackServiceClient = RackServiceClient(job_name="jp_test")

    specifier.rack_service_client = client

    descriptor = specifier.get_descriptor()

    print(descriptor)  # noqa: T201

    client.teardown()
