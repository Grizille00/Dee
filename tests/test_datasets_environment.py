import unittest

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.datasets import get_environment_from_dataset, list_environment_locations


class DatasetEnvironmentTests(unittest.TestCase):
    def setUp(self):
        initialize_application()

    def test_harare_is_prioritized_in_location_list(self):
        locations = list_environment_locations()
        self.assertGreater(len(locations), 0)
        self.assertEqual(locations[0], "Harare, Zimbabwe")

    def test_location_matching_supports_partial_and_case_insensitive_queries(self):
        harare = get_environment_from_dataset("harare zimbabwe")
        self.assertEqual(harare["location"], "Harare, Zimbabwe")

        nairobi = get_environment_from_dataset("NAIROBI")
        self.assertEqual(nairobi["location"], "Nairobi, Kenya")


if __name__ == "__main__":
    unittest.main()

