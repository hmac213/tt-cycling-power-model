"""Tests of the simulator and the two optimization stages."""

import unittest

import numpy as np

from physics_model import dynamics
from physics_model import params as physics_params
from power_model import params as rider_params
from solver import collocation
from solver import dynamic_program
from solver import optimize
from solver import simulate
from tests import helpers

_PHYSICS = physics_params.PhysicsParams()
_RIDER = rider_params.RiderParams()
_CONFIG = simulate.SimConfig()

# Coarse settings that keep the optimization tests quick.
_COARSE_CONFIG = simulate.SimConfig(step_length=40.0)
_COARSE_DP = dynamic_program.DpConfig(
    num_speeds=50, num_reserves=40, num_powers=17
)


def _hill(north: np.ndarray) -> np.ndarray:
    """An 80 m hill in the middle of an 8 km course."""
    return 80.0 * np.exp(-0.5 * ((north / 8_000.0 - 0.5) / 0.15) ** 2)


def _constant_plan(
    course, power: float, physics=_PHYSICS, config=_CONFIG
) -> simulate.RideResult:
    """Rides a course at one constant power."""
    grid = simulate.build_grid(course, physics, config)
    plan = np.full(grid.num_steps, power)
    return simulate.simulate(plan, grid, physics, _RIDER, config)


class GridTest(unittest.TestCase):

    def test_steps_have_the_requested_length(self):
        course = helpers.straight_course(1_010.0)
        grid = simulate.build_grid(course, _PHYSICS, _CONFIG)
        self.assertEqual(grid.num_steps, 51)
        self.assertLess(grid.step, _CONFIG.step_length)
        self.assertAlmostEqual(grid.nodes[-1], course.length)
        self.assertEqual(grid.theta.shape, (51, 2 * _CONFIG.substeps + 1))

    def test_step_count_scales_with_course_length(self):
        short = simulate.build_grid(
            helpers.straight_course(2_000.0), _PHYSICS, _CONFIG
        )
        long = simulate.build_grid(
            helpers.straight_course(8_000.0), _PHYSICS, _CONFIG
        )
        self.assertAlmostEqual(long.num_steps, 4 * short.num_steps, delta=1)
        self.assertAlmostEqual(long.step, short.step, delta=0.1)

    def test_plan_of_the_wrong_length_is_rejected(self):
        grid = simulate.build_grid(
            helpers.straight_course(1_000.0), _PHYSICS, _CONFIG
        )
        with self.assertRaises(ValueError):
            simulate.simulate(np.full(7, 300.0), grid, _PHYSICS, _RIDER)


class SimulateTest(unittest.TestCase):

    def test_reaches_steady_state_and_converges(self):
        course = helpers.straight_course(20_000.0)
        coarse = _constant_plan(
            course, 250.0, config=simulate.SimConfig(step_length=40.0)
        )
        fine = _constant_plan(
            course, 250.0, config=simulate.SimConfig(step_length=5.0)
        )
        steady = dynamics.steady_state_speed(250.0, 0.0, 0.0, _PHYSICS)
        self.assertAlmostEqual(coarse.speed[-1], steady, places=3)
        self.assertAlmostEqual(coarse.total_time, fine.total_time, delta=0.01)

    def test_standing_start_matches_closed_form(self):
        # Without resistance v^3 = 3 P s / m, so T = (3/2) L / v(L).
        physics = physics_params.PhysicsParams(cda=0.0, crr=0.0)
        course = helpers.straight_course(1_000.0)
        ride = _constant_plan(course, 400.0, physics)
        end_speed = (3 * 400.0 * course.length / physics.mass) ** (1 / 3)
        self.assertAlmostEqual(ride.speed[-1], end_speed, places=6)
        self.assertAlmostEqual(
            ride.total_time, 1.5 * course.length / end_speed, places=6
        )

    def test_coasting_over_a_crest_conserves_energy(self):
        # No resistance and no power: the speed at the top of a 10 m crest
        # follows from energy conservation alone.
        physics = physics_params.PhysicsParams(cda=0.0, crr=0.0)

        def rise(north: np.ndarray) -> np.ndarray:
            return 10.0 * np.sin(np.pi * north / 2_000.0) ** 2

        course = helpers.straight_course(1_000.0, rise)
        config = simulate.SimConfig(initial_speed=20.0)
        ride = _constant_plan(course, 0.0, physics, config)
        expected = np.sqrt(20.0**2 - 2 * physics.g * 10.0)
        self.assertAlmostEqual(ride.speed[-1], expected, places=3)

    def test_hard_deceleration_is_integrated_accurately(self):
        # Coasting up a steep ramp changes the speed a lot within one step.
        # The time must not depend on the step length.
        course = helpers.straight_course(100.0, lambda north: 0.08 * north)
        times = []
        for step_length in (20.0, 1.0):
            config = simulate.SimConfig(
                step_length=step_length, initial_speed=15.0
            )
            times.append(_constant_plan(course, 0.0, config=config).total_time)
        self.assertLess(times[0], 12.0)
        self.assertAlmostEqual(times[0], times[1], delta=0.005)

    def test_rider_brakes_for_the_corner(self):
        course = helpers.corner_course(radius=15.0, leg=1_000.0)
        grid = simulate.build_grid(course, _PHYSICS, _CONFIG)
        ride = _constant_plan(course, 350.0)
        corner_speed = np.sqrt(_PHYSICS.mu_corner * _PHYSICS.g * 15.0)
        before = np.searchsorted(grid.nodes, 950.0)
        self.assertGreater(ride.speed[before], 10.0)
        self.assertGreater(ride.brake_energy.sum(), 1_000.0)
        self.assertTrue(np.all(ride.speed[1:] <= grid.speed_cap + 1e-9))
        in_corner = (grid.nodes > 1_000.0) & (grid.nodes < 1_020.0)
        self.assertLess(ride.speed[in_corner].min(), corner_speed + 0.5)


class DynamicProgramTest(unittest.TestCase):

    def test_power_levels_include_critical_power(self):
        levels = dynamic_program.power_levels(_RIDER, 17)
        self.assertEqual(levels.size, 17)
        self.assertEqual(levels[0], 0.0)
        self.assertEqual(levels[-1], _RIDER.p_max)
        self.assertIn(_RIDER.cp, levels)
        self.assertTrue(np.all(np.diff(levels) > 0))

    def test_plan_is_feasible_and_beats_constant_power(self):
        course = helpers.straight_course(8_000.0, _hill)
        constant = optimize.constant_power_ride(
            course, _PHYSICS, _RIDER, _COARSE_CONFIG
        )
        grid = simulate.build_grid(course, _PHYSICS, _COARSE_CONFIG)
        ride = dynamic_program.solve(
            grid, _PHYSICS, _RIDER, _COARSE_CONFIG, _COARSE_DP
        )
        self.assertTrue(ride.feasible)
        self.assertLess(ride.total_time, constant.total_time - 1.0)
        self.assertLessEqual(ride.power.max(), _RIDER.p_max)


class OptimizeTest(unittest.TestCase):

    def test_constant_power_ride_empties_the_reserve(self):
        course = helpers.straight_course(8_000.0, _hill)
        constant = optimize.constant_power_ride(
            course, _PHYSICS, _RIDER, _COARSE_CONFIG
        )
        self.assertTrue(constant.feasible)
        self.assertAlmostEqual(constant.reserve[-1], 0.0, delta=1.0)
        self.assertAlmostEqual(np.ptp(constant.power), 0.0)

    def test_polish_improves_on_the_dynamic_program(self):
        course = helpers.straight_course(8_000.0, _hill)
        result = optimize.optimize_pacing(
            course, _PHYSICS, _RIDER, _COARSE_CONFIG, _COARSE_DP
        )
        self.assertTrue(result.polished)
        self.assertTrue(result.ride.feasible)
        self.assertLessEqual(result.ride.total_time, result.dp_ride.total_time)
        # The coarse grids already land within a fraction of a second.
        self.assertLess(
            result.dp_ride.total_time - result.ride.total_time, 0.5
        )
        # All of W' gets used, and the power cap is respected.
        self.assertLess(result.ride.reserve.min(), 50.0)
        self.assertLessEqual(result.ride.power.max(), _RIDER.p_max + 1e-6)
        # The polished plan is smoother than the gridded one.
        self.assertLess(
            np.abs(np.diff(result.ride.power)).mean(),
            np.abs(np.diff(result.dp_ride.power)).mean(),
        )

    def test_optimizer_eases_off_before_the_corner(self):
        course = helpers.corner_course(radius=15.0, leg=1_000.0)
        config = simulate.SimConfig()
        constant = optimize.constant_power_ride(
            course, _PHYSICS, _RIDER, config
        )
        result = optimize.optimize_pacing(
            course, _PHYSICS, _RIDER, config, _COARSE_DP
        )
        ride = result.ride
        self.assertTrue(ride.feasible)
        self.assertLess(ride.total_time, constant.total_time)
        approach = (ride.distance[1:] > 960.0) & (ride.distance[1:] <= 1_000.0)
        self.assertLess(
            ride.power[approach].mean(), constant.power[0] - 50.0
        )
        self.assertLess(ride.brake_energy.sum(), constant.brake_energy.sum())

    def test_polish_is_skipped_when_recovery_beats_expenditure(self):
        rider = rider_params.RiderParams(alpha=1.5)
        self.assertFalse(collocation.supports(rider))
        course = helpers.straight_course(2_000.0)
        result = optimize.optimize_pacing(
            course, _PHYSICS, rider, _COARSE_CONFIG, _COARSE_DP
        )
        self.assertFalse(result.polished)
        self.assertIs(result.ride, result.dp_ride)
        self.assertTrue(result.ride.feasible)


if __name__ == "__main__":
    unittest.main()
