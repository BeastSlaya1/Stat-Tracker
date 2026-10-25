import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';

const offer={type:'offer',sdp:'v=0\r\nprivate-camera-description'};
const answer={type:'answer',sdp:'v=0\r\nprivate-receiver-description'};
async function device(f){return (await f.request('/login','POST',{email:'staff@example.com',password:'Strong test password 123'})).body.token;}
test('camera negotiation requires separate signed-in sessions and sender approval',async()=>{
  const f=fixture();try{
    assert.equal((await f.request('/camera/rooms','POST',{offer})).status,401);
    const sender=await f.login(),receiver=await device(f),stranger=await device(f);
    assert.equal((await f.request('/camera/rooms','POST',{offer:{type:'answer',sdp:'v=0'}},sender)).status,400);
    const created=await f.request('/camera/rooms','POST',{offer},sender);assert.equal(created.status,201);
    const path='/camera/rooms/'+created.body.code;
    assert.equal((await f.request(path,'GET',null,stranger)).status,403);
    assert.equal((await f.request(path+'/join','POST',{},sender)).status,409);
    assert.equal((await f.request(path+'/join','POST',{},receiver)).status,200);
    assert.equal((await f.request(path+'/join','POST',{},stranger)).status,409);
    assert.equal((await f.request(path,'GET',null,receiver)).body.offer,null);
    assert.equal((await f.request(path+'/approve','POST',{},receiver)).status,403);
    assert.equal((await f.request(path+'/answer','POST',{answer},receiver)).status,403);
    assert.equal((await f.request(path+'/approve','POST',{},sender)).status,200);
    assert.deepEqual((await f.request(path,'GET',null,receiver)).body.offer,offer);
    assert.equal((await f.request(path+'/answer','POST',{answer},receiver)).status,200);
    assert.deepEqual((await f.request(path,'GET',null,sender)).body.answer,answer);
    assert.equal((await f.request(path+'/answer','POST',{answer},receiver)).status,200);
    assert.equal((await f.request(path+'/answer','POST',{answer:{...answer,sdp:'v=0 changed'}},receiver)).status,409);
    assert.equal((await f.request(path+'/close','POST',{},stranger)).status,403);
    assert.equal((await f.request(path+'/close','POST',{},receiver)).status,200);
    assert.equal((await f.request(path,'GET',null,sender)).status,404);
  }finally{f.sqlite.close();}
});
test('camera codes expire, creating a link replaces the old one, logout revokes signaling',async()=>{
  const f=fixture();try{
    const sender=await f.login();
    const first=(await f.request('/camera/rooms','POST',{offer},sender)).body.code;
    const second=(await f.request('/camera/rooms','POST',{offer},sender)).body.code;
    assert.equal((await f.request('/camera/rooms/'+first,'GET',null,sender)).status,404);
    f.sqlite.prepare('UPDATE camera_rooms SET expires_at=0 WHERE code=?').run(second);
    assert.equal((await f.request('/camera/rooms/'+second,'GET',null,sender)).status,404);
    const third=(await f.request('/camera/rooms','POST',{offer},sender)).body.code;
    await f.request('/logout','POST',{},sender);
    assert.equal((await f.request('/camera/rooms/'+third,'GET',null,sender)).status,401);
  }finally{f.sqlite.close();}
});
