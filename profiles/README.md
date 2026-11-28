# Rider profiles

A profile is one JSON file holding everything that belongs to a rider and
their bike. It is loaded into `rider.RiderProfile` at run time and fills in
the parameters of the physics and power models.

```python
from profiles import rider

profile = rider.load("tt_specialist")      # or a path to any profile JSON
physics = profile.physics_params()         # mass, CdA, Crr filled in
power = profile.rider_params()             # LT1, LT2, W', P_max, fatigue
```

`run_baseline.py --profile climber` does the same from the command line.

## Shipped profiles

Two rider types (time trial specialist, climber), each in a men's and a
women's version, built from published data on professional riders. Every
value, its source and the fits are in [SOURCES.md](SOURCES.md).

| | `tt_specialist` | `climber` | `tt_specialist_women` | `climber_women` |
| --- | --- | --- | --- | --- |
| Rider mass [kg] | 72.6 | 63.2 | 61.7 | 53.7 |
| Bike mass [kg] | 8.5 | 7.5 | 8.5 | 7.5 |
| $C_dA$ [m²] | 0.211 | 0.217 | 0.188 | 0.193 |
| $C_{rr}$ | 0.0032 | 0.0032 | 0.0032 | 0.0032 |
| LT1 [W] | 309 | 278 | 230 | 196 |
| LT2 = fresh $CP$ [W] | 412 | 370 | 307 | 261 |
| $W'$ [kJ] | 28.75 | 24.1 | 25.7 | 14.9 |
| $P_\text{max}$ [W] | 1306 | 1137 | 944 | 822 |
| Fresh $CP$ per kg of rider [W/kg] | 5.67 | 5.85 | 4.98 | 4.86 |
| Fresh $CP$ per kg of rider + bike [W/kg] | 5.08 | 5.23 | 4.37 | 4.26 |
| Fresh $CP / C_dA$ [W/m²] | 1953 | 1705 | 1633 | 1352 |

**Sources in brief.** Men's mass and power: Valenzuela et al. (2022), record
power profiles of 144 professionals by rider type. Women's power: Mateo-March
et al. (2022); women's mass scaled from Ebert et al. (2005). LT2 and W′ are
fitted so that the stamina model reproduces the 5, 10 and 20 min maximal
mean powers; LT1 is assumed to be 75% of LT2. The fatigue parameters are
population values (see [../power_model/README.md](../power_model/README.md)).
Time trialists' $C_dA$: 0.211 m² in a time-trial position, wind tunnel
(Defraeye et al. 2010), scaled by frontal area for the women. Climbers'
$C_dA$: the Garcia-Lopez et al. (2014) professional value (0.237 m²) scaled
by frontal area, i.e. a less optimised position than a specialist's.
$C_{rr}$: Martin et al. (1998). $P_\text{max}$: best 5 s power.

**The data, not a rule, set the direction.** Men's climbers have more power
per kilogram than men's time trialists (Valenzuela 2022). Women's time
trialists have *more* power per kilogram than women's climbers over 10–60 min
(Mateo-March 2022), so `climber_women` uses the median (P50) record power
profile and is slightly below the specialist in W/kg. In both genders the
time trialist has more power per unit of drag.

## File format

```json
{
  "name": "TT specialist",
  "description": "Big, powerful rider in a very aerodynamic time-trial position.",
  "rider_mass_kg": 74.0,
  "bike_mass_kg": 9.0,
  "cda_m2": 0.19,
  "crr": 0.003,
  "power": {
    "lt1_w": 309,
    "lt2_w": 412,
    "w_prime_j": 28750,
    "p_max_w": 1306,
    "recovery_alpha": 1.0,
    "recovery_beta": 1.0,
    "fatigue_exponent": 1.7,
    "fatigue_time_s": 3000,
    "w_prime_work_scale_j_per_kg": 57400,
    "best_efforts": [[300, 503], [600, 455], [1200, 426]]
  }
}
```

Only `lt1_w`, `lt2_w`, `w_prime_j` and `p_max_w` are required in `power`.
The recovery numbers default to 1 and the three fatigue numbers to the
values shown. `best_efforts` lists the (duration in seconds, power in watts)
pairs the numbers were fitted to; it is kept for reference and for the test
that checks the fit, and the model does not read it. `description` is
optional too. Unknown keys, missing keys, and non-positive numbers are
rejected with an error that names the key.

## What is not in a profile

Gravity, air density, cornering grip, and braking strength describe the
conditions, not the rider, so they stay in `PhysicsParams`. Pass a base to
`profile.physics_params(base)` to change them.

## Assumptions and gaps filled

- **Typical riders, not individuals.** Each profile is a percentile of a
  population of professionals, not any one rider, so it should be somewhat
  slower than race winners.
- **Women's per-type data are sparse.** Women's masses and the climber's
  position are scaled from the men's type differences (see SOURCES.md).
- **Bike masses are assumed.** No peer-reviewed source was found.
- **One $C_dA$ per rider.** The rider holds one position on every course,
  including climbs, where real riders sit up.
- **LT1 is assumed** to be 75% of LT2 for every profile.
- **The fatigue numbers are shared.** All riders use the same $\gamma$,
  $\tau_F$, $E_W$ per kilogram, and recovery law ($\alpha = \beta = 1$).
  Only the 5 to 20 min powers are fitted per profile.
- **Same tyres and same grip.** All profiles use $C_{rr} = 0.0032$ and corner
  equally well.
