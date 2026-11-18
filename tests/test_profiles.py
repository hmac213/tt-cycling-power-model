"""Tests of the rider profiles."""

import json
import pathlib
import tempfile
import unittest

from physics_model import params as physics_params
from profiles import rider


class RiderProfileTest(unittest.TestCase):

    def test_shipped_profiles_load(self):
        self.assertIn("tt_specialist", rider.available())
        self.assertIn("climber", rider.available())
        for name in rider.available():
            with self.subTest(profile=name):
                profile = rider.load(name)
                self.assertGreater(profile.p_max, profile.cp)

    def test_specialists_differ_the_right_way(self):
        tt_specialist = rider.load("tt_specialist")
        climber = rider.load("climber")
        # More power per unit drag on the flat, more per kilogram uphill.
        self.assertGreater(
            tt_specialist.cp / tt_specialist.cda, climber.cp / climber.cda
        )
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

    def test_unknown_profile_name(self):
        with self.assertRaises(FileNotFoundError):
            rider.load("sprinter")


if __name__ == "__main__":
    unittest.main()
