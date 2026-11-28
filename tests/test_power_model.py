"""Tests of the two-reserve stamina model and its calibration."""

import dataclasses
import unittest

import numpy as np

from power_model import calibrate
from power_model import cp_model
from power_model import params as rider_params

_RIDER = rider_params.RiderParams()
# The same rider with the loss of durability switched off.
_CLASSIC = dataclasses.replace(
    _RIDER, fatigue_time=np.inf, work_capacity=np.inf
)


class FastReserveTest(unittest.TestCase):

    def test_three_regimes(self):
        cp, capacity = 300.0, 20_000.0
        # Expenditure: 100 W above CP for 10 s uses 1 kJ of 20 kJ.
        spent = cp_model.step_deficit(0.5, 400.0, 10.0, cp, capacity, _RIDER)
        self.assertAlmostEqual(float(spent), 0.55)
        # Neutral: riding at CP changes nothing.
        same = cp_model.step_deficit(0.5, 300.0, 10.0, cp, capacity, _RIDER)
        self.assertAlmostEqual(float(same), 0.5)
        # Recovery: the deficit shrinks.
        eased = cp_model.step_deficit(0.5, 200.0, 10.0, cp, capacity, _RIDER)
        self.assertLess(float(eased), 0.5)

    def test_full_reserve_does_not_overfill(self):
        full = cp_model.step_deficit(0.0, 100.0, 600.0, 300.0, 20e3, _RIDER)
        self.assertAlmostEqual(float(full), 0.0, places=9)

    def test_exact_recovery_matches_euler_integration(self):
        cp, capacity = 300.0, 20_000.0
        for beta in (1.0, 0.5, 2.0):
            with self.subTest(beta=beta):
                rider = rider_params.RiderParams(beta=beta)
                deficit = 0.75
                dt = 0.01
                for _ in range(int(120 / dt)):
                    rate = -rider.alpha * (cp - 150.0) * deficit**beta
                    deficit += dt * rate / capacity
                exact = cp_model.step_deficit(
                    0.75, 150.0, 120.0, cp, capacity, rider
                )
                self.assertAlmostEqual(float(exact), deficit, places=4)

    def test_classic_model_is_the_limit_without_durability_loss(self):
        # Then time to exhaustion is the hyperbola W' / (P - CP).
        limit = cp_model.time_to_exhaustion(np.array([500.0, 350.0]), _CLASSIC)
        np.testing.assert_allclose(limit, [100.0, 400.0], rtol=1e-6)
        forever = cp_model.time_to_exhaustion(300.0, _CLASSIC, max_time=3600)
        self.assertTrue(np.isinf(forever))


class DurabilityTest(unittest.TestCase):

    def test_fatigue_rate_follows_the_thresholds(self):
        at_lt2 = float(cp_model.fatigue_rate(_RIDER.lt2, _RIDER))
        self.assertAlmostEqual(at_lt2, 1.0, places=3)
        below_lt1 = float(cp_model.fatigue_rate(0.8 * _RIDER.lt1, _RIDER))
        self.assertLess(below_lt1, 1e-4)
        # Twice the intensity costs 2^gamma times as much.
        double = float(
            cp_model.fatigue_rate(2 * _RIDER.lt2 - _RIDER.lt1, _RIDER)
        )
        self.assertAlmostEqual(
            double, 2.0**_RIDER.fatigue_exponent, places=3
        )

    def test_critical_power_falls_from_lt2_towards_lt1(self):
        fresh = float(cp_model.critical_power(0.0, _RIDER))
        self.assertEqual(fresh, _RIDER.lt2)
        tired = float(cp_model.critical_power(_RIDER.fatigue_time, _RIDER))
        span = _RIDER.lt2 - _RIDER.lt1
        self.assertAlmostEqual(tired, _RIDER.lt1 + span / np.e)
        spent = float(cp_model.critical_power(1e6, _RIDER))
        self.assertAlmostEqual(spent, _RIDER.lt1)

    def test_durability_starts_flat(self):
        early = float(cp_model.durability(0.1 * _RIDER.fatigue_time, _RIDER))
        self.assertGreater(early, 0.99)

    def test_capacity_shrinks_with_work(self):
        self.assertEqual(
            float(cp_model.reserve_capacity(0.0, _RIDER)), _RIDER.w_prime
        )
        worked = float(
            cp_model.reserve_capacity(_RIDER.work_capacity, _RIDER)
        )
        self.assertAlmostEqual(worked, _RIDER.w_prime / np.e)

    def test_step_state_accumulates_fatigue_and_work(self):
        deficit, fatigue, work = cp_model.step_state(
            0.0, 0.0, 0.0, _RIDER.lt2, 60.0, _RIDER
        )
        self.assertAlmostEqual(float(work), 60.0 * _RIDER.lt2)
        self.assertAlmostEqual(float(fatigue), 60.0, delta=0.01)
        # Critical power was still LT2 at the start of the interval.
        self.assertAlmostEqual(float(deficit), 0.0)

    def test_critical_power_cannot_be_held_forever(self):
        minutes = float(cp_model.time_to_exhaustion(_RIDER.lt2, _RIDER)) / 60
        self.assertGreater(minutes, 20.0)
        self.assertLess(minutes, 40.0)
        # At LT1 the rider never tires.
        easy = cp_model.time_to_exhaustion(_RIDER.lt1, _RIDER, max_time=7200)
        self.assertTrue(np.isinf(easy))

    def test_power_duration_curve_falls_and_respects_the_cap(self):
        durations = np.array([1.0, 60.0, 300.0, 1200.0, 3600.0, 10_800.0])
        curve = cp_model.power_duration_curve(durations, _RIDER)
        self.assertEqual(curve[0], _RIDER.p_max)
        self.assertTrue(np.all(np.diff(curve) < 0))
        # An hour is held below LT2 and three hours above LT1.
        self.assertLess(curve[4], _RIDER.lt2)
        self.assertGreater(curve[5], _RIDER.lt1)
        # Short efforts are held below what the classic model allows.
        classic = cp_model.power_duration_curve(durations, _CLASSIC)
        self.assertTrue(np.all(curve[1:] < classic[1:]))


class CalibrateTest(unittest.TestCase):

    def test_recovers_lt2_and_w_prime_from_short_efforts(self):
        truth = rider_params.RiderParams(lt1=240.0, lt2=320.0, w_prime=18e3)
        durations = (300.0, 600.0, 1200.0)
        efforts = list(zip(
            durations, cp_model.power_duration_curve(durations, truth)
        ))
        fitted = calibrate.fit(_RIDER, efforts, lt1_ratio=0.75)
        self.assertAlmostEqual(fitted.lt2, 320.0, delta=1.0)
        self.assertAlmostEqual(fitted.lt1, 0.75 * fitted.lt2)
        self.assertAlmostEqual(fitted.w_prime, 18e3, delta=500.0)
        errors = calibrate.fit_errors(fitted, efforts)
        self.assertLess(np.abs(errors).max(), 0.5)

    def test_recovers_fatigue_time_from_a_long_effort(self):
        truth = dataclasses.replace(_RIDER, fatigue_time=2000.0)
        efforts = [
            (7200.0, float(cp_model.power_duration_curve(7200.0, truth)[0]))
        ]
        fitted = calibrate.fit(_RIDER, efforts, fields=("fatigue_time",))
        self.assertAlmostEqual(fitted.fatigue_time, 2000.0, delta=100.0)

    def test_rejects_bad_requests(self):
        with self.assertRaises(ValueError):
            calibrate.fit(_RIDER, [(300.0, 400.0)], fields=("p_max",))
        with self.assertRaises(ValueError):
            calibrate.fit(_RIDER, [(300.0, 400.0)])


class RiderParamsTest(unittest.TestCase):

    def test_thresholds_must_be_ordered(self):
        with self.assertRaises(ValueError):
            rider_params.RiderParams(lt1=310.0, lt2=300.0)
        self.assertEqual(_RIDER.cp, _RIDER.lt2)


if __name__ == "__main__":
    unittest.main()
