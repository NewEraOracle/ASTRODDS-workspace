# -*- coding: utf-8 -*-
"""
ASTRODDS 122 - Retrosheet BaseballPred Sidecar Audit

Purpose:
- Add BaseballPred-style historical Retrosheet support on the side.
- Does NOT touch the current live bot, Telegram, public board, O/U model, moneyline engine, or scans.
- Audits Retrosheet game log files if they exist locally.
- Prepares the path for rolling 162-game historical features later.

Expected Retrosheet folder:
1) Set env var:
   ASTRODDS_RETROSHEET_GAMELOG_DIR=C:\\path\\to\\retrosheet\\gamelogs

OR

2) Put files here:
   .astrodds\\retrosheet\\gamelogs\\gl1980.txt, gl1981.txt, ...

Safe:
- Audit only
- No Telegram send
- No betting automation
- No model override
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import os
import re
from collections import defaultdict, deque

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/Toronto")

REPORT = BASE / "reports" / "122_retrosheet_baseballpred_sidecar_audit_report.txt"
LATEST_JSON = ROOT / ".astrodds" / "ASTRODDS-retrosheet-baseballpred-sidecar-audit-latest.json"

DEFAULT_GAMELOG_DIR = ROOT / ".astrodds" / "retrosheet" / "gamelogs"
OUT_FEATURE_PREVIEW = ROOT / ".astrodds" / "retrosheet" / "baseballpred_rolling162_feature_preview.json"

# Retrosheet game log column positions from BaseballPred style logs.
IDX_DATE = 0
IDX_DBLHEADER = 1
IDX_TEAM_V = 3
IDX_TEAM_H = 6
IDX_RUNS_V = 9
IDX_RUNS_H = 10
IDX_DAY_NIGHT = 12
IDX_BALLPARK = 16

# Basic hitting stats by away/home side.
IDX_AB_V = 21
IDX_H_V = 22
IDX_2B_V = 23
IDX_3B_V = 24
IDX_HR_V = 25
IDX_BB_V = 30
IDX_HBP_V = 29
IDX_SF_V = 28

IDX_AB_H = 49
IDX_H_H = 50
IDX_2B_H = 51
IDX_3B_H = 52
IDX_HR_H = 53
IDX_BB_H = 58
IDX_HBP_H = 57
IDX_SF_H = 56

ROLLING_WINDOW = 162

def as_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def as_str(row, idx, default=""):
    try:
        return str(row[idx])
    except Exception:
        return default

def get_gamelog_dir():
    env_path = os.getenv("ASTRODDS_RETROSHEET_GAMELOG_DIR")
    if env_path:
        return Path(env_path)
    return DEFAULT_GAMELOG_DIR

def list_gamelog_files(folder):
    if not folder.exists():
        return []
    files = []
    for p in folder.glob("gl*.txt"):
        if re.match(r"gl\d{4}\.txt$", p.name.lower()):
            files.append(p)
    return sorted(files)

def team_side_stats(row, side):
    if side == "v":
        ab = as_int(row[IDX_AB_V])
        hits = as_int(row[IDX_H_V])
        doubles = as_int(row[IDX_2B_V])
        triples = as_int(row[IDX_3B_V])
        hr = as_int(row[IDX_HR_V])
        bb = as_int(row[IDX_BB_V])
        hbp = as_int(row[IDX_HBP_V])
        sf = as_int(row[IDX_SF_V])
    else:
        ab = as_int(row[IDX_AB_H])
        hits = as_int(row[IDX_H_H])
        doubles = as_int(row[IDX_2B_H])
        triples = as_int(row[IDX_3B_H])
        hr = as_int(row[IDX_HR_H])
        bb = as_int(row[IDX_BB_H])
        hbp = as_int(row[IDX_HBP_H])
        sf = as_int(row[IDX_SF_H])

    singles = max(0, hits - doubles - triples - hr)
    total_bases = singles + (2 * doubles) + (3 * triples) + (4 * hr)

    return {
        "ab": ab,
        "hits": hits,
        "doubles": doubles,
        "triples": triples,
        "hr": hr,
        "bb": bb,
        "hbp": hbp,
        "sf": sf,
        "total_bases": total_bases,
    }

def rate_from_history(history):
    if not history:
        return {
            "games": 0,
            "runsForPerGame": None,
            "runsAllowedPerGame": None,
            "avg": None,
            "obp": None,
            "slg": None,
        }

    games = len(history)
    rf = sum(x["runs_for"] for x in history)
    ra = sum(x["runs_allowed"] for x in history)
    ab = sum(x["ab"] for x in history)
    hits = sum(x["hits"] for x in history)
    bb = sum(x["bb"] for x in history)
    hbp = sum(x["hbp"] for x in history)
    sf = sum(x["sf"] for x in history)
    tb = sum(x["total_bases"] for x in history)

    avg = (hits / ab) if ab else None
    obp_den = ab + bb + hbp + sf
    obp = ((hits + bb + hbp) / obp_den) if obp_den else None
    slg = (tb / ab) if ab else None

    def r(v):
        return round(v, 4) if v is not None else None

    return {
        "games": games,
        "runsForPerGame": r(rf / games),
        "runsAllowedPerGame": r(ra / games),
        "avg": r(avg),
        "obp": r(obp),
        "slg": r(slg),
    }

def parse_games(files):
    games = []
    bad_rows = 0

    for path in files:
        year_match = re.search(r"gl(\d{4})\.txt$", path.name.lower())
        season = int(year_match.group(1)) if year_match else None

        with path.open("r", encoding="latin-1", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 161:
                    bad_rows += 1
                    continue

                date = as_int(row[IDX_DATE])
                dbl = as_int(row[IDX_DBLHEADER])
                away = as_str(row, IDX_TEAM_V)
                home = as_str(row, IDX_TEAM_H)
                runs_away = as_int(row[IDX_RUNS_V])
                runs_home = as_int(row[IDX_RUNS_H])

                games.append({
                    "date": date,
                    "dateDbl": int(f"{date}{dbl}"),
                    "season": season,
                    "away": away,
                    "home": home,
                    "runsAway": runs_away,
                    "runsHome": runs_home,
                    "runTotal": runs_away + runs_home,
                    "homeVictory": 1 if runs_home > runs_away else 0,
                    "dayNight": as_str(row, IDX_DAY_NIGHT),
                    "ballpark": as_str(row, IDX_BALLPARK),
                    "awayStats": team_side_stats(row, "v"),
                    "homeStats": team_side_stats(row, "h"),
                })

    games.sort(key=lambda x: (x["date"], x["dateDbl"], x["away"], x["home"]))
    return games, bad_rows

def build_feature_preview(games, limit=25):
    """
    Build a small BaseballPred-style preview:
    For each game, calculate each team's rolling 162-game stats BEFORE current game.
    This is only a preview, not the production model dataset yet.
    """
    team_hist = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW))
    rows = []

    for g in games:
        away_hist = list(team_hist[g["away"]])
        home_hist = list(team_hist[g["home"]])

        away_roll = rate_from_history(away_hist)
        home_roll = rate_from_history(home_hist)

        if len(rows) < limit and away_roll["games"] >= 20 and home_roll["games"] >= 20:
            rows.append({
                "date": g["date"],
                "season": g["season"],
                "away": g["away"],
                "home": g["home"],
                "runsAway": g["runsAway"],
                "runsHome": g["runsHome"],
                "homeVictory": g["homeVictory"],
                "runTotal": g["runTotal"],
                "awayRolling162": away_roll,
                "homeRolling162": home_roll,
                "featureMeaning": "Rolling stats use only games before current game.",
            })

        away_result = {
            "runs_for": g["runsAway"],
            "runs_allowed": g["runsHome"],
            **g["awayStats"],
        }
        home_result = {
            "runs_for": g["runsHome"],
            "runs_allowed": g["runsAway"],
            **g["homeStats"],
        }

        team_hist[g["away"]].append(away_result)
        team_hist[g["home"]].append(home_result)

    return rows

def main():
    generated = datetime.now(ET).isoformat()
    folder = get_gamelog_dir()
    files = list_gamelog_files(folder)

    parsed_games = []
    bad_rows = 0
    preview = []

    if files:
        parsed_games, bad_rows = parse_games(files)
        preview = build_feature_preview(parsed_games)
        OUT_FEATURE_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
        OUT_FEATURE_PREVIEW.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")

    seasons = sorted(set(g["season"] for g in parsed_games if g.get("season"))) if parsed_games else []
    home_win_rate = None
    avg_total = None

    if parsed_games:
        home_win_rate = round(sum(g["homeVictory"] for g in parsed_games) / len(parsed_games), 4)
        avg_total = round(sum(g["runTotal"] for g in parsed_games) / len(parsed_games), 4)

    result = {
        "generatedAt": generated,
        "rules": {
            "mode": "sidecar audit only",
            "doesNotTouch": ["live bot", "Telegram sends", "official picks", "public board", "odds scans"],
            "baseballPredGoal": "Retrosheet 1980+ game logs -> rolling 162-game team features -> historical model training later",
        },
        "paths": {
            "gamelogDir": str(folder),
            "expectedPattern": "gl1980.txt, gl1981.txt, ...",
            "featurePreview": str(OUT_FEATURE_PREVIEW),
        },
        "counts": {
            "gamelogFiles": len(files),
            "gamesParsed": len(parsed_games),
            "badRows": bad_rows,
            "featurePreviewRows": len(preview),
        },
        "summary": {
            "firstSeason": seasons[0] if seasons else None,
            "lastSeason": seasons[-1] if seasons else None,
            "homeWinRate": home_win_rate,
            "avgRunTotal": avg_total,
        },
        "nextSteps": [
            "Download Retrosheet game logs and place them in the gamelogDir.",
            "Run this audit again.",
            "If gamesParsed is large, create 123_retrosheet_rolling_162_features.py to build full feature CSV.",
            "Train 124 only after validating no leakage.",
        ],
        "preview": preview[:5],
    }

    LATEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 122 RETROSHEET BASEBALLPRED SIDECAR AUDIT",
        "=" * 70,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Sidecar audit only.",
        "- Does not touch current live bot.",
        "- Does not send Telegram.",
        "- Does not create picks.",
        "- Goal: Retrosheet 1980+ -> rolling 162-game features -> future model.",
        "",
        f"Retrosheet folder: {folder}",
        f"Game log files found: {len(files)}",
        f"Games parsed: {len(parsed_games)}",
        f"Bad rows: {bad_rows}",
        f"Feature preview rows: {len(preview)}",
        "",
        "Summary:",
        f"- First season: {seasons[0] if seasons else 'N/A'}",
        f"- Last season: {seasons[-1] if seasons else 'N/A'}",
        f"- Home win rate: {home_win_rate if home_win_rate is not None else 'N/A'}",
        f"- Avg run total: {avg_total if avg_total is not None else 'N/A'}",
        "",
    ]

    if not files:
        lines += [
            "Status: NO RETROSHEET FILES FOUND",
            "",
            "Put Retrosheet game logs here:",
            str(folder),
            "",
            "Expected examples:",
            "- gl1980.txt",
            "- gl1981.txt",
            "- gl2022.txt",
            "",
            "Or set:",
            "$env:ASTRODDS_RETROSHEET_GAMELOG_DIR='C:\\path\\to\\retrosheet\\gamelogs'",
        ]
    else:
        lines += [
            "Files loaded:",
            *[f"- {p.name}" for p in files[:20]],
            "",
            "Preview:",
        ]
        for row in preview[:5]:
            lines.append(
                f"- {row['date']} {row['away']} @ {row['home']} | "
                f"awayRF162={row['awayRolling162']['runsForPerGame']} "
                f"homeRF162={row['homeRolling162']['runsForPerGame']} "
                f"homeWin={row['homeVictory']}"
            )

    lines += [
        "",
        f"JSON: {LATEST_JSON}",
        f"Feature preview: {OUT_FEATURE_PREVIEW}",
        "",
        "Rule: historical sidecar only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
