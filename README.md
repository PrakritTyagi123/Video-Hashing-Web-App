# Video Hasher — Duplicate-finder & gallery for huge video folders

A self-hosted Flask web-app that walks through any folder, hashes every video (SHA-256 by default, optional **blake3**), and shows you—live—exact duplicates, wasted bytes, and pretty thumbnails / 5-second previews.
Pause, resume or stop on demand; when you’re done, prune dupes from the browser or export JSON/CSV reports.

---

## ✨ Key features

| Feature                                | Details                                                                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **100 % bit-wise duplicate detection** | Each file is read end-to-end and hashed (SHA-256 ↔ blake3) by a worker thread                                           |
| **Fast re-runs**                       | Results cached in `hashed/hash_cache.json`, so unchanged files are skipped on the next scan                             |
| **Live dashboard**                     | Server-Sent Events update overall progress, per-file progress, CPU/RAM/disk, ETA, speed & duplicate stats in real time  |
| **Visual duplicates review**           | For every hash group you get thumbnails and 5 s muted previews; select & delete right from the modal                    |
| **Shareable results**                  | Finished screen offers a QR code and public link, plus JSON & CSV downloads                                             |
| **Cross-platform**                     | Tested on Windows 10/11, macOS 14 and Ubuntu 24.04. Anything with Python ≥ 3.9 & `ffmpeg` in `PATH` should work.        |

---

## 🚀 Quick start

```bash
git clone https://github.com/your-name/video-hashing.git
cd video-hashing
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt                     # dependencies :contentReference[oaicite:5]{index=5}
python app.py                                       # launches on http://localhost:5000
```

1. Open the page, choose a folder (drag-drop works) and hit **Start scan** .
2. Watch the dashboard or leave it running in a tab; progress is preserved if you refresh.
3. When it finishes, review/delete duplicates or grab the report.

---

## 🗂 Project layout

```
video-hashing/
│  app.py                # 1-liner that boots the Flask app
├─ backend/              # long-running worker + shared job state
├─ web/                  # Flask blueprint, templates & static assets
├─ hashed/               # thumbnails, previews, cache & per-scan reports
├─ requirements.txt
└─ structure.txt         # (this tree)
```

(The full annotated tree lives in `structure.txt`.)&#x20;

---

## ⚙️ Configuration & tips

* **ffmpeg** is mandatory for thumbnails / previews; install via `winget`, `brew`, `apt` or download from ffmpeg.org.
* To speed up large drives, set environment variable `VH_HASHER=blake3` to switch algorithms (blake3 dependency already listed).
* Want HTTPS or multiple workers? Run under **gunicorn**:

  ```bash
  pip install gunicorn
  gunicorn -w 4 -b 0.0.0.0:8000 web:create_app
  ```
* All output (hashes, thumbnails, previews) is written to `hashed/` next to the repo so the original folders stay untouched.

---

## 🛠 API (for hackers)

| Route                                | Method      | Purpose                          |
| ------------------------------------ | ----------- | -------------------------------- |
| `/start/<jid>`                       | `POST`      | Kick off a queued scan           |
| `/progress_stream/<jid>`             | `GET` (SSE) | Live JSON updates for dashboards |
| `/control/<jid>/<pause⟋resume⟋stop>` | `POST`      | Runtime control                  |
| `/thumb/<file>` / `/preview/<file>`  | `GET`       | Serve cached media               |

All endpoints return JSON or raw media and are declared in `web/routes.py`.

---

## 📈 Roadmap

* ✨  Perceptual (pHash/VidHash) similarity mode
* 🧮  CLI front-end for headless servers
* 🔗  Dedup across multiple scan folders
* 🐳  Docker image

---

## 🤝 Contributing

1. Fork → hack → PR.
2. Make sure `pre-commit run --all-files` passes.
3. Add/update tests where you touch core logic.

---

## 📝 License

MIT. Do what you want, just don’t sue me.

---
