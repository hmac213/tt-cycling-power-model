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
| `courses/` | The Tokyo and Flanders 2021 courses, our custom loop, synthetic demo courses, and the scripts that generate them | [courses/README.md](courses/README.md) |
| `analysis/` | Experiments for the full problem statement (race courses, wind, power errors, fatigue) and their figures | |
| `docs/` | Team time trial extension | [docs/team_time_trial.md](docs/team_time_trial.md) |
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

## The full problem statement (2022 MCM Problem A)

The sections above cover the core model. This section covers every item
the problem statement asks for. Reproduce it with

```bash
python analysis/run_analysis.py all      # about 40 min on 2 cores
python analysis/plot_analysis.py         # figures in outputs/analysis/figures
```

A frozen copy of the summaries and figures is in `results/`.

| Requirement | Where |
| --- | --- |
| Two rider types, one a TT specialist, and both genders | `profiles/`: `tt_specialist`, `climber`, `tt_specialist_women`, `climber_women` |
| 2021 Olympic TT course, Tokyo | `courses/tokyo_2021_men.gpx` (44 km), `tokyo_2021_women.gpx` (22 km) |
| 2021 Worlds TT course, Flanders | `courses/flanders_2021_men.gpx` (43.3 km), `flanders_2021_women.gpx` (30.3 km) |
| Own course: 4+ sharp turns, a real grade, finish near start | `courses/custom_loop.gpx` |
| Limits on total energy, past aggressiveness, fatigue | W′ (past aggressiveness) plus CP decline over long races (`fatigue_rate`) |
| Weather sensitivity | `analysis/run_analysis.py wind` |
| Sensitivity to missing power targets, split-time ranges | `solver/execution.py`, `analysis/run_analysis.py deviation` |
| Team time trial extension | [docs/team_time_trial.md](docs/team_time_trial.md) |

These results come from the dynamic program alone (no collocation
polish), which changes times by about 0.1 s.

### Courses

**Tokyo and Flanders are the real routes**, user-made GPX files from
RideWithGPS that match the official distances and start and finish points
(sources and checks in [courses/README.md](courses/README.md)). Their
elevation comes from a map elevation model, so they are loaded with
`sigma_ele = 1.0` m. With that setting the model's climbing matches
ProCyclingStats almost exactly: 747 m vs. 746 m for the men's Tokyo course
and 379 m vs. 380 m for the women's.

The custom loop is 12 km with seven corners of 80° or more (radius
12–20 m), a 1.5 km climb that reaches 7%, and the finish line on the start
line.

### Rider profiles

| | TT specialist | Climber | TT specialist (W) | Climber (W) |
| --- | --- | --- | --- | --- |
| Rider / bike mass [kg] | 74 / 9 | 58 / 7 | 63 / 8 | 52 / 7 |
| $C_dA$ [m²] | 0.19 | 0.24 | 0.18 | 0.22 |
| $CP$ [W] | 410 | 350 | 300 | 270 |
| $W'$ [kJ] | 22 | 15 | 16 | 12 |
| $P_\text{max}$ [W] | 1300 | 900 | 950 | 750 |

The numbers are illustrative values in the professional range, not
measurements. `analysis/plot_analysis.py` draws each rider's power curve,
$P(t) = \min(CP + W'/t,\ P_\text{max})$.

### Results on the race courses

Constant power, optimal, time saved, kinetic energy braked away; then the
optimal time and saving with long-race fatigue on ($k = 0.07$, onset
30 min):

| Course | Rider | Constant | Optimal | Saved | Braked: constant → optimal | With fatigue: optimal (saved) |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo (43.9 km) | TT specialist | 60:15.3 | 57:07.5 | 187.8 s | 270 → 116 kJ | 57:27.5 (191.1 s) |
| Tokyo (43.9 km) | Climber | 63:58.6 | 61:35.8 | 142.8 s | 126 → 39 kJ | 62:00.0 (154.8 s) |
| Tokyo (22.0 km) | TT specialist (W) | 32:53.3 | 31:27.7 | 85.6 s | 93 → 40 kJ | 31:27.7 (85.8 s) |
| Tokyo (22.0 km) | Climber (W) | 34:16.5 | 33:08.7 | 67.8 s | 46 → 13 kJ | 33:08.9 (68.1 s) |
| Flanders (43.7 km) | TT specialist | 51:47.1 | 50:27.8 | 79.3 s | 125 → 36 kJ | 50:35.8 (80.2 s) |
| Flanders (43.7 km) | Climber | 57:29.0 | 56:32.6 | 56.5 s | 69 → 15 kJ | 56:45.9 (56.9 s) |
| Flanders (30.3 km) | TT specialist (W) | 38:50.0 | 37:58.3 | 51.7 s | 60 → 15 kJ | 37:59.6 (51.9 s) |
| Flanders (30.3 km) | Climber (W) | 42:07.6 | 41:29.3 | 38.3 s | 37 → 6 kJ | 41:32.1 (38.5 s) |
| Custom loop (12.0 km) | TT specialist | 15:21.8 | 14:49.8 | 32.1 s | 55 → 30 kJ | – |
| Custom loop (12.0 km) | Climber | 16:36.4 | 16:13.1 | 23.3 s | 27 → 11 kJ | – |
| Custom loop (12.0 km) | TT specialist (W) | 16:47.5 | 16:15.1 | 32.4 s | 37 → 19 kJ | – |
| Custom loop (12.0 km) | Climber (W) | 17:46.8 | 17:21.8 | 25.0 s | 20 → 9 kJ | – |

**Check against the real races.** The model's TT specialists are
3.7–5.6% slower than the 2021 winners: Tokyo men
57:07 vs. Roglič's 55:04.19,
Tokyo women 31:27 vs.
van Vleuten's 30:13.49, Flanders men
50:27 vs. Ganna's 47:47.83,
Flanders women 37:58
vs. van Dijk's 36:05.28. That is about right for profiles a little below
world-champion level, and the model is not tuned to these races.

**Where the gain comes from.** Pacing saves 3.3–5.2% on
Tokyo (up to 3 minutes) and
1.5–2.6% on Flanders. Both real courses have far more tight
corners than the synthetic ones: the motor circuit at Fuji and the town
centres of Knokke and Bruges. A rider holding constant power pedals hard
into every one of them and then brakes the energy away. The optimal rider
eases off before each corner, sprints out of it, pushes on the climbs, and
coasts the long descents. On the men's Tokyo course the TT specialist brakes
away 116 kJ instead of
270 kJ. Corner radii come
from the GPX line, so a route drawn slightly off the real racing line would
make some corners tighter than they are. Treat the corner share of the gain
as an upper estimate.

### Fatigue: total energy and CP decline

The plain CP model lets a rider hold CP forever. The problem says riders
tire as the race goes on, so CP now declines after an onset time $t_0$:

$$CP(t) = CP \left(1 - k \ln\frac{t}{t_0}\right), \qquad t > t_0.$$

This also caps the total energy over the race, at
$\int_0^T CP(t)\,dt + W'$. CP depends on elapsed time, and elapsed time
depends on the plan, so the solver alternates the two until they agree
(fixed-point iteration, 2–4 rounds). $k$ is a placeholder, so here is its
effect on the men's Tokyo course (TT specialist):

| $k$ | Constant | Optimal | Saved |
| --- | --- | --- | --- |
| 0 (off) | 60:15.3 | 57:07.5 | 187.8 s |
| 0.035 | 60:26.8 | 57:17.5 | 189.3 s |
| 0.07 | 60:38.6 | 57:27.5 | 191.1 s |
| 0.14 | 61:35.2 | 57:47.6 | 227.6 s |

Fatigue barely matters below about 35 minutes (the women's courses). On the
50–65-minute men's courses it costs 8–24 s at
$k = 0.07$ and makes careful pacing slightly more valuable. It is off by
default (`fatigue_rate = 0`), so the core results above are unchanged.

### Weather

The wind blows uniformly from 8 directions at 2, 4, and 6 m/s, and the plan is
re-optimized each time. The table shows the change in optimal time from a calm
day, in seconds, by the direction the wind blows from:

**Flanders, men's TT specialist (point to point; calm 50:27.8)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | -72 | -67 | -19 | +50 | +96 | +87 | +30 | -35 |
| 4 m/s | -121 | -115 | -27 | +115 | +218 | +195 | +71 | -55 |
| 6 m/s | -149 | -145 | -24 | +198 | +368 | +326 | +123 | -61 |

**Tokyo, women's TT specialist (loop; calm 31:27.7)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | +7 | -10 | -19 | -15 | +2 | +24 | +34 | +25 |
| 4 m/s | +23 | -4 | -22 | -20 | +13 | +61 | +82 | +61 |
| 6 m/s | +49 | +18 | -7 | -14 | +33 | +110 | +146 | +105 |

* On the point-to-point Flanders course, which runs from the coast inland
  to the south-west, wind dominates everything else. A 6 m/s wind from the
  south costs about 6 minutes, and one from the north saves about 2.5.
  Riders starting at different times can face very different races.
* On the Tokyo loop, headwind and tailwind sections largely cancel, but not
  fully, and the climb faces one way. Wind from the east or south-east
  helps slightly, up to 22 s,
  while a 6 m/s westerly costs about 2.5 minutes.
* Pacing saves 68–92 s on Flanders and 79–93 s on
  Tokyo across all these winds. The optimal rider pushes into the headwind
  and saves energy in the tailwind.

**Wrong forecast.** A plan made for a 4 m/s wind from the south-west, ridden
in winds 1 m/s stronger or weaker and 45° off, costs at most 17 s
against a plan made for the actual wind. The plan is robust to small
forecast errors. What matters is knowing roughly where the wind comes from.

### Missing the power targets

`solver/execution.py` rides the optimal plan with errors that drift along
the course (correlation length 200 m). Whenever the reserve runs out, the
rider is forced down to the most they can still sustain. 500 rides of the
men's Tokyo plan (TT specialist, perfect time 57:07.5):

| Execution | Mean time lost | 5–95% range | Steps forced to back off |
| --- | --- | --- | --- |
| random 2.5% | +9.7 s | +7.1 to +13.7 s | 5% |
| random 5% | +20.4 s | +14.8 to +28.7 s | 5% |
| random 10% | +43.8 s | +30.5 to +63.0 s | 5% |
| 3% too easy | +51.9 s | +36.7 to +69.1 s | 0% |
| 3% too hard | +15.9 s | +13.3 to +19.0 s | 14% |
| 6% too hard | +21.0 s | +18.0 to +23.8 s | 22% |

Expected split times with a 5% random error:

| Checkpoint | Plan | 5–95% range |
| --- | --- | --- |
| top of climb 1 (km 10.5) | 14:59.9 | 15:04.2 – 15:11.6 |
| bottom of descent 1 (km 15.5) | 19:49.7 | 19:54.2 – 20:02.0 |
| end of lap 1 (km 22.0) | 28:29.7 | 28:36.4 – 28:47.0 |
| top of climb 2 (km 32.5) | 43:39.9 | 43:51.7 – 44:04.3 |
| bottom of descent 2 (km 37.5) | 48:29.8 | 48:41.9 – 48:54.5 |
| finish (km 43.9) | 57:07.5 | 57:22.3 – 57:36.2 |

* Random errors cost little: about 20 s for a typical 5%
  error, 44 s for a sloppy 10%.
* **Riding too easy is far worse than riding too hard.** A rider 3% under
  target finishes with unused reserve and loses about 52 s.
  A rider 3% over target loses only about 16 s, because
  the reserve runs out early and they are forced to ease off for a few short
  stretches.
* **Timing matters more than averages.** A simplified plan with one average
  power per kilometre loses 157 s against the
  detailed plan and beats constant power by only 31 s.
  It averages away exactly the moves that matter: easing off before corners
  and sprinting out of them. Race guidance should describe where to change
  effort, not just how hard to ride each kilometre.

### Team time trial

See [docs/team_time_trial.md](docs/team_time_trial.md): position-dependent
drag, one speed shared by six reserves, rotation and release decisions, and
the fourth-rider finish. In the equal-share approximation, six TT specialists
ride at about 62.5 km/h against 53.1 km/h alone.

## Known limits

- $C_dA$, $\rho$, and $C_{rr}$ do not vary with position, altitude, or speed.
- No drivetrain loss or wheel rotational inertia.
- The CP model lets the rider hold exactly CP forever, so it is only reasonable
  for efforts from a few minutes up to roughly an hour.
- The optimizer is global only up to the resolution of the dynamic program's
  grids.
- The demo courses are synthetic. The Tokyo and Flanders files are
  user-made RideWithGPS routes, not official organiser files.
- The fatigue rate $k$ is a placeholder that has not been fitted to data.
