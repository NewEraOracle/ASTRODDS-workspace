from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, json, re, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

REPORT = REPORTS / "252_inspect_moneyline_source_columns_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-252-moneyline-source-column-inspection-latest.json"

SOURCES = [
    ASTRO / "ASTRODDS-289-best-price-line-shopping-latest.csv",
    ASTRO / "ASTRODDS-292-calibrated-candidate-board-latest.csv",
    ASTRO / "ASTRODDS-267-source-first-official-gate-latest.csv",
    ASTRO / "ASTRODDS-266-source-model-market-bridge-latest.csv",
    ASTRO / "ASTRODDS-255-schedule-first-full-slate-bridge-latest.csv",
    ASTRO / "ASTRODDS-273-market-moneyline-sources-latest.csv",
    ASTRO / "ASTRODDS-281-credit-aware-market-fetch-latest.csv",
    ASTRO / "ASTRODDS-299-safe-best-price-line-shopping-latest.csv",
]

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def fnum(v):
    try:
        s = str(v or "").strip().replace("%","").replace("$","").replace("+","").replace(",", ".")
        if not s:
            return None
        return float(s)
    except Exception:
        return None

def read_csv(path):
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
            return [{str(k or "").strip(): v for k,v in row.items()} for row in csv.DictReader(f, dialect=dialect)]
    except Exception:
        return []

def fetch_schedule():
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            teams = g.get("teams", {})
            away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
            home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
            if away and home:
                games.append(f"{away} @ {home}")
    return today, games

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    date, official_games = fetch_schedule()
    game_terms = []
    for g in official_games:
        if " @ " in g:
            a,h = g.split(" @ ",1)
            game_terms.extend([a,h,g])

    inspection = []
    for src in SOURCES:
        rows = read_csv(src)
        if not rows:
            inspection.append({
                "file": str(src),
                "exists": src.exists(),
                "rows": 0,
                "columns": [],
                "officialGameRows": 0,
                "priceLikeColumns": [],
                "modelLikeColumns": [],
                "sampleOfficialRows": [],
            })
            continue

        columns = list(rows[0].keys()) if rows else []
        price_like = [c for c in columns if any(x in norm(c) for x in ["price","odds","moneyline","implied","market","entry","best"])]
        model_like = [c for c in columns if any(x in norm(c) for x in ["model","prob","confidence","score","edge"])]

        official_rows = []
        for row in rows:
            text = norm(" ".join(str(v or "") for v in row.values()))
            if any(norm(term) in text for term in game_terms):
                official_rows.append(row)
            if len(official_rows) >= 8:
                break

        samples = []
        for row in official_rows[:5]:
            sample = {}
            for c in columns:
                val = row.get(c, "")
                if val not in ("", None) and (c in price_like or c in model_like or any(x in norm(c) for x in ["team","pick","game","match","event","side","selection","outcome"])):
                    sample[c] = val
            samples.append(sample)

        inspection.append({
            "file": str(src),
            "exists": True,
            "rows": len(rows),
            "columns": columns,
            "officialGameRowsSampled": len(official_rows),
            "priceLikeColumns": price_like,
            "modelLikeColumns": model_like,
            "sampleOfficialRows": samples,
        })

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scheduleDateET": date,
        "officialGames": official_games,
        "inspection": inspection,
        "rule": "Inspect source schemas before increasing price coverage, to avoid copying generic game values to both teams.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 252 INSPECT MONEYLINE SOURCE COLUMNS",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        f"Schedule date ET: {date}",
        "",
        "Official games:",
    ]
    for g in official_games:
        lines.append(f"- {g}")

    for item in inspection:
        lines += [
            "",
            f"FILE: {item['file']}",
            f"Exists: {item['exists']}",
            f"Rows: {item['rows']}",
            f"Official game rows sampled: {item.get('officialGameRowsSampled', 0)}",
            f"Price-like columns: {item.get('priceLikeColumns', [])}",
            f"Model-like columns: {item.get('modelLikeColumns', [])}",
            "Columns:",
        ]
        lines.append(", ".join(item.get("columns", [])[:120]))
        lines.append("Sample official rows:")
        samples = item.get("sampleOfficialRows", [])
        if samples:
            for s in samples[:5]:
                lines.append(json.dumps(s, ensure_ascii=False))
        else:
            lines.append("- none")

    lines += ["", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
