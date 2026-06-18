from pathlib import Path
from datetime import datetime, timezone
import json, hashlib

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
TOP6_JSON = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
LEDGER = ASTRO / "ASTRODDS-client-lean-ledger.json"
REPORT = REPORTS / "508_log_client_leans_to_ledger_report.txt"

def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception: return default

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def fnum(v, default=0.0):
    try: return float(str(v).replace(",", ".").replace("%", "").strip())
    except Exception: return default

def key_for(p):
    raw = f"{p.get('game','')}|{p.get('pick','')}|{p.get('edgePct','')}|{p.get('pm','')}|{p.get('fair','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def main():
    ASTRO.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    top = load(TOP6_JSON, {})
    picks = top.get("top6ValidatedPicks", []) or []
    ledger = load(LEDGER, {"createdAt": datetime.now(timezone.utc).isoformat(), "clientLeans": []})
    existing = {x.get("signalKey"): x for x in ledger.get("clientLeans", [])}
    added, skipped = [], []
    for p in picks:
        edge = fnum(p.get("edgePct"))
        if edge < 0.5:
            skipped.append(f"{p.get('pick')} skipped edge<0.5")
            continue
        signal_key = key_for(p)
        if signal_key in existing:
            skipped.append(f"{p.get('pick')} already logged")
            continue
        row = {
            "signalKey": signal_key,
            "loggedAtUTC": datetime.now(timezone.utc).isoformat(),
            "pick": p.get("pick"), "game": p.get("game"),
            "edgePct": p.get("edgePct"), "grade": p.get("grade"),
            "pm": p.get("pm"), "fair": p.get("fair"),
            "clientAction": p.get("clientAction"), "officialTier": p.get("officialTier"),
            "suggestedStake": "0.5%-1% max bankroll" if edge >= 3 else "0.25%-0.5% max bankroll",
            "status": "PENDING", "result": None, "winner": None,
            "awayScore": None, "homeScore": None, "gamePk": None,
            "settledAtUTC": None,
            "rule": "Client lean ledger only. Separate from official A_PICK ledger."
        }
        ledger["clientLeans"].append(row); added.append(row)
    ledger["updatedAt"] = datetime.now(timezone.utc).isoformat(); save(LEDGER, ledger)
    lines = ["ASTRODDS 508 LOG CLIENT LEANS TO LEDGER", "="*78, f"Generated UTC: {datetime.now(timezone.utc).isoformat()}", "", f"Input top6 rows: {len(picks)}", f"Added rows: {len(added)}", f"Total ledger rows: {len(ledger.get('clientLeans', []))}", "", "Added:"]
    lines += [f"- {r['pick']} ML | {r['game']} | Edge=+{r['edgePct']}% | Status=PENDING" for r in added] or ["- none"]
    lines += ["", "Skipped:"] + ([f"- {s}" for s in skipped] or ["- none"])
    lines += ["", f"Ledger: {LEDGER}", "Rule: log client leans before settlement."]
    REPORT.write_text("\n".join(lines), encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
