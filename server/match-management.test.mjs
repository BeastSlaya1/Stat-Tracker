import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
const password='New account password 123';
async function setup(){
 const f=fixture(),admin=await f.login();f.sqlite.prepare("UPDATE users SET role='admin'").run();
 async function create(name,role='user'){
  const email=name+'@example.com';
  assert.equal((await f.request('/accounts','POST',{email,display_name:name,password,role},admin)).status,201);
  return (await f.request('/login','POST',{email,password})).body;
 }
 return {...f,admin,create};
}
function mutation(id,version=0){
 const team={id:'home',name:'SCC',short_name:'SCC',logo_color:'#000000',secondary_color:'#ffffff',badge_symbol:''};
 return {base_version:version,mutation_id:crypto.randomUUID(),deleted:false,body:{id,sport:'SOCCER',title:'Game',date:'2026-09-27',location:'Home',home_team:team,away_team:{...team,id:'away'},events:[]}};
}
test('creator cannot be spoofed and editor changes without changing creator',async()=>{
 const f=await setup();try{
  const a=await f.create('Alice'),staff=await f.create('Editor','staff'),b=await f.create('Bob');
  const m=mutation('game');m.body.created_by_name='Spoof';m.body.edited_by_name='Spoof';
  assert.equal((await f.request('/matches/game','PUT',m,a.token)).status,200);
  const record=(await f.request('/matches','GET',null,a.token)).body.records[0];
  assert.equal(record.body.created_by_name,'Alice');assert.equal(record.body.edited_by_name,'Alice');
  const legacy=(await f.request('/matches','GET',null,a.token,'https://stattrackerv4.stream',{'X-StatTracker-Features':''})).body.records[0];
  assert.equal(legacy.body.created_by_name,undefined);assert.equal(legacy.body.title,'Game');
  assert.deepEqual((await f.request('/matches','GET',null,b.token)).body.records,[]);
  assert.equal((await f.request('/matches/game','PUT',{...m,base_version:1,mutation_id:crypto.randomUUID()},staff.token)).status,200);
  const edited=(await f.request('/matches','GET',null,a.token)).body.records[0];
  assert.equal(edited.body.created_by_id,a.user.id);assert.equal(edited.body.created_by_name,'Alice');assert.equal(edited.body.edited_by_name,'Editor');
 }finally{f.sqlite.close();}
});
test('admin deletion revokes login, preserves games and names, protects own account',async()=>{
 const f=await setup();try{
  const a=await f.create('Alice'),staff=await f.create('Staff2','staff');
  await f.request('/matches/game','PUT',mutation('game'),a.token);
  const path='/accounts/'+a.user.id,body={confirm_email:a.user.email};
  assert.equal((await f.request(path,'DELETE',body,staff.token)).status,403);
  assert.equal((await f.request(path,'DELETE',body,a.token)).status,403);
  assert.equal((await f.request(path,'DELETE',{confirm_email:'wrong'},f.admin)).status,400);
  const admin=(await f.request('/me','GET',null,f.admin)).body.user;
  assert.equal((await f.request('/accounts/'+admin.id,'DELETE',{confirm_email:admin.email},f.admin)).status,400);
  const deleted=await f.request(path,'DELETE',body,f.admin);assert.equal(deleted.status,200,JSON.stringify(deleted.body));
  assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM users WHERE id=?').get(a.user.id).n,0);
  assert.equal((await f.request('/me','GET',null,a.token)).status,401);
  assert.equal((await f.request('/login','POST',{email:a.user.email,password})).status,401);
  const game=(await f.request('/matches','GET',null,f.admin)).body.records[0];
  assert.equal(game.deleted,false);assert.equal(game.owner_id,admin.id);
  assert.equal(game.body.created_by_name,'Alice');assert.equal(game.body.edited_by_name,'Alice');
  const replacement=await f.create('Alice');
  assert.deepEqual((await f.request('/matches','GET',null,replacement.token)).body.records,[]);
  assert.equal((await f.request('/matches/game','PUT',mutation('game',1),f.admin)).status,409);
 }finally{f.sqlite.close();}
});
test('two admins cannot concurrently delete the last administrator',async()=>{
 const f=await setup();try{
  const second=await f.create('Second','admin'),first=(await f.request('/me','GET',null,f.admin)).body.user;
  await Promise.all([f.request('/accounts/'+second.user.id,'DELETE',{confirm_email:second.user.email},f.admin),f.request('/accounts/'+first.id,'DELETE',{confirm_email:first.email},second.token)]);
  assert.equal(f.sqlite.prepare("SELECT COUNT(*) n FROM users WHERE role='admin' AND enabled=1").get().n,1);
 }finally{f.sqlite.close();}
});
