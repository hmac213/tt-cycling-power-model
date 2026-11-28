# Solver

Couples the three models and solves the pacing problem

$$\min_{P(\cdot)} \; T = \int_0^L \frac{ds}{v_b(s)} \quad \text{subject to the physics and stamina dynamics}, \quad 0 \le P \le P_\text{max}, \quad B \ge 0, \quad v_b \le V(s).$$

## The grid

The course is cut into steps of one fixed length, 20 m by default
(`SimConfig.step_length`), so a course twice as long gets twice as many steps.
Power is constant on each step. The simulator and both optimization stages use
this same grid, so the pacing plan is as fine as the states it is checked
against.

Inside a step the speed is integrated with 4 RK4 substeps of 5 m
(`SimConfig.substeps`), each reading slope and wind from the smooth course.
The substeps are there for accuracy only. Without them, a plan that stops
pedalling on a steep climb changes speed so much in one step that the
integrator is wrong by seconds, and an optimizer will find and exploit that.

Distance is the independent variable, so the finish is a fixed endpoint and
$T$ is an output.

## Method

**Simulate** (`simulate.py`). The state $z = v_b^3$ is advanced with RK4 on
$dz/ds = \tfrac{3}{m}(P - v_b F_\text{res})$. At the end of each step the speed
is capped at the envelope $V$, and the kinetic energy removed is recorded as
braking. Time is the integral of $ds / v_b$ over 8 pieces per step, with
$v_b^3$ taken as linear in $s$ on each piece, which gives
$\Delta t = \tfrac32 h\,(a + b)/(a^2 + ab + b^2)$ for speeds $a, b$ at the two
ends of a piece. The stamina state (deficit $x$, fatigue $F$, work $E$; see
[../power_model/README.md](../power_model/README.md)) is then updated over
the step's duration, with critical power and reserve capacity taken from
the start of the step.

**Optimize** (`optimize.py`) runs two stages.

1. **Dynamic programming** (`dynamic_program.py`). Let $J_k(v, x, F)$ be the
   least time to the finish from node $k$ at speed $v$, with deficit $x$ of
   the fast reserve and fatigue $F$. Then $J_n = 0$ and

   $$J_k(v, x, F) = \min_{P} \big[\, \Delta t(v, P) + J_{k+1}(v', x', F') \,\big], \qquad x' \le 1.$$

   $J$ is tabulated backwards from the finish on a grid of 50 speeds, 40
   deficits and 12 fatigues, trying 25 power levels at every grid point. The
   plan is then read off by riding forwards from the start and taking the
   best power at each step. This looks at every plan the grids can express,
   so it needs no starting guess and cannot get stuck in a local optimum.
   Its answer is rounded to the grids.
2. **Collocation** (`collocation.py`). Speed, the three stamina states, and
   power at every node become the unknowns of one sparse nonlinear program,
   with the dynamics as constraints between neighbouring nodes. IPOPT solves
   it with exact derivatives from CasADi, starting from the dynamic
   program's plan. This removes the rounding. The result is kept only if the
   simulator confirms it is feasible and no slower than stage 1.

`optimize.constant_power_ride` finds the highest constant power that never
overdraws the fast reserve. It is the benchmark.

### The work state in the dynamic program

The stamina model has three states, but the table has only two of them as
dimensions. The work done $E$ only sets the size $W'$ of the fast reserve,
and how much work has been done by a given point on the course hardly
depends on the pacing. So the table is built with $W'$ at each step taken
from a reference ride (the constant-power ride), while the forward ride
tracks $E$ exactly. If $W'$ along the forward ride differs from the
reference by more than 1% anywhere, the table is rebuilt with the forward
ride as the new reference. The collocation stage and the simulator carry
$E$ exactly, so the final plan obeys the full model.

Fatigue $F$ is different: it depends strongly on the pacing and is the main
trade-off the optimizer makes over a long race, so it is a full dimension
of the table.

### Details of the collocation stage

- **Braking.** The motion constraint is an inequality,
  $v_{k+1}^3 \le$ (RK4 result). The gap is the kinetic energy braked away, so
  no separate brake variable is needed. The corner limit is a plain bound,
  $v_{k+1} \le V$.
- **The kink at $P = CP$.** Besides the power $P$ there is a second unknown
  per step, $e \ge \max(P - CP, 0)$, the power counted as above critical
  power. Draining depends only on $e$ and recovery only on $CP - P + e$, and
  both pieces are smooth. Choosing $e$ larger than it must be never pays as
  long as $\alpha \le 1$, so the optimum has $e = \max(P - CP, 0)$ on its
  own.
- **Same equations as the simulator.** The transcription reuses the
  simulator's RK4 substeps, time rule, and stamina update, so the polished
  plan is verified by simply simulating it.

### Imperfect execution (`execution.py`)

`execution.ride_plan` rides a fixed plan with relative power errors
(`execution.power_noise`: a drifting AR(1) error plus an optional bias),
and/or on a grid with different wind from the one the plan was made for.
When a requested power would take the reserve below zero, the rider rides
the largest power that keeps $B \ge 0$ instead. It simulates many rides at
once and reports split times at any distances.

## Settings

| Name | Where | Meaning | Default |
| --- | --- | --- | --- |
| `step_length` | `SimConfig` | Length of one grid step [m] | 20 |
| `substeps` | `SimConfig` | RK4 substeps per grid step | 4 |
| `initial_speed` | `SimConfig` | Speed at the start line [m/s] | 0 (standing start) |
| `min_speed` | `SimConfig` | Speed floor [m/s] | 0.5 |
| `corner_window` | `SimConfig` | Curvature averaging length for the corner limit [m] | 20 |
| `num_speeds`, `num_deficits`, `num_fatigues`, `num_powers` | `DpConfig` | Grid sizes of the dynamic program | 50, 40, 12, 25 |
| `rollout_refinement` | `DpConfig` | Extra power levels tried in the forward ride | 4x |

Run time grows in proportion to course length: about 20 s for 8 km, 50 s for
20 km, and a few minutes for the 44 km championship courses.

## How accurate it is

Measured on `technical.gpx` with the TT specialist:

| Step length | Steps | Optimal time | Run time |
| --- | --- | --- | --- |
| 80 m | 100 | 9:45.6 | 5 s |
| 40 m | 200 | 9:43.8 | 9 s |
| 20 m | 400 | 9:44.4 | 18 s |
| 10 m | 799 | 9:44.0 | 39 s |
| 5 m | 1598 | 9:43.7 | 77 s |

- From 40 m down, the time moves by less than 1 s in 9.7 minutes.
- Doubling every grid of the dynamic program changes its time by 0.13 s.
- The polish improves on the dynamic program by 0.15 to 0.5 s on the five
  demo courses and gives a smoother power trace.
- On the hill and climb courses, re-integrating the final plans with 0.25 m
  substeps reproduces the reported times to within 3 ms.

## Assumptions

- Power is constant on each grid step and may jump freely between steps.
- The rider starts fresh, $B(0) = W'$, and may finish with anything $B(L) \ge 0$.
  The optimum always finishes empty.

## Ambiguities and gaps filled

- **Solution method.** The write-up poses the optimal control problem but not
  how to solve it.
- **Step length.** 20 m is about 1.5 s of riding at race speed, close to how
  fast a rider can deliberately change effort.
- **Initial speed.** Not specified. The baseline uses a standing start,
  $v_0 = 0$, as in a real time trial.
- **Stalling.** With $P \ge 0$ the rider could still stall on a steep climb at
  low power, which makes $dt = ds/v_b$ blow up. Speed is floored at
  `min_speed` = 0.5 m/s. This never binds near an optimal ride.
- **Control in distance vs. time.** The write-up writes $P(t)$. The solver finds
  $P(s)$, and since $t(s)$ is increasing the two describe the same plan.
- **Braking within a step.** When the rider brakes, the speed removed is taken
  to come off evenly along the step.

## Limitations

- **Global only up to the grids.** The dynamic program's guarantee holds for
  plans its grids can express. The checks above suggest the rounding is under
  0.1 s, but that is evidence, not proof.
- **The polish is local.** It refines the plan it is given and has no global
  guarantee of its own. If it ever returns a slower or infeasible plan, that
  plan is discarded and stage 1's is used.
- **$\alpha > 1$ skips the polish.** If recovery returns more than a joule per
  joule, the split-power form could create reserve from nothing, so only the
  dynamic program runs. The dynamic program itself then exploits the same
  loophole in the model by alternating hard and easy steps.
- **Memory.** The value table holds (steps x 50 x 40 x 12) numbers, about
  100 MB for 20 km and 210 MB for the 44 km championship courses.
- **The table uses a reference for $W'$.** See "The work state in the
  dynamic program" above. The forward ride, the polish and the simulator do
  not.
- **Corner timing.** The corner limit for a step is the lowest envelope value
  inside it, so a corner is entered up to one step early.
