"""Build feature scaffold for ASTRODDS MLB Engine.

Runs safely without data. It does not invent features or write fake processed
training rows.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl"}


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def list_raw_files() -> list[Path]:
    return [path for path in RAW_DIR.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES]


def main() -> None:
    ensure_dirs()
    raw_files = list_raw_files()
    print("ASTRODDS MLB Engine - build_features")
    if not raw_files:
        print("No raw MLB data found. No processed features were written.")
        print("Next: run fetch_data.py or place verified 2023-2026 season-to-date data in mlb-engine/data/raw/.")
        return
    print(f"Found {len(raw_files)} raw file(s).")
    print("Feature builders are not implemented yet, so no model features were written.")
    print("Next: implement verified parsers for moneyline features first, then total_runs features.")


if __name__ == "__main__":
    main()