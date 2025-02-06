from GetAdaptersInfo cimport *
from libc.stdlib cimport malloc, free
from typing import NamedTuple

class CyAdapter(NamedTuple):
    ComboIndex: int
    AdapterName: str
    Description: str
    AddressLength: int
    Address: bytes

cdef class CyGetAdapterInfo:
    cdef list _parse_adapters(self, IP_ADAPTER_INFO* adapter_info):
        cdef IP_ADAPTER_INFO* current_adapter = adapter_info
        adapters_list = []

        while current_adapter:
            parsed_adapter = CyAdapter(
                ComboIndex=current_adapter.ComboIndex,
                AdapterName=current_adapter.AdapterName.decode("utf-8"),
                Description=current_adapter.Description.decode("utf-8"),
                AddressLength=current_adapter.AddressLength,
                Address='-'.join(f"{b:02X}" for b in current_adapter.Address),
            )
            adapters_list.append(parsed_adapter)
            current_adapter = current_adapter.Next

        return adapters_list

    def get_adapters_info(self):
        cdef unsigned long dwRetVal  = 0
        cdef unsigned long out_buf_len = sizeof(IP_ADAPTER_INFO)
        cdef IP_ADAPTER_INFO* adapter_info = <IP_ADAPTER_INFO*> malloc(sizeof(IP_ADAPTER_INFO))

        if adapter_info == NULL:
            raise MemoryError("Error allocating initial memory for GetAdaptersInfo")

        dwRetVal = GetAdaptersInfo(adapter_info, &out_buf_len)
        if dwRetVal == ERROR_BUFFER_OVERFLOW:
            free(adapter_info)
            adapter_info = <IP_ADAPTER_INFO*> malloc(out_buf_len)
            if adapter_info == NULL:
                raise MemoryError("Error allocating memory for GetAdaptersInfo")

            dwRetVal = GetAdaptersInfo(adapter_info, &out_buf_len)

        if dwRetVal != NO_ERROR:
            free(adapter_info)
            raise OSError("GetAdaptersInfo failed with error code {}".format(dwRetVal))
            
        adapters = self._parse_adapters(adapter_info)

        free(adapter_info)
        return adapters


