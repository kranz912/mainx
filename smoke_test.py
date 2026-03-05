from __future__ import annotations

import time

import requests

from maix import api


def main() -> None:
    api.reload()
    print("Loaded clients:", api.list_clients())

    # Direct call example.
    try:
        weather_response = api.weather.call(
            "forecast",
            params={
                "latitude": 52.52,
                "longitude": 13.41,
                "hourly": "temperature_2m",
            },
        )
        print("Weather status:", weather_response.status_code)
    except requests.RequestException as exc:
        print(f"Weather request failed: {exc}")

    # Another direct call example.
    try:
        stock_response = api.stockprice.call(
            "quote",
            params={"symbols": "AAPL"},
        )
        print("Stock status (direct):", stock_response.status_code)
        if getattr(stock_response, "parsed", None) is not None:
            print("Stock parsed type:", type(stock_response.parsed).__name__)
    except requests.RequestException as exc:
        print(f"Stock direct request failed: {exc}")

    # Queue a few calls and process synchronously.
    api.stockprice.enqueue_call("quote", params={"symbols": "MSFT"})
    api.stockprice.enqueue_call("quote", params={"symbols": "GOOGL"})
    try:
        queued_responses = api.stockprice.process_all(continue_on_error=True)
        print("Processed queued responses:", len(queued_responses))
    except requests.RequestException as exc:
        print(f"Queued processing failed: {exc}")

    # Queue work and let the background worker drain it.
    api.stockprice.enqueue_call("quote", params={"symbols": "NVDA"})
    api.stockprice.enqueue_call("quote", params={"symbols": "AMZN"})

    api.stockprice.start_worker(poll_interval=0.2, continue_on_error=True)
    try:
        while api.stockprice.queue_size() > 0:
            time.sleep(0.1)
    finally:
        api.stockprice.stop_worker(timeout=2.0)

    print("Queue size after worker:", api.stockprice.queue_size())
    if api.stockprice.worker_last_error() is not None:
        print("Worker captured error:", api.stockprice.worker_last_error())


if __name__ == "__main__":
    main()
