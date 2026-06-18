import argparse, csv, json
from pathlib import Path
from datetime import datetime

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def val(row, name):
    return str(row.get(name, "")).strip()

def num(value):
    try:
        return float(str(value).replace("%", "").replace("¢", "").replace(",", ".").strip())
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    astro = root / ".astrodds"

    rows = read_csv(astro / "ASTRODDS-289-best-price-line-shopping-latest.csv")

    playable = []
    official = []

    for r in rows:
        status = val(r, "MlbStatus")
        book = val(r, "BestBook")

        if status not in ["Scheduled", "Pre-Game", "Warmup"]:
            continue

        if book.lower() == "internal":
            continue

        model = num(val(r, "ModelProbability"))
        price = num(val(r, "BestEntry"))

        if model is None or price is None:
            continue

        edge = round(model - price, 1)
        need = round(model - 5, 1)
        decision = val(r, "LineShopDecision")

        item = {
            "decision": decision,
            "pick": val(r, "Pick"),
            "game": val(r, "Game"),
            "status": status,
            "model": model,
            "price": price,
            "edge": edge,
            "need": need,
            "book": book,
        }

        playable.append(item)

        if edge >= 5 and ("SEND" in decision.upper() or "OFFICIAL" in decision.upper()):
            official.append(item)

    lines = []
    lines.append("ASTRODDS CLEAN CLIENT VALUE REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    if official:
        lines.append("OFFICIAL VALUE FOUND")
        lines.append("")
        for p in official:
            lines.append(f"- {p['pick']} ML | {p['game']}")
            lines.append(f"  Model: {p['model']}% | Best: {p['price']} cents {p['book']} | Edge: +{p['edge']}%")
            lines.append("")
    else:
        lines.append("NO OFFICIAL PICKS RIGHT NOW")
        lines.append("Reason: current market prices are too expensive versus model probability.")
        lines.append("")

        if playable:
            lines.append("Closest live/pre-game values:")
            lines.append("")
            for p in sorted(playable, key=lambda x: x["edge"], reverse=True)[:8]:
                lines.append(f"- {p['pick']} | {p['game']} | {p['status']}")
                lines.append(f"  Model {p['model']}% | Best {p['price']} cents {p['book']} | Edge {p['edge']}%")
                lines.append(f"  Need {p['need']} cents or lower for official +5% edge.")
                lines.append("")
        else:
            lines.append("No playable external market rows right now.")

    lines.append("Rules: MLB moneyline only | No parlays | 5% bankroll max | No picks after start | External market required")

    output = {
        "generatedAt": datetime.now().isoformat(),
        "officialCount": len(official),
        "playableCount": len(playable),
        "playable": playable,
    }

    (astro / "ASTRODDS-389-clean-client-value-report-latest.json").write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    (astro / "ASTRODDS-389-clean-client-value-report-latest.txt").write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print("\n".join(lines))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())