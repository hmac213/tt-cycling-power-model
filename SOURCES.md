# Sources

A running list of every source the project uses, what was taken from it, and
where it is used. Add a row whenever a new source informs the code or the
documentation.

"Read as" says how far the source was checked: **full text**, **abstract**
(numbers taken from the abstract or a database record only), or **not
re-read** (a standard reference cited without going back to it).

## Stamina model (`power_model/`)

| Source | What we took | Where it is used | Read as |
| --- | --- | --- | --- |
| Clark IE, Vanhatalo A, Thompson C, Joseph C, Black MI, Blackwell JR, Wylie LJ, Tan R, Bailey SJ, Wilkins BW, Kirby BS, Jones AM (2019). Dynamics of the power-duration relationship during prolonged endurance exercise and influence of carbohydrate ingestion. *J Appl Physiol* 127:726–736. doi:10.1152/japplphysiol.00207.2019 | Critical power and W′ after 40, 80 and 120 min at 164 W (threshold 132 W, CP 260 W): CP 260 / 268 / 260 / 236 W, W′ 17.9 / 16.1 / 14.7 / 13.8 kJ. With 60 g/h carbohydrate: CP 254 W, W′ 13.5 kJ. No correlation between glycogen change and CP change. | Flat-start shape of the durability curve; $\gamma$ and $\tau_F$ (one of two data points); $E_W$; the rule that W′ follows work; the fed-rider assumption; "F is not a fuel tank". `power_model/README.md`, defaults in `power_model/params.py` and `profiles/rider.py` | Full text |
| Mateo-March M, Leo P, Muriel X, Javaloyes A, Mujika I, Barranco-Gil D, Pallarés JG, Lucia A, Valenzuela PL (2024). Is all work the same? Performance after accumulated work of differing intensities in male professional cyclists. *J Sci Med Sport*. doi:10.1016/j.jsams.2024.03.005 | Table 1, 17 WorldTour riders (66.0 kg): CP 408 W fresh; 399 / 383 / 342 W after 2.5 / 5.0 / 7.5 kJ/kg above CP; 406 / 404 / 403 W after the same work below CP. 5-min power 475 / 467 / 453 / 408 W. | Intensity-weighted fatigue; flat-start shape; $\gamma$ and $\tau_F$ (the other data point); evidence that W′ does not follow intensity. `power_model/README.md` | Full text |
| Clark IE et al. (2019), companion study in *Am J Physiol Regul Integr Comp Physiol* (cited as ref. 13 in the paper above) | After 2 h of heavy exercise, CP about 11% lower and W′ about 20% lower | Background for the size of the losses; not used for any number in the code | Abstract. **To check:** full citation |
| Barranco-Gil D et al. (2024). Intensity matters: effect of different work-matched efforts on subsequent performance in cyclists. *Int J Sports Physiol Perform* | Work-matched intervals at 110–120% of CP cut 2-min power and W′ more than steady riding at 60–70%; CP not different | Evidence that sprints have a lasting cost; discussion only | Abstract |
| Sánchez-Jiménez JL et al. (2025). Is intensity the most important factor in determining the amount of prior work accumulated that affects cyclists' acute durability? A systematic review. *Eur J Appl Physiol* | 21 studies: efforts above CP cause larger declines with less work; kilojoules alone are an inadequate fatigue measure. One included study found no effect of intensity domain. | Support for intensity-weighted fatigue, and the caveat that the evidence is not unanimous. `power_model/README.md` (limitations) | Abstract |
| Mateo-March M et al. (2022). The record power profile of male professional cyclists: fatigue matters. *Int J Sports Physiol Perform* 17(6):926–931. doi:10.1123/ijspp.2021-0403 | Power falls 1.6–3.0% after 15 kJ/kg of race work and 6.0–9.7% after 45 kJ/kg | Background only | Abstract |
| Skiba PF, Fulford J, Clarke DC, Vanhatalo A, Jones AM (2015). Intramuscular determinants of the ability to recover work capacity above critical power. *Eur J Appl Physiol* | The W′ balance differential model: below CP, the reserve recovers at a rate proportional to (CP − P) and to the share already used | Recovery law of the fast reserve ($\alpha = \beta = 1$). `power_model/cp_model.py`, `DECISIONS.md` no. 3 | Not re-read |

## Physics (`physics_model/`)

| Source | What we took | Where it is used | Read as |
| --- | --- | --- | --- |
| Martin JC, Milliken DL, Cobb JE, McFadden KL, Coggan AR (1998). Validation of a mathematical model for road cycling power. *J Appl Biomech* 14(3):276–291 | Drivetrain efficiency 0.977, wheel inertia 0.14 kg·m², tyre radius 0.311 m, $C_{rr}$ = 0.0032 | `physics_model/params.py`, profiles. Page references in `DECISIONS.md` | See `DECISIONS.md` |
| Defraeye T, Blocken B, Koninckx E, Hespel P, Carmeliet J (2010). Aerodynamic study of different cyclist positions. *J Biomech* 43(7):1262–1268. doi:10.1016/j.jbiomech.2010.01.025 | Wind-tunnel drag area 0.211 m² in a time-trial position | `cda_m2` of the time trial specialists | See `DECISIONS.md` (value still to be checked against the full text) |

## Rider profiles (`profiles/`)

The sources for masses, drag areas and the 5, 10 and 20 minute powers of the
four profiles (Valenzuela 2022, Mateo-March 2022 on women, Ebert 2005,
Garcia-Lopez 2014, Padilla 1999, Impellizzeri 2008, Horvath & Andersson
2025) are listed with full references and the status of every number in
[profiles/SOURCES.md](profiles/SOURCES.md).

## Courses (`courses/`)

The origin of the Tokyo and Flanders GPX files and the checks against
official distances and climbing are in [courses/README.md](courses/README.md).

## Software (`solver/`)

| Source | What we took | Where it is used | Read as |
| --- | --- | --- | --- |
| Andersson JAE, Gillis J, Horn G, Rawlings JB, Diehl M (2019). CasADi: a software framework for nonlinear optimization and optimal control. *Math Program Comput* 11:1–36 | Symbolic expressions with exact derivatives | `solver/collocation.py` | Not re-read |
| Wächter A, Biegler LT (2006). On the implementation of an interior-point filter line-search algorithm for large-scale nonlinear programming. *Math Program* 106:25–57 | IPOPT, the nonlinear programming solver | `solver/collocation.py` | Not re-read |
| SciPy | Root finding, least squares, smoothing splines, N-dimensional interpolation | `solver/`, `power_model/calibrate.py`, `course_loader/gpx.py` | – |

## Problem statement

2022 MCM Problem A (power profile of a cyclist), which sets the requirements
listed in `README.md`.
