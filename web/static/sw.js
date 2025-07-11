/*service-worker – caches static assets + root*/
const CACHE="vh-cache-v1";
const ASSETS=["/","/static/style.css","/static/progress.js"];

self.addEventListener("install",ev=>{
  ev.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
});
self.addEventListener("fetch",ev=>{
  ev.respondWith(
    fetch(ev.request).catch(()=>caches.match(ev.request).then(r=>r||caches.match("/")))
  );
});
