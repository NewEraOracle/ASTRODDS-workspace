from pathlib import Path
import csv
import json
import urllib.request
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

INPUT = ROOT / ".astrodds" / "VVS-game-context-latest.json"
OUT_JSON = ROOT / ".astrodds" / "VVS-pitcher-context-latest.json"
OUT_CSV = ROOT / ".astrodds" / "VVS-pitcher-context-latest.csv"
REPORT = BASE / "reports" / "09_pitcher_context_snapshot_report.txt"

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def get_url_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def nested(obj, path, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def get_game_feed(game_pk):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    return get_url_json(url)

def extract_probable_pitcher(feed, side):
    pitcher = nested(feed, ["gameData", "probablePitchers", side], {})
    if not isinstance(pitcher, dict):
        return None, None
    return pitcher.get("id"), pitcher.get("fullName")

def fetch_pitcher_season_stats(person_id):
    if not person_id:
        return None

    query = urlencode({
        "hydrate": "stats(group=[pitching],type=[season],sportId=1)"
    })

    url = f"https://statsapi.mlb.com/api/v1/people/{person_id}?{query}"

    try:
        data = get_url_json(url)
    except Exception as e:
        return {"statsError": str(e)}

    people = data.get("people", [])
    if not people:
        return {"statsError": "person_not_found"}

    person = people[0]
    stats_blocks = person.get("stats", [])

    for block in stats_blocks:
        splits = block.get("splits", [])
        if not splits:
            continue

        stat = splits[0].get("stat", {})

        return {
            "pitcherId": person_id,
            "pitcherName": person.get("fullName"),
            "era": stat.get("era"),
            "whip": stat.get("whip"),
            "inningsPitched": stat.get("inningsPitched"),
            "gamesStarted": stat.get("gamesStarted"),
            "gamesPitched": stat.get("gamesPitched"),
            "wins": stat.get("wins"),
            "losses": stat.get("losses"),
            "strikeOuts": stat.get("strikeOuts"),
            "baseOnBalls": stat.get("baseOnBalls"),
            "hits": stat.get("hits"),
            "earnedRuns": stat.get("earnedRuns"),
            "homeRuns": stat.get("homeRuns"),
            "battersFaced": stat.get("battersFaced"),
            "avg": stat.get("avg"),
        }

    return {
        "pitcherId": person_id,
        "pitcherName": person.get("fullName"),
        "statsError": "no_pitching_season_split",
    }

def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except Exception:
        return None

def pitcher_flags(prefix, stats):
    flags = []

    if not stats or stats.get("statsError"):
        flags.append(f"{prefix}_stats_missing")
        return flags

    era = to_float(stats.get("era"))
    whip = to_float(stats.get("whip"))
    gs = to_float(stats.get("gamesStarted"))
    ip = to_float(stats.get("inningsPitched"))

    if gs is not None and gs < 3:
        flags.append(f"{prefix}_low_start_sample")

    if ip is not None and ip < 20:
        flags.append(f"{prefix}_low_ip_sample")

    if era is not None and era >= 5.00:
        flags.append(f"{prefix}_high_era")

    if whip is not None and whip >= 1.45:
        flags.append(f"{prefix}_high_whip")

    return flags

def add_prefixed_stats(row, prefix, stats):
    if not stats:
        row[f"{prefix}PitcherStatsStatus"] = "missing"
        return

    if stats.get("statsError"):
        row[f"{prefix}PitcherStatsStatus"] = "error"
        row[f"{prefix}PitcherStatsError"] = stats.get("statsError")
        return

    row[f"{prefix}PitcherStatsStatus"] = "available"
    for key, value in stats.items():
        row[f"{prefix}Pitcher_{key}"] = value

def main():
    rows = read_json(INPUT)
    output = []
    errors = []

    for row in rows:
        out = dict(row)
        game_pk = out.get("gamePk")

        try:
            feed = get_game_feed(game_pk)
        except Exception as e:
            out["pitcherContextStatus"] = "feed_failed"
            out["pitcherContextError"] = str(e)
            errors.append(f"{game_pk}: {e}")
            output.append(out)
            continue

        away_id, away_name = extract_probable_pitcher(feed, "away")
        home_id, home_name = extract_probable_pitcher(feed, "home")

        out["awayProbablePitcherId"] = away_id
        out["homeProbablePitcherId"] = home_id
        out["awayProbablePitcher"] = away_name or out.get("awayProbablePitcher")
        out["homeProbablePitcher"] = home_name or out.get("homeProbablePitcher")

        away_stats = fetch_pitcher_season_stats(away_id)
        home_stats = fetch_pitcher_season_stats(home_id)

        add_prefixed_stats(out, "away", away_stats)
        add_prefixed_stats(out, "home", home_stats)

        flags = []
        flags.extend(pitcher_flags("away_pitcher", away_stats))
        flags.extend(pitcher_flags("home_pitcher", home_stats))

        out["pitcherContextFlags"] = "|".join(flags) if flags else "none"
        out["pitcherContextStatus"] = "ok"

        output.append(out)

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    fieldnames = sorted({key for row in output for key in row.keys()})

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    lines = []
    lines.append("ASTRODDS 09 PITCHER CONTEXT SNAPSHOT REPORT")
    lines.append("=" * 46)
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Output rows: {len(output)}")
    lines.append("")
    lines.append("Pitcher context:")

    for row in output:
        lines.append(
            f"- {row.get('game')} | Pick: {row.get('pick')} | "
            f"Away SP: {row.get('awayProbablePitcher')} "
            f"ERA={row.get('awayPitcher_era', '-')} WHIP={row.get('awayPitcher_whip', '-')} | "
            f"Home SP: {row.get('homeProbablePitcher')} "
            f"ERA={row.get('homePitcher_era', '-')} WHIP={row.get('homePitcher_whip', '-')} | "
            f"Flags: {row.get('pitcherContextFlags')}"
        )

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append("Important:")
    lines.append("Pitcher context is informational only. It does not change VVS picks yet.")
    lines.append("")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
