# -*- coding: utf-8 -*-
"""
ASTRODDS 119 - Resolve Verified + O/U Results

Purpose:
- Resolve pending Official Telegram A+ moneyline results.
- Resolve pending O/U Paper Test results.
- Update both ledgers and regenerate both public result pages.
- Does NOT send Telegram.
- Does NOT create picks.
"""

from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse
import re
import html

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

OFFICIAL_LEDGER = ROOT / ".astrodds" / "telegram-verified-signal-ledger.json"
OU_LEDGER = ROOT / ".astrodds" / "ou-paper-test-ledger.json"

OFFICIAL_JSON = ROOT / "public" / "astrodds-verified-telegram-results.json"
OFFICIAL_HTML = ROOT / "public" / "astrodds-verified-telegram-results.html"
OU_JSON = ROOT / "public" / "astrodds-ou-paper-test-results.json"
OU_HTML = ROOT / "public" / "astrodds-ou-paper-test-results.html"

REPORT = BASE / "reports" / "119_resolve_verified_and_ou_results_report.txt"
ET = ZoneInfo("America/Toronto")

TEAM_ALIASES = {
    "Athletics": ["Athletics", "Oakland Athletics"],
    "Arizona Diamondbacks": ["Arizona Diamondbacks"],
    "Atlanta Braves": ["Atlanta Braves"],
    "Baltimore Orioles": ["Baltimore Orioles"],
    "Boston Red Sox": ["Boston Red Sox"],
    "Chicago Cubs": ["Chicago Cubs"],
    "Chicago White Sox": ["Chicago White Sox"],
    "Cincinnati Reds": ["Cincinnati Reds"],
    "Cleveland Guardians": ["Cleveland Guardians"],
    "Colorado Rockies": ["Colorado Rockies"],
    "Detroit Tigers": ["Detroit Tigers"],
    "Houston Astros": ["Houston Astros"],
    "Kansas City Royals": ["Kansas City Royals"],
    "Los Angeles Angels": ["Los Angeles Angels"],
    "Los Angeles Dodgers": ["Los Angeles Dodgers"],
    "Miami Marlins": ["Miami Marlins"],
    "Milwaukee Brewers": ["Milwaukee Brewers"],
    "Minnesota Twins": ["Minnesota Twins"],
    "New York Mets": ["New York Mets"],
    "New York Yankees": ["New York Yankees"],
    "Philadelphia Phillies": ["Philadelphia Phillies"],
    "Pittsburgh Pirates": ["Pittsburgh Pirates"],
    "San Diego Padres": ["San Diego Padres"],
    "San Francisco Giants": ["San Francisco Giants"],
    "Seattle Mariners": ["Seattle Mariners"],
    "St. Louis Cardinals": ["St. Louis Cardinals"],
    "Tampa Bay Rays": ["Tampa Bay Rays"],
    "Texas Rangers": ["Texas Rangers"],
    "Toronto Blue Jays": ["Toronto Blue Jays"],
    "Washington Nationals": ["Washington Nationals"],
}

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_json(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

def canonical_team(name):
    n = norm(name)
    for canon, vals in TEAM_ALIASES.items():
        if n in [norm(v) for v in vals]:
            return canon
    return str(name or "")

def contains_team(text, team):
    t = norm(text)
    vals = TEAM_ALIASES.get(team, [team])
    return any(norm(v) in t for v in vals)

def signal_local_date(value):
    if not value:
        return None
    raw = str(value)
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ET).date().isoformat()
        return raw[:10]
    except Exception:
        return raw[:10]

def fetch_schedule(date_key):
    params = urllib.parse.urlencode({
        "sportId": 1,
        "date": date_key,
        "hydrate": "team,linescore"
    })
    return fetch_json(f"https://statsapi.mlb.com/api/v1/schedule?{params}")

def build_schedule_cache(dates):
    out = {}
    for d in sorted([x for x in set(dates) if x]):
        try:
            out[d] = fetch_schedule(d)
        except Exception as e:
            out[d] = {"error": str(e), "dates": []}
    return out

def find_game_for_signal(signal, schedules):
    date_key = signal_local_date(signal.get("date") or signal.get("signalDate"))
    schedule = schedules.get(date_key) or {}
    target_text = f"{signal.get('game') or ''} {signal.get('market') or ''}"

    for block in schedule.get("dates", []):
        for g in block.get("games", []):
            teams = g.get("teams") or {}
            away_team = canonical_team(((teams.get("away") or {}).get("team") or {}).get("name"))
            home_team = canonical_team(((teams.get("home") or {}).get("team") or {}).get("name"))

            if contains_team(target_text, away_team) and contains_team(target_text, home_team):
                return g

    return None

def score_from_game(g):
    teams = g.get("teams") or {}
    away = teams.get("away") or {}
    home = teams.get("home") or {}
    return {
        "awayTeam": canonical_team(((away.get("team") or {}).get("name"))),
        "homeTeam": canonical_team(((home.get("team") or {}).get("name"))),
        "awayScore": away.get("score"),
        "homeScore": home.get("score"),
        "state": ((g.get("status") or {}).get("abstractGameState")),
        "detailedState": ((g.get("status") or {}).get("detailedState")),
        "gamePk": g.get("gamePk"),
    }

def is_final(score):
    return str(score.get("state") or "").lower() == "final" or "final" in str(score.get("detailedState") or "").lower()

def resolve_moneyline(signal, score):
    if not is_final(score):
        return None

    away_score = int(score.get("awayScore") or 0)
    home_score = int(score.get("homeScore") or 0)
    winner = score["awayTeam"] if away_score > home_score else score["homeTeam"]
    pick = str(signal.get("pick") or "")

    result = "WIN" if contains_team(pick, winner) else "LOSS"

    return {
        "result": result,
        "finalScore": f"{score['awayTeam']} {away_score} - {score['homeTeam']} {home_score}",
        "winner": winner,
        "resolvedAt": datetime.now(ET).isoformat(),
        "gamePk": score.get("gamePk"),
    }

def parse_ou_pick(signal):
    raw = str(signal.get("pick") or "")
    m = re.search(r"\b(over|under)\s*([0-9]+(?:\.[0-9]+)?)", raw, re.I)
    if not m:
        return None, None
    return m.group(1).lower(), float(m.group(2))

def resolve_ou(signal, score):
    if not is_final(score):
        return None

    side, line = parse_ou_pick(signal)
    if not side:
        return None

    away_score = int(score.get("awayScore") or 0)
    home_score = int(score.get("homeScore") or 0)
    total = away_score + home_score

    if total == line:
        result = "PUSH"
    elif side == "over":
        result = "WIN" if total > line else "LOSS"
    else:
        result = "WIN" if total < line else "LOSS"

    return {
        "result": result,
        "finalTotalRuns": total,
        "finalScore": f"{score['awayTeam']} {away_score} - {score['homeTeam']} {home_score}",
        "resolvedAt": datetime.now(ET).isoformat(),
        "gamePk": score.get("gamePk"),
    }

def money(v):
    try:
        n = float(v or 0)
        sign = "+" if n >= 0 else "-"
        return f"{sign}${abs(n):.2f}"
    except Exception:
        return "-"

def pct(v):
    try:
        return f"{float(v) * 100:.2f}%"
    except Exception:
        return "-"

def publish_official(ledger):
    signals = [
        s for s in ledger.get("signals", [])
        if s.get("telegramSent") and str(s.get("grade") or "").upper() in ["A+", "OFFICIAL", "A_PLUS"]
    ]
    signals.sort(key=lambda x: str(x.get("signalDate") or x.get("date") or ""), reverse=True)

    wins = [s for s in signals if s.get("result") == "WIN"]
    losses = [s for s in signals if s.get("result") == "LOSS"]
    pushes = [s for s in signals if s.get("result") == "PUSH"]
    pending = [s for s in signals if s.get("result") == "PENDING"]
    graded = len(wins) + len(losses)
    win_rate = len(wins) / graded if graded else 0.0
    profit = sum(float(s.get("profit") or 0) for s in wins)

    public = {
        "generatedAt": datetime.now(ET).isoformat(),
        "title": "ASTRODDS Verified Telegram Results",
        "rules": {
            "included": "Only verified Telegram A+/official signals.",
            "excluded": ["paper picks", "watchlist", "model-only", "non-Telegram value/action leans"]
        },
        "summary": {
            "record": f"{len(wins)}-{len(losses)}",
            "wins": len(wins),
            "losses": len(losses),
            "pushes": len(pushes),
            "pending": len(pending),
            "graded": graded,
            "winRate": round(win_rate, 4),
            "winRateLabel": f"{win_rate:.0%}" if graded else "N/A",
            "totalProfitTracked": round(profit, 2),
        },
        "signals": signals,
    }
    write_json(OFFICIAL_JSON, public)

    rows = []
    for s in signals:
        date = s.get("signalDate") or s.get("date") or "-"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(date))}</td>"
            f"<td>{html.escape(str(s.get('market') or s.get('game') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('pick') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('grade') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('result') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('finalScore') or '-'))}</td>"
            "</tr>"
        )

    OFFICIAL_HTML.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>ASTRODDS Verified Results</title>
<style>body{{font-family:Arial;margin:32px;background:#f8fafc;color:#101828}}.card{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:24px;max-width:1100px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}.metric{{background:#f1f5f9;border-radius:12px;padding:16px}}.value{{font-size:28px;font-weight:800}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left}}</style></head><body><div class="card">
<h1>ASTRODDS Verified Telegram Results</h1><p>Only Telegram A+ / official signals count.</p>
<div class="summary"><div class="metric">Record<div class="value">{public['summary']['record']}</div></div><div class="metric">Win Rate<div class="value">{public['summary']['winRateLabel']}</div></div><div class="metric">Verified<div class="value">{len(signals)}</div></div><div class="metric">Pending<div class="value">{len(pending)}</div></div></div>
<table><thead><tr><th>Date</th><th>Market</th><th>Pick</th><th>Grade</th><th>Result</th><th>Final</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>Generated: {html.escape(public['generatedAt'])}</p></div></body></html>""", encoding="utf-8")

    return public["summary"]

def publish_ou(ledger):
    signals = ledger.get("signals", [])
    signals.sort(key=lambda x: str(x.get("date") or ""), reverse=True)

    wins = [s for s in signals if s.get("result") == "WIN"]
    losses = [s for s in signals if s.get("result") == "LOSS"]
    pushes = [s for s in signals if s.get("result") == "PUSH"]
    pending = [s for s in signals if s.get("result") == "PENDING"]
    graded = len(wins) + len(losses)
    win_rate = len(wins) / graded if graded else 0.0

    public = {
        "generatedAt": datetime.now(ET).isoformat(),
        "title": "ASTRODDS Over/Under Paper Test Results",
        "rules": ledger.get("rules", {}),
        "summary": {
            "ouPaperSignals": len(signals),
            "record": f"{len(wins)}-{len(losses)}",
            "wins": len(wins),
            "losses": len(losses),
            "pushes": len(pushes),
            "pending": len(pending),
            "graded": graded,
            "winRate": round(win_rate, 4),
            "winRateLabel": f"{win_rate:.0%}" if graded else "N/A",
        },
        "signals": signals,
    }
    write_json(OU_JSON, public)

    rows = []
    for s in signals:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(s.get('date') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('game') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('pick') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('category') or '-'))}</td>"
            f"<td>{html.escape(pct(s.get('probabilityEdge')))}</td>"
            f"<td>{html.escape(str(s.get('result') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('finalScore') or '-'))}</td>"
            "</tr>"
        )

    OU_HTML.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>ASTRODDS O/U Paper Test</title>
<style>body{{font-family:Arial;margin:32px;background:#f8fafc;color:#101828}}.card{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:24px;max-width:1200px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}.metric{{background:#f1f5f9;border-radius:12px;padding:16px}}.value{{font-size:28px;font-weight:800}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left}}</style></head><body><div class="card">
<h1>ASTRODDS Over/Under Paper Test</h1><p>Separate paper-test record. Does not affect Telegram A+ record.</p>
<div class="summary"><div class="metric">Record<div class="value">{public['summary']['record']}</div></div><div class="metric">Win Rate<div class="value">{public['summary']['winRateLabel']}</div></div><div class="metric">Signals<div class="value">{len(signals)}</div></div><div class="metric">Pending<div class="value">{len(pending)}</div></div></div>
<table><thead><tr><th>Date</th><th>Game</th><th>Pick</th><th>Type</th><th>Edge</th><th>Result</th><th>Final</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>Generated: {html.escape(public['generatedAt'])}</p></div></body></html>""", encoding="utf-8")

    return public["summary"]

def main():
    generated = datetime.now(ET).isoformat()

    official = read_json(OFFICIAL_LEDGER, {"signals": []})
    ou = read_json(OU_LEDGER, {"signals": []})

    date_keys = []
    for s in official.get("signals", []):
        if s.get("result") == "PENDING":
            date_keys.append(signal_local_date(s.get("signalDate") or s.get("date")))
    for s in ou.get("signals", []):
        if s.get("result") == "PENDING":
            date_keys.append(signal_local_date(s.get("date")))

    schedules = build_schedule_cache(date_keys)

    official_updates = []
    ou_updates = []

    for s in official.get("signals", []):
        if s.get("result") != "PENDING":
            continue
        g = find_game_for_signal(s, schedules)
        if not g:
            continue
        score = score_from_game(g)
        resolved = resolve_moneyline(s, score)
        if resolved:
            s.update(resolved)
            official_updates.append(s)

    for s in ou.get("signals", []):
        if s.get("result") != "PENDING":
            continue
        g = find_game_for_signal(s, schedules)
        if not g:
            continue
        score = score_from_game(g)
        resolved = resolve_ou(s, score)
        if resolved:
            s.update(resolved)
            ou_updates.append(s)

    official["updatedAt"] = generated
    ou["updatedAt"] = generated
    write_json(OFFICIAL_LEDGER, official)
    write_json(OU_LEDGER, ou)

    official_summary = publish_official(official)
    ou_summary = publish_ou(ou)

    lines = [
        "ASTRODDS 119 RESOLVE VERIFIED + O/U RESULTS",
        "=" * 64,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Resolves only pending ledger entries.",
        "- Official page = Telegram A+/official only.",
        "- O/U page = separate paper-test only.",
        "- No Telegram send.",
        "",
        f"Official updates: {len(official_updates)}",
        f"O/U updates: {len(ou_updates)}",
        "",
        "Official summary:",
        f"- Record: {official_summary.get('record')}",
        f"- Win rate: {official_summary.get('winRateLabel')}",
        f"- Pending: {official_summary.get('pending')}",
        "",
        "O/U paper summary:",
        f"- Record: {ou_summary.get('record')}",
        f"- Win rate: {ou_summary.get('winRateLabel')}",
        f"- Pending: {ou_summary.get('pending')}",
        "",
        "Updated entries:",
    ]

    for s in official_updates:
        lines.append(f"- OFFICIAL | {s.get('market') or s.get('game')} | Pick={s.get('pick')} | Result={s.get('result')} | Final={s.get('finalScore')}")
    for s in ou_updates:
        lines.append(f"- O/U TEST | {s.get('game')} | Pick={s.get('pick')} | Result={s.get('result')} | Final={s.get('finalScore')} | Total={s.get('finalTotalRuns')}")

    lines += [
        "",
        f"Official JSON: {OFFICIAL_JSON}",
        f"Official HTML: {OFFICIAL_HTML}",
        f"O/U JSON: {OU_JSON}",
        f"O/U HTML: {OU_HTML}",
        "",
        "Rule: result resolver only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
