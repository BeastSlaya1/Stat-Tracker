"""Local discovery and automatic WebRTC pairing for apps and supported browsers."""
import asyncio
import secrets
from shared_match import local_address, local_request, discover_matches, DISCOVERY_PORTS, SharedError

async def request(web,base,path,token='',body=None,timeout=5):
    base=local_address(base)
    if not web:return await asyncio.wait_for(asyncio.to_thread(local_request,base,path,token,body),timeout)
    from pyodide.http import pyfetch
    import json
    options={'method':'POST' if body is not None else 'GET','headers':{'Content-Type':'application/json','Authorization':'Bearer '+token},'redirect':'error'}
    if body is not None:options['body']=json.dumps(body)
    response=await asyncio.wait_for(pyfetch(base+path,**options),timeout)
    data=await response.json()
    if response.status>=400:raise SharedError(data.get('error','Local connection failed.'),response.status)
    return data

async def find(web,hint=''):
    if hint:
        base=local_address(hint);data=await request(web,base,'/discover')
        if data.get('protocol')!='stat-tracker-directory-v1':raise SharedError('Update the app providing this local directory.')
        return [base]
    if not web:
        rows=await asyncio.to_thread(discover_matches,'stat-tracker-directory-v1')
        return [row['address'] for row in rows]
    # Browsers cannot enumerate adapters/broadcast. Probe common hotspot gateways;
    # custom networks use the address displayed by the installed app.
    bases=[f'http://{ip}:{port}' for ip in ('192.168.137.1','192.168.49.1','192.168.43.1','192.168.50.1') for port in DISCOVERY_PORTS]
    async def probe(base):
        try:
            data=await request(True,base,'/discover',timeout=2)
            if data.get('protocol')=='stat-tracker-directory-v1':return base
        except Exception:pass
    return [base for base in await asyncio.gather(*(probe(base) for base in bases)) if base]

class DirectoryMixin:
    def _ensure_directory(self):
        if self.is_web:return None
        from pairing_directory import directory
        directory.start();return directory

    async def _directory_publish(self):
        if self._database_user.get('hidden'):return
        try:
            if self.is_web:
                bases=await find(True,getattr(self,'_directory_hint',''))
                if not bases:self._peer_message('Hosting with codes. No local app directory reached; allow local-network access or enter its address to advertise here.');return
                base=bases[0]
            else:base='http://127.0.0.1:'+str(self._ensure_directory().server.server_port)
            registration=await request(self.is_web,base,'/register',body={'name':self.match.title,'sport':self.match.sport})
            self._directory_registration={'base':base,**registration}
            self.page.run_task(self._directory_poll,self._directory_registration)
        except Exception as error:self._peer_message('Connection codes remain available. Local discovery: '+str(error))

    async def _directory_poll(self,registration):
        base=registration['base'];token=registration['token'];host=registration['id'];pending={}
        while self._live_active() and getattr(self,'_directory_registration',None) is registration:
            try:
                result=await request(self.is_web,base,'/host/poll',token,{'host':host})
                for row in result['requests']:
                    identity=row['id'];body={'host':host,'request':identity}
                    if not row['offer']:
                        code=pending.get(identity)
                        if code is None:
                            code=(await self._peer_command('offer',peer=secrets.token_hex(16)))['code'];pending[identity]=code
                        await request(self.is_web,base,'/host/offer',token,{**body,'code':code})
                    elif row['answer'] and not row['accepted']:
                        if pending.get(identity)!='accepted':
                            await self._peer_command('accept',code=row['answer']);pending[identity]='accepted'
                        await request(self.is_web,base,'/host/accepted',token,body)
                alive={r['id'] for r in result['requests']}
                for key,code in list(pending.items()):
                    if key not in alive and code!='accepted':
                        import base64,json
                        value=json.loads(base64.urlsafe_b64decode(code[5:]+'==='))
                        await self._peer_command('drop',peer=value['peer'])
                pending={k:v for k,v in pending.items() if k in alive}
            except Exception as error:self._peer_message('Local discovery interrupted: '+str(error)+'. Connection codes are still available.')
            await asyncio.sleep(1)

    async def _directory_join(self,base,identity):
        if self._live_active():raise SharedError('Leave the current shared match first.')
        self._ensure_peer_link()
        joining=await request(self.is_web,base,'/connect',body={'host':identity})
        for _ in range(50):
            result=await request(self.is_web,base,'/reply',joining['token'],{'request':joining['request']})
            if result.get('offer'):
                reply=await self._peer_command('answer',code=result['offer']);self._peer_remote=reply['peer']
                await request(self.is_web,base,'/answer',joining['token'],{'request':joining['request'],'code':reply['code']})
                self._peer_message('Connecting. The host will approve your device.');return
            await asyncio.sleep(1)
        raise SharedError('Host did not respond. Scan and try again.')

    async def _directory_leave(self):
        registration=getattr(self,'_directory_registration',None);self._directory_registration=None
        if registration:
            try:await request(self.is_web,registration['base'],'/host/leave',registration['token'],{'host':registration['id']})
            except Exception:pass
