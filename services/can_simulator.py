from dataclasses import asdict, dataclass
import csv
from pathlib import Path
from config import settings as cfg


@dataclass(frozen=True)
class CANData:
    speed_kmh: float
    vehicle_mass_kg: float
    cargo_mass_kg: float
    total_mass_kg: float
    simulation_time_s: float


class CANSimulator:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.vehicle_mass_kg = cfg.VEHICLE_MASS_KG
        self.cargo_mass_kg = cfg.CARGO_MASS_KG
        self.speed_kmh = 0.0
        self.simulation_time_s = 0.0
        self._stream = None
        self._writer = None
        self.reset()

    def get_current_data(self) -> CANData:
        return CANData(self.speed_kmh, self.vehicle_mass_kg, self.cargo_mass_kg,
                       self.vehicle_mass_kg + self.cargo_mass_kg, self.simulation_time_s)

    def record(self, speed_kmh: float, simulation_time_s: float) -> None:
        self.speed_kmh, self.simulation_time_s = speed_kmh, simulation_time_s
        if self._writer:
            self._writer.writerow(asdict(self.get_current_data()))
            self._stream.flush()

    def reset(self) -> None:
        self.close()
        self.speed_kmh = self.simulation_time_s = 0.0
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = self.path.open("w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._stream, fieldnames=list(asdict(self.get_current_data())))
            self._writer.writeheader()
            self.record(0, 0)

    def close(self) -> None:
        if self._stream:
            self._stream.close()
        self._stream = self._writer = None
