"""One-time, config-independent data prep: load, clean, feature-engineer, cache."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.config import BASE_FEATURES_PATH
from merve_solar.data import load_all_cities, save_base_features


def main():
    df = load_all_cities()
    save_base_features(df, BASE_FEATURES_PATH)
    print(f"Saved {len(df)} rows ({df['city'].nunique()} cities) to {BASE_FEATURES_PATH}")
    print(df.groupby("city")["datetime"].agg(["min", "max", "count"]))


if __name__ == "__main__":
    main()
