const V='brief-2f037892f8';
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
