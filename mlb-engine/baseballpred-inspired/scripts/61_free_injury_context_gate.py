from pathlib import Path
import json
import csv
import re
from datetime import datetime, timezone, timedelta

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

SLATE_INPUT = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json"
INJURY_INPUT = ROOT / ".astrodds" / "ASTRODDS-free-injury-transactions-latest.json"
PITCHER_INPUT = ROOT / ".astrodds" / "VVS-pitcher-context-latest.json"

OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-free-injury-context-gate-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-free-injury-context-gate-latest.csv"
REPORT = BASE / "reports" / "61_free_injury_context_gate_report.txt"
POLICY = BASE / "models" / "ASTRODDS_FREE_INJURY_CONTEXT_GATE_POLICY.json"

TEAM_ALIASES = {
    "athletics": "athletics",
    "oakland athletics": "athletics",
    "a's": "athletics",
    "arizona diamondbacks": "arizona diamondbacks",
    "atlanta braves": "atlanta braves",
    "baltimore orioles": "baltimore orioles",
    "boston red sox": "boston red sox",
    "chicago cubs": "chicago cubs",
    "chicago white sox": "chicago white sox",
    "cincinnati reds": "cincinnati reds",
    "cleveland guardians": "cleveland guardians",
    "colorado rockies": "colorado rockies",
    "detroit tigers": "detroit tigers",
    "houston astros": "houston astros",
    "kansas city royals": "kansas city royals",
    "los angeles angels": "los angeles angels",
    "la angels": "los angeles angels",
    "los angeles dodgers": "los angeles dodgers",
    "la dodgers": "los angeles dodgers",
    "miami marlins": "miami marlins",
    "milwaukee brewers": "milwaukee brewers",
    "minnesota twins": "minnesota twins",
    "new york mets": "new york mets",
    "ny mets": "new york mets",
    "new york yankees": "new york yankees",
    "ny yankees": "new york yankees",
    "philadelphia phillies": "philadelphia phillies",
    "pittsburgh pirates": "pittsburgh pirates",
    "san diego padres": "san diego padres",
    "san francisco giants": "san francisco giants",
    "seattle mariners": "seattle mariners",
    "st. louis cardinals": "st. louis cardinals",
    "st louis cardinals": "st. louis cardinals",
    "tampa bay rays": "tampa bay rays",
    "texas rangers": "texas rangers",
    "toronto blue jays": "toronto blue jays",
    "washington nationals": "washington nationals",
}

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def clean_name(value):
    s = str(value or "").lower().strip()
    s = re.sub(r"[^a-z0-9Ã -Ã¿Ã±Ã³Ã©Ã­Ã¡ÃºÃ¼Ã§\s\.\-']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_team(name):
    s = str(name or "").lower().strip()
    s = s.replace("@", " ")
    s = re.sub(r"[^a-z0-9\. ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return TEAM_ALIASES.get(s, s)

def parse_date(value):
    if not value:
        return None
    s = str(value)
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return datetime.fromisoformat(s).date()
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            return None

def days_ago(value):
    d = parse_date(value)
    if not d:
        return None
    today = datetime.now(timezone.utc).date()
    return (today - d).days

def get_game_teams(row):
    away = row.get("awayTeam") or row.get("away_team")
    home = row.get("homeTeam") or row.get("home_team")

    if (not away or not home) and row.get("game"):
        game = str(row.get("game"))
        if " @ " in game:
            parts = game.split(" @ ", 1)
            away = away or parts[0].strip()
            home = home or parts[1].strip()
        elif " vs " in game:
            parts = game.split(" vs ", 1)
            away = away or parts[0].strip()
            home = home or parts[1].strip()

    return away, home

def game_key(away, home):
    return f"{norm_team(away)}|{norm_team(home)}"

def get_any(row, keys):
    for k in keys:
        if k in row and row.get(k) not in [None, ""]:
            return row.get(k)
    return None

def pitcher_context_map():
    rows = read_json(PITCHER_INPUT, [])
    if not isinstance(rows, list):
        return {}

    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue

        away, home = get_game_teams(row)
        key = game_key(away, home)

        away_sp = get_any(row, [
            "awayProbablePitcher", "awayPitcher", "awayStartingPitcher", "awaySP",
            "away_probable_pitcher", "away_probable_pitcher_name"
        ])
        home_sp = get_any(row, [
            "homeProbablePitcher", "homePitcher", "homeStartingPitcher", "homeSP",
            "home_probable_pitcher", "home_probable_pitcher_name"
        ])

        # Some generated context rows use display fields instead of camel-case.
        if not away_sp:
            for k, v in row.items():
                if "away" in str(k).lower() and ("pitcher" in str(k).lower() or str(k).lower().endswith("sp")):
                    away_sp = v
                    break
        if not home_sp:
            for k, v in row.items():
                if "home" in str(k).lower() and ("pitcher" in str(k).lower() or str(k).lower().endswith("sp")):
                    home_sp = v
                    break

        if key.strip("|"):
            out[key] = {
                "awayProbablePitcher": away_sp,
                "homeProbablePitcher": home_sp,
            }
    return out

def is_active_injury(tx):
    label = str(tx.get("injuryRiskLabel") or "").lower()
    desc = str(tx.get("description") or "").lower()

    if label == "cleared_or_activated":
        return False
    if "activated" in desc or "reinstated" in desc:
        return False

    return label in ["high", "medium", "low"]

def is_recent_active(tx):
    d = days_ago(tx.get("date") or tx.get("effectiveDate"))
    if d is None:
        return True
    label = str(tx.get("injuryRiskLabel") or "").lower()

    if label == "high":
        return d <= 14
    if label == "medium":
        return d <= 10
    if label == "low":
        return d <= 7
    return False

def tx_position_hint(tx):
    desc = str(tx.get("description") or "")
    # Captures common MLB transaction position abbreviations before player name.
    m = re.search(r"\b(RHP|LHP|SP|RP|P|C|1B|2B|3B|SS|LF|CF|RF|OF|DH)\b", desc)
    return m.group(1) if m else ""

def player_matches(name_a, name_b):
    a = clean_name(name_a)
    b = clean_name(name_b)
    if not a or not b:
        return False
    return a == b or a in b or b in a

def summarize_team(team_key, txs, probable_pitcher_name=None):
    active = [tx for tx in txs if is_active_injury(tx) and is_recent_active(tx)]

    high = [x for x in active if str(x.get("injuryRiskLabel")).lower() == "high"]
    medium = [x for x in active if str(x.get("injuryRiskLabel")).lower() == "medium"]
    low = [x for x in active if str(x.get("injuryRiskLabel")).lower() == "low"]

    probable_pitcher_hit = []
    for tx in active:
        if player_matches(tx.get("playerName"), probable_pitcher_name):
            probable_pitcher_hit.append(tx)

    pitcher_injuries = []
    hitter_injuries = []
    for tx in active:
        pos = tx_position_hint(tx)
        if pos in ["RHP", "LHP", "SP", "RP", "P"]:
            pitcher_injuries.append(tx)
        else:
            hitter_injuries.append(tx)

    score = 0
    for tx in active:
        label = str(tx.get("injuryRiskLabel") or "").lower()
        d = days_ago(tx.get("date") or tx.get("effectiveDate"))
        recency_bonus = 10 if d is not None and d <= 3 else 0

        if label == "high":
            score += 25 + recency_bonus
        elif label == "medium":
            score += 15 + recency_bonus
        elif label == "low":
            score += 5

    if probable_pitcher_hit:
        score += 60

    score = min(score, 100)

    if probable_pitcher_hit:
        risk = "critical_pitcher_match"
    elif len(high) >= 2:
        risk = "high"
    elif len(high) == 1 or len(medium) >= 2:
        risk = "medium"
    elif len(medium) == 1 or low:
        risk = "low"
    else:
        risk = "none"

    latest = sorted(active, key=lambda x: str(x.get("date") or ""), reverse=True)[:5]
    details = []
    for tx in latest:
        details.append(f"{tx.get('date')} {tx.get('playerName')}: {tx.get('description')}")

    return {
        "teamKey": team_key,
        "activeInjuryCount": len(active),
        "highCount": len(high),
        "mediumCount": len(medium),
        "lowCount": len(low),
        "probablePitcherName": probable_pitcher_name,
        "probablePitcherHitCount": len(probable_pitcher_hit),
        "pitcherInjuryCount": len(pitcher_injuries),
        "hitterInjuryCount": len(hitter_injuries),
        "risk": risk,
        "score": score,
        "details": " || ".join(details) if details else "No recent active official IL transaction found for this team.",
    }

def official_buy_impact(picked_summary):
    risk = picked_summary.get("risk")
    if risk == "critical_pitcher_match":
        return "block_or_admin_review"
    if risk == "high":
        return "manual_review"
    if risk == "medium":
        return "manual_review"
    if risk == "low":
        return "monitor"
    return "no_block"

def main():
    generated = datetime.now(timezone.utc).isoformat()

    slate = read_json(SLATE_INPUT, [])
    injuries = read_json(INJURY_INPUT, [])
    pitcher_map = pitcher_context_map()

    if not isinstance(slate, list):
        slate = []
    if not isinstance(injuries, list):
        injuries = []

    by_team = {}
    for tx in injuries:
        team_key = norm_team(tx.get("teamName"))
        if not team_key:
            continue
        by_team.setdefault(team_key, []).append(tx)

    output_rows = []

    for row in slate:
        if not isinstance(row, dict):
            continue

        away, home = get_game_teams(row)
        pick = row.get("pick") or row.get("selectedSide") or row.get("pickTeam")

        away_key = norm_team(away)
        home_key = norm_team(home)
        pick_key = norm_team(pick)
        gkey = game_key(away, home)

        pctx = pitcher_map.get(gkey, {})
        away_sp = pctx.get("awayProbablePitcher")
        home_sp = pctx.get("homeProbablePitcher")

        away_summary = summarize_team(away_key, by_team.get(away_key, []), away_sp)
        home_summary = summarize_team(home_key, by_team.get(home_key, []), home_sp)

        if pick_key == away_key:
            picked_summary = away_summary
            opponent_summary = home_summary
        elif pick_key == home_key:
            picked_summary = home_summary
            opponent_summary = away_summary
        else:
            picked_summary = {
                "risk": "unknown",
                "score": 0,
                "details": "Picked team could not be matched to away/home team.",
                "activeInjuryCount": 0,
                "probablePitcherHitCount": 0,
            }
            opponent_summary = {"risk": "unknown", "score": 0, "details": ""}

        impact = official_buy_impact(picked_summary)

        flags = []
        risk = picked_summary.get("risk")
        if risk == "critical_pitcher_match":
            flags.append("picked_probable_pitcher_injured")
        elif risk == "high":
            flags.append("picked_team_high_recent_injury_cluster")
        elif risk == "medium":
            flags.append("picked_team_medium_recent_injury_context")
        elif risk == "low":
            flags.append("picked_team_low_injury_monitor")
        elif risk == "none":
            flags.append("free_injury_context_clean")
        else:
            flags.append("picked_team_match_unknown")

        if opponent_summary.get("risk") in ["critical_pitcher_match", "high", "medium"]:
            flags.append("opponent_injury_context")

        output_rows.append({
            "snapshotTime": generated,
            "sourceSlate": str(SLATE_INPUT),
            "sourceInjuries": str(INJURY_INPUT),
            "sourcePitchers": str(PITCHER_INPUT),
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "game": row.get("game") or f"{away} @ {home}",
            "awayTeam": away,
            "homeTeam": home,
            "pick": pick,
            "decision": row.get("thresholdDecision") or row.get("finalEngineDecision") or row.get("decision"),
            "grade": row.get("grade") or row.get("finalGrade"),
            "awayProbablePitcher": away_sp,
            "homeProbablePitcher": home_sp,
            "awayInjuryRisk": away_summary.get("risk"),
            "awayInjuryScore": away_summary.get("score"),
            "awayActiveInjuryCount": away_summary.get("activeInjuryCount"),
            "awayProbablePitcherHitCount": away_summary.get("probablePitcherHitCount"),
            "homeInjuryRisk": home_summary.get("risk"),
            "homeInjuryScore": home_summary.get("score"),
            "homeActiveInjuryCount": home_summary.get("activeInjuryCount"),
            "homeProbablePitcherHitCount": home_summary.get("probablePitcherHitCount"),
            "pickedTeamInjuryRisk": picked_summary.get("risk"),
            "pickedTeamInjuryScore": picked_summary.get("score"),
            "pickedTeamActiveInjuryCount": picked_summary.get("activeInjuryCount"),
            "pickedTeamProbablePitcherHitCount": picked_summary.get("probablePitcherHitCount"),
            "pickedTeamInjuryDetails": picked_summary.get("details"),
            "opponentInjuryRisk": opponent_summary.get("risk"),
            "freeInjuryContextFlags": "|".join(flags),
            "officialBuyImpact": impact,
            "paperOnly": True,
        })

    write_json(OUT_JSON, output_rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "snapshotTime", "sourceSlate", "sourceInjuries", "sourcePitchers", "gameId", "date", "game",
        "awayTeam", "homeTeam", "pick", "decision", "grade",
        "awayProbablePitcher", "homeProbablePitcher",
        "awayInjuryRisk", "awayInjuryScore", "awayActiveInjuryCount", "awayProbablePitcherHitCount",
        "homeInjuryRisk", "homeInjuryScore", "homeActiveInjuryCount", "homeProbablePitcherHitCount",
        "pickedTeamInjuryRisk", "pickedTeamInjuryScore", "pickedTeamActiveInjuryCount",
        "pickedTeamProbablePitcherHitCount", "pickedTeamInjuryDetails",
        "opponentInjuryRisk", "freeInjuryContextFlags", "officialBuyImpact", "paperOnly",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in output_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    policy = {
        "version": "ASTRODDS_FREE_INJURY_CONTEXT_GATE_POLICY_V2",
        "createdAt": generated,
        "status": "OK" if output_rows else "NO_SLATE_ROWS",
        "source": "MLB StatsAPI transactions joined to current slate teams",
        "lookbackRules": {
            "high": "14 days",
            "medium": "10 days",
            "low": "7 days",
        },
        "smarterGateRules": {
            "critical_pitcher_match": "block_or_admin_review only when picked probable pitcher matches injured player",
            "high": "manual_review for picked-team high injury cluster",
            "medium": "manual_review for picked-team medium injury context",
            "low": "monitor only",
            "none": "no_block",
        },
        "limits": [
            "covers official injured-list transactions, not all day-to-day injuries",
            "does not replace confirmed lineups",
            "team-level matching cannot fully know player importance without lineup/roster weighting",
        ],
        "outputs": {
            "json": str(OUT_JSON),
            "csv": str(OUT_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    counts = {}
    for r in output_rows:
        impact = r.get("officialBuyImpact", "unknown")
        counts[impact] = counts.get(impact, 0) + 1

    lines = []
    lines.append("ASTRODDS 61 FREE INJURY CONTEXT GATE REPORT")
    lines.append("=" * 54)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Slate rows: {len(slate)}")
    lines.append(f"Free injury rows loaded: {len(injuries)}")
    lines.append(f"Pitcher context games loaded: {len(pitcher_map)}")
    lines.append(f"Output rows: {len(output_rows)}")
    lines.append("")
    lines.append("Official buy impact counts:")
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("Current injury gate rows:")
    for r in output_rows[:20]:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"PickedRisk={r.get('pickedTeamInjuryRisk')} | "
            f"ActiveInj={r.get('pickedTeamActiveInjuryCount')} | "
            f"PitcherHit={r.get('pickedTeamProbablePitcherHitCount')} | "
            f"Impact={r.get('officialBuyImpact')} | Flags={r.get('freeInjuryContextFlags')}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- Smarter gate: does not block every team just because any player has an IL transaction.")
    lines.append("- Block is reserved for picked probable pitcher injury match.")
    lines.append("- High/medium team injury context forces manual review, not public auto-send.")
    lines.append("- This does not consume odds credits.")
    lines.append("- Paper/manual only. No real-money automation.")
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: injury context gate only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

