# Time-Trial Cycling Power Model

Model for optimal pacing in an individual time trial.

## Problem restatement

Given a course of length $L$ described by its incline angle $\theta(s)$,
curvature $\kappa(s)$, and headwind $v_\text{wind}(s)$, find the power profile
$P \ge 0$ that minimizes the race time

$$T = \int_0^L \frac{ds}{v_b(s)}$$

subject to the equation of motion of the bike, the grip limit in corners, and
the rider's stamina: a rechargeable reserve above critical power, and a slow
loss of durability that lowers critical power as the race goes on.

## Layout

| Folder | What it does | Model notes |
| --- | --- | --- |
| `course_loader/` | Smooth course geometry from a GPX track: $\theta(s)$, $\kappa(s)$, heading, $v_\text{wind}(s)$ | [course_loader/README.md](course_loader/README.md) |
| `physics_model/` | Power-to-speed equation of motion and cornering limits | [physics_model/README.md](physics_model/README.md) |
| `power_model/` | Two-reserve stamina model: critical power with durability | [power_model/README.md](power_model/README.md) |
| `profiles/` | Rider profiles (JSON): masses, $C_dA$, and power numbers | [profiles/README.md](profiles/README.md) |
| `solver/` | Forward simulation and two-stage pacing optimization | [solver/README.md](solver/README.md) |
| `courses/` | The Tokyo and Flanders 2021 courses, our custom loop, synthetic demo courses, and the scripts that generate them | [courses/README.md](courses/README.md) |
| `analysis/` | Experiments for the full problem statement (race courses, wind, power errors, durability) and their figures | |
| `docs/` | Team time trial extension | [docs/team_time_trial.md](docs/team_time_trial.md) |
| `tests/` | Sanity checks | |

Group decisions on the open modelling questions are in
[DECISIONS.md](DECISIONS.md). Every source, what was taken from it, and where
it is used is listed in [SOURCES.md](SOURCES.md).

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
over (distance, speed, reserve, fatigue) first finds the globally best plan
its grids can express, and a collocation solve (CasADi + IPOPT) then polishes it. See
[solver/README.md](solver/README.md).

## Full system

State $(v_b, x, F, E)$, control $P$, written against time. $x$ is the deficit
of the fast reserve, $F$ the fatigue, and $E$ the work done:

$$m_\text{eff} \frac{dv_b}{dt} = \frac{\eta P}{v_b} - \tfrac12 \rho\, C_dA\, (v_b + v_\text{wind})\lvert v_b + v_\text{wind}\rvert - C_{rr}\, m g \cos\theta(s) - m g \sin\theta(s) - F_\text{brake}, \qquad m_\text{eff} = m + I/r^2$$

$$\frac{dF}{dt} = \max(i, 0)^{\gamma}, \quad i = \frac{P - LT1}{LT2 - LT1}, \qquad \frac{dE}{dt} = P$$

$$CP = LT1 + (LT2 - LT1)\, e^{-(F/\tau_F)^2}, \qquad W' = W'_0\, e^{-E/E_W}$$

$$\frac{dx}{dt} = \begin{cases} (P - CP)/W' & P \ge CP \\ -\alpha\,(CP - P)\, x^{\beta}/W' & P < CP \end{cases} \qquad B = (1 - x)\,W'$$

$$v_b^2\, \lvert\kappa(s)\rvert \le \mu\, g \cos\theta(s), \qquad 0 \le F_\text{brake} \le m\, a_\text{brake}$$

$$\frac{ds}{dt} = v_b, \qquad 0 \le x \le 1, \qquad 0 \le P \le P_\text{max}, \qquad x(0) = F(0) = E(0) = 0, \qquad v_b(0) = v_0$$

## Variables and parameters

| Symbol | Code name | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $t$ | `time` | Time elapsed | s | output |
| $s$ | `distance` | Distance ridden, $s \in [0, L]$ | m | independent variable |
| $v_b$ | `speed` | Bike speed | m/s | state |
| $P$ | `power` | Rider's pedal power ($\eta P$ reaches the wheel) | W | control |
| $x$ | `deficit` | Deficit of the fast reserve, $1 - B/W'$ | – | state |
| $B$ | `reserve` | Fast reserve left above critical power, $(1 - x)W'$ | J | output |
| $F$ | `fatigue` | Fatigue, in seconds ridden at LT2; never recovers | s | state |
| $E$ | `work` | Mechanical work done | J | state |
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
| $LT1$ | `RiderParams.lt1` | First lactate threshold: where fatigue starts, and the floor of critical power | W | 225 |
| $LT2$ | `RiderParams.lt2` | Second lactate threshold, taken as the fresh critical power | W | 300 |
| $W'_0$ | `RiderParams.w_prime` | Work capacity above critical power when fresh | J | 20 000 |
| $P_\text{max}$ | `RiderParams.p_max` | Cap on instantaneous power | W | 900 |
| $\alpha$ | `RiderParams.alpha` | Recovery rate coefficient | – | 1 |
| $\beta$ | `RiderParams.beta` | Recovery saturation exponent | – | 1 |
| $\gamma$ | `RiderParams.fatigue_exponent` | How steeply fatigue grows with intensity | – | 1.7 |
| $\tau_F$ | `RiderParams.fatigue_time` | Fatigue at which critical power has lost 63% of $LT2 - LT1$ | s | 3000 |
| $E_W$ | `RiderParams.work_capacity` | Work at which $W'$ has fallen to 37% (profiles: 57.4 kJ per kg of rider) | J | 4.3 MJ |
| $v_0$ | `SimConfig.initial_speed` | Speed at the start line | m/s | 0 |
| $h$ | `SimConfig.step_length` | Length of one grid step | m | 20 |

The defaults are a generic rider. The rider profiles in `profiles/` override
mass, $C_dA$, $C_{rr}$, the thresholds, $W'_0$, and $P_\text{max}$.

## Ambiguities and how the baseline resolves them

- **Rider stamina limits.** A rider cannot hold sprint power forever, and
  cannot hold critical power forever either. Resolved with a two-reserve
  model: the Critical Power / $W'$ reserve for short efforts, and a
  durability reserve that lowers critical power over long ones
  ([power_model/README.md](power_model/README.md)).
- **Course geometry and turns.** Corners cap speed no matter the power
  available. Resolved with a grip limit on lateral acceleration and a
  latest-braking speed envelope, both computed from the curvature of the GPX
  track.
- **Depletion vs. recovery.** Riding above CP drains the finite reserve $W'$;
  riding below CP refills it. Fatigue, in contrast, never recovers during
  the race.

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
| `flat.gpx` (10 km) | 11:36.8 → 11:35.0 (1.8 s) | 12:08.3 → 12:06.7 (1.6 s) |
| `hill.gpx` (10 km, 100 m hill) | 12:12.1 → 11:59.6 (12.5 s) | 12:40.6 → 12:29.4 (11.2 s) |
| `climb.gpx` (6 km at 8%) | 16:17.3 → 16:14.9 (2.3 s) | 16:05.6 → 16:03.6 (2.0 s) |
| `rolling.gpx` (20 km, 191 m climbing, wind 3 m/s from 300°) | 23:27.6 → 23:08.1 (19.5 s) | 24:18.8 → 24:01.8 (17.0 s) |
| `technical.gpx` (8 km, 6 tight corners) | 10:11.3 → 9:44.4 (27.0 s) | 10:29.4 → 10:05.7 (23.7 s) |

The optimal plan pushes above CP on climbs and into headwinds, eases off on
descents to refill $B$, and holds speed much more even than constant power
does. On the technical course it also stops pedalling ahead of the corners:
the TT specialist brakes away 12.0 kJ in total, against 29.6 kJ at constant
power. On a steady climb there is almost nothing to gain, since constant
power is already close to optimal there. The TT specialist wins everywhere
except the steep climb.

## Sensitivity to the recovery exponent β

β is a placeholder, so we varied it on `hill.gpx` (TT specialist, dynamic
program only, no polish):

| β | Constant power | Optimal | Time saved |
| --- | --- | --- | --- |
| 0.5 | 12:12.1 | 11:59.4 | 12.6 s |
| 1 | 12:12.1 | 11:59.8 | 12.3 s |
| 2 | 12:12.1 | 12:00.1 | 11.9 s |

The time saved changes by only ±0.4 s over a 4× range of β, so the main
result does not depend on this uncertain parameter. Larger β slows recovery,
since (1 − B/W′)^β shrinks as β grows when B < W′, which slightly reduces the
benefit of recovering on the descent. The constant-power ride never drops
below its critical power, so it never recovers and β does not affect it.

## The full problem statement (2022 MCM Problem A)

The sections above cover the core model. This section covers every item
the problem statement asks for. Reproduce it with

```bash
python -m analysis.run_analysis all      # about 45 min on 7 cores
python analysis/plot_analysis.py         # figures in outputs/analysis/figures
```

A frozen copy of the summaries and figures is in `results/`.

| Requirement | Where |
| --- | --- |
| Two rider types, one a TT specialist, and both genders | `profiles/`: `tt_specialist`, `climber`, `tt_specialist_women`, `climber_women` |
| 2021 Olympic TT course, Tokyo | `courses/tokyo_2021_men.gpx` (44 km), `tokyo_2021_women.gpx` (22 km) |
| 2021 Worlds TT course, Flanders | `courses/flanders_2021_men.gpx` (43.3 km), `flanders_2021_women.gpx` (30.3 km) |
| Own course: 4+ sharp turns, a real grade, finish near start | `courses/custom_loop.gpx` |
| Limits on total energy, past aggressiveness, fatigue | W′ (past aggressiveness) plus the durability reserve: fatigue lowers CP, and work done shrinks W′ |
| Weather sensitivity | `analysis/run_analysis.py wind` |
| Sensitivity to missing power targets, split-time ranges | `solver/execution.py`, `analysis/run_analysis.py deviation` |
| Team time trial extension | [docs/team_time_trial.md](docs/team_time_trial.md) |

These results use the full solver. The collocation polish was accepted
for 83 of the 86 solves. For the other 3, all the TT specialist on the men's
Tokyo course, where the many tight corners make the nonlinear program hard
to converge, the solver kept the dynamic-program plan, which is valid and
close to optimal. Each result
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
| LT1 [W] | 309 | 278 | 230 | 196 |
| LT2 = fresh $CP$ [W] | 412 | 370 | 307 | 261 |
| $W'_0$ [kJ] | 28.75 | 24.1 | 25.7 | 14.9 |
| $P_\text{max}$ [W] | 1306 | 1137 | 944 | 822 |

The values come from published data on professional riders: men's mass and
power from Valenzuela et al. (2022), women's power from Mateo-March et al.
(2022), time trialists' $C_dA$ from wind-tunnel tests (Defraeye et al. 2010),
and LT2 and $W'_0$ fitted through the stamina model to the 5–20 min record
powers, with LT1 assumed to be 75% of LT2. Each profile is a
typical professional of that type, not any one rider. The women's climber
has slightly *less* power per kilogram than the women's specialist, because
that is what the women's data show. Every source is in
[profiles/SOURCES.md](profiles/SOURCES.md). `analysis/plot_analysis.py` draws
each rider's power curve, the best constant power the model allows for each
duration.

### Results on the race courses

Constant power, optimal, time saved, kinetic energy braked away; then, for
comparison, the optimal time and saving of the same rider under the classic
Critical Power model (no loss of durability):

| Course | Rider | Constant | Optimal | Saved | Braked: constant → optimal | Classic CP model: optimal (saved) |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo (43.9 km) | TT specialist | 63:01.3 | 60:50.9 | 130.5 s | 231 → 128 kJ | 57:30.9 (200.1 s) |
| Tokyo (43.9 km) | Climber | 64:14.4 | 62:13.2 | 121.2 s | 169 → 90 kJ | 58:59.3 (182.9 s) |
| Tokyo (22.0 km) | TT specialist (W) | 33:06.1 | 31:48.5 | 77.7 s | 93 → 49 kJ | 30:51.3 (98.7 s) |
| Tokyo (22.0 km) | Climber (W) | 34:44.9 | 33:44.1 | 60.8 s | 62 → 33 kJ | 32:45.0 (83.3 s) |
| Flanders (43.7 km) | TT specialist | 54:23.7 | 53:52.7 | 31.0 s | 105 → 48 kJ | 51:56.5 (78.1 s) |
| Flanders (43.7 km) | Climber | 56:25.3 | 55:56.5 | 28.9 s | 81 → 36 kJ | 54:01.2 (70.0 s) |
| Flanders (30.3 km) | TT specialist (W) | 39:34.5 | 39:18.9 | 15.6 s | 56 → 25 kJ | 38:06.4 (52.6 s) |
| Flanders (30.3 km) | Climber (W) | 41:53.7 | 41:37.2 | 16.5 s | 39 → 15 kJ | 40:29.0 (46.1 s) |
| Custom loop (12.0 km) | TT specialist | 15:44.4 | 15:13.0 | 31.4 s | 49 → 26 kJ | – |
| Custom loop (12.0 km) | Climber | 16:09.7 | 15:41.4 | 28.3 s | 37 → 18 kJ | – |
| Custom loop (12.0 km) | TT specialist (W) | 16:49.4 | 16:12.8 | 36.6 s | 36 → 18 kJ | – |
| Custom loop (12.0 km) | Climber (W) | 17:47.8 | 17:18.7 | 29.1 s | 24 → 12 kJ | – |

**Check against the real races.** The model's TT specialists are
5.2–12.7% slower than the 2021 winners: Tokyo men 60:51 vs. Roglič's
55:04.19, Tokyo women 31:49 vs. van Vleuten's 30:13.49, Flanders men 53:53
vs. Ganna's 47:47.83, Flanders women 39:19 vs. van Dijk's 36:05.28. The
profiles are typical professionals of each type, not world champions, so
they should be slower, and the model is not tuned to these races. The gap
is widest on the two men's courses, which take about an hour. That
suggests the population fatigue numbers are too harsh for the very best
riders; fitting $\tau_F$ to each profile's best efforts of an hour or more
would settle it (see [profiles/SOURCES.md](profiles/SOURCES.md)).

**Where the gain comes from.** Pacing saves 2.9–3.9% on Tokyo (up to 2.2
minutes) and 0.7–0.9% on Flanders. Both real courses have far more tight
corners than the synthetic ones: the motor circuit at Fuji and the town
centres of Knokke and Bruges. A rider holding constant power pedals hard
into every one of them and then brakes the energy away. The optimal rider
eases off before each corner, pushes on the climbs, and coasts the long
descents. On the men's Tokyo course the TT specialist brakes away 128 kJ
instead of 231 kJ. Corner radii come
from the GPX line, so a route drawn slightly off the real racing line would
make some corners tighter than they are. Treat the corner share of the gain
as an upper estimate.

### Fatigue: durability

The classic CP model lets a rider hold CP forever. The problem says riders
tire as the race goes on, so in our model fatigue builds with intensity and
critical power sinks from LT2 towards LT1, while $W'$ shrinks with the work
done ([power_model/README.md](power_model/README.md)). On the men's Tokyo
course the TT specialist's critical power falls from 412 W at the start to
336 W at the finish.

This changes three things, all visible in the table above.

* **Long races are slower.** The same rider is 200 s slower on the men's
  Tokyo course and 116 s slower on the men's Flanders course than the classic
  model says, and 57–73 s slower on the half-hour to 40-minute women's
  courses.
* **The plan is smoother.** Under the classic model the men's Tokyo plan
  spends 491 s above 600 W, sprinting out of every corner. With durability
  it spends 33 s there and never exceeds 646 W, because hard surges now have
  a lasting cost.
* **Pacing is worth less, but still a lot on a varied course.** The saving
  over constant power drops from 200 s to 131 s on Tokyo and from 78 s to
  31 s on flat Flanders.

The fatigue time $\tau_F$ is the least certain number, so here is its
effect on the men's Tokyo course (TT specialist):

| $\tau_F$ | Constant | Optimal | Saved |
| --- | --- | --- | --- |
| classic model (no loss) | 60:51.0 | 57:30.9 | 200.1 s |
| 6000 s | 61:46.7 | 59:22.5 | 144.2 s |
| 3000 s (default) | 63:01.3 | 60:50.9 | 130.5 s |
| 1500 s | 64:29.7 | 62:35.2 | 114.5 s |

Halving or doubling $\tau_F$ moves the optimal time by 1.5 to 1.7 minutes
in an hour, so this parameter matters and should be fitted per rider when
long best efforts are available.

### Weather

The wind blows uniformly from 8 directions at 2, 4, and 6 m/s, and the plan is
re-optimized each time. The table shows the change in optimal time from a calm
day, in seconds, by the direction the wind blows from:

**Flanders, men's TT specialist (point to point; calm 53:52.7)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | -82 | -75 | -20 | +57 | +109 | +98 | +33 | -40 |
| 4 m/s | -136 | -128 | -29 | +133 | +249 | +221 | +79 | -62 |
| 6 m/s | -164 | -160 | -24 | +228 | +424 | +373 | +139 | -69 |

**Tokyo, women's TT specialist (loop; calm 31:48.5)**

| Wind | N | NE | E | SE | S | SW | W | NW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 m/s | +7 | -8 | -17 | -14 | +2 | +24 | +33 | +25 |
| 4 m/s | +25 | +1 | -17 | -18 | +14 | +62 | +82 | +59 |
| 6 m/s | +53 | +26 | -0 | -12 | +35 | +114 | +147 | +105 |

* On the point-to-point Flanders course, which runs from the coast inland
  to the south-west, wind dominates everything else. A 6 m/s wind from the
  south costs about 7 minutes, and one from the north saves about 2.7.
  Riders starting at different times can face very different races.
* On the Tokyo loop, headwind and tailwind sections largely cancel, but not
  fully, and the climb faces one way. Wind from the east or south-east
  helps slightly, up to 18 s,
  while a 6 m/s westerly costs about 2.4 minutes.
* Pacing saves 30–39 s on Flanders and 72–82 s on
  Tokyo across all these winds. The optimal rider pushes into the headwind
  and saves energy in the tailwind.

**Wrong forecast.** A plan made for a 4 m/s wind from the south-west, ridden
in winds 1 m/s stronger or weaker and 45° off, costs at most 14 s
against a plan made for the actual wind. The plan is robust to small
forecast errors. What matters is knowing roughly where the wind comes from.

### Missing the power targets

`solver/execution.py` rides the optimal plan with errors that drift along
the course (correlation length 200 m). Whenever the reserve runs out, the
rider is forced down to the most they can still sustain. 500 rides of the
men's Tokyo plan (TT specialist, perfect time 60:50.9):

| Execution | Mean time lost | 5–95% range | Steps forced to back off |
| --- | --- | --- | --- |
| random 2.5% | +5.5 s | +2.7 to +10.5 s | 2% |
| random 5% | +14.6 s | +9.3 to +23.4 s | 2% |
| random 10% | +39.6 s | +29.0 to +55.5 s | 3% |
| 3% too easy | +54.2 s | +36.5 to +73.7 s | 0% |
| 3% too hard | +19.1 s | +14.4 to +23.7 s | 9% |
| 6% too hard | +32.3 s | +27.9 to +37.2 s | 15% |

Expected split times with a 5% random error:

| Checkpoint | Plan | 5–95% range |
| --- | --- | --- |
| top of climb 1 (km 10.5) | 15:23.0 | 15:24.6 – 15:33.9 |
| bottom of descent 1 (km 15.5) | 20:25.4 | 20:26.7 – 20:36.5 |
| end of lap 1 (km 22.0) | 29:41.4 | 29:42.8 – 29:56.1 |
| top of climb 2 (km 32.5) | 46:09.4 | 46:16.6 – 46:29.5 |
| bottom of descent 2 (km 37.5) | 51:17.7 | 51:24.9 – 51:37.8 |
| finish (km 43.9) | 60:50.9 | 61:00.1 – 61:14.3 |

* Random errors cost little: about 15 s for a typical 5%
  error, 40 s for a sloppy 10%.
* **Riding too easy is far worse than riding too hard.** A rider 3% under
  target finishes with unused reserve and loses about 54 s.
  A rider 3% over target loses only about 19 s, because
  the reserve runs out early and they are forced to ease off for a few short
  stretches.
* **Timing matters more than averages.** A simplified plan with one average
  power per kilometre loses 113 s against the
  detailed plan and beats constant power by only 18 s.
  It averages away exactly the moves that matter: easing off before corners
  and pushing on the climbs. Race guidance should describe where to change
  effort, not just how hard to ride each kilometre.

### Team time trial

See [docs/team_time_trial.md](docs/team_time_trial.md): position-dependent
drag, one speed shared by six reserves, rotation and release decisions, and
the fourth-rider finish. In the equal-share approximation, six TT specialists
ride at about 60.5 km/h against 51.3 km/h alone.

## Known limits

- $C_dA$ and $C_{rr}$ do not vary with position or speed, and $\rho$ is one
  value per venue.
- The stamina model is meant for efforts up to about 6 hours. Beyond that,
  fueling, heat and sleep matter, and none of them is modelled.
- The fatigue parameters $\gamma$, $\tau_F$ and $E_W$ are population values
  from two small studies, and LT1 is assumed to be 75% of LT2.
- The optimizer is global only up to the resolution of the dynamic program's
  grids.
- The demo courses are synthetic. The Tokyo and Flanders files are
  user-made RideWithGPS routes, not official organiser files.
