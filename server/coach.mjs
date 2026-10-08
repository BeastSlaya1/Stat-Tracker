export const coachSports=['SOCCER','HOCKEY','BASKETBALL','RUGBY','RUGBY_SEVENS','WATERPOLO','CRICKET'];
export function coachAssignment(b){
 const team_code=typeof b.team_code==='string'?b.team_code.replace(/\s+/g,'').toUpperCase():'';
 return (/^U(?:[6-9]|1[0-9]|2[0-3])(?:[A-Z]|[1-8](?:ST|ND|RD|TH))$/.test(team_code)||(/^[1-8](?:ST|ND|RD|TH)TEAM$/.test(team_code)||team_code==='OTHER'))&&coachSports.includes(b.sport)?{team_code,sport:b.sport}:null;
}
export async function coachProfile(db,user){
 if(!user)return user;
 const access=await db.prepare('SELECT owner,hidden,can_grant_owner FROM account_access WHERE user_id=?').bind(user.id).first();
 let profile={...user,hidden:!!access?.hidden,can_grant_owner:!!access?.can_grant_owner,visibility_version:1};
 if(access?.owner)return {...profile,role:'owner'};
 if(user.role!=='user')return profile;
 const a=await db.prepare('SELECT team_code,sport FROM coach_assignments WHERE user_id=?').bind(user.id).first();
 return a?{...profile,role:'coach',...a}:profile;
}
export const visibilitySql=(user,alias='m')=>user.role==='owner'?'1=1':`COALESCE((SELECT hidden FROM match_privacy WHERE match_id=${alias}.id),0)=${user.hidden?1:0}`;
export const visibleMatch=(user,row)=>user.role==='owner'||!!row.hidden===!!user.hidden;
export const visiblePeer=(viewer,hidden)=>viewer.role==='owner'||!!viewer.hidden===!!hidden;
