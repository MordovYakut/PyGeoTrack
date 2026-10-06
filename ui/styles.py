from config import settings as cfg

STYLE = """
QMainWindow, QWidget { background: #101923; color: #e7eff7; font-family: 'Segoe UI'; font-size: 12px; }
QFrame#card, QFrame#panel { background: #182533; border: 1px solid #293a4c; border-radius: 10px; }
QLabel { background: transparent; border: none; }
QLabel#title { font-size: 23px; font-weight: 700; }
QLabel#subtitle { color: #91a6bb; font-size: 12px; }
QLabel#metric { font-size: 24px; font-weight: 600; color: #f0f6fc; }
QLabel#accent { font-size: 24px; font-weight: 700; color: #4be1bf; }
QPushButton { background: #24374c; border: 1px solid #3c536b; padding: 8px 13px; border-radius: 6px; font-weight: 600; }
QPushButton:hover { background: #35506a; }
QPushButton:disabled { color: #63758a; background: #1b2937; }
QPushButton#start { background: #2bc7a3; color: #062f28; border: none; }
QDoubleSpinBox { background: #1c2b3c; border: 1px solid #3b4c60; border-radius: 5px; padding: 2px 34px 2px 7px; }
QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; top: 1px; right: 1px; width: 28px; height: 18px; background: #30465d; border-top-right-radius: 4px; }
QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; bottom: 1px; right: 1px; width: 28px; height: 18px; background: #30465d; border-bottom-right-radius: 4px; }
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #496881; }
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed { background: #258c79; }
QDoubleSpinBox::up-arrow { image: url(ICON_PATH/up.svg); width: 10px; height: 7px; }
QDoubleSpinBox::down-arrow { image: url(ICON_PATH/down.svg); width: 10px; height: 7px; }
QComboBox { background: #1c2b3c; border: 1px solid #3b4c60; border-radius: 5px; padding: 5px; min-height: 18px; }
QCheckBox { spacing: 9px; font-weight: 600; }
QCheckBox::indicator { width: 17px; height: 17px; }
QStatusBar { color: #9db1c5; background: #152231; }
QSplitter::handle { background: #101923; width: 10px; }
QProgressBar { background: #253447; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #4be1bf; border-radius: 3px; }
""".replace("ICON_PATH", (cfg.ROOT / "ui" / "icons").as_posix())
