import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
const password='Coach account test password 123';
test('coach sees only assigned team and sport and cannot change matches or accounts',async()=>{
 const f=fixture();try{
  const admin=await f.login();f.sqlite.prepare("UPDATE users SET role='admin'").run();
  const create={email:'coach@example.com',display_name:'Coach',password,role:'coach',team_code:'u15 a',sport:'BASKETBALL'};
  assert.equal((await f.request('/accounts','POST',{...create,team_code:''},admin)).status,400);
  const created=await f.request('/accounts','POST',create,admin);assert.equal(created.status,201);
  let login=await f.request('/login','POST',{email:create.email,password});const token=login.body.token;
  assert.equal(login.body.user.role,'coach');assert.equal(login.body.user.team_code,'U15A');
  for(const [id,team,sport] of [['yes','U15A','BASKETBALL'],['wrongteam','U15B','BASKETBALL'],['wrongsport','U15A','SOCCER'],['unassigned','','BASKETBALL']]){
   const t={id:'home',name:'SCC',short_name:'SCC',logo_color:'#000000',secondary_color:'#ffffff',badge_symbol:'',team_code:team};
   const body={id,sport,title:id,date:'2026-10-07',location:'Home',home_team:t,away_team:{...t,id:'away',team_code:'U15A'},events:[]};
   const mutation={body,deleted:false,base_version:0,mutation_id:crypto.randomUUID()};
   assert.equal((await f.request('/matches/'+id,'PUT',mutation,admin)).status,200);
   assert.equal((await f.request('/matches/'+id,'PUT',{...mutation,base_version:1},token)).status,403);
  }
  assert.deepEqual((await f.request('/matches','GET',null,token)).body.records.map(r=>r.id),['yes']);
  assert.equal((await f.request('/accounts','GET',null,token)).status,403);
  assert.equal((await f.request('/catalog/manage','GET',null,token)).status,403);
  const accounts=(await f.request('/accounts','GET',null,admin)).body.accounts;
  assert.equal(accounts.find(a=>a.id===created.body.id).role,'coach');
  assert.equal((await f.request('/accounts/'+created.body.id,'PUT',{role:'coach',enabled:true,team_code:'U15B',sport:'BASKETBALL'},admin)).status,200);
  assert.equal((await f.request('/matches','GET',null,token)).status,401);
  login=await f.request('/login','POST',{email:create.email,password});
  assert.deepEqual((await f.request('/matches','GET',null,login.body.token)).body.records.map(r=>r.id),['wrongteam']);
 }finally{f.sqlite.close();}
});

import {coachAssignment} from './coach.mjs';
test('shared dropdown generic choices normalize for coach matching',()=>{
 for(const team_code of ['1st Team','2nd Team','Other','U17 1st']){
  assert.equal(coachAssignment({team_code,sport:'BASKETBALL'}).team_code,team_code.replace(/\s+/g,'').toUpperCase());
 }
 assert.equal(coachAssignment({team_code:'',sport:'BASKETBALL'}),null);
});
