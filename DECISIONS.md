# Modeling decisions

Group decisions on the open questions of the model. Each one says what the
code does and where.

| # | Decision | What we chose | Where in the code |
| --- | --- | --- | --- |
| 1 | Rider types | Time trial specialist and climber, each in a men's and a women's version | `profiles/` |
| 2 | Max power | 2-parameter CP model + a constraint P ≤ P_max | `RiderParams.p_max`, solver bounds |
| 3 | Recovery model | W′ balance ODE (Skiba et al. 2015): dB/dt = (1 − B/W′)(CP − P) below CP, with CP and W′ the rider's current values (see no. 12) | `power_model/cp_model.py` (α = β = 1) |
| 4 | Notation | **B** is the remaining W′ reserve (W′_bal in Skiba's papers). CP, s, t in seconds, P everywhere. | everywhere |
| 5 | Drivetrain efficiency | Keep η as a parameter, **η = 0.977** (a 2.3% chain loss), from Martin et al. (1998). P is the rider's pedal power; η P reaches the wheel. | `PhysicsParams.drivetrain_efficiency`, `--efficiency` |
| 6 | Wheel rotational inertia | Fold into an effective mass m_eff = m + I/r², with **I = 0.14 kg·m²** (both wheels) and **r = 0.311 m**, from Martin et al. (1998); adds 1.45 kg | `PhysicsParams.wheel_inertia`, `wheel_radius`, `effective_mass` |
| 7 | Air density | Constant per venue: **ρ = 1.15 kg/m³ for Tokyo** (Fuji Speedway, about 500–700 m up, hot), **ρ = 1.20 kg/m³ for Flanders** and the custom loop (sea level) | `analysis/run_analysis.py` (`AIR_DENSITY`), `--rho` |
| 8 | Wind | Along-road component only, positive = headwind. Crosswind is neglected and stated as an assumption. | `Course.headwind` |
| 9 | "Sharp turn" | Turn radius **below 40 m** (with μ = 0.5 that caps speed at about 50 km/h) | course design and description |
| 10 | "Nontrivial grade" | **At least 4% sustained over at least 500 m** | course design and description |
| 11 | Grip μ and braking deceleration | μ = 0.5 and a_brake = 3 m/s² are placeholders, to be sourced or varied in a sensitivity analysis | `PhysicsParams.mu_corner`, `brake_decel` |
| 12 | Races longer than the CP model's range | CP is validated for about 2–30 min; the men's races take 50–60 min. The stamina model therefore has two reserves. Fatigue F builds with intensity between LT1 and LT2, dF/dt = max(i, 0)^γ, and never recovers; critical power sinks from LT2 towards LT1 as CP = LT1 + (LT2 − LT1) exp(−(F/τ_F)²); W′ shrinks with total work, W′ = W′₀ exp(−E/E_W). γ = 1.7, τ_F = 3000 s, E_W = 57.4 kJ/kg from Clark et al. (2019) and Mateo-March et al. (2024). This replaces the earlier optional time-based decline CP(t) = CP(1 − k ln(t/t₀)), whose k was never fitted. | `power_model/`, [power_model/README.md](power_model/README.md) |
| 13 | Women's profiles | Same model; only LT1, LT2, W′, mass, C_dA and P_max change | `profiles/*.json` |
| 14 | Start | Standing start, v₀ = 0 | `SimConfig.initial_speed` |
| 15 | Profile values | Four profiles built from published data on professional riders (Valenzuela 2022, Mateo-March 2022, Ebert 2005, Garcia-Lopez 2014, Defraeye 2010, Padilla 1999). LT2 and W′ are fitted through the stamina model to the 5–20 min powers; LT1 is assumed to be 75% of LT2. | `profiles/`, `profiles/SOURCES.md` |
| 16 | Women's climber | **Follow the data**: women's time trialists have higher power per kilogram over 10–60 min (Mateo-March et al. 2022), so the climber uses the P50 row: CP = 255 W, W′ = 16.1 kJ. Report it as a finding. | `profiles/climber_women.json` |
| 17 | Time trialists' C_dA | **0.211 m²** for men (wind tunnel, time-trial position, Defraeye et al. 2010), scaled by frontal area to **0.188 m²** for women. Climbers keep the frontal-area scaling of the professional value 0.237 m² (Garcia-Lopez et al. 2014), i.e. a less optimised position. | `cda_m2` in the profiles |
| 18 | Courses | Each rider rides the route of their own race: Tokyo men 2 laps (43.9 km) and women 1 lap (22.0 km); Flanders men 43.8 km and women 30.3 km. Map-derived elevation, loaded with `sigma_ele = 1` m. | `courses/`, `courses/README.md` |
| 19 | Pacing-error model | Planned power × (1 + e), e an AR(1) process in distance (correlation length 200 m) plus an optional bias; σ = 2.5%, 5%, 10% and biases of −3%, +3%, +6%. An exhausted rider rides the most power that keeps B ≥ 0. The σ values are assumed. | `solver/execution.py` |

## The equation of motion

```
m_eff dv/dt = η P / v − ½ ρ C_dA (v + v_wind)|v + v_wind| − C_rr m g cos θ − m g sin θ − F_brake
m_eff = m + I / r²
```

P is the rider's pedal power (what the CP model describes); η P reaches the
wheel. Gravity and rolling resistance use the real mass m; only the term
that accelerates the bike uses m_eff. In the distance form the solver uses,
d(v³)/ds = (3 / m_eff)(η P − v F_res).

## Sources

- Martin, J. C., Milliken, D. L., Cobb, J. E., McFadden, K. L., & Coggan,
  A. R. (1998). Validation of a mathematical model for road cycling power.
  *Journal of Applied Biomechanics*, 14(3), 276–291.
  - η: "the efficiency of the chain drive system (E_c) was 97.698%" (p. 283),
    rounded to 0.977. The paper's Appendix I worked example rounds it to
    0.976.
  - I: "the moment of inertia of the two wheels (approximately 0.14 kg·m²)"
    (p. 280). This is for both wheels together.
  - r: 0.311 m appears in the Appendix I sample calculation, in the term
    0.14/0.311² (p. 291). The text calls r "the outside radius of the tire".
  - C_rr = 0.0032 for their tyres (p. 280, Appendix I).
- Defraeye, T., Blocken, B., Koninckx, E., Hespel, P., & Carmeliet, J.
  (2010). Aerodynamic study of different cyclist positions: CFD analysis and
  full-scale wind-tunnel tests. *Journal of Biomechanics*, 43(7), 1262–1268.
  doi:10.1016/j.jbiomech.2010.01.025. Wind-tunnel drag areas of 0.270, 0.243
  and 0.211 m² for the upright, dropped and time-trial positions. **To
  check:** the 0.211 m² value and the test rider against the full text.
- Skiba, P. F., Fulford, J., Clarke, D. C., Vanhatalo, A., & Jones, A. M.
  (2015). Intramuscular determinants of the ability to recover work capacity
  above critical power. *European Journal of Applied Physiology*.
- Rider profile sources: [profiles/SOURCES.md](profiles/SOURCES.md).
- Every source, with what was taken from it and where it is used:
  [SOURCES.md](SOURCES.md).
