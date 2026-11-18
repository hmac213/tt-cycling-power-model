"""Generates the synthetic demo GPX files in this folder.

    python -m courses.make_demo_gpx

These stand in for real courses. `climb.gpx` is steep enough for a light
rider to beat a more powerful, more aerodynamic one. `rolling.gpx` and
`technical.gpx` include simulated GPS noise so that the loader's smoothing
has something to do.
"""

import pathlib

import numpy as np

from course_loader import gpx

_OUTPUT_DIR = pathlib.Path(__file__).resolve().parent

# Origin of every demo course, and the local size of a degree there.
_ORIGIN_LAT = 34.0
_ORIGIN_LON = -118.5
_METRES_PER_DEG_LAT = 110_922.0
_METRES_PER_DEG_LON = 92_385.0

# Corners of the technical course: (start [m], turn [deg], radius [m]).
_TECHNICAL_CORNERS = (
    (1_200, 90, 25),
    (2_000, -90, 18),
    (3_600, 180, 12),
    (4_400, -60, 40),
    (5_600, 90, 15),
    (6_400, -90, 30),
)


def _bump(fraction: np.ndarray, centre: float, width: float) -> np.ndarray:
    """Returns a unit-height Gaussian bump over the course fraction."""
    return np.exp(-0.5 * ((fraction - centre) / width) ** 2)


def make_track(
    heading: np.ndarray,
    elevation: np.ndarray,
    spacing: float,
    noise_xy: float = 0.0,
    noise_ele: float = 0.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Lays out track points along a path of given heading and elevation.

    Args:
        heading: Compass bearing of travel at each point [rad].
        elevation: Elevation at each point [m].
        spacing: Horizontal distance between consecutive points [m].
        noise_xy: Standard deviation of simulated position noise [m].
        noise_ele: Standard deviation of simulated elevation noise [m].
        seed: Seed of the noise generator.

    Returns:
        Arrays (lat [deg], lon [deg], elevation [m]).
    """
    east = np.concatenate([[0.0], np.cumsum(spacing * np.sin(heading[:-1]))])
    north = np.concatenate([[0.0], np.cumsum(spacing * np.cos(heading[:-1]))])
    rng = np.random.default_rng(seed)
    east = east + rng.normal(0.0, noise_xy, east.size)
    north = north + rng.normal(0.0, noise_xy, north.size)
    elevation = elevation + rng.normal(0.0, noise_ele, east.size)
    lat = _ORIGIN_LAT + north / _METRES_PER_DEG_LAT
    lon = _ORIGIN_LON + east / _METRES_PER_DEG_LON
    return lat, lon, elevation


def _write_flat() -> None:
    """Writes flat.gpx: 10 km due north at sea level."""
    zeros = np.zeros(1001)
    gpx.write_gpx(
        _OUTPUT_DIR / "flat.gpx", *make_track(zeros, zeros, 10.0), name="flat"
    )


def _write_hill() -> None:
    """Writes hill.gpx: 10 km due north over one 100 m hill."""
    fraction = np.linspace(0.0, 1.0, 1001)
    elevation = 100.0 * _bump(fraction, 0.5, 0.15)
    track = make_track(np.zeros_like(fraction), elevation, 10.0)
    gpx.write_gpx(_OUTPUT_DIR / "hill.gpx", *track, name="hill")


def _write_rolling() -> None:
    """Writes rolling.gpx: 20 km of climbs, rollers, and sweeping bends."""
    fraction = np.linspace(0.0, 1.0, 2001)
    elevation = (
        120.0 * _bump(fraction, 0.30, 0.10)
        + 60.0 * _bump(fraction, 0.70, 0.05)
        + 8.0 * np.sin(2 * np.pi * 6 * fraction) * fraction
    )
    heading = (
        1.2 * np.sin(2 * np.pi * 1.5 * fraction)
        + 0.5 * np.sin(2 * np.pi * 7 * fraction)
        + np.pi * fraction
    )
    track = make_track(
        heading, elevation, 10.0, noise_xy=1.5, noise_ele=0.5, seed=142
    )
    gpx.write_gpx(_OUTPUT_DIR / "rolling.gpx", *track, name="rolling")


def _write_technical() -> None:
    """Writes technical.gpx: 8 km with tight corners and a downhill hairpin."""
    spacing = 5.0
    along = np.arange(0.0, 8_000.0 + spacing, spacing)
    heading = np.zeros_like(along)
    for start, turn_deg, radius in _TECHNICAL_CORNERS:
        arc_length = radius * np.radians(abs(turn_deg))
        progress = np.clip((along - start) / arc_length, 0.0, 1.0)
        heading += np.radians(turn_deg) * progress
    fraction = along / along[-1]
    elevation = (
        60.0 * _bump(fraction, 0.30, 0.08) + 25.0 * _bump(fraction, 0.75, 0.06)
    )
    track = make_track(
        heading, elevation, spacing, noise_xy=0.5, noise_ele=0.3, seed=7
    )
    gpx.write_gpx(_OUTPUT_DIR / "technical.gpx", *track, name="technical")


def _write_climb() -> None:
    """Writes climb.gpx: 6 km uphill at 8% with sweeping bends."""
    spacing = 10.0
    fraction = np.linspace(0.0, 1.0, 601)
    # Ease the grade in and out over the first and last 5% of the course.
    grade = 0.08 * np.clip(np.minimum(fraction, 1 - fraction) / 0.05, 0, 1)
    elevation = np.concatenate([[0.0], np.cumsum(spacing * grade[:-1])])
    heading = 0.6 * np.sin(2 * np.pi * 3 * fraction)
    track = make_track(heading, elevation, spacing)
    gpx.write_gpx(_OUTPUT_DIR / "climb.gpx", *track, name="climb")


def main() -> None:
    _write_flat()
    _write_climb()
    _write_hill()
    _write_rolling()
    _write_technical()


if __name__ == "__main__":
    main()
