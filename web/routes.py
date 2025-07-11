import json
import time
import uuid
import mimetypes
import subprocess
import platform
from pathlib import Path

from flask import (
    render_template, request, redirect, abort,
    send_file, Response, stream_with_context, url_for
)
from send2trash import send2trash
import pandas as pd

from backend.scanner import launch_scan
from backend.state   import JOBS, safe

# scans queued here until user presses “Start scan”
PENDING: dict[str, tuple[str, bool]] = {}   # jid → (folder, verify_flag)

def register_routes(app):

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            folder = request.form["folder"].strip()
            verify = "verify" in request.form
            if not folder or not Path(folder).is_dir():
                return render_template("index.html", error="Folder not found.")
            jid = str(uuid.uuid4())
            PENDING[jid] = (folder, verify)
            return redirect(url_for("progress", jid=jid))
        return render_template("index.html")

    @app.route("/start/<jid>", methods=["POST"])
    def start(jid):
        if jid not in PENDING:
            abort(404)
        folder, verify = PENDING.pop(jid)
        launch_scan(jid, folder, verify)
        return ""

    @app.route("/progress/<jid>")
    def progress(jid):
        if jid not in JOBS and jid not in PENDING:
            return redirect(url_for("index"))
        return render_template("progress.html", jid=jid, pending=(jid in PENDING))

    @app.route("/progress_stream/<jid>")
    def progress_stream(jid):
        if jid not in JOBS:
            abort(404)
        def generate():
            yield ":" + " " * 2048 + "\n\n"
            while True:
                yield f"data:{json.dumps(safe(JOBS[jid]))}\n\n"
                if JOBS[jid].get("done") or JOBS[jid].get("stop"):
                    break
                time.sleep(0.4)
        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.route("/control/<jid>/<cmd>", methods=["POST"])
    def control(jid, cmd):
        job = JOBS.get(jid)
        if not job:
            abort(404)
        if cmd == "pause":
            job["pause"].clear()
        elif cmd == "resume":
            job["pause"].set()
        elif cmd == "stop":
            job["stop"] = True
            job["pause"].set()
        else:
            abort(400)
        return ""

    @app.route("/thumb/<fname>")
    def thumb(fname):
        p = Path.cwd() / "hashed" / "thumbnails" / fname
        if not p.exists():
            abort(404)
        return send_file(p, mimetype="image/jpeg")

    @app.route("/preview/<fname>")
    def preview(fname):
        p = Path.cwd() / "hashed" / "previews" / fname
        if not p.exists():
            abort(404)
        return send_file(p, mimetype="video/mp4")

    @app.route("/results/<jid>")
    def results(jid):
        if jid not in JOBS:
            return redirect(url_for("index"))
        return render_template("results.html", jid=jid, job=safe(JOBS[jid]))

    @app.route("/download/<jid>")
    def download(jid):
        path = JOBS.get(jid, {}).get("json_path")
        if path and Path(path).exists():
            return send_file(path, as_attachment=True)
        return redirect(url_for("index"))

    @app.route("/csv/<jid>")
    def csv_export(jid):
        json_path = JOBS.get(jid, {}).get("json_path")
        if not json_path or not Path(json_path).exists():
            return redirect(url_for("index"))
        data = json.load(open(json_path))["videos"]
        csv_bytes = pd.DataFrame(data).to_csv(index=False).encode()
        return Response(
            csv_bytes,
            headers={
                "Content-Disposition": f"attachment; filename=hashes_{jid}.csv",
                "Content-Type": "text/csv"
            },
        )

    @app.route("/dupes/<digest>")
    def dupes(digest):
        for job in JOBS.values():
            dups = job.get("duplicates")
            if dups and digest in dups:
                return dups[digest]
        abort(404)

    @app.route("/delete", methods=["POST"])
    def delete_files():
        deleted = []
        for p in request.json.get("paths", []):
            try:
                send2trash(p)
                deleted.append(p)
            except:
                pass
        return {"deleted": deleted}

    @app.route("/reveal")
    def reveal():
        path = request.args.get("path")
        if not path:
            abort(400)
        sys = platform.system()
        if sys == "Windows":
            subprocess.Popen(["explorer", "/select,", path])
        elif sys == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", Path(path).parent])
        return "", 204

    @app.route("/rescan/<jid>")
    def rescan(jid):
        job = JOBS.get(jid)
        if not job:
            abort(404)
        folder = job.get("scanned_folder")
        verify = job.get("verify_after", False)
        new_jid = str(uuid.uuid4())
        launch_scan(new_jid, folder, verify)
        return redirect(url_for("progress", jid=new_jid))

    @app.route("/gallery/<jid>")
    def gallery(jid):
        if jid not in JOBS:
            return redirect(url_for("results", jid=jid))
        json_path = JOBS[jid].get("json_path")
        if not json_path or not Path(json_path).exists():
            abort(404)
        data = json.load(open(json_path))
        videos = data.get("videos", [])
        # filter out duplicates—only first occurrence of each hash
        seen = set()
        unique = []
        for v in videos:
            h = v.get("hash")
            if h and h not in seen:
                seen.add(h)
                unique.append(v)
        return render_template("gallery.html", vids=unique, jid=jid)
