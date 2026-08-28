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

# Descriptive-statistics / EDA outputs (scripts/02_descriptive_analysis.py). These describe
# the dataset itself rather than one experiment, so they live outside outputs/experiments/.
EDA_DIR = OUTPUTS_DIR / "eda"
EDA_FIGURES_DIR = EDA_DIR / "figures"
EDA_TABLES_DIR = EDA_DIR / "tables"

# Clear-sky reference cache, built on demand by eda.load_clearsky_reference().
# CLRSKY_SFC_SW_DWN is in DROPPED_COLUMNS and must never become a model feature (it is a
# near-deterministic envelope of the target). It is read back here for DESCRIPTIVE USE ONLY
# -- the clearness index kt = ALLSKY / CLRSKY is what makes the cities comparable on
# cloudiness rather than on latitude. Nothing under experiment.py reads this file.
CLEARSKY_REFERENCE_PATH = OUTPUTS_DIR / "processed" / "clearsky_reference.parquet"

CITIES = ["Ankara", "Antalya", "Konya", "Rize", "Van"]
CITY_TO_ID = {city: i for i, city in enumerate(CITIES)}

# NASA POWER's missing-value sentinel.
MISSING_SENTINEL = -999

# Last valid timestamp before NASA POWER's near-real-time processing-latency gap
# (2026-03-31 00:00 -> 2026-06-30 23:00 is -999 for ALLSKY_SFC_SW_DWN/CLRSKY_SFC_SW_DWN
# in every sheet, verified directly against the source file).
LAST_VALID_TIMESTAMP = "2026-03-30 23:00:00"
EXPECTED_TRIMMED_ROWS_PER_SHEET = 2208

# Target: global horizontal irradiance under all-sky conditions, in W/m^2.
TARGET_COLUMN = "ALLSKY_SFC_SW_DWN"

# Columns dropped while reading the xlsx (see data.py). The source file is left
# physically untouched so it stays the raw NASA POWER export; the drop list lives here.
#   ALLSKY_KT - clearness index, undefined at night (~50% -999); dropping it is what
#               makes the "no -999 remains" integrity check pass.
DROPPED_COLUMNS = ["ALLSKY_KT"]

# Kept in the frame but NEVER a model input.
#
# CLRSKY_SFC_SW_DWN is a near-deterministic geometric upper envelope of the target, so as a
# *feature* it turns part of the task into a clear-sky-index fit and inflates skill relative
# to what is available operationally -- which is why it was removed from the feature set.
# That same property is exactly what makes it the right *instrument*: clear-sky irradiance is
# pure solar geometry with no weather term, so `CLRSKY > 0` is an exact "is the sun above the
# horizon" indicator that never reads the realised target. Useless as a predictor, ideal as a
# mask. It defines the daylight subset used for metrics (see metrics.py).
#
# Measured against the alternatives on the full record (295,920 rows): `CLRSKY > 0` selects
# 151,643 rows and agrees with a `y >= 1 W/m^2` target threshold on 99.9983% of hours, but
# never conditions on the outcome. A (city, month, hour) climatological cell selects 156,909
# -- it over-admits 5,266 twilight hours at the edges of monthly cells, whose median irradiance
# is 12.0 W/m^2 against the daylight interior's 395.7, which would put much of the night
# inflation straight back into the "daylight" numbers.
MASK_COLUMNS = ["CLRSKY_SFC_SW_DWN"]
DAYLIGHT_REFERENCE_COLUMN = "CLRSKY_SFC_SW_DWN"

# A secondary aggregate that leaves Rize out, reported alongside the plain one.
# The five provinces are two regimes, not one: Rize's daily clear-sky index is 0.697 against
# 0.806-0.840 elsewhere, its overcast-day share (kt < 0.3) is 8.0% against 1.0-2.8%, and its
# best season (kt 0.772) sits near the others' winter. The plain aggregate therefore buries
# Rize four-to-one -- which is exactly where the city embedding has to do its work, so the
# contribution of cross-city transfer is invisible in the headline number without this row.
SECONDARY_AGGREGATE_EXCLUDES = ["Rize"]

# Arm-selection axes. Both are recorded in the ledger, so adding GRU/SVR/RF later needs no
# header migration. "global" is the headline configuration and the default; "per_city" exists
# only as the ablation arm that tests the paper's cross-city transfer claim.
TRAINING_SCOPES = ("global", "per_city")
MODEL_FAMILIES = ("lstm", "climatology", "persistence")

NUMERIC_FEATURE_COLUMNS = [
    "ALLSKY_SFC_SW_DWN",  # own-lag, autoregressive
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

# Physical meteorological variables, for the paper's descriptive-statistics table. Derived
# from NUMERIC_FEATURE_COLUMNS rather than written out a second time: if the feature set ever
# changes, the dataset table must not keep describing the old one. The sin/cos encodings are
# excluded because their mean/std are constants by construction (mean~0, std~0.707) and carry
# no information; the time features are described separately (see eda.temporal_coverage_table).
RAW_METEO_COLUMNS = [c for c in NUMERIC_FEATURE_COLUMNS if not c.endswith(("_sin", "_cos"))]

# Wind direction is circular: its arithmetic mean/std are meaningless (a pooled "189.5 +- 107
# deg" is an artifact, not a statistic). Reported separately via circular statistics.
CIRCULAR_COLUMNS = ["WD10M", "WD50M"]

# CLRSKY_SFC_SW_DWN now sits in the frame rather than being dropped, which makes it the column
# most likely to drift back into the feature list by accident -- there is even a cached parquet
# of it on disk inviting the mistake. This guard is what stops that, so it must keep covering
# MASK_COLUMNS as well as DROPPED_COLUMNS.
_non_feature = set(DROPPED_COLUMNS) | set(MASK_COLUMNS)
_misused = _non_feature & (set(NUMERIC_FEATURE_COLUMNS) | {TARGET_COLUMN})
if _misused:
    raise ValueError(
        f"Columns reserved as non-features are used as a feature or the target: {sorted(_misused)}"
    )


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

    # arm selection (see TRAINING_SCOPES / MODEL_FAMILIES above)
    training_scope: str = "global"
    model_family: str = "lstm"
    # Mask the training loss to daylight steps. Default off: it is a modelling change, not a
    # reporting one -- night outputs become unsupervised and free to drift, only ~13 of the 24
    # horizon steps stay supervised (and which 13 shifts with the season), and it leaves the UQ
    # layer unconstrained at night so CP and PINW become partly meaningless there. Evaluate it
    # as its own experiment rather than folding it into another comparison.
    loss_daylight_only: bool = False

    def __post_init__(self) -> None:
        # Validate here rather than at use: from_json() runs this too, so a typo'd
        # "per-city" fails at load instead of three hours into a sweep.
        if self.training_scope not in TRAINING_SCOPES:
            raise ValueError(f"training_scope must be one of {TRAINING_SCOPES}, got {self.training_scope!r}")
        if self.model_family not in MODEL_FAMILIES:
            raise ValueError(f"model_family must be one of {MODEL_FAMILIES}, got {self.model_family!r}")
        if not 0.0 < self.dropout_rate < 1.0:
            raise ValueError("dropout_rate must be in (0, 1): it is the only source of MC-Dropout randomness")

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
