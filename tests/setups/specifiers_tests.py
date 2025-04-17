from tests.setups.rack_service_client import RackServiceClient
from tests.setups.rack_specifiers import ECAT_CAP_SETUP
from tests.setups.specifiers import RackServiceConfigSpecifier

if __name__ == "__main__":
    specifier: RackServiceConfigSpecifier = ECAT_CAP_SETUP
    print("starting connection")
    client: RackServiceClient = RackServiceClient(job_name="jp_test")
    print("connected")

    specifier.rack_service_client = client

    descriptor = specifier.get_descriptor()

    print(descriptor)

    client.teardown()
