# Presentation Outline — Solar Dryer Digital Twin

*Target: 10–12 slides, 12 minutes + 3 minutes Q&A. Treat speaker notes as the bullet-by-bullet narrative the presenter will say aloud.*

---

## Slide 1 — Title

**Solar Air Dryer — A CFD-Trained Digital Twin**
CLL251 · Heat Transfer for Chemical Engineers · IIT Delhi
Team: *[names]* · Date: *[date]*

*Speaker notes:* "We built a four-layer thermal model of an agricultural solar dryer and shipped it as a live web app. Twelve minutes — let's go."

---

## Slide 2 — Problem & Motivation

- Post-harvest losses in India: 10–30% of horticultural produce
- Solar drying = lowest-cost preservation route
- Tray temperature ↔ drying time ↔ product quality
- CFD captures the physics but takes hours per case → unusable as a design tool

*Speaker notes:* Anchor on a familiar number (loss percentage). Then frame the gap: rigorous thermal model vs. usable design tool.

---

## Slide 3 — Approach: A Four-Layer Stack

```
   Analytical heat balance  →  1D FDM (transient)
                                   ↓
                              3D CFD sweep (102 design points)
                                   ↓
                              ML surrogate (polynomial regression)
                                   ↓
                              Web app: real-time, interactive
```

Each layer independently defensible; they cross-validate each other.

*Speaker notes:* "We didn't pick one method. We stacked four — and the figure on slide 7 shows them agreeing within engineering tolerance."

---

## Slide 4 — CFD Setup

- Geometry: slanted absorber + vertical chimney + 4 trays
- Mesh: 603 822 elements, laminar viscous (justified by Re ≈ 350)
- Inlet: 0.01 m/s, BC: heat-flux 300–800 W/m², porosity 0.5–0.9
- 102 cases swept in Ansys Fluent
- Outputs: 4 area-weighted tray temperatures per case

*Insert:* mesh + low/high HF contours.

---

## Slide 5 — CFD Results

- Tray temperatures **monotonically descending** T₁ > T₂ > T₃ > T₄ across all 102 cases
- Plate hotspot scales near-linearly with I (358 K at 300 W/m², 395 K at 800 W/m²)
- Velocity field: buoyancy-driven plume confirms mixed-convection regime predicted by Ra/Re analysis

*Insert:* contour comparison + velocity vectors.

---

## Slide 6 — 1D FDM (proposal commitment)

Lumped energy balance on the absorber plate (Bi ≈ 6×10⁻⁴ ≪ 0.1):

ρ·c_p·δ · dT/dt = α·I − h·(T − T_∞) − ε·σ·(T⁴ − T_sky⁴)

Explicit Euler in NumPy; stability bound Δt < ρcpδ / h_eff with safety 0.5.

*Insert:* [`figures/fdm_transient.png`](../figures/fdm_transient.png) — plate T(t) at I = 300, 500, 800 W/m².

*Speaker notes:* "This is the deliverable promised in the abstract. Integrator self-checks against Newton iteration to sub-millikelvin agreement."

---

## Slide 7 — ML Surrogate + Parity Plot (Money Slide)

- Polynomial regression, degree 3, 81 train / 21 test
- Per-tray acceptance gate: MAE < 0.5 K, R² > 0.98 — **all four trays pass**

*Insert:* [`figures/parity_plot.png`](../figures/parity_plot.png) (full slide width).

| Tray | MAE (K) | R² |
|---|---|---|
| T₁ | 0.25 | 0.996 |
| T₂ | 0.19 | 0.993 |
| T₃ | 0.15 | 0.987 |
| T₄ | 0.11 | 0.981 |

*Speaker notes:* "Tightly on the diagonal. Inference < 1 ms. CFD took ~ 1 hr per case."

---

## Slide 8 — System Architecture

```
Browser (Streamlit)
   │ HTTP
   ▼
FastAPI ── Redis (cache) ── Postgres (audit)
   │
   ▼
sklearn surrogate + physics module (Nu wind correction, Lewis kinetics, η)
```

- Stateless service, Dockerised, `docker compose up`
- p50 latency ~ 3 ms cached / 12 ms cold
- `/metrics` exposed for Prometheus, `/docs` for Swagger

*Speaker notes:* "Unusual for a heat-transfer poster. Showing it because it makes the project deployable, not just demo-able."

---

## Slide 9 — Live Demo

Demo flow (4 minutes):

1. Move irradiance slider 300 → 800 W/m². Tray temperatures rise ≈ linearly.
2. Drop ambient to 15 °C. All tray temps fall in lock-step.
3. Crank wind 0 → 8 m/s. Wind correction badge updates; tray temps shrink toward ambient.
4. Switch crop tomato → mango. Drying time updates via Arrhenius.
5. Open `/docs` Swagger to show the underlying API contract.

**Fallback:** screenshot of the dashboard pre-loaded; pre-typed `curl` commands in terminal.

---

## Slide 10 — Validation: All Four Layers Agree

*Insert:* [`figures/fdm_full_vs_no_rad.png`](../figures/fdm_full_vs_no_rad.png) — FDM (full physics, ε=0.1) vs FDM (CFD-comparable, ε=0) vs CFD peak.

Bullet:
- Apples-to-apples FDM (ε=0) vs CFD: monotone trend, error within tens of K — consistent with 1D-vs-3D fidelity gap
- Full-physics FDM (ε=0.1) is the realistic operating value — *lower* than CFD peak because radiation to sky pulls energy out

---

## Slide 11 — Limitations & Future Work

- **1D vs 3D.** FDM cannot resolve plate hotspots — by design.
- **Lewis constants** are calibrated, not lab-fit. Replace with measured kinetics in v2.
- **Sweep envelope.** Surrogate valid only for I ∈ [300, 800] W/m² and porosity ∈ [0.5, 0.9].
- **Future.** Couple humidity, add a transient drying ODE in the surrogate, deploy to a public URL with monitoring.

---

## Slide 12 — Closing + Q&A

> "A four-layer thermal model — analytical, FDM, CFD, ML — wrapped in a deployable web app. CFD-equivalent predictions in milliseconds."

QR code → GitHub + live demo URL.

*Speaker notes:* Pause. Invite questions. Anticipated Q's:
- *Why polynomial?* Smooth physics over a 2D input space; degree 3 already saturates on R².
- *Why Streamlit not React?* Time/value trade-off; backend is framework-agnostic.
- *Why no transient CFD?* Drying is multi-hour; instantaneous fields are quasi-steady. Transient handled by 1D FDM.

---

*Rehearsal checklist.* (1) Run live-demo at least once with Wi-Fi off using localhost. (2) Confirm screenshot fallbacks exist for every demo step. (3) Know the parity-plot table by heart. (4) Time the talk — target 11 minutes, leaving 4 minutes of Q&A buffer.
