from __future__ import annotations

import unittest

from maix.openapi_bridge import export_maix_to_openapi, import_openapi_to_maix_config


class TestOpenApiBridge(unittest.TestCase):
    def test_import_openapi_to_maix_config(self) -> None:
        openapi = {
            "openapi": "3.0.3",
            "servers": [{"url": "https://api.example.com"}],
            "paths": {
                "/users/{id}": {
                    "get": {
                        "operationId": "get_user",
                    }
                }
            },
        }

        config = import_openapi_to_maix_config(openapi)

        self.assertEqual(config["base_url"], "https://api.example.com")
        self.assertIn("get_user", config["endpoints"])
        self.assertEqual(config["endpoints"]["get_user"]["path"], "/users/{id}")
        self.assertEqual(config["endpoints"]["get_user"]["method"], "GET")

    def test_export_maix_config_to_openapi(self) -> None:
        config = {
            "base_url": "https://api.example.com",
            "endpoints": {
                "get_user": {
                    "method": "GET",
                    "path": "/users/{id}",
                }
            },
        }

        openapi = export_maix_to_openapi(config, title="Demo", version="2.0.0")

        self.assertEqual(openapi["openapi"], "3.0.3")
        self.assertEqual(openapi["info"]["title"], "Demo")
        self.assertEqual(openapi["info"]["version"], "2.0.0")
        self.assertEqual(openapi["servers"][0]["url"], "https://api.example.com")
        self.assertIn("/users/{id}", openapi["paths"])
        self.assertIn("get", openapi["paths"]["/users/{id}"])


if __name__ == "__main__":
    unittest.main()
