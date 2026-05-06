"""Solar Dryer Digital Twin — Streamlit frontend.

Calls POST /v1/simulate on the FastAPI backend and renders:
  - 4 tray temperature tiles
  - Per-tray drying time table
  - Thermal efficiency badge
  - Moisture ratio vs time curve (MR = exp(-k·t)) per tray
  - Wind correction annotation
"""

import math
import numpy as np
import plotly.graph_objects as go
import requests
import streamlit as st

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Solar Dryer Digital Twin",
    page_icon="☀️",
    layout="wide",
)

# ── helpers ───────────────────────────────────────────────────────────────────
try:
    API = st.secrets["API_URL"]
except Exception:
    API = "http://localhost:8000"

TRAY_COLORS = ["#FF6B35", "#F7C59F", "#EFEFD0", "#004E89"]
TRAY_LABELS = ["Tray 1 (top)", "Tray 2", "Tray 3", "Tray 4 (bottom)"]

CROP_DESCRIPTIONS = {
    "tomato": "Tomato (Lycopersicum esculentum)",
    "mango":  "Mango (Mangifera indica)",
    "chilli": "Chilli (Capsicum annuum)",
    "onion":  "Onion (Allium cepa)",
}


def call_simulate(payload: dict) -> dict | None:
    try:
        r = requests.post(f"{API}/v1/simulate", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API server. Make sure the backend is running on " + API)
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        return None


def moisture_curve(rate_k: float, t_max_h: float, n: int = 300) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0, t_max_h, n)
    mr = np.exp(-rate_k * t)
    return t, mr


def efficiency_color(eta: float) -> str:
    if eta >= 0.6:
        return "#2ecc71"
    if eta >= 0.35:
        return "#f39c12"
    return "#e74c3c"


# ── sidebar — inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/en/thumb/b/b7/IIT_Delhi_logo.svg/200px-IIT_Delhi_logo.svg.png",
        width=80,
    )
    st.title("Solar Dryer\nDigital Twin")
    st.caption("CLL251 · Heat Transfer for Chemical Engineers · IIT Delhi")
    st.divider()

    st.subheader("☀️ Environmental")
    heat_flux = st.slider("Solar irradiance (W/m²)", 300, 800, 600, step=10)
    ambient_c = st.slider("Ambient temperature (°C)", 15, 40, 25)
    wind_mps  = st.slider("Wind speed (m/s)", 0.0, 8.0, 2.0, step=0.5)

    st.subheader("🌾 Crop & Dryer")
    porosity = st.slider("Crop porosity", 0.50, 0.90, 0.70, step=0.01)
    crop_key = st.selectbox("Crop type", list(CROP_DESCRIPTIONS.keys()),
                             format_func=lambda k: CROP_DESCRIPTIONS[k])
    target_pct = st.slider("Target moisture (% d.b.)", 5, 20, 10)

    st.divider()
    run = st.button("▶  Run Simulation", use_container_width=True, type="primary")

# ── header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <h1 style='margin-bottom:0'>☀️ Solar Dryer Digital Twin</h1>
    <p style='color:grey;margin-top:4px'>
    CFD-trained ML surrogate · Real-time tray temperature prediction · Lewis drying kinetics
    </p>
    """,
    unsafe_allow_html=True,
)
st.divider()

# ── run on first load OR button press ────────────────────────────────────────
if "last_data" not in st.session_state:
    st.session_state["last_data"] = None

if run or st.session_state["last_data"] is None:
    payload = {
        "heat_flux":          heat_flux,
        "porosity":           porosity,
        "ambient_c":          float(ambient_c),
        "wind_mps":           float(wind_mps),
        "crop":               crop_key,
        "initial_moisture_db": 9.0,
        "target_moisture_db": target_pct / 100.0,
    }
    with st.spinner("Calling backend…"):
        data = call_simulate(payload)
    if data:
        st.session_state["last_data"] = data

data = st.session_state["last_data"]

if data is None:
    st.info("Configure inputs in the sidebar and click **▶ Run Simulation**.")
    st.stop()

# ── unpack response ───────────────────────────────────────────────────────────
temps     = data["temps"]          # {t1_c, t2_c, t3_c, t4_c}
trays     = data["trays"]          # list of {tray, temp_c, drying_time_hours, rate_constant_per_hour}
eta       = data["thermal_efficiency"]
wind_corr = data["wind_correction_k"]
mv        = data["model_version"]

temp_vals = [temps["t1_c"], temps["t2_c"], temps["t3_c"], temps["t4_c"]]

# ── section 1: tray temperature tiles ─────────────────────────────────────────
st.subheader("🌡️ Tray Temperatures")

cols = st.columns(4)
for i, (col, label, temp, color) in enumerate(zip(cols, TRAY_LABELS, temp_vals, TRAY_COLORS)):
    with col:
        st.markdown(
            f"""
            <div style='
                background:{color};
                border-radius:12px;
                padding:20px 16px;
                text-align:center;
                color:{"white" if i in (0, 3) else "#333"};
            '>
                <div style='font-size:0.85rem;font-weight:600;letter-spacing:0.05em;opacity:0.9'>
                    {label.upper()}
                </div>
                <div style='font-size:2.6rem;font-weight:800;line-height:1.1;margin:8px 0'>
                    {temp:.1f}°C
                </div>
                <div style='font-size:0.78rem;opacity:0.85'>
                    ({temp + 273.15:.1f} K)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# wind correction annotation
if abs(wind_corr) > 0.05:
    st.caption(
        f"🌬️ Wind correction applied: **−{wind_corr:.2f} K** per tray "
        f"(flat-plate Nu correlation, wind = {wind_mps} m/s)"
    )

st.divider()

# ── section 2: drying table + efficiency badge ─────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("⏱️ Drying Times")
    st.caption(
        f"Crop: **{CROP_DESCRIPTIONS[crop_key]}** · "
        f"Target moisture: **{target_pct}% d.b.** · "
        f"Lewis thin-layer model: MR = exp(−k·t)"
    )
    table_rows = []
    for tray in trays:
        table_rows.append({
            "Tray": TRAY_LABELS[tray["tray"] - 1],
            "Temperature (°C)": f"{tray['temp_c']:.1f}",
            "Rate constant k (h⁻¹)": f"{tray['rate_constant_per_hour']:.4f}",
            "Drying time (h)": f"{tray['drying_time_hours']:.2f}",
        })
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("⚡ Thermal Efficiency")
    eta_pct = eta * 100
    color = efficiency_color(eta)
    st.markdown(
        f"""
        <div style='
            background:{color};
            border-radius:16px;
            padding:32px 20px;
            text-align:center;
            color:white;
            margin-top:8px;
        '>
            <div style='font-size:0.9rem;font-weight:600;letter-spacing:0.08em;opacity:0.9'>
                THERMAL EFFICIENCY
            </div>
            <div style='font-size:3.2rem;font-weight:900;line-height:1.0;margin:12px 0'>
                {eta_pct:.1f}%
            </div>
            <div style='font-size:0.8rem;opacity:0.85'>
                η = ṁ·cₚ·ΔT / (I·A)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Model version: `{mv}`")

st.divider()

# ── section 3: moisture ratio vs time curve ────────────────────────────────────
st.subheader("💧 Moisture Ratio vs. Time")
st.caption("MR(t) = exp(−k·t) per tray  ·  Target MR shown as dashed line")

# compute MR curves — extend to 120% of the longest drying time for headroom
max_t = max(tray["drying_time_hours"] for tray in trays) * 1.2
target_mr = math.exp(-trays[0]["rate_constant_per_hour"] * trays[0]["drying_time_hours"])

fig = go.Figure()

for tray, color in zip(trays, TRAY_COLORS):
    t_arr, mr_arr = moisture_curve(tray["rate_constant_per_hour"], max_t)
    fig.add_trace(go.Scatter(
        x=t_arr,
        y=mr_arr,
        mode="lines",
        name=TRAY_LABELS[tray["tray"] - 1],
        line=dict(color=color, width=2.5),
        hovertemplate="t = %{x:.2f} h<br>MR = %{y:.4f}<extra>" + TRAY_LABELS[tray["tray"] - 1] + "</extra>",
    ))
    # dot at drying time
    fig.add_trace(go.Scatter(
        x=[tray["drying_time_hours"]],
        y=[math.exp(-tray["rate_constant_per_hour"] * tray["drying_time_hours"])],
        mode="markers",
        marker=dict(color=color, size=9, symbol="circle"),
        showlegend=False,
        hovertemplate=f"Tray {tray['tray']}: done at {tray['drying_time_hours']:.2f} h<extra></extra>",
    ))

# target MR line
target_mr_val = math.exp(
    -trays[0]["rate_constant_per_hour"] * trays[0]["drying_time_hours"]
)
fig.add_hline(
    y=target_mr_val,
    line_dash="dash",
    line_color="grey",
    annotation_text=f"Target MR = {target_mr_val:.3f}  ({target_pct}% d.b.)",
    annotation_position="bottom right",
)

fig.update_layout(
    xaxis_title="Time (hours)",
    yaxis_title="Moisture Ratio MR = M/M₀",
    yaxis=dict(range=[0, 1.05]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=20, t=40, b=60),
    height=400,
    plot_bgcolor="white",
    paper_bgcolor="white",
)
fig.update_xaxes(showgrid=True, gridcolor="#eee")
fig.update_yaxes(showgrid=True, gridcolor="#eee")

st.plotly_chart(fig, use_container_width=True)

# ── section 4: model info expander ────────────────────────────────────────────
with st.expander("ℹ️ Model & Physics Details"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**Surrogate model**
- Polynomial regression (degree 3), multi-output
- Trained on 102 CFD design points (Ansys Fluent)
- Inputs: heat flux (W/m²), porosity
- Outputs: T₁…T₄ tray temperatures (K)
- Acceptance gate: MAE < 0.5 K, R² > 0.98 per tray

**Wind correction**
- Flat-plate Nusselt correlation (laminar / turbulent)
- Applied as a fractional shrink on (T_tray − T_ambient)
- Capped at 50% to avoid unphysical outputs
        """)
    with c2:
        st.markdown(f"""
**Drying kinetics (Lewis model)**
- MR(t) = exp(−k·t)
- k(T) = k₀ · exp(−Eₐ / RT)  (Arrhenius)
- Crop: {CROP_DESCRIPTIONS[crop_key]}

**Thermal efficiency**
- η = ṁ·cₚ·ΔT / (I · A_collector)
- Bounded to [0, 1]

**CFD setup**
- 603 822-element mesh, laminar viscous model
- Inlet: 0.01 m/s, porous tray BC
- 4 area-weighted tray temperatures (K) per run
        """)

st.caption(
    "Solar Dryer Digital Twin · CLL251 Heat Transfer for Chemical Engineers · IIT Delhi · "
    f"API: `{API}` · Model: `{mv}`"
)
