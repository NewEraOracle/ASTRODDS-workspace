from pathlib import Path
import json
import hashlib
import urllib.request
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / ".astrodds" / "cache"

def utc_now():
    return datetime.utcnow()

def iso_now():
    return utc_now().isoformat() + "Z"

def cache_key(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

def cache_path(namespace, key):
    safe_namespace = str(namespace).replace("/", "_").replace("\\", "_")
    return CACHE_DIR / safe_namespace / (cache_key(key) + ".json")

def read_cache(namespace, key, ttl_seconds):
    path = cache_path(namespace, key)

    if not path.exists():
        return None, "miss"

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        saved_at = payload.get("savedAt")
        data = payload.get("data")

        if not saved_at:
            return None, "stale"

        saved_dt = datetime.fromisoformat(saved_at.replace("Z", ""))
        age = (utc_now() - saved_dt).total_seconds()

        if age > ttl_seconds:
            return None, "expired"

        return data, "hit"

    except Exception:
        return None, "error"

def write_cache(namespace, key, data):
    path = cache_path(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "savedAt": iso_now(),
        "namespace": namespace,
        "key": str(key),
        "data": data,
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path

def cached_get_json(url, namespace="url_json", ttl_seconds=3600, timeout=60):
    cached, status = read_cache(namespace, url, ttl_seconds)

    if status == "hit":
        return cached, "cache_hit"

    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))

    write_cache(namespace, url, data)
    return data, "network_fetch"

def cache_stats():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    files = list(CACHE_DIR.rglob("*.json"))
    total_bytes = sum(p.stat().st_size for p in files if p.exists())

    by_namespace = {}

    for path in files:
        try:
            namespace = path.parent.name
            by_namespace[namespace] = by_namespace.get(namespace, 0) + 1
        except Exception:
            pass

    return {
        "cacheDir": str(CACHE_DIR),
        "files": len(files),
        "bytes": total_bytes,
        "byNamespace": by_namespace,
    }
