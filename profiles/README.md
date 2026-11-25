# Rider profiles

A profile is one JSON file holding everything that belongs to a rider and
their bike. It is loaded into `rider.RiderProfile` at run time and fills in
the parameters of the physics and power models.

```python
from profiles import rider

profile = rider.load("tt_specialist")      # or a path to any profile JSON
physics = profile.physics_params()         # mass, CdA, Crr filled in
power = profile.rider_params()             # CP, W', P_max, alpha, beta
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
| $CP$ [W] | 400 | 359 | 298 | 255 |
| $W'$ [kJ] | 31.8 | 27.5 | 27.8 | 16.1 |
| $P_\text{max}$ [W] | 1306 | 1137 | 944 | 822 |
| $CP$ per kg of rider [W/kg] | 5.51 | 5.68 | 4.83 | 4.75 |
| $CP$ per kg of rider + bike [W/kg] | 4.93 | 5.08 | 4.25 | 4.17 |
| $CP / C_dA$ [W/m²] | 1896 | 1654 | 1585 | 1321 |

**Sources in brief.** Men's mass and power: Valenzuela et al. (2022), record
power profiles of 144 professionals by rider type. Women's power: Mateo-March
et al. (2022); women's mass scaled from Ebert et al. (2005). CP and W′ are
linear fits W = CP·t + W′ to the 5, 10 and 20 min maximal mean powers.
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
    "cp_w": 410.0,
    "w_prime_j": 22000.0,
    "p_max_w": 1300.0,
    "recovery_alpha": 1.0,
    "recovery_beta": 1.0
  }
}
```

`description`, `recovery_alpha`, and `recovery_beta` are optional (the last two
default to 1). Unknown keys, missing keys, and non-positive numbers are
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
- **The power profile is CP, $W'$, and $P_\text{max}$.** No full power-duration
  curve is stored. All riders use the same recovery law ($\alpha = \beta = 1$).
- **Same tyres and same grip.** All profiles use $C_{rr} = 0.0032$ and corner
  equally well.
