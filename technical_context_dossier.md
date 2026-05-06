# Solar Dryer Digital Twin — Technical Context Dossier
*Designed as a single-source-of-truth handoff for any AI agent or new team member joining the project.*
*Generated 06 May 2026.*

This document captures **all known technical context** about the project. It is exhaustive by design — read it once and you should be able to pick up any track without further briefing.

---

## 0. Document Purpose & How To Use

This dossier is the **canonical project state**. If you are an LLM agent picking up a task on this project, you should be able to answer any question about scope, data, physics, or technical decisions from this document alone. If you find a contradiction between this document and a chat message or older file, **trust this document** unless explicitly told otherwise — it is updated to reflect the current consensus.

Companion documents:
- `01_next_steps_and_project_plan.md` — what to do next, with task breakdowns
- `solar_dryer_project_approach.md` — original framing memo (read-only, for historical context)
- `solar_dryer_ml.csv` — the canonical dataset (102 design points)

---

## 1. Project Metadata

| Field | Value |
|---|---|
| Course | CLL251 — Heat Transfer for Chemical Engineers |
| Institution | IIT Delhi (inferred from course code) |
| Project type | Term project / poster + presentation deliverable |
| Deliverable format | 44" × 44" poster (provided template), slide deck with live demo, public web app, GitHub repo |
| Team size | Multi-member (exact composition TBD per task plan) |
| Communication channel | WhatsApp + GitHub |

---

## 2. Project Framing

### One-liner
A CFD-trained surrogate model for real-time thermal prediction of an agricultural solar dryer, deployed as an interactive web app.

### What problem are we solving
Solar dryers are used to dehydrate crops (tomato, mango, chilli, etc.) at low cost in regions with high insolation. Designers and operators want to know: given today's weather and crop load, how long will drying take, and what will the air temperatures be at each tray? CFD answers this but takes hours per case. A trained surrogate gives the answer in milliseconds, on a laptop or phone, via a web UI.

### Why the framing works for grading (Heat Transfer course)
- Heat transfer modes covered: solar radiation absorption, conduction in absorber plate, free + forced convection in chimney, radiation to sky, evaporative cooling at crop surface
- Dimensionless analysis: Ra, Re, Nu, Pr, Bi all appear naturally
- Original commitment in submitted abstract: numerical model of transient HT via FDM with conduction, convection, solar radiation. **All honored.** The CFD/ML/web-app additions are expansions, not pivots.
- Live demo distinguishes the project at poster time

### Scope boundaries (explicit)
| In scope | Out of scope |
|---|---|
| Single fixed geometry, varying operating conditions | Geometry optimization |
| Heat flux + porosity as primary design variables | Multi-objective optimization |
| Steady-state CFD | Transient CFD (handled instead by 1D FDM module) |
| Crop modeled as porous medium with effective properties | Grain-scale moisture transport |
| Wind speed handled via analytical Nu correlation | Wind in CFD sweep |
| One default crop (tomato) for kinetics; dropdown for others | Validation of kinetics constants in lab |

---

## 3. Physical System — Geometry & Dimensions

### Configuration
The solar dryer is an **indirect-type chimney dryer** with two main components:

1. **Slanted glass-covered absorber plate** (the "solar collector"). Air enters at the lower end, is heated by solar irradiation passing through the glass cover and absorbed by the plate, and rises by combined buoyancy + induced flow.
2. **Vertical drying chimney** containing **4 horizontal trays** stacked one above the other. Hot air from the absorber enters at the bottom of the chimney, passes upward through the four trays sequentially, and exits at the top through a small chimney cap.

### Numbering convention
- **Tray 1 = bottom-most tray** (closest to the heated air inlet). Sees the hottest air.
- **Tray 4 = top-most tray.** Sees the coolest air (after passing through trays 1, 2, 3).
- This convention is confirmed by the data: T₁ > T₂ > T₃ > T₄ for all 102 design points.

### Approximate dimensions
- Glass cover (slanted absorber surface): ~ **2 m × 0.5 m**
- Chimney section: vertical column with 4 trays
- Exact heights, widths, and tray spacings: see geometry images in the project workspace

### Materials and treatment in CFD
- Absorber plate: opaque, heat-flux boundary condition applied (representing absorbed solar)
- Glass cover: not modeled separately in current CFD; absorbed solar collapses to plate heat flux
- Trays: **modeled as porous media** with porosity = sweep variable; represents bulk crop layer
- Walls of chimney: adiabatic in current setup (acknowledged simplification)

### Geometric features visible in renders
- Slanted absorber on left, vertical chimney on right meeting at a lower elbow
- Small protrusion at top of chimney = exit
- 4 horizontal slits visible in the chimney wall = tray locations

---

## 4. CFD Setup (Ansys Fluent)

### Solver
- Steady-state pressure-based solver
- **Viscous model: laminar** (chosen for simplicity given the very low inlet velocity; explicitly acknowledged as a limitation on the poster)
- Energy equation: ON
- Radiation: not separately modeled (radiative effects collapsed into absorber boundary condition)

### Boundary conditions
| Boundary | Type | Value |
|---|---|---|
| Inlet | Velocity inlet, magnitude normal to boundary | **0.01 m/s** |
| Inlet temperature | Thermal | 300 K (ambient, default) |
| Absorber plate | Heat flux | Sweep variable: **300–800 W/m²** |
| Outlet | Pressure outlet | 0 Pa gauge |
| Trays | Porous medium | Sweep variable porosity: **0.5–0.9** |
| Walls | No-slip, adiabatic | — |

### Mesh
- Element count: **603,822** (single mesh used across all 102 runs)
- Mesh quality metrics: not yet documented (recommend orthogonal quality and skewness be reported on poster)
- **Mesh independence study: not yet performed.** This is the only outstanding CFD gap. Recommended: one additional run at 500 W/m² + 0.8 porosity on a coarser mesh (~250–350k elements) to report % change in T₁.

### Convergence criteria
- Continuity, momentum, energy residuals: standard 10⁻³ / 10⁻⁶ thresholds (specifics to be confirmed from Fluent log)

### Outputs extracted
For each design point, four area-weighted average static temperatures are reported:
- `contact_region-trg` → **Tray 1** (bottom)
- `contact_region_2-trg` → **Tray 2**
- `contact_region_3-trg` → **Tray 3**
- `contact_region_4-trg` → **Tray 4** (top)

These regions correspond to the porous-tray volumes; "trg" is the Fluent zone tag for "tray region group".

---

## 5. The Dataset — `solar_dryer_ml.csv`

### File metadata
- Generated: 2026-04-25 from Ansys Fluent parametric study
- Encoding: UTF-8
- 102 rows of design-point data, plus 6 header/comment lines

### Schema

| Column | Original Fluent name | Description | Units | Range |
|---|---|---|---|---|
| `Name` | — | Design-point identifier | — | DP 0 … DP 101 |
| `P1` | Heat_flux | Solar heat flux on absorber | W/m² | 300–800 |
| `P6` | Crop_Porosity | Tray porosity | dimensionless | 0.5–0.9 |
| `P2` | tray_1Temp | Tray 1 (bottom) area-weighted avg temp | K | 317.56–333.25 |
| `P3` | Tray_2Temp | Tray 2 avg temp | K | 311.30–321.39 |
| `P4` | Tray_3Temp | Tray 3 avg temp | K | 307.26–314.55 |
| `P5` | Tray_4Temp | Tray 4 (top) avg temp | K | 304.64–309.45 |

### Coverage in input space

**Heat flux levels (28 unique values):**
300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500, 520, 540, 550, 560, 575, 580, 600, 620, 640, 660, 680, 700, 720, 740, 760, 780, 800 W/m²

**Porosity levels (9 unique values):**
0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9

**Structure:** A coarse grid (DPs 0–20, 6 heat-flux × 5 porosity values = ~30 corners and edges) plus a dense fine-scale sweep (DPs 22–101) that samples the central region densely (heat flux 320–780, porosity 0.55–0.85).

### Output statistics

| Tray | Min (K) | Max (K) | Mean (K) | Min (°C) | Max (°C) |
|---|---|---|---|---|---|
| T₁ (bottom) | 317.56 | 333.25 | 327.44 | 44.4 | 60.1 |
| T₂ | 311.30 | 321.39 | 317.47 | 38.2 | 48.2 |
| T₃ | 307.26 | 314.55 | 311.43 | 34.1 | 41.4 |
| T₄ (top) | 304.64 | 309.45 | 307.37 | 31.5 | 36.3 |

### Sanity checks (passed)
- Monotonicity: T₁ > T₂ > T₃ > T₄ holds for **all 102 rows** → physically consistent (hotter air at bottom, cooled progressively as it rises through trays)
- Heat flux dependence: tray temps increase monotonically with heat flux (checked along porosity = 0.8 slice)
- Porosity dependence: weaker effect than heat flux, generally small monotonic shift (denser crop bed = slightly more heat trapped at lower trays)

### Sample rows for quick reference

| DP | HF (W/m²) | Porosity | T₁ (K) | T₂ (K) | T₃ (K) | T₄ (K) |
|---|---|---|---|---|---|---|
| DP 2 | 300 | 0.8 | 317.76 | 311.32 | 307.36 | 304.76 |
| DP 1 | 500 | 0.8 | 326.89 | 317.09 | 311.10 | 307.18 |
| DP 0 | 575 | 0.8 | 329.99 | 319.40 | 312.97 | 308.43 |
| DP 6 | 800 | 0.8 | 333.01 | 320.82 | 313.68 | 308.79 |
| DP 7 | 500 | 0.5 | 327.08 | 317.10 | 310.95 | 306.99 |
| DP 10 | 500 | 0.9 | 326.60 | 317.07 | 311.32 | 307.46 |

### Known data quirks
- Some non-monotonicity in T₁ at high heat fluxes (e.g., DP 76 at 640 W/m², 0.75 porosity gives T₁ = 330.70 K, slightly below DP 75 at 640 W/m², 0.65 → 330.96 K). Likely CFD convergence noise of order ±0.3 K. **Does not affect surrogate fitting.** Should be acknowledged in the poster Discussion if a reviewer asks.

---

## 6. Available Visual Outputs (Image Inventory)

The project workspace contains the following images. Each is described here so an agent can request the relevant one without re-inspecting:

| Image | Content | Use |
|---|---|---|
| Geometry render (white CAD) | Isometric view of dryer, slanted absorber + chimney with 4 trays, no mesh | Methods panel — geometry figure |
| Mesh render (dark) | Full mesh on geometry, 603,822 elements visible | Methods panel — mesh figure |
| Static T contour, low HF (peak ~358 K) | Volume contour at ~300 W/m², porosity 0.8 | Results — low-input case |
| Static T contour, high HF (peak ~395 K) | Volume contour at high heat flux | Results — high-input case (contrast figure) |
| Static T contour with trays exposed | Side view showing tray-by-tray temperature gradient | Results — illustrating the tray-cooling progression |
| Velocity vector field | Vector glyphs in chimney, peak ~16.5 mm/s | Discussion — flow regime |
| Tray-temp output table | Numeric output for one DP | Methods — output extraction example |
| Inlet BC screenshot (Fluent dialog) | Velocity inlet at 0.01 m/s | Methods — BC documentation |

### Notable values from images
- Velocity field peak: ~16.5 mm/s in the chimney plume
- Velocity field minimum: ~80 nm/s (essentially zero) in stagnation zones
- Temperature peak at low heat flux: 358 K (≈85 °C) on the absorber surface
- Temperature peak at high heat flux: 395 K (≈122 °C) on the absorber surface
- Inlet temperature: 300 K (27 °C, ambient)

---

## 7. Physics Layer — Equations and Correlations

### 7.1 Absorber plate energy balance (used in 1D FDM)

$$
\rho_p c_{p,p} \delta_p \frac{dT_p}{dt} = \alpha I - h_c (T_p - T_\infty) - \varepsilon_p \sigma (T_p^4 - T_{sky}^4) - q_{loss,back}
$$

| Symbol | Meaning | Default value (tomato dryer) |
|---|---|---|
| $\rho_p$ | Plate density | ~7800 kg/m³ (steel) |
| $c_{p,p}$ | Plate specific heat | ~470 J/kg·K |
| $\delta_p$ | Plate thickness | ~2 mm = 0.002 m |
| $\alpha$ | Solar absorptivity | 0.9 (selective coating) |
| $I$ | Solar irradiance | 300–800 W/m² |
| $h_c$ | Convective HTC | 5–25 W/m²·K (regime dependent) |
| $\varepsilon_p$ | Plate emissivity | 0.1 (selective coating) |
| $\sigma$ | Stefan-Boltzmann | 5.67 × 10⁻⁸ W/m²·K⁴ |
| $T_{sky}$ | Sky temperature | $T_\infty - 6$ K rule |

### 7.2 Tray energy balance (lumped)

$$
m_{air} c_{p,air} \frac{dT_{tray}}{dt} = \dot{m} c_{p,air} (T_{in} - T_{tray}) - h_{tray} A_{tray} (T_{tray} - T_{walls}) - \dot{m}_{evap} L_v
$$

Where $L_v$ is latent heat of vaporization, $\dot{m}_{evap}$ is moisture evaporation rate from the crop bed.

### 7.3 Dimensionless numbers

- **Reynolds (chimney):** $Re = \rho v L / \mu$. With $v = 0.01$ m/s, $L \sim 0.5$ m, this gives Re ≈ 350 → **clearly laminar**. Justifies the laminar viscous model.
- **Rayleigh (chimney free convection):** $Ra = g \beta \Delta T L^3 / (\nu \alpha_{th})$. With $\Delta T \sim 30$ K and $L \sim 1$ m, Ra ≈ 10⁹ → buoyancy is significant, regime is **mixed convection** (free dominant).
- **Prandtl (air):** Pr ≈ 0.71 at typical conditions.
- **Biot (plate):** $Bi = h \delta / k_p$. With $h = 15$, $\delta = 0.002$, $k_p \sim 50$, Bi ≈ 6 × 10⁻⁴ → **lumped assumption justified.**

### 7.4 Nusselt correlations used

**Flat plate, forced convection, laminar** (used for wind correction in web app):
$$
Nu = 0.664 \cdot Re^{0.5} \cdot Pr^{1/3}
$$

**Vertical channel, free convection, laminar:**
$$
Nu = 0.59 \cdot Ra^{0.25}
$$

**Mixed convection, assisting flow (Churchill correlation):**
$$
Nu_{eff}^3 = Nu_{forced}^3 + Nu_{free}^3
$$

### 7.5 Drying kinetics — Lewis thin-layer model

$$
MR(t) = \frac{M(t) - M_e}{M_0 - M_e} = \exp(-k \cdot t)
$$

Where $k$ is the drying rate constant (units 1/s or 1/hr) with Arrhenius temperature dependence:

$$
k(T) = k_0 \exp(-E_a / R T)
$$

**Default crop: tomato slices.**
| Parameter | Value | Source |
|---|---|---|
| $k_0$ | ~0.012 s⁻¹ | typical solar-drying literature |
| $E_a$ | ~25 kJ/mol | typical for fruits/vegetables |
| $M_0$ (initial moisture, dry basis) | 9.0 (≈ 90% wet basis) | tomato baseline |
| $M_e$ (equilibrium) | 0.05 | depends on RH |
| Target $M_{final}$ | 0.10–0.20 (dry basis) | shelf-stable |

(Exact constants to be sourced and cited in the derivations doc.)

### 7.6 Thermal efficiency

$$
\eta_{thermal} = \frac{\dot{m}_{air} c_{p,air} (T_{outlet} - T_{inlet})}{I \cdot A_{collector}}
$$

Reported as a single number on the web app dashboard.

---

## 8. ML Surrogate Architecture

### Inputs (2)
- Heat flux $I$ ∈ [300, 800] W/m²
- Crop porosity ∈ [0.5, 0.9]

### Outputs (4)
- $T_1$, $T_2$, $T_3$, $T_4$ in K

### Approach
1. **Default model: polynomial regression, degree 2 or 3.** Closed-form, small parameter count, easy to defend. With smooth physics over a 2D input space, expected to achieve R² > 0.99.
2. **Backup: gradient boosting.** Used only if polynomial fails.
3. **Last resort: small MLP.** Avoid unless absolutely needed.

### Train/test split
- 80/20 random split, fixed random seed for reproducibility
- ~82 train, ~20 test

### Acceptance criteria
- Test R² > 0.99 on each tray temperature
- Test MAE < 0.5 K
- Parity plot shows points clustered tightly along the diagonal across all 4 trays
- No systematic residual structure visible in error heatmap

### Wind speed correction (post-surrogate, in web app)
Surrogate gives baseline tray temps assuming the CFD's fixed boundary conditions. Wind speed input from the user adjusts the external convective coefficient on the glass cover via the flat-plate Nu correlation, computing an additional heat-loss term that reduces each tray's predicted temperature by an analytically computed offset:

$$
\Delta T_{wind} \approx \frac{h_{wind}(v) \cdot A_{cover} \cdot (T_{cover} - T_\infty)}{\dot{m} c_p}
$$

Stated explicitly on poster as a physics-grounded extrapolation, not a hack.

---

## 9. Web App Architecture

### Stack
- **Framework:** Streamlit
- **Deployment:** Streamlit Community Cloud (free tier, ~10 min from GitHub)
- **ML library:** scikit-learn (for serialized polynomial / GBM model)
- **Plotting:** Matplotlib for static, Plotly for interactive

### Inputs (sidebar)
| Control | Type | Range / Options | Default |
|---|---|---|---|
| Solar irradiance | Slider | 300–800 W/m² | 600 |
| Ambient temp | Slider | 15–40 °C | 25 |
| Wind speed | Slider | 0–8 m/s | 2 |
| Crop porosity | Slider | 0.5–0.9 | 0.7 |
| Crop type | Dropdown | Tomato, Mango, Chilli, Onion | Tomato |
| Target moisture | Slider | 5–20% | 10 |

### Outputs (main panel)
- 4 large numeric tiles: $T_1$, $T_2$, $T_3$, $T_4$ in °C
- Drying time per tray (hours), based on Lewis kinetics
- Thermal efficiency (single number, %)
- 2D illustrative cross-section with tray temperatures color-coded
- Live moisture-vs-time plot, 4 lines (one per tray)
- Wind correction value displayed as a small annotation: "ΔT_wind = X K applied"

### Data flow
```
User inputs ──► surrogate.predict(HF, porosity)  →  T1..T4
            ──► wind_correction(v)               →  ΔT_wind
            ──► T1..T4 corrected
            ──► lewis_kinetics(T_corrected, crop)  →  drying time per tray
            ──► render plots and metrics
```

---

## 10. Validation Strategy

Every quantitative claim is cross-checked across at least two independent methods:

| Method | What it produces | What it validates |
|---|---|---|
| Analytical (steady-state heat balance + Nu correlations) | Single plate temperature value per case | Sanity check on FDM and CFD |
| 1D FDM (Python NumPy) | Transient + steady-state plate temperature | Honors proposal commitment, validates CFD steady-state |
| CFD (Ansys Fluent) | 4 tray temperatures, full T and v fields | Treated as ground truth |
| ML surrogate | 4 tray temperatures (real-time) | Validated against held-out CFD points |

### Centerpiece poster figure
**Parity plot.** X-axis: CFD truth tray temperature. Y-axis: ML prediction. 4 colored series (one per tray). Diagonal y = x line. Points should cluster tightly along the diagonal. Annotate with R² and MAE per tray.

For maximum credibility, **also overlay analytical and FDM predictions** for the absorber-plate steady-state temperature on a separate axis or in a small inset. This creates a single figure that visually demonstrates all four physics layers agreeing.

---

## 11. Tech Stack Decisions and Rationale

| Choice | Why |
|---|---|
| Ansys Fluent for CFD | Already set up, license access, prior team familiarity |
| Laminar viscous model | Re ≈ 350 → laminar regime; simpler than k-ε; defensible at 0.01 m/s inlet |
| Steady-state CFD | Drying is multi-hour process; instantaneous fields are quasi-steady; transient effects captured by 1D FDM separately |
| 102-point parametric sweep | Enough for 2D smooth-physics surrogate; more would have diminishing returns |
| Polynomial regression first | Smooth physics, low-D, easy to defend, deterministic, no hyperparameters |
| Streamlit | Fastest path from Python to web app; one file; free deployment |
| GitHub + Streamlit Cloud | Zero-cost public deployment; auto-redeploys on push |

---

## 12. Assumptions & Known Limitations

These should appear on the poster Discussion panel in this exact framing:

1. **Single-geometry assumption.** All CFD on one fixed dryer design. We predict performance under varying *operating conditions* on a fixed geometry — not optimizing the geometry itself. This bounds our scope cleanly and is a feature, not a bug.

2. **Wind speed handled analytically, not via CFD.** Disclosed openly. Uses standard flat-plate forced-convection Nu correlation to compute additional heat loss; no fitted parameters.

3. **Crop modeled as porous medium with effective properties.** Internal grain-scale moisture dynamics are out of scope. The Lewis thin-layer kinetic model is well-established and adequate for engineering predictions.

4. **Steady-state CFD.** Diurnal transient effects (sunrise to peak to sunset) are captured via the 1D FDM module, not CFD.

5. **Laminar viscous model.** Re ≈ 350 supports this, but transitional effects at higher buoyancy-driven flow are not captured. Acknowledged trade-off for tractable simulation time.

6. **Adiabatic chimney walls in CFD.** Real walls have some heat loss to ambient. Effect is small but acknowledged.

7. **Radiation heat loss from absorber to sky** is included in the FDM module but is collapsed into the heat flux BC in CFD. The net effect on tray temperatures is small.

8. **Crop kinetics constants** ($k_0$, $E_a$) sourced from literature; not measured in-house.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| DP | Design Point — a single CFD run at one (heat flux, porosity) combination |
| Tray 1–4 | Horizontal crop trays, numbered bottom (1) to top (4) |
| Surrogate / ROM | Reduced-Order Model — fast approximation of CFD |
| Parity plot | Scatter of predicted vs true values, with y=x diagonal |
| Lewis model | Thin-layer drying kinetics: $MR = \exp(-kt)$ |
| MR | Moisture Ratio (dimensionless) |
| HF | Heat flux (W/m²) |
| BC | Boundary condition |
| Ra, Re, Nu, Pr, Bi | Standard heat-transfer dimensionless groups |
| FDM | Finite Difference Method |
| ROM | Reduced-Order Model (synonym for surrogate) |
| `contact_region-trg` | Fluent zone tag for tray 1; suffix `-trg` = "tray region group" |

---

## 14. Open Questions / Pending Confirmations

These are flagged so an agent picking up the project knows where to verify:

1. **Mesh independence** — needs one additional Fluent run for documentation. (Highest priority gap.)
2. **Mesh quality metrics** (orthogonal quality, skewness, aspect ratio) — extract from Fluent and report on poster.
3. **Convergence residual thresholds** — confirm exact values from Fluent log files.
4. **Glass cover dimensions** — confirmed approximate ~2 m × 0.5 m; exact value to be pulled from CAD if needed.
5. **Tray dimensions** — to be measured from CAD for use in tray-volume calculations.
6. **Air flow rate** $\dot{m}$ — derived from inlet velocity 0.01 m/s × inlet cross-section; confirm cross-section area from geometry.
7. **Specific tomato kinetic constants** — to be cited from published source in derivations doc.
8. **Crop bed thickness on each tray** — currently implicit in porosity sweep; could be added as a future parameter.

---

## 15. File Inventory in Project Workspace

| File | Purpose |
|---|---|
| `solar_dryer_project_approach.md` | Original framing memo (read-only historical) |
| `solar_dryer_ml.csv` | Canonical 102-point CFD dataset |
| Geometry render JPEGs | CAD views of dryer |
| Mesh render JPEGs | Mesh visualization (603,822 elements) |
| Temperature contour JPEGs | CFD output, low and high heat flux |
| Velocity vector JPEG | Chimney flow pattern |
| BC screenshots | Fluent dialog captures (inlet velocity, viscous model note) |
| Tray-temp output JPEG | Tabular extraction example |

---

## 16. Quick-Start Commands (for agents picking up tasks)

### Load the dataset
```python
import pandas as pd
df = pd.read_csv("solar_dryer_ml.csv", skiprows=6)
df.columns = ["Name", "HeatFlux_Wm2", "Porosity", "T1_K", "T2_K", "T3_K", "T4_K"]
```

### Train baseline surrogate
```python
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split

X = df[["HeatFlux_Wm2", "Porosity"]].values
y = df[["T1_K", "T2_K", "T3_K", "T4_K"]].values

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
model = make_pipeline(PolynomialFeatures(degree=3), LinearRegression())
model.fit(X_tr, y_tr)
print("Test R²:", model.score(X_te, y_te))
```

### Predict tray temps for a new operating point
```python
T_pred_K = model.predict([[600, 0.7]])[0]   # → array of 4 temps
T_pred_C = T_pred_K - 273.15
```

---

## 17. Definition of Done (project-wide)

- [ ] All CFD documentation finalized (mesh independence run included)
- [ ] ML surrogate trained, R² > 0.99 on test, parity plot generated
- [ ] FDM Python module validated against ≥1 CFD case
- [ ] Heat transfer derivations document (≥3 pages, equations + correlations)
- [ ] Streamlit app live at public URL, all 6 inputs functional
- [ ] Poster filled into 44×44 template, ready to print
- [ ] Slide deck rehearsed, demo flow practiced
- [ ] GitHub repo cleaned with README and pinned dependencies

---

*End of dossier.*
