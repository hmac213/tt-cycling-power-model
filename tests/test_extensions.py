"""Tests of the extensions: durability, imperfect execution, race courses."""

import dataclasses
import pathlib
import unittest

import numpy as np

from course_loader import gpx
from physics_model import params as physics_params
from power_model import params as rider_params
from profiles import rider as rider_profiles
from solver import execution
from solver import optimize
from solver import simulate
from tests import helpers

_PHYSICS = physics_params.PhysicsParams()
_RIDER = rider_params.RiderParams()
_COURSES = pathlib.Path(__file__).resolve().parent.parent / "courses"


class DurabilityTest(unittest.TestCase):

    def setUp(self):
        # The same rider with the loss of durability switched off.
        self.classic = dataclasses.replace(
            _RIDER, fatigue_time=np.inf, work_capacity=np.inf
        )

    def test_short_ride_is_barely_affected(self):
        course = helpers.straight_course(3_000.0)
        full = optimize.constant_power_ride(course, _PHYSICS, _RIDER)
        classic = optimize.constant_power_ride(course, _PHYSICS, self.classic)
        self.assertGreaterEqual(full.total_time, classic.total_time)
        self.assertLess(full.total_time, 1.01 * classic.total_time)

    def test_long_ride_is_slowed_and_ends_with_less_critical_power(self):
        course = helpers.straight_course(30_000.0)
        config = simulate.SimConfig(step_length=100.0)
        full = optimize.constant_power_ride(course, _PHYSICS, _RIDER, config)
        classic = optimize.constant_power_ride(
            course, _PHYSICS, self.classic, config
        )
        self.assertGreater(full.total_time, classic.total_time + 5.0)
        self.assertLess(full.critical_power[-1], _RIDER.lt2 - 5.0)
        self.assertGreaterEqual(full.critical_power[-1], _RIDER.lt1)
        self.assertLess(full.capacity[-1], _RIDER.w_prime)
        np.testing.assert_allclose(classic.critical_power, _RIDER.lt2)

    def test_ride_records_work_and_fatigue(self):
        course = helpers.straight_course(3_000.0)
        ride = optimize.constant_power_ride(course, _PHYSICS, _RIDER)
        done = np.sum(ride.power * np.diff(ride.time))
        self.assertAlmostEqual(ride.work[-1], done, delta=1e-6 * done)
        self.assertTrue(np.all(np.diff(ride.fatigue) >= 0))
        self.assertTrue(ride.feasible)
        self.assertAlmostEqual(ride.deficit.max(), 1.0, places=4)


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
            course = gpx.load_gpx(_COURSES / f"{name}.gpx", sigma_ele=1.0)
            self.assertAlmostEqual(course.length, length, delta=0.015 * length)
            # Map elevation loaded this way gives realistic road grades.
            self.assertLess(np.tan(np.abs(course.theta)).max(), 0.20)

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
