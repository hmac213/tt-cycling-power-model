"""Small synthetic courses shared by the tests."""

import numpy as np

from course_loader import course as course_lib
from course_loader import gpx

# Size of a degree near latitude 34 N [m].
METRES_PER_DEG_LAT = 110_922.0
METRES_PER_DEG_LON = 92_385.0


def course_from_xy(
    east: np.ndarray, north: np.ndarray, elevation: np.ndarray, **kwargs
) -> course_lib.Course:
    """Builds a course from local east/north coordinates in metres."""
    return gpx.course_from_track(
        34.0 + north / METRES_PER_DEG_LAT,
        -118.5 + east / METRES_PER_DEG_LON,
        elevation,
        **kwargs,
    )


def straight_course(length: float, elevation_fn=None) -> course_lib.Course:
    """Builds an unsmoothed course heading due north."""
    north = np.linspace(0.0, length, 401)
    elevation = np.zeros_like(north)
    if elevation_fn is not None:
        elevation = elevation_fn(north)
    return course_from_xy(
        np.zeros_like(north), north, elevation, sigma_xy=0.0, sigma_ele=0.0
    )


def circle_course(radius: float) -> course_lib.Course:
    """Builds an unsmoothed clockwise circle that starts heading north."""
    angle = np.linspace(0.0, 2 * np.pi, 400)
    east = radius * (1 - np.cos(angle))
    north = radius * np.sin(angle)
    return course_from_xy(
        east, north, np.zeros_like(angle), sigma_xy=0.0, sigma_ele=0.0
    )


def corner_course(radius: float, leg: float) -> course_lib.Course:
    """Builds two flat straights joined by a 90 degree right-hand corner."""
    spacing = 2.0
    along = np.arange(0.0, 2 * leg + spacing, spacing)
    arc_length = radius * np.pi / 2
    heading = (np.pi / 2) * np.clip((along - leg) / arc_length, 0.0, 1.0)
    east = np.concatenate([[0.0], np.cumsum(spacing * np.sin(heading[:-1]))])
    north = np.concatenate([[0.0], np.cumsum(spacing * np.cos(heading[:-1]))])
    return course_from_xy(
        east, north, np.zeros_like(along), sigma_xy=0.0, sigma_ele=0.0
    )
