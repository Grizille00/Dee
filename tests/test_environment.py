import unittest
from unittest.mock import patch

import pandas as pd

from dosimetry_app.validators import validate_dataset
from dosimetry_app.weather import (
    auto_detect_environment,
    detect_location_from_ip,
    fetch_current_environment,
    geocode_location,
    reverse_geocode_coordinates,
)


class EnvironmentTests(unittest.TestCase):
    def test_validate_environmental_dataset(self):
        frame = pd.DataFrame(
            [
                {"location": "Clinic A", "temperature_c": 21.5, "pressure_kpa": 100.9},
                {"location": "Clinic B", "temperature_c": 24.1, "pressure_kpa": 101.2},
            ]
        )
        errors = validate_dataset("environmental_data", frame)
        self.assertEqual(errors, [])

    def test_validate_environmental_dataset_invalid_pressure(self):
        frame = pd.DataFrame(
            [{"location": "Clinic A", "temperature_c": 21.5, "pressure_kpa": 0.0}]
        )
        errors = validate_dataset("environmental_data", frame)
        self.assertTrue(any("pressure_kpa" in err for err in errors))

    @patch("dosimetry_app.weather._fetch_json")
    def test_detect_location_from_ip(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "city": "Seattle",
            "region": "Washington",
            "country_name": "United States",
            "latitude": 47.61,
            "longitude": -122.33,
        }
        result = detect_location_from_ip()
        self.assertEqual(result["location_label"], "Seattle, Washington, United States")
        self.assertAlmostEqual(result["latitude"], 47.61, places=2)
        self.assertAlmostEqual(result["longitude"], -122.33, places=2)

    @patch("dosimetry_app.weather._fetch_json")
    def test_fetch_current_environment(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "current": {
                "temperature_2m": 18.4,
                "surface_pressure": 1008.0,
            }
        }
        result = fetch_current_environment(47.61, -122.33)
        self.assertAlmostEqual(result["temperature_c"], 18.4, places=3)
        self.assertAlmostEqual(result["pressure_kpa"], 100.8, places=3)

    @patch("dosimetry_app.weather._fetch_json")
    def test_geocode_location_prefers_africa(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "results": [
                {"name": "Harare", "country": "United States", "country_code": "US", "latitude": 38.0, "longitude": -85.0},
                {"name": "Harare", "country": "Zimbabwe", "country_code": "ZW", "latitude": -17.8292, "longitude": 31.0522},
            ]
        }
        result = geocode_location("Harare")
        self.assertIn("Zimbabwe", result["location_label"])
        self.assertEqual(result["country_code"], "ZW")

    @patch("dosimetry_app.weather._fetch_json")
    def test_auto_detect_environment_with_preferred_location(self, mock_fetch_json):
        mock_fetch_json.side_effect = [
            {
                "results": [
                    {
                        "name": "Harare",
                        "admin1": "Harare Province",
                        "country": "Zimbabwe",
                        "country_code": "ZW",
                        "latitude": -17.8292,
                        "longitude": 31.0522,
                    }
                ]
            },
            {"current": {"temperature_2m": 23.2, "surface_pressure": 859.0}},
        ]
        result = auto_detect_environment(preferred_location="Harare, Zimbabwe")
        self.assertEqual(result["provider"]["geolocation"], "open-meteo-geocoding")
        self.assertIn("Harare", result["location"])
        self.assertEqual(result["city"], "Harare")
        self.assertEqual(result["country"], "Zimbabwe")
        self.assertAlmostEqual(result["temperature_c"], 23.2, places=3)
        self.assertAlmostEqual(result["pressure_kpa"], 85.9, places=3)

    @patch("dosimetry_app.weather._fetch_json")
    def test_reverse_geocode_coordinates_prefers_africa(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "results": [
                {
                    "name": "Mutare",
                    "admin1": "Manicaland",
                    "country": "Zimbabwe",
                    "country_code": "ZW",
                },
                {
                    "name": "Mutare",
                    "admin1": "Washington",
                    "country": "United States",
                    "country_code": "US",
                },
            ]
        }
        result = reverse_geocode_coordinates(-18.97, 32.67)
        self.assertIn("Zimbabwe", result["location_label"])
        self.assertEqual(result["city"], "Mutare")
        self.assertEqual(result["country"], "Zimbabwe")
        self.assertEqual(result["country_code"], "ZW")


if __name__ == "__main__":
    unittest.main()
