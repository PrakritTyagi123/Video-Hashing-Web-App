from __future__ import annotations
import re, json, time, datetime, hashlib, subprocess, shutil, psutil
from pathlib import Path
import os
from threading import Event, Thread
from PIL import Image
from .state import JOBS

ROOT_DIR   = Path.cwd() / "hashed"
THUMB_DIR  = ROOT_DIR / "thumbnails"
PREV_DIR   = ROOT_DIR / "previews"
CACHE_FILE = ROOT_DIR / "hash_cache.json"
for d in (THUMB_DIR, PREV_DIR):
    d.mkdir(parents=True, exist_ok=True)

VIDEO_EXT       = {'.mp4','.mkv','.avi','.mov','.wmv','.flv','.webm'}
CHUNK           = 1 << 20
HASHER          = hashlib.sha256
RENAME_MIN_TIME = 1.0  # seconds for the rename pass to last

def _load_cache() -> dict:
    return json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

def _save_cache(db: dict):
    CACHE_FILE.write_text(json.dumps(db, indent=2))

def _hash_stream(path: Path, job) -> str:
    alg, size, done = HASHER(), path.stat().st_size, 0
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(CHUNK), b''):
            if job['stop']: break
            job['pause'].wait()
            alg.update(chunk)
            done += len(chunk)
            job['file_pct'] = done * 100 / size if size else 100
    return alg.hexdigest()

def _vid_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output([
            'ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','format=duration','-of','json', str(path)
        ], text=True)
        return float(json.loads(out)['format']['duration'])
    except:
        return None

def _thumb_for(path: Path, tag: str) -> str:
    jpg = THUMB_DIR / f"{tag}.jpg"
    if jpg.exists(): return jpg.name
    dur = _vid_duration(path) or 4
    ts  = str(datetime.timedelta(seconds=dur/2))
    try:
        subprocess.run([
            'ffmpeg','-y','-loglevel','error',
            '-ss', ts, '-i', str(path),
            '-frames:v','1','-vf','scale=320:-1', str(jpg)
        ], check=True)
    except:
        Image.new('RGB',(320,180),(220,0,0)).save(jpg,'JPEG')
    return jpg.name

def _preview_for(path: Path, tag: str) -> str:
    mp4 = PREV_DIR / f"{tag}.mp4"
    if mp4.exists(): return mp4.name
    dur = _vid_duration(path) or 4
    ts  = str(datetime.timedelta(seconds=dur/2))
    try:
        subprocess.run([
            'ffmpeg','-y','-loglevel','error',
            '-ss', ts, '-i', str(path),
            '-t','5','-vf','scale=320:-1', '-an', str(mp4)
        ], check=True)
    except:
        pass
    return mp4.name

def _sys_stats(base: Path):
    d = shutil.disk_usage(base.drive if os.name=='nt' else '/')
    return {
        'cpu': psutil.cpu_percent(),
        'mem': psutil.virtual_memory().percent,
        'free': round(d.free/(1<<30),1)
    }

def launch_scan(jid: str, folder: str|Path, verify_after: bool):
    pause = Event(); pause.set()
    JOBS[jid] = {
        'pause': pause,
        'stop': False,
        'scanned_folder': str(folder),
        'verify_after': verify_after,
        'stage': 'Waiting…',
        'progress': 0, 'total': 0,
        'bytes_scanned': 0, 'bytes_total': 0,
        'speed': 0, 'eta': 0, 'file_pct': 0,
        'duplicate_bytes': 0, 'dup_groups': 0, 'largest_group': 1
    }
    Thread(target=_worker, args=(jid, Path(folder)), daemon=True).start()

def _worker(jid: str, folder: Path):
    J = JOBS[jid]
    files = [p for p in folder.rglob('*') if p.suffix.lower() in VIDEO_EXT]
    J.update(total=len(files))

    # preload total size
    total_bytes = sum(p.stat().st_size for p in files)
    J.update(bytes_total=total_bytes, bytes_scanned=0)

    # 1) Pre-hash: renaming
    J.update(stage="(STAGE 1/6) Pre-hash: Renaming Files", progress=0)
    per_delay = max(RENAME_MIN_TIME / max(len(files),1), 0.15)
    rx = re.compile(r'[_-]?720m', re.I)
    renamed = []
    for i,p in enumerate(files,1):
        if J['stop']: break
        newn = rx.sub('', p.name.replace('-',' ')).strip()
        q = p.with_name(newn)
        if q != p:
            try: p.rename(q)
            except: pass
        renamed.append(q)
        J.update(progress=i, current_file=str(q), file_pct=100, **_sys_stats(folder))
        time.sleep(per_delay)
    files = renamed

    # 2) Pre-hash: extracting previews
    J.update(stage="(STAGE 2/6) Pre-hash: Extracting Previews", progress=0)
    for i,p in enumerate(files,1):
        if J['stop']: break
        _preview_for(p, p.stem)
        J.update(progress=i, current_file=str(p), file_pct=100, **_sys_stats(folder))

    # 3) Pre-hash: collecting thumbnails
    J.update(stage="(STAGE 3/6) Pre-hash: Collecting Thumbnails", progress=0)
    for i,p in enumerate(files,1):
        if J['stop']: break
        thumb = _thumb_for(p, p.stem)
        J.update(progress=i, thumbnail=thumb, current_file=str(p), file_pct=100, **_sys_stats(folder))

    # 4) Loading files
    J.update(stage="(STAGE 4/6) Loading files…",
             remaining=[{'name':p.name,'size':p.stat().st_size} for p in files],
             scanned_names=[], progress=0, file_pct=0)
    time.sleep(0.5)

    # 5) Hashing
    cache, videos, dupmap, dup_bytes = _load_cache(), [], {}, 0
    start_ts = time.time()
    J.update(stage="(STAGE 5/6) Hashing…", progress=0, bytes_scanned=0)

    json_path = ROOT_DIR / f"video_hashes_{jid}.json"
    J['json_path'] = str(json_path)

    for i,p in enumerate(files,1):
        if J['stop']: break
        st = p.stat()
        J.update(current_file=str(p), current_size=st.st_size, file_pct=0, progress=i)

        key = str(p)
        c   = cache.get(key)
        dig = c['hash'] if c and c['size']==st.st_size and c['mtime']==st.st_mtime \
              else _hash_stream(p, J)
        cache[key] = {'hash':dig,'size':st.st_size,'mtime':st.st_mtime}

        thumb = _thumb_for(p, dig)
        prev  = _preview_for(p, dig)

        rec = {'path':str(p),'name':p.name,'hash':dig,
               'size':st.st_size,'thumb':thumb,'prev':prev}
        videos.append(rec)
        grp = dupmap.setdefault(dig, [])
        grp.append(rec)
        if len(grp)>1: dup_bytes += st.st_size

        scanned = sum(v['size'] for v in videos)
        speed   = int(scanned/max(time.time()-start_ts,1)/1048576)
        eta     = int((total_bytes-scanned)/1048576/max(speed,1))

        J.update(
          bytes_scanned=scanned, speed=speed, eta=eta, file_pct=0,
          duplicate_bytes=dup_bytes,
          dup_groups=len([g for g in dupmap.values() if len(g)>1]),
          largest_group=max((len(g) for g in dupmap.values()), default=1),
          thumbnail=thumb,
          scanned_names=[v['name'] for v in videos],
          remaining=[{'name':x.name,'size':x.stat().st_size} for x in files[i:]],
          duplicates={h:v for h,v in dupmap.items() if len(v)>1},
          **_sys_stats(folder)
        )

        json_path.write_text(json.dumps({
          'scanned_folder':str(folder),
          'scanned_at':datetime.datetime.now().isoformat(timespec='seconds'),
          'videos':videos,'duplicates':J['duplicates'],
          'progress':f"{i}/{len(files)}",'dup_bytes':dup_bytes
        }, indent=2))

    _save_cache(cache)
    J.update(stage="(STAGE 6/6)Hashing Complete", done=True, speed=0, eta=0, file_pct=100)
