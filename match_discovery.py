"""Local broadcast discovery; approval and data transfer still use authenticated HTTP."""
import json
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

def discover_addresses(interfaces,wait=1.0):
    """Only return source IPs of local replies; never accept a supplied redirect host."""
    import select
    sockets=[];found=set()
    try:
        for ip in interfaces:
            if not is_local_ipv4(ip) or ip.startswith('127.'):continue
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind((ip,0));sock.setblocking(False)
                sock.sendto(MAGIC,('255.255.255.255',PORT));sockets.append(sock)
            except OSError:sock.close()
        end=time.monotonic()+wait
        while sockets and time.monotonic()<end:
            ready,_,_=select.select(sockets,[],[],max(0,end-time.monotonic()))
            for sock in ready:
                try:
                    raw,peer=sock.recvfrom(512);data=json.loads(raw)
                    port=data.get('port')
                    if data.get('protocol')=='stat-tracker-match-v1' and type(port)==int and 0<port<65536 and is_local_ipv4(peer[0]):found.add(f'http://{peer[0]}:{port}')
                except (OSError,ValueError,AttributeError):continue
        return sorted(found)
    finally:
        for sock in sockets:sock.close()
