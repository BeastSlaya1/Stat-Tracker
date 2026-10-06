const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const valid=(d,type)=>d&&d.type===type&&typeof d.sdp==='string'&&d.sdp.startsWith('v=0')&&d.sdp.length<=65536;
export async function cameraLinks(request,db,user,session,bodyOf){
 const path=new URL(request.url).pathname,now=Date.now();
 if(path==='/camera/devices'&&request.method==='GET'){
  const rows=await db.prepare('SELECT code,name,kind FROM camera_links WHERE last_seen>? AND expires_at>? AND receiver_session IS NULL ORDER BY name LIMIT 100').bind(now-45000,now).all();
  return reply({devices:rows.results});
 }
 // A per-control nonce also distinguishes tabs sharing the same staff login.
 const peer=request.headers.get('X-Camera-Device')||'';
 if(!/^[a-f0-9]{32}$/.test(peer))return reply({error:'Camera device identity required.'},400);
 const identity=session+':'+peer;
 if(path==='/camera/devices'&&request.method==='POST'){
  const b=await bodyOf(request);
  if(!valid(b.offer,'offer')||typeof b.name!=='string'||!b.name.trim()||b.name.length>80||!['Windows','Android','iOS','Browser','Desktop'].includes(b.kind))return reply({error:'Invalid camera announcement.'},400);
  const code=Array.from(crypto.getRandomValues(new Uint8Array(6)),x=>x.toString(16).padStart(2,'0')).join('').toUpperCase();
  await db.batch([db.prepare('DELETE FROM camera_links WHERE expires_at<=? OR owner_session=?').bind(now,identity),db.prepare('INSERT INTO camera_links(code,owner_session,name,kind,offer,last_seen,expires_at) VALUES(?,?,?,?,?,?,?)').bind(code,identity,b.name.trim(),b.kind,JSON.stringify(b.offer),now,now+90000)]);
  return reply({code},201);
 }
 const m=path.match(/^\/camera\/devices\/([A-F0-9]{12})(?:\/(join|approve|answer|heartbeat|close))?$/);
 if(!m)return reply({error:'Camera not found.'},404);
 const [,code,action]=m;
 const r=await db.prepare('SELECT * FROM camera_links WHERE code=? AND expires_at>?').bind(code,now).first();
 if(!r)return reply({error:'Camera is no longer available. Scan again.'},404);
 const owner=r.owner_session===identity,receiver=r.receiver_session===identity;
 if(action==='join'&&request.method==='POST'){
  if(owner)return reply({error:'Select a camera on another device.'},409);
  if(r.last_seen<=now-45000)return reply({error:'Camera is offline. Scan again.'},404);
  const result=await db.prepare('UPDATE camera_links SET receiver_session=?,receiver_name=? WHERE code=? AND (receiver_session IS NULL OR receiver_session=?) RETURNING code').bind(identity,user.display_name,code,identity).first();
  return result?reply({waiting:true}):reply({error:'Camera is already paired with another receiver.'},409);
 }
 if(!owner&&!receiver)return reply({error:'Camera access denied.'},403);
 if(request.method==='GET'&&!action)return reply(owner?{receiver_name:r.receiver_name,approved:!!r.approved,answer:r.answer?JSON.parse(r.answer):null}:{approved:!!r.approved,offer:r.approved?JSON.parse(r.offer):null});
 if(request.method==='POST'&&action==='heartbeat'){
  if(owner)await db.prepare('UPDATE camera_links SET last_seen=?,expires_at=? WHERE code=?').bind(now,now+90000,code).run();
  return reply({ok:true});
 }
 if(request.method==='POST'&&action==='approve'&&owner&&r.receiver_session){await db.prepare('UPDATE camera_links SET approved=1 WHERE code=?').bind(code).run();return reply({ok:true});}
 if(request.method==='POST'&&action==='answer'&&receiver&&r.approved){
  const b=await bodyOf(request);if(!valid(b.answer,'answer'))return reply({error:'Invalid camera answer.'},400);
  const value=JSON.stringify(b.answer);
  const changed=await db.prepare('UPDATE camera_links SET answer=? WHERE code=? AND (answer IS NULL OR answer=?) RETURNING code').bind(value,code,value).first();
  return changed?reply({ok:true}):reply({error:'Camera already connected.'},409);
 }
 if(request.method==='POST'&&action==='close'){await db.prepare('DELETE FROM camera_links WHERE code=?').bind(code).run();return reply({ok:true});}
 return reply({error:'Camera action not allowed.'},403);
}
