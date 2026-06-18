from pathlib import Path
from datetime import datetime, timezone
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
SOURCE_265 = ASTRO / "ASTRODDS-265-source-first-baseline-model-latest.csv"
SOURCE_266 = ASTRO / "ASTRODDS-266-source-model-market-bridge-latest.csv"
SOURCE_PLUS = ASTRO / "ASTRODDS-baseballpred-plus-context-latest.csv"

OUT_JSON = ASTRO / "ASTRODDS-400-market-pm-exact-team-join-latest.json"
REPORT = REPORTS / "400_market_pm_exact_team_join_report.txt"

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def fnum(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%", "").replace("+", "").replace("$", "").replace("Â¢", "").replace("Ã‚", "").replace(",", ".")
    if not s:
        return default
    try:
        x = float(s)
        # 49.5 means 49.5%, convert to 0.495.
        if 1.0 < x <= 100.0:
            return x / 100.0
        return x
    except Exception:
        return default

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
            return [{str(k or "").strip(): v for k, v in row.items()} for row in csv.DictReader(f, dialect=dialect)]
    except Exception:
        return []

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def source_map_from_265():
    out = {}
    for r in read_csv(SOURCE_265):
        game = r.get("Game", "")
        away = r.get("AwayTeam", "")
        home = r.get("HomeTeam", "")
        if not game or not away or not home:
            continue

        # Side-specific market and model fields are the cleanest PM/Fair source.
        away_pm = fnum(r.get("AwayMarketAvg"))
        home_pm = fnum(r.get("HomeMarketAvg"))
        away_fair = fnum(r.get("AwayModelProbability"))
        home_fair = fnum(r.get("HomeModelProbability"))

        out[(norm(game), norm(away))] = {
            "price": away_pm,
            "modelProbability": away_fair,
            "source": str(SOURCE_265),
            "priceColumn": "AwayMarketAvg",
            "modelColumn": "AwayModelProbability",
            "mode": "source_265_side_specific_away_market_avg",
            "sourceRow": r,
        }
        out[(norm(game), norm(home))] = {
            "price": home_pm,
            "modelProbability": home_fair,
            "source": str(SOURCE_265),
            "priceColumn": "HomeMarketAvg",
            "modelColumn": "HomeModelProbability",
            "mode": "source_265_side_specific_home_market_avg",
            "sourceRow": r,
        }
    return out

def source_map_from_266():
    out = {}
    for r in read_csv(SOURCE_266):
        game = r.get("Game", "")
        pick = r.get("Pick", "")
        if not game or not pick:
            continue
        price = fnum(r.get("MarketProbability")) or fnum(r.get("Entry"))
        model = fnum(r.get("ModelProbability")) or fnum(r.get("ModelProbabilityRaw"))
        out[(norm(game), norm(pick))] = {
            "price": price,
            "modelProbability": model,
            "source": str(SOURCE_266),
            "priceColumn": "MarketProbability/Entry",
            "modelColumn": "ModelProbability",
            "mode": "source_266_pick_specific_market_probability",
            "sourceRow": r,
        }
    return out

def source_map_from_plus():
    out = {}
    for r in read_csv(SOURCE_PLUS):
        game = r.get("Game", "")
        pick = r.get("Pick", "")
        if not game or not pick:
            continue
        price = fnum(r.get("BestEntry"))
        model = fnum(r.get("ModelProbability"))
        out[(norm(game), norm(pick))] = {
            "price": price,
            "modelProbability": model,
            "source": str(SOURCE_PLUS),
            "priceColumn": "BestEntry",
            "modelColumn": "ModelProbability",
            "mode": "baseballpred_plus_pick_specific_best_entry",
            "sourceRow": r,
        }
    return out

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load_json(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    map265 = source_map_from_265()
    map266 = source_map_from_266()
    mapplus = source_map_from_plus()

    updated_price = 0
    updated_model = 0
    source_counts = {}
    missing = []

    new_rows = []
    for raw in rows:
        r = dict(raw)
        key = (norm(r.get("game", "")), norm(r.get("pick", "")))

        chosen = None
        # Prefer 265 because it has side-specific AwayMarketAvg/HomeMarketAvg for both teams.
        for srcmap in [map265, map266, mapplus]:
            cand = srcmap.get(key)
            if cand and (cand.get("price") is not None or cand.get("modelProbability") is not None):
                chosen = cand
                break

        old_price = fnum(r.get("price"))
        old_model = fnum(r.get("modelProbability"))

        if chosen:
            if chosen.get("price") is not None:
                if old_price is None or abs(chosen["price"] - old_price) > 0.00001:
                    updated_price += 1
                r["price"] = round(chosen["price"], 6)
                r["priceSourceFile"] = chosen["source"]
                r["priceSourceColumn"] = chosen["priceColumn"]
                r["priceSourceMode"] = chosen["mode"]

            if chosen.get("modelProbability") is not None:
                if old_model is None or abs(chosen["modelProbability"] - old_model) > 0.00001:
                    updated_model += 1
                r["modelProbability"] = round(chosen["modelProbability"], 6)
                r["modelSourceFile"] = chosen["source"]
                r["modelSourceColumn"] = chosen["modelColumn"]
                r["modelSourceMode"] = chosen["mode"]

            source_counts[chosen["mode"]] = source_counts.get(chosen["mode"], 0) + 1

        price = fnum(r.get("price"))
        model = fnum(r.get("modelProbability"))
        if price is not None and model is not None:
            r["currentEdgePct"] = round((model - price) * 100.0, 2)
            r["edgePct"] = r["currentEdgePct"]
        else:
            r["currentEdgePct"] = None
            r["edgePct"] = None
            missing.append({"pick": r.get("pick"), "game": r.get("game"), "price": price, "model": model})

        r["pmExactTeamJoinApplied"] = True
        new_rows.append(r)

    # Sanity: if both sides available, total PM should be reasonably around 1.00, with normal vig.
    warnings = []
    by_game = {}
    for r in new_rows:
        by_game.setdefault(norm(r.get("game", "")), []).append(r)

    for gk, group in by_game.items():
        if len(group) == 2:
            prices = [fnum(x.get("price")) for x in group]
            if all(p is not None for p in prices):
                total = sum(prices)
                if total < 0.90 or total > 1.15:
                    warnings.append(f"Suspicious PM total {total:.3f}: {group[0].get('game')}")
            models = [fnum(x.get("modelProbability")) for x in group]
            if all(m is not None for m in models):
                total_m = sum(models)
                if total_m < 0.98 or total_m > 1.02:
                    warnings.append(f"Suspicious Fair total {total_m:.3f}: {group[0].get('game')}")

    rows_with_price = sum(1 for r in new_rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in new_rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in new_rows if fnum(r.get("currentEdgePct")) is not None)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rows": len(new_rows),
        "rowsWithPrice": rows_with_price,
        "rowsWithModel": rows_with_model,
        "rowsWithEdge": rows_with_edge,
        "updatedPriceRows": updated_price,
        "updatedModelRows": updated_model,
        "sourceCounts": source_counts,
        "missingRows": missing,
        "warnings": warnings,
        "moneylineBoard": new_rows,
        "rule": "Join PM/market and Fair/model by exact official game + exact team side. Prefer source 265 side-specific Away/Home MarketAvg and ModelProbability.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(new_rows), "moneylineBoard": new_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 400 MARKET PM EXACT TEAM JOIN",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows: {out['rows']}",
        f"Rows with price: {rows_with_price}",
        f"Rows with model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Updated price rows: {updated_price}",
        f"Updated model rows: {updated_model}",
        f"Warnings: {len(warnings)}",
        "",
        "Source counts:",
    ]
    for k, v in sorted(source_counts.items()):
        lines.append(f"- {k}: {v}")

    lines += ["", "Board:"]
    for r in new_rows:
        lines.append(
            f"- {r.get('pick')} | {r.get('game')} | PM={round(fnum(r.get('price'),0)*100,2) if fnum(r.get('price')) is not None else None}% | "
            f"Fair={round(fnum(r.get('modelProbability'),0)*100,2) if fnum(r.get('modelProbability')) is not None else None}% | "
            f"Edge={r.get('currentEdgePct')}% | status={r.get('liveMlbStatus')} | mode={r.get('priceSourceMode','')}"
        )

    if missing:
        lines += ["", "Missing rows:"]
        for m in missing:
            lines.append(f"- {m['pick']} | {m['game']} | price={m['price']} | model={m['model']}")

    if warnings:
        lines += ["", "Warnings:"]
        for w in warnings:
            lines.append(f"- {w}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: market PM exact team join should lift price coverage toward 18/18."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
