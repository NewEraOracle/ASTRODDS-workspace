from pathlib import Path
from datetime import datetime, timezone
import json
ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"; REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
LEDGER = ASTRO / "ASTRODDS-client-lean-ledger.json"
OUT_JSON = ASTRO / "ASTRODDS-client-lean-results-summary-latest.json"
REPORT = REPORTS / "510_client_lean_results_report.txt"
def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception: return default
def main():
    ledger = load(LEDGER, {"clientLeans": []}); rows = ledger.get("clientLeans", []) or []
    settled = [r for r in rows if r.get("status") == "SETTLED"]
    pending = [r for r in rows if r.get("status") == "PENDING"]
    wins = [r for r in settled if r.get("result") == "WIN"]; losses = [r for r in settled if r.get("result") == "LOSS"]
    win_rate = round((len(wins)/len(settled))*100,2) if settled else None
    out = {"generatedAt": datetime.now(timezone.utc).isoformat(), "totalClientLeans": len(rows), "settled": len(settled), "pending": len(pending), "wins": len(wins), "losses": len(losses), "winRate": win_rate, "rows": rows}
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["ASTRODDS 510 CLIENT LEAN RESULTS REPORT", "="*78, f"Generated UTC: {out['generatedAt']}", "", "Record:", f"- Client leans total: {len(rows)}", f"- Settled: {len(settled)}", f"- Pending: {len(pending)}", f"- Wins: {len(wins)}", f"- Losses: {len(losses)}", f"- Win rate: {win_rate if win_rate is not None else 'N/A'}", "", "Rows:"]
    lines += [f"- {r.get('status')} | {r.get('result') or 'PENDING'} | {r.get('pick')} ML | {r.get('game')} | Edge=+{r.get('edgePct')}% | Stake={r.get('suggestedStake')}" for r in rows] or ["- none"]
    lines += ["", f"JSON: {OUT_JSON}", "Rule: client leans are proof-tracked but not official 5% A_PICKs."]
    REPORT.write_text("\n".join(lines), encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
