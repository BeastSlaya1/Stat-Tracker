import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './worker.test.mjs';
import {totp} from './security.mjs';
const password='Strong test password 123',email='staff@example.com';
function configured(f){Object.assign(f.env,{TWILIO_ACCOUNT_SID:'AC'+'1'.repeat(32),TWILIO_VERIFY_SERVICE_SID:'VA'+'2'.repeat(32),TWILIO_AUTH_TOKEN:'test-only',SIGNIN_EMAIL:'true',SIGNIN_SMS:'true'});}
function provider(t){
 let n=0;const sent=[];
 t.mock.method(globalThis,'fetch',async(url,init)=>{
  const p=new URLSearchParams(init.body);
  assert.ok(url.startsWith('https://verify.twilio.com/v2/Services/'));
  if(url.endsWith('/Verifications')){const sid='VE'+(++n).toString(16).padStart(32,'0');sent.push({sid,to:p.get('To'),channel:p.get('Channel')});return Response.json({sid,status:'pending'});}
  return Response.json({status:p.get('Code')==='123456'&&sent.some(x=>x.sid===p.get('VerificationSid'))?'approved':'pending'});
 });return sent;
}
async function enroll(f,token,channel='email'){
 const start=await f.request('/signin/enroll','POST',{password,channel},token);assert.equal(start.status,200);
 const confirmed=await f.request('/signin/confirm','POST',{challenge:start.body.challenge,verification_code:'123456'},token);assert.equal(confirmed.status,200);
}
test('unconfigured delivery stays off and unknown routes do not bypass authentication',async()=>{
 const f=fixture();try{await f.login();const methods=await f.request('/signin/methods');assert.equal(methods.body.email,false);assert.equal(methods.body.sms,false);
 assert.equal((await f.request('/signin/start','POST',{email,channel:'email'})).status,503);
 assert.equal((await f.request('/signin/authenticator','POST',{email,code:'123456'})).status,401);
 assert.equal((await f.request('/signin/preference','POST',{method:'authenticator',enabled:true})).status,401);
 }finally{f.sqlite.close();}
});
test('authenticator-only sign-in requires opt-in and a fresh TOTP; replay and recovery-only login fail',async()=>{
 const f=fixture();try{
  const token=await f.login(),step=Math.floor(Date.now()/30000);
  const setup=await f.request('/security/setup','POST',{password},token);
  const confirm=await f.request('/security/confirm','POST',{password,code:await totp(setup.body.secret,step-1)},token);
  assert.equal(confirm.status,200);
  assert.equal((await f.request('/signin/authenticator','POST',{email,code:await totp(setup.body.secret,step)})).status,401);
  assert.equal((await f.request('/signin/preference','POST',{method:'authenticator',enabled:true,password,code:await totp(setup.body.secret,step)},token)).status,200);
  const code=await totp(setup.body.secret,step+1);
  const replies=await Promise.all([f.request('/signin/authenticator','POST',{email,code}),f.request('/signin/authenticator','POST',{email,code})]);
  assert.deepEqual(replies.map(x=>x.status).sort(),[200,401]);
  assert.equal((await f.request('/signin/authenticator','POST',{email,code:confirm.body.recovery_codes[0]})).status,401);
  assert.equal((await f.request('/security/disable','POST',{password,code:confirm.body.recovery_codes[0]},token)).status,200);
  assert.equal(f.sqlite.prepare('SELECT authenticator_login FROM signin_methods').get().authenticator_login,0);
 }finally{f.sqlite.close();}
});
test('email verification is session-bound and a login code is single-use',async t=>{
 const f=fixture();configured(f);const sent=provider(t);try{
  const token=await f.login();
  const unverified=await f.request('/signin/start','POST',{email,channel:'email'});assert.equal(unverified.status,200);assert.equal(sent.length,0);
  const start=await f.request('/signin/enroll','POST',{password,channel:'email'},token);assert.equal(start.status,200);
  const other=(await f.request('/login','POST',{email,password})).body.token;
  assert.equal((await f.request('/signin/confirm','POST',{challenge:start.body.challenge,verification_code:'123456'},other)).status,401);
  assert.equal((await f.request('/signin/check','POST',{challenge:start.body.challenge,verification_code:'123456'})).status,401);
  assert.equal((await f.request('/signin/confirm','POST',{challenge:start.body.challenge,verification_code:'123456'},token)).status,200);
  assert.equal((await f.request('/signin/options','GET',null,token)).body.email_verified,true);
  const login=await f.request('/signin/start','POST',{email,channel:'email'});
  const body={challenge:login.body.challenge,verification_code:'123456'};
  const replies=await Promise.all([f.request('/signin/check','POST',body),f.request('/signin/check','POST',body)]);
  assert.deepEqual(replies.map(x=>x.status).sort(),[200,401]);
  assert.equal((await f.request('/signin/check','POST',body)).status,401);
  assert.equal(sent.at(-1).to,email);
 }finally{f.sqlite.close();}
});
test('SMS uses the verified saved phone; contact changes invalidate pending codes',async t=>{
 const f=fixture();configured(f);const sent=provider(t);try{
  const token=await f.login();
  assert.equal((await f.request('/profile','POST',{password,email,phone:'+27821234567'},token)).status,200);
  await enroll(f,token,'sms');
  const login=await f.request('/signin/start','POST',{email,channel:'sms',phone:'+19999999999'});
  assert.equal(sent.at(-1).to,'+27821234567');
  assert.equal((await f.request('/profile','POST',{password,email,phone:'+27821234568'},token)).status,200);
  assert.equal((await f.request('/signin/check','POST',{challenge:login.body.challenge,verification_code:'123456'})).status,401);
  assert.equal((await f.request('/signin/options','GET',null,token)).body.sms_verified,false);
 }finally{f.sqlite.close();}
});
test('bad, expired and revoked codes fail; wrong guesses have an account budget',async t=>{
 const f=fixture();configured(f);provider(t);try{
  const token=await f.login();await enroll(f,token);
  const login=await f.request('/signin/start','POST',{email,channel:'email'});
  assert.equal((await f.request('/signin/check','POST',{challenge:login.body.challenge,verification_code:'000000'})).status,401);
  f.sqlite.prepare('UPDATE signin_challenges SET expires_at=0').run();
  assert.equal((await f.request('/signin/check','POST',{challenge:login.body.challenge,verification_code:'123456'})).status,401);
  const next=await f.request('/signin/start','POST',{email,channel:'email'});
  assert.equal((await f.request('/signin/preference','POST',{password,method:'email',enabled:false},token)).status,200);
  assert.equal((await f.request('/signin/check','POST',{challenge:next.body.challenge,verification_code:'123456'})).status,401);
  for(let i=0;i<11;i++)await f.request('/signin/authenticator','POST',{email,code:'000000'});
  assert.equal((await f.request('/signin/authenticator','POST',{email,code:'000000'})).status,429);
 }finally{f.sqlite.close();}
});
test('email login cannot bypass configured two-factor authentication',async t=>{
 const f=fixture();configured(f);provider(t);try{
  const token=await f.login();await enroll(f,token);
  const setup=await f.request('/security/setup','POST',{password},token),step=Math.floor(Date.now()/30000);
  assert.equal((await f.request('/security/confirm','POST',{password,code:await totp(setup.body.secret,step-1)},token)).status,200);
  const login=await f.request('/signin/start','POST',{email,channel:'email'});
  const body={challenge:login.body.challenge,verification_code:'123456'};
  assert.equal((await f.request('/signin/check','POST',body)).status,401);
  assert.equal((await f.request('/signin/check','POST',{...body,code:await totp(setup.body.secret,step)})).status,200);
 }finally{f.sqlite.close();}
});
test('password changes clear optional enrollment and outstanding login codes',async t=>{
 const f=fixture();configured(f);provider(t);try{
  const token=await f.login();await enroll(f,token);
  const login=await f.request('/signin/start','POST',{email,channel:'email'});
  assert.equal((await f.request('/password','POST',{current_password:password,new_password:'Different test password 456'},token)).status,200);
  assert.equal(f.sqlite.prepare('SELECT email_address FROM signin_methods').get().email_address,null);
  assert.equal((await f.request('/signin/check','POST',{challenge:login.body.challenge,verification_code:'123456'})).status,401);
 }finally{f.sqlite.close();}
});
test('delivery failure issues no challenge or session and returns no provider secrets',async t=>{
 const f=fixture();configured(f);t.mock.method(globalThis,'fetch',async()=>Response.json({error:'private-provider-detail'},{status:500}));try{
  const token=await f.login();
  const result=await f.request('/signin/enroll','POST',{password,channel:'email'},token);
  assert.equal(result.status,503);assert.ok(!JSON.stringify(result.body).includes('private-provider-detail'));
  assert.equal(f.sqlite.prepare('SELECT count(*) n FROM signin_challenges').get().n,0);
 }finally{f.sqlite.close();}
});
