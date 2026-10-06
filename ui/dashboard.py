from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QFrame, QLabel
from simulation.vehicle_simulator import VehicleState


def format_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}"


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.values = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for i, (key, title) in enumerate([
            ("speed", "СКОРОСТЬ · км/ч"), ("recommended", "РЕКОМЕНДАЦИЯ · км/ч"),
            ("time", "ВРЕМЯ В ПУТИ"), ("distance", "РАССТОЯНИЕ · км"),
            ("fuel", "ТЕКУЩИЙ РАСХОД"), ("total", "ИЗРАСХОДОВАНО · л"),
            ("slope", "ТЕКУЩИЙ УКЛОН · %"), ("prediction", "ПРОГНОЗ +300 м · %")]):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.setContentsMargins(12, 9, 12, 9)
            label = QLabel(title)
            label.setObjectName("subtitle")
            value = QLabel("—")
            value.setObjectName("accent" if key == "recommended" else "metric")
            box.addWidget(label)
            box.addWidget(value)
            self.values[key] = value
            grid.addWidget(card, i // 2, i % 2)

    def update_state(self, state: VehicleState, length_m: float) -> None:
        values = {
            "speed": f"{state.speed_kmh:.1f}", "recommended": f"{state.recommended_speed_kmh:.0f}",
            "time": format_time(state.simulation_time_s),
            "distance": f"{state.current_distance_m / 1000:.2f} / {length_m / 1000:.1f}",
            "fuel": f"{state.fuel_l_per_100km:.1f} л/100 км" if state.fuel_l_per_100km is not None else f"{state.fuel_l_h:.1f} л/ч",
            "total": f"{state.fuel_used_l:.3f}", "slope": f"{state.slope_pct:+.1f}",
            "prediction": "— конец маршрута" if state.predicted_slope_pct is None else f"{state.predicted_slope_pct:+.1f}",
        }
        for key, value in values.items():
            self.values[key].setText(value.replace(".", ","))
