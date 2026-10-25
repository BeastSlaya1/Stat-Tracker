"""Temporary LAN directory: exchanges pairing codes, never match data or permissions."""
import atexit
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from shared_match import DISCOVERY_PORTS, SharedError
from local_network import is_local_ipv4

class PairingDirectory:
    def __init__(self):
        self.lock=threading.RLock();self.hosts={};self.requests={}
        self.server=None;self.beacon=None;self.closed=False;self.hidden=False
        self.identity=secrets.token_hex(16)
    def _clean(self):
        now=time.monotonic()
        self.hosts={k:v for k,v in self.hosts.items() if now-v['seen']<45}
        self.requests={k:v for k,v in self.requests.items() if now-v['created']<60 and v['host'] in self.hosts}
    def dispatch(self,path,token='',body=None):
        with self.lock:
            self._clean();body=body or {}
            if path=='/discover':return {'protocol':'stat-tracker-directory-v1','name':'Local match directory','sport':'DIRECTORY','session':self.identity}
            if path=='/list':return {'matches':[{'id':k,'name':v['name'],'sport':v['sport']} for k,v in self.hosts.items()]}
            if path=='/register':
                if len(self.hosts)>=8:raise SharedError('Local directory is full.',429)
                if body.get('hidden'):raise SharedError('Hidden matches use private connection codes.',403)
                identity=secrets.token_hex(16);secret=secrets.token_hex(32)
                self.hosts[identity]={'token':secret,'name':str(body.get('name','Match'))[:160],'sport':str(body.get('sport',''))[:40],'seen':time.monotonic()}
                return {'id':identity,'token':secret}
            if path=='/connect':
                identity=body.get('host')
                if identity not in self.hosts:raise SharedError('Match is no longer sharing.',404)
                if sum(r['host']==identity for r in self.requests.values())>=8:raise SharedError('Too many connections waiting. Try again shortly.',429)
                request=secrets.token_hex(16);secret=secrets.token_hex(32)
                self.requests[request]={'host':identity,'token':secret,'created':time.monotonic(),'offer':'','answer':'','accepted':False}
                return {'request':request,'token':secret}
            if path.startswith('/host/'):
                identity=body.get('host');host=self.hosts.get(identity)
                if not host or not secrets.compare_digest(host['token'],token):raise SharedError('Host session expired.',403)
                host['seen']=time.monotonic()
                if path=='/host/poll':return {'requests':[{'id':k,'offer':bool(v['offer']),'answer':v['answer'],'accepted':v['accepted']} for k,v in self.requests.items() if v['host']==identity]}
                if path=='/host/leave':
                    del self.hosts[identity];self._clean();return {}
                row=self.requests.get(body.get('request'))
                if not row or row['host']!=identity:raise SharedError('Connection request expired.',404)
                if path=='/host/offer':
                    if row['offer']:raise SharedError('Invitation already created.',409)
                    row['offer']=self._code(body.get('code'));return {}
                if path=='/host/accepted':row['accepted']=True;return {}
            if path in ('/reply','/answer'):
                row=self.requests.get(body.get('request'))
                if not row or not secrets.compare_digest(row['token'],token):raise SharedError('Connection request expired.',403)
                if path=='/reply':return {'offer':row['offer'],'accepted':row['accepted']}
                if row['answer']:raise SharedError('Reply already submitted.',409)
                row['answer']=self._code(body.get('code'));return {}
            raise SharedError('Unknown directory action.',404)
    @staticmethod
    def _code(value):
        if not isinstance(value,str) or not value.startswith('STC1.') or len(value)>100000:raise SharedError('Invalid connection code.')
        return value
    def start(self,bind="0.0.0.0",ports=DISCOVERY_PORTS):
        if self.server:return self.server.server_port
        directory=self
        class Server(ThreadingHTTPServer):
            daemon_threads=True
            allow_reuse_address=False
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_OPTIONS(self):
                self.send_response(204);self.cors();self.end_headers()
            def cors(self):
                self.send_header('Access-Control-Allow-Origin','*')
                self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization')
                self.send_header('Access-Control-Allow-Private-Network','true')
                self.send_header('Cache-Control','no-store')
            def do_GET(self):self.respond(False)
            def do_POST(self):self.respond(True)
            def respond(self,post):
                try:
                    self.connection.settimeout(5)
                    if not is_local_ipv4(self.client_address[0]):raise SharedError('Local network only.',403)
                    size=int(self.headers.get('Content-Length',0))
                    if size<0 or size>110000:raise SharedError('Request is too large.',413)
                    if not post and self.path not in ('/discover','/list'):raise SharedError('Use POST.',405)
                    body=json.loads(self.rfile.read(size)) if post else None
                    if post and not isinstance(body,dict):raise SharedError('Invalid request.')
                    result=directory.dispatch(self.path,self.headers.get('Authorization','').removeprefix('Bearer '),body);status=200
                except SharedError as error:result={'error':str(error)};status=error.status
                except Exception:result={'error':'Invalid directory request.'};status=400
                data=json.dumps(result).encode();self.send_response(status);self.cors()
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        for port in ports:
            try:self.server=Server((bind,port),Handler);break
            except OSError:continue
        if not self.server:raise SharedError('All local sharing ports are busy. Close other Stat Tracker instances.')
        self.closed=False;threading.Thread(target=self.server.serve_forever,daemon=True).start()
        from match_discovery import MatchBeacon
        if bind!="127.0.0.1":self.beacon=MatchBeacon(self);self.beacon.start()
        atexit.register(self.stop)
        return self.server.server_port
    def stop(self):
        self.closed=True
        if self.beacon:self.beacon.stop();self.beacon=None
        if self.server:self.server.shutdown();self.server.server_close();self.server=None
        self.hosts.clear();self.requests.clear()

directory=PairingDirectory()
