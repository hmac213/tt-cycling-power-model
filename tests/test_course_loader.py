"""Tests of the GPX loader.

    python -m unittest discover tests
"""

import pathlib
import tempfile
import unittest

import numpy as np

from course_loader import course as course_lib
from course_loader import gpx
from tests import helpers


class GpxTest(unittest.TestCase):

    def test_round_trip_of_a_steady_ramp(self):
        # 2 km at 5%: road length and slope angle must come out right.
        north = np.linspace(0.0, 2_000.0, 201)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ramp.gpx"
            gpx.write_gpx(
                path,
                34.0 + north / helpers.METRES_PER_DEG_LAT,
                np.full(north.size, -118.5),
                0.05 * north,
            )
            course = gpx.load_gpx(path, sigma_xy=0.0, sigma_ele=0.0)
        self.assertEqual(course.name, "ramp")
        expected_length = 2_000.0 * np.hypot(1.0, 0.05)
        self.assertAlmostEqual(course.length, expected_length, delta=1.0)
        np.testing.assert_allclose(course.theta, np.arctan(0.05), atol=1e-4)
        np.testing.assert_allclose(course.heading, 0.0, atol=1e-6)
        np.testing.assert_allclose(course.curvature, 0.0, atol=1e-8)
        self.assertAlmostEqual(course.elevation[-1], 100.0, delta=1e-2)

    def test_file_without_points_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "empty.gpx"
            path.write_text("<gpx></gpx>")
            with self.assertRaises(ValueError):
                gpx.read_gpx_points(path)

    def test_curvature_and_heading_of_a_circle(self):
        course = helpers.circle_course(200.0)
        interior = slice(20, -20)
        np.testing.assert_allclose(
            course.curvature[interior], 1 / 200.0, rtol=0.01
        )
        np.testing.assert_allclose(
            course.mean_curvature(20.0)[interior], 1 / 200.0, rtol=0.01
        )
        self.assertAlmostEqual(course.length, 2 * np.pi * 200.0, delta=2.0)
        turned = course.heading[-1] - course.heading[0]
        self.assertAlmostEqual(turned, 2 * np.pi, delta=0.02)

    def test_smoothing_recovers_slope_and_curvature_from_noise(self):
        rng = np.random.default_rng(0)
        north = np.linspace(0.0, 5_000.0, 501)
        east = 300.0 * np.sin(north / 400.0)
        elevation = 40.0 * np.sin(north / 500.0)
        noisy_east = east + rng.normal(0.0, 1.5, north.size)
        noisy_north = north + rng.normal(0.0, 1.5, north.size)
        noisy_elevation = elevation + rng.normal(0.0, 0.5, north.size)

        clean = helpers.course_from_xy(
            east, north, elevation, sigma_xy=0.0, sigma_ele=0.0
        )
        raw = helpers.course_from_xy(
            noisy_east, noisy_north, noisy_elevation,
            sigma_xy=0.0, sigma_ele=0.0,
        )
        smooth = helpers.course_from_xy(
            noisy_east, noisy_north, noisy_elevation
        )

        def rms_error(course: course_lib.Course, field: str) -> float:
            fraction = np.linspace(0.02, 0.98, 500)
            got = np.interp(
                fraction, course.distance / course.length,
                getattr(course, field),
            )
            want = np.interp(
                fraction, clean.distance / clean.length,
                getattr(clean, field),
            )
            return float(np.sqrt(np.mean((got - want) ** 2)))

        # The noise levels are estimated from the data.
        self.assertAlmostEqual(smooth.sigma_xy, 1.5, delta=0.3)
        self.assertAlmostEqual(smooth.sigma_ele, 0.5, delta=0.1)
        self.assertLess(
            rms_error(smooth, "theta"), 0.2 * rms_error(raw, "theta")
        )
        self.assertLess(rms_error(smooth, "theta"), 0.2 * clean.theta.std())
        self.assertLess(
            rms_error(smooth, "curvature"), 0.05 * rms_error(raw, "curvature")
        )
        # Noise inflates the raw path length; smoothing removes that.
        self.assertLess(
            abs(smooth.length - clean.length), 0.002 * clean.length
        )
        self.assertGreater(
            abs(raw.length - clean.length),
            5 * abs(smooth.length - clean.length),
        )

    def test_headwind_follows_heading(self):
        course = helpers.circle_course(200.0).with_wind(5.0, from_deg=0.0)
        quarter = course.length / 4
        # North is a full headwind, east a pure crosswind, south a tailwind.
        self.assertAlmostEqual(float(course.wind_at(0.0)), 5.0, delta=0.05)
        self.assertAlmostEqual(float(course.wind_at(quarter)), 0.0, delta=0.05)
        self.assertAlmostEqual(
            float(course.wind_at(2 * quarter)), -5.0, delta=0.05
        )


if __name__ == "__main__":
    unittest.main()
