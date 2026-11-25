# Extending the model to a team time trial

In a team time trial (TTT) six riders from one team ride together and take
turns at the front. The team's time is taken when its **fourth** rider
crosses the line, so two riders may be used up and dropped before the finish.
This note sets out how the individual model extends to that race. It is a
design for the extension, plus one back-of-envelope calculation; the code
does not solve the full TTT yet.

## What changes

**1. Drag depends on position in the line.** A rider sitting in the wheel of
a teammate has much less air resistance. Blocken et al. (2018) simulated
pacelines of up to nine riders: the second rider saves about 36% of the
aerodynamic drag, the leader also gains a few percent from the riders behind,
and in a line of 7-9 riders the average drag is about half that of a rider
alone. Write the drag of rider $i$ in position $j$ as

$$F_{\text{air},i} = \tfrac12 \rho\, C_dA_i\, d_j\, (v + v_\text{wind})\lvert v + v_\text{wind}\rvert,$$

with drag factors $d_1 \approx 0.975$ (leader), $d_2 \approx 0.64$, and
$d_3, \dots, d_6 \approx 0.55, 0.50, 0.48, 0.47$. The values after the
second position are read approximately from the trend Blocken et al. report
and should be replaced with values for the actual spacing.

**2. One speed, six reserves.** The riders stay together, so there is a
single speed $v(s)$ but each rider has their own reserve $B_i(s)$, governed
by the same CP/W′ law with their own $CP_i$ and $W'_i$. Rider $i$'s power is
whatever it takes to hold the group's speed from their position:

$$P_i = v \left( F_{\text{air},i} + F_{rr,i} + F_{\text{grav},i} \right) + m_i v \frac{dv}{dt}.$$

**3. New decisions.** Besides the speed profile, the team chooses

* the rotation order and how long each rider stays at the front (their
  *pull*), which can differ by rider and by terrain (shorter pulls for the
  weaker riders, longer ones for the strongest, short pulls on climbs where
  drafting helps less);
* when, if ever, riders 5 and 6 are released. Once released, a rider no longer
  constrains the group, so a rider who will be dropped should spend all of
  their W′ at the front first.

**4. New objective.** Minimize the time at which the fourth rider finishes,
subject to $B_i \ge 0$ for every rider still in the group.

## How to solve it

The dynamic program cannot carry six reserves as states (60⁶ grid points).
Two practical approaches:

* **Decompose.** For a given rotation plan (pull lengths and release points),
  every rider's power is a known function of the group speed. Fix the plan,
  optimize the group speed $v(s)$ with the collocation solver, which handles
  any number of reserve states since its size grows only linearly, and
  search over rotation plans in an outer loop (a small grid or a
  derivative-free search).
* **Equal-share approximation.** If all riders are alike and take equal pulls,
  each rider's average drag factor over a rotation is the mean
  $\bar d = \frac1n \sum_j d_j$. A team of identical riders then behaves like
  one rider with drag area $\bar d\, C_dA$, and the existing solver applies
  unchanged. The W′ dynamics within a rotation (spending at the front,
  recovering behind) are averaged out, which is reasonable when pulls are
  short compared with the time it takes to empty W′.

## Back-of-envelope result

Using the equal-share approximation with six copies of our TT specialist on
flat, windless roads at sea level ($\rho = 1.20$ kg/m³, $\bar d \approx 0.60$):

| Group | Average drag factor | Steady speed at CP |
| --- | --- | --- |
| Rider alone | 1.00 | 50.8 km/h |
| 4 riders | 0.67 | 57.7 km/h |
| 6 riders | 0.60 | 59.8 km/h |

At 59.8 km/h the leader needs about 620 W of pedal power, well above the
specialist's CP of 400 W, so every pull drains W′ and every spell in the line
refills it. That is exactly the spend-and-recover balance the CP/W′ model
describes, and it means the pull length is limited by W′. A 220 W excess
over CP empties 31.8 kJ in about 2.4 minutes, so pulls should be well under
two minutes.
Dropping to four riders late in the race costs about 2 km/h. Riders 5 and 6
should therefore stay as long as they can contribute, and spend everything
they have left in long final pulls before they are released.

## What this would need to be complete

* Drag factors for the actual rider spacing, and for crosswinds, which
  break up a straight paceline.
* A model of the transitions: the rider leaving the front briefly rides in
  the wind before rejoining at the back.
* Different rider profiles within one team, which is where the choice of pull
  lengths matters most.

## Reference

Blocken, B., Toparlar, Y., van Druenen, T., Andrianne, T. (2018).
Aerodynamic drag in cycling team time trials. *Journal of Wind Engineering
and Industrial Aerodynamics*, 182, 128-145.
