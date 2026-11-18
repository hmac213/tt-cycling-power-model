"""Tests of the Critical Power / W' model."""

import unittest

from power_model import cp_model
from power_model import params as rider_params

_RIDER = rider_params.RiderParams()


class CpModelTest(unittest.TestCase):

    def test_three_regimes(self):
        half = 0.5 * _RIDER.w_prime
        self.assertEqual(cp_model.reserve_rate(400.0, half, _RIDER), -100.0)
        self.assertEqual(cp_model.reserve_rate(300.0, half, _RIDER), 0.0)
        # alpha (CP - P) (1 - B/W') = 1 * 100 * 0.5
        self.assertEqual(cp_model.reserve_rate(200.0, half, _RIDER), 50.0)

    def test_full_reserve_does_not_overfill(self):
        rate = cp_model.reserve_rate(200.0, _RIDER.w_prime, _RIDER)
        self.assertEqual(rate, 0.0)

    def test_exact_step_matches_euler_integration(self):
        for beta in (1.0, 0.5, 2.0):
            with self.subTest(beta=beta):
                rider = rider_params.RiderParams(beta=beta)
                reserve = 5_000.0
                dt = 0.01
                for _ in range(int(120 / dt)):
                    rate = cp_model.reserve_rate(150.0, reserve, rider)
                    reserve += dt * float(rate)
                exact = cp_model.step_reserve(5_000.0, 150.0, 120.0, rider)
                self.assertAlmostEqual(float(exact), reserve, delta=2.0)

    def test_reserve_is_empty_at_time_to_exhaustion(self):
        duration = cp_model.time_to_exhaustion(500.0, _RIDER)
        reserve = cp_model.step_reserve(
            _RIDER.w_prime, 500.0, duration, _RIDER
        )
        self.assertAlmostEqual(float(reserve), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
