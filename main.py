"""Desktop entry point: python main.py. Use --smoke-test for automated GUI checks."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from config import settings as cfg


def configure_logging() -> None:
    handlers = [logging.StreamHandler()]
    try:
        folder = cfg.ROOT / "logs"
        folder.mkdir(exist_ok=True)
        handlers.append(RotatingFileHandler(folder / "application.log", maxBytes=2_000_000,
                                            backupCount=2, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)


def main() -> int:
    parser = argparse.ArgumentParser(description="PyGeoTrack — симулятор движения")
    parser.add_argument("--smoke-test", action="store_true", help="Проверить интерфейс, сохранить снимки и выйти")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")
    cfg.prepare_runtime_files()
    configure_logging()
    try:
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
    except ImportError:
        logging.exception("Не установлены зависимости. Выполните: python -m pip install -r requirements.txt")
        return 1
    app = QApplication(sys.argv[:1])
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
    translator = QTranslator(app)
    translator.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    app.installTranslator(translator)
    app.setApplicationName("PyGeoTrack")
    app.setOrganizationName("PyGeoTrack")
    window = MainWindow()
    if args.smoke_test:
        from scripts.gui_smoke import install_smoke_test
        install_smoke_test(app, window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
