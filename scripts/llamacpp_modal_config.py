from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


DEFAULT_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda-b9049"
ROUTE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SUPPORTED_ROLES = {"text", "vision"}


@dataclass(frozen=True)
class ModalAppConfig:
    name: str = "secret-student-llamacpp"
    gpu: str = "L40S"
    image: str = DEFAULT_IMAGE
    secret_name: str = "secret-student-llm"
    timeout_minutes: int = 15
    scaledown_minutes: int = 15
    startup_timeout_seconds: int = 900
    max_concurrent_inputs: int = 12


@dataclass(frozen=True)
class ModelConfig:
    route: str
    model_ref: str
    port: int
    role: str = ""
    ctx_size: int = 8192
    gpu_layers: int = 999
    threads: int = 8
    parallel: int = 1
    extra_args: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DeploymentConfig:
    app: ModalAppConfig
    models: tuple[ModelConfig, ...]
    source: str
    legacy: bool = False


def load_deployment_config(path: str | Path) -> DeploymentConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"Modal model config does not exist: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Modal model config must be a YAML mapping.")
    app_raw = _mapping(raw.get("app", {}), "app")
    defaults = _mapping(raw.get("defaults", {}), "defaults")
    models_raw = raw.get("models")
    if not isinstance(models_raw, list) or not models_raw:
        raise ValueError("Modal model config must contain a non-empty models list.")

    allowed_app_keys = {
        "name",
        "gpu",
        "image",
        "secret_name",
        "timeout_minutes",
        "scaledown_minutes",
        "startup_timeout_seconds",
        "max_concurrent_inputs",
    }
    unknown_app_keys = sorted(set(app_raw) - allowed_app_keys)
    if unknown_app_keys:
        raise ValueError(f"Unknown app keys: {', '.join(unknown_app_keys)}")

    app = ModalAppConfig(
        name=_non_empty_string(app_raw.get("name", ModalAppConfig.name), "app.name"),
        gpu=_non_empty_string(app_raw.get("gpu", ModalAppConfig.gpu), "app.gpu"),
        image=_non_empty_string(app_raw.get("image", ModalAppConfig.image), "app.image"),
        secret_name=_non_empty_string(
            app_raw.get("secret_name", ModalAppConfig.secret_name), "app.secret_name"
        ),
        timeout_minutes=_positive_int(
            app_raw.get("timeout_minutes", ModalAppConfig.timeout_minutes),
            "app.timeout_minutes",
        ),
        scaledown_minutes=_positive_int(
            app_raw.get("scaledown_minutes", ModalAppConfig.scaledown_minutes),
            "app.scaledown_minutes",
        ),
        startup_timeout_seconds=_positive_int(
            app_raw.get(
                "startup_timeout_seconds", ModalAppConfig.startup_timeout_seconds
            ),
            "app.startup_timeout_seconds",
        ),
        max_concurrent_inputs=_positive_int(
            app_raw.get(
                "max_concurrent_inputs", ModalAppConfig.max_concurrent_inputs
            ),
            "app.max_concurrent_inputs",
        ),
    )

    allowed_model_keys = {
        "route",
        "role",
        "model_ref",
        "ctx_size",
        "gpu_layers",
        "threads",
        "parallel",
        "extra_args",
    }
    unknown_defaults = sorted(set(defaults) - allowed_model_keys)
    if unknown_defaults:
        raise ValueError(f"Unknown defaults keys: {', '.join(unknown_defaults)}")

    models: list[ModelConfig] = []
    routes: set[str] = set()
    roles: set[str] = set()
    for index, item in enumerate(models_raw):
        if 8001 + index > 65535:
            raise ValueError("Too many models to assign valid internal TCP ports.")
        model_raw = {**defaults, **_mapping(item, f"models[{index}]")}
        unknown = sorted(set(model_raw) - allowed_model_keys)
        if unknown:
            raise ValueError(
                f"Unknown keys in models[{index}]: {', '.join(unknown)}"
            )
        route = _non_empty_string(model_raw.get("route"), f"models[{index}].route")
        if not ROUTE_PATTERN.fullmatch(route):
            raise ValueError(
                f"models[{index}].route must match {ROUTE_PATTERN.pattern!r}."
            )
        if route in routes:
            raise ValueError(f"Duplicate model route: {route}")
        routes.add(route)

        role = str(model_raw.get("role", "")).strip().lower()
        if role and role not in SUPPORTED_ROLES:
            raise ValueError(
                f"models[{index}].role must be text, vision, or omitted."
            )
        if role in roles:
            raise ValueError(f"Duplicate model role: {role}")
        if role:
            roles.add(role)

        models.append(
            ModelConfig(
                route=route,
                role=role,
                model_ref=_non_empty_string(
                    model_raw.get("model_ref"), f"models[{index}].model_ref"
                ),
                port=8001 + index,
                ctx_size=_positive_int(
                    model_raw.get("ctx_size", ModelConfig.ctx_size),
                    f"models[{index}].ctx_size",
                ),
                gpu_layers=_non_negative_int(
                    model_raw.get("gpu_layers", ModelConfig.gpu_layers),
                    f"models[{index}].gpu_layers",
                ),
                threads=_positive_int(
                    model_raw.get("threads", ModelConfig.threads),
                    f"models[{index}].threads",
                ),
                parallel=_positive_int(
                    model_raw.get("parallel", ModelConfig.parallel),
                    f"models[{index}].parallel",
                ),
                extra_args=_string_list(
                    model_raw.get("extra_args", []), f"models[{index}].extra_args"
                ),
            )
        )

    return DeploymentConfig(app=app, models=tuple(models), source=str(config_path))


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping.")
    return value


def _non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _string_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of strings.")
    return tuple(value)
