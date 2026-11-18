# Physics model (power to speed, cornering)

Newton's second law along the road:

$$m \frac{dv_b}{dt} = F_\text{drive} - F_\text{air} - F_{rr} - F_\text{grav}$$

$$m \frac{dv_b}{dt} = \frac{P}{v_b} - \tfrac12 \rho\, C_dA\, (v_b + v_\text{wind})\lvert v_b + v_\text{wind}\rvert - C_{rr}\, m g \cos\theta(s) - m g \sin\theta(s)$$

| Force | Expression | Function |
| --- | --- | --- |
| Drive | $P / v_b$ | (inside `acceleration`) |
| Aerodynamic drag | $\tfrac12 \rho\, C_dA\, (v_b + v_\text{wind})\lvert v_b + v_\text{wind}\rvert$ | `aero_force` |
| Rolling resistance | $C_{rr}\, m g \cos\theta$ | `rolling_force` |
| Gravity | $m g \sin\theta$ | `gravity_force` |

## Parameters (`PhysicsParams`)

| Symbol | Field | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $m$ | `mass` | Rider + bike mass | kg | 80 |
| $g$ | `g` | Gravitational acceleration | m/s² | 9.81 |
| $\rho$ | `rho` | Air density | kg/m³ | 1.225 |
| $C_dA$ | `cda` | Drag area (typical range 0.25–0.35) | m² | 0.30 |
| $C_{rr}$ | `crr` | Rolling resistance coefficient | – | 0.004 |
| $\mu$ | `mu_corner` | Usable lateral grip (max cornering acceleration / $g$) | – | 0.5 |
| $a_\text{brake}$ | `brake_decel` | Largest deceleration from the brakes alone | m/s² | 3.0 |

The defaults are a generic rider. A rider profile (`profiles/`) overrides
$m$, $C_dA$, and $C_{rr}$ and leaves the rest alone.

Inputs that come from elsewhere: $P$ (control, from the solver), and
$\theta(s)$, $\kappa(s)$, $v_\text{wind}(s)$ (from `course_loader`).

## Distance form used by the solver

The term $P / v_b$ blows up at $v_b = 0$, which is exactly where a time trial
starts. Using $dt = ds / v_b$ and multiplying through by $v_b$ gives
$m v_b^2 \, dv_b/ds = P - v_b F_\text{res}(v_b)$, meaning

$$\frac{d(v_b^3)}{ds} = \frac{3}{m}\Big(P - v_b\, F_\text{res}(v_b, s)\Big), \qquad F_\text{res} = F_\text{air} + F_{rr} + F_\text{grav}.$$

This is the same physics with no singularity (`dynamics.speed_cubed_rate`). It is a change of
variables, not an extra assumption.

## Cornering (`cornering.py`)

**Grip limit.** In a corner of curvature $\kappa$ the tyres must supply the
lateral acceleration $v_b^2 \lvert\kappa\rvert$, which is capped by grip:

$$v_b^2\, \lvert\kappa(s)\rvert \le \mu\, g \cos\theta(s) \quad\Longrightarrow\quad v_\text{corner}(s) = \sqrt{\frac{\mu\, g \cos\theta(s)}{\lvert\kappa(s)\rvert}}$$

(`corner_speed_limit`). The curvature used is the 20 m average
(`SimConfig.corner_window` in the solver), which is far less noise-sensitive than the
pointwise value.

**Speed envelope.** The rider must also be able to slow down in time. The
hardest they can decelerate is with full brakes and no pedalling, at
$a = a_\text{brake} + F_\text{res}(v_b, s)/m$. Marching backwards from the finish,

$$V^2(s) = \min\Big(v_\text{corner}^2(s),\; V^2(s + ds) + 2\,a(s)\,ds\Big)$$

gives the envelope $V(s)$ (`speed_envelope`): the fastest speed at each point
from which every corner ahead can still be made. It equals $v_\text{corner}$
inside a corner and rises ahead of it along the latest-braking curve.

**How the rider uses it.** The model requires $v_b(s) \le V(s)$. The simulator
applies the brakes only when the speed would cross the envelope, and only as
much as needed, so braking is never wasted. Whether to keep pedalling right up
to the braking point or to stop early and coast into the corner is left to the
pacing plan. Pedalling into a corner burns $W'$ that the brakes then turn to
heat, so the optimizer coasts wherever the reserve is worth more than the time.

## Assumptions

- **Constant mass.** Sweat and fuel loss is under 1% over a time trial.
- **Constant $C_dA$.** The rider keeps one position for the whole course.
- **Constant $C_{rr}$ and $\rho$.** Uniform road surface, no equipment wear, and
  no change in air density with altitude or temperature.
- **Braking only for corners.** The control is $P \ge 0$, and the brakes act
  only to keep the speed on or under the envelope.
- **The rider follows the GPX line.** No use of the road width to open up a
  corner.
- **No crosswinds.** Wind enters only through its component along the road.
- **Point mass.** The rider and bike are one particle moving along the road.

## Ambiguities and gaps filled

- **Sign of the wind.** $v_\text{wind} > 0$ is a headwind. The $x\lvert x\rvert$ form
  means a tailwind faster than the rider pushes them forward, as it should.
- **Drivetrain efficiency.** Not in the write-up. $P$ is taken as power at the
  wheel (efficiency 1). To model pedal power, scale $P$ by about 0.97.
- **Rotational inertia of the wheels.** Ignored. It would add roughly 1–2% to
  the effective mass in the $m\, dv/dt$ term only.
- **Cornering was assumed away in the write-up** ("continuous, obstacle-free
  track", "braking force ignored"). Both are now relaxed as described above.
- **Grip and braking values.** $\mu = 0.5$ and $a_\text{brake} = 3$ m/s² are
  placeholders for a dry road and a rider cornering with some margin.
- **Braking and cornering at once.** The grip limit and the braking limit are
  applied separately. In reality they share one friction budget, so braking
  hard while leaned over is not possible.
- **Banking and lean dynamics.** The road is taken as unbanked and the rider
  leans instantly.
- **Rolling resistance at rest.** $F_{rr}$ is applied at all speeds, including
  $v_b = 0$. It does not matter in the distance form, since it enters as $v_b F_{rr}$.
