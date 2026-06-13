from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

OUT_JSON = REPORTS / "12_data_source_registry.json"
OUT_TXT = REPORTS / "12_data_source_registry_report.txt"

sources = [
    {
        "name": "MLB StatsAPI",
        "type": "free_public_api",
        "cost": "free",
        "apiKeyRequired": False,
        "status": "connected",
        "useFor": [
            "schedule",
            "results",
            "live game status",
            "boxscore",
            "probable pitchers",
            "lineups",
            "venue",
            "bullpen usage"
        ],
        "risk": "unofficial/public endpoint behavior can change",
        "enginePriority": 1
    },
    {
        "name": "pybaseball",
        "type": "python_package_scraper",
        "cost": "free",
        "apiKeyRequired": False,
        "status": "not_connected",
        "useFor": [
            "Statcast",
            "pitcher advanced stats",
            "batter advanced stats",
            "team batting",
            "team pitching",
            "FanGraphs-style batting/pitching tables",
            "Baseball Savant data"
        ],
        "risk": "scraping-based; source pages can change; needs caching",
        "enginePriority": 1
    },
    {
        "name": "Open-Meteo",
        "type": "free_public_api",
        "cost": "free_non_commercial",
        "apiKeyRequired": False,
        "status": "connected",
        "useFor": [
            "weather forecast",
            "historical weather",
            "temperature",
            "wind speed",
            "wind direction",
            "precipitation"
        ],
        "risk": "weather is context; not a standalone pick signal",
        "enginePriority": 2
    },
    {
        "name": "Retrosheet",
        "type": "free_download_dataset",
        "cost": "free_with_attribution",
        "apiKeyRequired": False,
        "status": "not_connected",
        "useFor": [
            "historical game logs",
            "play-by-play",
            "team daily logs",
            "player daily logs",
            "long-term validation"
        ],
        "risk": "large files; attribution required; not live",
        "enginePriority": 2
    },
    {
        "name": "Lahman / SABR Baseball Database",
        "type": "free_download_dataset",
        "cost": "free",
        "apiKeyRequired": False,
        "status": "not_connected",
        "useFor": [
            "long historical player stats",
            "team stats",
            "pitching",
            "batting",
            "fielding",
            "standings"
        ],
        "risk": "not ideal for same-day betting; better for historical priors",
        "enginePriority": 3
    },
    {
        "name": "Sportsbook odds provider",
        "type": "api",
        "cost": "free_limited_or_paid",
        "apiKeyRequired": True,
        "status": "partially_connected",
        "useFor": [
            "market price",
            "implied probability",
            "opening price if available",
            "current price",
            "line movement",
            "closing price if archived"
        ],
        "risk": "historical closing odds are the hardest free data problem",
        "enginePriority": 1
    },
    {
        "name": "Polymarket MLB markets",
        "type": "market_api",
        "cost": "free_public",
        "apiKeyRequired": False,
        "status": "connected_partial",
        "useFor": [
            "market discovery",
            "market matching",
            "team winner markets",
            "liquidity context"
        ],
        "risk": "team/market alias matching must be strict",
        "enginePriority": 2
    }
]

registry = {
    "createdAt": datetime.utcnow().isoformat() + "Z",
    "project": "ASTRODDS MLB Engine",
    "goal": "BaseballPred-style free-data prediction engine with calibration and edge tracking",
    "rules": [
        "No source changes picks until backtested.",
        "Every feature must be tested against baseline.",
        "Market edge must be resolved with win/loss and ROI.",
        "Paper only until edge buckets prove results.",
        "Cache all external API responses."
    ],
    "sources": sources
}

OUT_JSON.write_text(json.dumps(registry, indent=2), encoding="utf-8")

lines = []
lines.append("ASTRODDS 12 DATA SOURCE REGISTRY")
lines.append("=" * 38)
lines.append("")
lines.append("Goal:")
lines.append("Build a BaseballPred-style engine using free/public data sources.")
lines.append("")
lines.append("Sources:")

for s in sorted(sources, key=lambda x: x["enginePriority"]):
    lines.append("")
    lines.append(f"- {s['name']}")
    lines.append(f"  Status: {s['status']}")
    lines.append(f"  Cost: {s['cost']}")
    lines.append(f"  API key: {s['apiKeyRequired']}")
    lines.append(f"  Priority: {s['enginePriority']}")
    lines.append(f"  Use: {', '.join(s['useFor'])}")
    lines.append(f"  Risk: {s['risk']}")

lines.append("")
lines.append("Next:")
lines.append("13_master_feature_dataset.py")
lines.append("Build one master table with baseline + pitcher + bullpen + lineup + weather + odds fields.")

OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
print("")
print(f"Saved JSON: {OUT_JSON}")
print(f"Saved report: {OUT_TXT}")
