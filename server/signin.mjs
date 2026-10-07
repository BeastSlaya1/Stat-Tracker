import {consumeFactor, limited} from './security.mjs';
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),b=>b.toString(16).padStart(2,'0')).join('');
const configured=(env,channel)=>['email','sms'].includes(channel)&&env['SIGNIN_'+channel.toUpperCase()]==='true'&&/^AC[a-fA-F0-9]{32}$/.test(env.TWILIO_ACCOUNT_SID||'')&&/^VA[a-fA-F0-9]{32}$/.test(env.TWILIO_VERIFY_SERVICE_SID||'')&&!!env.TWILIO_AUTH_TOKEN;
const unavailable=()=>reply({error:'This sign-in method is not configured yet. Use password sign-in.'},503);
const rejected=()=>reply({error:'Sign-in could not be verified. Check your details and use a fresh code.'},401);
async function provider(env,path,params){
 const response=await fetch('https://verify.twilio.com/v2/Services/'+env.TWILIO_VERIFY_SERVICE_SID+'/'+path,{
  method:'POST',headers:{Authorization:'Basic '+btoa(env.TWILIO_ACCOUNT_SID+':'+env.TWILIO_AUTH_TOKEN),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(params),signal:AbortSignal.timeout(10000)});
 const data=await response.json();
 if(!response.ok)throw new Error('verification-unavailable');
 return data;
}
async function session(env,user,method,destination=""){
 const token=Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join(''),expires=Date.now()+7*86400000;
 const predicate=method==='authenticator'
  ? "EXISTS(SELECT 1 FROM signin_methods m JOIN account_security a ON a.user_id=m.user_id WHERE m.user_id=users.id AND m.authenticator_login=1 AND a.secret IS NOT NULL)"
  : method==='email'
  ? "EXISTS(SELECT 1 FROM signin_methods m WHERE m.user_id=users.id AND m.email_address=users.email AND m.email_address=?)"
  : "EXISTS(SELECT 1 FROM signin_methods m JOIN account_security a ON a.user_id=m.user_id WHERE m.user_id=users.id AND m.sms_address=a.phone AND m.sms_address=?)";
 const args=[await hash(token),expires,user.id,user.password_hash];
 if(method!=='authenticator')args.push(destination);
 const result=await env.DB.prepare(`INSERT INTO sessions(token_hash,user_id,expires_at) SELECT ?,id,? FROM users WHERE id=? AND enabled=1 AND password_hash=? AND ${predicate} RETURNING user_id`).bind(...args).first();
 if(!result)return rejected();
 return reply({token,expires_at:expires,user:{id:user.id,email:user.email,display_name:user.display_name,role:user.role}});
}
async function contact(db,user,channel){
 if(channel==='email')return user.email;
 return (await db.prepare('SELECT phone FROM account_security WHERE user_id=?').bind(user.id).first())?.phone||'';
}
async function checkLimit(request,db,identity,prefix='signin'){
 // Both account-wide and IP-wide budgets resist distributed guessing and send abuse.
 const ip=request.headers.get('CF-Connecting-IP')||'unknown';
 return await limited(db,prefix+':ip:'+await hash(ip)) || await limited(db,prefix+':account:'+await hash(identity));
}
export async function signInRoutes(request,env,bodyOf,staff,passwordHash,equal){
 const path=new URL(request.url).pathname,db=env.DB;
 const capabilities={password:true,authenticator:true,email:configured(env,'email'),sms:configured(env,'sms')};
 if(path==='/signin/methods'&&request.method==='GET')return reply(capabilities);
 const privateRoute=['/signin/options','/signin/enroll','/signin/confirm','/signin/preference'].includes(path);
 const user=privateRoute?await staff(request,db):null;
 if(privateRoute&&!user)return rejected();
 if(path==='/signin/options'&&request.method==='GET'){
  const saved=await db.prepare('SELECT * FROM signin_methods WHERE user_id=?').bind(user.id).first();
  const security=await db.prepare('SELECT phone,secret FROM account_security WHERE user_id=?').bind(user.id).first();
  return reply({...capabilities,email_verified:saved?.email_address===user.email,sms_verified:!!saved?.sms_address&&saved.sms_address===security?.phone,authenticator_login:!!saved?.authenticator_login&&!!security?.secret});
 }
 if(request.method!=='POST')return reply({error:'Not found.'},404);
 const b=await bodyOf(request),email=typeof b.email==='string'?b.email.trim().toLowerCase():'';
 if(email.length>254)return rejected();
 if(await checkLimit(request,db,user?.id||email))return reply({error:'Too many attempts. Try again in ten minutes.'},429);
 if(path==='/signin/authenticator'){
  const account=await db.prepare('SELECT * FROM users WHERE email=? AND enabled=1').bind(email).first();
  if(!account||typeof b.code!=='string'||!/^\d{6}$/.test(b.code))return rejected();
  const methods=await db.prepare('SELECT authenticator_login FROM signin_methods WHERE user_id=?').bind(account.id).first();
  const security=await db.prepare('SELECT secret FROM account_security WHERE user_id=?').bind(account.id).first();
  if(!methods?.authenticator_login||!security?.secret||!await consumeFactor(db,env,account.id,b.code))return rejected();
  return session(env,account,'authenticator');
 }
 if(path==='/signin/enroll'||path==='/signin/preference'){
  const account=await db.prepare('SELECT * FROM users WHERE id=? AND enabled=1').bind(user.id).first();
  if(!account||typeof b.password!=='string'||b.password.length>128||!equal(await passwordHash(b.password,account.password_salt),account.password_hash)||!await consumeFactor(db,env,user.id,b.code))return rejected();
  if(path==='/signin/preference'){
   if(b.method==='authenticator'){
    const security=await db.prepare('SELECT secret FROM account_security WHERE user_id=?').bind(user.id).first();
    if(b.enabled===true&&!security?.secret)return reply({error:'Set up an authenticator in Profile and security first.'},400);
    await db.prepare('INSERT INTO signin_methods(user_id,authenticator_login) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET authenticator_login=excluded.authenticator_login').bind(user.id,b.enabled===true?1:0).run();
   }else if(['email','sms'].includes(b.method)&&b.enabled===false){
    const column=b.method==='email'?'email_address':'sms_address';
    await db.prepare(`UPDATE signin_methods SET ${column}=NULL WHERE user_id=?`).bind(user.id).run();
   }else return reply({error:'Invalid sign-in setting.'},400);
   await db.prepare('DELETE FROM signin_challenges WHERE user_id=?').bind(user.id).run();
   return reply({ok:true});
  }
 }
 if(path==='/signin/start'||path==='/signin/enroll'){
  if(!configured(env,b.channel))return unavailable();
  if(await checkLimit(request,db,user?.id||email,'signin-send'))return reply({error:'Too many code requests. Try again in ten minutes.'},429);
  const account=user||await db.prepare('SELECT * FROM users WHERE email=? AND enabled=1').bind(email).first();
  const id=crypto.randomUUID(),purpose=privateRoute?'enroll':'login';
  let target=account?await contact(db,account,b.channel):'';
  if(purpose==='login'&&account){
   const saved=await db.prepare('SELECT * FROM signin_methods WHERE user_id=?').bind(account.id).first();
   if(!target||saved?.[b.channel==='email'?'email_address':'sms_address']!==target)target='';
  }
  if(purpose==='enroll'&&!target)return reply({error:'Save your email and phone number in Profile and security first.'},400);
  if(target){
   try{
    const sent=await provider(env,'Verifications',{To:target,Channel:b.channel});
    if(!/^VE[a-fA-F0-9]{32}$/.test(sent.sid||''))throw new Error('invalid-verification');
    await db.batch([
     db.prepare('DELETE FROM signin_challenges WHERE expires_at<=? OR (user_id=? AND channel=? AND purpose=?)').bind(Date.now(),account.id,b.channel,purpose),
     db.prepare('INSERT INTO signin_challenges(id,user_id,channel,destination,provider_sid,purpose,session_hash,expires_at) VALUES(?,?,?,?,?,?,?,?)').bind(id,account.id,b.channel,target,sent.sid,purpose,privateRoute?await hash(request.headers.get('Authorization').slice(7)):'',Date.now()+600000)
    ]);
   }catch{return reply({error:'Code delivery is temporarily unavailable. Use password sign-in or try later.'},503);}
  }
  return reply({challenge:id,message:purpose==='enroll'?'Enter the code sent to your saved contact.':'If this account has this sign-in method enabled, a code has been sent.'});
 }
 if(path==='/signin/check'||path==='/signin/confirm'){
  if(typeof b.challenge!=='string'||b.challenge.length>100||typeof b.verification_code!=='string'||!/^\d{4,10}$/.test(b.verification_code))return rejected();
  const c=await db.prepare('SELECT * FROM signin_challenges WHERE id=? AND expires_at>? AND state=\'pending\'').bind(b.challenge,Date.now()).first();
  if(!c||!configured(env,c.channel)||c.purpose!==(privateRoute?'enroll':'login'))return rejected();
  if(privateRoute&&(c.user_id!==user.id||c.session_hash!==await hash(request.headers.get('Authorization').slice(7))))return rejected();
  if(await limited(db,'signin-check:'+c.user_id))return reply({error:'Too many attempts. Try again in ten minutes.'},429);
  const account=await db.prepare('SELECT * FROM users WHERE id=? AND enabled=1').bind(c.user_id).first();
  if(!account||await contact(db,account,c.channel)!==c.destination)return rejected();
  if(!privateRoute){
   const methods=await db.prepare('SELECT * FROM signin_methods WHERE user_id=?').bind(c.user_id).first();
   if(methods?.[c.channel==='email'?'email_address':'sms_address']!==c.destination)return rejected();
   if(!await consumeFactor(db,env,c.user_id,b.code))return reply({error:'Enter a fresh authenticator or recovery code as well.',two_factor_required:true},401);
  }
  const claimed=await db.prepare("UPDATE signin_challenges SET state='checking' WHERE id=? AND state='pending' AND expires_at>? RETURNING id").bind(c.id,Date.now()).first();
  if(!claimed)return rejected();
  let verified;
  try{verified=await provider(env,'VerificationCheck',{VerificationSid:c.provider_sid,Code:b.verification_code});}
  catch{
   await db.prepare("UPDATE signin_challenges SET state='pending' WHERE id=? AND state='checking'").bind(c.id).run();
   return rejected();
  }
  if(verified.status!=='approved'){
   await db.prepare("UPDATE signin_challenges SET state='pending' WHERE id=? AND state='checking'").bind(c.id).run();
   return rejected();
  }
  // Consume once; revocation while the provider request was in flight cancels it.
  const consumed=await db.prepare("DELETE FROM signin_challenges WHERE id=? AND state='checking' AND expires_at>? RETURNING id").bind(c.id,Date.now()).first();
  if(!consumed)return rejected();
  const current=await db.prepare('SELECT * FROM users WHERE id=? AND enabled=1').bind(c.user_id).first();
  if(!current||await contact(db,current,c.channel)!==c.destination)return rejected();
  if(privateRoute){
   if(!await staff(request,db))return rejected();
   const column=c.channel==='email'?'email_address':'sms_address';
   await db.prepare(`INSERT INTO signin_methods(user_id,${column}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET ${column}=excluded.${column}`).bind(c.user_id,c.destination).run();
   return reply({ok:true});
  }
  return session(env,current,c.channel,c.destination);
 }
 return reply({error:'Not found.'},404);
}
