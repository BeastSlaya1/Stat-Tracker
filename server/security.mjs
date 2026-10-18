// Authenticator-app TOTP (RFC 6238), encrypted enrollment, and single-use recovery.
const enc=new TextEncoder();
const hex=b=>Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('');
const unhex=s=>Uint8Array.from(s.match(/../g)||[],x=>parseInt(x,16));
const reply=(b,status=200)=>new Response(JSON.stringify(b),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
export function base32(bytes){let value=0,bits=0,out='';for(const b of bytes){value=(value<<8)|b;bits+=8;while(bits>=5){bits-=5;out+=alphabet[(value>>>bits)&31];}}if(bits)out+=alphabet[(value<<(5-bits))&31];return out;}
function decode32(s){let value=0,bits=0,out=[];for(const c of s){value=(value<<5)|alphabet.indexOf(c);bits+=5;if(bits>=8){bits-=8;out.push((value>>>bits)&255);}}return new Uint8Array(out);}
export async function totp(secret,step,digits=6){
 const counter=new ArrayBuffer(8);new DataView(counter).setBigUint64(0,BigInt(step));
 const key=await crypto.subtle.importKey('raw',decode32(secret),{name:'HMAC',hash:'SHA-1'},false,['sign']);
 const result=new Uint8Array(await crypto.subtle.sign('HMAC',key,counter)),offset=result[19]&15;
 return String((new DataView(result.buffer).getUint32(offset)&0x7fffffff)%10**digits).padStart(digits,'0');
}
const hash=async s=>hex(await crypto.subtle.digest('SHA-256',enc.encode(s)));
async function keyFor(env){
 if(!/^[a-fA-F0-9]{64}$/.test(env.MFA_ENCRYPTION_KEY||''))throw new Error('mfa-key-unavailable');
 return crypto.subtle.importKey('raw',unhex(env.MFA_ENCRYPTION_KEY),'AES-GCM',false,['encrypt','decrypt']);
}
async function seal(secret,env,id){const iv=crypto.getRandomValues(new Uint8Array(12));return hex(iv)+':'+hex(await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:enc.encode(id)},await keyFor(env),enc.encode(secret)));}
async function open(value,env,id){const [iv,data]=value.split(':');return new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:unhex(iv),additionalData:enc.encode(id)},await keyFor(env),unhex(data)));}
export async function limited(db,key){
 const now=Date.now();const a=await db.prepare(`INSERT INTO login_attempts(key,count,reset_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset_at<=? THEN 1 ELSE count+1 END, reset_at=CASE WHEN reset_at<=? THEN excluded.reset_at ELSE reset_at END RETURNING count`).bind(key,now+600000,now,now).first();return a.count>10;
}
async function validStep(secret,code,last=-1){
 if(typeof code!=='string'||!/^\d{6}$/.test(code))return null;
 const now=Math.floor(Date.now()/30000);
 for(const step of [now,now-1,now+1])if(step>last&&await totp(secret,step)===code)return step;
 return null;
}
export async function consumeFactor(db,env,id,code){
 const s=await db.prepare('SELECT * FROM account_security WHERE user_id=?').bind(id).first();
 if(!s?.secret)return true;
 if(await limited(db,'mfa:'+id))return false;
 if(typeof code!=='string'||code.length>80)return false;
 const step=await validStep(await open(s.secret,env,id),code.trim(),s.last_step);
 if(step!==null)return !!await db.prepare('UPDATE account_security SET last_step=? WHERE user_id=? AND secret=? AND last_step<? RETURNING user_id').bind(step,id,s.secret,step).first();
 const wanted=await hash(code.trim().replaceAll('-','').toLowerCase());
 const codes=JSON.parse(s.recovery_hashes);if(!codes.includes(wanted))return false;
 return !!await db.prepare('UPDATE account_security SET recovery_hashes=? WHERE user_id=? AND secret=? AND recovery_hashes=? RETURNING user_id').bind(JSON.stringify(codes.filter(c=>c!==wanted)),id,s.secret,s.recovery_hashes).first();
}
export async function securityRoutes(request,env,user,bodyOf,passwordHash,equal){
 const db=env.DB,path=new URL(request.url).pathname;
 let s=await db.prepare('SELECT * FROM account_security WHERE user_id=?').bind(user.id).first();
 if(path==='/profile'&&request.method==='GET')return reply({email:user.email,phone:s?.phone||'',two_factor_enabled:!!s?.secret});
 if(request.method!=='POST')return reply({error:'Not found.'},404);
 const b=await bodyOf(request);
 if(await limited(db,'security:'+user.id))return reply({error:'Too many attempts. Try again in ten minutes.'},429);
 const account=await db.prepare('SELECT * FROM users WHERE id=? AND enabled=1').bind(user.id).first();
 if(!account||typeof b.password!=='string'||b.password.length>128||!equal(await passwordHash(b.password,account.password_salt),account.password_hash))return reply({error:'Your current password is incorrect.'},400);
 const session=await hash(request.headers.get('Authorization').slice(7));
 if(path==='/profile'){
  const email=typeof b.email==='string'?b.email.trim().toLowerCase():'';
  const phone=typeof b.phone==='string'?b.phone.trim().replace(/[ ()-]/g,''):'';
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254||phone&&!/^\+[1-9]\d{6,14}$/.test(phone))return reply({error:'Enter a valid email and a phone number with country code, such as +27821234567.'},400);
  if(!await consumeFactor(db,env,user.id,b.code))return reply({error:'Enter a fresh authenticator code or unused recovery code.'},400);
  const duplicate=await db.prepare('SELECT id FROM users WHERE email=? AND id<>?').bind(email,user.id).first();if(duplicate)return reply({error:'That email is already in use.'},409);
  await db.batch([
   db.prepare('UPDATE users SET email=? WHERE id=?').bind(email,user.id),
   db.prepare('INSERT INTO account_security(user_id,phone) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone').bind(user.id,phone),
   db.prepare('DELETE FROM sessions WHERE user_id=? AND token_hash<>?').bind(user.id,session)
  ]);
  return reply({ok:true,email,phone});
 }
 if(path==='/security/setup'){
  if(s?.secret)return reply({error:'2FA is already enabled. Disable it before replacing your authenticator.'},409);
  try{await keyFor(env);}catch{return reply({error:'Authenticator setup is not configured on the server yet.'},503);}
  const secret=base32(crypto.getRandomValues(new Uint8Array(20))),encrypted=await seal(secret,env,user.id);
  await db.prepare(`INSERT INTO account_security(user_id,pending,pending_expires,pending_session) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET pending=excluded.pending,pending_expires=excluded.pending_expires,pending_session=excluded.pending_session WHERE secret IS NULL`).bind(user.id,encrypted,Date.now()+600000,session).run();
  return reply({secret,uri:'otpauth://totp/'+encodeURIComponent('Stat Tracker:'+user.email)+'?secret='+secret+'&issuer=Stat%20Tracker&algorithm=SHA1&digits=6&period=30'});
 }
 if(path==='/security/confirm'){
  if(s?.secret||!s?.pending||s.pending_expires<Date.now()||s.pending_session!==session)return reply({error:'Setup expired. Start authenticator setup again.'},400);
  const step=await validStep(await open(s.pending,env,user.id),b.code);
  if(step===null)return reply({error:'Enter the six-digit code from your authenticator.'},400);
  const codes=Array.from({length:10},()=>hex(crypto.getRandomValues(new Uint8Array(10))));
  const hashes=JSON.stringify(await Promise.all(codes.map(hash)));
  const saved=await db.prepare(`UPDATE account_security SET secret=pending,pending=NULL,pending_expires=0,pending_session=NULL,last_step=?,recovery_hashes=? WHERE user_id=? AND secret IS NULL AND pending=? AND pending_session=? AND pending_expires>? RETURNING user_id`).bind(step,hashes,user.id,s.pending,session,Date.now()).first();
  if(!saved)return reply({error:'Setup changed. Start again.'},409);
  await db.prepare('DELETE FROM sessions WHERE user_id=? AND token_hash<>?').bind(user.id,session).run();
  return reply({ok:true,recovery_codes:codes});
 }
 if(path==='/security/disable'){
  if(!s?.secret)return reply({error:'2FA is not enabled.'},400);
  if(!await consumeFactor(db,env,user.id,b.code))return reply({error:'Enter a fresh authenticator code or unused recovery code.'},400);
  await db.batch([
   db.prepare('UPDATE account_security SET secret=NULL,pending=NULL,pending_session=NULL,pending_expires=0,last_step=-1,recovery_hashes=\'[]\' WHERE user_id=? AND secret=?').bind(user.id,s.secret),
   db.prepare('DELETE FROM sessions WHERE user_id=? AND token_hash<>?').bind(user.id,session)
  ]);return reply({ok:true});
 }
 return reply({error:'Not found.'},404);
}
