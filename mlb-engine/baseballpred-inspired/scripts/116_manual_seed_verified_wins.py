# -*- coding: utf-8 -*-
"""
ASTRODDS 116 - Manual seed verified Telegram wins

Purpose:
- Seed the proof ledger with the 3 manually verified wins already taken.
- From this point forward, stats should count only Telegram A+/official signals.
- Manual seed entries are clearly marked manualVerified=True.

Safe:
- Does not send Telegram
- Does not create picks
- Does not modify the betting engine
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LEDGER = ROOT / ".astrodds" / "telegram-verified-signal-ledger.json"
REPORT = BASE / "reports" / "116_manual_seed_verified_wins_report.txt"
ET = ZoneInfo("America/Toronto")

MANUAL_WINS = [
    {
        "signalId": "manual-seed-001-rays-angels-rays",
        "signalDate": "2026-06-14",
        "market": "Tampa Bay Rays vs. Los Angeles Angels",
        "pick": "Tampa Bay Rays",
        "marketType": "moneyline",
        "grade": "A+",
        "stakeRule": "manual",
        "telegramSent": True,
        "result": "WIN",
        "profit": 9.42,
        "manualVerified": True,
        "source": "manual_result_seed",
        "note": "Verified from user Polymarket screenshot."
    },
    {
        "signalId": "manual-seed-002-astros-royals-royals",
        "signalDate": "2026-06-14",
        "market": "Houston Astros vs. Kansas City Royals",
        "pick": "Kansas City Royals",
        "marketType": "moneyline",
        "grade": "A+",
        "stakeRule": "manual",
        "telegramSent": True,
        "result": "WIN",
        "profit": 8.92,
        "manualVerified": True,
        "source": "manual_result_seed",
        "note": "Verified from user Polymarket screenshot."
    },
    {
        "signalId": "manual-seed-003-rays-angels-angels",
        "signalDate": "2026-06-13",
        "market": "Tampa Bay Rays vs. Los Angeles Angels",
        "pick": "Los Angeles Angels",
        "marketType": "moneyline",
        "grade": "A+",
        "stakeRule": "manual",
        "telegramSent": True,
        "result": "WIN",
        "profit": 10.11,
        "manualVerified": True,
        "source": "manual_result_seed",
        "note": "Verified from user Polymarket screenshot."
    },
]

def read_ledger():
    if not LEDGER.exists():
        return {
            "createdAt": datetime.now(ET).isoformat(),
            "rules": {
                "publicWinRate": "Only verified Telegram A+/official signals count.",
                "excluded": ["watchlist", "paper-only", "value lean not sent to Telegram", "action lean not sent to Telegram", "model-only"],
            },
            "signals": []
        }

    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {
            "createdAt": datetime.now(ET).isoformat(),
            "rules": {
                "publicWinRate": "Only verified Telegram A+/official signals count.",
                "excluded": ["watchlist", "paper-only", "value lean not sent to Telegram", "action lean not sent to Telegram", "model-only"],
            },
            "signals": []
        }

def main():
    ledger = read_ledger()
    ledger.setdefault("signals", [])

    existing_ids = {s.get("signalId") for s in ledger["signals"]}
    added = 0
    skipped = 0

    for win in MANUAL_WINS:
        if win["signalId"] in existing_ids:
            skipped += 1
            continue

        win["addedAt"] = datetime.now(ET).isoformat()
        ledger["signals"].append(win)
        added += 1

    ledger["updatedAt"] = datetime.now(ET).isoformat()

    wins = [s for s in ledger["signals"] if s.get("telegramSent") and s.get("result") == "WIN"]
    losses = [s for s in ledger["signals"] if s.get("telegramSent") and s.get("result") == "LOSS"]
    pushes = [s for s in ledger["signals"] if s.get("telegramSent") and s.get("result") == "PUSH"]
    pending = [s for s in ledger["signals"] if s.get("telegramSent") and s.get("result") == "PENDING"]

    graded = len(wins) + len(losses)
    win_rate = (len(wins) / graded) if graded else 0

    ledger["summary"] = {
        "verifiedTelegramSignals": len([s for s in ledger["signals"] if s.get("telegramSent")]),
        "wins": len(wins),
        "losses": len(losses),
        "pushes": len(pushes),
        "pending": len(pending),
        "graded": graded,
        "winRate": round(win_rate, 4),
        "manualSeedWins": len([s for s in ledger["signals"] if s.get("manualVerified") and s.get("result") == "WIN"]),
        "totalProfitTracked": round(sum(float(s.get("profit") or 0) for s in ledger["signals"] if s.get("result") == "WIN"), 2),
    }

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 116 MANUAL SEED VERIFIED WINS",
        "=" * 58,
        f"Generated: {datetime.now(ET).isoformat()}",
        "",
        "Rules:",
        "- Public win rate counts only verified Telegram A+/official signals.",
        "- Manual seed entries are marked manualVerified=true.",
        "- Paper picks / watchlist / non-Telegram leans are excluded.",
        "",
        f"Added: {added}",
        f"Skipped existing: {skipped}",
        "",
        "Current verified Telegram summary:",
        f"- Wins: {ledger['summary']['wins']}",
        f"- Losses: {ledger['summary']['losses']}",
        f"- Pushes: {ledger['summary']['pushes']}",
        f"- Pending: {ledger['summary']['pending']}",
        f"- Win rate: {ledger['summary']['winRate']:.2%}",
        f"- Total profit tracked: ${ledger['summary']['totalProfitTracked']}",
        "",
        "Seeded wins:",
    ]

    for win in MANUAL_WINS:
        lines.append(f"- {win['market']} | Pick={win['pick']} | Result=WIN | Profit=${win['profit']} | Date={win['signalDate']}")

    lines += [
        "",
        f"Ledger: {LEDGER}",
        "",
        "Rule: proof ledger only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
