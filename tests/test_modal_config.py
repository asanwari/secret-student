from __future__ import annotations

from pathlib import Path

import pytest

from scripts.llamacpp_modal_config import load_deployment_config


EXAMPLE_CONFIG = Path("config/modal-models.example.yaml")


def test_example_modal_config_loads_models_and_defaults():
    deployment = load_deployment_config(EXAMPLE_CONFIG)

    assert deployment.app.name == "secret-student-models"
    assert deployment.app.gpu == "L4"
    assert [model.route for model in deployment.models] == ["text", "vision"]
    assert [model.port for model in deployment.models] == [8001, 8002]
    assert deployment.models[0].parallel == 2
    assert deployment.models[1].ctx_size == 4096
    assert deployment.models[1].threads == 8


def test_modal_config_supports_additional_unassigned_models(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(
        """
models:
  - route: text
    role: text
    model_ref: example/text
  - route: vision
    role: vision
    model_ref: example/vision
  - route: helper
    model_ref: example/helper
    extra_args: [--flash-attn, "on"]
""".strip()
    )

    deployment = load_deployment_config(path)

    assert len(deployment.models) == 3
    assert deployment.models[2].port == 8003
    assert deployment.models[2].role == ""
    assert deployment.models[2].extra_args == ("--flash-attn", "on")


@pytest.mark.parametrize(
    ("yaml_text", "message"),
    [
        (
            "models: [{route: bad/path, model_ref: example/model}]",
            "route must match",
        ),
        (
            "models: [{route: text, model_ref: a}, {route: text, model_ref: b}]",
            "Duplicate model route",
        ),
        (
            "models: [{route: a, role: text, model_ref: a}, {route: b, role: text, model_ref: b}]",
            "Duplicate model role",
        ),
        (
            "models: [{route: text, model_ref: example/model, parallel: 0}]",
            "parallel must be a positive integer",
        ),
    ],
)
def test_modal_config_rejects_invalid_values(tmp_path, yaml_text, message):
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml_text)

    with pytest.raises(ValueError, match=message):
        load_deployment_config(path)
