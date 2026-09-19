import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from './worker.mjs';

function fixture() {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
  sqlite.exec(readFileSync(new URL('./seed.sql',import.meta.url),'utf8'));
  const prepare = sql => {
    let values=[];
    return {
      bind(...args){values=args;return this;},
      async first(){return sqlite.prepare(sql).get(...values)||null;},
      async all(){return {results:sqlite.prepare(sql).all(...values)};},
      async run(){return sqlite.prepare(sql).run(...values);}
    };
  };
  const env = {DB:{prepare,async batch(statements){sqlite.exec('BEGIN');try {
    const values=[];for (const statement of statements)values.push(await statement.run());
    sqlite.exec('COMMIT');return values;
  }catch(error){sqlite.exec('ROLLBACK');throw error;}}},ADMIN_SETUP_KEY:'test-only-setup-key'};
  const request = async (path,method='GET',body,token='',origin='https://stattrackerv4.stream') => {
    const headers={'Origin':origin,'Content-Type':'application/json','CF-Connecting-IP':'127.0.0.1'};
    if(token)headers.Authorization='Bearer '+token;
    const response=await worker.fetch(new Request('https://test.example'+path,{method,headers,body:body?JSON.stringify(body):undefined}),env);
    return {status:response.status,body:response.status===204?null:await response.json()};
  };
  const login = async () => {
    assert.equal((await request('/admin/users','POST',{email:'staff@example.com',display_name:'Staff',password:'Strong test password 123'},env.ADMIN_SETUP_KEY)).status,201);
    const session=await request('/login','POST',{email:'staff@example.com',password:'Strong test password 123'});
    assert.equal(session.status,200);return session.body.token;
  };
  return {sqlite,request,login};
}
test('staff authentication protects data, passwords are hashed, and logout revokes access',async()=>{
 const f=fixture();try {
  assert.equal((await f.request('/matches')).status,401);
  assert.equal((await f.request('/admin/users','POST',{})).status,401);
  const token=await f.login();
  const user=f.sqlite.prepare('SELECT * FROM users').get();
  assert.notEqual(user.password_hash,'Strong test password 123');
  assert.equal(user.password_hash.length,64);
  assert.equal((await f.request('/catalog','GET',null,token)).body.Schools.length,13);
  assert.equal((await f.request('/logout','POST',{},token)).status,200);
  assert.equal((await f.request('/matches','GET',null,token)).status,401);
 }finally{f.sqlite.close();}
});
test('retries are idempotent and stale edits cannot overwrite another staff edit',async()=>{
 const f=fixture();try{
  const token=await f.login();
  const team={id:'home',name:'SCC',short_name:'SCC',logo_color:'#000000',secondary_color:'#ffffff',badge_symbol:''};
  const body={id:'match-1',sport:'SOCCER',title:'Match',date:'2026-09-19',location:'Home',home_team:team,away_team:{...team,id:'away',name:'Opponent'},events:[],home_score:0};
  const update={base_version:0,mutation_id:'mutation-000000001',body,deleted:false};
  assert.equal((await f.request('/matches/match-1','PUT',update,token)).body.version,1);
  assert.equal((await f.request('/matches/match-1','PUT',update,token)).body.version,1);
  const next={...update,base_version:1,mutation_id:'mutation-000000002',body:{...body,home_score:2}};
  assert.equal((await f.request('/matches/match-1','PUT',next,token)).body.version,2);
  const stale={...next,mutation_id:'mutation-000000003',body:{...body,home_score:1}};
  const conflict=await f.request('/matches/match-1','PUT',stale,token);
  assert.equal(conflict.status,409);assert.equal(conflict.body.current.body.home_score,2);
  const deleted={...next,base_version:2,mutation_id:'mutation-000000004',deleted:true};
  assert.equal((await f.request('/matches/match-1','PUT',deleted,token)).body.version,3);
  const records=(await f.request('/matches','GET',null,token)).body.records;
  assert.equal(records.length,1);assert.equal(records[0].deleted,true);
 }finally{f.sqlite.close();}
});
test('unknown origins, excessive sign-in attempts and malformed records are rejected',async()=>{
 const f=fixture();try{
  assert.equal((await f.request('/health','GET',null,'','https://unrelated.example')).status,403);
  for(let i=0;i<10;i++)assert.equal((await f.request('/login','POST',{email:'none@example.com',password:'wrong'})).status,401);
  assert.equal((await f.request('/login','POST',{email:'none@example.com',password:'wrong'})).status,429);
  const token=await f.login();
  assert.equal((await f.request('/matches/match-1','PUT',{base_version:-1},token)).status,400);
 }finally{f.sqlite.close();}
});
