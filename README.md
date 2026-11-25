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

Group decisions on the open modelling questions, with sources, are in
[DECISIONS.md](DECISIONS.md).

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

$$m_\text{eff} \frac{dv_b}{dt} = \frac{\eta P}{v_b} - \tfrac12 \rho\, C_dA\, (v_b + v_\text{wind})\lvert v_b + v_\text{wind}\rvert - C_{rr}\, m g \cos\theta(s) - m g \sin\theta(s) - F_\text{brake}, \qquad m_\text{eff} = m + I/r^2$$

$$\frac{dB}{dt} = \begin{cases} -(P - CP) & P \ge CP \\ \alpha\,(CP - P)\left(1 - B/W'\right)^{\beta} & P < CP \end{cases}$$

$$v_b^2\, \lvert\kappa(s)\rvert \le \mu\, g \cos\theta(s), \qquad 0 \le F_\text{brake} \le m\, a_\text{brake}$$

$$\frac{ds}{dt} = v_b, \qquad 0 \le B \le W', \qquad 0 \le P \le P_\text{max}, \qquad B(0) = W', \qquad v_b(0) = v_0$$

## Variables and parameters

| Symbol | Code name | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $t$ | `time` | Time elapsed | s | output |
| $s$ | `distance` | Distance ridden, $s \in [0, L]$ | m | independent variable |
| $v_b$ | `speed` | Bike speed | m/s | state |
| $P$ | `power` | Rider's pedal power ($\eta P$ reaches the wheel) | W | control |
| $B$ | `reserve` | Remaining anaerobic reserve | J | state |
| $m$ | `PhysicsParams.mass` | Rider + bike mass | kg | 80 |
| $g$ | `PhysicsParams.g` | Gravitational acceleration | m/s² | 9.81 |
| $\rho$ | `PhysicsParams.rho` | Air density (analysis: 1.15 Tokyo, 1.20 Flanders and custom loop) | kg/m³ | 1.225 |
| $C_dA$ | `PhysicsParams.cda` | Drag area | m² | 0.30 |
| $C_{rr}$ | `PhysicsParams.crr` | Rolling resistance coefficient | – | 0.004 |
| $\eta$ | `PhysicsParams.drivetrain_efficiency` | Share of pedal power reaching the wheel (Martin et al. 1998) | – | 0.977 |
| $I$ | `PhysicsParams.wheel_inertia` | Moment of inertia of both wheels (Martin et al. 1998) | kg m² | 0.14 |
| $r$ | `PhysicsParams.wheel_radius` | Outside tyre radius (Martin et al. 1998) | m | 0.311 |
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
   sweat and fuel over a time trial is under 1%. The spinning wheels add
   $I/r^2 \approx 1.45$ kg to the mass being accelerated, and the chain
   loses 2.3% of the pedal power (Martin et al. 1998).
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
| `flat.gpx` (10 km) | 11:37.5 → 11:34.7 (2.8 s) | 12:08.8 → 12:06.3 (2.5 s) |
| `hill.gpx` (10 km, 100 m hill) | 12:13.0 → 11:57.8 (15.1 s) | 12:41.2 → 12:27.3 (13.9 s) |
| `climb.gpx` (6 km at 8%) | 16:18.9 → 16:17.5 (1.4 s) | 16:07.0 → 16:05.6 (1.3 s) |
| `rolling.gpx` (20 km, 191 m climbing, wind 3 m/s from 300°) | 23:26.0 → 22:57.4 (28.6 s) | 24:16.9 → 23:51.5 (25.4 s) |
| `technical.gpx` (8 km, 6 tight corners) | 10:11.9 → 9:38.5 (33.5 s) | 10:29.7 → 9:59.9 (29.8 s) |

The optimal plan pushes above CP on climbs and into headwinds, eases off on
descents to refill $B$, and holds speed much more even than constant power
does. On the technical course it also stops pedalling ahead of the corners:
the TT specialist brakes away 11.7 kJ in total, against 29.5 kJ at constant
power. On a steady climb there is almost nothing to gain, since constant
power is already close to optimal there. The TT specialist wins everywhere
except the steep climb.

## Sensitivity to the recovery exponent β

β is a placeholder, so we varied it on `hill.gpx` (TT specialist, dynamic
program only, no polish):

| β | Constant power | Optimal | Time saved |
| --- | --- | --- | --- |
| 0.5 | 12:13.0 | 11:57.4 | 15.5 s |
| 1 | 12:13.0 | 11:57.9 | 15.1 s |
| 2 | 12:13.0 | 11:58.3 | 14.7 s |

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

These results use the full solver. The collocation polish was accepted
for 79 of the 86 solves. For the other 7, all on Tokyo, where the many tight
corners make the nonlinear program hard to converge, the solver kept the
dynamic-program plan, which is valid and close to optimal. Each result
records this in its `polished` field.

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
| Rider / bike mass [kg] | 72.6 / 8.5 | 63.2 / 7.5 | 61.7 / 8.5 | 53.7 / 7.5 |
| $C_dA$ [m²] | 0.211 | 0.217 | 0.188 | 0.193 |
| $CP$ [W] | 400 | 359 | 298 | 255 |
| $W'$ [kJ] | 31.8 | 27.5 | 27.8 | 16.1 |
| $P_\text{max}$ [W] | 1306 | 1137 | 944 | 822 |

The values come from published data on professional riders: men's mass and
power from Valenzuela et al. (2022), women's power from Mateo-March et al.
(2022), time trialists' $C_dA$ from wind-tunnel tests (Defraeye et al. 2010),
and CP and $W'$ fitted to the 5–20 min record powers. Each profile is a
typical professional of that type, not any one rider. The women's climber
has slightly *less* power per kilogram than the women's specialist, because
that is what the women's data show. Every source is in
[profiles/SOURCES.md](profiles/SOURCES.md). `analysis/plot_analysis.py` draws
each rider's power curve, $P(t) = \min(CP + W'/t,\ P_\text{max})$.

### Results on the race courses

Constant power, optimal, time saved, kinetic energy braked away; then the
optimal time and saving with long-race fatigue on ($k = 0.07$, onset
30 min):

| Course | Rider | Constant | Optimal | Saved | Braked: constant → optimal | With fatigue: optimal (saved) |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo (43.9 km) | TT specialist | 61:37.1 | 58:04.2 | 212.9 s | 242 → 108 kJ | 58:24.0 (218.4 s) |
| Tokyo (43.9 km) | Climber | 62:48.8 | 59:34.2 | 194.7 s | 178 → 73 kJ | 59:56.4 (198.9 s) |
| Tokyo (22.0 km) | TT specialist (W) | 32:54.0 | 31:09.1 | 104.8 s | 94 → 47 kJ | 31:09.2 (105.1 s) |
| Tokyo (22.0 km) | Climber (W) | 34:28.8 | 33:02.6 | 86.2 s | 63 → 24 kJ | 33:02.9 (86.6 s) |
| Flanders (43.7 km) | TT specialist | 53:42.9 | 52:23.8 | 79.1 s | 110 → 25 kJ | 52:33.4 (79.9 s) |
| Flanders (43.7 km) | Climber | 55:40.8 | 54:29.9 | 70.8 s | 85 → 18 kJ | 54:41.4 (71.5 s) |
| Flanders (30.3 km) | TT specialist (W) | 39:19.2 | 38:26.6 | 52.6 s | 58 → 11 kJ | 38:28.1 (52.9 s) |
| Flanders (30.3 km) | Climber (W) | 41:32.3 | 40:45.9 | 46.4 s | 41 → 6 kJ | 40:48.4 (46.7 s) |
| Custom loop (12.0 km) | TT specialist | 15:45.2 | 15:06.2 | 39.0 s | 49 → 24 kJ | – |
| Custom loop (12.0 km) | Climber | 16:10.3 | 15:34.5 | 35.8 s | 37 → 16 kJ | – |
| Custom loop (12.0 km) | TT specialist (W) | 16:49.5 | 16:04.4 | 45.1 s | 36 → 17 kJ | – |
| Custom loop (12.0 km) | Climber (W) | 17:47.9 | 17:13.3 | 34.7 s | 24 → 11 kJ | – |

**Check against the real races.** The model's TT specialists are
3.1–9.6% slower than the 2021 winners: Tokyo men 58:04 vs. Roglič's
55:04.19, Tokyo women 31:09 vs. van Vleuten's 30:13.49, Flanders men 52:24
vs. Ganna's 47:47.83, Flanders women 38:27 vs. van Dijk's 36:05.28. The
profiles are typical professionals of each type, not world champions, so
they should be slower, and the model is not tuned to these races.

**Where the gain comes from.** Pacing saves 4.2–5.8% on Tokyo (up to 3.5
minutes) and 1.9–2.5% on Flanders. Both real courses have far more tight
corners than the synthetic ones: the motor circuit at Fuji and the town
centres of Knokke and Bruges. A rider holding constant power pedals hard
into every one of them and then brakes the energy away. The optimal rider
eases off before each corner, sprints out of it, pushes on the climbs, and
coasts the long descents. On the men's Tokyo course the TT specialist brakes
away 108 kJ instead of 242 kJ. Corner radii come
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
| 0 (off) | 61:37.1 | 58:04.2 | 212.9 s |
| 0.035 | 61:49.5 | 58:13.9 | 215.6 s |
| 0.07 | 62:02.3 | 58:24.0 | 218.4 s |
| 0.14 | 62:47.3 | 58:45.2 | 242.1 s |

Fatigue barely matters below about 35 minutes (the women's courses). On the
52–62-minute men's courses it costs 10–22 s at
$k = 0.07$ and makes careful pacing slightly more valuable. It is off by
default (`fatigue_rate = 0`), so the core results above are unchanged.

### Weather

The wind blows uniformly from 8 directions at 2, 4, and 6 m/s, and the plan is
re-optimized each time. The table shows the change in optimal time from a calm
day, in seconds, by the direction the wind blows from:

**Flanders, men's TT specialist (point to point; calm 52:23.8)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | -80 | -74 | -21 | +56 | +108 | +97 | +33 | -38 |
| 4 m/s | -134 | -127 | -30 | +129 | +245 | +218 | +79 | -60 |
| 6 m/s | -164 | -160 | -27 | +221 | +413 | +364 | +137 | -67 |

**Tokyo, women's TT specialist (loop; calm 31:09.1)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | +7 | -9 | -18 | -15 | +2 | +23 | +32 | +24 |
| 4 m/s | +23 | -2 | -20 | -20 | +12 | +59 | +80 | +58 |
| 6 m/s | +49 | +18 | -4 | -15 | +31 | +109 | +142 | +103 |

* On the point-to-point Flanders course, which runs from the coast inland
  to the south-west, wind dominates everything else. A 6 m/s wind from the
  south costs about 7 minutes, and one from the north saves about 2.7.
  Riders starting at different times can face very different races.
* On the Tokyo loop, headwind and tailwind sections largely cancel, but not
  fully, and the climb faces one way. Wind from the east or south-east
  helps slightly, up to 20 s,
  while a 6 m/s westerly costs about 2.4 minutes.
* Pacing saves 65–94 s on Flanders and 102–112 s on
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
men's Tokyo plan (TT specialist, perfect time 58:04.2):

| Execution | Mean time lost | 5–95% range | Steps forced to back off |
| --- | --- | --- | --- |
| random 2.5% | +10.4 s | +7.8 to +13.8 s | 4% |
| random 5% | +21.7 s | +16.3 to +28.8 s | 4% |
| random 10% | +46.0 s | +34.3 to +62.3 s | 4% |
| 3% too easy | +51.6 s | +37.3 to +68.8 s | 0% |
| 3% too hard | +20.6 s | +17.0 to +24.7 s | 12% |
| 6% too hard | +29.3 s | +25.3 to +33.0 s | 18% |

Expected split times with a 5% random error:

| Checkpoint | Plan | 5–95% range |
| --- | --- | --- |
| top of climb 1 (km 10.5) | 15:11.3 | 15:17.7 – 15:23.0 |
| bottom of descent 1 (km 15.5) | 20:09.6 | 20:16.3 – 20:21.9 |
| end of lap 1 (km 22.0) | 28:54.7 | 29:03.3 – 29:12.3 |
| top of climb 2 (km 32.5) | 44:23.5 | 44:37.2 – 44:48.4 |
| bottom of descent 2 (km 37.5) | 49:21.8 | 49:35.8 – 49:46.7 |
| finish (km 43.9) | 58:04.2 | 58:20.5 – 58:33.0 |

* Random errors cost little: about 22 s for a typical 5%
  error, 46 s for a sloppy 10%.
* **Riding too easy is far worse than riding too hard.** A rider 3% under
  target finishes with unused reserve and loses about 52 s.
  A rider 3% over target loses only about 21 s, because
  the reserve runs out early and they are forced to ease off for a few short
  stretches.
* **Timing matters more than averages.** A simplified plan with one average
  power per kilometre loses 148 s against the
  detailed plan and beats constant power by only 65 s.
  It averages away exactly the moves that matter: easing off before corners
  and sprinting out of them. Race guidance should describe where to change
  effort, not just how hard to ride each kilometre.

### Team time trial

See [docs/team_time_trial.md](docs/team_time_trial.md): position-dependent
drag, one speed shared by six reserves, rotation and release decisions, and
the fourth-rider finish. In the equal-share approximation, six TT specialists
ride at about 59.8 km/h against 50.8 km/h alone.

## Known limits

- $C_dA$ and $C_{rr}$ do not vary with position or speed, and $\rho$ is one
  value per venue.
- The CP model lets the rider hold exactly CP forever, so it is only reasonable
  for efforts from a few minutes up to roughly an hour.
- The optimizer is global only up to the resolution of the dynamic program's
  grids.
- The demo courses are synthetic. The Tokyo and Flanders files are
  user-made RideWithGPS routes, not official organiser files.
- The fatigue rate $k$ is a placeholder that has not been fitted to data.
