import json
from pathlib import Path
from typing import Union

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


class FSoEDictionaryMapJSONSerializer:
    """Class to handle serialization and deserialization of FSoE dictionary maps."""

    @staticmethod
    def serialize_mapping_to_dict(
        handler: FSoEMasterHandler,
    ) -> dict[str, list[dict[str, Union[str, int]]]]:
        """Serialize the current mapping to a dictionary for JSON storage.

        Args:
            handler: The FSoE master handler with the mapping to serialize.

        Returns:
            Dictionary containing the serialized mapping data.
        """
        mapping_data: dict[str, list[dict[str, Union[str, int]]]] = {"inputs": [], "outputs": []}

        # Serialize inputs and outputs mapping
        for item_key, item in zip(
            ["inputs", "outputs"], [handler.maps.inputs, handler.maps.outputs]
        ):
            for item in item:
                # FSoE dictionary item
                if hasattr(item, "uid"):
                    item_data = {
                        "type": "item",
                        "uid": item.uid,
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
        handler: FSoEMasterHandler, mapping_data: dict[str, list[dict[str, Union[str, int]]]]
    ) -> None:
        """Loads a mapping from a dictionary into the FSoE master handler.

        Args:
            handler: The FSoE master handler to load the mapping into.
            mapping_data: Dictionary containing the serialized mapping data.
        """
        # Clear existing mappings
        handler.maps.inputs.clear()
        handler.maps.outputs.clear()

        # Load inputs and outputs mapping
        for item_key, item in zip(
            ["inputs", "outputs"], [handler.maps.inputs, handler.maps.outputs]
        ):
            for item_data in mapping_data[item_key]:
                if item_data["type"] == "item":
                    if item_data["uid"] in handler.dictionary.name_map:
                        fsoe_item = handler.dictionary.name_map[item_data["uid"]]
                        item.add(fsoe_item)
                elif item_data["type"] == "padding":
                    item.add_padding(item_data["bits"])

    @staticmethod
    def save_mapping_to_json(
        handler: FSoEMasterHandler, filename: Path, override: bool = False
    ) -> None:
        """Save the current mapping to a JSON file.

        Args:
            handler: The FSoE master handler with the mapping to save.
            filename: Path to the JSON file to save.
            override: If True, will overwrite existing file. Defaults to False.

        Raises:
            FileExistsError: If override is False and the file already exists.
        """
        mapping_data = FSoEDictionaryMapJSONSerializer.serialize_mapping_to_dict(handler)
        if override:
            filename.unlink(missing_ok=True)
        if filename.exists():
            raise FileExistsError(f"File {filename} already exists.")

        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as f:
            json.dump(mapping_data, f, indent=2)

    @staticmethod
    def load_mapping_from_json(handler: FSoEMasterHandler, filename: Path) -> None:
        """Load a mapping from a JSON file into the FSoE master handler.

        Args:
            handler: The FSoE master handler to load the mapping into.
            filename: Path to the JSON file to load.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
        """
        if not filename.exists():
            raise FileNotFoundError(f"Mapping file {filename} does not exist.")

        with open(filename) as f:
            mapping_data = json.load(f)
        FSoEDictionaryMapJSONSerializer.load_mapping_from_dict(handler, mapping_data)
