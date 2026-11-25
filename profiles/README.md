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

| | `tt_specialist` | `climber` |
| --- | --- | --- |
| Rider mass [kg] | 74 | 58 |
| Bike mass [kg] | 9.0 | 7.0 |
| $C_dA$ [m²] | 0.19 | 0.24 |
| $C_{rr}$ | 0.003 | 0.003 |
| $CP$ [W] | 410 | 350 |
| $W'$ [kJ] | 22 | 15 |
| $P_\text{max}$ [W] | 1300 | 900 |
| $CP$ per kg of rider [W/kg] | 5.54 | 6.03 |
| $CP$ per kg of rider + bike [W/kg] | 4.94 | 5.38 |
| $CP / C_dA$ [W/m²] | 2158 | 1458 |

The TT specialist has far more power per unit of drag, which decides flat and
rolling courses. The climber has more power per kilogram, which decides steep
climbs: on `courses/climb.gpx` (6 km at 8%) the climber wins by 30 s, and on
`courses/flat.gpx` (10 km) the TT specialist wins by 91 s.

## Women's profiles

`tt_specialist_women` (63 + 8 kg, $C_dA$ 0.18 m², CP 300 W, W′ 16 kJ,
$P_\text{max}$ 950 W) and `climber_women` (52 + 7 kg, $C_dA$ 0.22 m², CP
270 W, W′ 12 kJ, $P_\text{max}$ 750 W). Like the men's profiles, these
are illustrative values in the professional range. On the real Flanders
course, the women's TT specialist is about 5% slower than the 2021 world
champion.

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

- **The numbers are illustrative.** They are round figures in the range of
  professional riders, not measurements of anyone.
- **One $C_dA$ per rider.** The rider holds one position on every course,
  including climbs, where real riders sit up.
- **The power profile is CP, $W'$, and $P_\text{max}$.** No full power-duration
  curve is stored. Both riders use the same recovery law ($\alpha = \beta = 1$).
- **Same tyres and same grip.** Both profiles use $C_{rr} = 0.003$ and corner
  equally well.
