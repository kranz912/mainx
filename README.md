# MAIX

Modular API Integration eXecutor.

## Install

```bash
pip install -e .
```

For CloudWatch logging support:

```bash
pip install -e .[cloudwatch]
```

## Config Files

Put one YAML file per API under `config/`.

Examples included:
- `config/weather.yml`
- `config/Stockprice.yml`

## Usage

```python
import time

import requests

from maix import api

api.reload()
print("Loaded clients:", api.list_clients())

try:
    # Direct call from config/weather.yml
    weather_response = api.weather.call(
        "forecast",
        params={
            "latitude": 52.52,
            "longitude": 13.41,
            "hourly": "temperature_2m",
        },
    )
    print(weather_response.status_code)
except requests.RequestException as exc:
    print(f"Weather request failed: {exc}")

try:
    # Direct call from config/Stockprice.yml
    stock_response = api.stockprice.call(
        "quote",
        params={"symbols": "AAPL"},
    )
    print(stock_response.status_code)
except requests.RequestException as exc:
    print(f"Stock request failed: {exc}")

# Queue + sync processing
api.stockprice.enqueue_call("quote", params={"symbols": "MSFT"})
api.stockprice.enqueue_call("quote", params={"symbols": "GOOGL"})
queued_responses = api.stockprice.process_all(continue_on_error=True)
print(len(queued_responses))

# Queue + background worker processing
api.stockprice.enqueue_call("quote", params={"symbols": "NVDA"})
api.stockprice.enqueue_call("quote", params={"symbols": "AMZN"})

api.stockprice.start_worker(poll_interval=0.2, continue_on_error=True)
while api.stockprice.queue_size() > 0:
    time.sleep(0.1)
api.stockprice.stop_worker(timeout=2.0)

if api.stockprice.worker_last_error() is not None:
    print("Worker captured error:", api.stockprice.worker_last_error())
```

You can run the full sample locally with `python smoke_test.py`.
Public APIs may return `429 Too Many Requests`; the sample catches these to keep the demo running.

## API Surface

- `api.<config_name>.call(endpoint_name, ...)`
- `api.<config_name>.request(method, path, ...)`
- `api.<config_name>.enqueue_call(endpoint_name, ...)`
- `api.<config_name>.enqueue_request(method, path, ...)`
- `api.<config_name>.process_next()` and `api.<config_name>.process_all()`
- `api.<config_name>.start_worker()` and `api.<config_name>.stop_worker()`
- `api.list_clients()` to show loaded clients
- `api.reload()` to re-read changed config files at runtime

Config file names become client names (lowercase), so `Stockprice.yml` is available as `api.stockprice`.

## Authentication

Supported auth types in YAML:

```yaml
auth:
    type: bearer
    token: "your-token"
```

```yaml
auth:
    type: basic
    username: "user"
    password: "pass"
```

```yaml
auth:
    type: api_key
    in: header # or query
    key: "X-API-Key"
    value: "your-key"
```

You can define `auth` at root level (applies to all endpoints) or inside a specific endpoint.

## Retries

```yaml
retries:
    total: 3
    backoff_factor: 0.5
    status_forcelist: [429, 500, 502, 503, 504]
    allowed_methods: [GET, POST]
```

You can define retries globally or per endpoint.

## Response Validation

```yaml
validation:
    raise_for_status: true
    allowed_statuses: [200]
    content_type_contains: "application/json"
    required_json_fields: ["data"]
```

Validation can be configured globally or per endpoint.

## Logging

You can configure logging per client (root `logging`) and per endpoint (`endpoints.<name>.logging`).

### File logging

```yaml
logging:
    provider: file
    level: INFO
    file_path: logs/stockprice.log
```

### Console logging

```yaml
logging:
    provider: console
    level: DEBUG
```

### CloudWatch logging

```yaml
logging:
    provider: cloudwatch
    level: INFO
    cloudwatch_log_group: maix-api
    cloudwatch_log_stream: stockprice
    cloudwatch_region: us-east-1
```

CloudWatch provider requires `boto3`. Install with `pip install -e .[cloudwatch]`.

## In-Memory Queue

Use the built-in FIFO queue when you want to buffer calls and execute them later.

```python
from maix import api

api.stockprice.enqueue_call("quote", params={"symbols": "AAPL"})
api.stockprice.enqueue_call("quote", params={"symbols": "MSFT"})

responses = api.stockprice.process_all(continue_on_error=True)
print(len(responses))  # 2
```

## Background Worker Mode

Run queue processing in the background using a daemon thread.

```python
from maix import api

api.stockprice.enqueue_call("quote", params={"symbols": "AAPL"})
api.stockprice.enqueue_call("quote", params={"symbols": "MSFT"})

api.stockprice.start_worker(poll_interval=0.2, continue_on_error=True)

# ... do other work

api.stockprice.stop_worker(timeout=2.0)
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```
