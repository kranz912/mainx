from __future__ import annotations

import re
from typing import Any

import yaml


def _sanitize_path_for_name(path: str) -> str:
    cleaned = re.sub(r"\{([^}]+)\}", r"\1", path)
    cleaned = cleaned.strip("/").replace("/", "_").replace("-", "_")
    return cleaned or "root"


def import_openapi_to_maix_config(openapi: dict[str, Any]) -> dict[str, Any]:
    servers = openapi.get("servers", []) or []
    base_url = ""
    if servers and isinstance(servers[0], dict):
        base_url = str(servers[0].get("url", ""))

    endpoints: dict[str, Any] = {}
    for path, path_item in (openapi.get("paths", {}) or {}).items():
        if not isinstance(path_item, dict):
            continue

        for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            operation_id = operation.get("operationId")
            name = str(operation_id) if operation_id else f"{method}_{_sanitize_path_for_name(path)}"
            endpoints[name] = {
                "method": method.upper(),
                "path": path,
            }

    return {
        "base_url": base_url,
        "timeout": 10,
        "headers": {"Accept": "application/json"},
        "endpoints": endpoints,
    }


def export_maix_to_openapi(maix_config: dict[str, Any], title: str = "MAIX Export", version: str = "1.0.0") -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for endpoint_name, endpoint in (maix_config.get("endpoints", {}) or {}).items():
        if not isinstance(endpoint, dict):
            continue
        path = str(endpoint.get("path", "/"))
        method = str(endpoint.get("method", "GET")).lower()

        if path not in paths:
            paths[path] = {}
        paths[path][method] = {
            "operationId": endpoint_name,
            "responses": {
                "200": {
                    "description": "Successful response"
                }
            },
        }

    openapi_doc: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": version,
        },
        "paths": paths,
    }

    base_url = maix_config.get("base_url")
    if base_url:
        openapi_doc["servers"] = [{"url": base_url}]

    return openapi_doc


def load_api_document(file_path: str) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if file_path.lower().endswith(".json"):
        import json

        return json.loads(content)

    return yaml.safe_load(content) or {}


def write_api_document(file_path: str, document: dict[str, Any]) -> None:
    if file_path.lower().endswith(".json"):
        import json

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2)
        return

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(document, f, sort_keys=False)
