# Builds the installable phone-app (PWA) version of the football brief.
# Usage: python3 tools/build_app.py [brief.html]   (default src/football-brief.html) -> index.html, sw.js, manifest in the repo root
import os, re, json, shutil, hashlib, zipfile

import sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'src', 'football-brief.html')
OUT = REPO
html = open(SRC, encoding='utf-8').read()

# icons: kept as-is in icons/ (helmet)

# ---------- manifest ----------
manifest = {
    "name": "Football Brief", "short_name": "Brief",
    "description": "Denise's daily NFL + college football brief: bets, picks, lessons.",
    "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#FAFAF7", "theme_color": "#2E6B45",
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
json.dump(manifest, open(OUT + '/manifest.webmanifest', 'w'), indent=1)

# ---------- page ----------
head_add = '''<meta name="theme-color" content="#2E6B45">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Brief">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png?v=2">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
'''
assert '<title>Football Brief</title>' in html
html = html.replace('<title>Football Brief</title>', '<title>Football Brief</title>\n' + head_add, 1)

css_add = '''
/* app additions */
.applog{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px 18px}
.applog form{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 4px}
.applog label{display:flex;flex-direction:column;font-family:"Barlow Condensed",Arial,sans-serif;font-size:15px;color:var(--muted)}
.applog label.full{grid-column:1/-1}
.applog input,.applog select{font:inherit;font-family:"Source Serif 4",Georgia,serif;font-size:16px;color:var(--ink);background:var(--paper);
  border:1px solid var(--line);border-radius:6px;padding:8px 10px;min-width:0}
.applog .btn{font-family:"Barlow Condensed",Arial,sans-serif;font-size:17px;font-weight:600;border:0;border-radius:6px;padding:10px 14px;
  background:var(--field);color:#fff;cursor:pointer}
.applog .btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.applog .row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.lg{border-top:1px solid var(--line);padding:10px 0}
.lg:first-child{border-top:0}
.lg .t{display:flex;justify-content:space-between;gap:8px;font-weight:600}
.lg .m{color:var(--muted);font-size:15px}
.lg select,.lg input{font-size:15px;padding:4px 6px;margin-top:6px}
.lgtiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.lgtiles div{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:8px;text-align:center}
.lgtiles b{display:block;font-family:"Barlow Condensed",Arial,sans-serif;font-size:24px}
.pos{color:var(--field)} .neg{color:#B3261E}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .neg{color:#FF8A80}}
:root[data-theme="dark"] .neg{color:#FF8A80}
#appbar{position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:50;background:var(--ink);color:var(--paper);
  border-radius:8px;padding:10px 14px;font-family:"Barlow Condensed",Arial,sans-serif;font-size:17px;display:flex;justify-content:space-between;gap:10px;align-items:center}
#appbar button{font:inherit;background:var(--flag);color:#14202B;border:0;border-radius:6px;padding:6px 12px;font-weight:700}
@media (max-width:420px){.applog form{grid-template-columns:1fr}}
'''
html = html.replace('</style>', css_add + '</style>', 1)

nav_old = '<a href="#mybets">Your bets</a>'
assert nav_old in html
html = html.replace(nav_old, '<a href="#betlog">Bet log</a>' + nav_old, 1)

log_sec = '''<section id="betlog">
<h2>My bet log</h2>
<p>Saved on this phone only. Add each Kalshi bet as you place it, then mark it won, lost or cashed out. Use Export now and then as a backup.</p>
<div class="applog">
<div class="lgtiles"><div><b id="lgOpen">0</b>open</div><div><b id="lgRisk">$0</b>at risk</div><div><b id="lgNet">$0</b>settled net</div></div>
<details><summary><strong>Add a bet</strong></summary>
<form id="lgForm">
<label class="full">Market, side and line<input name="mk" required placeholder="Bijan Robinson: 70+ yards → YES"></label>
<label class="full">Game<input name="gm" placeholder="Falcons at Saints · Mon 5:15"></label>
<label>Cost ($)<input name="cost" type="number" step="0.01" min="0" required inputmode="decimal"></label>
<label>Pays if it wins ($)<input name="pay" type="number" step="0.01" min="0" required inputmode="decimal"></label>
<div class="row full" style="grid-column:1/-1"><button class="btn" type="submit">Save bet</button></div>
</form>
</details>
<div id="lgList"></div>
<div class="row"><button class="btn ghost" type="button" id="lgExp">Export backup</button><label class="btn ghost" style="display:inline-block">Import backup<input type="file" id="lgImp" accept="application/json" hidden></label></div>
</div>
</section>

'''
anchor = '<section id="mybets"'
assert anchor in html
html = html.replace(anchor, log_sec + anchor, 1)

js_add = r'''
<script>
(function(){
var K='fbBetLog',L=[];
try{L=JSON.parse(localStorage.getItem(K)||'[]')}catch(e){L=[]}
function save(){try{localStorage.setItem(K,JSON.stringify(L))}catch(e){}}
function $(id){return document.getElementById(id)}
function money(n){var s=(n<0?'-':'')+'$'+Math.abs(n).toFixed(2);return s}
function net(b){if(b.st==='won')return b.pay-b.cost;if(b.st==='lost')return -b.cost;if(b.st==='cashed')return (b.co||0)-b.cost;return 0}
function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function render(){var box=$('lgList');if(!box)return;box.innerHTML='';
 var open=0,risk=0,tot=0;
 L.slice().reverse().forEach(function(b){var i=L.indexOf(b);
  if(b.st==='open'){open++;risk+=b.cost}else tot+=net(b);
  var d=document.createElement('div');d.className='lg';var n=net(b);
  d.innerHTML='<div class="t"><span>'+esc(b.mk)+'</span><span class="'+(b.st==='open'?'':(n>=0?'pos':'neg'))+'">'+(b.st==='open'?money(b.cost)+' → '+money(b.pay):money(n))+'</span></div>'+
   '<div class="m">'+esc(b.gm)+(b.gm?' · ':'')+esc(b.dt)+'</div>'+
   '<select aria-label="Result"><option value="open">Open</option><option value="won">Won</option><option value="lost">Lost</option><option value="cashed">Cashed out</option></select> '+
   '<input type="number" step="0.01" min="0" inputmode="decimal" placeholder="Cash-out $" aria-label="Cash-out amount" style="width:110px'+(b.st==='cashed'?'':';display:none')+'" value="'+(b.co!=null?b.co:'')+'"> '+
   '<button type="button" class="btn ghost" style="padding:4px 10px;font-size:15px">Delete</button>';
  var sel=d.querySelector('select'),co=d.querySelector('input'),del=d.querySelector('button');sel.value=b.st;
  sel.onchange=function(){b.st=sel.value;save();render()};
  co.onchange=function(){b.co=parseFloat(co.value)||0;save();render()};
  del.onclick=function(){if(confirmDel(d)){L.splice(i,1);save();render()}};
  box.appendChild(d)});
 if(!L.length)box.innerHTML='<p class="m" style="margin:10px 0 0">No bets logged yet.</p>';
 $('lgOpen').textContent=open;$('lgRisk').textContent=money(risk);var t=$('lgNet');t.textContent=money(tot);t.className=tot>0?'pos':(tot<0?'neg':'')}
function confirmDel(d){if(d.dataset.arm){return true}d.dataset.arm=1;var b=d.querySelector('button');b.textContent='Tap again to delete';setTimeout(function(){delete d.dataset.arm;b.textContent='Delete'},3000);return false}
var f=$('lgForm');if(f)f.onsubmit=function(e){e.preventDefault();var v=new FormData(f);
 L.push({mk:v.get('mk'),gm:v.get('gm'),cost:parseFloat(v.get('cost'))||0,pay:parseFloat(v.get('pay'))||0,st:'open',
  dt:new Date().toLocaleString('en-US',{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})});
 save();f.reset();render()};
$('lgExp').onclick=function(){var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(L,null,1)],{type:'application/json'}));
 a.download='bet-log-'+new Date().toISOString().slice(0,10)+'.json';document.body.appendChild(a);a.click();a.remove()};
$('lgImp').onchange=function(){var file=this.files[0];if(!file)return;file.text().then(function(t){try{var x=JSON.parse(t);if(Array.isArray(x)){L=x;save();render()}}catch(e){}})};
var rb=$('refreshBtn');if(rb)rb.onclick=function(){rb.textContent='Checking…';
 var go=function(){location.reload()};
 if(navigator.serviceWorker&&navigator.serviceWorker.getRegistration){navigator.serviceWorker.getRegistration().then(function(r){return r?r.update():null}).then(function(){setTimeout(go,600)},go)}else go()};
render();
// offline + update support
if('serviceWorker' in navigator && location.protocol!=='file:'){
 navigator.serviceWorker.register('sw.js').then(function(reg){
  reg.addEventListener('updatefound',function(){var w=reg.installing;w&&w.addEventListener('statechange',function(){
   if(w.state==='installed'&&navigator.serviceWorker.controller)bar()})})}).catch(function(){});
}
function bar(){if($('appbar'))return;var d=document.createElement('div');d.id='appbar';
 d.innerHTML='<span>New edition of the brief is ready.</span><button type="button">Load it</button>';
 d.querySelector('button').onclick=function(){location.reload()};document.body.appendChild(d)}
})();
</script>
'''

# ---------- "Run my brief" button ----------
SESSION_URL = 'https://claude.ai/code/session_01KyqEyHbiBAUVaBETN2uhGK'
html = re.sub(r'(<span class="stamp">.*?</span>)',
  r'\1<br><a class="runbtn" href="%s" target="_blank" rel="noopener">Run my brief in Claude →</a> <button type="button" class="runbtn ghostbtn" id="refreshBtn">↻ Refresh</button>' % SESSION_URL, html, count=1)
assert 'class="runbtn"' in html
html = html.replace('</style>', '.runbtn{display:inline-block;margin-top:12px;background:var(--flag);color:#14202B;text-decoration:none;'
  'font-family:"Barlow Condensed",Arial,sans-serif;font-weight:700;font-size:19px;padding:8px 16px;border-radius:6px;border:0;cursor:pointer;margin-right:8px;vertical-align:top}'
  '.ghostbtn{background:rgba(255,255,255,.18);color:#fff}\n</style>', 1)

html = html.replace('</body>', js_add + '</body>', 1)
open(OUT + '/index.html', 'w', encoding='utf-8').write(html)

# ---------- service worker (version = content hash so each edition triggers an update) ----------
ver = hashlib.sha1(html.encode()).hexdigest()[:10]
sw = '''const V='brief-%s';
const SHELL=['./','index.html','manifest.webmanifest','icons/apple-touch-icon.png','icons/icon-192.png','icons/icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  const r=e.request; if(r.method!=='GET')return;
  const page=r.mode==='navigate';
  if(page){ // network first so a new edition shows when online; cached copy when offline
    e.respondWith(fetch(r).then(res=>{const c=res.clone();caches.open(V).then(x=>x.put('index.html',c));return res}).catch(()=>caches.match('index.html')));
    return;}
  e.respondWith(caches.match(r).then(hit=>hit||fetch(r).then(res=>{const c=res.clone();caches.open(V).then(x=>x.put(r,c));return res})));
});
''' % ver
open(OUT + '/sw.js', 'w').write(sw)

# ---------- setup guide ----------
guide = '''FOOTBALL BRIEF - PHONE APP
Live at https://foolserrandsf.github.io/football-brief/
Claude publishes each new edition here; the app shows "New edition of the brief is ready - Load it".
Install: open the address in Safari, tap Share, then Add to Home Screen.
Bet log is saved only on your phone; use Export backup to keep a copy.
'''
open(OUT + '/README.txt', 'w').write(guide)

print('built', ver)
