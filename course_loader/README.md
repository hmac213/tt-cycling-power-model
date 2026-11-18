# Course loader

Turns a GPX track into a smooth description of the road: at every metre it
gives the incline angle $\theta(s)$, heading $\psi(s)$, curvature $\kappa(s)$,
elevation, and headwind $v_\text{wind}(s)$. GPX is the only input format.

```python
from course_loader import gpx

course = gpx.load_gpx("courses/rolling.gpx", wind_speed=3, wind_from_deg=300)
course.theta_at(1250.0)      # incline 1.25 km into the course
course.curvature             # curvature at every sample
```

## Why not just difference the GPS points

Slope and curvature are derivatives of position, and differentiating noisy
points amplifies the noise. On `rolling.gpx` (10 m point spacing, 1.5 m
position noise, 0.5 m elevation noise), differencing the raw points gives a
grade error 3 times larger than the grade itself, 650 m of climbing where the
truth is 191 m, and curvature that is pure noise. Averaging over coarse
segments hides this but also blurs real features and still gives no usable
curvature.

So the loader does not discretize the track. It fits one smooth curve to all
the points and differentiates that curve analytically.

## Pipeline

1. **Read** every `<trkpt>` (or `<rtept>`) with its `<ele>`.
2. **Project** latitude and longitude to local east/north metres on the WGS84
   ellipsoid, about the centre of the track.
3. **Clean.** Drop points within 0.5 m of the previous kept point, and
   parameterize the rest by cumulative chord length $u$.
4. **Estimate the noise.** Each point is compared with the straight line
   through its two neighbours. A smooth road barely leaves that line over one
   sample spacing, so the leftover is noise, and its median absolute deviation
   gives $\sigma_{xy}$ and $\sigma_\text{ele}$. Elevations rounded to whole
   metres or decimetres get at least the rounding error.
5. **Smooth.** Fit cubic smoothing splines $x(u)$, $y(u)$, $h(u)$. Each is the
   smoothest curve whose RMS misfit to the points equals the noise level
   (`scipy.interpolate.UnivariateSpline` with $s = N$ and weights $1/\sigma$).
   With $\sigma = 0$ the spline passes through every point.
6. **Differentiate** the splines exactly:

$$\theta = \arctan\frac{h'}{\sqrt{x'^2 + y'^2}}, \qquad \psi = \operatorname{atan2}(x', y'), \qquad \kappa = \frac{x'' y' - x' y''}{(x'^2 + y'^2)^{3/2}}$$

7. **Re-parameterize** by distance ridden $s$, the 3-D arc length of the smooth
   curve, and sample every 1 m. Linear interpolation between samples that
   close is effectively the continuous function.

On `rolling.gpx` this recovers grade to within 5% of its spread and curvature
to within 7%, and the course length to 9 m in 20 km (the raw points overstate
it by 630 m).

## Quantities (`course.Course`)

| Symbol | Field | Description | Units |
| --- | --- | --- | --- |
| $s$ | `distance` | Distance ridden from the start | m |
| $L$ | `length` | Course length | m |
| $h(s)$ | `elevation` | Elevation | m |
| $\theta(s)$ | `theta` | Incline angle, $\sin\theta = dh/ds$ | rad |
| $\psi(s)$ | `heading` | Compass bearing of travel (0 = north, unwrapped) | rad |
| $\kappa(s)$ | `curvature` | Horizontal curvature, positive turning right; radius is $1/\lvert\kappa\rvert$ | 1/m |
| | `lat`, `lon` | Position on the smoothed track | deg |
| $v_\text{wind}(s)$ | `headwind` | Wind component against the rider | m/s |
| $\sigma_{xy}$, $\sigma_\text{ele}$ | `sigma_xy`, `sigma_ele` | Noise levels used for smoothing | m |

`course.mean_curvature(window)` gives curvature averaged over a sliding
window, computed as heading change over distance. This is what the cornering
model uses, since heading is much less noise-sensitive than pointwise curvature.

## Wind

GPX has no wind, so it is supplied separately as a uniform wind vector:
`load_gpx(..., wind_speed=W, wind_from_deg=d)` or `course.with_wind(W, d)`,
where $d$ is the compass bearing the wind blows from. The headwind is its
component along the road,

$$v_\text{wind}(s) = W \cos\big(\psi(s) - d\big),$$

so it changes as the course turns.

## Loader settings

| Argument | Meaning | Default |
| --- | --- | --- |
| `sigma_xy` | Position noise [m]; `None` estimates it, 0 disables smoothing | `None` |
| `sigma_ele` | Elevation noise [m]; same conventions | `None` |
| `resolution` | Spacing of the output samples [m] | 1.0 |
| `min_spacing` | Points closer than this are dropped [m] | 0.5 |

## Assumptions

- **The rider follows the smoothed track.** No racing line across the road
  width.
- **Wind is uniform and steady.** One wind vector for the whole course and race.
- **No crosswinds.** Only the along-road component is kept.

## Ambiguities and gaps filled

- **How much to smooth.** Set by the noise estimate above, which assumes
  point-to-point independent noise. Real GPS error is partly correlated
  between neighbouring points, and that part cannot be estimated or removed
  this way. Override `sigma_xy` / `sigma_ele` if a track looks under- or
  over-smoothed.
- **Tight corners.** A corner shorter than a few track points cannot be
  resolved, whatever the smoothing. With 5 m spacing and 0.5 m noise, corner
  radii of 12–40 m come out within about 20%; with 1.5 m noise they can be off
  by a factor of two.
- **Elevation source.** GPS elevation also carries slow drift that smoothing
  cannot remove. Barometric or map-corrected elevation is better.
- **Demo courses.** No specific course is named in the model write-up, so
  the five files in `courses/` are synthetic
  (`python -m courses.make_demo_gpx`).
