from threading import Event

# Global job dictionary (jid → data)
JOBS: dict[str, dict] = {}

def safe(job: dict) -> dict:
    """
    Return a JSON-serialisable snapshot of a job dict.
    • Strips out objects Pylance/JSON can't encode (Event, thread objects, etc.)
    • Adds a boolean “paused” flag so the frontend knows pause/resume state
    """
    cleaned = {k: v for k, v in job.items() if not isinstance(v, Event)}
    if "pause" in job:
        cleaned["paused"] = not job["pause"].is_set()
    return cleaned
