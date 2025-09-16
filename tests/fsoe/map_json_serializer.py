import json
from pathlib import Path
from typing import TYPE_CHECKING, Union

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if TYPE_CHECKING:
    from ingeniamotion.fsoe_master.fsoe import FSoEDictionaryMap

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.process_image import ProcessImage


class FSoEDictionaryMapJSONSerializer:
    """Class to handle serialization and deserialization of FSoE dictionary maps."""

    @staticmethod
    def serialize_mapping_to_dict(
        maps: "ProcessImage",
    ) -> dict[str, list[dict[str, Union[str, int]]]]:
        """Serialize the current mapping to a dictionary for JSON storage.

        Args:
            maps: The PDU maps with the mapping to serialize.

        Returns:
            Dictionary containing the serialized mapping data.
        """
        mapping_data: dict[str, list[dict[str, Union[str, int]]]] = {"inputs": [], "outputs": []}

        # Serialize inputs and outputs mapping
        for item_key, item in zip(["inputs", "outputs"], [maps.inputs, maps.outputs]):
            for item in item:
                # FSoE dictionary item
                if item.item is not None:
                    item_data = {
                        "type": "item",
                        "uid": item.item.name,
                    }
                # Padding
                else:
                    item_data = {
                        "type": "padding",
                        "bits": item.bits,
                    }
                mapping_data[item_key].append(item_data)

        return mapping_data

    @staticmethod
    def load_mapping_from_dict(
        dictionary: "FSoEDictionaryMap", mapping_data: dict[str, list[dict[str, Union[str, int]]]]
    ) -> "ProcessImage":
        """Loads a mapping from a dictionary into the PDU maps.

        Args:
            dictionary: The FSoE dictionary.
            mapping_data: Dictionary containing the serialized mapping data.

        Returns:
            ProcessImage: The PDU maps with the loaded mapping.
        """
        # Clear existing mappings
        maps = ProcessImage.empty(dictionary=dictionary)

        # Load inputs and outputs mapping
        for item_key, item in zip(["inputs", "outputs"], [maps.inputs, maps.outputs]):
            for item_data in mapping_data[item_key]:
                if item_data["type"] == "item":
                    if item_data["uid"] in dictionary.name_map:
                        fsoe_item = dictionary.name_map[item_data["uid"]]
                        item.add(fsoe_item)
                elif item_data["type"] == "padding":
                    item.add_padding(item_data["bits"])
        return maps

    @staticmethod
    def save_mapping_to_json(
        maps: "ProcessImage", filename: Path, override: bool = False
    ) -> dict[str, list[dict[str, Union[str, int]]]]:
        """Save the current mapping to a JSON file.

        Args:
            maps: The PDU maps with the mapping to save.
            filename: Path to the JSON file to save.
            override: If True, will overwrite existing file. Defaults to False.

        Returns:
            Dictionary containing the generated mapping data.

        Raises:
            FileExistsError: If override is False and the file already exists.
        """
        mapping_data = FSoEDictionaryMapJSONSerializer.serialize_mapping_to_dict(maps)
        if override:
            filename.unlink(missing_ok=True)
        if filename.exists():
            raise FileExistsError(f"File {filename} already exists.")

        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as f:
            json.dump(mapping_data, f, indent=2)
        return mapping_data

    @staticmethod
    def load_mapping_from_json(dictionary: "FSoEDictionaryMap", filename: Path) -> "ProcessImage":
        """Load a mapping from a JSON file into the FSoE dictionary.

        Args:
            dictionary: The FSoE dictionary.
            filename: Path to the JSON file to load.

        Returns:
            ProcessImage: The PDU maps with the loaded mapping.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
        """
        if not filename.exists():
            raise FileNotFoundError(f"Mapping file {filename} does not exist.")

        with open(filename) as f:
            mapping_data = json.load(f)
        return FSoEDictionaryMapJSONSerializer.load_mapping_from_dict(dictionary, mapping_data)
