import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from config import settings as cfg


class RouteCharts(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(270)
        self.setMaximumHeight(350)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self.plots, self.full, self.estimated, self.passed, self.cursors = [], [], [], [], []
        for i, (title, unit) in enumerate((("ВЫСОТА", "м"), ("УКЛОН ДОРОГИ", "%"))):
            plot = pg.PlotWidget(background="#182533")
            # PlotWidget's default size hint is 600 px; ignore it inside a scroll panel.
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
            plot.setMinimumHeight(125)
            plot.setTitle(title, color="#aac1d6", size="10pt")
            plot.setLabel("left", unit)
            plot.setLabel("bottom", "Расстояние", units="км")
            plot.showGrid(x=True, y=True, alpha=.12)
            plot.setMenuEnabled(False)
            plot.addLegend(offset=(8, 3), labelTextColor="#dce9f5", labelTextSize="8pt")
            self.full.append(plot.plot(pen=pg.mkPen("#79bfff", width=1.8), name="Исходные данные"))
            color = "#ffbf69" if i == 0 else "#cf98ef"
            name = "После восстановления" if i == 0 else "Прогноз +300 м"
            self.estimated.append(plot.plot(pen=pg.mkPen(color, width=1.7,
                style=pg.QtCore.Qt.PenStyle.DashLine), name=name))
            self.passed.append(plot.plot(pen=pg.mkPen("#4be1bf", width=2.5)))
            cursor = pg.InfiniteLine(angle=90, pen=pg.mkPen("#a9bcd0", style=pg.QtCore.Qt.PenStyle.DashLine))
            plot.addItem(cursor)
            self.cursors.append(cursor)
            self.plots.append(plot)
            layout.addWidget(plot)
        self.restored = self.plots[0].plot(pen=None, symbol="o", symbolSize=6, symbolBrush="#ffbf69", symbolPen=None)
        self.future = self.plots[1].plot(pen=None, symbol="d", symbolSize=10, symbolBrush="#cf98ef", symbolPen=None)
        self.route = None

    def set_route(self, route, original) -> None:
        self.route = route
        self.original = original
        self.x = route.total_distance_m.to_numpy() / 1000
        for i, col in enumerate(("elevation_m", "slope_pct")):
            self.full[i].setData(original.total_distance_m.to_numpy() / 1000, original[col].to_numpy())
            self.plots[i].setXRange(0, self.x[-1], padding=.02)
        self.estimated[0].setData(self.x, route.elevation_m.to_numpy())
        # Predictions refer to the target position, not to the position of the input.
        target_x = self.x + cfg.PREDICTION_DISTANCE_M / 1000
        valid = (target_x <= self.x[-1]) & (route.prediction_available.to_numpy() == 1)
        self.estimated[1].setData(target_x[valid], route.predicted_slope_pct.to_numpy()[valid])
        restored = route.is_restored.to_numpy() == 1
        self.restored.setData(self.x[restored], route.elevation_m.to_numpy()[restored])
        self.reset()

    def reset(self) -> None:
        for curve in self.passed:
            curve.setData([], [])
        self.future.setData([], [])
        for cursor in self.cursors:
            cursor.setValue(0)

    def update_state(self, state) -> None:
        if self.route is None:
            return
        km = state.current_distance_m / 1000
        end = np.searchsorted(self.x, km, side="right")
        for i, (col, value) in enumerate((("elevation_m", state.elevation_m), ("slope_pct", state.slope_pct))):
            self.passed[i].setData(np.r_[self.x[:end], km], np.r_[self.route[col].to_numpy()[:end], value])
            self.cursors[i].setValue(km)
        if state.predicted_slope_pct is not None:
            self.future.setData([km + cfg.PREDICTION_DISTANCE_M / 1000], [state.predicted_slope_pct])
        else:
            self.future.setData([], [])
