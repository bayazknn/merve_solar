"""ExperimentConfig: the facet class parameterizing one training+evaluation run."""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_XLSX_PATH = PROJECT_ROOT / "SolarData_Merve_All(16July).xlsx"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
BASE_FEATURES_PATH = OUTPUTS_DIR / "processed" / "base_features.parquet"
EXPERIMENTS_DIR = OUTPUTS_DIR / "experiments"
LEDGER_PATH = OUTPUTS_DIR / "experiments_ledger.csv"

CITIES = ["Ankara", "Antalya", "Konya", "Rize", "Van"]
CITY_TO_ID = {city: i for i, city in enumerate(CITIES)}

# NASA POWER's missing-value sentinel.
MISSING_SENTINEL = -999

# Last valid timestamp before NASA POWER's near-real-time processing-latency gap
# (2026-03-31 00:00 -> 2026-06-30 23:00 is -999 for ALLSKY_SFC_SW_DWN/CLRSKY_SFC_SW_DWN
# in every sheet, verified directly against the source file).
LAST_VALID_TIMESTAMP = "2026-03-30 23:00:00"
EXPECTED_TRIMMED_ROWS_PER_SHEET = 2208

TARGET_COLUMN = "ALLSKY_SFC_SW_DWN"

NUMERIC_FEATURE_COLUMNS = [
    "ALLSKY_SFC_SW_DWN",  # own-lag, autoregressive
    "CLRSKY_SFC_SW_DWN",
    "T2M",
    "RH2M",
    "QV2M",
    "T2MDEW",
    "PS",
    "WS10M",
    "WS50M",
    "PRECTOTCORR",
    "WD10M_sin",
    "WD10M_cos",
    "WD50M_sin",
    "WD50M_cos",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
]


@dataclass
class ExperimentConfig:
    experiment_id: str

    # sequence / windowing
    lookback_hours: int = 24
    horizon_hours: int = 24
    window_stride: int = 1

    # chronological split ratios (test = 1 - train_ratio - val_ratio)
    train_ratio: float = 0.74
    val_ratio: float = 0.11

    # architecture
    hidden_sizes: list = field(default_factory=lambda: [64, 32])
    dropout_rate: float = 0.3
    city_embedding_dim: int = 4

    # training
    learning_rate: float = 1e-3
    batch_size: int = 128
    max_epochs: int = 100
    early_stop_patience: int = 10
    lr_reduce_factor: float = 0.5
    lr_reduce_patience: int = 7
    nonneg_penalty_weight: float = 0.1

    # uncertainty quantification
    n_bootstrap: int = 8
    mc_dropout_passes: int = 100
    bootstrap_block_length: int = 168

    seed: int = 42

    @property
    def test_ratio(self) -> float:
        return 1.0 - self.train_ratio - self.val_ratio

    @property
    def experiment_dir(self) -> Path:
        return EXPERIMENTS_DIR / self.experiment_id

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "ExperimentConfig":
        return cls(**json.loads(Path(path).read_text()))
