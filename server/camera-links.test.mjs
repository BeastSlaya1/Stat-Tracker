import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
const offer={type:'offer',sdp:'v=0 private offer'},answer={type:'answer',sdp:'v=0 private answer'};
test('one authenticated discovery list; approval required; same-login devices stay separate',async()=>{
 const f=fixture();try{
  const token=await f.login();
  const call=(peer,path,method='GET',body)=>f.request(path,method,body,token,undefined,{'X-Camera-Device':peer.repeat(32)});
  assert.equal((await f.request('/camera/devices')).status,401);
  const created=await call('a','/camera/devices','POST',{name:'Windows camera',kind:'Windows',offer});assert.equal(created.status,201);
  const path='/camera/devices/'+created.body.code;
  const discovered=await f.request('/camera/devices','GET',null,token);
  assert.deepEqual(Object.keys(discovered.body.devices[0]).sort(),['code','kind','name']);
  assert.equal((await call('b',path)).status,403);
  assert.equal((await call('b',path+'/join','POST',{})).status,200);
  assert.equal((await call('c',path+'/join','POST',{})).status,409);
  assert.equal((await call('b',path)).body.offer,null);
  assert.equal((await call('b',path+'/answer','POST',{answer})).status,403);
  assert.equal((await call('b',path+'/approve','POST',{})).status,403);
  assert.equal((await call('a',path+'/approve','POST',{})).status,200);
  assert.deepEqual((await call('b',path)).body.offer,offer);
  assert.equal((await call('b',path+'/answer','POST',{answer})).status,200);
  assert.deepEqual((await call('a',path)).body.answer,answer);
  assert.equal((await f.request('/camera/devices','GET',null,token)).body.devices.length,0);
  assert.equal((await call('c',path+'/close','POST',{})).status,403);
  assert.equal((await call('b',path+'/close','POST',{})).status,200);
  assert.equal((await call('a',path)).status,404);
 }finally{f.sqlite.close();}
});
test('stale senders disappear and heartbeat restores presence without exposing connection details',async()=>{
 const f=fixture();try{
  const token=await f.login(),headers={'X-Camera-Device':'d'.repeat(32)};
  const call=(path,method='GET',body)=>f.request(path,method,body,token,undefined,headers);
  const created=await call('/camera/devices','POST',{name:'Phone',kind:'Browser',offer});const path='/camera/devices/'+created.body.code;
  f.sqlite.prepare('UPDATE camera_links SET last_seen=?').run(Date.now()-46000);
  assert.equal((await call('/camera/devices')).body.devices.length,0);
  assert.equal((await call(path+'/heartbeat','POST',{})).status,200);
  assert.equal((await call('/camera/devices')).body.devices.length,1);
  const again=await call('/camera/devices','POST',{name:'New camera',kind:'Android',offer});
  assert.equal((await call(path)).status,404);
  assert.equal((await call('/camera/devices')).body.devices[0].code,again.body.code);
  await f.request('/logout','POST',{},token);
  assert.equal((await call('/camera/devices')).status,401);
 }finally{f.sqlite.close();}
});
