# Power model (two reserves: critical power with durability)

The classic Critical Power model gives the rider one rechargeable reserve
$W'$ above a fixed critical power $CP$. It fits efforts of roughly 2 to 20
minutes, and it says $CP$ can be held forever, which is false. This model
keeps the rechargeable reserve and adds a second, slow reserve that only
drains: the rider's **durability**. As it drains, critical power sinks from
the second lactate threshold LT2 towards the first, LT1.

Sources for every number and claim here are listed in
[../SOURCES.md](../SOURCES.md).

## State

| Symbol | Code name | Meaning | Units |
| --- | --- | --- | --- |
| $x$ | `deficit` | Deficit of the fast reserve, $x = 1 - B/W'$: 0 full, 1 empty | – |
| $F$ | `fatigue` | Fatigue, counted in seconds ridden at LT2. Never recovers. | s |
| $E$ | `work` | Mechanical work done so far | J |

The rider starts fresh: $x = 0$, $F = 0$, $E = 0$.

## Equations

**Intensity.** Where the power sits between the two thresholds:

$$i = \frac{P - LT1}{LT2 - LT1} \qquad (0 \text{ at } LT1,\ 1 \text{ at } LT2).$$

**Slow states.** Fatigue builds with intensity, faster than in proportion,
and work is the integral of power:

$$\frac{dF}{dt} = \max(i, 0)^{\gamma}, \qquad \frac{dE}{dt} = P.$$

**Durability reserve.** The share of the span between LT1 and LT2 that the
rider's critical power still covers:

$$R(F) = \exp\!\left(-\left(F/\tau_F\right)^2\right), \qquad CP = LT1 + (LT2 - LT1)\,R(F).$$

**Capacity of the fast reserve.** It shrinks with total work done:

$$W' = W'_0 \exp(-E / E_W).$$

**Fast reserve.** $B = (1 - x)\,W'$ is measured against the current $CP$
and $W'$:

| Regime | Condition | $dx/dt$ |
| --- | --- | --- |
| Expenditure | $P > CP$ | $(P - CP)/W'$ |
| Neutral | $P = CP$ | $0$ |
| Recovery | $P < CP$ | $-\alpha\,(CP - P)\,x^{\beta}/W'$ |

The rider is exhausted when $x = 1$ ($B = 0$), and the solver requires
$x \le 1$ at all times. The state is the fraction $x$, not the joules $B$,
so when $W'$ shrinks the stored reserve shrinks in proportion.

With $\tau_F = E_W = \infty$ this is exactly the classic model, with
$dB/dt = -(P - CP)$ above $CP$ and the Skiba recovery law below it.

## Why this shape

- **$CP$ is a real anchor.** It is the boundary above which the body cannot
  reach a steady state, so the model is built on it. We take $CP_0 = LT2$.
- **LT1 is the floor and the onset.** Below LT1 fatigue does not build, and
  a fully fatigued rider can still hold LT1. This makes $R$ a second
  reserve with a physical reading: it is something a critical-power test in
  the middle of a ride measures directly (Clark et al. 2019 did exactly
  that).
- **Fatigue is intensity-weighted.** Work above $CP$ lowers $CP$ far more
  than the same work below it (Mateo-March et al. 2024), so plain kilojoules
  are not enough.
- **$R$ starts flat.** In both data sets the loss of $CP$ accelerates:
  nothing after 40 and 80 minutes and 9% after 2 hours (Clark et al. 2019),
  and 2.2%, 6.1%, 16.2% after one, two, three doses of hard work
  (Mateo-March et al. 2024). A loss that grows with the square of the dose
  fits both, which is what $\exp(-(F/\tau_F)^2)$ does for small $F$.
- **$W'$ follows work, not intensity.** In Clark et al. (2019) $W'$ fell
  steadily from the start (10%, 18%, 23% after 40, 80, 120 minutes), was not
  rescued by carbohydrate, and tracked glycogen loss. In Mateo-March et al.
  (2024) $CP$ fell 16% while the gap between 5-minute power and $CP$ hardly
  moved. The riders in the first study had done twice the work of the top
  dose in the second. Tying $W'$ to total work is the one rule that agrees
  with both.
- **Short races are barely affected.** $F$ stays far below $\tau_F$, so
  $R \approx 1$.

## Parameters (`RiderParams`)

| Symbol | Field | Description | Units | Default |
| --- | --- | --- | --- | --- |
| $LT1$ | `lt1` | First lactate threshold | W | 225 |
| $LT2$ | `lt2` | Second lactate threshold, taken as fresh critical power $CP_0$ | W | 300 |
| $W'_0$ | `w_prime` | Work capacity above $CP$ when fresh | J | 20 000 |
| $P_\text{max}$ | `p_max` | Cap on instantaneous power | W | 900 |
| $\alpha$ | `alpha` | Recovery rate coefficient | – | 1 |
| $\beta$ | `beta` | Recovery saturation exponent | – | 1 |
| $\gamma$ | `fatigue_exponent` | How steeply fatigue grows with intensity | – | 1.7 |
| $\tau_F$ | `fatigue_time` | Fatigue at which $CP$ has lost 63% of the span $LT2 - LT1$ | s | 3000 |
| $E_W$ | `work_capacity` | Work at which $W'$ has fallen to 37% | J | 4.3 MJ |

`RiderParams.cp` returns `lt2`. The defaults describe a strong amateur. A
rider profile (`profiles/`) overrides all of them, and sets $E_W$ as
57.4 kJ per kilogram of body mass.

### Where $\gamma$, $\tau_F$ and $E_W$ come from

Two studies give one point each, at very different intensities, so together
they fix $\gamma$ and $\tau_F$.

| Study | Riding | Intensity $i$ | Loss of $CP$ |
| --- | --- | --- | --- |
| Clark et al. 2019, with carbohydrate | 2 h at 164 W (threshold 132 W, $CP$ 260 W) | 0.25 | 260 → 254 W |
| Clark et al. 2019, water only | same | 0.25 | 260 → 236 W |
| Mateo-March et al. 2024 | 7.5 kJ/kg above $CP$ | about 1.9 | 408 → 342 W |

- **$\gamma \approx 1.7$, $\tau_F \approx 3000$ s** match the carbohydrate
  case of Clark together with Mateo-March. The water-only case gives
  $\gamma \approx 1.4$, $\tau_F \approx 2300$ s. We use the fed values,
  since anyone racing for over an hour eats.
- **The exponent is uncertain.** Mateo-March et al. do not report how far
  above $CP$ the hard work was. Assuming 450 to 600 W gives $\gamma$ from
  1.5 to 2.0. For the same reason, LT1 for their riders is assumed to be
  75% of $CP$.
- **$E_W = 57.4$ kJ/kg** makes $W'$ fall 23% after the 14.9 kJ/kg of Clark's
  2-hour ride. The same rule gives 8% and 16% at 40 and 80 minutes, against
  the measured 10% and 18%.
- **Check.** With the defaults, a fresh rider lasts about 30 minutes at
  $CP$. The classic model says forever.

These are population values from two small studies. Fit them to the rider
when long best efforts are available (next section).

## Fitting a rider (`calibrate.py`)

The model predicts a rider's power-duration curve, the best constant power
for each duration (`cp_model.power_duration_curve`). `calibrate.fit` chooses
parameters so that curve passes through measured best efforts.

| Efforts available | Fits |
| --- | --- |
| 3 to 20 min | `lt2` and `w_prime` |
| One of 1 h or more | `fatigue_time` |
| Two of 1 h or more | `fatigue_time` and `fatigue_exponent` |

Fitting through the model matters. A critical power read off a plain
$W = CP\,t + W'$ fit already contains some of the fatigue that this model
adds separately, so using it as $CP_0$ would count that fatigue twice. For
the men's time trialist, the plain fit gives 400 W and the fit through the
model gives 412 W.

LT1, LT2 and the sprint maximum are all powers. The model also needs $W'_0$
(joules) and $\tau_F$ (seconds), and no combination of three powers gives a
time, so at least one short and one long best effort are needed on top of
the thresholds.

## Functions (`cp_model.py`)

- `intensity`, `fatigue_rate`, `durability`, `critical_power`,
  `reserve_capacity`: the pieces above.
- `step_deficit(deficit, power, duration, cp, capacity, rider)`: exact
  update of $x$ over an interval at constant power, with $CP$ and $W'$ held
  fixed. With $k = \alpha(CP - P)/W'$, recovery solves $\dot x = -k x^\beta$,
  so $x(t) = x_0 e^{-kt}$ when $\beta = 1$ and
  $x(t) = \big(x_0^{1-\beta} - (1-\beta)kt\big)^{1/(1-\beta)}$ otherwise.
- `step_state(deficit, fatigue, work, power, duration, rider)`: advances all
  three states, taking $CP$ and $W'$ from the start of the interval.
- `time_to_exhaustion(power, rider)`: how long a fresh rider lasts at a
  constant power.
- `power_duration_curve(durations, rider)`: the best constant power for each
  duration.

## Assumptions

- **$CP_0 = LT2$.** A lactate-derived LT2 usually sits a little below
  critical power and depends on the laboratory's definition.
- **The rider is fed**, at 60 g of carbohydrate per hour or more.
- **Fatigue never recovers during the race.**
- **Nothing below LT1 is tiring.**
- **Expenditure is linear**: every joule above $CP$ costs one joule of $B$.
- **$\alpha$ is at most 1.** Otherwise alternating hard and easy efforts
  would create energy from nothing.

## Limitations

- **About 6 hours at most.** Beyond that, performance is limited by things
  this model leaves out: fuel intake against burn rate, heat, hydration,
  stops, and sleep. Riding below LT1 is free here, which is wrong for a
  12 or 24 hour event.
- **$F$ is descriptive, not a fuel tank.** In Clark et al. (2019),
  carbohydrate preserved $CP$ without changing glycogen depletion, and the
  change in glycogen did not correlate with the change in $CP$. So $F$ is
  anchored by measured losses of $CP$, not by one substrate.
- **Thin evidence.** $\gamma$, $\tau_F$ and $E_W$ rest on two studies, one
  of 16 trained non-elite athletes in a laboratory and one of 17
  professionals in the field. The evidence that intensity matters is not
  unanimous.
- **Slow states are updated once per grid step.** $CP$ and $W'$ are held
  fixed within a step of a few seconds, over which they change by a few
  watts at most, and only during a sprint.
- **The corner in $\max(i, 0)$ is rounded** over 1% of the threshold span,
  so that the optimizer sees smooth derivatives. Riding at LT1 therefore
  adds about $10^{-4}$ seconds of fatigue per second.
- **Maximum power is a constant cap** and does not shrink as $B$ drains.
