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
        self.controllers={'video':'host','time':'host'};self.control_generation=0;self.control_seen=time.monotonic()
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
            self._restore_departed_controllers()
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
                        if permissions is not None:m['permissions']=assignment(self.match.sport,'All' if permissions.get('section')=='All' else permissions.get('sections',permissions['section']),permissions['stats'],permissions.get('stream_only',False),permissions.get('players'))
                        m['approved']=True
                        if m['permissions'].get('stream_only'):
                            self.assign_controllers(self.host_token,identity,'host' if self.controllers['time']==identity else self.controllers['time'])
                        self.revision+=1
                    else:
                        self.members.pop(token);self.video.pop(identity,None);self._restore_departed_controllers()
                    return
    def assign_controllers(self,token,video,time_device):
        with self.lock:
            if self.actor(token)!='host':raise SharedError('Only the host can assign devices.',403)
            allowed={'host'}|{m['id'] for m in self.members.values() if m['approved']}
            if video not in allowed or time_device not in allowed:raise SharedError('Choose an approved device.')
            if any(m['id']==time_device and m['permissions'].get('stream_only') for m in self.members.values()):raise SharedError('A stream-only device cannot control match time.')
            for member in self.members.values():
                if member['id']!=video and member['permissions'].get('stream_only'):
                    member['permissions']=assignment(self.match.sport,[],[])
            if video!=self.controllers['video']:
                self.video.clear();self.video_generation+=1
            if time_device!=self.controllers['time']:
                current=self.snapshot(self.host_token)['match']
                self.match.minute=current['minute'];self.match.second=current['second']
                self.match.basketball_elapsed=current['basketball_elapsed']
                self.match.stats.home_possession_seconds=current['stats']['home_possession_seconds']
                self.match.stats.away_possession_seconds=current['stats']['away_possession_seconds']
                self.running=False;self.match.is_live=False;self.anchor=time.monotonic()
                self.control_generation+=1
            self.controllers={'video':video,'time':time_device};self.revision+=1
            return self.snapshot(token)
    def delegated_control(self,token,body):
        with self.lock:
            if self.actor(token)!=self.controllers['time']:raise SharedError('This device does not control time.',403)
            if body.get('generation')!=self.control_generation:raise SharedError('Timer assignment changed.',409)
            values=body.get('clock',{})
            if any(type(values.get(k)) is not int or not 0<=values[k]<=100000 for k in ('minute','second','basketball_elapsed')) or values['second']>59:
                raise SharedError('Invalid match clock.')
            periods={'1ST_HALF','2ND_HALF','HALF_TIME','FULL_TIME'}|{f'{p}{i}' for p in ('Q','OT') for i in range(1,5)}
            if values.get('period') not in periods or type(body.get('running')) is not bool:raise SharedError('Invalid timer state.')
            elapsed=max(0,min(6,values['minute']*60+values['second']-self.match.minute*60-self.match.second)) if values['period']==self.match.period and self.running else 0
            side=self.match.possession_team
            if side in ('home','away'):
                field=side+'_possession_seconds';setattr(self.match.stats,field,getattr(self.match.stats,field)+elapsed)
            for key in ('minute','second','basketball_elapsed','period'):setattr(self.match,key,values[key])
            self.match.is_live=body['running'];self.running=body['running']
            self.anchor=self.control_seen=time.monotonic()
            return self.snapshot(token)
    def _restore_departed_controllers(self):
        allowed={'host'}|{m['id'] for m in self.members.values() if m['approved']}
        if any(value not in allowed for value in self.controllers.values()):
            self.assign_controllers(self.host_token, self.controllers['video'] if self.controllers['video'] in allowed else 'host', self.controllers['time'] if self.controllers['time'] in allowed else 'host')
    def apply(self,token,added,removed):
        with self.lock:
            actor=self.actor(token)
            if actor!='host' and self.members[token]['permissions'].get('stream_only') and (added or removed):raise SharedError('This device is assigned to stream only.',403)
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
                if actor!=self.controllers['time'] and event.event_type in ('BB_TO','BB_SUBSTITUTION','TURNOVER','SUBSTITUTION','BB_TIMEOUT','BB_OVERTIME','BB_END_QUARTER','BB_FULL_TIME','TIMEOUT','END_QUARTER','FULL_TIME'):raise SharedError('The host controls match time.',403)
                if event.id in self.owners and self.owners[event.id]!=actor:raise SharedError('Another device owns that event.',403)
                if event.id in self.owners or event.id in self.deleted:continue
                target=event.basketball.get('target_id') or event.target_id
                if target and (target in self.deleted or self.owners.get(target,actor if target in new_ids else None)!=actor):raise SharedError('Only the device that logged an action can mark or convert it.',409)
                if actor!='host' and not (actor==self.controllers['time'] and event.event_type in ('BB_TO','BB_SUBSTITUTION','TURNOVER','SUBSTITUTION','BB_TIMEOUT','BB_OVERTIME','BB_END_QUARTER','BB_FULL_TIME','TIMEOUT','END_QUARTER','FULL_TIME')) and not permits(self.match.sport,self.members[token]['permissions'],event,self.match.events+parsed):raise SharedError('The host has not assigned this stat to your device.',403)
                if self.match.sport=='BASKETBALL':
                    from stat_policy import TEAM_ACTIONS
                    code=event.event_type.removeprefix('BB_')
                    parent=next((e for e in self.match.events+parsed if e.id==target),None) if target else None
                    if code in ('INCOMPLETE','CONVERSION') and parent is None:raise SharedError('Original player action was not found.',409)
                    source=parent or event
                    scoped=source.event_type.removeprefix('BB_') not in TEAM_ACTIONS and not (source.event_type=='BB_PENALTY' and source.basketball.get('direction') in ('opposition','defence'))
                    if scoped:
                        pid=source.basketball.get('player_id')
                        player=next((p for p in self.match.home_team.players if p.id==pid and (p.active or parent is not None)),None)
                        if player is None or event.basketball.get('player_id')!=pid:raise SharedError('Select an active team jersey for this stat.',403)
                        event.basketball['jersey']=player.number;event.player_name='#'+str(player.number)
                        if code=='CONVERSION' and event.basketball.get('assist'):
                            assister=event.basketball.get('assist_player_id')
                            if not any(p.id==assister and p.active and p.id!=pid for p in self.match.home_team.players):raise SharedError('Choose a different active jersey for the assist.',403)
                event.source_device=actor;parsed.append(event)
            for identity in removed:
                original=next((e for e in self.match.events if e.id==identity),None)
                if actor!='host' and original and not (actor==self.controllers['time'] and original.event_type in ('BB_TO','BB_SUBSTITUTION','TURNOVER','SUBSTITUTION','BB_TIMEOUT','BB_OVERTIME','BB_END_QUARTER','BB_FULL_TIME','TIMEOUT','END_QUARTER','FULL_TIME')) and not permits(self.match.sport,self.members[token]['permissions'],original,self.match.events):raise SharedError('The host has not assigned this stat to your device.',403)
                if identity in self.owners and actor!='host' and self.owners[identity]!=actor:raise SharedError('Only your own events can be removed.',403)
            existing={e.id for e in self.match.events}
            for event in parsed:
                if event.id not in existing and event.id not in self.deleted:
                    self.match.events.append(event);self.owners[event.id]=actor;existing.add(event.id)
                    if actor!='host' and event.event_type in ('BB_TO','TURNOVER'):
                        self.match.possession_team='away' if self.match.possession_team!='away' else 'home'
            removals=set(removed)
            removals.update(e.id for e in self.match.events if (e.basketball.get('target_id') or e.target_id) in removals)
            self.deleted.update(removals);self.match.events=[e for e in self.match.events if e.id not in removals]
            recalculate_stats(self.match)
            if self.match.sport not in ('BASKETBALL','HOCKEY'):self.match.away_score=self.base_away+self._conceded();self.match.home_score+=self.base_home
            if parsed or removed:self.revision+=1
            return self.snapshot(token)
    def control(self,match,running):
        with self.lock:
            for key in CONTROL_FIELDS:
                if self.controllers['time']=='host' or key in ('basketball_baseline','hockey_baseline','possession_team'):setattr(self.match,key,copy.deepcopy(getattr(match,key)))
            if self.controllers['time']=='host':
                for field in ('home_possession_seconds','away_possession_seconds','home_possession','away_possession'):setattr(self.match.stats,field,getattr(match.stats,field))
            if self.match.sport not in ('BASKETBALL','HOCKEY'):
                self.base_away=match.away_score-sum(e.event_type in ('GOALS_GIVEN','GOALS_GIVEN_CONVERSION') for e in match.events)
                projection=Match.from_dict(match.to_dict());recalculate_stats(projection)
                self.base_home=match.home_score-projection.home_score
                self.match.away_score=self.base_away+self._conceded()
            self.match.home_team.players=copy.deepcopy(match.home_team.players)
            self.host_seen=time.monotonic()
            if self.controllers['time']=='host':
                self.running=bool(running);self.anchor=self.control_seen=self.host_seen
    def snapshot(self,token):
        with self.lock:
            actor=self.actor(token);result=copy.deepcopy(self.match.to_dict());now=time.monotonic()
            running=self.running and now-self.host_seen<6 and now-self.control_seen<6
            seconds=int(min(6,max(0,now-self.anchor))) if self.running else 0
            total=result['minute']*60+result['second']+seconds;result['minute'],result['second']=divmod(total,60)
            result['basketball_elapsed']+=seconds
            side=result.get('possession_team')
            if side:result['stats'][side+'_possession_seconds']+=seconds
            return {'controllers':dict(self.controllers),'control_generation':self.control_generation,'permissions':assignment(self.match.sport) if actor=='host' else copy.deepcopy(self.members[token]['permissions']),'match':result,'revision':self.revision,'running':running,'host_online':now-self.host_seen<6,'device':actor,
                    'members':[{'id':m['id'],'name':m['name'],'approved':m['approved'],'permissions':copy.deepcopy(m['permissions'])} for m in self.members.values()] if actor=='host' else []}
    def signal(self,token,body=None):
        with self.lock:
            actor=self.actor(token)
            if body is not None:
                if actor==self.controllers['video'] and body.get('reset'):
                    self.video.clear();self.video_generation+=1
                elif actor==self.controllers['video']:
                    identity=body.get('device');offer=body.get('offer')
                    if identity==actor or (identity!='host' and not any(m['approved'] and m['id']==identity for m in self.members.values())):raise SharedError('Device is not approved.',403)
                    self._sdp(offer,'offer');self.video[identity]={'offer':offer,'generation':self.video_generation}
                else:
                    self._sdp(body.get('answer'),'answer')
                    row=self.video.get(actor)
                    if not row or row['generation']!=body.get('generation'):raise SharedError('Camera restarted. Reconnecting.',409)
                    row['answer']=body['answer']
            if actor==self.controllers['video']:
                receivers=['host']+[m['id'] for m in self.members.values() if m['approved']]
                return {'devices':[{'id':identity,**self.video.get(identity,{})} for identity in receivers if identity!=actor]}
            return self.video.get(actor,{'generation':self.video_generation})
    @staticmethod
    def _sdp(value,kind):
        if not isinstance(value,dict) or value.get('type')!=kind or not isinstance(value.get('sdp'),str) or not value['sdp'].startswith('v=0') or len(value['sdp'])>65536:raise SharedError('Invalid camera connection.')
    def start(self):
        hub=self
        class LocalServer(ThreadingHTTPServer):
            allow_reuse_address=False
            def server_bind(self):
                if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                    self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                super().server_bind()
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
                    elif self.path=='/control' and post:result=hub.delegated_control(token,body)
                    elif self.path=='/events' and post:result=hub.apply(token,body.get('added',[]),body.get('removed',[]))
                    elif self.path=='/video':result=hub.signal(token,body)
                    else:raise SharedError('Unknown session action.',404)
                    status=200
                except SharedError as e:result={'error':str(e)};status=e.status
                except Exception:result={'error':'Invalid shared-match request.'};status=400
                data=json.dumps(result).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        for port in (*DISCOVERY_PORTS,0):
            try:
                self.server=LocalServer(('0.0.0.0',port),Handler)
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


def discover_matches(protocol='stat-tracker-match-v1'):
    """Scan every attached local /24, prioritizing hotspot hosts and UDP replies."""
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
    targets={f'http://{ip}:{port}' for network in networks for ip in network.hosts() for port in DISCOVERY_PORTS}
    likely=set(announced)|{f'http://{ip}:{port}' for network in networks for ip in (network.network_address+1,network.broadcast_address-1) for port in DISCOVERY_PORTS}
    def probe(base,timeout=.6):
        try:
            request=Request(base+'/discover',headers={'Accept':'application/json'})
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=timeout) as response:
                data=json.loads(response.read(4096))
            if data.get('protocol')==protocol and isinstance(data.get('name'),str) and isinstance(data.get('sport'),str):
                return {'address':base,'name':data['name'][:160],'sport':data['sport'][:40],'session':data.get('session','')}
        except Exception:pass
    found={}
    with ThreadPoolExecutor(max_workers=64) as pool:
        for row in pool.map(lambda base:probe(base,1.2),sorted(likely)):
            if row:found[row['address']]=row
        for row in pool.map(probe,sorted(targets-likely)):
            if row:found[row['address']]=row
        # Hotspots and sleeping tablets may need a second request after waking.
        for row in pool.map(lambda base:probe(base,1.2),sorted(likely-set(found))):
            if row:found[row['address']]=row
    # One host can advertise multiple adapters; expose one reachable address.
    unique={}
    for row in found.values():unique.setdefault(row.get('session') or row['address'],row)
    return sorted(unique.values(),key=lambda row:(row['name'],row['address']))
