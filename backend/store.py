"""
Tiny JSON-on-disk cache. Anything Groq produces (classifications, summaries,
topic expansions) is saved here so we never pay for the same work twice,
even after a restart.
"""
import json
import threading
import time

from .config import DATA_DIR


class DiskCache:
    def __init__(self, name: str, max_age_hours: float | None = None):
        self.path = DATA_DIR / f"{name}.json"
        self.max_age = max_age_hours * 3600 if max_age_hours else None
        self._lock = threading.Lock()
        self._dirty = False
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}
        self._prune()

    def _prune(self):
        if not self.max_age:
            return
        cutoff = time.time() - self.max_age
        self._data = {k: v for k, v in self._data.items() if v.get("_t", 0) >= cutoff}

    def get(self, key):
        item = self._data.get(key)
        return item["v"] if item else None

    def set(self, key, value):
        with self._lock:
            self._data[key] = {"v": value, "_t": time.time()}
            self._dirty = True

    def __contains__(self, key):
        return key in self._data

    def save(self):
        with self._lock:
            if not self._dirty:
                return
            self._prune()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            self._dirty = False


classifications = DiskCache("classifications", max_age_hours=96)
summaries = DiskCache("summaries", max_age_hours=96)
topic_expansions = DiskCache("topics")  # kept forever, they're tiny


def save_all():
    for c in (classifications, summaries, topic_expansions):
        c.save()
