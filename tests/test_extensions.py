"""Tests of the extensions: fatigue, imperfect execution, race courses."""

import dataclasses
import pathlib
import unittest

import numpy as np

from course_loader import gpx
from physics_model import params as physics_params
from power_model import cp_model
from power_model import params as rider_params
from profiles import rider as rider_profiles
from solver import execution
from solver import optimize
from solver import simulate
from tests import helpers

_PHYSICS = physics_params.PhysicsParams()
_RIDER = rider_params.RiderParams()
_COURSES = pathlib.Path(__file__).resolve().parent.parent / "courses"


class FatigueTest(unittest.TestCase):

    def test_factor_is_one_before_onset_and_declines_after(self):
        rider = dataclasses.replace(_RIDER, fatigue_rate=0.07, fatigue_onset=1800.0)
        factor = cp_model.fatigue_factor([0.0, 1800.0, 3600.0], rider)
        np.testing.assert_allclose(factor[:2], 1.0)
        self.assertAlmostEqual(factor[2], 1.0 - 0.07 * np.log(2.0))

    def test_no_fatigue_leaves_results_unchanged(self):
        course = helpers.straight_course(3_000.0)
        plain = optimize.constant_power_ride(course, _PHYSICS, _RIDER)
        zero = dataclasses.replace(_RIDER, fatigue_rate=0.0)
        same = optimize.constant_power_ride(course, _PHYSICS, zero)
        self.assertAlmostEqual(plain.total_time, same.total_time)

    def test_fatigue_slows_the_constant_power_ride(self):
        course = helpers.straight_course(6_000.0)
        tired = dataclasses.replace(_RIDER, fatigue_rate=0.1, fatigue_onset=200.0)
        fresh = optimize.constant_power_ride(course, _PHYSICS, _RIDER)
        slow = optimize.constant_power_ride(course, _PHYSICS, tired)
        self.assertGreater(slow.total_time, fresh.total_time)

    def test_at_step_scales_cp(self):
        rider = dataclasses.replace(_RIDER, cp_scale=(1.0, 0.9))
        self.assertEqual(cp_model.at_step(rider, 1).cp, 0.9 * _RIDER.cp)
        self.assertIsNone(cp_model.at_step(rider, 1).cp_scale)


class ExecutionTest(unittest.TestCase):

    def setUp(self):
        self.course = helpers.straight_course(4_000.0)
        self.grid = simulate.build_grid(self.course, _PHYSICS)

    def test_exact_ride_matches_simulator(self):
        plan = np.full(self.grid.num_steps, 320.0)
        exact = simulate.simulate(plan, self.grid, _PHYSICS, _RIDER)
        ride = execution.ride_plan(plan, self.grid, _PHYSICS, _RIDER)
        self.assertAlmostEqual(ride.total_time[0], exact.total_time, places=6)

    def test_overcooked_rider_never_goes_negative(self):
        plan = np.full(self.grid.num_steps, 600.0)
        ride = execution.ride_plan(plan, self.grid, _PHYSICS, _RIDER)
        self.assertGreaterEqual(ride.reserve.min(), 0.0)
        self.assertGreater(ride.exhausted[0], 0.0)

    def test_noise_statistics(self):
        errors = execution.power_noise(2000, 50, 20.0, 0.05, bias=0.02, seed=3)
        self.assertAlmostEqual(errors.mean(), 0.02, delta=0.005)
        self.assertAlmostEqual(errors.std(), 0.05, delta=0.005)


class RaceCourseTest(unittest.TestCase):

    def _gap(self, course):
        dlat = np.radians(course.lat[-1] - course.lat[0])
        dlon = np.radians(course.lon[-1] - course.lon[0]) * np.cos(
            np.radians(course.lat[0]))
        return 6_371_000.0 * np.hypot(dlat, dlon)

    def test_published_lengths(self):
        for name, length in (("tokyo_2021_men", 44_200), ("tokyo_2021_women", 22_100),
                             ("flanders_2021_men", 43_300),
                             ("flanders_2021_women", 30_300)):
            course = gpx.load_gpx(_COURSES / f"{name}.gpx")
            self.assertAlmostEqual(course.length, length, delta=0.005 * length)

    def test_custom_loop_meets_the_requirements(self):
        course = gpx.load_gpx(_COURSES / "custom_loop.gpx")
        self.assertLess(self._gap(course), 50.0)  # finish near the start
        self.assertGreater(np.tan(np.abs(course.theta)).max(), 0.05)
        # At least four sharp corners: separate stretches tighter than 30 m.
        sharp = np.abs(course.mean_curvature(20.0)) > 1 / 30.0
        self.assertGreaterEqual(np.sum(np.diff(sharp.astype(int)) == 1), 4)

    def test_women_profiles_load(self):
        for name in ("tt_specialist_women", "climber_women"):
            self.assertGreater(rider_profiles.load(name).cp, 0)


if __name__ == "__main__":
    unittest.main()
