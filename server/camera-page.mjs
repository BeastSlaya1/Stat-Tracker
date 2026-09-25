export const cameraPage = String.raw`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Stat Tracker · Camera link</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#080f1d;color:#eef6ff}*{box-sizing:border-box}
body{margin:0;padding:clamp(16px,4vw,40px)}main{max-width:1100px;margin:auto}header{display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:24px}
a{color:#7dd3fc}h1{font-size:clamp(25px,4vw,38px);margin:0}h2{font-size:21px}.card{background:#101c30;border:1px solid #284666;border-radius:18px;padding:clamp(16px,3vw,28px);margin:16px 0}
p{line-height:1.6;color:#b7c9dd}label{display:block;margin:12px 0 6px}input,button,select{font:inherit;border-radius:10px;padding:13px;min-height:48px}input,select{background:#091423;border:1px solid #456783;color:#fff;width:100%;max-width:460px}
button{background:#0784ca;color:#fff;border:1px solid #38bdf8;font-weight:650;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.secondary{background:#182b43;border-color:#456783}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}.row>*{max-width:100%}
#status{border-left:4px solid #38bdf8;padding:12px 16px;background:#10243b;white-space:pre-wrap}#video-frame{position:relative;width:100%;aspect-ratio:16/9;max-height:70dvh;overflow:hidden;background:#000;border-radius:14px}#video-frame:fullscreen{max-height:none;height:100%;border-radius:0}video{display:block;position:absolute;left:50%;top:50%;object-fit:contain}#view-tools{position:absolute;right:10px;top:10px;z-index:1;display:flex;gap:6px;flex-wrap:wrap}#view-tools button{background:#10243bdd}#pair-code{font-size:clamp(22px,5vw,36px);letter-spacing:3px;overflow-wrap:anywhere;color:#7dd3fc}small{color:#b7c9dd}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #7dd3fc;outline-offset:3px}[hidden]{display:none!important}
@media(max-width:540px){.row button{flex:1 1 auto}header a{font-size:14px}.card{padding:16px}}
</style><script src="/camera/app.js" defer></script></head><body><main>
<header><h1>Stat Tracker <span style="color:#38bdf8">Camera link</span></h1><a href="https://stattrackerv4.stream">Match workspace ↗</a></header>
<p>Send your iPhone, iPad or other browser camera to another device. Sign in on both devices, enter the camera code, then approve the receiver.</p>
<section id="login-card" class="card"><h2>Staff sign in</h2><form id="login-form"><label for="email">Staff email</label><input id="email" type="email" autocomplete="username" required><label for="password">Password</label><input id="password" type="password" autocomplete="current-password" required><div class="row"><button id="login-button">Sign in</button></div></form></section>
<section id="controls" class="card" hidden><div class="row"><strong id="staff-name"></strong><button id="sign-out" class="secondary">Sign out</button></div>
<div id="choose"><div class="row"><button id="send">Send this camera</button><button id="receive" class="secondary">Receive a camera</button></div><label for="lens">Camera to send</label><select id="lens"><option value="environment">Back camera</option><option value="user">Front camera</option></select></div>
<form id="join-form" hidden><label for="code">Code shown on the camera device</label><input id="code" maxlength="16" autocomplete="off" autocapitalize="characters" spellcheck="false" required><div class="row"><button id="join">Connect to camera</button></div></form>
<div id="pairing" hidden><p>On the receiving device, open this same camera page, sign in, choose <b>Receive a camera</b> and enter:</p><strong id="pair-code"></strong><div class="row"><button id="copy" class="secondary">Copy code</button></div><p id="receiver-name"></p><button id="approve" hidden>Approve receiving device</button></div>
<div class="row"><button id="stop" class="secondary" hidden>Stop connection</button><button id="fullscreen" class="secondary" hidden>Full screen video</button><button id="play" hidden>Show video</button></div>
</section><p id="status" role="status" aria-live="polite">Sign in to start.</p>
<div id="video-frame" hidden><video id="video" autoplay muted playsinline></video><div id="view-tools"><button id="rotate" class="secondary" title="Rotate this screen’s video 90 degrees clockwise">↻ Rotate view</button><button id="mirror" class="secondary" title="Flip this screen’s video left-to-right" aria-pressed="false">⇆ Mirror view</button></div></div>
<p><strong>Use the same Wi-Fi for the most reliable connection.</strong> Some guest, school or mobile networks block direct video connections. A relay is not configured yet. Keep the camera page visible and the device unlocked. Video appears on this receiving page; you can keep the match workspace open beside it.</p>
<small>Video is encrypted between the devices and is not recorded by this service. Pairing codes expire after ten minutes; an established video link can continue until you stop it.</small>
</main></body></html>`;

export const cameraScript = String.raw`
'use strict';
const $=id=>document.getElementById(id);
let token='',pc=null,stream=null,room='',timer=null,deadline=null,wake=null,generation=0,role='',answerSet=false;
let quarterTurns=0,mirrored=false;
function fitVideo(){const box=$('video-frame'),v=$('video'),odd=quarterTurns%2;v.style.width=(odd?box.clientHeight:box.clientWidth)+'px';v.style.height=(odd?box.clientWidth:box.clientHeight)+'px';v.style.transform='translate(-50%,-50%) scaleX('+(mirrored?-1:1)+') rotate('+(quarterTurns*90)+'deg)';}
new ResizeObserver(fitVideo).observe($('video-frame'));
$('rotate').onclick=()=>{quarterTurns=(quarterTurns+1)%4;fitVideo();};
$('mirror').onclick=()=>{mirrored=!mirrored;$('mirror').setAttribute('aria-pressed',String(mirrored));$('mirror').textContent=mirrored?'⇆ Mirror: On':'⇆ Mirror view';fitVideo();};
const status=text=>{$('status').textContent=text;};
async function api(path,method='GET',body){
  const response=await fetch(path,{method,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:body?JSON.stringify(body):undefined,cache:'no-store'});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Connection service unavailable.');return data;
}
async function closeLink(notify=true){
  generation++;clearTimeout(timer);clearTimeout(deadline);timer=null;deadline=null;
  const oldRoom=room;room='';role='';answerSet=false;
  if(pc){pc.onconnectionstatechange=null;pc.close();pc=null;}
  if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}
  $('video').srcObject=null;$('video-frame').hidden=true;
  if(wake){wake.release().catch(()=>{});wake=null;}
  ['pairing','join-form','stop','fullscreen','play','approve'].forEach(id=>$(id).hidden=true);
  $('choose').hidden=false;$('send').disabled=false;$('join').disabled=false;
  if(notify&&oldRoom&&token)await api('/camera/rooms/'+oldRoom+'/close','POST',{}).catch(()=>{});
}
async function fail(error){await closeLink();status(error.message||String(error));}
async function keepAwake(){try{if(!wake||wake.released)wake=await navigator.wakeLock?.request('screen');}catch{}}
function showVideo(media){$('video').srcObject=media;$('video-frame').hidden=false;fitVideo();$('video').play().catch(()=>{$('play').hidden=false;});}
function peer(){
  const connection=new RTCPeerConnection({iceServers:[{urls:'stun:stun.cloudflare.com:3478'}]});
  connection.ontrack=event=>{showVideo(event.streams[0]||new MediaStream([event.track]));};
  connection.onconnectionstatechange=()=>{
    if(connection!==pc)return;
    if(connection.connectionState==='connected'){
      clearTimeout(timer);clearTimeout(deadline);status(role==='send'?'Live — sending camera video.':'Live — receiving camera video.');
      $('pairing').hidden=true;$('fullscreen').hidden=false;keepAwake();
    }else if(connection.connectionState==='failed'){
      fail(new Error('Video could not connect. Put both devices on the same Wi-Fi and start a new link. This network may require a video relay.'));
    }else if(connection.connectionState==='disconnected')status('Video connection interrupted. Keep both pages open; reconnect if it does not recover.');
  };
  return connection;
}
async function gather(connection){
  if(connection.iceGatheringState==='complete')return;
  await new Promise(resolve=>{
    const done=()=>{clearTimeout(timeout);connection.removeEventListener('icegatheringstatechange',changed);resolve();};
    const changed=()=>{if(connection.iceGatheringState==='complete')done();};
    const timeout=setTimeout(done,10000);connection.addEventListener('icegatheringstatechange',changed);
  });
}
function connectionDeadline(){clearTimeout(deadline);if(pc?.connectionState!=='connected')deadline=setTimeout(()=>fail(new Error('Video connection timed out. Try the same Wi-Fi on both devices, then start a new camera link.')),45000);}
async function poll(run){
  if(run!==generation||!room||!pc)return;
  try{
    const data=await api('/camera/rooms/'+room);
    if(run!==generation||!pc)return;
    if(role==='send'){
      $('receiver-name').textContent=data.receiver_name?data.receiver_name+' wants to receive this camera.':'';
      $('approve').hidden=!data.receiver_name||data.approved;
      if(data.answer&&!answerSet){answerSet=true;await pc.setRemoteDescription(data.answer);if(run!==generation)return;connectionDeadline();}
    }else if(data.approved&&data.offer&&!answerSet){
      answerSet=true;const connection=pc;await connection.setRemoteDescription(data.offer);
      await connection.setLocalDescription(await connection.createAnswer());await gather(connection);
      if(run!==generation)return;
      await api('/camera/rooms/'+room+'/answer','POST',{answer:connection.localDescription});if(run!==generation)return;connectionDeadline();if(pc.connectionState!=='connected')status('Connecting video…');
    }
    if(run===generation&&pc?.connectionState!=='connected')timer=setTimeout(()=>poll(run),1800);
  }catch(error){if(run===generation)await fail(error);}
}
$('login-form').onsubmit=async event=>{
  event.preventDefault();$('login-button').disabled=true;status('Signing in…');
  try{const data=await api('/login','POST',{email:$('email').value,password:$('password').value});token=data.token;$('password').value='';$('staff-name').textContent=data.user.display_name;$('login-card').hidden=true;$('controls').hidden=false;status('Choose whether this device sends or receives video.');if(new URLSearchParams(location.search).get('mode')==='receive')$('receive').click();}
  catch(error){status(error.message);}finally{$('login-button').disabled=false;}
};
$('send').onclick=async()=>{
  await closeLink();const run=generation;role='send';$('send').disabled=true;$('choose').hidden=true;$('stop').hidden=false;status('Allow camera access when your browser asks.');
  try{
    if(!navigator.mediaDevices?.getUserMedia||!window.RTCPeerConnection)throw new Error('Use an up-to-date Safari, Edge or Chrome browser over HTTPS.');
    const media=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:$('lens').value},width:{ideal:1280},height:{ideal:720},frameRate:{ideal:20,max:30}}});
    if(run!==generation){media.getTracks().forEach(track=>track.stop());return;}
    stream=media;showVideo(stream);pc=peer();const connection=pc;stream.getTracks().forEach(track=>connection.addTrack(track,stream));
    status('Preparing camera link…');await connection.setLocalDescription(await connection.createOffer());await gather(connection);
    if(run!==generation)return;
    const data=await api('/camera/rooms','POST',{offer:connection.localDescription});
    if(run!==generation){api('/camera/rooms/'+data.code+'/close','POST',{}).catch(()=>{});return;}
    room=data.code;$('pair-code').textContent=room;$('pairing').hidden=false;status('Camera ready. Waiting for a receiving device.');keepAwake();poll(run);
  }catch(error){if(run===generation)await fail(error);}
};
$('receive').onclick=()=>{$('choose').hidden=true;$('join-form').hidden=false;$('stop').hidden=false;$('code').focus();status('Enter the code shown on the camera device.');};
$('join-form').onsubmit=async event=>{
  event.preventDefault();const code=$('code').value.replace(/[\s-]/g,'').toUpperCase();
  if(!/^[A-F0-9]{12}$/.test(code)){status('Enter the 12-character camera code.');return;}
  $('join').disabled=true;const run=generation;
  try{await api('/camera/rooms/'+code+'/join','POST',{});if(run!==generation)return;room=code;role='receive';pc=peer();$('join-form').hidden=true;status('Waiting for approval on the camera device…');poll(run);}
  catch(error){if(run===generation)await fail(error);}
};
$('approve').onclick=async()=>{const run=generation;$('approve').disabled=true;try{await api('/camera/rooms/'+room+'/approve','POST',{});if(run===generation){$('approve').hidden=true;status('Receiver approved. Connecting video…');}}catch(error){if(run===generation)await fail(error);}finally{$('approve').disabled=false;}};
$('stop').onclick=async()=>{await closeLink();status('Camera connection stopped.');};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(room);status('Camera code copied.');}catch{status('Copy the code displayed above to the receiving device.');}};
$('play').onclick=()=>{$('video').play().then(()=>$('play').hidden=true).catch(()=>status('Your browser could not play the video. Try Safari, Edge or Chrome.'));};
$('fullscreen').onclick=()=>{const box=$('video-frame'),v=$('video');if(box.requestFullscreen)box.requestFullscreen().catch(()=>{});else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen();};
$('sign-out').onclick=async()=>{await closeLink();try{await api('/logout','POST',{});}catch{}token='';$('controls').hidden=true;$('login-card').hidden=false;status('Signed out.');};
window.addEventListener('pagehide',()=>{const code=room;if(code&&token)fetch('/camera/rooms/'+code+'/close',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{});closeLink(false);});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&pc)keepAwake();});
`;
