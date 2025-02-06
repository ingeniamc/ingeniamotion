from GetAdaptersInfo cimport *
from libc.stdlib cimport malloc, free

cdef class CyGetAdapterInfo:

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
            


        free(adapter_info)


