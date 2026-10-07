// Run from server/ after wrangler login. Never replace an existing MFA key.
import {randomBytes} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const cli=new URL('./node_modules/wrangler/bin/wrangler.js',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const secrets=JSON.parse(execFileSync(process.execPath,[decodeURIComponent(cli),'secret','list'],{encoding:'utf8'}));
if(secrets.some(s=>s.name==='MFA_ENCRYPTION_KEY')){
 console.log('Existing MFA encryption key retained.');
}else{
 execFileSync(process.execPath,[decodeURIComponent(cli),'secret','put','MFA_ENCRYPTION_KEY'],{input:randomBytes(32).toString('hex')+'\n',stdio:['pipe','inherit','inherit']});
 console.log('MFA encryption key configured. Keep this secret unchanged after enrollment.');
}
