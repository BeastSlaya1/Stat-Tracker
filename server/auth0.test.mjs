import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPair,exportJWK,SignJWT} from 'jose';
import {fixture} from './worker.test.mjs';
import worker from './worker.mjs';
import {AUTH0} from './auth0.mjs';
const password='Strong test password 123',email='staff@example.com';
const {privateKey,publicKey}=await generateKeyPair('RS256');
const jwk={...await exportJWK(publicKey),kid:'test-key',alg:'RS256',use:'sig'};
const issuer='https://'+AUTH0.domain+'/';
const verifier='v'.repeat(64),challenge=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))).toString('base64url');
async function callback(f,start){
 const state=new URL(start.body.authorize_url).searchParams.get('state');
 return worker.fetch(new Request('https://test.example/auth0/callback?state='+encodeURIComponent(state)+'&code=test-code'),f.env);
}
async function start(f,token='',purpose='login',extra={}){
 const result=await f.request('/auth0/start','POST',{platform:'windows',challenge,purpose,password,...extra},token);
 assert.equal(result.status,200);return result;
}
function provider(t,f,overrides={}){
 t.mock.method(globalThis,'fetch',async(url,init)=>{
  const href=String(url);
  if(href.endsWith('/.well-known/jwks.json'))return Response.json({keys:[jwk]});
  assert.equal(href,issuer+'oauth/token');
  const body=JSON.parse(init.body);assert.equal(body.code_verifier,verifier);assert.ok(!('client_secret' in body));
  const flow=f.sqlite.prepare("SELECT * FROM auth0_flows WHERE status='processing' ORDER BY expires_at DESC").get();
  const claims={email,email_verified:true,nonce:flow.nonce,...overrides};
  const token=await new SignJWT(claims).setProtectedHeader({alg:'RS256',kid:'test-key'}).setIssuer(overrides.iss||issuer).setAudience(overrides.aud||flow.client_id).setSubject(overrides.sub||'auth0|test-user').setIssuedAt().setExpirationTime(overrides.exp||'5m').sign(privateKey);
  return Response.json({id_token:token});
 });
}
async function link(f,token){const begin=await start(f,token,'link');assert.equal((await callback(f,begin)).status,200);const result=await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier},token);assert.equal(result.status,200);assert.equal(result.body.linked,true);}
test('Auth0 requires explicit linking, preserves the account, and consumes login once',async t=>{
 const f=fixture();provider(t,f);try{
  const token=await f.login();
  const unlinked=await start(f);await callback(f,unlinked);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:unlinked.body.ticket,verifier})).status,403);
  assert.equal(f.sqlite.prepare('SELECT count(*) n FROM users').get().n,1);
  await link(f,token);
  const login=await start(f);await callback(f,login);
  const result=await f.request('/auth0/finish','POST',{ticket:login.body.ticket,verifier});
  assert.equal(result.status,200);assert.equal(result.body.user.email,email);assert.equal(result.body.user.role,'staff');
  assert.equal((await f.request('/me','GET',null,result.body.token)).status,200);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:login.body.ticket,verifier})).status,401);
 }finally{f.sqlite.close();}
});
test('wrong PKCE verifier, invalid state, cancellation and expired flows are rejected',async t=>{
 const f=fixture();provider(t,f);try{
  await f.login();const begin=await start(f);
  assert.equal((await worker.fetch(new Request('https://test.example/auth0/callback?state=wrong&code=x'),f.env)).status,400);
  await callback(f,begin);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier:'x'.repeat(64)})).status,401);
  await f.request('/auth0/cancel','POST',{ticket:begin.body.ticket});
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier})).status,401);
  const expired=await start(f);f.sqlite.exec('UPDATE auth0_flows SET expires_at=0');
  assert.equal((await callback(f,expired)).status,400);
 }finally{f.sqlite.close();}
});
for(const [name,claims] of [['nonce',{nonce:'wrong'}],['audience',{aud:'other-client'}],['issuer',{iss:'https://attacker.invalid/'}],['expiry',{exp:1}]]){
 test('Auth0 rejects incorrect '+name,async t=>{const f=fixture();provider(t,f,claims);try{
  const token=await f.login(),begin=await start(f,token,'link');await callback(f,begin);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier},token)).status,401);
  assert.equal(f.sqlite.prepare('SELECT count(*) n FROM auth0_links').get().n,0);
 }finally{f.sqlite.close();}});
}
test('linking needs existing password and matching verified email',async t=>{
 const f=fixture();provider(t,f,{email_verified:false});try{
  const token=await f.login();
  assert.equal((await f.request('/auth0/start','POST',{platform:'web',challenge,purpose:'link',password:'wrong'},token)).status,401);
  const begin=await start(f,token,'link');await callback(f,begin);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier},token)).status,403);
 }finally{f.sqlite.close();}
});
test('another session cannot complete a link and disabling the user cancels access',async t=>{
 const f=fixture();provider(t,f);try{
  const token=await f.login(),other=(await f.request('/login','POST',{email,password})).body.token;
  const begin=await start(f,token,'link');await callback(f,begin);
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier},other)).status,401);
  f.sqlite.exec('UPDATE users SET enabled=0');
  assert.equal((await f.request('/auth0/finish','POST',{ticket:begin.body.ticket,verifier},token)).status,401);
 }finally{f.sqlite.close();}
});

test('Auth0 login enforces existing 2FA and consumes a flow only once under concurrency',async t=>{
 const f=fixture();provider(t,f);try{
  const token=await f.login();await link(f,token);
  const {totp}=await import('./security.mjs');
  const secret=(await f.request('/security/setup','POST',{password},token)).body.secret;
  const enrolled=await f.request('/security/confirm','POST',{password,code:await totp(secret,Math.floor(Date.now()/30000))},token);
  assert.equal(enrolled.status,200);
  const missing=await start(f);await callback(f,missing);
  const denied=await f.request('/auth0/finish','POST',{ticket:missing.body.ticket,verifier});
  assert.equal(denied.status,401);assert.equal(denied.body.two_factor_required,true);
  const fresh=await start(f);await callback(f,fresh);
  const body={ticket:fresh.body.ticket,verifier,code:enrolled.body.recovery_codes[0]};
  const results=await Promise.all([f.request('/auth0/finish','POST',body),f.request('/auth0/finish','POST',body)]);
  assert.deepEqual(results.map(r=>r.status).sort(),[200,401]);
 }finally{f.sqlite.close();}
});
