# Power model (Critical Power / W′ stamina)

$B(t)$ is the work capacity above Critical Power that the rider has left,
with $0 \le B(t) \le W'$ and $B(0) = W'$. It changes in three regimes:

| Regime | Condition | $dB/dt$ |
| --- | --- | --- |
| Expenditure | $P > CP$ | $-(P - CP)$ |
| Neutral | $P = CP$ | $0$ |
| Recovery | $P < CP$ | $\alpha\,(CP - P)\,(1 - B/W')^{\beta}$ |

The rider is exhausted when $B = 0$, and the solver requires $B \ge 0$ at all times.
At constant power $P > CP$ this gives the classic hyperbolic relation
$t_\text{exhaustion} = W' / (P - CP)$ (`cp_model.time_to_exhaustion`).

## Parameters (`RiderParams`)

| Symbol | Field | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $CP$ | `cp` | Critical power (sustainable aerobic threshold) | W | 300 |
| $W'$ | `w_prime` | Anaerobic work capacity above CP | J | 20 000 |
| $P_\text{max}$ | `p_max` | Cap on instantaneous power | W | 900 |
| $\alpha$ | `alpha` | Recovery rate coefficient | – | 1 |
| $\beta$ | `beta` | Recovery saturation exponent | – | 1 |

The defaults describe a strong amateur. Typical ranges are $CP$ 200–450 W and
$W'$ 10–30 kJ. A rider profile (`profiles/`) overrides all five.

## Functions

- `cp_model.reserve_rate(power, reserve, rider)`: the right-hand side $dB/dt$ above.
- `cp_model.step_reserve(reserve, power, duration, rider)`: exact update of
  $B$ over a time interval at constant power. With $x = 1 - B/W'$ and $k = \alpha(CP - P)/W'$, recovery
  solves $\dot x = -k x^\beta$, so $x(t) = x_0 e^{-kt}$ when $\beta = 1$ and
  $x(t) = \big(x_0^{1-\beta} - (1-\beta)kt\big)^{1/(1-\beta)}$ otherwise.
- `cp_model.time_to_exhaustion(power, rider)`.

## Assumptions

- $CP$ and $W'$ are fixed for the whole race (no fatigue drift, no fueling effects).
- Expenditure is linear: every joule above CP costs one joule of $B$, no matter
  how far above CP the rider is.
- Riding at exactly CP can be held forever.

## Ambiguities and gaps filled

- **Form of the recovery law.** The write-up gives recovery as
  "$\alpha(CP - P)\,\beta(B/W')$ where $\alpha$ and $\beta$ are weighting
  coefficients", which does not pin down a formula. Read literally as a product
  with $B/W'$, recovery would be *fastest when full and zero when empty*, so an
  exhausted rider could never recover and $B$ could grow past $W'$. The baseline
  instead uses $\alpha\,(CP - P)\,(1 - B/W')^{\beta}$: recovery is fastest when
  empty and stops at $B = W'$, so the bound $B \le W'$ holds on its own. With
  $\alpha = \beta = 1$ this is the standard Skiba differential $W'_\text{bal}$ model.
  **This is the main modeling choice to confirm.** Swapping in a different law
  requires changing `reserve_rate`, `step_reserve`, and the matching update in
  `solver/collocation.py`.
- **$\alpha$ above 1.** Recovery would then return more than a joule per joule
  when the reserve is nearly empty, and alternating hard and easy efforts
  would create energy from nothing. Keep $\alpha \le 1$.
- **Maximum power.** The write-up only has $P \ge 0$. Without a cap, the CP model
  allows an arbitrarily large power for an arbitrarily short time, so the
  baseline adds $P \le P_\text{max}$ (900 W). The cap is constant and does not
  shrink as $B$ drains.
- **Values of $\alpha$, $\beta$, $CP$, $W'$.** Not specified, so the defaults
  above are placeholders to be fit to a rider.
- **Braking and coasting.** While coasting or braking the rider is at $P = 0$,
  so the reserve recovers at the $P = 0$ rate.
- **At $P = CP$.** The code groups $P = CP$ with expenditure, which gives
  $dB/dt = 0$ either way.
