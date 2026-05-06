"""Unit tests for the 1D FDM absorber-plate solver."""
from dataclasses import replace

import numpy as np
import pytest

from app.services.fdm import PlateProps, SIGMA, stable_dt, steady_state, transient


T_INF = 298.15  # K


def test_steady_state_monotone_in_irradiance():
    props = PlateProps()
    temps = [steady_state(I, T_INF, props) for I in (300, 500, 800)]
    assert temps[0] < temps[1] < temps[2]


def test_steady_state_above_ambient_for_positive_flux():
    """Any positive solar input must drive the plate above ambient."""
    props = PlateProps()
    assert steady_state(300, T_INF, props) > T_INF


def test_steady_state_returns_ambient_for_zero_flux():
    """With I=0 and T0=T∞, the only stable point is T = T_sky-shifted equilibrium.

    With ε > 0 the plate sees a net radiation loss to a colder sky, so the
    equilibrium plate temperature sits slightly *below* ambient. With ε = 0 the
    plate equilibrates exactly at ambient (no driving force).
    """
    props_norad = replace(PlateProps(), epsilon=0.0)
    assert steady_state(0.0, T_INF, props_norad) == pytest.approx(T_INF, abs=1e-3)


def test_transient_converges_to_steady_state():
    """Time-marched solution at large t must equal the Newton-iteration steady T."""
    props = PlateProps()
    for I in (300, 500, 800):
        _, T = transient(I=I, T_inf=T_INF, t_end=3600.0, props=props)
        T_ss = steady_state(I, T_INF, props)
        assert abs(T[-1] - T_ss) < 0.5, f"I={I}: |Δ| = {abs(T[-1] - T_ss):.4e} K"


def test_transient_starts_at_initial_condition():
    props = PlateProps()
    T0 = 310.0
    _, T = transient(I=500, T_inf=T_INF, T0=T0, t_end=10.0, props=props)
    assert T[0] == T0


def test_transient_monotone_rising_from_ambient():
    """At I=800, plate heats up monotonically from ambient until equilibrium."""
    props = PlateProps()
    _, T = transient(I=800, T_inf=T_INF, T0=T_INF, t_end=600.0, props=props)
    # First derivative non-negative everywhere within numerical tolerance.
    diffs = np.diff(T)
    assert (diffs >= -1e-9).all()


def test_stable_dt_positive_and_uses_safety_factor():
    props = PlateProps()
    dt = stable_dt(props, T_ref=350.0, safety=0.5)
    h_eff = props.h_conv + 4 * props.epsilon * SIGMA * 350.0**3
    upper = props.rho * props.cp * props.delta / h_eff
    assert 0 < dt < upper
    assert dt == pytest.approx(0.5 * upper)


def test_no_radiation_recovers_simple_balance():
    """With ε=0, steady T = T∞ + α·I / h."""
    props = replace(PlateProps(), epsilon=0.0)
    I = 500.0
    T_pred = T_INF + props.alpha_solar * I / props.h_conv
    assert steady_state(I, T_INF, props) == pytest.approx(T_pred, abs=1e-3)
