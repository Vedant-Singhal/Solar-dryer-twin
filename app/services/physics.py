"""Post-surrogate physics: wind correction + Lewis drying kinetics + efficiency.

Constants and correlations are sourced from the project dossier (sec 7-8).
Values are engineering approximations adequate for the dryer's operating envelope.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

# Air properties at ~310 K, 1 atm
RHO_AIR = 1.13          # kg/m^3
CP_AIR = 1007.0         # J/(kg*K)
MU_AIR = 1.9e-5         # Pa*s
K_AIR = 0.027           # W/(m*K)
PR_AIR = 0.71

# Geometry (dossier sec 3)
COVER_LENGTH = 2.0      # m, characteristic length along wind
COVER_AREA = 1.0        # m^2, ~ 2 m x 0.5 m
INLET_AREA = 0.005      # m^2
INLET_VELOCITY = 0.01   # m/s

# Crop kinetics (Lewis thin-layer), Arrhenius k(T) = k0 * exp(-Ea/RT).
# k0 has units of [1/s]; calibrated against published solar-drying k values
# (~0.3-0.6 /hr at 55-60 C) so that drying times are within the literature range
# of 8-20 hours for tomato slices. Replace with measured values when the
# derivations doc has lab-fitted constants.
R_GAS = 8.314           # J/(mol*K)
CROP_PARAMS = {
    # k0 [1/s], Ea [J/mol]
    "tomato": (1.0,  25_000),
    "mango":  (0.7,  27_000),
    "chilli": (1.5,  24_000),
    "onion":  (0.9,  26_000),
}

MAX_LOSS_FRACTION = 0.5  # cap wind-driven cover loss at 50% of incident solar


@dataclass(frozen=True)
class WindResult:
    """Loss fraction (0..MAX_LOSS_FRACTION) of incident solar diverted by wind, plus h_wind for diagnostics."""
    loss_fraction: float
    h_wind: float


def wind_correction(
    t_cover_c: float,
    ambient_c: float,
    wind_mps: float,
    heat_flux_w_m2: float,
) -> WindResult:
    """Compute wind-driven cover heat loss as a fraction of incident solar.

    Uses flat-plate forced-convection Nu correlation:
        laminar  (Re < 5e5):  Nu = 0.664 * Re^0.5 * Pr^(1/3)
        turbulent (Re >= 5e5): Nu = 0.037 * Re^0.8 * Pr^(1/3)

    The loss fraction is then applied per-tray by the caller as
        T_corrected = T_baseline - loss_fraction * (T_baseline - ambient)
    so each tray's rise above ambient is shrunk proportionally to wind heat loss.
    This avoids the trap of dividing heat loss by the dryer's tiny natural-
    convection mass flow, which produced unphysical >100 K deltas in earlier
    formulations.
    """
    if wind_mps <= 0 or heat_flux_w_m2 <= 0:
        return WindResult(loss_fraction=0.0, h_wind=0.0)

    re = RHO_AIR * wind_mps * COVER_LENGTH / MU_AIR
    if re < 5e5:
        nu = 0.664 * (re ** 0.5) * (PR_AIR ** (1 / 3))
    else:
        nu = 0.037 * (re ** 0.8) * (PR_AIR ** (1 / 3))
    h_wind = nu * K_AIR / COVER_LENGTH

    q_loss = h_wind * COVER_AREA * max(t_cover_c - ambient_c, 0.0)
    q_incident = heat_flux_w_m2 * COVER_AREA
    loss_fraction = min(q_loss / q_incident, MAX_LOSS_FRACTION)
    return WindResult(loss_fraction=loss_fraction, h_wind=h_wind)


def apply_wind_to_trays(
    temps_c: tuple[float, float, float, float],
    ambient_c: float,
    loss_fraction: float,
) -> tuple[float, float, float, float]:
    """Reduce each tray's rise above ambient by the wind loss fraction."""
    return tuple(
        t - loss_fraction * max(t - ambient_c, 0.0)
        for t in temps_c
    )  # type: ignore[return-value]


def lewis_drying_time(
    tray_temp_c: float,
    crop: str,
    initial_moisture_db: float,
    target_moisture_db: float,
    equilibrium_moisture_db: float = 0.05,
) -> tuple[float, float]:
    """Return (drying_time_hours, k_per_hour) for a single tray using Lewis MR=exp(-kt).

    k(T) = k0 * exp(-Ea / R T)
    """
    k0, ea = CROP_PARAMS.get(crop, CROP_PARAMS["tomato"])
    t_kelvin = tray_temp_c + 273.15
    k_per_s = k0 * math.exp(-ea / (R_GAS * t_kelvin))
    k_per_hour = k_per_s * 3600.0

    mr_target = max(
        (target_moisture_db - equilibrium_moisture_db)
        / (initial_moisture_db - equilibrium_moisture_db),
        1e-6,
    )
    if k_per_hour <= 0:
        return float("inf"), 0.0
    time_h = -math.log(mr_target) / k_per_hour
    return time_h, k_per_hour


def thermal_efficiency(t_outlet_c: float, t_inlet_c: float, heat_flux: float) -> float:
    """eta = m*cp*dT / (I*A_collector). Returns dimensionless fraction."""
    m_dot = RHO_AIR * INLET_VELOCITY * INLET_AREA
    useful_w = m_dot * CP_AIR * max(t_outlet_c - t_inlet_c, 0.0)
    incident_w = heat_flux * COVER_AREA
    if incident_w <= 0:
        return 0.0
    return useful_w / incident_w
