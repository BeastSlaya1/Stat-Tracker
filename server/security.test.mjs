import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
import {totp,base32} from './security.mjs';
const password='Strong test password 123';
const login=(code)=>({email:'staff@example.com',password,code});
const setup=async f=>{const token=await f.login();const other=(await f.request('/login','POST',login())).body.token;const result=await f.request('/security/setup','POST',{password},token);assert.equal(result.status,200);return {token,other,secret:result.body.secret};};
test('RFC 6238 reference vectors',async()=>{
 const secret=base32(new TextEncoder().encode('12345678901234567890'));
 for(const [time,expected] of [[59,'94287082'],[1111111109,'07081804'],[1111111111,'14050471'],[1234567890,'89005924'],[2000000000,'69279037'],[20000000000,'65353130']])assert.equal(await totp(secret,Math.floor(time/30),8),expected);
});
test('enrollment is encrypted, requires confirmation, enforces codes and revokes other sessions',async()=>{
 const f=fixture();try{
  const {token,other,secret}=await setup(f);
  assert.equal((await f.request('/login','POST',login())).status,200);
  assert.ok(!f.sqlite.prepare('SELECT pending FROM account_security').get().pending.includes(secret));
  assert.equal((await f.request('/security/confirm','POST',{password,code:'wrong'},token)).status,400);
  const code=await totp(secret,Math.floor(Date.now()/30000));
  const result=await f.request('/security/confirm','POST',{password,code},token);
  assert.equal(result.status,200);assert.equal(result.body.recovery_codes.length,10);
  assert.equal((await f.request('/me','GET',null,other)).status,401);
  assert.equal((await f.request('/login','POST',login())).status,401);
  assert.equal((await f.request('/login','POST',login(code))).status,401,'setup code cannot be replayed');
  const recovery=result.body.recovery_codes[0];
  assert.equal((await f.request('/login','POST',login(recovery))).status,200);
  assert.equal((await f.request('/login','POST',login(recovery))).status,401);
  const stored=f.sqlite.prepare('SELECT * FROM account_security').get();
  assert.ok(!stored.secret.includes(secret));assert.ok(!stored.recovery_hashes.includes(recovery));
  assert.equal((await f.request('/security/disable','POST',{password},token)).status,400);
  assert.equal((await f.request('/security/disable','POST',{password,code:result.body.recovery_codes[1]},token)).status,200);
  assert.equal((await f.request('/login','POST',login())).status,200);
 }finally{f.sqlite.close();}
});
test('fresh codes succeed once; concurrent replay cannot create two sessions',async()=>{
 const f=fixture();try{
  const {token,secret}=await setup(f),step=Math.floor(Date.now()/30000);
  assert.equal((await f.request('/security/confirm','POST',{password,code:await totp(secret,step-1)},token)).status,200);
  const code=await totp(secret,step);
  const results=await Promise.all([f.request('/login','POST',login(code)),f.request('/login','POST',login(code))]);
  assert.deepEqual(results.map(r=>r.status).sort(),[200,401]);
 }finally{f.sqlite.close();}
});
test('setup is bound to session, expires, and rate limits incorrect factors',async()=>{
 const f=fixture();try{
  const {token,other,secret}=await setup(f),code=await totp(secret,Math.floor(Date.now()/30000));
  assert.equal((await f.request('/security/confirm','POST',{password,code},other)).status,400);
  f.sqlite.prepare('UPDATE account_security SET pending_expires=0').run();
  assert.equal((await f.request('/security/confirm','POST',{password,code},token)).status,400);
  for(let i=0;i<8;i++)await f.request('/security/setup','POST',{password:'incorrect'},token);
  assert.equal((await f.request('/security/setup','POST',{password},token)).status,429);
 }finally{f.sqlite.close();}
});
test('profile details validate and update email sign-in, require password, and never reveal secrets',async()=>{
 const f=fixture();try{
  const token=await f.login();
  assert.equal((await f.request('/profile','POST',{email:'new@example.com',phone:'+27821234567'})).status,401);
  assert.equal((await f.request('/profile','POST',{password:'wrong',email:'new@example.com',phone:''},token)).status,400);
  assert.equal((await f.request('/profile','POST',{password,email:'new@example.com',phone:'123'},token)).status,400);
  assert.equal((await f.request('/profile','POST',{password,email:'new@example.com',phone:'+27 82 123 4567'},token)).status,200);
  assert.deepEqual((await f.request('/profile','GET',null,token)).body,{email:'new@example.com',phone:'+27821234567',two_factor_enabled:false});
  assert.equal((await f.request('/login','POST',login())).status,401);
  assert.equal((await f.request('/login','POST',{email:'new@example.com',password})).status,200);
 }finally{f.sqlite.close();}
});
test('enrollment fails safely without encryption key and wrong codes are throttled per account',async()=>{
 const f=fixture();try{
  const token=await f.login();const key=f.env.MFA_ENCRYPTION_KEY;delete f.env.MFA_ENCRYPTION_KEY;
  assert.equal((await f.request('/security/setup','POST',{password},token)).status,503);
  f.env.MFA_ENCRYPTION_KEY=key;
  const secret=(await f.request('/security/setup','POST',{password},token)).body.secret;
  const confirmation=await f.request('/security/confirm','POST',{password,code:await totp(secret,Math.floor(Date.now()/30000))},token);
  assert.equal(confirmation.status,200);
  for(let i=0;i<10;i++)assert.equal((await f.request('/login','POST',login('wrong'),'','https://stattrackerv4.stream',{'CF-Connecting-IP':'ip-'+i})).status,401);
  assert.equal((await f.request('/login','POST',login(confirmation.body.recovery_codes[0]),'','https://stattrackerv4.stream',{'CF-Connecting-IP':'fresh-ip'})).status,401);
 }finally{f.sqlite.close();}
});
test('profile changes require second factor and account deletion removes all factor data',async()=>{
 const f=fixture();try{
  const admin=await f.login();f.sqlite.prepare("UPDATE users SET role='admin'").run();
  assert.equal((await f.request('/accounts','POST',{email:'target@example.com',display_name:'Target',role:'user',password},admin)).status,201);
  const token=(await f.request('/login','POST',{email:'target@example.com',password})).body.token;
  const secret=(await f.request('/security/setup','POST',{password},token)).body.secret;
  const result=await f.request('/security/confirm','POST',{password,code:await totp(secret,Math.floor(Date.now()/30000))},token);
  assert.equal(result.status,200);
  assert.equal((await f.request('/profile','POST',{password,email:'changed@example.com',phone:''},token)).status,400);
  const id=f.sqlite.prepare("SELECT id FROM users WHERE email='target@example.com'").get().id;
  assert.equal((await f.request('/accounts/'+id,'DELETE',{confirm_email:'target@example.com'},admin)).status,200);
  assert.equal(f.sqlite.prepare('SELECT count(*) n FROM account_security').get().n,0);
 }finally{f.sqlite.close();}
});
