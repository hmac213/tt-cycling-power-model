"""Course representation: a smooth road sampled densely along its length."""

import dataclasses

import numpy as np
from numpy import typing as npt


@dataclasses.dataclass(frozen=True)
class Course:
    """A course as dense, uniformly spaced samples of a smooth curve.

    The samples come from evaluating a smoothing-spline fit of the GPX track
    (see `gpx.py`), so slope, heading, and curvature are exact derivatives of
    that fit and not finite differences of GPS points. They are spaced closely
    enough (1 m by default) that linear interpolation between them is, for
    practical purposes, the continuous function.

    Attributes:
        distance: Distance ridden along the road from the start, s [m].
        elevation: Height [m].
        theta: Incline angle [rad], with sin(theta) = d(elevation)/ds.
        heading: Compass bearing of travel [rad], unwrapped; 0 is north and
            pi/2 is east.
        curvature: Horizontal path curvature [1/m]; positive when turning
            right. The corner radius is 1/|curvature|.
        lat: Latitude [deg].
        lon: Longitude [deg].
        headwind: Wind component opposing the rider [m/s]; negative is a
            tailwind.
        name: Label for the course.
        wind_speed: Speed of the uniform wind applied [m/s].
        wind_from_deg: Compass bearing the wind blows from [deg].
        sigma_xy: Position noise level the track was smoothed with [m].
        sigma_ele: Elevation noise level the track was smoothed with [m].
    """

    distance: np.ndarray
    elevation: np.ndarray
    theta: np.ndarray
    heading: np.ndarray
    curvature: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    headwind: np.ndarray
    name: str = "course"
    wind_speed: float = 0.0
    wind_from_deg: float = 0.0
    sigma_xy: float = 0.0
    sigma_ele: float = 0.0

    @property
    def length(self) -> float:
        """Total course distance L [m]."""
        return float(self.distance[-1])

    @property
    def total_climb(self) -> float:
        """Sum of all elevation gained [m]."""
        return float(np.clip(np.diff(self.elevation), 0.0, None).sum())

    def elevation_at(self, distance: npt.ArrayLike) -> np.ndarray:
        """Returns the elevation [m] at the given distances [m]."""
        return np.interp(distance, self.distance, self.elevation)

    def theta_at(self, distance: npt.ArrayLike) -> np.ndarray:
        """Returns the incline angle [rad] at the given distances [m]."""
        return np.interp(distance, self.distance, self.theta)

    def heading_at(self, distance: npt.ArrayLike) -> np.ndarray:
        """Returns the heading [rad] at the given distances [m]."""
        return np.interp(distance, self.distance, self.heading)

    def curvature_at(self, distance: npt.ArrayLike) -> np.ndarray:
        """Returns the curvature [1/m] at the given distances [m]."""
        return np.interp(distance, self.distance, self.curvature)

    def wind_at(self, distance: npt.ArrayLike) -> np.ndarray:
        """Returns the headwind [m/s] at the given distances [m]."""
        return np.interp(distance, self.distance, self.headwind)

    def mean_curvature(self, window: float) -> np.ndarray:
        """Computes the curvature averaged over a sliding window.

        The average over [s - window/2, s + window/2] equals the change in
        heading across the window divided by its length. Heading is far less
        sensitive to GPS noise than pointwise curvature, so this is the
        quantity to use for cornering limits.

        Args:
            window: Averaging length [m]. Zero returns pointwise curvature.

        Returns:
            Mean curvature [1/m] at every sample of the course.
        """
        if window <= 0:
            return self.curvature
        ahead = np.minimum(self.distance + 0.5 * window, self.length)
        behind = np.maximum(self.distance - 0.5 * window, 0.0)
        turned = self.heading_at(ahead) - self.heading_at(behind)
        return turned / (ahead - behind)

    def with_wind(self, speed: float, from_deg: float) -> "Course":
        """Applies a uniform wind to the course.

        The headwind at each point is the wind's component along the
        direction of travel there, so it changes as the road turns.

        Args:
            speed: Wind speed [m/s].
            from_deg: Compass bearing the wind blows from [deg]; 0 is a wind
                from the north.

        Returns:
            A copy of the course with `headwind` set accordingly.
        """
        headwind = speed * np.cos(self.heading - np.radians(from_deg))
        return dataclasses.replace(
            self,
            headwind=headwind,
            wind_speed=float(speed),
            wind_from_deg=float(from_deg),
        )
