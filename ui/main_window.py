import logging
import time
import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QDoubleSpinBox, QComboBox, QCheckBox, QProgressBar, QMessageBox,
    QScrollArea, QFrame,
)
from config import settings as cfg
from services.pipeline import RoutePipeline, RouteBundle
from services.can_simulator import CANSimulator
from simulation.vehicle_simulator import VehicleSimulator
from map.map_widget import MapWidget
from ui.dashboard import Dashboard, format_time
from ui.charts import RouteCharts
from ui.styles import STYLE

log = logging.getLogger(__name__)


class RouteWorker(QObject):
    ready = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, start, end, force):
        super().__init__()
        self.start_point, self.end_point, self.force = start, end, force

    @Slot()
    def run(self):
        try:
            bundle = RoutePipeline().load(self.start_point, self.end_point, self.force)
            simulator = VehicleSimulator(bundle.route, geometry=bundle.geometry)
            self.ready.emit(bundle, simulator)
        except Exception as exc:
            log.exception("Ошибка подготовки маршрута")
            self.failed.emit("Не удалось подготовить маршрут. Проверьте координаты, доступ к сети и файлы в папке data. "
                             "Подробности записаны в logs/application.log.")
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    route_loaded = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyGeoTrack · Симулятор движения")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 960)
        self.setStyleSheet(STYLE)
        self.simulator = None
        self.bundle = None
        self.thread = None
        self.worker = None
        self.closing = False
        self.timer = QTimer(self)
        self.timer.setInterval(cfg.SIMULATION_TIMER_MS)
        self.timer.timeout.connect(self.tick)
        self.last_tick = time.perf_counter()
        self._build_ui()
        QTimer.singleShot(0, self.load_route)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 10)
        root.setSpacing(12)
        title_row = QHBoxLayout()
        title = QLabel("PyGeoTrack")
        title.setObjectName("title")
        title_row.addWidget(title)
        subtitle = QLabel("СИМУЛЯТОР   /   РЕЛЬЕФ • ТЕЛЕМЕТРИЯ • РАСХОД")
        subtitle.setObjectName("subtitle")
        title_row.addWidget(subtitle)
        title_row.addStretch()
        self.state_label = QLabel("ПОДГОТОВКА МАРШРУТА")
        self.state_label.setStyleSheet("color:#4be1bf;font-weight:700")
        title_row.addWidget(self.state_label)
        root.addLayout(title_row)

        route_row = QHBoxLayout()
        self.coordinate_fields = []
        for label, value, limit in (("Широта А", cfg.START_LAT, 90), ("Долгота А", cfg.START_LON, 180),
                                     ("Широта Б", cfg.END_LAT, 90), ("Долгота Б", cfg.END_LON, 180)):
            route_row.addWidget(QLabel(label))
            field = QDoubleSpinBox()
            field.setFixedHeight(38)
            field.setRange(-limit, limit)
            field.setDecimals(5)
            field.setValue(value)
            field.setSingleStep(.001)
            self.coordinate_fields.append(field)
            route_row.addWidget(field)
        self.rebuild_button = QPushButton("ПОСТРОИТЬ МАРШРУТ")
        self.rebuild_button.clicked.connect(lambda: self.load_route(True))
        route_row.addWidget(self.rebuild_button)
        root.addLayout(route_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.route_title = QLabel("Загрузка маршрута…")
        self.route_title.setStyleSheet("font-size:16px;font-weight:600")
        left_layout.addWidget(self.route_title)
        self.map = MapWidget()
        self.map.map_ready.connect(lambda ok: self.statusBar().showMessage("Карта недоступна; симуляция продолжает работать") if not ok else None)
        left_layout.addWidget(self.map, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        left_layout.addWidget(self.progress)
        self.details = QLabel("Масса 14 000 кг  ·  Автомобиль 9 000 кг + груз 5 000 кг")
        self.details.setObjectName("subtitle")
        left_layout.addWidget(self.details)
        self.source = QLabel("OpenStreetMap / OSRM · Open-Meteo / Copernicus DEM GLO-90")
        self.source.setObjectName("subtitle")
        left_layout.addWidget(self.source)
        splitter.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(420)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(9)
        self.dashboard = Dashboard()
        right_layout.addWidget(self.dashboard)
        self.charts = RouteCharts()
        right_layout.addWidget(self.charts, 1)
        self.ai_status = QLabel("ИИ-рельеф: загрузка  ·  ИИ-уклон: загрузка")
        self.ai_status.setWordWrap(True)
        self.ai_status.setObjectName("subtitle")
        right_layout.addWidget(self.ai_status)
        legend = QLabel("Синий: исходные данные · Золотой: восстановление\nФиолетовый: прогноз уклона на 300 м вперёд")
        legend.setObjectName("subtitle")
        right_layout.addWidget(legend)
        controls = QHBoxLayout()
        self.ai = QCheckBox("ИИ-УПРАВЛЕНИЕ СКОРОСТЬЮ")
        self.ai.setChecked(True)
        self.ai.toggled.connect(self._control_changed)
        controls.addWidget(self.ai)
        controls.addStretch()
        self.manual = QDoubleSpinBox()
        self.manual.setFixedHeight(38)
        self.manual.setMinimumWidth(140)
        self.manual.setToolTip("Желаемая скорость на прямой. Перед поворотами автомобиль замедляется автоматически.")
        self.manual.setRange(cfg.MIN_SPEED_KMH, cfg.MAX_SPEED_KMH)
        self.manual.setValue(cfg.DEFAULT_SPEED_KMH)
        self.manual.setSuffix(" км/ч")
        self.manual.setEnabled(False)
        self.manual.valueChanged.connect(self._control_changed)
        controls.addWidget(self.manual)
        right_layout.addLayout(controls)
        actions = QHBoxLayout()
        self.start_button = QPushButton("СТАРТ")
        self.start_button.setObjectName("start")
        self.pause_button = QPushButton("ПАУЗА")
        self.reset_button = QPushButton("СБРОС")
        self.start_button.clicked.connect(self.start)
        self.pause_button.clicked.connect(self.pause)
        self.reset_button.clicked.connect(self.reset)
        for button in (self.start_button, self.pause_button, self.reset_button):
            button.setEnabled(False)
            actions.addWidget(button)
        self.scale = QComboBox()
        for value in (1, 2, 5, 10, 20):
            self.scale.addItem(f"×{value}", value)
        self.scale.setCurrentIndex(self.scale.findData(cfg.DEFAULT_TIME_SCALE))
        actions.addWidget(self.scale)
        right_layout.addLayout(actions)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        scroll.setMinimumWidth(445)
        splitter.addWidget(scroll)
        splitter.setSizes([870, 500])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

    @Slot()
    def load_route(self, force_network: bool = False):
        if self.thread is not None:
            return
        self.pause()
        self.state_label.setText("ЗАГРУЗКА МАРШРУТА")
        self.statusBar().showMessage("Загрузка маршрута и обучение моделей…")
        for button in (self.start_button, self.pause_button, self.reset_button, self.rebuild_button):
            button.setEnabled(False)
        coords = [field.value() for field in self.coordinate_fields]
        self.thread = QThread(self)
        self.worker = RouteWorker(tuple(coords[:2]), tuple(coords[2:]), force_network)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.ready.connect(self._loaded)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(object, object)
    def _loaded(self, bundle: RouteBundle, simulator: VehicleSimulator):
        if self.simulator:
            self.simulator.can.close()
        self.bundle, self.simulator = bundle, simulator
        try:
            simulator.can = CANSimulator(cfg.DATA_DIR / "can_data.csv")
        except OSError:
            log.exception("Журнал CAN недоступен")
            bundle.status += " · Не удалось записать CSV телеметрии"
        self.route_title.setText(f"{bundle.metadata['name']}   /   {simulator.length_m / 1000:.2f} км")
        for field, value in zip(self.coordinate_fields,
                bundle.metadata.get("start", [bundle.route.latitude.iloc[0], bundle.route.longitude.iloc[0]]) +
                bundle.metadata.get("end", [bundle.route.latitude.iloc[-1], bundle.route.longitude.iloc[-1]])):
            field.setValue(value)
        self.map.set_route(simulator.geometry[:, ::-1].tolist())
        self.charts.set_route(bundle.route, bundle.original)
        terrain, slope = bundle.metrics["terrain"], bundle.metrics["slope"]
        terrain_text = f"Рельеф: готово · Восстановлено точек: {terrain['restored_points']}"
        if "mae_pct" in slope:
            quality = "низкая точность" if slope.get("r2") is not None and slope["r2"] < 0 else "готово"
            slope_text = f"Уклон: {quality} · MAE {slope['mae_pct']:.2f}% · Горизонт 300 м"
        else:
            slope_text = f"Уклон: {slope.get('note', 'готово')}"
        self.ai_status.setText(terrain_text + "\n" + slope_text)
        self.ai_status.setToolTip("MAE — средняя абсолютная ошибка на проверочной части маршрута.\n"
                                 "Оранжевые точки — восстановленные высоты. Исходные данные сохранены отдельно.")
        self.statusBar().showMessage(bundle.status)
        self.reset()
        self.route_loaded.emit()

    @Slot(str)
    def _failed(self, error: str):
        self.state_label.setText("ОШИБКА ЗАГРУЗКИ")
        self.statusBar().showMessage(error)
        if not self.closing:
            QMessageBox.warning(self, "Маршрут недоступен", error)

    @Slot()
    def _thread_finished(self):
        self.thread = self.worker = None
        self.rebuild_button.setEnabled(True)
        if self.simulator:
            self.start_button.setEnabled(not self.simulator.state.completed)
            self.reset_button.setEnabled(True)
        if self.closing:
            self.close()

    def _control_changed(self, *_):
        self.manual.setEnabled(not self.ai.isChecked())
        if self.simulator:
            self.simulator.ai_control = self.ai.isChecked()
            self.simulator.manual_speed_kmh = self.manual.value()

    @Slot()
    def start(self):
        if not self.simulator or self.simulator.state.completed or self.thread:
            return
        self._control_changed()
        self.simulator.start()
        self.last_tick = time.perf_counter()
        self.timer.start()
        self.state_label.setText("ДВИЖЕНИЕ")
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        log.info("Симуляция запущена")

    @Slot()
    def pause(self):
        self.timer.stop()
        if self.simulator:
            self.simulator.pause()
            self.state_label.setText("ПАУЗА")
            self.start_button.setEnabled(not self.simulator.state.completed)
            self.pause_button.setEnabled(False)
            log.info("Симуляция приостановлена")

    @Slot()
    def reset(self):
        if not self.simulator:
            return
        self.timer.stop()
        self.simulator.reset()
        self.map.reset()
        self.charts.reset()
        self.dashboard.update_state(self.simulator.state, self.simulator.length_m)
        self.progress.setValue(0)
        self.details.setText(f"Высота {self.simulator.state.elevation_m:.1f} м   ·   Масса {self.simulator.can.get_current_data().total_mass_kg:,.0f} кг")
        self.state_label.setText("ГОТОВ К СТАРТУ")
        self.start_button.setEnabled(self.thread is None)
        self.pause_button.setEnabled(False)
        self.reset_button.setEnabled(True)
        log.info("Симуляция сброшена")

    @Slot()
    def tick(self):
        now = time.perf_counter()
        # Cap wall time after dragging/window stalls to avoid a visible teleport.
        dt = min(now - self.last_tick, .5) * self.scale.currentData()
        self.last_tick = now
        state = self.simulator.step(dt)
        self.dashboard.update_state(state, self.simulator.length_m)
        self.charts.update_state(state)
        count = int(np.searchsorted(self.simulator.geometry_distances, state.current_distance_m, side="right"))
        self.map.update_progress(count, state.latitude, state.longitude)
        self.progress.setValue(round(1000 * state.current_distance_m / self.simulator.length_m))
        self.details.setText(f"Высота {state.elevation_m:.1f} м   ·   Повороты: до {state.curve_speed_limit_kmh:.0f} км/ч   ·   {'ИИ' if self.ai.isChecked() else 'Ручной режим'}")
        if state.completed:
            self.timer.stop()
            self.state_label.setText("МАРШРУТ ЗАВЕРШЁН")
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            summary = self.simulator.summary()
            message = (f"Время в пути: {format_time(summary.travel_time_s)}\n"
                       f"Расстояние: {summary.distance_km:.2f} км\nИзрасходовано: {summary.fuel_used_l:.2f} л\n"
                       f"Средний расход: {summary.average_fuel_l_100km:.1f} л/100 км\n"
                       f"Средняя скорость: {summary.average_speed_kmh:.1f} км/ч")
            log.info("Маршрут завершён: %s", summary)
            dialog = QMessageBox(QMessageBox.Icon.Information, "Маршрут завершён", message, parent=self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.open()

    def closeEvent(self, event):
        self.timer.stop()
        if self.thread is not None:
            self.closing = True
            self.statusBar().showMessage("Ожидание завершения запроса перед закрытием…")
            event.ignore()
            return
        if self.simulator:
            self.simulator.can.close()
        event.accept()
