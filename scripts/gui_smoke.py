"""Runs the real Qt/WebEngine application through its control lifecycle."""
import json
import logging
import time
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox
from config import settings as cfg


def install_smoke_test(app, window):
    log = logging.getLogger(__name__)
    artifacts = cfg.ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    started = time.monotonic()
    report = {}

    def fail(exc):
        log.error("GUI smoke failed: %s", exc)
        (artifacts / "gui_smoke.json").write_text(json.dumps({"passed": False, "error": str(exc)}), encoding="utf-8")
        window.timer.stop()
        app.exit(1)

    def guard(func):
        def wrapped(*args):
            try:
                func(*args)
            except Exception as exc:
                fail(exc)
        return wrapped

    @guard
    def start_drive():
        if window.thread is not None or not window.map.ready:
            QTimer.singleShot(100, start_drive)
            return
        window.grab().save(str(artifacts / "gui_initial.png"))
        assert window.simulator.length_m >= 100000
        window.ai.setChecked(False)
        option = QStyleOptionSpinBox()
        window.manual.initStyleOption(option)
        rect = window.manual.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option,
                                                   QStyle.SubControl.SC_SpinBoxUp, window.manual)
        old = window.manual.value()
        QTest.mouseClick(window.manual, Qt.MouseButton.LeftButton, pos=rect.center())
        assert window.manual.value() == old + window.manual.singleStep()
        window.manual.setValue(old)
        window.ai.setChecked(True)
        assert len(window.charts.full[0].getData()[0]) == len(window.bundle.original)
        assert window.charts.estimated[1].getData()[0][0] == cfg.PREDICTION_DISTANCE_M / 1000
        report["speed_arrow"] = True
        report["original_and_prediction_charts"] = True
        window.scale.setCurrentIndex(window.scale.findData(20))
        window.start_button.click()
        QTimer.singleShot(1800, pause_drive)

    @guard
    def pause_drive():
        window.pause_button.click()
        assert window.simulator.state.current_distance_m > 100
        frozen = window.simulator.state.current_distance_m
        window.simulator.step(10)
        assert window.simulator.state.current_distance_m == frozen
        report["start_pause"] = True
        window.reset_button.click()
        assert window.simulator.state.fuel_used_l == window.simulator.state.current_distance_m == 0
        cleared = window.charts.passed[0].getData()[0]
        assert cleared is None or len(cleared) == 0
        report["reset"] = True
        window.start_button.click()
        window.timer.stop()
        QTimer.singleShot(0, finish_trip)

    @guard
    def finish_trip():
        for _ in range(10):
            window.simulator.step(10)
            if window.simulator.state.completed:
                break
        window.last_tick = time.perf_counter()
        window.tick()
        if window.simulator.state.current_distance_m > window.simulator.length_m * .35 and "running_screenshot" not in report:
            report["running_screenshot"] = True
            QTimer.singleShot(500, capture_running)
            return
        if window.simulator.state.completed:
            assert window.simulator.state.speed_kmh == 0
            assert window.progress.value() == 1000
            report["completed"] = True
            QTimer.singleShot(500, check_map)
        else:
            QTimer.singleShot(0, finish_trip)

    @guard
    def capture_running():
        window.grab().save(str(artifacts / "gui_running.png"))
        assert window.start_button.visibleRegion().boundingRect().height() > 0
        QTimer.singleShot(0, finish_trip)

    @guard
    def check_map():
        window.grab().save(str(artifacts / "gui_completed.png"))
        window.map.page().runJavaScript(
            "JSON.stringify({ready:window.mapReady,leaflet:!!window.L,route:routePoints.length,passed:passedPoints.length,tiles:tileLoaded,vehicle:vehiclePosition,end:routePoints[routePoints.length-1]})", checked)

    @guard
    def checked(value):
        data = json.loads(value)
        assert data["ready"] and data["leaflet"] and data["route"] > 100
        assert data["vehicle"] == data["end"]
        assert data["passed"] >= data["route"]
        report.update({"map": data, "passed": True, "elapsed_s": time.monotonic() - started})
        (artifacts / "gui_smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.info("GUI SMOKE PASSED: %s", report)
        window.close()
        app.quit()

    window.route_loaded.connect(lambda: QTimer.singleShot(100, start_drive))
    QTimer.singleShot(60000, lambda: fail("60-second GUI smoke timeout"))
