"""
Wrapper for GetAdaptersInfo function (iphlpapi.h).
"""
from libc.time cimport time_t

cdef extern from "windows.h":
    pass


cdef extern from "winerror.h":
    enum:
        ERROR_BUFFER_OVERFLOW
        NO_ERROR

cdef extern from "ipifcons.h":
    enum:
        MIB_IF_TYPE_OTHER
        MIB_IF_TYPE_ETHERNET
        MIB_IF_TYPE_TOKENRING
        MIB_IF_TYPE_FDDI
        MIB_IF_TYPE_PPP
        MIB_IF_TYPE_LOOPBACK
        MIB_IF_TYPE_SLIP

cdef extern from "iptypes.h":
    # https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/NetworkManagement/IpHelper/index.html
    # Use an enum -> they are defined as constants in "iptypes.h", but they can not be used in the struct (Not allowed in a constant expression)
    enum:
        MAX_ADAPTER_DESCRIPTION_LENGTH
        MAX_ADAPTER_NAME_LENGTH
        MAX_ADAPTER_ADDRESS_LENGTH

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_addr_string
    ctypedef struct _IP_ADDRESS_STRING:
        char String[64]

    ctypedef struct _IP_MASK_STRING:
        char String[64]

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_addr_string
    ctypedef struct _IP_ADDR_STRING:
        _IP_ADDR_STRING* Next
        _IP_ADDRESS_STRING IpAddress
        _IP_MASK_STRING IpMask
        unsigned long Context

    ctypedef _IP_ADDR_STRING IP_ADDR_STRING
    ctypedef _IP_ADDR_STRING* PIP_ADDR_STRING

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_info
    ctypedef struct _IP_ADAPTER_INFO:
        _IP_ADAPTER_INFO* Next
        unsigned long ComboIndex
        char AdapterName[MAX_ADAPTER_NAME_LENGTH + 4]
        char Description[MAX_ADAPTER_DESCRIPTION_LENGTH + 4]
        unsigned int AddressLength
        unsigned char Address[MAX_ADAPTER_ADDRESS_LENGTH]
        unsigned long Index
        unsigned int Type
        unsigned int DhcpEnabled
        void* CurrentIpAddress
        _IP_ADDR_STRING IpAddressList
        _IP_ADDR_STRING GatewayList
        _IP_ADDR_STRING DhcpServer
        int HaveWins
        _IP_ADDR_STRING PrimaryWinsServer
        _IP_ADDR_STRING SecondaryWinsServer
        time_t LeaseObtained
        time_t LeaseExpires

    ctypedef _IP_ADAPTER_INFO IP_ADAPTER_INFO
    ctypedef _IP_ADAPTER_INFO* PIP_ADAPTER_INFO

# https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersinfo
cdef extern from "iphlpapi.h":
    unsigned long GetAdaptersInfo(IP_ADAPTER_INFO* pAdapterInfo, unsigned long* pOutBufLen) except +