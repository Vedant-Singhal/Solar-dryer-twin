import math
from app.services.physics import (
    apply_wind_to_trays,
    lewis_drying_time,
    thermal_efficiency,
    wind_correction,
)


def test_wind_correction_zero_when_no_wind():
    r = wind_correction(t_cover_c=60, ambient_c=25, wind_mps=0, heat_flux_w_m2=600)
    assert r.loss_fraction == 0.0


def test_wind_correction_increases_with_wind_speed():
    a = wind_correction(60, 25, 2, 600).loss_fraction
    b = wind_correction(60, 25, 6, 600).loss_fraction
    assert b >= a >= 0
    assert b <= 0.5  # capped


def test_apply_wind_keeps_trays_above_ambient():
    temps = (60.0, 50.0, 40.0, 35.0)
    out = apply_wind_to_trays(temps, ambient_c=25.0, loss_fraction=0.3)
    for t_in, t_out in zip(temps, out):
        assert t_out >= 25.0
        assert t_out <= t_in


def test_lewis_drying_time_decreases_with_temperature():
    fast, _ = lewis_drying_time(60, "tomato", 9.0, 0.15)
    slow, _ = lewis_drying_time(35, "tomato", 9.0, 0.15)
    assert slow > fast > 0
    assert math.isfinite(fast)


def test_thermal_efficiency_bounded():
    eff = thermal_efficiency(t_outlet_c=35, t_inlet_c=25, heat_flux=600)
    assert 0.0 <= eff <= 1.0
