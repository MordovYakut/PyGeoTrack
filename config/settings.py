"""Application paths and demonstration parameters; SI unless named otherwise."""
from pathlib import Path
import shutil
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]
FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
ROOT = Path(sys.executable).resolve().parent if FROZEN else SOURCE_ROOT
DATA_DIR = ROOT / "data"


def prepare_runtime_files() -> None:
    """Create writable runtime folders and seed packaged data on first launch."""
    ROOT.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        bundled_data = RESOURCE_ROOT / "data"
        if bundled_data.is_dir():
            shutil.copytree(bundled_data, DATA_DIR, dirs_exist_ok=True)
OSRM_BASE_URL = "https://router.project-osrm.org"
ELEVATION_API_URL = "https://api.open-meteo.com/v1/elevation"
START_LAT, START_LON = 44.0964, 39.0747
END_LAT, END_LON = 43.5855, 39.7231
DEFAULT_ROUTE_NAME = "Туапсе → Сочи · Россия"
MISSING_ELEVATION_FRACTION = 0.20
ROUTE_SAMPLE_STEP_M = 100.0
USE_CACHED_ROUTE = True
HTTP_TIMEOUT_S = 15
HTTP_ATTEMPTS = 3
ELEVATION_BATCH_SIZE = 100
ELEVATION_BATCH_INTERVAL_S = 11.0
MAX_ROUTE_POINTS = 10000
VEHICLE_MASS_KG = 9000.0
CARGO_MASS_KG = 5000.0
DEFAULT_SPEED_KMH = 60.0
MIN_SPEED_KMH = 30.0
MAX_SPEED_KMH = 90.0
SIMULATION_TIMER_MS = 100
DEFAULT_TIME_SCALE = 1
PREDICTION_DISTANCE_M = 300.0
GRAVITY = 9.81
AIR_DENSITY = 1.225
ROLLING_RESISTANCE = 0.008
DRAG_COEFFICIENT = 0.65
FRONTAL_AREA_M2 = 7.5
ENGINE_EFFICIENCY = 0.38
DIESEL_ENERGY_KWH_PER_L = 9.8
IDLE_FUEL_L_H = 1.5
LAMBDA_TIME = 0.8
FUEL_REFERENCE_L_100KM = 30.0
MAX_TRACTION_POWER_KW = 210.0
POWER_PENALTY = 3.0
ACCELERATION_M_S2 = 1.0
DECELERATION_M_S2 = 1.5
RECOMMENDATION_CHANGE_KMH_S = 3.0
MAX_SLOPE_PCT = 25.0
RANDOM_SEED = 42
CURVE_SAMPLE_STEP_M = 10.0
CURVE_WINDOW_M = 20.0
MAX_LATERAL_ACCELERATION_M_S2 = 1.3
MIN_CURVE_SPEED_KMH = 10.0
CURVE_BRAKING_M_S2 = 1.0
