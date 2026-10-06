import pytest
from models.fuel_model import FuelModel


def test_mass_increases_forces():
    model = FuelModel()
    a, b = [model.calculate(60, mass, 5) for mass in (9000, 14000)]
    assert b.rolling_force_n > a.rolling_force_n
    assert b.grade_force_n > a.grade_force_n
    assert b.fuel_l_h > a.fuel_l_h


def test_uphill_consumes_more():
    f = FuelModel()
    assert f.calculate(60, 14000, 5).fuel_l_h > f.calculate(60, 14000, 0).fuel_l_h


@pytest.mark.parametrize("speed,slope", [(0, 0), (60, -25), (90, 25), (.1, -5)])
def test_finite_nonnegative(speed, slope):
    result = FuelModel().calculate(speed, 14000, slope)
    assert result.fuel_l_h >= 0
    assert result.traction_power_kw >= 0
    if speed < 1:
        assert result.fuel_l_per_100km is None


def test_acceleration_energy():
    model = FuelModel()
    assert model.calculate(40, 14000, 0, 1).fuel_l_h > model.calculate(40, 14000, 0).fuel_l_h


def test_invalid_inputs():
    with pytest.raises(ValueError):
        FuelModel().calculate(float("nan"), 14000, 0)
