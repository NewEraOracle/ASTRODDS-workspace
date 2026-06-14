from pathlib import Path
import json
import csv
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

REPORT = BASE / "reports" / "60_mlb_free_injury_connector_report.txt"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-free-injury-transactions-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-free-injury-transactions-latest.csv"
POLICY = BASE / "models" / "ASTRODDS_MLB_FREE_INJURY_CONNECTOR_POLICY.json"

API = "https://statsapi.mlb.com/api/v1/transactions"

# IMPORTANT:
# Do not use the raw substring "il" because it falsely matches words like Louisville, Gilliland, Villalona.
INJURY_PATTERNS = [
    re.compile(r"\binjured list\b", re.I),
    re.compile(r"\binjured\b", re.I),
    re.compile(r"\binjury\b", re.I),
    re.compile(r"\b10-day\b", re.I),
    re.compile(r"\b15-day\b", re.I),
    re.compile(r"\b60-day\b", re.I),
    re.compile(r"\b10 day\b", re.I),
    re.compile(r"\b15 day\b", re.I),
    re.compile(r"\b60 day\b", re.I),
    re.compile(r"\bIL\b"),
    re.compile(r"\bdisabled list\b", re.I),
]

ACTIVATION_PATTERNS = [
    re.compile(r"\breinstated\b", re.I),
    re.compile(r"\bactivated\b", re.I),
    re.compile(r"\breturned from\b", re.I),
]

EXCLUDE_PATTERNS = [
    re.compile(r"\bpaternity list\b", re.I),
    re.compile(r"\bbereavement list\b", re.I),
    re.compile(r"\boptioned\b", re.I),
    re.compile(r"\bsigned free agent\b", re.I),
    re.compile(r"\bminor league contract\b", re.I),
    re.compile(r"\bassigned\b", re.I),
]

def fetch_transactions(days_back=21):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)

    params = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "sportId": "1",
        "limit": "1000",
    }
    url = API + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ASTRODDS-free-injury-connector/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)

    transactions = data.get("transactions", [])
    if not isinstance(transactions, list):
        transactions = []

    return url, start.isoformat(), end.isoformat(), transactions

def text_blob(tx):
    return " ".join([
        str(tx.get("description") or ""),
        str(tx.get("typeDesc") or ""),
        str(tx.get("typeCode") or ""),
    ])

def has_any(patterns, text):
    return any(p.search(text) for p in patterns)

def is_injury_related(tx):
    text = text_blob(tx)

    if not has_any(INJURY_PATTERNS, text):
        return False

    # Allow activations from injured list, but exclude unrelated list/option/signed transactions.
    if has_any(EXCLUDE_PATTERNS, text) and not re.search(r"\binjured list\b|\b10-day\b|\b15-day\b|\b60-day\b", text, re.I):
        return False

    return True

def is_activation_related(tx):
    text = text_blob(tx)
    return has_any(ACTIVATION_PATTERNS, text)

def risk_from_transaction(tx):
    text = text_blob(tx).lower()

    if is_activation_related(tx):
        return "cleared_or_activated", 0, "player_activation_or_reinstatement"

    if "60-day" in text or "60 day" in text:
        return "high", 90, "long_term_injured_list"

    if "15-day" in text or "15 day" in text:
        return "high", 75, "pitcher_or_medium_term_injured_list"

    if "10-day" in text or "10 day" in text:
        return "medium", 60, "standard_injured_list"

    if "injured list" in text or "injury" in text or "injured" in text:
        return "medium", 50, "injury_transaction"

    return "low", 20, "injury_related_unclear"

def normalize_tx(tx):
    team = tx.get("toTeam") or tx.get("fromTeam") or {}
    person = tx.get("person") or {}

    risk, score, flag = risk_from_transaction(tx)

    return {
        "snapshotTime": datetime.now(timezone.utc).isoformat(),
        "transactionId": tx.get("id"),
        "date": tx.get("date"),
        "effectiveDate": tx.get("effectiveDate"),
        "resolutionDate": tx.get("resolutionDate"),
        "playerId": person.get("id"),
        "playerName": person.get("fullName") or person.get("name"),
        "teamId": team.get("id"),
        "teamName": team.get("name"),
        "typeCode": tx.get("typeCode"),
        "typeDesc": tx.get("typeDesc"),
        "description": tx.get("description"),
        "injuryRiskLabel": risk,
        "injuryImpactScore": score,
        "injuryContextFlags": flag,
        "source": "MLB StatsAPI transactions",
        "verifiedFreeSource": True,
        "paperOnly": True,
    }

def main():
    generated = datetime.now(timezone.utc).isoformat()

    try:
        url, start_date, end_date, transactions = fetch_transactions(days_back=21)
        status = "OK"
        error = ""
    except Exception as exc:
        url = ""
        start_date = ""
        end_date = ""
        transactions = []
        status = "ERROR"
        error = str(exc)

    injury_rows = [normalize_tx(tx) for tx in transactions if is_injury_related(tx)]
    injury_rows.sort(key=lambda x: str(x.get("date") or ""), reverse=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(injury_rows, indent=2), encoding="utf-8")

    fieldnames = [
        "snapshotTime", "transactionId", "date", "effectiveDate", "resolutionDate",
        "playerId", "playerName", "teamId", "teamName", "typeCode", "typeDesc",
        "description", "injuryRiskLabel", "injuryImpactScore", "injuryContextFlags",
        "source", "verifiedFreeSource", "paperOnly",
    ]

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in injury_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    policy = {
        "version": "ASTRODDS_MLB_FREE_INJURY_CONNECTOR_POLICY_V2",
        "createdAt": generated,
        "status": status,
        "source": "MLB StatsAPI transactions endpoint",
        "cost": "free_public_endpoint",
        "falsePositiveFix": "Removed raw substring 'il' matching. Uses safer regex patterns for IL/injured list.",
        "coverage": [
            "official transactions",
            "injured list placements",
            "activations/reinstatements when present",
        ],
        "limits": [
            "does not guarantee day-to-day injuries",
            "does not guarantee late scratches",
            "does not replace confirmed lineups",
            "does not provide medical detail beyond transaction description",
        ],
        "officialBuyRule": "If a picked team's key player appears on recent injured-list transaction, downgrade to review unless lineup/context confirms it is irrelevant.",
        "outputs": {
            "json": str(OUT_JSON),
            "csv": str(OUT_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    POLICY.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    counts = {}
    for row in injury_rows:
        k = row.get("injuryRiskLabel", "unknown")
        counts[k] = counts.get(k, 0) + 1

    lines = []
    lines.append("ASTRODDS 60 MLB FREE INJURY CONNECTOR REPORT")
    lines.append("=" * 54)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {status}")
    if error:
        lines.append(f"Error: {error}")
    lines.append(f"Date range: {start_date} to {end_date}")
    lines.append(f"API rows fetched: {len(transactions)}")
    lines.append(f"Injury-related rows: {len(injury_rows)}")
    lines.append("")
    lines.append("Risk counts:")
    if counts:
        for k in sorted(counts):
            lines.append(f"- {k}: {counts[k]}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Latest injury transactions:")
    for row in injury_rows[:25]:
        lines.append(
            f"- {row.get('date')} | {row.get('teamName')} | {row.get('playerName')} | "
            f"Risk={row.get('injuryRiskLabel')} | {row.get('description')}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- Free source covers official transactions / injured list activity.")
    lines.append("- False positive fix: no raw substring IL matching; safer regex only.")
    lines.append("- It does not fully cover day-to-day injuries or late scratches.")
    lines.append("- Keep lineup confirmation as the strongest final check.")
    lines.append("- Paper/manual only. No real-money automation.")
    lines.append("")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append("")
    lines.append("Rule: free injury connector only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

