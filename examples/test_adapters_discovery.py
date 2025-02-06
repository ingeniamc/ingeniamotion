from ingeniamotion.communication import Communication
from ingeniamotion.cy_wrappers.get_adapters_info.get_adapters_info import get_adapters_info

if __name__ == "__main__":
    print("\nCurrent method:")
    result = Communication.get_network_adapters()
    for idx, (description, name) in enumerate(result.items(), start=1):
        print(f"{idx} - {description}: {name}")

    print("\nWeapper method:")
    cy_adapters = get_adapters_info()
    for n_adapter, adapter in enumerate(cy_adapters, start=1):
        print(f"{n_adapter} - {adapter.Description}: {adapter.AdapterName}")
