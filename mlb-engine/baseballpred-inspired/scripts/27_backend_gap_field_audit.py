from pathlib import Path
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "27_backend_gap_field_audit_report.txt"

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    data = fetch_json(API_URL)
    rows = data.get("bestBetRows") or data.get("rows") or []

    all_keys = sorted({k for r in rows for k in r.keys()})
    gap_keys = [k for k in all_keys if "gap" in k.lower()]
    edge_keys = [k for k in all_keys if "edge" in k.lower()]
    prob_keys = [k for k in all_keys if "prob" in k.lower()]
    score_keys = [k for k in all_keys if "score" in k.lower()]
    diag_keys = [k for k in all_keys if "diagnostic" in k.lower()]

    lines = []
    lines.append("ASTRODDS 27 BACKEND GAP FIELD AUDIT")
    lines.append("=" * 42)
    lines.append("")
    lines.append(f"Rows: {len(rows)}")
    lines.append("")
    lines.append("Gap keys:")
    for k in gap_keys:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("Edge keys:")
    for k in edge_keys:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("Probability keys:")
    for k in prob_keys:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("Score keys:")
    for k in score_keys:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("Diagnostic keys:")
    for k in diag_keys:
        lines.append(f"- {k}")

    lines.append("")
    lines.append("First 5 moneyline rows:")
    moneyline = [r for r in rows if r.get("marketType") == "moneyline"][:5]

    for i, r in enumerate(moneyline, 1):
        lines.append("")
        lines.append(f"ROW {i}")
        lines.append(f"Game: {r.get('awayTeam')} @ {r.get('homeTeam')}")
        lines.append(f"Pick: {r.get('selectedSide')}")
        lines.append(f"Status: {r.get('status')}")
        lines.append(f"MarketProbability: {r.get('marketProbability')}")
        lines.append(f"CalibratedProbability: {r.get('calibratedProbability')}")
        lines.append(f"DiagnosticCalibratedEdgePct: {r.get('diagnosticCalibratedEdgePct')}")
        lines.append(f"DiagnosticRawEdgePct: {r.get('diagnosticRawEdgePct')}")
        lines.append("Keys:")
        for k in sorted(r.keys()):
            if any(x in k.lower() for x in ["gap", "edge", "prob", "score", "diagnostic"]):
                lines.append(f"  {k}: {r.get(k)}")

    lines.append("")
    lines.append("Conclusion:")
    lines.append("- If no gap key exists, backend route must add modelProbabilityGapPct.")
    lines.append("- Full slate official engine stays blocked until this field exists.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
