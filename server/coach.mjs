export const coachSports=['SOCCER','HOCKEY','BASKETBALL','RUGBY','RUGBY_SEVENS','WATERPOLO','CRICKET'];
export function coachAssignment(b){
 const team_code=typeof b.team_code==='string'?b.team_code.replace(/\s+/g,'').toUpperCase():'';
 return (/^U(?:[6-9]|1[0-9]|2[0-3])(?:[A-Z]|[1-8](?:ST|ND|RD|TH))$/.test(team_code)||['1STTEAM','2NDTEAM','OTHER'].includes(team_code))&&coachSports.includes(b.sport)?{team_code,sport:b.sport}:null;
}
export async function coachProfile(db,user){
 if(!user||user.role!=='user')return user;
 const a=await db.prepare('SELECT team_code,sport FROM coach_assignments WHERE user_id=?').bind(user.id).first();
 return a?{...user,role:'coach',...a}:user;
}
