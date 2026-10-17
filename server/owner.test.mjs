import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fixture} from './worker.test.mjs';
const password='Owner and hidden test password 123';
async function setup(){
 const f=fixture(),root=await f.login();
 f.sqlite.prepare("UPDATE users SET email='4530@sccstudent.co.za'").run();
 const migration=readFileSync(new URL('./owner-migration.sql',import.meta.url),'utf8');
 f.sqlite.exec(migration);f.sqlite.exec(migration);
 const create=async(email,role='user',hidden=false,extra={})=>{
  const result=await f.request('/accounts','POST',{email,display_name:email,password,role,hidden,...extra},root);
  assert.equal(result.status,201,JSON.stringify(result.body));
  const login=await f.request('/login','POST',{email,password});assert.equal(login.status,200);
  return {id:result.body.id,token:login.body.token,user:login.body.user,email};
 };
 return {...f,root,create};
}
function mutation(id){
 const team={id:'home',name:'SCC',short_name:'SCC',logo_color:'#000000',secondary_color:'#ffffff',badge_symbol:'',team_code:'U15A'};
 return {base_version:0,mutation_id:crypto.randomUUID(),deleted:false,body:{id,sport:'BASKETBALL',title:id,date:'2026-10-08',location:'Home',home_team:team,away_team:{...team,id:'away'},events:[]}};
}
test('only primary Owner grants Owner; only Owners manage hidden accounts',async()=>{
 const f=await setup();try{
  const me=(await f.request('/me','GET',null,f.root)).body.user;assert.equal(me.role,'owner');assert.equal(me.can_grant_owner,true);
  const admin=await f.create('admin@example.com','admin'),owner=await f.create('owner@example.com','owner'),hidden=await f.create('hidden@example.com','user',true);
  for(const token of [admin.token,owner.token])assert.equal((await f.request('/accounts','POST',{email:'extra@example.com',display_name:'Extra',password,role:'owner'},token)).status,403);
  assert.equal((await f.request('/accounts','POST',{email:'other@example.com',display_name:'Other',password,role:'user',hidden:true},admin.token)).status,403);
  assert.equal((await f.request('/accounts/'+hidden.id,'PUT',{role:'user',enabled:true},admin.token)).status,404);
  assert.equal((await f.request('/accounts/'+hidden.id,'DELETE',{confirm_email:hidden.email},admin.token)).status,404);
  assert.equal((await f.request('/accounts/'+owner.id,'PUT',{role:'user',enabled:true},admin.token)).status,403);
  assert.equal((await f.request('/accounts/'+me.id,'DELETE',{confirm_email:me.email},owner.token)).status,403);
  assert.equal((await f.request('/accounts/'+me.id,'PUT',{role:'admin',enabled:true},f.root)).status,400);
  assert.ok(!(await f.request('/accounts','GET',null,admin.token)).body.accounts.some(a=>a.id===hidden.id));
  assert.ok((await f.request('/accounts','GET',null,owner.token)).body.accounts.some(a=>a.id===hidden.id));
  assert.equal((await f.request('/accounts/'+hidden.id,'PUT',{role:'user',enabled:true,hidden:false},owner.token)).status,200);
  assert.equal((await f.request('/me','GET',null,hidden.token)).status,401);
 }finally{f.sqlite.close();}
});
test('hidden and normal matches are isolated for reads, writes, conflicts and deletion',async()=>{
 const f=await setup();try{
  const normal=await f.create('normal@example.com','admin'),hidden=await f.create('hidden@example.com','user',true),peer=await f.create('peer@example.com','user',true),coach=await f.create('coach@example.com','coach',true,{team_code:'U15A',sport:'BASKETBALL'});
  const pub=mutation('public'),priv=mutation('private');
  assert.equal((await f.request('/matches/public','PUT',pub,normal.token)).status,200);
  assert.equal((await f.request('/matches/private','PUT',priv,hidden.token)).status,200);
  for(const [token,expected] of [[normal.token,['public']],[hidden.token,['private']],[peer.token,['private']],[coach.token,['private']],[f.root,['private','public']]]){
   const result=await f.request('/matches','GET',null,token);assert.deepEqual(result.body.records.map(r=>r.id),expected);assert.equal(result.body.visibility_complete,true);
  }
  for(const [token,data] of [[normal.token,priv],[hidden.token,pub]]){
   for(const update of [data,{...data,base_version:1,deleted:true},{...data,base_version:9}]){
    const denied=await f.request('/matches/'+data.body.id,'PUT',update,token);assert.equal(denied.status,404);assert.ok(!denied.body.current);
   }
  }
  const peerRecord=(await f.request('/matches','GET',null,peer.token)).body.records[0];
  assert.equal(peerRecord.body.created_by_name,'Hidden account');assert.equal(peerRecord.body.created_by_id,'');
  assert.equal(peerRecord.owner_id,undefined);assert.equal(peerRecord.creator_name,undefined);
  assert.equal((await f.request('/matches/private','PUT',{...priv,base_version:1},coach.token)).status,403);
  assert.equal((await f.request('/accounts/'+hidden.id,'DELETE',{confirm_email:hidden.email},f.root)).status,200);
  assert.deepEqual((await f.request('/matches','GET',null,normal.token)).body.records.map(r=>r.id),['public']);
  assert.equal((await f.request('/matches','GET',null,f.root)).body.records.length,2);
 }finally{f.sqlite.close();}
});
test('hiding historical activity is private and cameras obey the same boundary',async()=>{
 const f=await setup();try{
  const admin=await f.create('admin@example.com','admin'),normal=await f.create('normal@example.com'),hidden=await f.create('hidden@example.com','user',true);
  const old=mutation('old');assert.equal((await f.request('/matches/old','PUT',old,normal.token)).status,200);
  assert.equal((await f.request('/accounts/'+normal.id,'PUT',{role:'user',enabled:true,hidden:true},f.root)).status,200);
  assert.equal((await f.request('/matches','GET',null,admin.token)).body.records.length,0);
  assert.equal((await f.request('/matches','GET',null,hidden.token)).body.records.length,1);
  const extra={'X-Camera-Device':'a'.repeat(32)},offer={type:'offer',sdp:'v=0 private'};
  const camera=await f.request('/camera/devices','POST',{name:'Hidden camera',kind:'Browser',offer},hidden.token,undefined,extra);assert.equal(camera.status,201);
  assert.equal((await f.request('/camera/devices','GET',null,admin.token)).body.devices.length,0);
  assert.equal((await f.request('/camera/devices','GET',null,f.root)).body.devices.length,1);
  assert.equal((await f.request('/camera/devices/'+camera.body.code+'/join','POST',{},admin.token,undefined,extra)).status,404);
  const room=await f.request('/camera/rooms','POST',{offer},hidden.token);assert.equal(room.status,201);
  assert.equal((await f.request('/camera/rooms/'+room.body.code+'/join','POST',{},admin.token)).status,404);
 }finally{f.sqlite.close();}
});
