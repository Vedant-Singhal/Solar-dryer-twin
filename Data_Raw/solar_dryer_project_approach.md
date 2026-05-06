# Solar Dryer Digital Twin — Project Approach
*CLL251: Heat Transfer for Chemical Engineers*

## What we're building (one-liner)

A **CFD-trained surrogate model for real-time thermal prediction of an agricultural solar dryer**, deployed as an interactive web app. Users adjust solar irradiation, ambient conditions, and crop properties via sliders and instantly see predicted tray temperatures, drying time, and thermal efficiency — without running CFD themselves.

## Framing relative to the submitted proposal

The submitted abstract committed us to a numerical model of transient heat transfer in a solar dryer using the finite difference method, with conduction, convection, and solar radiation as the heat transfer modes. We are honoring all of that and expanding the deliverable, not pivoting away from it.

The expansion: instead of stopping at a standalone 2D FDM script, we generate a CFD parametric dataset, train a machine-learning reduced-order model on it, wrap a 1D FDM module alongside it as a physics anchor, and deploy the whole thing as a web tool. The heat transfer physics is the backbone; the CFD adds fidelity; the ML enables real-time inference; the web app makes it usable.

This framing matters because:
- The prof grading a heat transfer course wants heat transfer content. We deliver derivations, dimensionless analysis, and an FDM solver alongside CFD.
- A standalone script is invisible after submission. A working web tool is something the prof can click on and play with.
- Every layer is independently defensible in viva because each is grounded in different physics.

## Technical pipeline

```
Analytical HT  ──┐
                 │
1D FDM (Python) ─┼──► Cross-validation ──► Confidence in physics
                 │
CFD (Ansys) ─────┤
                 │
                 └──► 102-point CSV ──► ML surrogate (ROM) ──► Streamlit web app
```

Three layers of modeling that all describe the same physics at different fidelities, validated against each other, with the cheapest layer (ML) deployed for end users.

## What we already have

- **102 CFD design points** from Ansys (Heat flux 300–800 W/m² × Crop porosity 0.5–0.9 → 4 tray temperatures). This is our training dataset.
- **One full geometry** with temperature contours and velocity vector fields.
- **Access to the Ansys workspace** — additional runs are possible if needed.

## What we need to add

### CFD work (small additions, focused on validation)

1. **2–3 validation runs** at parameter combinations *not* present in the training dataset (e.g., 650 W/m² × 0.65 porosity). These become the test set for the ML parity plot — the most important credibility figure on the poster.
2. **One contrasting contour image** at low heat flux (~300 W/m²) so we can show a side-by-side "low solar input vs high solar input" visual on the Results panel.
3. **Documented CFD setup**: geometry dimensions, boundary conditions, turbulence model, mesh element count, solver settings, convergence criterion. Goes verbatim into the Methods panel.
4. **Mesh independence note** if not already done — two meshes is enough for a defensible "Δresult < X% — mesh-independent" statement.

We are *not* expanding the parametric sweep further. 102 points across 2 inputs is plenty for the surrogate.

### Python FDM module

A 1D unsteady solution of the absorber plate energy equation:

ρ·c_p·δ·∂T/∂t = α·I − h·(T − T∞) − ε·σ·(T⁴ − T_sky⁴)

Solved with explicit Euler in NumPy. Compares its steady-state plate temperature to CFD as a third validation point. Honors the FDM commitment in the submitted proposal and gives us pure heat transfer content for the Methods section.

### Heat transfer analysis

Standard physics layer feeding everything else:
- Energy balance on absorber plate, lumped balance on each tray, coupled mass-energy balance for moisture evaporation in the crop bed.
- Dimensionless analysis: Rayleigh and Reynolds numbers in the chimney to confirm convection regime; Nusselt correlations (flat plate forced/natural, vertical channel) to estimate h.
- Drying kinetics via the Lewis thin-layer model: MR = exp(−k·t), with k = k₀·exp(−E_a/R·T) for one chosen crop (default: tomato slices). This translates tray temperatures into drying time — the metric end-users actually care about.

### ML surrogate

Trained on the 102-point CSV. Approach:
- Hold out ~20% as test set
- Start with polynomial regression (deg 2 and 3) and gradient boosting
- Only escalate to a small MLP if simple models underperform
- With 102 points and 2 input dimensions, polynomial regression will likely win and is far easier to defend

Output: a `predict(heat_flux, porosity) → (T₁, T₂, T₃, T₄)` function callable in milliseconds.

### Web application

**Stack:** Streamlit (Python) deployed to Streamlit Community Cloud (free, ~10 min deploy from a GitHub repo).

**Inputs:**
- Solar irradiation (W/m²) — slider
- Ambient temperature (°C) — slider
- Wind speed (m/s) — slider, handled via Nu correlation overlay since wind isn't in the CFD dataset
- Crop porosity — slider
- Crop type — dropdown (affects drying kinetics constants)

**Outputs:**
- Predicted tray temperatures T₁…T₄
- Drying time to target moisture (hr)
- Thermal efficiency η = ṁ·c_p·ΔT / (I·A)
- Color-coded 2D cross-section showing temperature gradient
- Live moisture-vs-time curve

**Wind speed handling (important to be honest about):** the CFD dataset doesn't include wind speed as a variable. We model its effect via the flat-plate forced-convection correlation Nu = 0.664·Re^0.5·Pr^(1/3), which adjusts the convective coefficient h on the dryer's external surfaces and corrects the ML prediction analytically. This will be stated explicitly on the poster Discussion panel — it's a physics-grounded correction, not a hack.

## Validation strategy

Every claim is cross-checked across at least two independent methods:

1. **Analytical** — closed-form steady-state plate temperature from heat balance with Nu correlations.
2. **FDM (Python)** — 1D unsteady solution of the absorber plate energy equation.
3. **CFD (Ansys)** — high-fidelity simulation, treated as ground truth.
4. **ML surrogate** — trained on (3), validated against held-out CFD runs.

The centerpiece poster figure is a parity plot showing analytical, FDM, CFD, and ML predictions agreeing within a defensible error band.

## Deliverables

| Deliverable | Format |
|---|---|
| Working web app | Public Streamlit URL |
| Poster | Filled into the provided 44×44 template |
| Presentation | Slide deck with live demo of the web app |
| Backing repo | Cleaned CSV, training notebook, FDM script, derivations document, web app code |

## Workstreams

Four parallel tracks. Each needs an owner; some can be combined depending on bandwidth.

| Track | Scope |
|---|---|
| **CFD & validation** | Run additional CFD cases, document setup, generate contour images, mesh independence note |
| **Heat transfer & FDM** | Derivations, dimensionless analysis, Python FDM solver, drying kinetics module, analytical sanity checks |
| **Surrogate & web app** | Train models on CSV, parity plots, error analysis, build & deploy Streamlit |
| **Deliverables** | Poster, presentation slides, integration of figures from other tracks |

## Tech stack

- **CFD:** Ansys Fluent (existing setup)
- **FDM solver:** Python + NumPy
- **ML:** scikit-learn (polynomial regression, gradient boosting; MLP only if needed)
- **Web app:** Streamlit
- **Plots:** Matplotlib for static figures, Plotly for any interactive 3D
- **Deployment:** Streamlit Community Cloud
- **Version control:** GitHub — one repo, everyone clones, push to a shared branch

## Risks & assumptions to state explicitly

- **Single-geometry assumption.** All CFD is on one dryer design. We are predicting performance under varying *operating conditions* on a fixed geometry, not optimizing the geometry itself. This is a feature, not a bug — it bounds our scope cleanly.
- **Wind speed handled analytically, not via CFD.** Disclosed openly on the poster.
- **Crop modeled as porous medium with effective properties.** Internal grain-scale moisture dynamics out of scope.
- **Steady-state CFD.** Diurnal transient effects (sunrise-to-sunset) are captured via the FDM module, not CFD.

## Definition of done

- Streamlit app live at a public URL
- Poster filled into the provided template, ready to print
- Presentation deck with live demo flow rehearsed
- Repo contains: cleaned CSV, surrogate training notebook with parity plots, FDM Python script, heat transfer derivations document, full web app code, README with deployment instructions
