import {coachAssignment} from './coach.mjs';
const reply=(body,status=200)=>Response.json(body,{status});
const code=value=>typeof value==='string'?value.replace(/\s+/g,'').toUpperCase():'';
export async function rosterRoutes(request,db,user,bodyOf){
 const url=new URL(request.url),team=code(url.searchParams.get('team'));
 if(!coachAssignment({team_code:team,sport:'BASKETBALL'}))return reply({error:'Choose a valid team.'},400);
 if(user.role==='coach'&&(user.sport!=='BASKETBALL'||code(user.team_code)!==team))return reply({error:'Only your assigned basketball team is available.'},403);
 const hidden=user.hidden?1:0;
 if(request.method==='GET'){
  const row=await db.prepare('SELECT version,players FROM team_rosters WHERE team_code=? AND hidden=?').bind(team,hidden).first();
  return reply(row?{version:row.version,players:JSON.parse(row.players)}:{version:0,players:[]});
 }
 if(request.method!=='PUT')return reply({error:'Method not allowed.'},405);
 const b=await bodyOf(request),ids=new Set(),numbers=new Set();
 if(!b||!Number.isInteger(b.version)||b.version<0||!Array.isArray(b.players)||b.players.length>100)return reply({error:'Invalid roster.'},400);
 for(const p of b.players){
  if(!p||typeof p.id!=='string'||!/^[a-f0-9]{32}$/.test(p.id)||!Number.isInteger(p.number)||p.number<0||p.number>99||typeof p.active!=='boolean'||ids.has(p.id)||numbers.has(p.number))return reply({error:'Each jersey needs a unique number from 0 to 99.'},400);
  ids.add(p.id);numbers.add(p.number);
 }
 const existing=await db.prepare('SELECT version,players FROM team_rosters WHERE team_code=? AND hidden=?').bind(team,hidden).first();
 if(existing&&JSON.parse(existing.players).some(p=>!b.players.some(n=>n.id===p.id&&n.number===p.number)))return reply({error:'Remove jerseys by marking them inactive; keep their history.'},400);
 const json=JSON.stringify(b.players.map(({id,number,active})=>({id,number,active})));
 const saved=b.version===0?await db.prepare('INSERT INTO team_rosters(team_code,hidden,version,players) VALUES(?,?,1,?) ON CONFLICT DO NOTHING RETURNING version').bind(team,hidden,json).first():await db.prepare('UPDATE team_rosters SET players=?,version=version+1 WHERE team_code=? AND hidden=? AND version=? RETURNING version').bind(json,team,hidden,b.version).first();
 return saved?reply({version:saved.version,players:JSON.parse(json)}):reply({error:'The team changed on another device. Reload before editing.'},409);
}
