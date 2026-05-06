"""1D unsteady absorber-plate energy balance — Finite Difference Method (explicit Euler).

Lumped-capacitance form (justified by Bi ≈ 6×10⁻⁴ << 0.1):

    ρ·cp·δ · dT/dt = α·I − h·(T − T∞) − ε·σ·(T⁴ − T_sky⁴)

The plate is a single thermal node; spatial gradients across its 2 mm thickness
are negligible. We integrate in time with explicit Euler. Stability bound for
the linearised problem is:

    Δt < ρ·cp·δ / h_eff,    h_eff = h + 4·ε·σ·T̄³

We apply a safety factor of 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Stefan–Boltzmann constant
SIGMA = 5.67e-8  # W/m²·K⁴


@dataclass(frozen=True)
class PlateProps:
    """Material and radiative properties of the absorber plate.

    Defaults are for a 2 mm steel plate with a selective solar coating
    (technical_context_dossier.md, section 7.1).
    """
    rho: float = 7800.0          # kg/m³        density
    cp: float = 470.0            # J/kg·K       specific heat
    delta: float = 0.002         # m            thickness
    alpha_solar: float = 0.9     # –            solar absorptivity
    epsilon: float = 0.1         # –            longwave emissivity
    h_conv: float = 8.0          # W/m²·K       convective HTC; chimney Re≈350 laminar
    sky_offset_k: float = 6.0    # K            T_sky = T∞ − offset


def steady_state(I: float, T_inf: float, props: PlateProps = PlateProps()) -> float:
    """Solve for steady-state plate temperature by Newton iteration.

    At steady state dT/dt = 0:
        α·I = h·(T − T∞) + ε·σ·(T⁴ − T_sky⁴)
    """
    T_sky = T_inf - props.sky_offset_k
    T = T_inf + 20.0  # initial guess

    for _ in range(100):
        f = (
            props.alpha_solar * I
            - props.h_conv * (T - T_inf)
            - props.epsilon * SIGMA * (T**4 - T_sky**4)
        )
        df = -props.h_conv - 4.0 * props.epsilon * SIGMA * T**3
        dT = f / df
        T -= dT
        if abs(dT) < 1e-6:
            break
    return T


def stable_dt(props: PlateProps, T_ref: float = 350.0, safety: float = 0.5) -> float:
    """Stability-bound time step for explicit Euler.

    h_eff linearises the radiative loss around T_ref.
    """
    h_eff = props.h_conv + 4.0 * props.epsilon * SIGMA * T_ref**3
    return safety * props.rho * props.cp * props.delta / h_eff


def transient(
    I: float,
    T_inf: float,
    *,
    T0: float | None = None,
    t_end: float = 1800.0,
    dt: float | None = None,
    props: PlateProps = PlateProps(),
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate the lumped energy balance from T0 to t_end.

    Returns (t_array_seconds, T_array_kelvin).
    """
    if T0 is None:
        T0 = T_inf
    if dt is None:
        dt = stable_dt(props)

    T_sky = T_inf - props.sky_offset_k
    rho_cp_delta = props.rho * props.cp * props.delta

    n = int(np.ceil(t_end / dt)) + 1
    t = np.linspace(0.0, dt * (n - 1), n)
    T = np.empty(n)
    T[0] = T0

    for i in range(n - 1):
        q_net = (
            props.alpha_solar * I
            - props.h_conv * (T[i] - T_inf)
            - props.epsilon * SIGMA * (T[i] ** 4 - T_sky**4)
        )
        T[i + 1] = T[i] + dt * q_net / rho_cp_delta
    return t, T
