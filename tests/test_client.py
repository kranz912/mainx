from __future__ import annotations

from dataclasses import dataclass
import time
import unittest
from unittest.mock import Mock

from maix.client import (
    AuthSpec,
    ConfigHttpClient,
    EndpointSpec,
    LoggingSpec,
    ResponseValidationSpec,
    RetrySpec,
)


class TestAuthSpec(unittest.TestCase):
    def test_bearer_auth_sets_header(self) -> None:
        spec = AuthSpec(type="bearer", token="abc123")

        headers, params, auth = spec.apply({}, {})

        self.assertEqual(headers["Authorization"], "Bearer abc123")
        self.assertEqual(params, {})
        self.assertIsNone(auth)

    def test_api_key_query_auth_sets_param(self) -> None:
        spec = AuthSpec(type="api_key", key="apikey", value="k1", in_="query")

        headers, params, auth = spec.apply({}, {})

        self.assertEqual(params["apikey"], "k1")
        self.assertEqual(headers, {})
        self.assertIsNone(auth)

    def test_basic_auth_returns_auth_tuple(self) -> None:
        spec = AuthSpec(type="basic", username="u", password="p")

        headers, params, auth = spec.apply({}, {})

        self.assertEqual(headers, {})
        self.assertEqual(params, {})
        self.assertEqual(auth, ("u", "p"))


class TestResponseValidationSpec(unittest.TestCase):
    def test_required_json_fields_success(self) -> None:
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"data": {"ok": True}}

        spec = ResponseValidationSpec(
            raise_for_status=False,
            allowed_statuses=[200],
            content_type_contains="application/json",
            required_json_fields=["data"],
        )

        spec.validate(response)

        response.raise_for_status.assert_not_called()

    def test_required_json_fields_missing_raises(self) -> None:
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"unexpected": True}

        spec = ResponseValidationSpec(
            raise_for_status=False,
            required_json_fields=["data"],
        )

        with self.assertRaises(ValueError):
            spec.validate(response)


class TestConfigHttpClient(unittest.TestCase):
    def test_request_applies_defaults_and_validation(self) -> None:
        validation = ResponseValidationSpec(raise_for_status=False, allowed_statuses=[200])
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            default_headers={"Accept": "application/json"},
            default_auth=AuthSpec(type="bearer", token="secret"),
            default_validation=validation,
        )

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"ok": True}

        client._session.request = Mock(return_value=response)

        actual = client.request("GET", "/resource", params={"a": 1})

        self.assertIs(actual, response)
        _, kwargs = client._session.request.call_args
        self.assertEqual(kwargs["url"], "https://example.com/resource")
        self.assertEqual(kwargs["headers"]["Accept"], "application/json")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["params"], {"a": 1})

    def test_call_uses_endpoint_overrides(self) -> None:
        endpoint = EndpointSpec(
            method="GET",
            path="/items/{item_id}",
            headers={"X-Endpoint": "1"},
            auth=AuthSpec(type="api_key", key="X-Key", value="v", in_="header"),
        )
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            endpoints={"get_item": endpoint},
        )

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"ok": True}

        client._session.request = Mock(return_value=response)

        client.call("get_item", path_params={"item_id": 42})

        _, kwargs = client._session.request.call_args
        self.assertEqual(kwargs["url"], "https://example.com/items/42")
        self.assertEqual(kwargs["headers"]["X-Endpoint"], "1")
        self.assertEqual(kwargs["headers"]["X-Key"], "v")

    def test_retry_session_is_configured(self) -> None:
        retries = RetrySpec(total=3, backoff_factor=0.2, status_forcelist=[500])
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            default_retries=retries,
        )

        https_adapter = client._session.adapters["https://"]
        self.assertEqual(https_adapter.max_retries.total, 3)
        self.assertEqual(https_adapter.max_retries.backoff_factor, 0.2)

    def test_in_memory_queue_enqueue_and_process_request(self) -> None:
        client = ConfigHttpClient(name="test", base_url="https://example.com")

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"ok": True}
        client._session.request = Mock(return_value=response)

        size_after_enqueue = client.enqueue_request(
            "GET",
            "/queued",
            params={"x": "1"},
        )

        self.assertEqual(size_after_enqueue, 1)
        self.assertEqual(client.queue_size(), 1)

        actual = client.process_next()

        self.assertIs(actual, response)
        self.assertEqual(client.queue_size(), 0)

    def test_in_memory_queue_process_all_call_tasks(self) -> None:
        endpoint = EndpointSpec(method="GET", path="/items/{item_id}")
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            endpoints={"get_item": endpoint},
        )

        response_one = Mock()
        response_one.status_code = 200
        response_one.headers = {"Content-Type": "application/json"}
        response_one.json.return_value = {"id": 1}

        response_two = Mock()
        response_two.status_code = 200
        response_two.headers = {"Content-Type": "application/json"}
        response_two.json.return_value = {"id": 2}

        client._session.request = Mock(side_effect=[response_one, response_two])

        client.enqueue_call("get_item", path_params={"item_id": 1})
        client.enqueue_call("get_item", path_params={"item_id": 2})

        results = client.process_all()

        self.assertEqual(len(results), 2)
        self.assertIs(results[0], response_one)
        self.assertIs(results[1], response_two)
        self.assertEqual(client.queue_size(), 0)

    def test_background_worker_processes_queue(self) -> None:
        client = ConfigHttpClient(name="test", base_url="https://example.com")

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"ok": True}
        client._session.request = Mock(return_value=response)

        client.enqueue_request("GET", "/worker")
        client.start_worker(poll_interval=0.01)

        deadline = time.time() + 1.0
        while time.time() < deadline and client.queue_size() > 0:
            time.sleep(0.01)

        client.stop_worker(timeout=1.0)

        self.assertEqual(client.queue_size(), 0)
        client._session.request.assert_called_once()
        self.assertFalse(client.is_worker_running())

    def test_request_writes_logs_when_logging_enabled(self) -> None:
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            default_logging=LoggingSpec(provider="console", level="INFO"),
        )

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"ok": True}
        client._session.request = Mock(return_value=response)

        mock_logger = Mock()
        client._logger = mock_logger

        client.request("GET", "/log-test")

        mock_logger.info.assert_any_call(
            "Request start method=%s url=%s",
            "GET",
            "https://example.com/log-test",
        )
        mock_logger.info.assert_any_call(
            "Request complete method=%s url=%s status=%s",
            "GET",
            "https://example.com/log-test",
            200,
        )

    def test_typed_response_parsing_sets_parsed_attribute(self) -> None:
        @dataclass
        class User:
            id: int
            name: str

        endpoint = EndpointSpec(method="GET", path="/user", response_model=User)
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            endpoints={"get_user": endpoint},
        )

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"id": 7, "name": "Alice"}
        client._session.request = Mock(return_value=response)

        actual = client.call("get_user")

        self.assertIs(actual, response)
        self.assertIsNotNone(actual.parsed)
        self.assertEqual(actual.parsed.id, 7)
        self.assertEqual(actual.parsed.name, "Alice")

    def test_typed_response_parsing_from_string_model_ref(self) -> None:
        endpoint = EndpointSpec(
            method="GET",
            path="/weather",
            response_model="examples.models:WeatherForecastResponse",
        )
        client = ConfigHttpClient(
            name="test",
            base_url="https://example.com",
            endpoints={"forecast": endpoint},
        )

        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.json.return_value = {"latitude": 52.52, "longitude": 13.41}
        client._session.request = Mock(return_value=response)

        actual = client.call("forecast")

        self.assertAlmostEqual(actual.parsed.latitude, 52.52)
        self.assertAlmostEqual(actual.parsed.longitude, 13.41)


if __name__ == "__main__":
    unittest.main()
