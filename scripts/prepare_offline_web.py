"""Add a versioned, asset-only offline cache to an already built Flet website."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import shutil
import sys
import tempfile


def remove_private_app_files(root):
    """Keep local state and development history out of the browser bundle.

    Flet's app archive is downloaded by every browser on startup. In addition
    to slowing first load, it must never contain a developer's local match
    database or repository history.
    """
    archive = Path(root) / 'assets/app/app.zip'
    private_names = {
        'stattracker_data.json',
        'stattracker_settings.json',
        'stattracker_sync.json',
    }

    def is_private(name):
        parts = Path(name).parts
        if '.git' in parts or '__pycache__' in parts:
            return True
        base = parts[-1].lower() if parts else ''
        return any(base == item or base.startswith(item + '.corrupt-')
                   for item in private_names)

    with ZipFile(archive, 'r') as source:
        retained = [item for item in source.infolist() if not is_private(item.filename)]
        if len(retained) == len(source.infolist()):
            return 0
        removed_count = len(source.infolist()) - len(retained)
        with tempfile.NamedTemporaryFile(dir=archive.parent, suffix='.zip', delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            with ZipFile(temp_path, 'w') as target:
                target.comment = source.comment
                for item in retained:
                    target.writestr(item, source.read(item.filename))
            try:
                temp_path.replace(archive)
            except PermissionError:
                # Windows app hosts can deny atomic replacement of an open
                # build artifact; the build output itself is safe to rewrite.
                shutil.copyfile(temp_path, archive)
                temp_path.unlink()
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    return removed_count


def prepare(root):
    root=Path(root).resolve()
    for name in ('index.html','python-worker.js','pyodide/pyodide.mjs','assets/app/app.zip'):
        if not (root/name).is_file():raise ValueError('Missing web build resource: '+name)
    removed = remove_private_app_files(root)
    index=root/'index.html';text=index.read_text(encoding='utf-8')
    import re
    text=re.sub(r'noCdn:\s*[^,\n]+', 'noCdn: true',text)
    text=re.sub(r'pyodideUrl:\s*"[^"]+"','pyodideUrl: "./pyodide/pyodide.mjs"',text)
    # Flutter's first frame can arrive while its Pyodide worker is still
    # downloading and initializing the Python app. Keep the branded splash
    # visible until the app sets its runtime title, instead of exposing a
    # blank canvas during that interval.
    splash_marker = 'function removeSplashFromWeb() {'
    if splash_marker in text and 'stcDeferredSplash' not in text:
        text=text.replace(splash_marker, '''function removeSplashFromWeb() {
      if (document.title === "Stat Tracker") {
        const titleNode = document.querySelector("title");
        const status = document.createElement("div");
        status.id = "stc-loading-status";
        status.textContent = "Loading Stat Tracker...";
        status.setAttribute("style", "position:fixed;left:50%;bottom:8vh;transform:translateX(-50%);z-index:9999;color:#94a3b8;font:15px system-ui,sans-serif;text-align:center;padding:10px 16px;max-width:90vw");
        document.body.appendChild(status);
        const stcDeferredSplash = new MutationObserver(() => {
          if (document.title !== "Stat Tracker") {
            stcDeferredSplash.disconnect();
            status.remove();
            document.getElementById("splash")?.remove();
            document.getElementById("splash-branding")?.remove();
            document.body.style.background = "transparent";
          }
        });
        if (titleNode) stcDeferredSplash.observe(titleNode, {childList:true, characterData:true, subtree:true});
        return;
      }''')
    # Use the same JavaScript/WebAssembly build on desktop and mobile Safari.
    # Let installed web apps rotate rather than locking the match to portrait.
    if 'name="apple-mobile-web-app-capable"' not in text:
        text=text.replace('</head>', '<meta name="apple-mobile-web-app-capable" content="yes">\n</head>')
    manifest_path=root/'manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest.update(name='Stat Tracker',short_name='Stat Tracker',orientation='any',display='standalone')
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    index.write_text(text,encoding='utf-8')
    # The save page owns registration; Flutter's version query otherwise
    # attempts an unnecessary network-only worker update during offline startup.
    bootstrap=root/'flutter_bootstrap.js'
    if bootstrap.exists():
        js=bootstrap.read_text(encoding='utf-8')
        js=re.sub(r'serviceWorkerSettings:\s*\{[^}]*\},?', '', js)
        bootstrap.write_text(js,encoding='utf-8')
    font=root/'assets/fonts/roboto.woff2'
    if font.exists():
        target=root/'assets/fonts/roboto/v32/KFOmCnqEu92Fr1Me4GZLCzYlKw.woff2'
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes(font.read_bytes())
    source_assets=Path(__file__).resolve().parents[1]/'assets'
    for name in ('icon.png','icon_small.png','splash.png','splash.jpg'):
        asset=source_assets/name
        if asset.exists():(root/name).write_bytes(asset.read_bytes())
    symbols=source_assets/'offline-fonts/NotoSansSymbols.woff2'
    if symbols.exists():
        target=root/'assets/fonts/notosanssymbols/v43/rP2up3q65FkAtHfwd-eIS2brbDN6gxP34F9jRRCe4W3gfQ8gb_VFRkzrbQ.woff2'
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(symbols.read_bytes())
        (target.parent/'OFL.txt').write_bytes((symbols.parent/'OFL.txt').read_bytes())
    offline='''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Save Stat Tracker offline</title>
<style>body{font:18px system-ui;background:#0f172a;color:#e2e8f0;max-width:650px;margin:8vh auto;padding:24px}button,a{font:inherit;color:#38bdf8}button{padding:14px;background:#172554;border:1px solid #38bdf8;border-radius:8px}p{line-height:1.6}</style>
<h1>Save Stat Tracker for offline use</h1><p>Use Safari on iPhone/iPad or Chrome/Edge on Android and Windows. Do this while online, on every browser you will use. Then open the app, sign in, and open or create your match before disconnecting. Keep the app tab open during the match.</p><button id="save">Save this version</button><p id="status"></p><p><a href="./">Open Stat Tracker</a></p><p>On iPhone/iPad you can also use Safari’s Share → Add to Home Screen. Open that saved app and save this version there before going offline.</p><p>Connect every device to the same Wi-Fi, Feem, Zapya or hotspot. Use Shared match to host or join; Connection codes (fallback) work when local discovery is unavailable. Browser storage can be cleared by your device: test a reload with internet disconnected before leaving.</p>
<script>
const status=document.querySelector('#status');document.querySelector('#save').onclick=async()=>{try{
if(!isSecureContext||!('serviceWorker' in navigator))throw Error('Open the HTTPS website in a browser that supports offline storage.');
status.textContent='Downloading the app and its offline runtime. Keep this page open…';
const reg=await navigator.serviceWorker.register('./flutter_service_worker.js');await reg.update();
await navigator.serviceWorker.ready;
if(reg.installing||reg.waiting){await new Promise((resolve,reject)=>{const worker=reg.installing||reg.waiting;worker.addEventListener('statechange',()=>{if(worker.state==='activated')resolve();if(worker.state==='redundant')reject(Error('Download failed. Check your connection and retry.'));});});}
const channel=new MessageChannel();const saved=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('Offline storage did not confirm. Retry while online.')),10000);channel.port1.onmessage=e=>{clearTimeout(timeout);resolve(e.data.ready);};reg.active.postMessage({type:'status'},[channel.port2]);});
if(!saved)throw Error('The offline download is incomplete. Retry while online.');
if(navigator.storage&&navigator.storage.persist)await navigator.storage.persist();
status.textContent='App files saved. Open Stat Tracker and sign in now, then test reopening it with internet disconnected.';
}catch(e){status.textContent=e.message;}};
</script></html>'''
    (root/'offline.html').write_text(offline,encoding='utf-8')
    skip={'flutter_service_worker.js','offline-manifest.json','.last_build_id'}
    files={}
    for p in root.rglob('*'):
        if not p.is_file() or p.name in skip or p.suffix in ('.map','.exe','.bat','.d.ts') or 'downloads' in p.relative_to(root).parts:continue
        files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    version=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:20]
    manifest={'version':version,'files':sorted(files)}
    (root/'offline-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    worker='''const VERSION=__VERSION__;const CACHE='stc-offline-'+VERSION;const FILES=__FILES__;
const ROOT=new URL('./',self.location.href);const urls=FILES.map(p=>new URL(p,ROOT).href);
self.addEventListener('install',event=>event.waitUntil((async()=>{const cache=await caches.open(CACHE);try{
let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<urls.length){const url=urls[next++];const response=await fetch(url,{cache:'reload'});if(!response.ok)throw Error('Offline download failed');await cache.put(url,response);}}));
await cache.put(new URL('__offline_ready__',ROOT),new Response(VERSION));await self.skipWaiting();
}catch(error){await caches.delete(CACHE);throw error;}})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{await self.clients.claim();for(const key of await caches.keys())if(key.startsWith('stc-offline-')&&key!==CACHE)await caches.delete(key);})()));
self.addEventListener('fetch',event=>{if(event.request.method!=='GET')return;const url=new URL(event.request.url);if(url.origin!==ROOT.origin)return;
let key=url.href.split('?')[0];if(key===ROOT.href)key=new URL('index.html',ROOT).href;if(!urls.includes(key))return;
event.respondWith((async()=>{const cache=await caches.open(CACHE);return (await cache.match(key))||fetch(event.request);})());});
self.addEventListener('message',event=>{if(event.data?.type==='status')event.waitUntil((async()=>{const cache=await caches.open(CACHE);event.ports[0]?.postMessage({ready:!!await cache.match(new URL('__offline_ready__',ROOT))});})());});
'''.replace('__VERSION__',json.dumps(version)).replace('__FILES__',json.dumps(sorted(files)))
    (root/'flutter_service_worker.js').write_text(worker,encoding='utf-8')
    print(f'Offline website prepared: {len(files)} assets, version {version}; removed {removed} private/development archive entries')
    return manifest

if __name__=='__main__':prepare(sys.argv[1] if len(sys.argv)>1 else 'build/web')
