from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from maix.client import AuthSpec, LoggingSpec, ResponseValidationSpec, RetrySpec
from maix.manager import ConfigHttpLibrary


class TestConfigHttpLibrary(unittest.TestCase):
    def test_loads_client_and_endpoint_with_advanced_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir)
            config_dir.joinpath("demo.yml").write_text(
                textwrap.dedent(
                    """
                    base_url: "https://api.example.com"
                    timeout: 7
                    headers:
                      Accept: "application/json"
                    retries:
                      total: 2
                      backoff_factor: 0.4
                    auth:
                      type: bearer
                      token: token-123
                    validation:
                      raise_for_status: true
                      allowed_statuses: [200]
                    logging:
                      provider: file
                      level: INFO
                      file_path: logs/demo.log

                    endpoints:
                      details:
                        method: GET
                        path: "/v1/details/{id}"
                        retries:
                          total: 1
                        auth:
                          type: api_key
                          in: query
                          key: apikey
                          value: xyz
                        validation:
                          required_json_fields: [data]
                        logging:
                          provider: console
                          level: DEBUG
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            lib = ConfigHttpLibrary(config_dir=config_dir)
            client = lib.get("demo")

            self.assertEqual(client.base_url, "https://api.example.com")
            self.assertEqual(client.default_timeout, 7.0)
            self.assertEqual(client.default_headers["Accept"], "application/json")
            self.assertIsInstance(client.default_retries, RetrySpec)
            self.assertEqual(client.default_retries.total, 2)
            self.assertIsInstance(client.default_auth, AuthSpec)
            self.assertEqual(client.default_auth.type, "bearer")
            self.assertIsInstance(client.default_validation, ResponseValidationSpec)
            self.assertEqual(client.default_validation.allowed_statuses, [200])
            self.assertIsInstance(client.default_logging, LoggingSpec)
            self.assertEqual(client.default_logging.provider, "file")
            self.assertEqual(client.default_logging.file_path, "logs/demo.log")

            endpoint = client.endpoints["details"]
            self.assertEqual(endpoint.path, "/v1/details/{id}")
            self.assertEqual(endpoint.retries.total, 1)
            self.assertEqual(endpoint.auth.type, "api_key")
            self.assertEqual(endpoint.auth.in_, "query")
            self.assertEqual(endpoint.validation.required_json_fields, ["data"])
            self.assertEqual(endpoint.logging.provider, "console")

    def test_missing_base_url_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir)
            config_dir.joinpath("bad.yml").write_text(
                "endpoints: {}\n", encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                ConfigHttpLibrary(config_dir=config_dir)


if __name__ == "__main__":
    unittest.main()
