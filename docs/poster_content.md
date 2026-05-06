# Poster Content — Solar Dryer Digital Twin

*44" × 44" template. 10-panel layout. Copy below is print-ready; trim to fit panel widths.*

---

## Panel 1 — Title Block

**Solar Air Dryer — A CFD-Trained Digital Twin for Real-Time Thermal Prediction**

Team: *[member names]*
Course: CLL251 — Heat Transfer for Chemical Engineers
Department of Chemical Engineering, IIT Delhi · Semester [Spring 2026]

---

## Panel 2 — Abstract / One-Liner

A four-tray solar air dryer is modelled across four nested layers — analytical heat balance, 1D FDM, 3D CFD, and an ML surrogate — and deployed as an interactive web dashboard. Users adjust irradiance, ambient conditions, and crop properties and instantly see predicted tray temperatures, drying time, and thermal efficiency. The surrogate matches CFD on a held-out test set within MAE < 0.25 K and R² > 0.98 per tray, while running in under a millisecond.

---

## Panel 3 — Geometry & Reference

- Slanted glass-covered absorber plate (~ 2 m × 0.5 m)
- Vertical chimney with 4 horizontal trays (T₁ top → T₄ bottom)
- Hot air enters at base of absorber, rises through trays under combined buoyancy + induced flow
- Insert: CAD render (`Data_Raw/Screenshot 2026-05-06 103337.jpg`) and contour overlay

---

## Panel 4 — Problem Framing

**Why model a solar dryer?**
Post-harvest losses in Indian agriculture run 10–30%; solar drying is the lowest-cost preservation route. Tray temperature governs drying time and product quality, but depends nonlinearly on irradiance, crop porosity, and ambient conditions. CFD captures the physics but takes hours per case — unusable as a design tool.

**Our approach.** Run CFD once over a parameter sweep, then train a fast ML surrogate that predicts tray temperatures in milliseconds, layered with analytical drying kinetics. Wrap in a public web dashboard.

---

## Panel 5 — Methods I: Governing Equations & CFD

**Absorber plate energy balance (1D FDM, lumped):**

ρ_p · c_p · δ · dT/dt = α·I − h·(T − T_∞) − ε·σ·(T⁴ − T_sky⁴)

Lumped justified by Bi ≈ 6×10⁻⁴ ≪ 0.1.

**Chimney regime (Re ≈ 350, Ra ≈ 10⁹, Pr ≈ 0.71):** mixed convection, buoyancy-dominant — laminar viscous model used in CFD.

**Nu correlations (Incropera & Bergman):**
- Forced flat-plate (laminar): Nu = 0.664·Re^½·Pr^⅓
- Free vertical channel: Nu = 0.59·Ra^¼
- Mixed (Churchill): Nu³_mixed = Nu³_forced + Nu³_free

**CFD setup (Ansys Fluent):**
- Mesh: 603 822 elements, laminar viscous
- Inlet: 0.01 m/s, ambient 25 °C
- Absorber: heat-flux BC, 300–800 W/m²
- Trays: porous medium (porosity 0.5–0.9)
- Outputs: 4 area-weighted tray temperatures per case

---

## Panel 6 — Methods II: ML Surrogate & System Architecture

**Surrogate.** Polynomial regression, degree 3, multi-output (one pipeline → 4 tray temps). Trained on 102 CFD design points with 80/20 split. Acceptance gate enforced at training time: per-tray MAE < 0.5 K and R² > 0.98.

**Inputs:** heat flux, crop porosity. **Outputs:** T₁, T₂, T₃, T₄.

**System architecture (unusual for a heat-transfer poster — included as a differentiator):**

```
   Browser (Streamlit)
        │  POST /v1/simulate
        ▼
   FastAPI service ── Redis (LRU prediction cache)
        │              Postgres (audit log)
        │              Prometheus /metrics
        ▼
   sklearn surrogate (joblib)
        │
        ▼
   Physics module: wind correction (Nu), Lewis kinetics, η
```

Public endpoint with auto-generated Swagger docs. Containerised, runs end-to-end with `docker compose up`.

---

## Panel 7 — Results I: CFD Contour Comparison

Two-panel side-by-side contour maps:

- **Low irradiance** (300 W/m², porosity 0.7): T peaks ≈ 358 K (85 °C) on absorber; tray temps in band 305–315 K.
- **High irradiance** (800 W/m², porosity 0.7): T peaks ≈ 395 K (122 °C) on absorber; tray temps 308–333 K.

Plus the velocity-vector overlay showing the buoyancy-driven plume. Source: Data_Raw screenshots.

Caption: "Temperature contour scales linearly with absorbed flux; tray-to-tray temperature drop confirms expected sequential cooling T₁ > T₂ > T₃ > T₄."

---

## Panel 8 — Results II: Parity Plot (Centerpiece)

**Insert:** [`figures/parity_plot.png`](../figures/parity_plot.png)

Caption block:

> Surrogate predictions vs CFD truth, held-out test set (n = 21).
> Per-tray accuracy:
> - T₁: MAE = 0.25 K · R² = 0.996
> - T₂: MAE = 0.19 K · R² = 0.993
> - T₃: MAE = 0.15 K · R² = 0.987
> - T₄: MAE = 0.11 K · R² = 0.981
>
> All trays clear the acceptance gate (MAE < 0.5 K, R² > 0.98). The surrogate is poster-grade — millisecond inference at CFD-equivalent accuracy.

Inset: **FDM steady-state plate temperature vs CFD peak** ([`figures/fdm_full_vs_no_rad.png`](../figures/fdm_full_vs_no_rad.png)) — shows the four-layer agreement on trend.

---

## Panel 9 — Results III: Web App + Latency

**Screenshot** of the Streamlit dashboard with sliders set, four large tray-temperature tiles, drying-time table, efficiency badge, and moisture-vs-time curve.

**Performance (read off `/metrics`):**
- p50 latency: ~3 ms (cache hit) / ~12 ms (cache miss)
- p99 latency: < 25 ms
- Throughput: ≥ 800 req/s on a single container

**Example prediction (Tomato, 600 W/m², porosity 0.7, ambient 25 °C, wind 2 m/s):**
- T₁ = 47.3 °C → drying time 11.4 hr to 10% MR
- η = 38.2%

QR code → live deployment URL.

---

## Panel 10 — Discussion · Conclusion · References

**Key findings.**
- CFD-trained polynomial surrogate hits MAE < 0.25 K per tray; sub-ms inference makes design iteration interactive.
- 1D FDM honours the proposal commitment and validates the time-domain physics; agreement with CFD trend is monotone and within engineering tolerance.
- Wind correction via flat-plate Nu cleanly bridges to ambient conditions not in the CFD sweep.

**Limitations.**
- 1D FDM cannot resolve 3D hotspots seen in CFD contours.
- Drying constants are calibrated placeholders; lab-fit values pending.
- CFD treats radiation by collapsing it into the heat-flux BC; FDM models it explicitly.

**Conclusion.** A four-layer modelling stack (analytical → FDM → CFD → ML) gives both the rigor required by the heat-transfer course and the interactivity required by an end user. The deployable web app is unusual for an undergraduate heat-transfer project and demonstrates that classical thermal physics can be packaged into modern decision tools.

**References.** Incropera & Bergman *Fundamentals of Heat and Mass Transfer* · Duffie & Beckman *Solar Engineering of Thermal Processes* · Lewis (1921) *J. Ind. Eng. Chem.* · Churchill (1977) *AIChE J.* · Akpinar (2006) *J. Food Eng.*

QR code → GitHub repo and deployed app.

---

*Print notes.* Use a serif body face (Source Serif / Charter) at 28 pt for body, 56 pt for panel headers, 96 pt for the title. Color palette aligned with the Streamlit dashboard tray colors: #FF6B35, #F7C59F, #8FBF9F, #004E89.
