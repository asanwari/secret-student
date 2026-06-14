from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.config import BASE_DIR, Settings


logger = logging.getLogger(__name__)
DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,", re.IGNORECASE)
SENSITIVE_KEYS = {"authorization", "api_key", "password", "token"}


class LLMTraceError(RuntimeError):
    """An LLM failure carrying the durable trace ID used to debug it."""

    def __init__(self, message: str, trace_id: str) -> None:
        super().__init__(f"{message} (trace: {trace_id})")
        self.trace_id = trace_id


class TraceRun:
    """Collects one model call and persists every important transition."""

    def __init__(
        self,
        settings: Settings,
        workflow: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings
        self.trace_id = str(uuid4())
        self.started = datetime.now(timezone.utc)
        self.started_perf = perf_counter()
        self.document: dict[str, Any] = {
            "schema_version": 1,
            "trace_id": self.trace_id,
            "workflow": workflow,
            "status": "running",
            "destination": settings.trace_destination,
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "started_at": self.started.isoformat(),
            "context": context or {},
            "events": [],
        }
        self._persist()

    def event(self, event_type: str, **data: Any) -> None:
        self.document["events"].append(
            {
                "sequence": len(self.document["events"]) + 1,
                "type": event_type,
                "at": datetime.now(timezone.utc).isoformat(),
                "elapsed_ms": round((perf_counter() - self.started_perf) * 1000, 2),
                **_redact_images_and_secrets(data),
            }
        )
        self._persist()

    def finish(self, status: str, **data: Any) -> None:
        self.document.update(
            {
                "status": status,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round((perf_counter() - self.started_perf) * 1000, 2),
                **data,
            }
        )
        self._persist(final=True)

    def _persist(self, final: bool = False) -> None:
        destination = self.settings.trace_destination
        if destination == "off":
            return
        if destination == "local":
            self._write_local(self.document)
            return
        if destination == "hub" and final:
            self._upload_hub(_sanitize_for_hub(self.document, self.settings))
            return
        if destination not in {"local", "hub", "off"}:
            logger.warning("Unknown TRACE_DESTINATION=%s; trace kept in logs only.", destination)

    def _filename(self) -> str:
        timestamp = self.started.strftime("%Y%m%dT%H%M%SZ")
        workflow = re.sub(r"[^a-zA-Z0-9_-]+", "-", self.document["workflow"])
        return f"{timestamp}_{workflow}_{self.trace_id}.json"

    def _write_local(self, document: dict[str, Any]) -> None:
        directory = Path(self.settings.trace_dir)
        if not directory.is_absolute():
            directory = BASE_DIR / directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self._filename()
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(document, indent=2, ensure_ascii=True) + "\n")
        temp_path.replace(path)

    def _upload_hub(self, document: dict[str, Any]) -> None:
        if not self.settings.trace_hub_repo_id:
            logger.error("TRACE_DESTINATION=hub requires TRACE_HUB_REPO_ID.")
            return
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=self.settings.trace_hub_token or None)
            api.create_repo(
                repo_id=self.settings.trace_hub_repo_id,
                repo_type="dataset",
                private=self.settings.trace_hub_private,
                exist_ok=True,
            )
            payload = io.BytesIO(
                (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode()
            )
            date_path = self.started.strftime("%Y/%m/%d")
            api.upload_file(
                path_or_fileobj=payload,
                path_in_repo=f"traces/{date_path}/{self._filename()}",
                repo_id=self.settings.trace_hub_repo_id,
                repo_type="dataset",
                commit_message=f"Add {self.document['workflow']} trace {self.trace_id}",
            )
        except Exception:
            # Trace publishing must never turn a successful lesson into a failure.
            logger.exception("Could not upload LLM trace %s to the Hub.", self.trace_id)


def _redact_images_and_secrets(value: Any, key: str = "") -> Any:
    if key.lower() in SENSITIVE_KEYS or key.lower().endswith("_token"):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: _redact_images_and_secrets(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_images_and_secrets(item) for item in value]
    if isinstance(value, str) and DATA_URL_RE.match(value):
        digest = hashlib.sha256(value.encode()).hexdigest()
        return f"<image-data-url sha256={digest} chars={len(value)}>"
    return value


def _sanitize_for_hub(document: dict[str, Any], settings: Settings) -> dict[str, Any]:
    sanitized = deepcopy(_redact_images_and_secrets(document))
    sanitized["context"].pop("user_id", None)
    if not settings.trace_hub_include_content:
        for event in sanitized.get("events", []):
            if event.get("type") == "request":
                event["messages"] = "<redacted; set TRACE_HUB_INCLUDE_CONTENT=true to publish>"
            if event.get("type") in {"response", "json_repair"}:
                event.pop("raw_content", None)
                event.pop("repaired_content", None)
    return sanitized
