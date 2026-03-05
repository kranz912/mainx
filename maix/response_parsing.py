from __future__ import annotations

from dataclasses import is_dataclass
from importlib import import_module
from typing import Any


def _load_model_from_string(model_ref: str) -> type[Any]:
    if ":" in model_ref:
        module_name, class_name = model_ref.split(":", 1)
    else:
        module_name, class_name = model_ref.rsplit(".", 1)

    module = import_module(module_name)
    model = getattr(module, class_name)
    if not isinstance(model, type):
        raise TypeError(f"response_model must reference a class: {model_ref}")
    return model


def parse_typed_response(payload: Any, response_model: str | type[Any]) -> Any:
    model_type = _load_model_from_string(response_model) if isinstance(response_model, str) else response_model

    try:
        from pydantic import BaseModel
    except ImportError:  # pragma: no cover - pydantic is a project dependency
        BaseModel = None  # type: ignore

    if BaseModel is not None and isinstance(model_type, type) and issubclass(model_type, BaseModel):
        return model_type.model_validate(payload)

    if isinstance(model_type, type) and is_dataclass(model_type):
        if not isinstance(payload, dict):
            raise TypeError("Dataclass response_model expects JSON object payload")
        return model_type(**payload)

    raise TypeError(
        "Unsupported response_model type. Use a pydantic BaseModel or dataclass class."
    )
