// Optional GitHub Actions setup; credentials are passed on stdin, never logged.
import {spawnSync} from 'node:child_process';
const names=['TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_VERIFY_SERVICE_SID'];
const present=names.filter(name=>process.env[name]);
if(present.length===0){
 console.log('Email/SMS delivery setup skipped; existing Worker settings are preserved.');
}else{
 if(present.length!==names.length)throw new Error('Set all three Twilio Actions secrets, or leave all absent.');
 const values=Object.fromEntries(names.map(name=>[name,process.env[name]]));
 for(const name of ['SIGNIN_EMAIL','SIGNIN_SMS']){
  if(!['true','false'].includes(process.env[name]||''))throw new Error('Set '+name+' repository variable to true or false.');
  values[name]=process.env[name];
 }
 const result=spawnSync('npx',['wrangler','secret','bulk'],{input:JSON.stringify(values),encoding:'utf8',shell:process.platform==='win32'});
 if(result.status!==0)throw new Error('Could not save delivery secrets. Check Cloudflare access.');
 console.log('Optional verification delivery configuration saved.');
}
