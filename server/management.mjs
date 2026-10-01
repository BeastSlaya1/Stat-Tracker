const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const roles=['admin','staff','user'];
const manager=u=>u.role==='admin'||u.role==='staff';
const validPassword=p=>typeof p==='string'&&p.length>=12&&p.length<=128;
export async function accountRoutes(request,db,user,bodyOf,passwordHash,random){
 if(!manager(user))return reply({error:'Only staff and admins can manage accounts.'},403);
 const path=new URL(request.url).pathname;
 if(path==='/accounts'&&request.method==='GET'){
  const rows=await db.prepare(user.role==='admin'?'SELECT id,email,display_name,role,enabled FROM users ORDER BY display_name':'SELECT id,email,display_name,role,enabled FROM users WHERE role=\'user\' ORDER BY display_name').all();
  return reply({accounts:rows.results});
 }
 if(path==='/accounts'&&request.method==='POST'){
  const b=await bodyOf(request),email=typeof b.email==='string'?b.email.trim().toLowerCase():'';
  if(!roles.includes(b.role)||!email.includes('@')||email.length>254||typeof b.display_name!=='string'||!b.display_name.trim()||b.display_name.length>100||!validPassword(b.password))return reply({error:'Enter a name, email, account type and password of 12–128 characters.'},400);
  if(user.role!=='admin'&&b.role!=='user')return reply({error:'Staff can create user accounts only.'},403);
  const id=crypto.randomUUID(),salt=random();
  const created=await db.prepare('INSERT INTO users(id,email,display_name,password_salt,password_hash,created_at,role) VALUES(?,?,?,?,?,?,?) ON CONFLICT(email) DO NOTHING RETURNING id').bind(id,email,b.display_name.trim(),salt,await passwordHash(b.password,salt),Date.now(),b.role).first();
  return created?reply({id,email,role:b.role},201):reply({error:'An account with that email already exists.'},409);
 }
 if(path.startsWith('/accounts/')&&request.method==='DELETE'){
  if(user.role!=='admin')return reply({error:'Only admins can delete accounts.'},403);
  const id=decodeURIComponent(path.slice(10)),b=await bodyOf(request);
  if(id===user.id)return reply({error:'You cannot delete your own administrator account.'},400);
  const target=await db.prepare('SELECT id,email,role FROM users WHERE id=?').bind(id).first();
  if(!target)return reply({error:'Account not found.'},404);
  if(b.confirm_email!==target.email)return reply({error:'Type the account email to confirm deletion.'},400);
  const guard="EXISTS(SELECT 1 FROM users acting WHERE acting.id=? AND acting.role='admin' AND acting.enabled=1)";
  // Preserve attribution and matches, transferring database ownership to the
  // acting admin. One transaction prevents partial deletion or broken FKs.
  const results=await db.batch([
   db.prepare(`UPDATE matches SET body=json_set(body,
    '$.created_by_id',COALESCE(NULLIF(json_extract(body,'$.created_by_id'),''),owner_id,''),
    '$.created_by_name',COALESCE(NULLIF(json_extract(body,'$.created_by_name'),''),(SELECT display_name FROM users WHERE id=owner_id),'Not recorded'),
    '$.edited_by_id',COALESCE(NULLIF(json_extract(body,'$.edited_by_id'),''),updated_by,''),
    '$.edited_by_name',COALESCE(NULLIF(json_extract(body,'$.edited_by_name'),''),(SELECT display_name FROM users WHERE id=updated_by),'Not recorded')),
    owner_id=CASE WHEN owner_id=? THEN ? ELSE owner_id END,
    updated_by=CASE WHEN updated_by=? THEN ? ELSE updated_by END,
    version=version+1,mutation_id=?,updated_at=? WHERE (owner_id=? OR updated_by=?) AND ${guard}`)
    .bind(id,user.id,id,user.id,'account-delete-'+crypto.randomUUID(),Date.now(),id,id,user.id),
   db.prepare('DELETE FROM camera_rooms WHERE owner_id=? AND '+guard).bind(id,user.id),
   db.prepare("DELETE FROM camera_links WHERE EXISTS (SELECT 1 FROM sessions WHERE user_id=? AND (camera_links.owner_session LIKE token_hash||':%' OR camera_links.receiver_session LIKE token_hash||':%')) AND "+guard).bind(id,user.id),
   db.prepare('DELETE FROM sessions WHERE user_id=? AND '+guard).bind(id,user.id),
   db.prepare('DELETE FROM users WHERE id=? AND '+guard).bind(id,user.id)
  ]);
  if(!(results.at(-1).meta?.changes??results.at(-1).changes))return reply({error:'Account access changed. Refresh and try again.'},409);
  return reply({ok:true,matches_preserved:true});
 }
 if(path.startsWith('/accounts/')&&request.method==='PUT'){
  if(user.role!=='admin')return reply({error:'Only admins can change account access.'},403);
  const id=decodeURIComponent(path.slice(10)),b=await bodyOf(request);
  if(!roles.includes(b.role)||typeof b.enabled!=='boolean'||(b.password!==undefined&&!validPassword(b.password)))return reply({error:'Choose a valid account type, access status and password of 12–128 characters.'},400);
  if(id===user.id&&(b.role!=='admin'||!b.enabled))return reply({error:'You cannot remove your own administrator access.'},400);
  const target=await db.prepare('SELECT id FROM users WHERE id=?').bind(id).first();
  if(!target)return reply({error:'Account not found.'},404);
  const statements=[db.prepare('UPDATE users SET role=?,enabled=? WHERE id=?').bind(b.role,b.enabled?1:0,id)];
  if(b.password!==undefined){const salt=random();statements.push(db.prepare('UPDATE users SET password_salt=?,password_hash=? WHERE id=?').bind(salt,await passwordHash(b.password,salt),id));}
  // Revoke target sessions whenever privileges/password change.
  statements.push(db.prepare('DELETE FROM sessions WHERE user_id=?').bind(id));
  await db.batch(statements);return reply({ok:true});
 }
 return reply({error:'Not found.'},404);
}
export const catalogFields={Schools:{ID:'number',School_ID:'text'},Sports:{ID:'number',SportID:'text'},Age_Groups:{ID:'number',Age:'number',Special_Lists:'number'},'Team Codes':{ID:'number',Team_Codes:'text',Special:'number'},Teams:{ID:'number',Age_Groups:'number','Team Codes':'number'},Stats:{ID:'number',Type:'text',Action:'text',Description:'text'}};
export async function catalogRoutes(request,db,user,bodyOf){
 if(!manager(user))return reply({error:'Only staff and admins can manage the shared database.'},403);
 const path=new URL(request.url).pathname;
 if(path==='/catalog/manage'&&request.method==='GET'){
  const rows=await db.prepare('SELECT table_name,rows_json,version FROM catalog').all();
  return reply({tables:rows.results.filter(r=>catalogFields[r.table_name]).map(r=>({name:r.table_name,rows:JSON.parse(r.rows_json),version:r.version,fields:catalogFields[r.table_name]}))});
 }
 if(path.startsWith('/catalog/manage/')&&request.method==='PUT'){
  const name=decodeURIComponent(path.slice('/catalog/manage/'.length)),fields=catalogFields[name],b=await bodyOf(request);
  if(!fields||!Number.isInteger(b.base_version)||!Array.isArray(b.rows)||b.rows.length>5000)return reply({error:'Invalid database update.'},400);
  const ids=new Set();
  for(const row of b.rows){
   if(!row||Array.isArray(row)||Object.keys(row).some(k=>!Object.hasOwn(fields,k))||Object.entries(fields).some(([k,type])=>type==='number'? !Number.isSafeInteger(row[k])||row[k]<0: typeof row[k]!=='string'||!row[k].trim()||row[k].length>500)||row.ID<1||ids.has(row.ID))return reply({error:'Each row needs a unique positive ID and valid values for every field.'},400);
   ids.add(row.ID);
  }
  const saved=await db.prepare('UPDATE catalog SET rows_json=?,version=version+1 WHERE table_name=? AND version=? RETURNING version').bind(JSON.stringify(b.rows),name,b.base_version).first();
  return saved?reply({version:saved.version}):reply({error:'This table changed on another device. Reopen it before editing.'},409);
 }
 return reply({error:'Not found.'},404);
}
