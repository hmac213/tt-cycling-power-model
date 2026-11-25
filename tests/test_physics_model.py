"""Tests of the equation of motion and the cornering limits."""

import unittest

import numpy as np

from physics_model import cornering
from physics_model import dynamics
from physics_model import params as physics_params
from tests import helpers

_PHYSICS = physics_params.PhysicsParams()


class DynamicsTest(unittest.TestCase):

    def test_steady_state_balances_forces(self):
        speed = dynamics.steady_state_speed(300.0, 0.02, 2.0, _PHYSICS)
        accel = dynamics.acceleration(speed, 300.0, 0.02, 2.0, _PHYSICS)
        self.assertAlmostEqual(float(accel), 0.0, places=9)

    def test_fast_tailwind_pushes_the_rider(self):
        rolling = dynamics.rolling_force(0.0, _PHYSICS)
        total = dynamics.resistive_force(5.0, 0.0, -10.0, _PHYSICS)
        self.assertLess(total, rolling)

    def test_distance_form_matches_time_form(self):
        # d(v^3)/ds = 3 v^2 dv/ds = 3 v (dv/dt).
        speed = 9.0
        accel = dynamics.acceleration(speed, 350.0, 0.03, 1.0, _PHYSICS)
        rate = dynamics.speed_cubed_rate(speed, 350.0, 0.03, 1.0, _PHYSICS)
        self.assertAlmostEqual(float(rate), 3 * speed * float(accel))

    def test_drivetrain_loss_and_wheel_inertia(self):
        # Only eta P reaches the wheel, and the wheels add I / r^2 to the
        # mass that is accelerated: 0.14 / 0.311^2 = 1.45 kg.
        self.assertAlmostEqual(
            _PHYSICS.effective_mass - _PHYSICS.mass, 0.14 / 0.311**2
        )
        ideal = physics_params.PhysicsParams(
            drivetrain_efficiency=1.0, wheel_inertia=0.0
        )
        lossy = dynamics.steady_state_speed(300.0, 0.0, 0.0, _PHYSICS)
        same = dynamics.steady_state_speed(
            0.977 * 300.0, 0.0, 0.0, ideal
        )
        self.assertAlmostEqual(lossy, same, places=9)


class CorneringTest(unittest.TestCase):

    def test_corner_speed_limit_formula(self):
        limit = cornering.corner_speed_limit(1 / 20.0, 0.0, _PHYSICS)
        expected = np.sqrt(_PHYSICS.mu_corner * _PHYSICS.g * 20.0)
        self.assertAlmostEqual(float(limit), expected)
        straight = cornering.corner_speed_limit(0.0, 0.0, _PHYSICS)
        self.assertEqual(float(straight), cornering.MAX_SPEED)

    def test_envelope_respects_corner_and_braking_limits(self):
        course = helpers.corner_course(radius=15.0, leg=1_000.0)
        corner_limit = cornering.corner_speed_limit(
            course.mean_curvature(20.0), course.theta, _PHYSICS
        )
        envelope = cornering.speed_envelope(
            course.distance, corner_limit, course.theta, course.headwind,
            _PHYSICS,
        )
        corner_speed = np.sqrt(_PHYSICS.mu_corner * _PHYSICS.g * 15.0)
        self.assertAlmostEqual(envelope.min(), corner_speed, delta=0.5)
        # Approaching the corner, the envelope falls no faster than braking
        # plus resistance can slow the rider.
        approach = (course.distance > 900.0) & (course.distance < 990.0)
        decel = -np.gradient(0.5 * envelope**2, course.distance)[approach]
        resistance = dynamics.resistive_force(
            envelope[approach], 0.0, 0.0, _PHYSICS
        )
        limit = _PHYSICS.brake_decel + resistance / _PHYSICS.mass
        self.assertTrue(np.all(decel <= limit + 0.05))
        self.assertGreater(decel.max(), _PHYSICS.brake_decel)


if __name__ == "__main__":
    unittest.main()
