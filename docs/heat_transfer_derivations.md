# Heat Transfer Derivations — Solar Air Dryer

*CLL251: Heat Transfer for Chemical Engineers · IIT Delhi*
*Companion document to the project's CFD, FDM, and ML surrogate layers.*

---

## Notation

| Symbol | Meaning | Units |
|---|---|---|
| $T$ | Temperature | K |
| $T_p$ | Absorber-plate temperature | K |
| $T_\infty$ | Ambient air temperature | K |
| $T_{sky}$ | Effective sky temperature | K |
| $I$ | Solar irradiance on the absorber | W/m² |
| $\alpha$ | Solar absorptivity | – |
| $\varepsilon$ | Longwave emissivity | – |
| $\sigma$ | Stefan–Boltzmann constant, $5.67 \times 10^{-8}$ | W/m²·K⁴ |
| $\rho_p, c_{p,p}, \delta_p$ | Plate density, specific heat, thickness | kg/m³, J/kg·K, m |
| $h_c$ | Convective heat-transfer coefficient | W/m²·K |
| $\dot m, c_p$ | Air mass flow, specific heat | kg/s, J/kg·K |
| $A_c$ | Collector aperture area | m² |
| $k$ | Drying rate constant (Lewis model) | s⁻¹ |
| $k_0, E_a, R$ | Arrhenius pre-factor, activation energy, gas constant | s⁻¹, J/mol, J/mol·K |
| $MR$ | Moisture ratio $= (M-M_e)/(M_0-M_e)$ | – |

---

## 1. Energy Balance on the Absorber Plate

### 1.1 Differential form

Apply the first law to a thin slab of absorber plate of thickness $\delta_p$ and unit area. Energy stored in the slab equals net energy in:

$$
\rho_p c_{p,p} \delta_p \frac{\partial T_p}{\partial t}
\;=\; \underbrace{\alpha I}_{\text{solar absorbed}}
\;-\; \underbrace{h_c (T_p - T_\infty)}_{\text{convection to chimney air}}
\;-\; \underbrace{\varepsilon \sigma (T_p^4 - T_{sky}^4)}_{\text{LW radiation to sky}}
\;-\; \underbrace{q''_{back}}_{\text{back-loss to ambient}} \quad \text{[W/m²]}
$$

For the present project the bottom of the plate is insulated, so $q''_{back} \approx 0$.

### 1.2 Justification of lumped-capacitance assumption

The Biot number for the plate is

$$
Bi = \frac{h_c \, \delta_p}{k_p}
\;=\; \frac{15 \cdot 0.002}{50}
\;\approx\; 6 \times 10^{-4}
$$

This is four orders of magnitude below the threshold $Bi < 0.1$ at which spatial gradients across the plate become negligible. The plate may be treated as a single thermal node — i.e. $T_p$ depends only on time, not on the through-thickness coordinate. This collapses the PDE into the ODE used in §3.

### 1.3 Sky temperature

A common engineering rule (Swinbank, 1963; Duffie & Beckman) sets

$$T_{sky} \approx T_\infty - 6 \text{ K}$$

for clear-sky conditions. Effects of cloud cover, humidity, and elevation perturb this by a few K. This rule is used throughout the FDM module.

---

## 2. Lumped Energy Balance per Tray

Each of the four trays is modelled as a perfectly mixed control volume. The hot air enters at $T_{in}$ from below, cools as it deposits sensible heat into the crop and walls, and leaves at $T_{tray}$.

$$
m_{air} c_p \frac{dT_{tray}}{dt}
\;=\; \dot m \, c_p \, (T_{in} - T_{tray})
\;-\; h_t A_t (T_{tray} - T_{wall})
\;-\; \dot m_{evap} L_v
$$

Where $h_t A_t$ is the conductive/convective UA between the tray air and the wall, and $L_v \approx 2.45 \text{ MJ/kg}$ is the latent heat of vaporisation. At quasi-steady the inertial term vanishes and one obtains an algebraic relation per tray. Stacking these gives the monotonic descent $T_1 > T_2 > T_3 > T_4$ that the CFD data set respects (verified in `tests/test_surrogate.py::test_monotonicity`).

### 2.1 Coupled mass–energy balance for the crop bed

The crop bed acts as a porous medium. Mass-flux conservation at each tray:

$$
\frac{dM}{dt} = -k(T_{tray}) \, (M - M_e)
$$

Coupled to the air enthalpy balance through the latent term. For the surrogate-driven dashboard this coupling is *decoupled*: tray temperatures come from the surrogate, then drying time is computed by solving the crop ODE in isolation at the predicted $T_{tray}$. This separation is justified because the air's residence time in any single tray is much shorter than the drying timescale (seconds vs hours).

---

## 3. Reduction to the FDM Solver

Setting $q''_{back} = 0$ and rearranging §1.1:

$$
\frac{dT_p}{dt}
\;=\; \frac{1}{\rho_p c_{p,p} \delta_p}
\bigl[\alpha I - h_c (T_p - T_\infty) - \varepsilon \sigma (T_p^4 - T_{sky}^4)\bigr]
$$

### 3.1 Discretisation (explicit Euler)

$$
T_p^{\,n+1} = T_p^{\,n} + \Delta t \cdot f(T_p^{\,n})
$$

where $f$ is the right-hand side. Implementation: [`app/services/fdm.py`](../app/services/fdm.py).

### 3.2 Stability bound

Linearise the radiative term about a representative $T_{ref}$:

$$
\frac{d(\varepsilon \sigma T^4)}{dT} = 4 \varepsilon \sigma T^3 \;\Rightarrow\; h_{eff} = h_c + 4\varepsilon\sigma T_{ref}^3
$$

The amplification factor of explicit Euler stays below unity when

$$
\Delta t \;<\; \frac{\rho_p c_{p,p} \delta_p}{h_{eff}}
$$

In the code we apply a safety factor of 0.5 to this bound.

### 3.3 Steady state

At $dT_p/dt = 0$ the balance becomes the nonlinear algebraic equation

$$
\alpha I = h_c (T_p^{ss} - T_\infty) + \varepsilon \sigma (T_p^{ss\,4} - T_{sky}^4)
$$

solved by Newton iteration in `fdm.steady_state`. Sub-millikelvin agreement with the time-marched solution at $t = 1$ hr (see [`figures/fdm_validation_table.md`](../figures/fdm_validation_table.md)) confirms the integrator has converged.

---

## 4. Dimensionless Analysis in the Chimney

The chimney has $L \sim 0.5\text{ m}$, average air velocity $v \approx 0.01$ m/s (CFD inlet), and ambient air properties: $\rho \approx 1.1$ kg/m³, $\mu \approx 1.85 \times 10^{-5}$ Pa·s, $\nu \approx 1.7 \times 10^{-5}$ m²/s, $\alpha_{th} \approx 2.4 \times 10^{-5}$ m²/s, $\beta \approx 1/T \approx 3.3 \times 10^{-3}$ K⁻¹.

### 4.1 Reynolds (forced flow)

$$
Re = \frac{\rho v L}{\mu}
\;=\; \frac{1.1 \cdot 0.01 \cdot 0.5}{1.85 \times 10^{-5}}
\;\approx\; 297 \;\text{(rounded to ≈ 350 over 1 m)}
$$

This is two orders of magnitude below the laminar–turbulent transition for internal flow ($Re_{crit} \sim 2{,}300$). It justifies the **laminar viscous model** used in Fluent (technical dossier §4).

### 4.2 Rayleigh (free convection)

$$
Ra = \frac{g \beta \Delta T L^3}{\nu \alpha_{th}}
\;=\; \frac{9.81 \cdot 3.3{\times}10^{-3} \cdot 30 \cdot 1^3}{1.7{\times}10^{-5} \cdot 2.4{\times}10^{-5}}
\;\approx\; 2.4 \times 10^{9}
$$

So $Ra \sim 10^9$. Free convection is significant.

### 4.3 Mixed-convection regime

The ratio $Ra / Re^2 \approx 2.4 \times 10^9 / 350^2 \approx 2 \times 10^4 \gg 1$, indicating buoyancy dominates the inertial scale. The chimney is therefore in **buoyancy-driven mixed convection** with the free component dominant — consistent with the upward thermal plume seen in the velocity-vector field (dossier §6).

### 4.4 Prandtl

$$
Pr = \frac{\nu}{\alpha_{th}} \approx 0.71
$$

at typical air temperatures.

### 4.5 Biot (plate)

Already computed in §1.2: $Bi \approx 6 \times 10^{-4}$, lumped assumption holds.

---

## 5. Nusselt Correlations

### 5.1 Flat plate, laminar forced convection (used for wind correction)

$$
\overline{Nu_L} = 0.664 \, Re_L^{1/2} \, Pr^{1/3}, \qquad Re_L < 5 \times 10^5
$$

(Incropera & Bergman). This is the basis of the over-glass wind correction in [`app/services/physics.py`](../app/services/physics.py): an external wind speed $v_w$ raises $Re_L$ on the cover glass, which raises $h_w$ via the correlation, which steals a fraction of the (T_tray − T_∞) lift away from each tray.

For $Re_L > 5 \times 10^5$ the turbulent extension

$$
\overline{Nu_L} = (0.037 \, Re_L^{4/5} - 871) \, Pr^{1/3}
$$

is used; transition is set at $Re_{x,c} = 5 \times 10^5$ in code.

### 5.2 Vertical channel, laminar free convection

$$
\overline{Nu_L} = 0.59 \, Ra_L^{1/4}, \qquad 10^4 < Ra_L < 10^9
$$

Just below the present chimney's Ra, but the correlation is the conventional reference for the regime.

### 5.3 Mixed convection (Churchill superposition)

$$
\overline{Nu_{mixed}}^{\,3} = \overline{Nu_{forced}}^{\,3} + \overline{Nu_{free}}^{\,3}
$$

Used as a sanity check on the CFD's effective $h$ — both forced (induced flow) and free (buoyancy) contribute, and Churchill's cube-root combination is the engineering shorthand.

---

## 6. Drying Kinetics — Lewis Thin-Layer Model

### 6.1 Empirical kinetic law

$$
MR(t) = \frac{M(t) - M_e}{M_0 - M_e} = \exp(-k \, t)
$$

This is the simplest of the family of thin-layer models (Lewis 1921). It captures the falling-rate-period dominant kinetics of fruits and vegetables in solar drying.

### 6.2 Temperature dependence (Arrhenius)

$$
k(T) = k_0 \, \exp\!\left(-\frac{E_a}{R T}\right)
$$

The bridge from heat transfer to drying time:

$$
T_{tray} \;\xrightarrow{\text{Arrhenius}}\; k(T_{tray})
\;\xrightarrow{\text{invert MR}}\; t_{dry} = -\frac{1}{k}\ln\!\left(\frac{M_{target} - M_e}{M_0 - M_e}\right)
$$

### 6.3 Crop parameters used

Calibrated values in `physics.CROP_PARAMS` (replace with cited literature constants once available):

| Crop | $k_0$ (s⁻¹) | $E_a$ (J/mol) | Reference range $t_{dry}$ |
|---|---|---|---|
| Tomato | ~0.012 | ~25 000 | 8–20 hr |
| Mango | ~0.015 | ~28 000 | 10–24 hr |
| Chilli | ~0.010 | ~26 000 | 12–20 hr |
| Onion | ~0.008 | ~23 000 | 8–18 hr |

These yield drying times within the literature range at typical tray temperatures (see test `tests/test_physics.py`).

---

## 7. Thermal Efficiency

The dryer's instantaneous thermal efficiency is the fraction of incident solar power converted to enthalpy gain of the airstream:

$$
\eta_{th} = \frac{\dot m \, c_p \, (T_{out} - T_{in})}{I \cdot A_c}
$$

$\dot m$ is computed from the CFD inlet condition (0.01 m/s, ambient density, inlet area). $T_{out}$ is taken as the top-tray temperature $T_1$. The result is bounded to $[0,1]$ in code as a sanity guard. Typical values are 30–55% in the simulation envelope.

---

## 8. Wind Correction (Over-Glass Loss)

External wind on the slanted glass cover boosts the convective coefficient $h_w$ via the flat-plate correlation in §5.1 (using the cover's chord length $L_{cov}$ as the characteristic length and $\nu_{air}$, $Pr$ at film temperature). The extra loss reduces the cover-to-ambient temperature difference, which in turn reduces each tray's temperature lift over ambient.

We model this as a fractional shrink applied per tray:

$$
T_{tray}^{\,corrected} - T_\infty
\;=\; (1 - \phi) \cdot (T_{tray}^{\,surrogate} - T_\infty),
\qquad \phi = \min\!\left(\phi_{max}, \frac{h_w(v) - h_w(0)}{h_{ref}}\right)
$$

with $\phi_{max} = 0.5$ to prevent unphysical outputs at high wind. Earlier formulations that divided the wind-induced heat loss by the dryer's natural-convection mass flow were discarded after producing >100 K corrections; the fractional-shrink form is what now ships.

---

## References

1. Incropera, F. P. & Bergman, T. L. *Fundamentals of Heat and Mass Transfer*, 8th ed., Wiley.
2. Duffie, J. A. & Beckman, W. A. *Solar Engineering of Thermal Processes*, 4th ed., Wiley.
3. Swinbank, W. C. (1963) "Long-wave radiation from clear skies." *Q. J. R. Meteorol. Soc.* **89** (381), 339–348.
4. Lewis, W. K. (1921) "The rate of drying of solid materials." *J. Ind. Eng. Chem.* **13** (5), 427–432.
5. Churchill, S. W. (1977) "A comprehensive correlating equation for laminar, assisting forced and free convection." *AIChE J.* **23** (1), 10–16.
6. Akpinar, E. K. (2006) "Mathematical modelling of thin layer drying process under open sun of some aromatic plants." *J. Food Eng.* **77** (4), 864–870.

---

*Last updated 2026-05-06. Owner: project team. Cross-references: [`technical_context_dossier.md`](../technical_context_dossier.md) §7, [`app/services/physics.py`](../app/services/physics.py), [`app/services/fdm.py`](../app/services/fdm.py).*
