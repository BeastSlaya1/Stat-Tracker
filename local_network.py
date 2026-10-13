"""Find local IPv4 addresses on Wi-Fi, USB tethering and Ethernet adapters."""
import ctypes
import ipaddress
import os
import socket

LOCAL_NETWORKS=tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','127.0.0.0/8'))

def is_local_ipv4(value):
    try:
        address=ipaddress.ip_address(value)
        return address.version==4 and not address.is_unspecified and not address.is_multicast and any(address in n for n in LOCAL_NETWORKS)
    except ValueError:return False

def _native_addresses():
    values=set()
    if os.name=='nt':
        class SocketAddress(ctypes.Structure):
            _fields_=[('address',ctypes.c_void_p),('length',ctypes.c_int)]
        class Unicast(ctypes.Structure):pass
        Unicast._fields_=[('alignment',ctypes.c_uint64),('next',ctypes.POINTER(Unicast)),('socket',SocketAddress)]
        class Adapter(ctypes.Structure):pass
        Adapter._fields_=[('alignment',ctypes.c_uint64),('next',ctypes.POINTER(Adapter)),('name',ctypes.c_char_p),('unicast',ctypes.POINTER(Unicast)),('anycast',ctypes.c_void_p),('multicast',ctypes.c_void_p),('dns',ctypes.c_void_p),('dns_suffix',ctypes.c_void_p),('description',ctypes.c_void_p),('friendly_name',ctypes.c_void_p),('physical',ctypes.c_ubyte*8),('physical_length',ctypes.c_ulong),('flags',ctypes.c_ulong),('mtu',ctypes.c_ulong),('if_type',ctypes.c_ulong),('oper_status',ctypes.c_int)]
        size=ctypes.c_ulong(16384)
        api=ctypes.WinDLL('iphlpapi').GetAdaptersAddresses
        api.argtypes=[ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        api.restype=ctypes.c_ulong
        for _ in range(3):
            buffer=ctypes.create_string_buffer(size.value)
            result=api(socket.AF_INET,0,None,buffer,ctypes.byref(size))
            if result==111:continue
            if result:return values
            adapter=ctypes.cast(buffer,ctypes.POINTER(Adapter))
            while adapter:
                item=adapter.contents.unicast if adapter.contents.oper_status==1 else None
                while item:
                    entry=item.contents.socket
                    if entry.address and entry.length>=8:values.add(socket.inet_ntoa(ctypes.string_at(entry.address+4,4)))
                    item=item.contents.next
                adapter=adapter.contents.next
            break
    else:
        class Interface(ctypes.Structure):pass
        Interface._fields_=[('next',ctypes.POINTER(Interface)),('name',ctypes.c_char_p),('flags',ctypes.c_uint),('address',ctypes.c_void_p),('netmask',ctypes.c_void_p),('destination',ctypes.c_void_p),('data',ctypes.c_void_p)]
        libc=ctypes.CDLL(None);head=ctypes.POINTER(Interface)()
        libc.getifaddrs.argtypes=[ctypes.POINTER(ctypes.POINTER(Interface))];libc.getifaddrs.restype=ctypes.c_int
        libc.freeifaddrs.argtypes=[ctypes.POINTER(Interface)]
        if libc.getifaddrs(ctypes.byref(head))!=0:return values
        try:
            item=head
            while item:
                row=item.contents
                if row.address and row.flags&1:
                    raw=ctypes.string_at(row.address,8)
                    # Linux/Android use a native ushort family; Apple uses length,family.
                    family=raw[1] if __import__('sys').platform in ('darwin','ios') else int.from_bytes(raw[:2],__import__('sys').byteorder)
                    if family==socket.AF_INET:values.add(socket.inet_ntoa(raw[4:8]))
                item=row.next
        finally:libc.freeifaddrs(head)
    return values

def local_ipv4_addresses():
    values=set()
    try:values.update(_native_addresses())
    except (OSError,AttributeError,ValueError):pass
    try:values.update(row[4][0] for row in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
    except OSError:pass
    # Fallback for restricted platforms; UDP connect chooses a route without sending data.
    for destination in ('192.168.43.1','192.168.137.1','172.20.10.1','10.0.0.1'):
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.connect((destination,9));values.add(sock.getsockname()[0])
        except OSError:pass
    return sorted(value for value in values if is_local_ipv4(value) and not value.startswith('127.'))

CABLE_HELP = [
 ('Android ↔ computer','Use a data-capable USB cable. Enable USB tethering in Android’s hotspot/tethering settings, then scan for shared matches. Driver and phone support vary; some phones require mobile data enabled to start tethering.'),
 ('iPhone/iPad ↔ computer','Apple USB Personal Hotspot requires supported cellular service/settings; Windows needs Apple Devices or iTunes and device trust. It is not a guaranteed fully offline USB network. For a fully offline setup, use supported Ethernet adapters on a local router/switch.'),
 ('Other wired connections','Connect supported USB-to-Ethernet adapters to the same local router or switch. The network needs local IP addresses but does not need internet. An ordinary USB cable between two computers or two phones usually does not create a network.'),
 ('Share without internet','Sign in before going offline. Host opens a saved match, starts sharing and turns on the camera. Other devices scan, request connection and wait for approval. Stats, clock and video then stay on the local network. Native Apple app support is still in preparation.'),
 ('If scanning finds nothing','Check that tethering/Ethernet is active and the host app is open. Allow the app on the private network if prompted. Use Manual connection with one of the host addresses and join code. A network with device isolation can block sharing.'),
]
