"""Local broadcast discovery; approval and data transfer still use authenticated HTTP."""
import json
import ipaddress
import socket
import threading
import time
from local_network import is_local_ipv4

PORT=8771
MAGIC=b'STAT_TRACKER_FIND_MATCH_V1'

class MatchBeacon:
    def __init__(self,hub):
        self.hub=hub;self.socket=None;self.closed=threading.Event()
    def start(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind(('0.0.0.0',PORT));sock.settimeout(.25)
        except OSError:sock.close();return
        self.socket=sock;threading.Thread(target=self.run,daemon=True).start()
    def run(self):
        sock=self.socket
        while not self.closed.is_set():
            try:
                data,peer=sock.recvfrom(256)
                if data!=MAGIC or not is_local_ipv4(peer[0]) or self.hub.hidden or self.hub.closed:continue
                server=self.hub.server
                if server:sock.sendto(json.dumps({'protocol':'stat-tracker-match-v1','port':server.server_port}).encode(),peer)
            except socket.timeout:continue
            except OSError:return
    def stop(self):
        self.closed.set()
        if self.socket:self.socket.close();self.socket=None

def discovery_targets(ip):
    network=ipaddress.ip_network(f'{ip}/24',strict=False)
    # Directed broadcasts and unicast also cover hotspot adapters that drop
    # limited broadcasts. No dependency on internet or Feem's file protocol.
    return sorted({'255.255.255.255',str(network.broadcast_address),
                   str(network.network_address+1),str(network.broadcast_address-1)}-{ip})


def discover_addresses(interfaces,wait=1.5):
    """Use each local adapter and retry discovery; trust only reply source IPs."""
    import select
    sockets=[];found=set();destinations={}
    try:
        for ip in dict.fromkeys(interfaces):
            if not is_local_ipv4(ip) or ip.startswith('127.'):continue
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                sock.bind((ip,0));sock.setblocking(False)
                sockets.append(sock);destinations[sock]=discovery_targets(ip)
            except OSError:sock.close()
        end=time.monotonic()+wait;next_send=0
        while sockets and time.monotonic()<end:
            now=time.monotonic()
            if now>=next_send:
                for sock in sockets:
                    for destination in destinations[sock]:
                        try:sock.sendto(MAGIC,(destination,PORT))
                        except OSError:pass
                next_send=now+.5
            ready,_,_=select.select(sockets,[],[],max(0,min(end,next_send)-time.monotonic()))
            for sock in ready:
                try:
                    raw,peer=sock.recvfrom(512);data=json.loads(raw)
                    port=data.get('port')
                    if data.get('protocol')=='stat-tracker-match-v1' and type(port)==int and 0<port<65536 and is_local_ipv4(peer[0]):found.add(f'http://{peer[0]}:{port}')
                except (OSError,ValueError,AttributeError):continue
        return sorted(found)
    finally:
        for sock in sockets:sock.close()
