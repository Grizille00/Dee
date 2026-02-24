import os
import unittest
from unittest.mock import patch

from dosimetry_app.auth import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    get_bootstrap_admin_credentials,
)


class AuthConfigTests(unittest.TestCase):
    def test_defaults_used_when_no_env_or_secrets(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOSIMETRY_ADMIN_USERNAME", None)
            os.environ.pop("DOSIMETRY_ADMIN_PASSWORD", None)
            with patch("dosimetry_app.auth._read_streamlit_secret", return_value=None):
                username, password = get_bootstrap_admin_credentials()

        self.assertEqual(username, DEFAULT_ADMIN_USERNAME)
        self.assertEqual(password, DEFAULT_ADMIN_PASSWORD)

    def test_env_overrides_defaults(self):
        with patch.dict(
            os.environ,
            {
                "DOSIMETRY_ADMIN_USERNAME": "cloud_admin",
                "DOSIMETRY_ADMIN_PASSWORD": "cloud_password",
            },
            clear=False,
        ):
            with patch("dosimetry_app.auth._read_streamlit_secret", return_value=None):
                username, password = get_bootstrap_admin_credentials()

        self.assertEqual(username, "cloud_admin")
        self.assertEqual(password, "cloud_password")

    def test_streamlit_secrets_used_when_env_missing(self):
        secrets = {
            "admin_username": "secret_admin",
            "admin_password": "secret_password",
        }
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOSIMETRY_ADMIN_USERNAME", None)
            os.environ.pop("DOSIMETRY_ADMIN_PASSWORD", None)
            with patch(
                "dosimetry_app.auth._read_streamlit_secret",
                side_effect=lambda key: secrets.get(key),
            ):
                username, password = get_bootstrap_admin_credentials()

        self.assertEqual(username, "secret_admin")
        self.assertEqual(password, "secret_password")


if __name__ == "__main__":
    unittest.main()
