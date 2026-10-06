import json
import logging
from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from config import settings as cfg


class MapWidget(QWebEngineView):
    map_ready = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.ready = False
        self.points = []
        self.last_progress = None
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.loadFinished.connect(self._loaded)
        self.setUrl(QUrl.fromLocalFile(str(cfg.RESOURCE_ROOT / "map" / "map.html")))

    def _loaded(self, ok: bool) -> None:
        self.ready = ok
        self.map_ready.emit(ok)
        if ok and self.points:
            self.set_route(self.points)
            if self.last_progress:
                self.update_progress(*self.last_progress)
        elif not ok:
            logging.getLogger(__name__).error("Не удалось загрузить HTML карты")

    def set_route(self, points: list) -> None:
        self.points = points
        if self.ready:
            self.page().runJavaScript(f"initializeRoute({json.dumps(points)});")

    def update_progress(self, count: int, latitude: float, longitude: float) -> None:
        self.last_progress = count, latitude, longitude
        if self.ready:
            self.page().runJavaScript(f"updateProgress({count},{latitude},{longitude});")

    def reset(self) -> None:
        self.last_progress = None
        if self.ready:
            self.page().runJavaScript("resetVehicle();")
