from __future__ import annotations

import logging
from threading import Event, Thread
from time import sleep
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .log_providers import build_logger
from .queue import InMemoryRequestQueue, QueuedTask
from .response_parsing import parse_typed_response
from .specs import (
    AuthSpec,
    EndpointSpec,
    LoggingSpec,
    ResponseValidationSpec,
    RetrySpec,
)


class ConfigHttpClient:
    """A single API client created from one YAML config file."""

    def __init__(
        self,
        name: str,
        base_url: str,
        default_timeout: float = 10.0,
        default_headers: dict[str, str] | None = None,
        default_retries: RetrySpec | None = None,
        default_auth: AuthSpec | None = None,
        default_validation: ResponseValidationSpec | None = None,
        default_logging: LoggingSpec | None = None,
        endpoints: dict[str, EndpointSpec] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout
        self.default_headers = default_headers or {}
        self.default_retries = default_retries
        self.default_auth = default_auth
        self.default_validation = default_validation
        self.default_logging = default_logging
        self.endpoints = endpoints or {}
        self._queue = InMemoryRequestQueue()
        self._worker_stop_event = Event()
        self._worker_thread: Thread | None = None
        self._worker_poll_interval = 0.5
        self._worker_continue_on_error = True
        self._worker_last_error: Exception | None = None
        self._logger = build_logger(self.name, self.default_logging)
        self._session = self._build_session(default_retries)

    def _get_logger(self, logging_spec: LoggingSpec | None) -> logging.Logger | None:
        if logging_spec is None or logging_spec is self.default_logging:
            return self._logger
        return build_logger(f"{self.name}.override", logging_spec)

    def queue_size(self) -> int:
        return self._queue.size()

    def clear_queue(self) -> None:
        self._queue.clear()
        if self._logger is not None:
            self._logger.info("Queue cleared")

    def start_worker(
        self,
        poll_interval: float = 0.5,
        continue_on_error: bool = True,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be > 0")

        if self.is_worker_running():
            return

        self._worker_poll_interval = poll_interval
        self._worker_continue_on_error = continue_on_error
        self._worker_last_error = None
        self._worker_stop_event.clear()
        self._worker_thread = Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        if self._logger is not None:
            self._logger.info(
                "Worker started poll_interval=%s continue_on_error=%s",
                poll_interval,
                continue_on_error,
            )

    def stop_worker(self, timeout: float | None = None) -> None:
        self._worker_stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)
        if self._logger is not None:
            self._logger.info("Worker stopped")

    def is_worker_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def worker_last_error(self) -> Exception | None:
        return self._worker_last_error

    def enqueue_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: RetrySpec | None = None,
        auth: AuthSpec | None = None,
        validation: ResponseValidationSpec | None = None,
        response_model: str | type[Any] | None = None,
    ) -> int:
        task = QueuedTask(
            action="request",
            payload={
                "method": method,
                "path": path,
                "params": params,
                "json": json,
                "data": data,
                "headers": headers,
                "timeout": timeout,
                "retries": retries,
                "auth": auth,
                "validation": validation,
                "response_model": response_model,
            },
        )
        size = self._queue.enqueue(task)
        if self._logger is not None:
            self._logger.info("Enqueued request method=%s path=%s queue_size=%s", method, path, size)
        return size

    def enqueue_call(
        self,
        endpoint_name: str,
        *,
        path_params: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: RetrySpec | None = None,
        auth: AuthSpec | None = None,
        validation: ResponseValidationSpec | None = None,
        response_model: str | type[Any] | None = None,
    ) -> int:
        task = QueuedTask(
            action="call",
            payload={
                "endpoint_name": endpoint_name,
                "path_params": path_params,
                "params": params,
                "json": json,
                "data": data,
                "headers": headers,
                "timeout": timeout,
                "retries": retries,
                "auth": auth,
                "validation": validation,
                "response_model": response_model,
            },
        )
        size = self._queue.enqueue(task)
        if self._logger is not None:
            self._logger.info(
                "Enqueued endpoint call endpoint=%s queue_size=%s",
                endpoint_name,
                size,
            )
        return size

    def process_next(self) -> requests.Response | None:
        task = self._queue.dequeue()
        if task is None:
            return None

        return self._execute_task(task)

    def _execute_task(self, task: QueuedTask) -> requests.Response:
        if self._logger is not None:
            self._logger.debug("Processing queued task action=%s", task.action)
        if task.action == "request":
            return self.request(**task.payload)
        if task.action == "call":
            return self.call(**task.payload)

        raise ValueError(f"Unknown queued action: {task.action}")

    def _worker_loop(self) -> None:
        while not self._worker_stop_event.is_set():
            task = self._queue.dequeue()
            if task is None:
                self._worker_stop_event.wait(self._worker_poll_interval)
                continue

            try:
                self._execute_task(task)
            except Exception as exc:  # pragma: no cover - thread exception path
                self._worker_last_error = exc
                if self._logger is not None:
                    self._logger.exception("Worker task failed: %s", exc)
                if not self._worker_continue_on_error:
                    self._worker_stop_event.set()
                else:
                    sleep(0)

    def process_all(self, continue_on_error: bool = False) -> list[requests.Response]:
        responses: list[requests.Response] = []
        while self.queue_size() > 0:
            try:
                response = self.process_next()
                if response is not None:
                    responses.append(response)
            except Exception:
                if not continue_on_error:
                    raise
        return responses

    def _build_session(self, retries: RetrySpec | None) -> requests.Session:
        session = requests.Session()
        if retries is None or retries.total <= 0:
            return session

        retry = Retry(
            total=retries.total,
            backoff_factor=retries.backoff_factor,
            status_forcelist=retries.status_forcelist,
            allowed_methods={method.upper() for method in retries.allowed_methods},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: RetrySpec | None = None,
        auth: AuthSpec | None = None,
        validation: ResponseValidationSpec | None = None,
        logging: LoggingSpec | None = None,
        response_model: str | type[Any] | None = None,
    ) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = {**self.default_headers, **(headers or {})}
        merged_params = dict(params or {})

        effective_auth = auth if auth is not None else self.default_auth
        effective_validation = validation if validation is not None else self.default_validation
        effective_retries = retries if retries is not None else self.default_retries
        effective_logging = logging if logging is not None else self.default_logging

        request_logger = self._get_logger(effective_logging)

        request_auth: tuple[str, str] | None = None
        if effective_auth is not None:
            merged_headers, merged_params, request_auth = effective_auth.apply(
                merged_headers, merged_params
            )

        session = (
            self._session
            if effective_retries is self.default_retries
            else self._build_session(effective_retries)
        )

        if request_logger is not None:
            request_logger.info("Request start method=%s url=%s", method.upper(), url)

        try:
            response = session.request(
                method=method.upper(),
                url=url,
                params=merged_params,
                json=json,
                data=data,
                headers=merged_headers,
                timeout=timeout if timeout is not None else self.default_timeout,
                auth=request_auth,
            )
        except Exception as exc:
            if request_logger is not None:
                request_logger.exception("Request failed method=%s url=%s error=%s", method.upper(), url, exc)
            raise

        if effective_validation is not None:
            effective_validation.validate(response)

        if response_model is not None:
            payload = response.json()
            response.parsed = parse_typed_response(payload, response_model)
        else:
            response.parsed = None

        if request_logger is not None:
            request_logger.info(
                "Request complete method=%s url=%s status=%s",
                method.upper(),
                url,
                response.status_code,
            )

        return response

    def call(
        self,
        endpoint_name: str,
        *,
        path_params: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: RetrySpec | None = None,
        auth: AuthSpec | None = None,
        validation: ResponseValidationSpec | None = None,
        logging: LoggingSpec | None = None,
        response_model: str | type[Any] | None = None,
    ) -> requests.Response:
        if endpoint_name not in self.endpoints:
            raise KeyError(
                f"Unknown endpoint '{endpoint_name}' for client '{self.name}'"
            )

        spec = self.endpoints[endpoint_name]
        path_params = path_params or {}
        path = spec.path.format(**path_params)

        merged_headers = {**spec.headers, **(headers or {})}
        final_timeout = timeout if timeout is not None else spec.timeout
        final_retries = retries if retries is not None else spec.retries
        final_auth = auth if auth is not None else spec.auth
        final_validation = validation if validation is not None else spec.validation
        final_logging = logging if logging is not None else spec.logging
        final_response_model = response_model if response_model is not None else spec.response_model

        return self.request(
            method=spec.method,
            path=path,
            params=params,
            json=json,
            data=data,
            headers=merged_headers,
            timeout=final_timeout,
            retries=final_retries,
            auth=final_auth,
            validation=final_validation,
            logging=final_logging,
            response_model=final_response_model,
        )
