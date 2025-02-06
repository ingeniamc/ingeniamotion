"""
Wrapper for GetAdaptersInfo function (iphlpapi.h).
"""

cdef extern from "windows.h":
    pass


cdef extern from "winerror.h":
    enum:
        ERROR_BUFFER_OVERFLOW
        NO_ERROR

cdef extern from "iptypes.h":
    # https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/NetworkManagement/IpHelper/index.html
    # Use an enum -> they are defined as constants in "iptypes.h", but they can not be used in the struct (Not allowed in a constant expression)
    enum:
        MAX_ADAPTER_DESCRIPTION_LENGTH
        MAX_ADAPTER_NAME_LENGTH
        MAX_ADAPTER_ADDRESS_LENGTH

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
        char IpAddressList
        char GatewayList
        char DhcpServer
        int HaveWins
        char PrimaryWinsServer
        char SecondaryWinsServer
        long LeaseObtained
        long LeaseExpires

    ctypedef _IP_ADAPTER_INFO IP_ADAPTER_INFO
    ctypedef _IP_ADAPTER_INFO* PIP_ADAPTER_INFO

# https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersinfo
cdef extern from "iphlpapi.h":
    unsigned long GetAdaptersInfo(IP_ADAPTER_INFO* pAdapterInfo, unsigned long* pOutBufLen) except +