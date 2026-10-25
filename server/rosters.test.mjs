import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
test('roster roles, coach scope, history, visibility and conflicts',async()=>{
 const f=fixture();try{
  const token=await f.login(),p={id:'a'.repeat(32),number:9999,active:true};
  for(const role of ['owner','admin','user','coach']){
   f.sqlite.prepare("UPDATE users SET role=?").run(role==='owner'?'admin':role==='coach'?'user':role);
   f.sqlite.prepare('INSERT OR REPLACE INTO account_access(user_id,owner) SELECT id,? FROM users').run(role==='owner'?1:0);
   f.sqlite.exec('DELETE FROM coach_assignments');
   if(role==='coach')f.sqlite.exec("INSERT INTO coach_assignments SELECT id,'U15A','BASKETBALL' FROM users");
   let current=await f.request('/rosters?team=U15A','GET',null,token);
   assert.equal(current.status,200);
   const result=await f.request('/rosters?team=U15A','PUT',{version:current.body.version,players:[p]},token);assert.equal(result.status,200);
   assert.equal((await f.request('/rosters?team=U15A','PUT',{version:current.body.version,players:[p]},token)).status,409);
  }
  assert.equal((await f.request('/rosters?team=U15B','GET',null,token)).status,403);
  let data=(await f.request('/rosters?team=U15A','GET',null,token)).body;
  assert.equal((await f.request('/rosters?team=U15A','PUT',{...data,players:[{...p,number:10000}]},token)).status,400);
  assert.equal((await f.request('/rosters?team=U15A','PUT',{...data,players:[]},token)).status,400);
  assert.equal((await f.request('/rosters?team=U15A','PUT',{...data,players:[{...p,active:false}]},token)).status,200);
  f.sqlite.prepare('UPDATE account_access SET hidden=1').run();
  assert.deepEqual((await f.request('/rosters?team=U15A','GET',null,token)).body,{version:0,players:[]});
 }finally{f.sqlite.close();}
});
