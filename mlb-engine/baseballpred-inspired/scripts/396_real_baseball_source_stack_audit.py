from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, json, re, subprocess, sys, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_JSON = ASTRO / "ASTRODDS-396-real-baseball-source-stack-audit-latest.json"
REPORT = REPORTS / "396_real_baseball_source_stack_audit_report.txt"

FOCUS_TEAMS = [
    "Cleveland Guardians",
    "Los Angeles Angels",
    "Chicago White Sox",
    "San Francisco Giants",
    "Baltimore Orioles",
    "St. Louis Cardinals",
    "Kansas City Royals",
    "Athletics",
]

EXPECTED_SOURCE_SCRIPTS = [
    "379_fetch_true_xfip_fangraphs_pybaseball.py",
    "380_fetch_team_platoon_statcast_pybaseball.py",
    "381_fetch_true_leverage_fangraphs_pybaseball.py",
    "382_run_real_baseballpred_data_acquisition.ps1",
    "383_real_premium_source_acquisition_report.ps1",
]

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def read_csv(path, max_rows=5000):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel
            rows = []
            for i, row in enumerate(csv.DictReader(f, dialect=dialect)):
                if i >= max_rows:
                    break
                rows.append({str(k or "").strip(): v for k,v in row.items()})
            return rows
    except Exception:
        return []

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def fnum(v):
    try:
        if v is None:
            return None
        s = str(v).replace(",", ".").replace("%","").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None

def check_pybaseball():
    try:
        p = subprocess.run([sys.executable, "-c", "import pybaseball; print('pybaseball OK', getattr(pybaseball, '__version__', 'unknown'))"], capture_output=True, text=True, timeout=20)
        return {"ok": p.returncode == 0, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}

def fetch_schedule():
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"
    games = []
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for d in data.get("dates", []):
            for g in d.get("games", []):
                teams = g.get("teams", {})
                away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
                home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
                if away and home:
                    status = (g.get("status") or {}).get("detailedState", "") or (g.get("status") or {}).get("abstractGameState", "")
                    games.append({"game": f"{away} @ {home}", "awayTeam": away, "homeTeam": home, "status": status, "gamePk": g.get("gamePk", "")})
    except Exception as e:
        return today, [], str(e)
    return today, games, ""

def find_candidate_source_files():
    terms = [
        "xfip", "fangraphs", "platoon", "statcast", "leverage", "retrosheet",
        "premium", "source", "baseline", "model", "fair", "context"
    ]
    files = []
    for p in ASTRO.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in [".csv", ".json", ".txt"]:
            continue
        name = norm(p.name)
        if any(t in name for t in terms):
            files.append(p)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:80]

def inspect_file(path, official_teams):
    info = {
        "file": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else "",
        "rows": None,
        "columns": [],
        "focusTeamHits": [],
        "officialTeamHits": [],
        "looksEmpty": True,
        "sample": {},
    }
    if not path.exists() or path.stat().st_size == 0:
        return info

    text = ""
    if path.suffix.lower() == ".csv":
        rows = read_csv(path, max_rows=200)
        info["rows"] = len(rows)
        if rows:
            info["columns"] = list(rows[0].keys())
            info["sample"] = {k:v for k,v in rows[0].items() if str(v).strip() != ""} if rows[0] else {}
            text = " ".join(" ".join(str(v) for v in r.values()) for r in rows[:200])
    elif path.suffix.lower() == ".json":
        data = load_json(path)
        text = json.dumps(data)[:200000]
        if isinstance(data, dict):
            info["columns"] = list(data.keys())[:80]
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:200000]
        except Exception:
            text = ""

    nt = norm(text)
    info["focusTeamHits"] = [t for t in FOCUS_TEAMS if norm(t) in nt]
    info["officialTeamHits"] = [t for t in official_teams if norm(t) in nt]
    info["looksEmpty"] = len(nt) < 50 or ("no data" in nt and len(info["focusTeamHits"]) == 0)
    return info

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    schedule_date, games, schedule_error = fetch_schedule()
    official_teams = []
    for g in games:
        official_teams.extend([g["awayTeam"], g["homeTeam"]])
    official_teams = sorted(set(official_teams))

    pybaseball_status = check_pybaseball()
    source_scripts = [{"script": str(SCRIPTS / s), "exists": (SCRIPTS / s).exists()} for s in EXPECTED_SOURCE_SCRIPTS]

    candidates = find_candidate_source_files()
    inspected = [inspect_file(p, official_teams) for p in candidates]

    # Existing current board health.
    money_board = load_json(ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json")
    rows = money_board.get("moneylineBoard", []) if isinstance(money_board, dict) else []
    rows_with_price = sum(1 for r in rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in rows if fnum(r.get("currentEdgePct")) is not None)

    # Determine root gap.
    data_source_hits = [x for x in inspected if x["focusTeamHits"] or x["officialTeamHits"]]
    if not pybaseball_status["ok"]:
        decision = "PYBASEBALL_NOT_READY"
    elif not data_source_hits:
        decision = "REAL_BASEBALL_DATA_NOT_CONNECTED"
    elif rows_with_model < len(rows):
        decision = "MODEL_FEATURES_NOT_FULLY_JOINED"
    elif rows_with_price < len(rows):
        decision = "MARKET_PM_PRICE_NOT_FULLY_JOINED"
    else:
        decision = "SOURCE_STACK_OK"

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scheduleDateET": schedule_date,
        "scheduleError": schedule_error,
        "officialGames": games,
        "officialTeams": official_teams,
        "pybaseball": pybaseball_status,
        "sourceScripts": source_scripts,
        "candidateFilesInspected": inspected,
        "currentBoard": {
            "rows": len(rows),
            "rowsWithPrice": rows_with_price,
            "rowsWithModel": rows_with_model,
            "rowsWithEdge": rows_with_edge,
        },
        "rule": "MLB StatsAPI = schedule/status. FanGraphs/Retrosheet/pybaseball = model/fair features. Market source = PM price.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 396 REAL BASEBALL SOURCE STACK AUDIT",
        "=" * 82,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision: {decision}",
        f"Schedule date ET: {schedule_date}",
        f"Official games: {len(games)}",
        f"Schedule error: {schedule_error or 'none'}",
        "",
        "Current Moneyline Board:",
        f"- rows: {len(rows)}",
        f"- rowsWithPrice: {rows_with_price}",
        f"- rowsWithModel: {rows_with_model}",
        f"- rowsWithEdge: {rows_with_edge}",
        "",
        "PyBaseball:",
        f"- ok: {pybaseball_status['ok']}",
        f"- stdout: {pybaseball_status['stdout']}",
        f"- stderr: {pybaseball_status['stderr']}",
        "",
        "Expected source scripts:",
    ]
    for s in source_scripts:
        lines.append(f"- {'OK' if s['exists'] else 'MISSING'} | {s['script']}")

    lines += ["", "Candidate data files with team hits:"]
    hit_count = 0
    for item in inspected:
        if item["focusTeamHits"] or item["officialTeamHits"]:
            hit_count += 1
            lines.append(f"- {Path(item['file']).name} | rows={item['rows']} | focusHits={item['focusTeamHits']} | officialHits={item['officialTeamHits'][:8]} | modified={item['modified']}")
            lines.append(f"  columns={item['columns'][:30]}")
            if item["sample"]:
                lines.append(f"  sample={json.dumps(item['sample'], ensure_ascii=False)[:800]}")
    if hit_count == 0:
        lines.append("- none")

    lines += [
        "",
        "Interpretation:",
        "- If PYBASEBALL_NOT_READY: install/fix pybaseball first.",
        "- If REAL_BASEBALL_DATA_NOT_CONNECTED: run source acquisition and verify non-empty CSVs.",
        "- If MODEL_FEATURES_NOT_FULLY_JOINED: data exists but is not being used in fair/modelProbability.",
        "- If MARKET_PM_PRICE_NOT_FULLY_JOINED: model is OK, but prices/PM are still missing.",
        "",
        f"JSON: {OUT_JSON}",
        "Rule: Do not replace MLB schedule; connect FanGraphs/Retrosheet to Fair/model and market source to PM.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
