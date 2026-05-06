# Solar Dryer Digital Twin — Next Steps & Full Project Plan
*CLL251: Heat Transfer for Chemical Engineers — IIT Delhi*
*Status doc, last updated 06 May 2026 — reflects current GitHub repo state*

---

## 1. Project at a Glance

**One-liner.** A CFD-trained surrogate model for real-time thermal prediction of an agricultural solar dryer, deployed as an interactive web tool. Users adjust solar irradiation, ambient conditions, and crop properties and instantly see predicted tray temperatures, drying time, and thermal efficiency — without running CFD themselves.

**Why this framing works for grading.** The submitted abstract committed to a numerical model of transient heat transfer using FDM, with conduction, convection, and solar radiation. Every word of that is honored. The expansion is additive: CFD adds fidelity, ML enables real-time inference, the web app makes it usable. The professor of a heat transfer course sees heat transfer content (derivations, dimensionless analysis, FDM solver) and *also* gets a clickable demo, which is rare and memorable.

**Three layers of modeling, each independently defensible:**
1. Analytical heat balance (closed-form steady-state, Nu correlations)
2. 1D FDM Python solver (transient, explicit Euler)
3. CFD parametric sweep (Ansys Fluent, 102 design points)
4. ML surrogate (polynomial regression, trained on CFD)

The poster centerpiece is a parity plot showing all four agreeing within a defensible error band.

---

## 2. Where We Are Now (Audit — 06 May 2026)

### ✅ Completed

**CFD parametric sweep — 102 design points.**
- Heat flux: 300–800 W/m² (28 unique values)
- Crop porosity: 0.5–0.9 (9 unique values)
- Outputs: 4 area-weighted average tray temperatures (K)
- Stored in `Data_Raw/solar_dryer_ml.csv`
- Data is physically consistent: T₁ > T₂ > T₃ > T₄ holds for all 102 rows

**CFD setup documented.**
- Geometry, mesh (603,822 elements), inlet BC (0.01 m/s), laminar viscous model, porous trays — all captured in the technical dossier and ready to drop into the Methods panel.

**Visual outputs available.**
- Geometry, mesh, low-HF and high-HF temperature contours, velocity vector field, BC screenshots, tabular tray-temp output.

**ML surrogate — trained and gated.** *(`app/train/train_surrogate.py`, `app/services/surrogate.py`)*
- Polynomial regression, degree 3, multi-output (one pipeline → 4 tray temps).
- 80/20 train/test split, fixed seed (42).
- Hard acceptance gate enforced at training time:
  - Per-tray MAE < 0.5 K
  - Per-tray R² > 0.98
  - (Overall R² is reported but not gated — T₄'s small variance makes it misleading.)
- Metrics serialized to `surrogate-v1.metrics.json` alongside the joblib artifact.
- Tests in `tests/test_surrogate.py` cover both the acceptance criteria and the physical monotonicity invariant (T₁ > T₂ > T₃ > T₄ across a grid of synthetic inputs).

**Physics module — implemented and tested.** *(`app/services/physics.py`)*
- **Wind correction.** Flat-plate Nu correlation (laminar / turbulent regimes), returns a loss-fraction applied per-tray as a shrink on (T_tray − T_ambient). Capped at 50% to avoid unphysical outputs at high wind. Earlier formulation that divided heat loss by the dryer's tiny natural-convection mass flow was discarded — it produced >100 K corrections.
- **Lewis drying kinetics.** k(T) = k₀ exp(−Eₐ/RT) with Arrhenius constants tabulated for tomato, mango, chilli, onion. k₀ values calibrated so drying times land in the literature range (8–20 hr for tomato at typical tray temps); will be replaced with measured constants once the derivations doc has lab-fitted values.
- **Thermal efficiency.** η = ṁ·cp·ΔT / (I·A_collector), bounded to [0, 1].
- Unit tests in `tests/test_physics.py` cover zero-wind no-op, monotonic loss with wind speed, ambient floor on tray temps, drying-time monotonicity in T, and efficiency bounds.

**Backend API — production-grade, deployed-ready.** *(`app/`, `Dockerfile`, `docker-compose.yml`)*
- This is a deliberate expansion beyond the originally-planned single-file Streamlit app. The repo now ships a stateless FastAPI service backed by Postgres (audit log) + Redis (LRU prediction cache) + Prometheus (`/metrics`).
- Endpoints: `/healthz`, `/readyz`, `/v1/predict`, `/v1/simulate`, `/v1/predictions/recent`, plus auto-generated `/docs` (Swagger).
- `predict` returns just tray temps; `simulate` adds per-tray Lewis drying time and overall efficiency.
- Cache key includes `model_version` so version bumps invalidate automatically.
- SQLite fallback in dev (no Postgres needed); compose file wires up the full stack for production-like local runs.
- End-to-end smoke tests in `tests/test_api.py` (skipped if model artifact / Redis / Postgres are absent).

**Repo hygiene.**
- Pinned dependencies in `requirements.txt` (FastAPI 0.115, scikit-learn 1.5.2, etc.).
- `Dockerfile` runs as non-root user 1001.
- `.env.example` documents all `DRYER_*` env vars.
- `README.md` covers architecture, API contract, DB schema, caching strategy, and a 3-command local quickstart.
- `technical_context_dossier.md` is the canonical handoff doc for any new contributor or AI agent.

### ⚠️ Gap: Mesh Independence

We have one mesh at 603,822 elements but no second mesh for comparison. This is the only outstanding CFD task. Run **one** additional case at a representative parameter combo (suggested: 500 W/m², porosity 0.8) on a coarser mesh — target ~250–350k elements — and report the percent change in Tray-1 temperature. A delta below ~1% lets us state on the poster: *"Tray temperatures changed by <X% between coarse and fine meshes; results are mesh-independent within reported precision."* Time cost: one Fluent run + one number on a slide.

### ❌ Not Yet Started

| Track | What's missing |
|---|---|
| **Frontend UI** | The backend API works, but there's no user-facing demo yet. Need a thin Streamlit (or React) client that calls `POST /v1/simulate` and renders the 4 tray-temp tiles, drying time, efficiency, and moisture-vs-time curve. |
| **Parity plot artifact** | Training computes metrics but doesn't currently save the parity plot image. Add a small script (or notebook cell) that loads the joblib model, predicts on the held-out test set, and writes `figures/parity_plot.png` — this is the centerpiece poster figure. |
| **FDM module** | 1D unsteady absorber-plate solver, validation against CFD steady-state. Honors the proposal commitment. |
| **Heat transfer derivations** | Energy balances, Ra/Re/Nu/Bi analysis, drying kinetics derivation, properly cited. ~3–5 page document. |
| **Poster** | Layout, figure integration, copy. |
| **Presentation** | Slide deck, demo flow, rehearsal. |

---

## 3. Critical Path & Sequencing (Revised)

The original critical path was *surrogate → web app → poster*. With the surrogate trained, the physics module implemented, and the backend API deployable, the path now collapses:

```
                   ┌────────────────┐
                   │ Mesh indep run │ ◄── one Fluent run, non-blocking
                   └────────────────┘
   ┌──────────┐     ┌──────────────┐     ┌──────────────┐
   │ Frontend │     │ FDM module   │     │ HT derivs    │
   │ UI       │     │              │     │              │
   └────┬─────┘     └──────┬───────┘     └──────┬───────┘
        │                  │                    │
        └─────────────┬────┴────────────────────┘
                      ▼
              ┌────────────────┐
              │ Parity plot    │
              │ + Poster       │
              │ + Slides       │
              └────────────────┘
```

All four boxes at the top are independently parallelizable — none blocks another. The only remaining serial dependency is the parity plot artifact before poster figures.

---

## 4. Detailed Task Breakdowns

### ✅ Task 1 — ML Surrogate — DONE

Polynomial regression degree 3 implemented in `app/train/train_surrogate.py`. Per-tray MAE and R² gated at train time. Joblib artifact loaded as a singleton in `app/services/surrogate.py`. Tests cover acceptance and monotonicity.

**Remaining sub-task:** save a parity-plot image from the held-out test set. Suggested ~30 lines:

```python
# scripts/plot_parity.py
import joblib, json, matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from app.train.train_surrogate import load
df = load("Data_Raw/solar_dryer_ml.csv")
X = df[["HeatFlux_Wm2","Porosity"]].values
y = df[["T1_K","T2_K","T3_K","T4_K"]].values
_, Xte, _, yte = train_test_split(X, y, test_size=0.2, random_state=42)
pipe = joblib.load("models/surrogate-v1.joblib")
ypred = pipe.predict(Xte)
fig, ax = plt.subplots(figsize=(6,6))
for i, label in enumerate(["T₁","T₂","T₃","T₄"]):
    ax.scatter(yte[:,i], ypred[:,i], label=label, alpha=0.7)
lo, hi = yte.min(), yte.max()
ax.plot([lo,hi],[lo,hi],"k--", lw=1)
ax.set_xlabel("CFD truth (K)"); ax.set_ylabel("Surrogate prediction (K)")
ax.legend(); ax.set_aspect("equal")
plt.savefig("figures/parity_plot.png", dpi=200, bbox_inches="tight")
```

Annotate with R² and MAE per tray from `surrogate-v1.metrics.json`. **Time: 1 hour.**

---

### Task 2 — 1D FDM Python Module (NOT STARTED)

**Physics.** Lumped 1D unsteady energy balance on the absorber plate:

ρ · cp · δ · ∂T/∂t = α · I − h · (T − T∞) − ε · σ · (T⁴ − T_sky⁴)

Symbols and default values are captured in section 7.1 of the technical dossier — pull them from there.

**Method.** Explicit Euler in NumPy. Time step from stability bound: Δt < ρcpδ / h with safety factor 0.5.

**Validation.** Run to steady state at I = 300, 500, 800 W/m². Compare to CFD area-weighted absorber-surface temperature at the same heat flux. Report agreement percentage.

**Repo placement.** Put under `app/services/fdm.py` (so the API can optionally expose it as a third endpoint, e.g. `/v1/fdm/transient`) or as a standalone `notebooks/fdm_validation.ipynb` if the API integration is out of scope. Either is fine for the poster.

**Deliverables.**
- FDM script
- Plot: plate temperature vs time, multiple I values overlaid
- Comparison table: FDM steady-state vs CFD vs analytical, three irradiance levels
- Brief markdown writeup of derivation, discretization, stability check

**Time estimate.** 4–6 hours.

---

### Task 3 — Heat Transfer Derivations Document (NOT STARTED)

The technical dossier (section 7) already has every equation and dimensionless number assembled with default values. This task is rendering that content as a citable document with full derivations.

**Sections, in order:**

1. **Energy balance on absorber plate.** Differential and lumped forms. Justification of lumped assumption (Bi ≈ 6 × 10⁻⁴, well below 0.1 — already computed in the dossier).
2. **Lumped balance on each tray.** Air-side convective gain, conductive loss to walls, latent heat sink from moisture evaporation.
3. **Coupled mass-energy balance for the crop bed.** Crop layer as porous medium with effective thermal conductivity.
4. **Dimensionless analysis in the chimney.** Re ≈ 350 (laminar), Ra ≈ 10⁹ (mixed convection, free dominant), Pr ≈ 0.71. Cross-reference with the laminar viscous model used in CFD.
5. **Nusselt correlations.** Flat-plate forced (Nu = 0.664·Re⁰·⁵·Pr¹/³), vertical channel free (Nu = 0.59·Ra⁰·²⁵), Churchill mixed.
6. **Drying kinetics — Lewis thin-layer model.** MR = exp(−k·t), k = k₀·exp(−Eₐ/RT). Bridge: tray temperatures from surrogate → k(T) → drying time to target MR.

**Deliverables.**
- `docs/heat_transfer_derivations.md` (or `.pdf` from LaTeX)
- 3–5 pages, equation-heavy, with citations to Incropera/Bergman and crop-drying literature for kinetic constants

**Time estimate.** 5–8 hours, mostly writing.

**Note:** once this doc lands, the literature-cited Lewis constants supersede the calibrated placeholders currently in `app/services/physics.py:CROP_PARAMS`. Update both in the same PR.

---

### Task 4 — Frontend Web UI (NOT STARTED — REVISED FROM ORIGINAL)

**What changed from the original plan.** The original task was a single-file Streamlit app that loaded `surrogate.pkl` directly, computed wind correction inline, and rendered plots. The repo now has a fully separated architecture: a stateless FastAPI backend serving JSON over HTTP, with all physics + ML logic on the server side. **The frontend's job is now just to render — all computation is one HTTP call away.**

This is strictly an upgrade for the demo: the UI stays simple, but if anyone asks "could this scale?" or "is the physics testable in isolation?" the answer is yes, with the repo as evidence.

**Two viable frontend options:**

**Option A — Streamlit (recommended for time).**
```python
# frontend/streamlit_app.py
import streamlit as st, requests, plotly.graph_objects as go
API = st.secrets.get("API_URL", "http://localhost:8000")

with st.sidebar:
    hf       = st.slider("Solar irradiance (W/m²)", 300, 800, 600)
    porosity = st.slider("Crop porosity",            0.5, 0.9, 0.7)
    ambient  = st.slider("Ambient temp (°C)",        15,  40,  25)
    wind     = st.slider("Wind speed (m/s)",         0,   8,   2)
    crop     = st.selectbox("Crop", ["tomato","mango","chilli","onion"])

r = requests.post(f"{API}/v1/simulate",
                  json={"heat_flux":hf,"porosity":porosity,
                        "ambient_c":ambient,"wind_mps":wind,"crop":crop})
data = r.json()
# 4 metric tiles, drying-time table, moisture-vs-time Plotly curve, η badge
```
Deploy to Streamlit Community Cloud. Backend can run on Render/Fly/Railway free tier, or even alongside the Streamlit container. **Time: 4–6 hours.**

**Option B — Static HTML + fetch().** Single-page app, hostable on GitHub Pages. More polish, more time. Skip unless the team has a frontend specialist with cycles to spare.

**Inputs (sidebar).**
| Input | Range | Default | Maps to API field |
|---|---|---|---|
| Solar irradiance | 300–800 W/m² | 600 | `heat_flux` |
| Ambient temperature | 15–40 °C | 25 | `ambient_c` |
| Wind speed | 0–8 m/s | 2 | `wind_mps` |
| Crop porosity | 0.5–0.9 | 0.7 | `porosity` |
| Crop type | dropdown | Tomato | `crop` |
| Target moisture | 5–20% | 10 | `target_moisture_db` |

**Outputs.**
- 4 large numeric tiles: T₁..T₄ (°C, from response `temps`)
- Drying time per tray (hours, from response `trays`)
- Thermal efficiency badge (from response `thermal_efficiency`)
- Live moisture-vs-time curve, 4 lines (compute MR(t) = exp(−k·t) per tray on the client; rate constants come back in the response)
- Annotation: "Wind correction applied: ΔT = X K" (from response `wind_correction_k`)

---

### Task 5 — Poster (NOT STARTED)

**Format.** 44" × 44" template provided by course.

**Suggested panel layout (10 panels):**
1. Title + team + course
2. Abstract / one-liner (matches submitted proposal language)
3. Geometry + photo of physical reference (if any)
4. Problem framing: why solar drying, why thermal modeling
5. Methods: CFD setup (mesh, BCs, solver) + governing equations
6. Methods: FDM derivation + ML surrogate approach + system architecture sketch (showing FastAPI + cache + DB; this is unusual for a heat-transfer poster and worth showcasing)
7. Results: contour comparison (low vs high heat flux)
8. Results: parity plot (CFD vs ML, the centerpiece)
9. Results: web app screenshot + drying-time prediction examples + p50/p99 latency from `/metrics`
10. Discussion (assumptions, wind correction note, limitations) + Conclusion + References + QR code to web app

**Time estimate.** 6–10 hours, mostly figure refinement and copy.

---

### Task 6 — Presentation (NOT STARTED)

- 10–12 slides
- 2 slides for problem and motivation
- 2 slides for CFD methods + results
- 2 slides for FDM + analytical
- 2 slides for ML approach + parity plot
- 2 slides for live web-app demo (screenshare with sliders being moved + a peek at `/docs` Swagger to show the underlying API)
- 1 slide for limitations and future work
- 1 slide closing + Q&A

Rehearse the demo specifically — that's the moment that makes the project memorable. Have a fallback screenshot in case Wi-Fi flakes. If demoing the API directly, have `curl` commands pre-typed in the terminal.

**Time estimate.** 4–6 hours.

---

## 5. Workstream Allocation (Revised)

| Track | Tasks | Status | Dependencies |
|---|---|---|---|
| **A. CFD validation** | Mesh-independence run, finalize contour figures | Outstanding (1 Fluent run) | None |
| **B. Heat transfer + FDM** | Tasks 2 + 3 | Not started | None |
| **C. Frontend + parity plot** | Task 4 + parity plot artifact | Backend done; UI + plot pending | Backend (✅) |
| **D. Deliverables** | Tasks 5 + 6 | Not started | Outputs from A, B, C |

**Recommended distribution:**
- One person owns **C** end-to-end (parity plot is small; UI is the gating item for the demo).
- One person owns **B** (FDM + derivations together — they're closely related physics).
- One person handles **A** + starts **D** in parallel.

---

## 6. Risk Register (Updated)

| Risk | Likelihood | Impact | Status / Mitigation |
|---|---|---|---|
| Mesh independence shows >5% delta | Low | Medium | Re-run at finer mesh; if persistent, report honestly with disclaimer |
| Polynomial surrogate underfits | ~~Low~~ Resolved | — | Per-tray MAE and R² acceptance gates pass at training time |
| Streamlit Cloud quota issues | Low | Low | Backend can self-host; print QR linking to repo as fallback |
| Backend deployment friction | Medium | Medium | **NEW** — FastAPI + Postgres + Redis is heavier than a single Streamlit script. Mitigation: Docker compose works locally; for live demo, a `docker compose up` on a laptop is sufficient. Render/Fly free tier as second fallback. |
| FDM doesn't match CFD within 5% | Medium | Low | Acknowledge as expected — 1D vs 3D will differ; report the gap as a learning |
| Drying-kinetics constants for chosen crop are uncertain | Medium | Low | Calibrated placeholders in `physics.py` already produce literature-range drying times; once derivations doc cites measured constants, replace and re-test |
| Time crunch near deadline | High | High | Lock down poster figures by Day −3; demo rehearsal Day −1 |

---

## 7. Definition of Done

- [x] ML surrogate trained, R² and MAE gates pass on test set
- [x] Physics module (wind, kinetics, efficiency) implemented and unit-tested
- [x] Backend API deployable via `docker compose up`, with `/healthz`, `/readyz`, `/metrics`
- [x] Pinned dependencies, README, technical dossier in repo
- [ ] Parity plot artifact saved to `figures/parity_plot.png`
- [ ] Frontend UI (Streamlit or HTML) live at a public URL, calling the API
- [ ] Mesh-independence statement on poster with concrete number
- [ ] FDM Python script in repo, validated against ≥1 CFD case
- [ ] Heat transfer derivations document in repo, ≥3 pages with equations
- [ ] Poster filled into provided 44×44 template, ready to print
- [ ] Slide deck rehearsed, demo flow practiced ≥1 time
- [ ] All four physics layers (analytical, FDM, CFD, ML) cross-validated and visible on the poster

---

## 8. Communication & Handoff

**Repo.** Single GitHub repo, shared branch model: `main` for stable, feature branches for in-progress work, PR review optional given small team.

**File conventions.**
- Production code lives under `app/`. Notebooks and one-off scripts under `notebooks/` and `scripts/`.
- All scripts have docstrings on every function.
- Plots saved as both PNG (for poster) and SVG (for vector embedding) under `figures/`.
- Data in `Data_Raw/`, code in `app/`, tests in `tests/`, generated artifacts in `models/` and `figures/`.

**Synchronization.** Daily 15-min standup until deadline week, then twice daily. WhatsApp for ad-hoc.

**Context handoff to AI agents.** Use `technical_context_dossier.md` as the single source of truth for any new agent or team member spinning up. It contains the complete technical state of the project. **This file (`01_next_steps_and_project_plan.md`) is the live status doc — keep it updated as items move from "Not Started" to "Done".**

---

## 9. Immediate Next 24 Hours

The original "train the surrogate" critical-path is done. Three independently-parallelizable items now sit at the top of the queue. If only **one** thing happens in the next day, pick the one whose owner has bandwidth:

1. **Generate the parity plot.** ~1 hour. Unblocks the poster's centerpiece figure. Use the snippet in Task 1 above.
2. **Build the Streamlit frontend.** ~4–6 hours. Unblocks the live demo. Backend is already running and documented; Task 4 has the skeleton code.
3. **Run the mesh-independence case in Fluent.** ~1–2 hours of compute + 10 minutes of writeup. Unblocks the methods panel.

If two people are available: pair on (1)+(2) — the parity plot can be embedded directly in the Streamlit dashboard as the "model accuracy" tab, killing two birds.

If three people are available: tackle (1), (2), and (3) in parallel; start (Task 2) FDM as soon as someone frees up.
