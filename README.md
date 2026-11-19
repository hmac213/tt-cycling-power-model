# Time-Trial Cycling Power Model

Model for optimal pacing in an individual time trial.

## Problem restatement

Given a course of length $L$ described by its incline angle $\theta(s)$,
curvature $\kappa(s)$, and headwind $v_\text{wind}(s)$, find the power profile
$P \ge 0$ that minimizes the race time

$$T = \int_0^L \frac{ds}{v_b(s)}$$

subject to the equation of motion of the bike, the grip limit in corners, and
the rider's stamina (Critical Power / $W'$) dynamics.

## Layout

| Folder | What it does | Model notes |
| --- | --- | --- |
| `course_loader/` | Smooth course geometry from a GPX track: $\theta(s)$, $\kappa(s)$, heading, $v_\text{wind}(s)$ | [course_loader/README.md](course_loader/README.md) |
| `physics_model/` | Power-to-speed equation of motion and cornering limits | [physics_model/README.md](physics_model/README.md) |
| `power_model/` | CP / $W'$ stamina model | [power_model/README.md](power_model/README.md) |
| `profiles/` | Rider profiles (JSON): masses, $C_dA$, and power numbers | [profiles/README.md](profiles/README.md) |
| `solver/` | Forward simulation and two-stage pacing optimization | [solver/README.md](solver/README.md) |
| `courses/` | Demo GPX files and the script that generates them | |
| `tests/` | Sanity checks | |

Each model folder has a README listing its equations, parameters, assumptions,
and ambiguities.

## Quick start

```bash
pip install -r requirements.txt
python run_baseline.py                         # rolling.gpx, TT specialist
python run_baseline.py courses/climb.gpx --profile climber
python run_baseline.py ride.gpx --wind-speed 4 --wind-from 270 --step 10
python -m unittest discover tests
```

`run_baseline.py` prints the optimal race time next to the best constant-power
ride and writes three files to `outputs/`: a plot, the step-by-step
pacing plan, and the course profile (slope, heading, curvature, headwind, and
speed limit at every metre).

```python
from course_loader import gpx
from profiles import rider
from solver import optimize

course = gpx.load_gpx("courses/rolling.gpx", wind_speed=3, wind_from_deg=300)
profile = rider.load("tt_specialist")
result = optimize.optimize_pacing(
    course, profile.physics_params(), profile.rider_params()
)
print(result.ride.total_time, result.ride.power)
```

## How it is solved

The course is cut into 20 m steps with one power per step. A dynamic program
over (distance, speed, reserve) first finds the globally best plan its grids
can express, and a collocation solve (CasADi + IPOPT) then polishes it. See
[solver/README.md](solver/README.md).

## Full system

State $(v_b, B)$, control $P$, written against time:

$$m \frac{dv_b}{dt} = \frac{P}{v_b} - \tfrac12 \rho\, C_dA\, (v_b + v_\text{wind})\lvert v_b + v_\text{wind}\rvert - C_{rr}\, m g \cos\theta(s) - m g \sin\theta(s) - F_\text{brake}$$

$$\frac{dB}{dt} = \begin{cases} -(P - CP) & P \ge CP \\ \alpha\,(CP - P)\left(1 - B/W'\right)^{\beta} & P < CP \end{cases}$$

$$v_b^2\, \lvert\kappa(s)\rvert \le \mu\, g \cos\theta(s), \qquad 0 \le F_\text{brake} \le m\, a_\text{brake}$$

$$\frac{ds}{dt} = v_b, \qquad 0 \le B \le W', \qquad 0 \le P \le P_\text{max}, \qquad B(0) = W', \qquad v_b(0) = v_0$$

## Variables and parameters

| Symbol | Code name | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $t$ | `time` | Time elapsed | s | output |
| $s$ | `distance` | Distance ridden, $s \in [0, L]$ | m | independent variable |
| $v_b$ | `speed` | Bike speed | m/s | state |
| $P$ | `power` | Mechanical power output | W | control |
| $B$ | `reserve` | Remaining anaerobic reserve | J | state |
| $m$ | `PhysicsParams.mass` | Rider + bike mass | kg | 80 |
| $g$ | `PhysicsParams.g` | Gravitational acceleration | m/s² | 9.81 |
| $\rho$ | `PhysicsParams.rho` | Air density | kg/m³ | 1.225 |
| $C_dA$ | `PhysicsParams.cda` | Drag area | m² | 0.30 |
| $C_{rr}$ | `PhysicsParams.crr` | Rolling resistance coefficient | – | 0.004 |
| $\mu$ | `PhysicsParams.mu_corner` | Usable lateral grip | – | 0.5 |
| $a_\text{brake}$ | `PhysicsParams.brake_decel` | Largest braking deceleration | m/s² | 3.0 |
| $\theta(s)$ | `Course.theta` | Road incline angle | rad | course |
| $\kappa(s)$ | `Course.curvature` | Horizontal path curvature | 1/m | course |
| $\psi(s)$ | `Course.heading` | Compass bearing of travel | rad | course |
| $v_\text{wind}(s)$ | `Course.headwind` | Headwind (negative = tailwind) | m/s | course + wind |
| $CP$ | `RiderParams.cp` | Critical power | W | 300 |
| $W'$ | `RiderParams.w_prime` | Anaerobic work capacity above CP | J | 20 000 |
| $P_\text{max}$ | `RiderParams.p_max` | Cap on instantaneous power | W | 900 |
| $\alpha$ | `RiderParams.alpha` | Recovery rate coefficient | – | 1 |
| $\beta$ | `RiderParams.beta` | Recovery saturation exponent | – | 1 |
| $v_0$ | `SimConfig.initial_speed` | Speed at the start line | m/s | 0 |
| $h$ | `SimConfig.step_length` | Length of one grid step | m | 20 |

The defaults are a generic rider. The rider profiles in `profiles/` override
mass, $C_dA$, $C_{rr}$, $CP$, $W'$, and $P_\text{max}$.

## Ambiguities and how the baseline resolves them

- **Rider stamina limits.** A rider cannot hold sprint power forever. Resolved
  with the standard Critical Power / $W'$ model.
- **Course geometry and turns.** Corners cap speed no matter the power
  available. Resolved with a grip limit on lateral acceleration and a
  latest-braking speed envelope, both computed from the curvature of the GPX
  track.
- **Depletion vs. recovery.** Riding above CP drains the finite reserve $W'$;
  riding below CP refills it.

## Assumptions

1. **Constant combined mass**, $m = m_\text{rider} + m_\text{bike}$. Mass lost to
   sweat and fuel over a time trial is under 1%.
2. **Uniform surface, no obstacles.** Time trials run on well-maintained roads,
   so speed follows from the physical forces and the corners alone.
3. **No mechanical failures or equipment wear.** Rolling resistance and drag
   coefficients stay constant for the whole race.
4. **Braking only when a corner demands it.** A rider avoids braking since it
   throws away kinetic energy, so the brakes are used only to get down to the
   cornering speed limit, and then as late and as hard as possible.
5. **Constant $C_dA$.** The rider holds the same position for the whole course.
6. **No crosswinds.** Only the wind component along the road matters.

## Results (20 m steps)

Constant power, then optimal, then the time saved:

| Course | TT specialist | Climber |
| --- | --- | --- |
| `flat.gpx` (10 km) | 11:10.6 → 11:07.7 (2.9 s) | 12:40.9 → 12:39.1 (1.8 s) |
| `hill.gpx` (10 km, 100 m hill) | 11:47.2 → 11:35.5 (11.7 s) | 13:09.1 → 13:00.8 (8.3 s) |
| `climb.gpx` (6 km at 8%) | 16:09.0 → 16:08.0 (1.0 s) | 15:39.0 → 15:38.3 (0.8 s) |
| `rolling.gpx` (20 km, 191 m climbing, wind 3 m/s from 300°) | 22:29.9 → 22:07.1 (22.8 s) | 24:57.3 → 24:42.5 (14.8 s) |
| `technical.gpx` (8 km, 6 tight corners) | 9:56.8 → 9:27.3 (29.5 s) | 10:49.5 → 10:29.4 (20.2 s) |

The optimal plan pushes above CP on climbs and into headwinds, eases off on
descents to refill $B$, and holds speed much more even than constant power
does. On the technical course it also stops pedalling ahead of the corners:
the TT specialist brakes away 15.2 kJ in total, against 34.4 kJ at constant
power. On a steady climb there is almost nothing to gain, since constant
power is already close to optimal there. The TT specialist wins everywhere
except the steep climb.

## Sensitivity to the recovery exponent β

β is a placeholder, so we varied it on `hill.gpx` (TT specialist, dynamic
program only, no polish):

| β | Constant power | Optimal | Time saved |
| --- | --- | --- | --- |
| 0.5 | 11:47.2 | 11:35.2 | 12.1 s |
| 1 | 11:47.2 | 11:35.6 | 11.7 s |
| 2 | 11:47.2 | 11:35.9 | 11.3 s |

The time saved changes by only ±0.4 s over a 4× range of β, so the main
result does not depend on this uncertain parameter. Larger β slows recovery,
since (1 − B/W′)^β shrinks as β grows when B < W′, which slightly reduces the
benefit of recovering on the descent. The constant-power ride never drops
below CP, so it never recovers and β does not affect it.

## Known limits

- $C_dA$, $\rho$, and $C_{rr}$ do not vary with position, altitude, or speed.
- No drivetrain loss or wheel rotational inertia.
- The CP model lets the rider hold exactly CP forever, so it is only reasonable
  for efforts from a few minutes up to roughly an hour.
- The optimizer is global only up to the resolution of the dynamic program's
  grids.
- The demo courses are synthetic.
