from dataclasses import dataclass


@dataclass()
class FSoEFrameElements:
    """FSoE Frame Elements.

    Indicates uids of elements that compose the FSoE frame, excluding the safe data.
    """

    command_uid: str
    crcs_prefix: str
    connection_id_uid: str

    def get_crc_uid(self, data_slot_i: int) -> str:
        """Get the CRC element name for the given data slot index.

        Returns:
            The CRC element name for the given data slot index.
        """
        return f"{self.crcs_prefix}{data_slot_i}"


MASTER_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_MASTER_FRAME_ELEM_CMD",
    crcs_prefix="FSOE_MASTER_FRAME_ELEM_CRC",
    connection_id_uid="FSOE_MASTER_FRAME_ELEM_CONNID",
)


SLAVE_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_SLAVE_FRAME_ELEM_CMD",
    crcs_prefix="FSOE_SLAVE_FRAME_ELEM_CRC",
    connection_id_uid="FSOE_SLAVE_FRAME_ELEM_CONNID",
)
