import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
const oldPassword='Strong test password 123',newPassword='A different password 456';
test('every role can change its own password; current session stays and other sessions expire',async()=>{
 for(const role of ['admin','staff','user']){
  const f=fixture();try{
   const token=await f.login();f.sqlite.prepare('UPDATE users SET role=?').run(role);
   const other=(await f.request('/login','POST',{email:'staff@example.com',password:oldPassword})).body.token;
   const before=f.sqlite.prepare('SELECT password_hash,password_salt FROM users').get();
   assert.equal((await f.request('/password','POST',{current_password:oldPassword,new_password:newPassword},token)).status,200);
   const after=f.sqlite.prepare('SELECT password_hash,password_salt FROM users').get();
   assert.notEqual(before.password_hash,after.password_hash);assert.notEqual(before.password_salt,after.password_salt);
   assert.notEqual(after.password_hash,newPassword);
   assert.equal((await f.request('/me','GET',null,token)).status,200);
   assert.equal((await f.request('/me','GET',null,other)).status,401);
   assert.equal((await f.request('/login','POST',{email:'staff@example.com',password:oldPassword})).status,401);
   assert.equal((await f.request('/login','POST',{email:'staff@example.com',password:newPassword})).status,200);
  }finally{f.sqlite.close();}
 }
});
test('password change requires sign-in and current password and throttles repeated failures',async()=>{
 const f=fixture();try{
  const token=await f.login(),body={current_password:oldPassword,new_password:newPassword};
  assert.equal((await f.request('/password','POST',body)).status,401);
  assert.equal((await f.request('/password','POST',{...body,new_password:'short'},token)).status,400);
  assert.equal((await f.request('/password','POST',{...body,new_password:oldPassword},token)).status,400);
  for(let i=0;i<9;i++)assert.equal((await f.request('/password','POST',{...body,current_password:'wrong'},token)).status,400);
  assert.equal((await f.request('/password','POST',body,token)).status,429);
  assert.equal((await f.request('/login','POST',{email:'staff@example.com',password:oldPassword})).status,200);
 }finally{f.sqlite.close();}
});
