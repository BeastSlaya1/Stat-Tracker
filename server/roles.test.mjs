import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
const password='Account testing password 123';
async function setup(){
 const f=fixture(),admin=await f.login();f.sqlite.prepare("UPDATE users SET role='admin'").run();
 async function create(email,role,token=admin){
  const result=await f.request('/accounts','POST',{email,display_name:email,password,role},token);
  assert.equal(result.status,201,JSON.stringify(result.body));
  const login=await f.request('/login','POST',{email,password});return {token:login.body.token,user:login.body.user};
 }
 return {...f,admin,create};
}
function mutation(id,n=0){
 const team={id:'home',name:'SCC',short_name:'SCC',logo_color:'#000000',secondary_color:'#ffffff',badge_symbol:''};
 return {base_version:n,mutation_id:crypto.randomUUID(),deleted:false,body:{id,sport:'SOCCER',title:'Match',date:'2026-09-26',location:'Home',home_team:team,away_team:{...team,id:'away'},events:[]}};
}
test('account creation matrix and administrator safeguards',async()=>{
 const f=await setup();try{
  const staff=await f.create('staff2@example.com','staff'),user=await f.create('user@example.com','user',staff.token);
  const body={email:'attempt@example.com',display_name:'Attempt',password,role:'admin'};
  assert.equal((await f.request('/accounts','POST',body,staff.token)).status,403);
  assert.equal((await f.request('/accounts','POST',{...body,role:'staff'},staff.token)).status,403);
  assert.equal((await f.request('/accounts','POST',{...body,role:'user'},user.token)).status,403);
  assert.equal((await f.request('/accounts','POST',body)).status,401);
  assert.equal((await f.request('/accounts','GET',null,user.token)).status,403);
  assert((await f.request('/accounts','GET',null,staff.token)).body.accounts.every(a=>a.role==='user'));
  const adminId=(await f.request('/me','GET',null,f.admin)).body.user.id;
  assert.equal((await f.request('/accounts/'+adminId,'PUT',{role:'user',enabled:true},f.admin)).status,400);
  assert.equal((await f.request('/accounts/'+user.user.id,'PUT',{role:'admin',enabled:true},staff.token)).status,403);
  assert.equal((await f.request('/accounts/'+user.user.id,'PUT',{role:'user',enabled:false},f.admin)).status,200);
  assert.equal((await f.request('/me','GET',null,user.token)).status,401);
  assert.equal((await f.request('/login','POST',{email:user.user.email,password})).status,401);
 }finally{f.sqlite.close();}
});
test('users only read/change their own matches; staff edits never change ownership',async()=>{
 const f=await setup();try{
  const a=await f.create('a@example.com','user'),b=await f.create('b@example.com','user'),staff=await f.create('manager@example.com','staff');
  const own=mutation('owned-a');own.body.owner_id=b.user.id;
  assert.equal((await f.request('/matches/owned-a','PUT',own,a.token)).status,200);
  for(const attempt of [own,{...own,base_version:1,mutation_id:crypto.randomUUID(),deleted:true},{...own,base_version:999,mutation_id:crypto.randomUUID()}]){
   const denied=await f.request('/matches/owned-a','PUT',attempt,b.token);assert.equal(denied.status,403);assert.equal(denied.body.current,undefined);
  }
  assert.deepEqual((await f.request('/matches','GET',null,b.token)).body.records,[]);
  assert.equal((await f.request('/matches/owned-a','PUT',mutation('owned-a',1),staff.token)).status,200);
  assert.equal((await f.request('/matches','GET',null,a.token)).body.records[0].owner_id,a.user.id);
  assert.equal((await f.request('/matches/owned-a','PUT',mutation('owned-a',2),a.token)).status,200);
  assert.equal((await f.request('/matches','GET',null,f.admin)).body.records.length,1);
  assert.equal((await f.request('/matches/owned-a','PUT',{...mutation('owned-a',3),deleted:true},a.token)).status,200);
 }finally{f.sqlite.close();}
});
test('reference database edits are manager-only and reject stale overwrites',async()=>{
 const f=await setup();try{
  const staff=await f.create('manager@example.com','staff'),user=await f.create('reader@example.com','user');
  assert.equal((await f.request('/catalog/manage','GET',null,user.token)).status,403);
  const tables=(await f.request('/catalog/manage','GET',null,staff.token)).body.tables;
  const schools=tables.find(t=>t.name==='Schools'),update={base_version:schools.version,rows:[...schools.rows,{ID:100,School_ID:'Test School'}]};
  assert.equal((await f.request('/catalog/manage/Schools','PUT',update,user.token)).status,403);
  assert.equal((await f.request('/catalog/manage/Schools','PUT',update,staff.token)).status,200);
  assert.equal((await f.request('/catalog/manage/Schools','PUT',update,f.admin)).status,409);
  assert.equal((await f.request('/catalog/manage/Schools','PUT',{base_version:2,rows:[{ID:1,School_ID:'A'},{ID:1,School_ID:'B'}]},f.admin)).status,400);
  assert.equal((await f.request('/catalog','GET',null,user.token)).body.Schools.at(-1).School_ID,'Test School');
 }finally{f.sqlite.close();}
});
