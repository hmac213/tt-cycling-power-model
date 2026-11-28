"""Tests of the rider profiles."""

import json
import pathlib
import tempfile
import unittest

import numpy as np

from physics_model import params as physics_params
from power_model import calibrate
from profiles import rider


class RiderProfileTest(unittest.TestCase):

    def test_shipped_profiles_load(self):
        for name in ("tt_specialist", "climber", "tt_specialist_women",
                     "climber_women"):
            self.assertIn(name, rider.available())
        for name in rider.available():
            with self.subTest(profile=name):
                profile = rider.load(name)
                self.assertGreater(profile.p_max, profile.cp)

    def test_specialists_differ_the_right_way(self):
        # Both genders: the time trialist has more power per unit drag.
        for suffix in ("", "_women"):
            tt_specialist = rider.load("tt_specialist" + suffix)
            climber = rider.load("climber" + suffix)
            self.assertGreater(
                tt_specialist.cp / tt_specialist.cda, climber.cp / climber.cda
            )
        # Men: the climber has more power per kilogram (Valenzuela 2022).
        # The women's data show the reverse (Mateo-March 2022), so no check.
        tt_specialist = rider.load("tt_specialist")
        climber = rider.load("climber")
        self.assertGreater(
            climber.cp / climber.total_mass,
            tt_specialist.cp / tt_specialist.total_mass,
        )

    def test_profile_fills_both_parameter_classes(self):
        profile = rider.load("tt_specialist")
        base = physics_params.PhysicsParams(mu_corner=0.3)
        physics = profile.physics_params(base)
        self.assertEqual(
            physics.mass, profile.rider_mass + profile.bike_mass
        )
        self.assertEqual(physics.cda, profile.cda)
        self.assertEqual(physics.crr, profile.crr)
        self.assertEqual(physics.mu_corner, 0.3)
        power = profile.rider_params()
        self.assertEqual(power.cp, profile.cp)
        self.assertEqual(power.w_prime, profile.w_prime)
        self.assertEqual(power.p_max, profile.p_max)

    def test_loads_from_a_path_and_rejects_bad_files(self):
        good = json.loads((rider.PROFILE_DIR / "climber.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "custom.json"
            path.write_text(json.dumps(good))
            self.assertEqual(rider.load(path), rider.load("climber"))

            unknown = dict(good, wingspan_m=1.8)
            path.write_text(json.dumps(unknown))
            with self.assertRaisesRegex(ValueError, "wingspan_m"):
                rider.load(path)

            missing = {k: v for k, v in good.items() if k != "cda_m2"}
            path.write_text(json.dumps(missing))
            with self.assertRaisesRegex(ValueError, "cda_m2"):
                rider.load(path)

            negative = dict(good, bike_mass_kg=-1.0)
            path.write_text(json.dumps(negative))
            with self.assertRaises(ValueError):
                rider.load(path)

    def test_profiles_reproduce_the_efforts_they_were_fitted_to(self):
        for name in rider.available():
            with self.subTest(profile=name):
                profile = rider.load(name)
                self.assertEqual(len(profile.best_efforts), 3)
                errors = calibrate.fit_errors(
                    profile.rider_params(), profile.best_efforts
                )
                powers = np.array([watts for _, watts in profile.best_efforts])
                self.assertLess(np.abs(errors / powers).max(), 0.01)

    def test_unknown_profile_name(self):
        with self.assertRaises(FileNotFoundError):
            rider.load("sprinter")


if __name__ == "__main__":
    unittest.main()
