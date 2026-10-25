import {coachProfile} from './coach.mjs';
import {createRemoteJWKSet,jwtVerify} from 'jose';
import {consumeFactor,limited} from './security.mjs';
export const AUTH0={domain:'dev-oh5h8875qsfq7eja.us.auth0.com',clients:{
 web:'u8NnDj8nN6Vo8aGMR3JCA0PaoVqvaVgu',
 windows:'NfWZEcFXPqaBdKG453NTD0EeAeRLyERh',
 android:'yC7iKrieD91ASJvl0kiyMsYGWLfzED2D'
}};
const issuer='https://'+AUTH0.domain+'/';
const jwks=createRemoteJWKSet(new URL(issuer+'.well-known/jwks.json'),{timeoutDuration:10000});
const bytes=s=>new TextEncoder().encode(s);
const hex=b=>Array.from(new Uint8Array(b),n=>n.toString(16).padStart(2,'0')).join('');
const hash=async s=>hex(await crypto.subtle.digest('SHA-256',bytes(s)));
const b64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
const random=()=>b64(crypto.getRandomValues(new Uint8Array(32)));
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const fail=()=>reply({error:'Auth0 sign-in expired or could not be verified. Start again.'},401);
function page(ok){
 return new Response('<!doctype html><html><meta name="viewport" content="width=device-width"><title>Stat Tracker sign-in</title><body><h1>Stat Tracker</h1><p>'+(ok?'Browser sign-in completed. Return to Stat Tracker to finish.':'Sign-in was cancelled or expired. Return to Stat Tracker and try again.')+'</p></body></html>',{status:ok?200:400,headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"}});
}
export async function verifyIdentity(token,flow){
 const {payload}=await jwtVerify(token,jwks,{issuer,audience:flow.client_id,algorithms:['RS256'],requiredClaims:['sub','iat','exp','nonce'],maxTokenAge:'10m',clockTolerance:5});
 if(payload.nonce!==flow.nonce||typeof payload.sub!=='string'||payload.sub.length>255||(payload.azp&&payload.azp!==flow.client_id)||(Array.isArray(payload.aud)&&payload.aud.length>1&&payload.azp!==flow.client_id))throw new Error('invalid-identity');
 return payload;
}
export async function auth0Routes(request,env,bodyOf,staff,passwordHash,equal){
 const db=env.DB,url=new URL(request.url),path=url.pathname;
 if(path==='/auth0/config'&&request.method==='GET')return reply({domain:AUTH0.domain,available:true});
 if(path==='/auth0/callback'&&request.method==='GET'){
  const state=url.searchParams.get('state'),code=url.searchParams.get('code'),error=url.searchParams.get('error');
  if(!state||!/^[-_A-Za-z0-9]{43}$/.test(state))return page(false);
  if(error){await db.prepare("UPDATE auth0_flows SET status='failed' WHERE state_hash=? AND status='pending'").bind(await hash(state)).run();return page(false);}
  if(!code||code.length>4096)return page(false);
  const saved=await db.prepare("UPDATE auth0_flows SET code=?,status='ready' WHERE state_hash=? AND status='pending' AND expires_at>? RETURNING ticket_hash").bind(code,await hash(state),Date.now()).first();
  return page(!!saved);
 }
 if(request.method!=='POST')return reply({error:'Not found.'},404);
 const b=await bodyOf(request);
 if(path==='/auth0/start'){
  const client=Object.hasOwn(AUTH0.clients,b.platform)?AUTH0.clients[b.platform]:null;
  if(!client||!/^[-_A-Za-z0-9]{43}$/.test(b.challenge||''))return reply({error:'Unsupported sign-in request.'},400);
  if(await limited(db,'auth0-start:'+await hash(request.headers.get('CF-Connecting-IP')||'unknown')))return reply({error:'Too many sign-in requests. Try again in ten minutes.'},429);
  let user=null,sessionHash='',purpose=b.purpose==='link'?'link':'login';
  if(purpose==='link'){
   user=await staff(request,db);if(!user)return fail();
   if(await limited(db,'auth0-link:'+user.id))return reply({error:'Too many attempts. Try again in ten minutes.'},429);
   const account=await db.prepare('SELECT * FROM users WHERE id=? AND enabled=1').bind(user.id).first();
   if(!account||typeof b.password!=='string'||b.password.length>128||!equal(await passwordHash(b.password,account.password_salt),account.password_hash)||!await consumeFactor(db,env,user.id,b.code))return reply({error:'Enter your current Stat Tracker password and a fresh authenticator or recovery code if 2FA is enabled.'},401);
   if(!await staff(request,db))return fail();
   sessionHash=await hash(request.headers.get('Authorization').slice(7));
  }
  const ticket=random(),state=random(),nonce=random(),redirect=url.origin+'/auth0/callback';
  await db.batch([
   db.prepare('DELETE FROM auth0_flows WHERE expires_at<=?').bind(Date.now()),
   db.prepare('INSERT INTO auth0_flows(ticket_hash,state_hash,client_id,challenge,nonce,redirect_uri,purpose,user_id,session_hash,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)').bind(await hash(ticket),await hash(state),client,b.challenge,nonce,redirect,purpose,user?.id||null,sessionHash,Date.now()+600000)
  ]);
  const authorize=new URL(issuer+'authorize');authorize.search=new URLSearchParams({response_type:'code',client_id:client,redirect_uri:redirect,scope:'openid profile email',state,nonce,code_challenge:b.challenge,code_challenge_method:'S256',prompt:'login'}).toString();
  return reply({ticket,authorize_url:authorize.href,expires_in:600});
 }
 if(!/^[-_A-Za-z0-9]{43}$/.test(b.ticket||''))return fail();
 const ticketHash=await hash(b.ticket);
 if(path==='/auth0/cancel'){
  await db.prepare('DELETE FROM auth0_flows WHERE ticket_hash=?').bind(ticketHash).run();return reply({ok:true});
 }
 const flow=await db.prepare('SELECT * FROM auth0_flows WHERE ticket_hash=? AND expires_at>?').bind(ticketHash,Date.now()).first();
 if(!flow)return fail();
 if(path==='/auth0/status')return reply({status:flow.status});
 if(path!=='/auth0/finish')return reply({error:'Not found.'},404);
 if(typeof b.verifier!=='string'||!/^[-._~A-Za-z0-9]{43,128}$/.test(b.verifier)||b64(await crypto.subtle.digest('SHA-256',bytes(b.verifier)))!==flow.challenge)return fail();
 if(flow.purpose==='link'){
  const user=await staff(request,db);
  if(!user||user.id!==flow.user_id||await hash(request.headers.get('Authorization').slice(7))!==flow.session_hash)return fail();
 }
 const claimed=await db.prepare("UPDATE auth0_flows SET status='processing',code=NULL WHERE ticket_hash=? AND status='ready' AND expires_at>? RETURNING ticket_hash").bind(ticketHash,Date.now()).first();
 if(!claimed)return fail();
 let identity;
 try{
  const response=await fetch(issuer+'oauth/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({grant_type:'authorization_code',client_id:flow.client_id,code:flow.code,code_verifier:b.verifier,redirect_uri:flow.redirect_uri}),signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw new Error('token-exchange');
  const tokens=await response.json();identity=await verifyIdentity(tokens.id_token,flow);
 }catch{
  await db.prepare('DELETE FROM auth0_flows WHERE ticket_hash=?').bind(ticketHash).run();return fail();
 }
 // Revocation during the network request cancels the transaction.
 const consumed=await db.prepare("DELETE FROM auth0_flows WHERE ticket_hash=? AND status='processing' AND expires_at>? RETURNING ticket_hash").bind(ticketHash,Date.now()).first();
 if(!consumed)return fail();
 if(flow.purpose==='link'){
  const user=await staff(request,db);
  if(!user||user.id!==flow.user_id)return fail();
  if(identity.email_verified!==true||typeof identity.email!=='string'||identity.email.toLowerCase()!==user.email.toLowerCase())return reply({error:'Use an Auth0 account with the same verified email as your Stat Tracker account. Verify the email in Auth0 first.'},403);
  const existing=await db.prepare('SELECT user_id FROM auth0_links WHERE issuer=? AND subject=?').bind(issuer,identity.sub).first();
  if(existing&&existing.user_id!==user.id)return reply({error:'That Auth0 account is already linked to another account.'},409);
  const own=await db.prepare('SELECT subject FROM auth0_links WHERE user_id=?').bind(user.id).first();
  if(own&&own.subject!==identity.sub)return reply({error:'This account already has a different Auth0 identity linked. Contact your administrator.'},409);
  await db.prepare('INSERT INTO auth0_links(issuer,subject,user_id) VALUES(?,?,?) ON CONFLICT DO NOTHING').bind(issuer,identity.sub,user.id).run();
  const saved=await db.prepare('SELECT user_id FROM auth0_links WHERE issuer=? AND subject=?').bind(issuer,identity.sub).first();
  return saved?.user_id===user.id?reply({linked:true}):fail();
 }
 const account=await db.prepare('SELECT u.* FROM users u JOIN auth0_links a ON a.user_id=u.id WHERE a.issuer=? AND a.subject=? AND u.enabled=1').bind(issuer,identity.sub).first();
 if(!account)return reply({error:'Link this Auth0 account first: sign in with your existing Stat Tracker password, then open Profile and security → Connect Auth0. Your existing matches stay with that account.'},403);
 // Existing app 2FA remains enforced until the owner explicitly changes it.
 if(!await consumeFactor(db,env,account.id,b.code))return reply({error:'Enter a fresh Stat Tracker authenticator or recovery code, then start Auth0 sign-in again.',two_factor_required:true},401);
 const token=random(),expires=Date.now()+7*86400000;
 const saved=await db.prepare('INSERT INTO sessions(token_hash,user_id,expires_at) SELECT ?,u.id,? FROM users u JOIN auth0_links a ON a.user_id=u.id WHERE u.id=? AND u.enabled=1 AND u.password_hash=? AND a.issuer=? AND a.subject=? RETURNING user_id').bind(await hash(token),expires,account.id,account.password_hash,issuer,identity.sub).first();
 if(!saved)return fail();
 return reply({token,expires_at:expires,user:await coachProfile(db,{id:account.id,email:account.email,display_name:account.display_name,role:account.role})});
}
