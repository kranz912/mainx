from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetryConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    backoff_factor: float = 0.0
    status_forcelist: list[int] = [429, 500, 502, 503, 504]
    allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class AuthConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str = "none"
    token: str | None = None
    username: str | None = None
    password: str | None = None
    key: str | None = None
    value: str | None = None
    in_: str = Field(default="header", alias="in")


class ValidationConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raise_for_status: bool = True
    allowed_statuses: list[int] = []
    content_type_contains: str | None = None
    required_json_fields: list[str] = []


class LoggingConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "none"
    level: str = "INFO"
    format: str = "%(asctime)s %(levelname)s %(name)s %(message)s"
    file_path: str | None = None
    location: str | None = None
    cloudwatch_log_group: str | None = None
    cloudwatch_log_stream: str | None = None
    cloudwatch_region: str | None = None
    log_group: str | None = None
    log_stream: str | None = None
    region: str | None = None


class VaultSecretsConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    token: str | None = None
    token_env: str | None = None
    timeout: float = 5.0


class SsmSecretsConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: str | None = None
    with_decryption: bool = True


class SecretsConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ssm: SsmSecretsConfigModel | None = None
    vault: VaultSecretsConfigModel | None = None


class EndpointConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = "GET"
    path: str
    timeout: float | None = None
    headers: dict[str, str] = {}
    retries: RetryConfigModel | None = None
    auth: AuthConfigModel | None = None
    validation: ValidationConfigModel | None = None
    logging: LoggingConfigModel | None = None
    response_model: str | None = None


class ClientConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    timeout: float = 10.0
    headers: dict[str, str] = {}
    retries: RetryConfigModel | None = None
    auth: AuthConfigModel | None = None
    validation: ValidationConfigModel | None = None
    logging: LoggingConfigModel | None = None
    endpoints: dict[str, EndpointConfigModel]
    secrets: SecretsConfigModel | None = None


def model_to_dict(model: BaseModel | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return model.model_dump(exclude_none=True, by_alias=True)
