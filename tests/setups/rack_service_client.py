import time
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Optional

import rpyc
from rpyc.core.protocol import Connection
from rpyc.core.service import Service

RACK_SERVICE_PORT = 33810


class PartNumber(Enum):
    """Part numbers available for connection on rack."""

    EVE_XCR_C = "EVE-XCR-C"
    EVE_XCR_E = "EVE-XCR-E"
    CAP_XCR_C = "CAP-XCR-C"
    CAP_XCR_E = "CAP-XCR-E"


class RackServiceClient:
    """Rack service client.

    Handles all the interactions with the rack service."""

    _SLEEP_BETWEEN_POWER_CYCLE_S: float = 5
    _DRIVES_TURN_ON_TIMEOUT_S: float = 90

    def __init__(
        self,
        job_name: str,
        port: int = RACK_SERVICE_PORT,
        sync_request_timeout: Optional[int] = None,
    ):
        """Connects to rack service.

        Args:
            port: rack service port. Defaults to 33810.
            job_name: name of the executing job.
                Will be set to rack service to have more info of the logs.
            sync_request_timeout: Default timeout for waiting results. Defaults to None.
        """
        self.__client: Connection = RackServiceClient.connect_to_rack_service(
            port=port, job_name=job_name, sync_request_timeout=sync_request_timeout
        )

    @property
    def client(self) -> Service:
        """Rack service client."""
        return self.__client.root

    @cached_property
    def configuration(self) -> object:
        """Rack configuration."""
        return self.client.get_configuration()

    @staticmethod
    def connect_to_rack_service(
        port: int, job_name: str, sync_request_timeout: Optional[int] = None
    ) -> Connection:
        """Connects to rack service.

        Args:
            port: rack service port.
            job_name: name of the executing job.
                Will be set to rack service to have more info of the logs.
            sync_request_timeout: Default timeout for waiting results. Defaults to None.

        Returns:
            client.
        """
        client = rpyc.connect(
            "localhost", port, config={"sync_request_timeout": sync_request_timeout}
        )
        client.root.set_job_name(job_name)
        return client

    @staticmethod
    def close_connection(client: Connection) -> None:
        """Closes the connection to the rack service.

        Args:
            client: rack service client.
        """
        client.close()

    @property
    def are_nodes_ready(self) -> bool:
        """Returns True if all nodes have started, False otherwise."""
        network = self.configuration.networks[0]
        all_nodes_started, _ = network.all_nodes_started()
        return all_nodes_started

    def power_cycle(self, wait_for_drives: bool = True) -> None:
        """Performs a power cycle and waits for all drives to turn on.

        Args:
            wait_for_drives: True to wait for drives to turn on, False otherwise.
                Defaults to True.
        """
        self.client.turn_off_ps()
        time.sleep(self._SLEEP_BETWEEN_POWER_CYCLE_S)
        self.client.turn_on_ps()

        if not wait_for_drives:
            return

        wait_until = time.time() + self._DRIVES_TURN_ON_TIMEOUT_S
        while time.time() < wait_until:
            if self.are_nodes_ready:
                return
        raise TimeoutError(
            f"Could not find drives in {self._DRIVES_TURN_ON_TIMEOUT_S} after rebooting"
        )

    def get_drive(self, part_number: PartNumber) -> tuple[int, object]:
        """Retrieves a drive from the rack.

        Args:
            part_number: drive part number.

        Raises:
            ValueError: if the part number is not available on the rack.

        Returns:
            drive index, drive.
        """
        part_number_value = part_number.value
        for idx, drive in enumerate(self.configuration.drives):
            if part_number_value == drive.part_number:
                return idx, drive
        raise ValueError(f"Drive {part_number_value} cannot be found on the rack's configuration.")

    def get_dictionary(self, rack_drive_idx: int, firmware_version: str) -> Path:
        return self.client.get_dictionary(rack_drive_idx, firmware_version)

    def teardown(self) -> None:
        """Closes the connection to the rack service."""
        self.__client.close()
