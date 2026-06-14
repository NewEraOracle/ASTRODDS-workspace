from pathlib import Path
import json
from datetime import datetime

from cache_utils import write_cache, read_cache, cache_stats

BASE = Path(__file__).resolve().parents[1]
REPORT = BASE / "reports" / "35_cache_health_report.txt"

def main():
    test_key = "astrodss_cache_test"
    test_data = {
        "status": "ok",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "message": "ASTRODDS cache layer is working."
    }

    write_path = write_cache("health_check", test_key, test_data)
    cached, status = read_cache("health_check", test_key, ttl_seconds=3600)
    stats = cache_stats()

    ok = status == "hit" and isinstance(cached, dict) and cached.get("status") == "ok"

    lines = []
    lines.append("ASTRODDS 35 CACHE HEALTH REPORT")
    lines.append("=" * 40)
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append(f"Status: {'OK' if ok else 'FAILED'}")
    lines.append(f"Cache write path: {write_path}")
    lines.append(f"Cache read status: {status}")
    lines.append("")
    lines.append("Cache stats:")
    lines.append(f"- Directory: {stats.get('cacheDir')}")
    lines.append(f"- Files: {stats.get('files')}")
    lines.append(f"- Bytes: {stats.get('bytes')}")
    lines.append("")
    lines.append("By namespace:")
    for key, value in sorted(stats.get("byNamespace", {}).items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Next:")
    lines.append("- Connect cache_utils.cached_get_json to bullpen / pitcher / weather scripts.")
    lines.append("- This will reduce repeated MLB StatsAPI calls and lower ETIMEDOUT risk.")
    lines.append("")
    lines.append("Rule: cache stores public sports data only. No secrets.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
