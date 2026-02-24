import unittest

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.settings import (
    DEFAULT_SETTINGS,
    ENV_SOURCE_DATASET,
    ENV_SOURCE_MANUAL,
    apply_live_detection_defaults_for_legacy_installations,
    get_environment_settings,
    save_environment_settings,
)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        initialize_application()
        save_environment_settings(
            env_source=DEFAULT_SETTINGS["env_source"],
            env_manual_temperature_c=float(DEFAULT_SETTINGS["env_manual_temperature_c"]),
            env_manual_pressure_kpa=float(DEFAULT_SETTINGS["env_manual_pressure_kpa"]),
            env_dataset_location=str(DEFAULT_SETTINGS["env_dataset_location"]),
        )

    def test_default_environment_settings_exist(self):
        settings = get_environment_settings()
        self.assertIn("env_source", settings)
        self.assertIn("env_manual_temperature_c", settings)
        self.assertIn("env_manual_pressure_kpa", settings)
        self.assertIn("env_dataset_location", settings)
        self.assertEqual(settings["env_source"], DEFAULT_SETTINGS["env_source"])

    def test_save_environment_settings_roundtrip(self):
        save_environment_settings(
            env_source=ENV_SOURCE_DATASET,
            env_manual_temperature_c=19.5,
            env_manual_pressure_kpa=100.2,
            env_dataset_location="Nairobi, Kenya",
        )
        settings = get_environment_settings()
        self.assertEqual(settings["env_source"], ENV_SOURCE_DATASET)
        self.assertAlmostEqual(float(settings["env_manual_temperature_c"]), 19.5, places=3)
        self.assertAlmostEqual(float(settings["env_manual_pressure_kpa"]), 100.2, places=3)
        self.assertEqual(settings["env_dataset_location"], "Nairobi, Kenya")

        save_environment_settings(
            env_source=ENV_SOURCE_MANUAL,
            env_manual_temperature_c=20.6,
            env_manual_pressure_kpa=98.18,
            env_dataset_location="",
        )

    def test_legacy_defaults_migrate_to_live_detection(self):
        save_environment_settings(
            env_source=ENV_SOURCE_MANUAL,
            env_manual_temperature_c=20.6,
            env_manual_pressure_kpa=98.18,
            env_dataset_location="",
        )
        apply_live_detection_defaults_for_legacy_installations()
        settings = get_environment_settings()
        self.assertEqual(settings["env_source"], DEFAULT_SETTINGS["env_source"])
        self.assertEqual(settings["env_dataset_location"], DEFAULT_SETTINGS["env_dataset_location"])

    def test_harare_defaults_migrate_to_live_detection(self):
        save_environment_settings(
            env_source=ENV_SOURCE_DATASET,
            env_manual_temperature_c=22.0,
            env_manual_pressure_kpa=85.9,
            env_dataset_location="Harare, Zimbabwe",
        )
        apply_live_detection_defaults_for_legacy_installations()
        settings = get_environment_settings()
        self.assertEqual(settings["env_source"], DEFAULT_SETTINGS["env_source"])
        self.assertEqual(settings["env_dataset_location"], DEFAULT_SETTINGS["env_dataset_location"])


if __name__ == "__main__":
    unittest.main()
