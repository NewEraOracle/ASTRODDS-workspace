# -*- coding: utf-8 -*-
"""
ASTRODDS 110 - Lineup + Pitcher Live Context Audit

Audit-only module:
- Reads .astrodds/ASTRODDS-mlb-gamepk-map-latest.json
- Pulls MLB StatsAPI live feed for probable pitchers and lineups
- Produces a report and JSON context file
- Never sends Telegram
- Never changes public signals
- Missing data becomes warning/neutral only
"""

from pathlib import Path
from datetime import datetime
import json
import urllib.request
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

GAMEPK_MAP = ROOT / ".astrodds" / "ASTRODDS-mlb-gamepk-map-latest.json"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-lineup-pitcher-live-context-latest.json"
REPORT = BASE / "reports" / "110_lineup_pitcher_live_context_audit_report.txt"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: int = 35) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def norm_name(value: object) -> str:
    raw = str(value or "").strip().lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return raw.replace(".", "").replace("-", " ").replace("  ", " ")


def get_probable(feed: dict, side: str) -> str | None:
    probable = ((feed.get("gameData") or {}).get("probablePitchers") or {}).get(side) or {}
    return probable.get("fullName") or probable.get("name")


def lineup_count(feed: dict, side: str) -> int:
    team = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}).get(side) or {}
    batters = team.get("batters") or []
    return len(batters)


def lineup_names(feed: dict, side: str) -> list[str]:
    team = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}).get(side) or {}
    batters = team.get("batters") or []
    players = team.get("players") or {}

    names = []
    for player_id in batters:
        player = players.get(f"ID{player_id}") or {}
        person = player.get("person") or {}
        name = person.get("fullName") or person.get("name")
        if name:
            names.append(name)

    return names[:12]


def lineup_status(count: int) -> str:
    if count >= 9:
        return "confirmed"
    if count > 0:
        return "partial"
    return "missing"


def classify_live_context(game: dict, feed: dict) -> dict:
    status = ((feed.get("gameData") or {}).get("status") or {})
    detailed_state = status.get("detailedState")
    abstract_state = status.get("abstractGameState")

    away_sp_feed = get_probable(feed, "away")
    home_sp_feed = get_probable(feed, "home")

    away_sp_map = game.get("awayProbablePitcher")
    home_sp_map = game.get("homeProbablePitcher")

    away_count = lineup_count(feed, "away")
    home_count = lineup_count(feed, "home")

    away_status = lineup_status(away_count)
    home_status = lineup_status(home_count)

    warnings = []

    if not away_sp_feed and not away_sp_map:
        warnings.append("away_pitcher_missing")
    if not home_sp_feed and not home_sp_map:
        warnings.append("home_pitcher_missing")

    if away_sp_feed and away_sp_map and norm_name(away_sp_feed) != norm_name(away_sp_map):
        warnings.append("away_pitcher_changed_or_mismatch")
    if home_sp_feed and home_sp_map and norm_name(home_sp_feed) != norm_name(home_sp_map):
        warnings.append("home_pitcher_changed_or_mismatch")

    if away_status != "confirmed":
        warnings.append(f"away_lineup_{away_status}")
    if home_status != "confirmed":
        warnings.append(f"home_lineup_{home_status}")

    state_text = f"{abstract_state or ''} {detailed_state or ''}".lower()
    if "final" in state_text or "in progress" in state_text or "live" in state_text:
        warnings.append("game_not_clean_pregame")

    impact = "CLEAN"
    confidence = "medium"

    if any("pitcher_changed" in warning for warning in warnings):
        impact = "DOWNGRADE"
        confidence = "low"
    elif any("lineup_" in warning for warning in warnings):
        impact = "WARNING"
        confidence = "low"
    elif warnings:
        impact = "WARNING"

    return {
        "abstractState": abstract_state,
        "detailedState": detailed_state,
        "awayProbablePitcherMap": away_sp_map,
        "homeProbablePitcherMap": home_sp_map,
        "awayProbablePitcherFeed": away_sp_feed,
        "homeProbablePitcherFeed": home_sp_feed,
        "awayLineupStatus": away_status,
        "homeLineupStatus": home_status,
        "awayBattersCount": away_count,
        "homeBattersCount": home_count,
        "awayBatters": lineup_names(feed, "away"),
        "homeBatters": lineup_names(feed, "home"),
        "impact": impact,
        "confidence": confidence,
        "warnings": warnings,
    }


def main() -> None:
    generated_at = datetime.utcnow().isoformat() + "Z"

    mapping = read_json(GAMEPK_MAP)
    games = mapping.get("games") or []

    contexts = []

    for game in games:
        game_pk = game.get("gamePk")

        if not game_pk:
            contexts.append({
                "oddsGameId": game.get("oddsGameId"),
                "gamePk": None,
                "date": game.get("commenceTime"),
                "awayTeam": game.get("awayTeam"),
                "homeTeam": game.get("homeTeam"),
                "game": game.get("game"),
                "status": "unavailable",
                "context": {
                    "impact": "NEUTRAL",
                    "confidence": "low",
                    "warnings": ["missing_gamePk"],
                },
            })
            continue

        try:
            feed = fetch_json(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")
            context = classify_live_context(game, feed)
            status = "available"
        except Exception as exc:
            context = {
                "impact": "NEUTRAL",
                "confidence": "low",
                "warnings": [f"live_feed_unavailable:{type(exc).__name__}"],
            }
            status = "unavailable"

        contexts.append({
            "oddsGameId": game.get("oddsGameId"),
            "gamePk": game_pk,
            "date": game.get("commenceTime"),
            "awayTeam": game.get("awayTeam"),
            "homeTeam": game.get("homeTeam"),
            "game": game.get("game"),
            "status": status,
            "context": context,
        })

    counts = {
        "gamesChecked": len(contexts),
        "feedAvailable": len([x for x in contexts if x["status"] == "available"]),
        "feedUnavailable": len([x for x in contexts if x["status"] != "available"]),
        "bothLineupsConfirmed": len([
            x for x in contexts
            if x["context"].get("awayLineupStatus") == "confirmed"
            and x["context"].get("homeLineupStatus") == "confirmed"
        ]),
        "lineupWarnings": len([
            x for x in contexts
            if "lineup" in "|".join(x["context"].get("warnings") or [])
        ]),
        "pitcherWarnings": len([
            x for x in contexts
            if "pitcher" in "|".join(x["context"].get("warnings") or [])
        ]),
        "downgrades": len([x for x in contexts if x["context"].get("impact") == "DOWNGRADE"]),
        "warnings": len([x for x in contexts if x["context"].get("impact") == "WARNING"]),
        "clean": len([x for x in contexts if x["context"].get("impact") == "CLEAN"]),
        "neutral": len([x for x in contexts if x["context"].get("impact") == "NEUTRAL"]),
    }

    output = {
        "generatedAt": generated_at,
        "mode": "audit_only",
        "rules": {
            "source": "MLB StatsAPI game feed/live via mapped gamePk",
            "noTelegram": True,
            "noPublicSignal": True,
            "failSafe": "If live feed, pitcher, or lineup is unavailable, context becomes warning/neutral. No pick is created.",
        },
        "counts": counts,
        "contexts": contexts,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 110 LINEUP + PITCHER LIVE CONTEXT AUDIT",
        "=" * 68,
        f"Generated UTC: {generated_at}",
        "",
        "Rules:",
        "- Audit only.",
        "- No Telegram send.",
        "- No public signal change.",
        "- Missing live data creates warning/neutral, never fake signal.",
        "",
        "Counts:",
    ]

    for key, value in counts.items():
        lines.append(f"- {key}: {value}")

    lines += ["", "Live contexts:"]

    if not contexts:
        lines.append("- none")
    else:
        for row in contexts[:20]:
            ctx = row["context"]
            lines.append(
                f"- {row.get('game')} | gamePk={row.get('gamePk')} | "
                f"State={ctx.get('detailedState', '-')} | "
                f"AwaySP={ctx.get('awayProbablePitcherFeed') or ctx.get('awayProbablePitcherMap') or '-'} | "
                f"HomeSP={ctx.get('homeProbablePitcherFeed') or ctx.get('homeProbablePitcherMap') or '-'} | "
                f"Lineups={ctx.get('awayLineupStatus', '-')}/{ctx.get('homeLineupStatus', '-')} | "
                f"Batters={ctx.get('awayBattersCount', '-')}/{ctx.get('homeBattersCount', '-')} | "
                f"Impact={ctx.get('impact')} | Confidence={ctx.get('confidence')} | "
                f"Warnings={','.join(ctx.get('warnings') or []) or 'none'}"
            )

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: context audit only. Paper/manual only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
