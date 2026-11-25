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
| `courses/` | Demo GPX files, the reconstructed Tokyo and Flanders courses, our custom loop, and the scripts that generate them | |
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
python -m courses.make_race_gpx          # writes the race courses
python analysis/run_analysis.py all      # about 40 min on 2 cores
python analysis/plot_analysis.py         # figures in outputs/analysis/figures
```

A frozen copy of the summaries and figures is in `results/`.

| Requirement | Where |
| --- | --- |
| Two rider types, one a TT specialist, and both genders | `profiles/`: `tt_specialist`, `climber`, `tt_specialist_women`, `climber_women` |
| 2021 Olympic TT course, Tokyo | `courses/tokyo_2021_men.gpx` (44.2 km), `tokyo_2021_women.gpx` (22.1 km) |
| 2021 Worlds TT course, Flanders | `courses/flanders_2021_men.gpx` (43.3 km), `flanders_2021_women.gpx` (30.3 km) |
| Own course: 4+ sharp turns, a real grade, finish near start | `courses/custom_loop.gpx` |
| Limits on total energy, past aggressiveness, fatigue | W′ (past aggressiveness) plus CP decline over long races (`fatigue_rate`) |
| Weather sensitivity | `analysis/run_analysis.py wind` |
| Sensitivity to missing power targets, split-time ranges | `solver/execution.py`, `analysis/run_analysis.py deviation` |
| Team time trial extension | [docs/team_time_trial.md](docs/team_time_trial.md) |

These results come from the dynamic program alone (no collocation
polish), which changes times by about 0.1 s.

### Courses

**Tokyo and Flanders are reconstructions, not surveyed tracks.** No GPX file
of either course was available, so `courses/make_race_gpx.py` builds each
from published facts: the lengths, the total climbing (Tokyo: 834 m modelled
against 846 m published for the men), the order and size of the climbs, the
start and finish, and realistic corner radii. The road layout itself is
schematic. To use the real roads, put the official GPX file in `courses/`
and load it; nothing else changes.

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

Constant power, optimal, time saved; then the optimal time and saving with
long-race fatigue on ($k = 0.07$, onset 30 min):

| Course | Rider | Constant | Optimal | Saved | With fatigue: optimal (saved) |
| --- | --- | --- | --- | --- | --- |
| Tokyo (44.2 km) | TT specialist | 59:43.0 | 57:37.4 | 125.6 s | 57:57.7 (129.7 s) |
| Tokyo (44.2 km) | Climber | 63:43.5 | 62:19.3 | 84.2 s | 62:45.1 (96.4 s) |
| Tokyo (22.1 km) | TT specialist (W) | 32:52.1 | 31:51.9 | 60.2 s | 31:51.9 (60.5 s) |
| Tokyo (22.1 km) | Climber (W) | 34:24.9 | 33:40.1 | 44.8 s | 33:40.4 (45.1 s) |
| Flanders (43.3 km) | TT specialist | 49:42.6 | 49:10.3 | 32.3 s | 49:17.5 (32.8 s) |
| Flanders (43.3 km) | Climber | 55:50.7 | 55:31.5 | 19.1 s | 55:44.3 (19.2 s) |
| Flanders (30.3 km) | TT specialist (W) | 37:54.7 | 37:31.3 | 23.4 s | 37:32.5 (23.6 s) |
| Flanders (30.3 km) | Climber (W) | 41:29.0 | 41:14.2 | 14.8 s | 41:17.0 (14.9 s) |
| Custom loop (12.0 km) | TT specialist | 15:21.8 | 14:49.8 | 32.1 s | – |
| Custom loop (12.0 km) | Climber | 16:36.4 | 16:13.1 | 23.3 s | – |
| Custom loop (12.0 km) | TT specialist (W) | 16:47.5 | 16:15.1 | 32.4 s | – |
| Custom loop (12.0 km) | Climber (W) | 17:46.8 | 17:21.8 | 25.0 s | – |

**Check against the real races.** The model's TT specialists are 3–5.5% slower
than the 2021 winners: Tokyo men 57:37 vs. Roglič's 55:04.19, Tokyo women
31:52 vs. van Vleuten's 30:13.49, Flanders men 49:10 vs. Ganna's 47:47.83,
Flanders women 37:31 vs. van Dijk's 36:05.28. That is about right for
profiles a little below world-champion level, so the physics gives
realistic speeds on both the flat and the hilly course.

**Why Tokyo gains so much.** On the hilly Tokyo course, pacing saves 2.2–3.5%
(up to 2 minutes), against 0.6–1.1% on flat Flanders. The optimal rider
pushes hard on the two big climbs, coasts the long descents, where extra
power buys almost no speed, and arrives at the corners at the bottom
without braking away energy (68 kJ braked vs. 149 kJ at constant power).
Part of that braking comes from the schematic corner placement, so treat
the size of the Tokyo gain as an upper estimate.

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
| 0 (off) | 59:43.0 | 57:37.4 | 125.6 s |
| 0.035 | 59:55.0 | 57:47.5 | 127.5 s |
| 0.07 | 60:07.4 | 57:57.7 | 129.7 s |
| 0.14 | 61:06.0 | 58:19.1 | 166.9 s |

Fatigue barely matters below about 35 minutes (the women's courses). On the
50–60-minute men's courses it costs 7–26 s (42 s at $k = 0.14$) and
makes careful pacing slightly more valuable. It is off by default (`fatigue_rate = 0`), so the core
results above are unchanged.

### Weather

The wind blows uniformly from 8 directions at 2, 4, and 6 m/s, and the plan is
re-optimized each time. The table shows the change in optimal time from a calm
day, in seconds, by the direction the wind blows from:

**Flanders, men's TT specialist (point to point; calm 49:10.3)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | -107 | -99 | -25 | +67 | +124 | +114 | +44 | -47 |
| 4 m/s | -200 | -184 | -32 | +156 | +265 | +244 | +109 | -74 |
| 6 m/s | -280 | -259 | -22 | +267 | +425 | +392 | +195 | -80 |

**Tokyo, women's TT specialist (loop; calm 31:51.9)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | -10 | -1 | +12 | +24 | +24 | +13 | -1 | -10 |
| 4 m/s | -4 | +10 | +35 | +60 | +60 | +36 | +8 | -6 |
| 6 m/s | +14 | +32 | +70 | +109 | +109 | +69 | +26 | +12 |

* On a point-to-point course, wind dominates everything else. A 6 m/s
  headwind costs 7 minutes and a tailwind saves almost 5. Each extra
  1 m/s of wind moves the time by roughly 40–80 s, depending on direction. Riders starting
  at different times can face very different races.
* On a loop, headwind and tailwind sections largely cancel, but not
  fully: headwinds cost more than tailwinds give back. A light wind from the
  north saves up to 10 s, but a 6 m/s wind slows the rider whichever way it
  blows.
* The time saved by pacing grows with wind (Flanders: 23–43 s instead of
  32 s), because the optimal rider pushes into the headwind and saves energy
  in the tailwind.

**Wrong forecast.** A plan made for a 4 m/s wind from the south-west, ridden
in winds 1 m/s stronger or weaker and 45° off, costs at most
12 s against a plan made for the actual wind. The plan is robust to
small forecast errors. What matters is knowing roughly where the wind comes
from.

### Missing the power targets

`solver/execution.py` rides the optimal plan with errors that drift along
the course (correlation length 200 m). Whenever the reserve runs out, the
rider is forced down to the most they can still sustain. 500 rides of the
men's Tokyo plan (TT specialist, perfect time 57:37.4):

| Execution | Mean time lost | 5–95% range | Steps forced to back off |
| --- | --- | --- | --- |
| random 2.5% | +7.6 s | +4.0 to +13.4 s | 5% |
| random 5% | +16.3 s | +8.7 to +28.4 s | 5% |
| random 10% | +36.8 s | +19.9 to +63.1 s | 6% |
| 3% too easy | +54.4 s | +36.4 to +75.5 s | 0% |
| 3% too hard | +8.9 s | +6.7 to +11.6 s | 18% |
| 6% too hard | +12.1 s | +9.9 to +14.8 s | 29% |

Expected split times with a 5% random error:

| Checkpoint | Plan | 5–95% range |
| --- | --- | --- |
| top of climb 1 | 14:16.7 | 14:18.2 – 14:29.7 |
| bottom of descent 1 | 23:20.6 | 23:22.5 – 23:35.0 |
| end of lap 1 | 28:45.4 | 28:48.8 – 29:01.3 |
| top of climb 2 | 43:09.8 | 43:16.1 – 43:34.6 |
| bottom of descent 2 | 52:14.2 | 52:21.3 – 52:40.3 |
| finish | 57:37.4 | 57:46.1 – 58:05.8 |

* Random errors cost little: about 15 s for a typical 5% error, 35 s for a
  sloppy 10%.
* **Riding too easy is far worse than riding too hard.** A rider 3% under
  target finishes with unused reserve and loses about 55 s. A rider 3% over
  target loses only about 9 s, because the reserve simply runs out early and
  they are forced to ease off for a few short stretches.
* A simpler plan, one average power per kilometre, loses
  70 s against the detailed
  plan but still beats constant power by
  55 s.

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
- The demo courses are synthetic, and the Tokyo and Flanders courses are
  reconstructions from published course facts, not surveyed tracks.
- The fatigue rate $k$ is a placeholder that has not been fitted to data.
