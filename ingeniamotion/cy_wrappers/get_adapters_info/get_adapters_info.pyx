from GetAdaptersInfo cimport *
from libc.stdlib cimport malloc, free
from typing import Optional
import dataclasses
import cython

cpdef enum CyAdapterType:
    ETHERNET = 0
    TOKENRING = 1
    FDDI = 2
    PPP = 3
    LOOPBACK = 4
    SLIP = 5
    OTHER = 6
    UNKNOWN = 7

@cython.cclass
@dataclasses.dataclass
class CyIpAddreString:
    IpAddress: str
    IpMask: str
    Context: int

@cython.cclass
@dataclasses.dataclass
class CyAdapter:
    ComboIndex: int
    AdapterName: str
    Description: str
    AddressLength: int
    Address: str
    Index: int
    Type: CyAdapterType
    DhcpEnabled: int
    IpAddressList: CyIpAddreString
    GatewayList: CyIpAddreString
    DhcpServer: Optional[CyIpAddreString]
    HaveWins: bool
    PrimaryWinsServer: CyIpAddreString
    SecondaryWinsServer: CyIpAddreString
    LeaseObtained: float
    LeaseExpires: float


cdef class CyGetAdapterInfo:
    cdef CyIpAddreString _parse_ip_addr_string(self, IP_ADDR_STRING data):
        return CyIpAddreString(
            IpAddress=data.IpAddress.String.decode("utf-8"),
            IpMask=data.IpMask.String.decode("utf-8"),
            Context=data.Context,
        )

    cdef CyAdapterType _parse_adapter_type(self, IP_ADAPTER_INFO* adapter):
        if adapter.Type == MIB_IF_TYPE_OTHER:
            return CyAdapterType.OTHER
        elif adapter.Type == MIB_IF_TYPE_ETHERNET:
           return CyAdapterType.ETHERNET
        elif adapter.Type == MIB_IF_TYPE_TOKENRING:
           return CyAdapterType.TOKENRING
        elif adapter.Type == MIB_IF_TYPE_FDDI:
           return CyAdapterType.FDDI
        elif adapter.Type == MIB_IF_TYPE_PPP:
           return CyAdapterType.PPP
        elif adapter.Type == MIB_IF_TYPE_LOOPBACK:
           return CyAdapterType.LOOPBACK
        elif adapter.Type == MIB_IF_TYPE_SLIP:
           return CyAdapterType.SLIP
        return CyAdapterType.UNKNOWN

    cdef list _parse_adapters(self, IP_ADAPTER_INFO* adapter_info):
        cdef IP_ADAPTER_INFO* current_adapter = adapter_info
        adapters_list = []

        while current_adapter:
            if current_adapter.DhcpEnabled:
                dchp_server = self._parse_ip_addr_string(current_adapter.DhcpServer)
            else:
                dchp_server = None
            parsed_adapter = CyAdapter(
                ComboIndex=current_adapter.ComboIndex,
                AdapterName=current_adapter.AdapterName.decode("utf-8"),
                Description=current_adapter.Description.decode("utf-8"),
                AddressLength=current_adapter.AddressLength,
                Address='-'.join(f"{b:02X}" for b in current_adapter.Address),
                Index=current_adapter.Index,
                Type=self._parse_adapter_type(current_adapter),
                DhcpEnabled=current_adapter.DhcpEnabled,
                IpAddressList=self._parse_ip_addr_string(current_adapter.IpAddressList),
                GatewayList=self._parse_ip_addr_string(current_adapter.GatewayList),
                DhcpServer=dchp_server,
                HaveWins=current_adapter.HaveWins,
                PrimaryWinsServer=self._parse_ip_addr_string(current_adapter.PrimaryWinsServer),
                SecondaryWinsServer=self._parse_ip_addr_string(current_adapter.SecondaryWinsServer),
                LeaseObtained=current_adapter.LeaseObtained,
                LeaseExpires=current_adapter.LeaseExpires,
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


