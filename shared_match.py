"""Local, authenticated match coordination for installed apps on one LAN."""
from concurrent.futures import ThreadPoolExecutor
import copy
import ipaddress
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from models import Match, StatEvent
from engine import recalculate_stats
from shared_permissions import assignment, permits

class SharedError(Exception):
    def __init__(self,message,status=400):super().__init__(message);self.status=status

DISCOVERY_PORTS=(8767,8768,8769,8770)

CONTROL_FIELDS=('minute','second','period','is_live','basketball_elapsed','basketball_baseline','hockey_baseline','possession_team')

def local_address(value):
    parsed=urlsplit(value if '://' in value else 'http://'+value)
    try:
        address=ipaddress.ip_address(parsed.hostname or '')
        port=parsed.port
    except ValueError:raise SharedError('Enter the host IP address and port shown on its screen.')
    from local_network import is_local_ipv4
    private=is_local_ipv4(str(address))
    if parsed.scheme!='http' or not private or address.is_unspecified or address.is_multicast or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not port:
        raise SharedError('Use the local IP address and port shown by the host.')
    return f'http://{address}:{port}'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):raise SharedError("The host tried to redirect the connection.",403)

def local_request(address,path,token='',body=None):
    base=local_address(address)
    headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
    request=Request(base+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    # Local traffic must never go through a configured internet proxy.
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:return json.load(response)
    except HTTPError as e:
        try:message=json.load(e).get('error','Shared match unavailable.')
        except Exception:message='Shared match unavailable.'
        finally:e.close()
        raise SharedError(message,e.code) from e

class SharedMatch:
    def __init__(self,match,hidden=False):
        self.lock=threading.RLock();self.match=Match.from_dict(match.to_dict())
        if self.match.sport=='BASKETBALL' and self.match.basketball_baseline is None:
            from basketball import box_score
            self.match.basketball_baseline={'home':self.match.home_score-box_score(self.match.events)['PTS'],'away':self.match.away_score-box_score(self.match.events)['POINTS_AGAINST']}
        if self.match.sport=='HOCKEY':
            from hockey import ensure_baseline
            ensure_baseline(self.match)
        self.host_token=secrets.token_hex(32);self.join_code=secrets.token_hex(8).upper()
        self.discovery_id=secrets.token_hex(16);self.requests={}
        self.hidden=hidden;self.members={};self.owners={e.id:'host' for e in match.events};self.deleted=set()
        self.video={};self.video_generation=0;self.running=False;self.anchor=time.monotonic();self.host_seen=time.monotonic()
        self.revision=0;self.closed=False;self.server=None;self.base_away=self.match.away_score-self._conceded();self.base_home=0
        for event in self.match.events:event.source_device='host'
    def _conceded(self):return sum(e.event_type in ('GOALS_GIVEN','GOALS_GIVEN_CONVERSION') for e in self.match.events)
    def join(self,code,name,hidden):
        with self.lock:
            if not secrets.compare_digest(str(code).upper().replace(' ',''),self.join_code):raise SharedError('Incorrect join code.',403)
            if bool(hidden)!=self.hidden:raise SharedError('Hidden and normal accounts cannot share a session.',403)
            self._expire_pending()
            if len(self.members)>=8:raise SharedError('This session already has eight joined devices.',409)
            if not isinstance(name,str) or not name.strip() or len(name)>60:raise SharedError('Enter a device name (up to 60 characters).')
            token=secrets.token_hex(32);identity=secrets.token_hex(16)
            self.members[token]={'id':identity,'name':name.strip(),'approved':False,'last_seen':time.monotonic(),'created':time.monotonic(),'permissions':assignment(self.match.sport)}
            return {'token':token,'device':identity,'waiting':True}
    def _expire_pending(self):
        now=time.monotonic()
        for token,member in list(self.members.items()):
            if not member['approved'] and now-member['created']>120:self.members.pop(token,None)
    def request_join(self,session,name,hidden,address):
        with self.lock:
            if self.closed or self.hidden or bool(hidden) or not isinstance(session,str) or not secrets.compare_digest(session,self.discovery_id):
                raise SharedError('This match is no longer discoverable. Scan again.',403)
            now=time.monotonic()
            self.requests={key:stamp for key,stamp in self.requests.items() if now-stamp<10}
            if address in self.requests:raise SharedError('Please wait a few seconds before requesting again.',429)
            self.requests[address]=now
            return self.join(self.join_code,name,False)
    def cancel_join(self,token):
        with self.lock:
            member=self.members.pop(token,None)
            if member:self.video.pop(member['id'],None)
            return {'ok':True}
    def actor(self,token,approved=True):
        if self.closed:raise SharedError('The host ended this session.',410)
        self._expire_pending()
        if secrets.compare_digest(token,self.host_token):return 'host'
        member=self.members.get(token)
        if not member:raise SharedError('Join this match from the host first.',403)
        member['last_seen']=time.monotonic()
        if approved and not member['approved']:raise SharedError('Waiting for the host to approve this device.',425)
        return member['id']
    def approve(self,identity,allowed=True,permissions=None):
        with self.lock:
            for token,m in list(self.members.items()):
                if m['id']==identity:
                    if allowed:
                        if permissions is not None:m['permissions']=assignment(self.match.sport,permissions['section'],permissions['stats'])
                        m['approved']=True
                        self.revision+=1
                    else:self.members.pop(token);self.video.pop(identity,None)
                    return
    def apply(self,token,added,removed):
        with self.lock:
            actor=self.actor(token)
            if not isinstance(added,list) or not isinstance(removed,list) or len(added)>200 or len(removed)>200:raise SharedError('Too many events in one update.')
            # Validate the entire operation before mutation; retries use event IDs.
            if any(not isinstance(b,dict) or not isinstance(b.get('id'),str) or not b['id'] for b in added) or any(not isinstance(i,str) for i in removed):raise SharedError('Invalid event identifiers.')
            parsed=[];new_ids={b['id'] for b in added}
            for body in added:
                if not isinstance(body,dict) or not isinstance(body.get('id'),str) or len(body['id'])>100:raise SharedError('Invalid event.')
                try:event=StatEvent.from_dict(body)
                except (TypeError,ValueError):raise SharedError('Invalid event.')
                if not isinstance(event.basketball,dict) or not isinstance(event.target_id,str):raise SharedError('Invalid event details.')
                if not isinstance(event.event_type,str) or len(event.event_type)>60 or event.team_id!='home' or not isinstance(event.minute,int):raise SharedError('Invalid event.')
                if actor!='host' and event.event_type in ('BB_TIMEOUT','BB_OVERTIME','BB_END_QUARTER','BB_FULL_TIME','TIMEOUT','END_QUARTER','FULL_TIME'):raise SharedError('The host controls match time.',403)
                if event.id in self.owners and self.owners[event.id]!=actor:raise SharedError('Another device owns that event.',403)
                if event.id in self.owners or event.id in self.deleted:continue
                target=event.basketball.get('target_id') or event.target_id
                if target and (target in self.deleted or self.owners.get(target,actor if target in new_ids else None)!=actor):raise SharedError('Only the device that logged an action can mark or convert it.',409)
                if actor!='host' and not permits(self.match.sport,self.members[token]['permissions'],event,self.match.events+parsed):raise SharedError('The host has not assigned this stat to your device.',403)
                event.source_device=actor;parsed.append(event)
            for identity in removed:
                original=next((e for e in self.match.events if e.id==identity),None)
                if actor!='host' and original and not permits(self.match.sport,self.members[token]['permissions'],original,self.match.events):raise SharedError('The host has not assigned this stat to your device.',403)
                if identity in self.owners and actor!='host' and self.owners[identity]!=actor:raise SharedError('Only your own events can be removed.',403)
            existing={e.id for e in self.match.events}
            for event in parsed:
                if event.id not in existing and event.id not in self.deleted:
                    self.match.events.append(event);self.owners[event.id]=actor;existing.add(event.id)
            removals=set(removed)
            removals.update(e.id for e in self.match.events if (e.basketball.get('target_id') or e.target_id) in removals)
            self.deleted.update(removals);self.match.events=[e for e in self.match.events if e.id not in removals]
            recalculate_stats(self.match)
            if self.match.sport not in ('BASKETBALL','HOCKEY'):self.match.away_score=self.base_away+self._conceded();self.match.home_score+=self.base_home
            if parsed or removed:self.revision+=1
            return self.snapshot(token)
    def control(self,match,running):
        with self.lock:
            for key in CONTROL_FIELDS:setattr(self.match,key,copy.deepcopy(getattr(match,key)))
            for field in ('home_possession_seconds','away_possession_seconds','home_possession','away_possession'):setattr(self.match.stats,field,getattr(match.stats,field))
            if self.match.sport not in ('BASKETBALL','HOCKEY'):
                self.base_away=match.away_score-sum(e.event_type in ('GOALS_GIVEN','GOALS_GIVEN_CONVERSION') for e in match.events)
                projection=Match.from_dict(match.to_dict());recalculate_stats(projection)
                self.base_home=match.home_score-projection.home_score
                self.match.away_score=self.base_away+self._conceded()
            self.running=bool(running);self.anchor=time.monotonic();self.host_seen=self.anchor
    def snapshot(self,token):
        with self.lock:
            actor=self.actor(token);result=copy.deepcopy(self.match.to_dict());now=time.monotonic()
            running=self.running and now-self.host_seen<6
            seconds=int(min(6,max(0,now-self.anchor))) if self.running else 0
            total=result['minute']*60+result['second']+seconds;result['minute'],result['second']=divmod(total,60)
            result['basketball_elapsed']+=seconds
            side=result.get('possession_team')
            if side:result['stats'][side+'_possession_seconds']+=seconds
            return {'permissions':assignment(self.match.sport) if actor=='host' else copy.deepcopy(self.members[token]['permissions']),'match':result,'revision':self.revision,'running':running,'host_online':now-self.host_seen<6,'device':actor,
                    'members':[{'id':m['id'],'name':m['name'],'approved':m['approved'],'permissions':copy.deepcopy(m['permissions'])} for m in self.members.values()] if actor=='host' else []}
    def signal(self,token,body=None):
        with self.lock:
            actor=self.actor(token)
            if body is not None:
                if actor=='host' and body.get('reset'):
                    self.video.clear();self.video_generation+=1
                elif actor=='host':
                    identity=body.get('device');offer=body.get('offer')
                    if not any(m['approved'] and m['id']==identity for m in self.members.values()):raise SharedError('Device is not approved.',403)
                    self._sdp(offer,'offer');self.video[identity]={'offer':offer,'generation':self.video_generation}
                else:
                    self._sdp(body.get('answer'),'answer')
                    row=self.video.get(actor)
                    if not row or row['generation']!=body.get('generation'):raise SharedError('Camera restarted. Reconnecting.',409)
                    row['answer']=body['answer']
            if actor=='host':return {'devices':[{'id':m['id'],**self.video.get(m['id'],{})} for m in self.members.values() if m['approved']]}
            return self.video.get(actor,{'generation':self.video_generation})
    @staticmethod
    def _sdp(value,kind):
        if not isinstance(value,dict) or value.get('type')!=kind or not isinstance(value.get('sdp'),str) or not value['sdp'].startswith('v=0') or len(value['sdp'])>65536:raise SharedError('Invalid camera connection.')
    def start(self):
        hub=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.respond(False)
            def do_POST(self):self.respond(True)
            def respond(self,post):
                try:
                    if self.headers.get('Origin'):raise SharedError('Use the installed app to join.',403)
                    size=int(self.headers.get('Content-Length',0))
                    if size<0 or size>1048576:raise SharedError('Request is too large.',413)
                    body=json.loads(self.rfile.read(size)) if post else None
                    token=self.headers.get('Authorization','').removeprefix('Bearer ')
                    if self.path=='/discover' and not post:
                        if hub.hidden or hub.closed:raise SharedError('No discoverable match.',404)
                        result={'protocol':'stat-tracker-match-v1','name':str(hub.match.title)[:160],'sport':hub.match.sport,'session':hub.discovery_id}
                    elif self.path=='/request-join' and post:result=hub.request_join(body.get('session'),body.get('name'),body.get('hidden'),self.client_address[0])
                    elif self.path=='/cancel-join' and post:result=hub.cancel_join(token)
                    elif self.path=='/join' and post:result=hub.join(body.get('code'),body.get('name'),body.get('hidden'))
                    elif self.path=='/state' and not post:result=hub.snapshot(token)
                    elif self.path=='/events' and post:result=hub.apply(token,body.get('added',[]),body.get('removed',[]))
                    elif self.path=='/video':result=hub.signal(token,body)
                    else:raise SharedError('Unknown session action.',404)
                    status=200
                except SharedError as e:result={'error':str(e)};status=e.status
                except Exception:result={'error':'Invalid shared-match request.'};status=400
                data=json.dumps(result).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        for port in (*DISCOVERY_PORTS,0):
            try:
                self.server=ThreadingHTTPServer(('0.0.0.0',port),Handler)
                break
            except OSError:
                if port==0:raise
        self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        from match_discovery import MatchBeacon
        self.beacon=MatchBeacon(self);self.beacon.start()
        return self.server.server_port
    def stop(self):
        self.closed=True
        if getattr(self,'beacon',None):self.beacon.stop()
        if self.server:
            self.server.shutdown();self.server.server_close();self.server=None

def addresses(port):
    from local_network import local_ipv4_addresses
    return [f'{value}:{port}' for value in local_ipv4_addresses()]


def discover_matches():
    """Bounded scan of directly attached private /24 networks; no credentials exposed."""
    networks=set();interfaces=[]
    for value in addresses(DISCOVERY_PORTS[0]):
        try:
            base=local_address(value)
            ip=ipaddress.ip_address(urlsplit(base).hostname)
            if not ip.is_loopback:
                networks.add(ipaddress.ip_network(f'{ip}/24',strict=False));interfaces.append(str(ip))
        except (SharedError,ValueError):continue
    from match_discovery import discover_addresses
    announced=discover_addresses(interfaces)
    targets=[f'http://{ip}:{port}' for network in sorted(networks,key=str)[:4] for ip in network.hosts() for port in DISCOVERY_PORTS]
    def probe(base):
        try:
            request=Request(base+'/discover',headers={'Accept':'application/json'})
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=.25) as response:
                data=json.loads(response.read(4096))
            if data.get('protocol')=='stat-tracker-match-v1' and isinstance(data.get('name'),str) and isinstance(data.get('sport'),str):
                return {'address':base,'name':data['name'][:160],'sport':data['sport'][:40],'session':data.get('session','')}
        except Exception:pass
    with ThreadPoolExecutor(max_workers=48) as pool:
        return sorted((row for row in pool.map(probe,sorted(set(targets+announced))) if row),key=lambda row:(row['name'],row['address']))
