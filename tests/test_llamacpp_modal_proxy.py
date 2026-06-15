from __future__ import annotations

from fastapi.testclient import TestClient

from scripts import deploy_llamacpp_modal
from scripts.llamacpp_modal_config import (
    DeploymentConfig,
    ModalAppConfig,
    ModelConfig,
)


class RunningProcess:
    def poll(self):
        return None


def test_routed_request_is_not_treated_as_missing_query_parameters(monkeypatch):
    deployment = DeploymentConfig(
        app=ModalAppConfig(),
        models=(
            ModelConfig(
                route="text",
                role="text",
                model_ref="example/text",
                port=8001,
            ),
        ),
        source="test",
    )
    monkeypatch.setattr(deploy_llamacpp_modal, "DEPLOYMENT", deployment)
    monkeypatch.setattr(
        deploy_llamacpp_modal,
        "start_model_servers",
        lambda _api_key: {"text": RunningProcess()},
    )
    monkeypatch.setattr(
        deploy_llamacpp_modal, "stop_model_servers", lambda _processes: None
    )

    app = deploy_llamacpp_modal.create_proxy_app("secret")
    with TestClient(app) as client:
        response = client.get("/unknown/health")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown model route: unknown"}
