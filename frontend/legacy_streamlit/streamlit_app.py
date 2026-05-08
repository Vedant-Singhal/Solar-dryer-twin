"""Solar Dryer Digital Twin — Streamlit frontend (CLL251 IIT Delhi).

A multi-tab dashboard that exposes all four layers of the modelling stack
described in the project report:

    1. Live Twin            — surrogate-backed real-time tray prediction
    2. 1D FDM (transient)   — lumped-capacitance absorber-plate solver
    3. Parametric Sweeps    — heat-flux and porosity scans (Figs 7-style)
    4. Validation           — surrogate metrics & four-layer stack
    5. Economics            — cost-per-kg vs diesel / electric drying

The tray indexing follows the report: Tray 1 = bottom (hottest),
Tray 4 = top (coolest). T1 > T2 > T3 > T4 verified across 102 CFD cases.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ────────────────────────────────────────────────────────────────────────────
# Page config
# ────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Solar Dryer Digital Twin · CLL251 IIT Delhi",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────────────────────────────────
# Constants — match the report
# ────────────────────────────────────────────────────────────────────────────
try:
    API = st.secrets["API_URL"].rstrip("/")
except Exception:
    API = "http://localhost:8000"

# Tray 1 = bottom (hottest, red), Tray 4 = top (coolest, blue) — see report §3.2 / §4.1
TRAY_LABELS = ["Tray 1 (bottom)", "Tray 2", "Tray 3", "Tray 4 (top)"]
TRAY_COLORS = ["#D7263D", "#F46036", "#2E86AB", "#1B4965"]

CROP_DESCRIPTIONS = {
    "tomato": "Tomato (Lycopersicum esculentum)",
    "mango":  "Mango (Mangifera indica)",
    "chilli": "Chilli (Capsicum annuum)",
    "onion":  "Onion (Allium cepa)",
}

# Physical constants for the live dimensionless-number panel (matches app/services/physics.py).
RHO_AIR = 1.13         # kg/m³ at ~310 K
MU_AIR  = 1.9e-5       # Pa·s
K_AIR   = 0.027        # W/(m·K)
PR_AIR  = 0.71
G       = 9.81         # m/s²
BETA    = 1.0 / 310.0  # K⁻¹, ideal-gas thermal expansion at ~310 K
NU_AIR  = MU_AIR / RHO_AIR
ALPHA_AIR = K_AIR / (RHO_AIR * 1007.0)
COVER_LENGTH = 2.0     # m (along absorber)
CHIMNEY_LENGTH = 1.0   # m (vertical)
PLATE_DELTA = 0.002    # m (2 mm steel)
K_PLATE = 50.0         # W/(m·K)
H_CONV_DEFAULT = 15.0  # W/(m²·K), chimney-side convection guess

# Validation metrics — load from artifact if present, else fall back to report values.
METRICS_PATH = Path(__file__).resolve().parents[2] / "models" / "surrogate-v1.metrics.json"
try:
    METRICS = json.loads(METRICS_PATH.read_text())
except Exception:
    METRICS = {
        "degree": 3,
        "r2_overall": 0.989,
        "r2_per_tray": [0.996, 0.993, 0.987, 0.981],
        "mae_per_tray_k": [0.248, 0.191, 0.154, 0.114],
        "n_train": 81,
        "n_test": 21,
    }


# ────────────────────────────────────────────────────────────────────────────
# Backend helpers
# ────────────────────────────────────────────────────────────────────────────
def _post(path: str, payload: dict, timeout: float = 30.0):
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot reach the API server at `{API}`. Make sure the backend is running.")
    except requests.exceptions.Timeout:
        st.error(f"API timeout (>{timeout:.0f}s). On Render free tier, first request can take ~30s — try again.")
    except requests.exceptions.HTTPError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
    except Exception as exc:  # noqa: BLE001 — last-resort guard against unexpected errors
        st.error(f"Unexpected backend error: {type(exc).__name__}: {exc}")
    return None


def call_simulate(payload: dict):
    return _post("/v1/simulate", payload)


def call_predict(payload: dict):
    return _post("/v1/predict", payload, timeout=15.0)


def call_fdm(payload: dict):
    return _post("/v1/fdm/transient", payload, timeout=30.0)


@st.cache_data(ttl=300, show_spinner=False)
def cached_predict(heat_flux: float, porosity: float, ambient_c: float, wind_mps: float):
    return call_predict({
        "heat_flux": heat_flux,
        "porosity":  porosity,
        "ambient_c": ambient_c,
        "wind_mps":  wind_mps,
    })


@st.cache_data(ttl=300, show_spinner=False)
def cached_fdm(heat_flux: float, ambient_c: float, t_end_s: float):
    return call_fdm({"heat_flux": heat_flux, "ambient_c": ambient_c, "t_end_s": t_end_s})


# ────────────────────────────────────────────────────────────────────────────
# Dimensionless-group helpers (live panel in tab 1)
# ────────────────────────────────────────────────────────────────────────────
def dimensionless_groups(wind_mps: float, t_plate_c: float, ambient_c: float) -> dict:
    """Return Bi, Re_chimney, Re_wind, Ra, Pr, Nu_free, Nu_forced for the inputs."""
    dT = max(t_plate_c - ambient_c, 0.5)
    re_chim = RHO_AIR * 0.01 * CHIMNEY_LENGTH / MU_AIR  # natural-draft inlet ≈ 0.01 m/s
    re_wind = RHO_AIR * max(wind_mps, 1e-3) * COVER_LENGTH / MU_AIR
    ra = G * BETA * dT * (CHIMNEY_LENGTH ** 3) / (NU_AIR * ALPHA_AIR)
    bi = H_CONV_DEFAULT * PLATE_DELTA / K_PLATE
    nu_free = 0.59 * (ra ** 0.25)
    nu_forced = 0.664 * (re_wind ** 0.5) * (PR_AIR ** (1 / 3))
    return {
        "Bi":   bi,
        "Re_chimney": re_chim,
        "Re_wind":    re_wind,
        "Ra":   ra,
        "Pr":   PR_AIR,
        "Nu_free":    nu_free,
        "Nu_forced":  nu_forced,
    }


# ════════════════════════════════════════════════════════════════════════════
# Sidebar — global inputs
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ☀️ Solar Dryer Digital Twin")
    st.caption("CLL251 · Heat Transfer for Chemical Engineers · IIT Delhi")
    st.divider()

    st.markdown("#### ☀️ Environmental")
    heat_flux = st.slider("Solar irradiance I (W/m²)", 300, 800, 600, step=10,
                          help="Validated CFD envelope: 300–800 W/m².")
    ambient_c = st.slider("Ambient temperature T∞ (°C)", 15, 40, 25)
    wind_mps  = st.slider("Wind speed (m/s)", 0.0, 8.0, 2.0, step=0.5,
                          help="Affects glass-cover heat loss via flat-plate Nu correlation.")

    st.markdown("#### 🌾 Crop & Bed")
    porosity = st.slider("Crop-bed porosity ϕ", 0.50, 0.90, 0.70, step=0.01,
                         help="Fraction of bed volume that is open. CFD envelope: 0.5–0.9.")
    crop_key = st.selectbox("Crop", list(CROP_DESCRIPTIONS.keys()),
                            format_func=lambda k: CROP_DESCRIPTIONS[k])
    initial_pct = st.slider("Initial moisture (% d.b.)", 50, 95, 90)
    target_pct  = st.slider("Target moisture (% d.b.)", 5, 30, 10)

    st.divider()
    run = st.button("▶  Run Simulation", use_container_width=True, type="primary")

    st.caption(f"Backend: `{API}`")


# ════════════════════════════════════════════════════════════════════════════
# Hero
# ════════════════════════════════════════════════════════════════════════════
# Plotly template: 'plotly' is theme-neutral (transparent bg, inherits text color),
# so charts look correct in both light and dark Streamlit themes without runtime
# theme detection (st.context.theme requires Streamlit >= 1.45).
PLOTLY_TEMPLATE = "plotly"
SUBTLE_TEXT = "#888"

st.markdown(
    f"""
    <div style="padding:1.5rem 0 0.75rem 0;">
      <h1 style="margin:0;font-size:2.4rem;">☀️ Solar Dryer Digital Twin</h1>
      <p style="margin:0.4rem 0 0 0;color:{SUBTLE_TEXT};font-size:1.05rem;">
        A CFD-trained four-layer thermal model for an agricultural solar air dryer ·
        <b>real-time</b> tray prediction · Lewis drying kinetics · validated against 102 CFD design points
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Validation badges + audience pitch
b1, b2, b3, b4 = st.columns(4)
b1.metric("Surrogate R² (overall)", f"{METRICS['r2_overall']:.3f}", "≥ 0.98 target")
b2.metric("Worst-tray MAE", f"{max(METRICS['mae_per_tray_k']):.2f} K", "≤ 0.5 K target")
b3.metric("CFD design points", f"{METRICS['n_train'] + METRICS['n_test']}", "Ansys Fluent")
b4.metric("Inference latency", "< 1 ms", "vs CFD: hours")

with st.expander("📌 Who is this dashboard for?", expanded=False):
    a1, a2, a3 = st.columns(3)
    a1.markdown(
        "**👨‍🌾 Smallholder farmer**\n\n"
        "Schedule drying runs against weather forecasts. Will tomorrow's irradiance be "
        "high enough to finish a tomato batch in one day?"
    )
    a2.markdown(
        "**🛠️ Dryer designer**\n\n"
        "Explore the absorber-area / chimney-geometry / porosity design space "
        "without rerunning hour-long CFD simulations."
    )
    a3.markdown(
        "**🌐 Extension worker**\n\n"
        "Benchmark solar drying against diesel- or electric-powered alternatives "
        "on a cost-per-kg-of-moisture-removed basis."
    )

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# Run simulation (shared by all tabs)
# ════════════════════════════════════════════════════════════════════════════
if "data" not in st.session_state:
    st.session_state["data"] = None
    st.session_state["last_inputs"] = None

current_inputs = (heat_flux, porosity, ambient_c, wind_mps, crop_key, initial_pct, target_pct)

if run or st.session_state["data"] is None or st.session_state["last_inputs"] != current_inputs:
    payload = {
        "heat_flux":            heat_flux,
        "porosity":             porosity,
        "ambient_c":            float(ambient_c),
        "wind_mps":             float(wind_mps),
        "crop":                 crop_key,
        "initial_moisture_db":  initial_pct / 100.0 * 9.0 / 0.9,  # rough scaling so default still gives ~9 d.b.
        "target_moisture_db":   target_pct / 100.0,
    }
    # The schema bounds initial_moisture_db to (0, 15]; clamp safely.
    payload["initial_moisture_db"] = max(0.5, min(payload["initial_moisture_db"], 14.5))
    with st.spinner("Calling backend (first call on Render free tier may take ~30s)…"):
        d = call_simulate(payload)
    if d:
        st.session_state["data"] = d
        st.session_state["last_inputs"] = current_inputs

data = st.session_state["data"]
if data is None:
    st.info("Adjust the sidebar inputs and click **▶ Run Simulation** to populate every tab.")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# Tabs
# ════════════════════════════════════════════════════════════════════════════
tab_twin, tab_fdm, tab_sweep, tab_valid, tab_econ = st.tabs(
    ["🌡️ Live Twin", "🔬 1D FDM (Plate Transient)", "📈 Parametric Sweeps",
     "✅ Validation", "💰 Economics"]
)


# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — Live Twin
# ────────────────────────────────────────────────────────────────────────────
with tab_twin:
    temps     = data["temps"]
    trays     = data["trays"]
    eta       = data["thermal_efficiency"]
    wind_corr = data["wind_correction_k"]
    mv        = data["model_version"]
    temp_vals = [temps["t1_c"], temps["t2_c"], temps["t3_c"], temps["t4_c"]]

    # 1.1 — Tray temperature tiles (Tray 1 = bottom = hottest)
    st.markdown("### 🌡️ Tray Temperatures")
    st.caption("Predicted by the polynomial-regression surrogate (deg 3) trained on 102 CFD cases. "
               "Monotonic descent T₁ > T₂ > T₃ > T₄ verified across all CFD design points.")

    cols = st.columns(4)
    for i, (col, label, temp, color) in enumerate(zip(cols, TRAY_LABELS, temp_vals, TRAY_COLORS)):
        with col:
            st.markdown(
                f"""
                <div style='
                    background:{color};
                    border-radius:14px;
                    padding:18px 14px;
                    text-align:center;
                    color:white;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                '>
                    <div style='font-size:0.78rem;font-weight:700;letter-spacing:0.06em;opacity:0.95'>
                        {label.upper()}
                    </div>
                    <div style='font-size:2.5rem;font-weight:800;line-height:1.1;margin:8px 0'>
                        {temp:.1f}°C
                    </div>
                    <div style='font-size:0.75rem;opacity:0.85'>
                        {temp + 273.15:.1f} K
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Sanity check + wind annotation
    if not (temp_vals[0] >= temp_vals[1] >= temp_vals[2] >= temp_vals[3]):
        st.warning("⚠️ Monotonic descent T₁ ≥ T₂ ≥ T₃ ≥ T₄ violated — check inputs.")
    if abs(wind_corr) > 0.05:
        st.caption(f"🌬️ Wind correction applied to bottom tray: −{wind_corr:.2f} K "
                   f"(flat-plate Nu correlation, wind = {wind_mps} m/s)")

    st.divider()

    # 1.2 — Drying table + efficiency badge + dimensionless panel
    c_left, c_right = st.columns([3, 2])

    with c_left:
        st.markdown("### ⏱️ Drying Times (Lewis thin-layer model)")
        st.caption(f"MR(t) = exp(−k·t) · Crop: **{CROP_DESCRIPTIONS[crop_key]}** · "
                   f"Target moisture: **{target_pct}% d.b.**")

        df_dry = pd.DataFrame([
            {
                "Tray":               TRAY_LABELS[t["tray"] - 1],
                "Temperature (°C)":   round(t["temp_c"], 2),
                "k (h⁻¹)":            round(t["rate_constant_per_hour"], 4),
                "Drying time (h)":    round(t["drying_time_hours"], 2),
            }
            for t in trays
        ])
        st.dataframe(df_dry, use_container_width=True, hide_index=True)

    with c_right:
        st.markdown("### ⚡ Thermal Efficiency")
        eta_pct = eta * 100
        eta_color = "#2ecc71" if eta_pct >= 50 else "#f39c12" if eta_pct >= 30 else "#e74c3c"
        st.markdown(
            f"""
            <div style='background:{eta_color};border-radius:14px;padding:24px;text-align:center;color:white;'>
                <div style='font-size:0.78rem;font-weight:700;letter-spacing:0.08em;opacity:0.95'>
                    THERMAL EFFICIENCY
                </div>
                <div style='font-size:3rem;font-weight:900;line-height:1;margin:10px 0'>
                    {eta_pct:.1f}%
                </div>
                <div style='font-size:0.78rem;opacity:0.9'>
                    η = ṁ·cₚ·ΔT / (I·A)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Literature range for cabinet dryers: 30–55% (Sharma et al. 2009).")

    st.divider()

    # 1.3 — Moisture-ratio curve
    st.markdown("### 💧 Moisture Ratio vs. Time")
    st.caption("MR(t) = exp(−k·t) per tray · marker = drying complete · "
               "dashed line = target MR.")

    max_t = max(t["drying_time_hours"] for t in trays) * 1.2
    target_mr = math.exp(-trays[0]["rate_constant_per_hour"] * trays[0]["drying_time_hours"])

    fig_mr = go.Figure()
    t_arr = np.linspace(0, max_t, 250)
    for t, color in zip(trays, TRAY_COLORS):
        mr = np.exp(-t["rate_constant_per_hour"] * t_arr)
        fig_mr.add_trace(go.Scatter(
            x=t_arr, y=mr, mode="lines", name=TRAY_LABELS[t["tray"] - 1],
            line=dict(color=color, width=2.5),
            hovertemplate="t = %{x:.2f} h<br>MR = %{y:.3f}<extra></extra>",
        ))
        fig_mr.add_trace(go.Scatter(
            x=[t["drying_time_hours"]],
            y=[math.exp(-t["rate_constant_per_hour"] * t["drying_time_hours"])],
            mode="markers", marker=dict(color=color, size=11, symbol="circle"),
            showlegend=False,
            hovertemplate=f"Tray {t['tray']}: complete @ {t['drying_time_hours']:.2f} h<extra></extra>",
        ))
    fig_mr.add_hline(y=target_mr, line_dash="dash", line_color="grey",
                    annotation_text=f"Target MR = {target_mr:.3f}", annotation_position="bottom right")
    fig_mr.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis_title="Time (hours)", yaxis_title="Moisture ratio MR = M / M₀",
        yaxis=dict(range=[0, 1.05]), height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=40, b=60),
    )
    st.plotly_chart(fig_mr, use_container_width=True)

    # 1.4 — Live dimensionless-group panel
    st.markdown("### 🧮 Dimensionless Groups (live)")
    st.caption("Computed at the current operating point — the core CLL251 view of the dryer's transport regime.")

    dg = dimensionless_groups(wind_mps, temp_vals[0], ambient_c)
    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("Bi (plate)", f"{dg['Bi']:.1e}", "≪ 0.1 ⇒ lumped OK")
    g2.metric("Re (chimney)", f"{dg['Re_chimney']:.0f}", "Laminar (<2300)")
    g3.metric("Ra (chimney)", f"{dg['Ra']:.1e}", "Mixed convection")
    g4.metric("Pr (air)", f"{dg['Pr']:.2f}", "")
    g5.metric("Nu_free", f"{dg['Nu_free']:.1f}", f"Nu_forced ≈ {dg['Nu_forced']:.1f}")

    # 1.5 — CSV download
    st.divider()
    csv_buf = io.StringIO()
    df_dry.to_csv(csv_buf, index=False)
    st.download_button(
        "⬇ Download tray results (CSV)",
        csv_buf.getvalue(),
        file_name=f"solar_dryer_I{int(heat_flux)}_phi{porosity:.2f}.csv",
        mime="text/csv",
    )


# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — 1D FDM (transient absorber plate)
# ────────────────────────────────────────────────────────────────────────────
with tab_fdm:
    st.markdown("### 🔬 1D Finite-Difference Transient — Absorber Plate")
    st.markdown(
        "Lumped-capacitance energy balance from report §3.1, equation (2):"
    )
    st.latex(r"\rho_p c_{p,p}\,\delta_p\,\frac{\partial T_p}{\partial t} "
             r"= \alpha I - h_c(T_p - T_\infty) - \varepsilon\sigma\,(T_p^4 - T_{sky}^4)")
    st.caption(f"Discretised with explicit Euler. Biot ≈ 6×10⁻⁴ (≪ 0.1) justifies the lumped treatment. "
               f"This figure reproduces **Figure 1** of the report.")

    fdm_horizon_min = st.slider("Integration horizon (min)", 5, 90, 60, step=5,
                                 help="Plate reaches steady state in ~30 min across the envelope.")

    irr_levels = [300, 500, 800]
    fig_fdm = go.Figure()
    progress = st.progress(0.0, text="Solving FDM at three irradiance levels…")
    fdm_data: dict[int, dict] = {}
    for i, I in enumerate(irr_levels):
        progress.progress((i + 1) / (len(irr_levels) + 1), text=f"Solving I = {I} W/m²…")
        resp = cached_fdm(float(I), float(ambient_c), fdm_horizon_min * 60.0)
        if resp is None:
            continue
        fdm_data[I] = resp
        t_min = np.array(resp["t_seconds"]) / 60.0
        T_c = np.array(resp["T_celsius"])
        fig_fdm.add_trace(go.Scatter(
            x=t_min, y=T_c, mode="lines", name=f"I = {I} W/m²",
            line=dict(width=2.5),
            hovertemplate="t = %{x:.1f} min<br>T_p = %{y:.2f} °C<extra></extra>",
        ))
    progress.empty()

    fig_fdm.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis_title="Time (min)", yaxis_title="Plate temperature T_p (°C)",
        height=440, margin=dict(l=60, r=20, t=30, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_fdm, use_container_width=True)

    # Steady-state and dimensionless diagnostics from the FDM endpoint
    if fdm_data:
        st.markdown("#### Steady-state plate temperatures & FDM diagnostics")
        rows = []
        for I, resp in fdm_data.items():
            d = resp["dimensionless"]
            rows.append({
                "I (W/m²)":           I,
                "T_steady (K)":       round(resp["T_steady_kelvin"], 2),
                "T_steady (°C)":      round(resp["T_steady_kelvin"] - 273.15, 2),
                "Δt used (s)":        round(resp["dt_s"], 3),
                "Bi":                 f"{d['biot']:.2e}",
                "Pr":                 f"{d['prandtl']:.2f}",
                "h_eff (W/m²K)":      round(d["h_eff_w_m2k"], 1),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.info(
            "**Cross-check vs report Table 3 (FDM-vs-CFD).** The 1-D FDM lies within ~12 K "
            "of the CFD peak across the envelope — the residual is three-dimensional non-uniformity "
            "the lumped model cannot resolve."
        )


# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — Parametric Sweeps
# ────────────────────────────────────────────────────────────────────────────
with tab_sweep:
    st.markdown("### 📈 Parametric Sweeps")
    st.caption("Reproduces the design-of-experiments view of the report (Figure 7-style). "
               "Each curve is a surrogate prediction at the swept input, with the other input held fixed.")

    sweep_kind = st.radio("Sweep variable",
                          ["Heat flux I (porosity fixed)", "Porosity ϕ (heat flux fixed)"],
                          horizontal=True)

    n_points = st.slider("Sweep resolution (points)", 8, 30, 16,
                         help="Each point is a /v1/predict call (cached) — keep small on Render free tier.")

    if sweep_kind.startswith("Heat flux"):
        sweep_x = np.linspace(300, 800, n_points)
        x_label = "Solar heat flux I (W/m²)"
        title_extra = f"ϕ = {porosity:.2f}"
        sweep_calls = [(float(I), porosity) for I in sweep_x]
    else:
        sweep_x = np.linspace(0.50, 0.90, n_points)
        x_label = "Crop porosity ϕ"
        title_extra = f"I = {heat_flux} W/m²"
        sweep_calls = [(float(heat_flux), float(p)) for p in sweep_x]

    progress = st.progress(0.0, text="Running surrogate sweep…")
    rows: list[list[float]] = []
    for i, (hf, phi) in enumerate(sweep_calls):
        progress.progress((i + 1) / len(sweep_calls), text=f"Point {i+1}/{len(sweep_calls)}")
        r = cached_predict(hf, phi, float(ambient_c), float(wind_mps))
        if r is None:
            break
        t = r["temps"]
        rows.append([t["t1_c"], t["t2_c"], t["t3_c"], t["t4_c"]])
    progress.empty()

    if rows:
        arr = np.array(rows)
        fig_sw = go.Figure()
        for j, (label, color) in enumerate(zip(TRAY_LABELS, TRAY_COLORS)):
            fig_sw.add_trace(go.Scatter(
                x=sweep_x[:len(arr)], y=arr[:, j], mode="lines+markers", name=label,
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
            ))
        fig_sw.update_layout(
            template=PLOTLY_TEMPLATE,
            title=f"Tray temperatures vs {sweep_kind.split(' ')[0].lower()} ({title_extra})",
            xaxis_title=x_label, yaxis_title="Tray temperature (°C)",
            height=460, margin=dict(l=60, r=20, t=60, b=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_sw, use_container_width=True)

        # Show the spread (T1 − T4) for design insight
        spread = arr[:, 0] - arr[:, 3]
        c1, c2, c3 = st.columns(3)
        c1.metric("Mean T₁−T₄ spread", f"{spread.mean():.1f} °C",
                  help="Diminishing return: more spread = more uneven drying.")
        c2.metric("Max T₁ in sweep", f"{arr[:, 0].max():.1f} °C")
        c3.metric("Min T₄ in sweep", f"{arr[:, 3].min():.1f} °C")

        st.caption("Note: tray spacing is widest at the bottom and narrows upward — "
                   "the air cools as it deposits sensible heat into successive porous trays "
                   "(report §4.2).")


# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — Validation & Methodology
# ────────────────────────────────────────────────────────────────────────────
with tab_valid:
    st.markdown("### ✅ Surrogate Validation")
    st.caption("Polynomial regression (degree 3) trained on an 80/20 split of 102 CFD design points. "
               "Acceptance gate: MAE < 0.5 K and R² > 0.98 per tray.")

    df_metrics = pd.DataFrame({
        "Tray": TRAY_LABELS,
        "R²":          [round(x, 4) for x in METRICS["r2_per_tray"]],
        "MAE (K)":     [round(x, 3) for x in METRICS["mae_per_tray_k"]],
        "Status":      ["✅ Pass" if (r2 > 0.98 and mae < 0.5) else "❌ Fail"
                        for r2, mae in zip(METRICS["r2_per_tray"], METRICS["mae_per_tray_k"])],
    })
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    fig_metrics = go.Figure()
    fig_metrics.add_trace(go.Bar(
        x=TRAY_LABELS, y=METRICS["mae_per_tray_k"], name="MAE (K)",
        marker_color=TRAY_COLORS, text=[f"{m:.3f}" for m in METRICS["mae_per_tray_k"]],
        textposition="outside",
    ))
    fig_metrics.add_hline(y=0.5, line_dash="dash", line_color="red",
                          annotation_text="Acceptance gate (0.5 K)", annotation_position="top right")
    fig_metrics.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Per-tray MAE vs acceptance gate", yaxis_title="MAE (K)",
        height=360, margin=dict(l=60, r=20, t=50, b=60),
    )
    st.plotly_chart(fig_metrics, use_container_width=True)

    st.caption(f"Train set: **{METRICS['n_train']}** points · Test set: **{METRICS['n_test']}** points · "
               f"Polynomial degree: **{METRICS['degree']}** · Worst-tray MAE = **{max(METRICS['mae_per_tray_k']):.2f} K** "
               f"(report-quoted bound: < 0.25 K).")

    st.divider()

    st.markdown("### 🏗️ Four-Layer Modelling Stack")
    L1, L2, L3, L4 = st.columns(4)
    layers = [
        (L1, "Layer 1 — Analytical",   "#1B4965",
         "Lumped-capacitance balance + dimensionless analysis (Bi, Re, Ra, Pr, Nu). "
         "Establishes the laminar mixed-convection regime."),
        (L2, "Layer 2 — 1D FDM",       "#2E86AB",
         "Explicit-Euler transient solver for the absorber plate. "
         "Δt safety factor 0.5 against linearised stability bound."),
        (L3, "Layer 3 — 3-D CFD",      "#F46036",
         "Ansys Fluent · 603,822-element mesh · 102 design points · "
         "(I, ϕ) sweep over 300–800 W/m² × 0.5–0.9."),
        (L4, "Layer 4 — ML Surrogate", "#D7263D",
         "Polynomial regression (deg 3) · MAE < 0.25 K, R² > 0.98 per tray · "
         "<1 ms inference · deployed via FastAPI."),
    ]
    for col, title, color, body in layers:
        with col:
            st.markdown(
                f"""
                <div style='background:{color};color:white;border-radius:14px;
                            padding:14px;height:100%;min-height:180px;'>
                    <b style='font-size:0.95rem'>{title}</b>
                    <div style='font-size:0.85rem;margin-top:8px;opacity:0.95;line-height:1.45'>
                        {body}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    with st.expander("📐 Heat-transfer correlations used (report §3.1)"):
        st.latex(r"\text{Bi} = \frac{h_c\,\delta_p}{k_p} \approx 6\times 10^{-4} \;\;\Longrightarrow\;\;"
                 r"\text{lumped model valid}")
        st.latex(r"\text{Nu}_{\text{forced}} = 0.664\,\text{Re}^{1/2}\,\text{Pr}^{1/3} "
                 r"\quad\text{(absorber–air interface)}")
        st.latex(r"\text{Nu}_{\text{free}} = 0.59\,\text{Ra}^{1/4} "
                 r"\quad\text{(vertical chimney)}")
        st.latex(r"\text{Nu}^3_{\text{mix}} = \text{Nu}^3_{\text{forced}} + \text{Nu}^3_{\text{free}} "
                 r"\quad\text{(Churchill superposition)}")
        st.latex(r"\text{MR}(t) = \exp(-k\,t),\quad k(T) = k_0 \exp\!\left(-\frac{E_a}{R T}\right)")


# ────────────────────────────────────────────────────────────────────────────
# TAB 5 — Economics (extension-worker view)
# ────────────────────────────────────────────────────────────────────────────
with tab_econ:
    st.markdown("### 💰 Cost vs Diesel / Electric Drying")
    st.caption("Order-of-magnitude comparison on a per-kg-of-moisture-removed basis. "
               "Solar input is free; competing technologies pay for fuel + capital.")

    e1, e2 = st.columns(2)
    with e1:
        batch_kg = st.number_input("Batch mass (kg, fresh weight)", min_value=1.0, max_value=500.0, value=20.0)
        diesel_price = st.number_input("Diesel price (₹/L)", min_value=50.0, max_value=200.0, value=95.0)
        electric_price = st.number_input("Electricity price (₹/kWh)", min_value=2.0, max_value=20.0, value=8.0)
    with e2:
        diesel_eff = st.slider("Diesel-dryer thermal efficiency", 0.20, 0.60, 0.35,
                                help="Typical for direct-fired LPG/diesel dryers.")
        electric_eff = st.slider("Electric-dryer thermal efficiency", 0.50, 0.95, 0.75)

    # Latent-heat removed at the bottom-tray temperature (rough, but consistent with report).
    lv = 2.45e6  # J/kg, latent heat of vaporisation of water
    moisture_removed_kg = batch_kg * (initial_pct - target_pct) / 100.0
    energy_required_J = moisture_removed_kg * lv

    DIESEL_HEAT_J_PER_L = 36e6   # ~36 MJ/L lower-heating value
    diesel_litres = energy_required_J / (diesel_eff * DIESEL_HEAT_J_PER_L)
    diesel_cost = diesel_litres * diesel_price
    electric_kwh = energy_required_J / (electric_eff * 3.6e6)
    electric_cost = electric_kwh * electric_price

    # Solar drying cost is dominated by amortised capital; assume zero fuel cost,
    # cabinet capex ₹15 000 amortised over 5 years at 50 batches/year.
    solar_capex = 15000.0
    solar_lifetime_batches = 5 * 50
    solar_cost = solar_capex / solar_lifetime_batches

    df_econ = pd.DataFrame([
        {"Method": "☀️ Solar (this dryer)",  "Energy required":  f"{energy_required_J / 1e6:.2f} MJ",
         "Fuel / electricity": "—", "Cost per batch (₹)": round(solar_cost, 2)},
        {"Method": "🔥 Diesel-fired",         "Energy required":  f"{energy_required_J / 1e6:.2f} MJ",
         "Fuel / electricity": f"{diesel_litres:.2f} L", "Cost per batch (₹)": round(diesel_cost, 2)},
        {"Method": "⚡ Electric-resistance",  "Energy required":  f"{energy_required_J / 1e6:.2f} MJ",
         "Fuel / electricity": f"{electric_kwh:.1f} kWh", "Cost per batch (₹)": round(electric_cost, 2)},
    ])
    st.dataframe(df_econ, use_container_width=True, hide_index=True)

    fig_cost = go.Figure(go.Bar(
        x=["Solar", "Diesel", "Electric"],
        y=[solar_cost, diesel_cost, electric_cost],
        marker_color=["#2ecc71", "#34495e", "#f39c12"],
        text=[f"₹{c:,.0f}" for c in (solar_cost, diesel_cost, electric_cost)],
        textposition="outside",
    ))
    fig_cost.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Cost per batch (₹) — {batch_kg:.0f} kg, moisture {initial_pct}% → {target_pct}% d.b.",
        yaxis_title="Cost per batch (₹)", height=360, margin=dict(l=60, r=20, t=60, b=60),
    )
    st.plotly_chart(fig_cost, use_container_width=True)

    st.caption(
        "Caveats: solar capex assumed ₹15,000 amortised over 5 years × 50 batches/yr. "
        "Diesel LHV taken as 36 MJ/L. Electric efficiency includes resistive heating only. "
        "Numbers are illustrative — calibrate with local price quotes before reporting."
    )

# ════════════════════════════════════════════════════════════════════════════
# Footer
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.caption(
    f"**Solar Dryer Digital Twin** · CLL251 Heat Transfer · IIT Delhi · "
    f"Authors: Eric Kapil, Vedant Singhal, Kridant Kumar, Tanisha Sangwan · "
    f"Model `{data['model_version']}` · Backend `{API}`"
)
