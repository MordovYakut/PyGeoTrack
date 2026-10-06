"""Qt tests use offscreen; WebEngine is exercised separately by --smoke-test."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QStyleOptionSpinBox, QStyle
from ui.styles import STYLE
from ui.charts import RouteCharts


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_spinbox_arrow_hitboxes(app):
    field = QDoubleSpinBox()
    field.setStyleSheet(STYLE)
    field.resize(160, 38)
    field.setFixedHeight(38)
    field.setRange(30, 90)
    field.show()
    app.processEvents()
    option = QStyleOptionSpinBox()
    field.initStyleOption(option)
    rectangles = []
    for control, delta in ((QStyle.SubControl.SC_SpinBoxUp, 1), (QStyle.SubControl.SC_SpinBoxDown, -1)):
        rectangle = field.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, control, field)
        rectangles.append(rectangle)
        assert rectangle.width() >= 24 and rectangle.height() >= 16
        # Check the entire interior, including the area around the glyph.
        for x in range(rectangle.left() + 2, rectangle.right() - 1, 5):
            for y in range(rectangle.top() + 2, rectangle.bottom() - 1, 4):
                field.setValue(60)
                QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
                assert field.value() == 60 + delta
    assert not rectangles[0].intersects(rectangles[1])
    field.close()


def test_charts_compare_original_and_predictions_at_target_distance(app, route):
    original = route.copy()
    restored = route.copy()
    restored.loc[5:9, "elevation_m"] += 20
    restored.loc[5:9, "is_restored"] = 1
    restored["predicted_slope_pct"] = np.arange(len(route), dtype=float)
    restored["prediction_available"] = (route.total_distance_m + 300 <= route.total_distance_m.iloc[-1]).astype(int)
    charts = RouteCharts()
    charts.set_route(restored, original)
    assert np.array_equal(charts.full[0].getData()[1], original.elevation_m)
    assert np.array_equal(charts.full[1].getData()[1], original.slope_pct)
    assert np.array_equal(charts.estimated[0].getData()[1], restored.elevation_m)
    x, y = charts.estimated[1].getData()
    valid = restored.prediction_available == 1
    assert np.allclose(x, route.loc[valid, "total_distance_m"] / 1000 + .3)
    assert np.array_equal(y, restored.loc[valid, "predicted_slope_pct"])
    charts.reset()
    assert len(charts.full[0].getData()[0]) == len(route)
    charts.close()
