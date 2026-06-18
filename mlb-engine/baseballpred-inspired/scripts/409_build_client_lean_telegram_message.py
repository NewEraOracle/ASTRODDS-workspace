from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

TOP6_JSON = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-client-lean-telegram-message-latest.json"
REPORT = REPORTS / "409_client_lean_telegram_message_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def fnum(v, default=None):
    try:
        if v is None:
            return default
        s = str(v).replace(",", ".").replace("%", "").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load(TOP6_JSON)
    picks = data.get("top6ValidatedPicks", []) or []

    eligible = []
    for p in picks:
        edge = fnum(p.get("edgePct"))
        tier = str(p.get("officialTier", ""))
        action = str(p.get("clientAction", ""))
        if edge is not None and edge >= 0.5 and tier in ["CLIENT_LEAN", "CLIENT_PASS_LEAN"] and action in ["Buy", "Lean", "Pass/Lean"]:
            eligible.append(p)

    eligible.sort(key=lambda x: fnum(x.get("edgePct"), -999), reverse=True)
    chosen = eligible[:3]

    if chosen:
        lines = [
            "ASTRODDS CLIENT LEAN",
            "Small edge detected - NOT an official 5% A_PICK.",
            "",
        ]

        for i, p in enumerate(chosen, 1):
            edge = fnum(p.get("edgePct"), 0)
            pm = fnum(p.get("pm"), 0)
            fair = fnum(p.get("fair"), 0)
            grade = p.get("grade", "NA")
            stake = "0.5%-1% max bankroll" if edge >= 3 else "0.25%-0.5% max bankroll"

            lines += [
                f"{i}. {p.get('pick')} ML",
                f"Game: {p.get('game')}",
                f"Market Price: {pm:.2f}%",
                f"Fair Price: {fair:.2f}%",
                f"Edge: +{edge:.2f}%",
                f"Grade: {grade}",
                "Action: Small lean / Buy",
                f"Stake: {stake}",
                "",
            ]

        lines += [
            "Rule: client lean only. Smaller size than official picks.",
            "No parlays. Paper/manual only. No real-money automation.",
        ]
        should_send = True
        reason = "eligible_client_lean_found"
    else:
        lines = [
            "ASTRODDS CLIENT LEAN",
            "No client lean available right now.",
            "Rule: no Telegram send when no positive client lean exists.",
        ]
        should_send = False
        reason = "no_eligible_client_lean"

    message = "\n".join(lines)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "shouldSend": should_send,
        "reason": reason,
        "eligibleRows": len(eligible),
        "chosenRows": len(chosen),
        "telegramMessage": message,
        "picks": chosen,
        "rule": "Client lean Telegram is separate from official A_PICK Telegram. ASCII safe.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    report = [
        "ASTRODDS 409 CLIENT LEAN TELEGRAM MESSAGE",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Should send: {should_send}",
        f"Reason: {reason}",
        f"Eligible rows: {len(eligible)}",
        f"Chosen rows: {len(chosen)}",
        "",
        "Message:",
        message,
        "",
        f"JSON: {OUT_JSON}",
        "Rule: separate small lean alerts from official bankroll alerts.",
    ]

    REPORT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))

if __name__ == "__main__":
    main()
