from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    SessionRecord,
    SourceKind,
)
from remote_image_compare.services.runtime_paths import app_data_dir


def default_session_record_store_path() -> Path:
    return app_data_dir() / "session_records.json"


class SessionRecordStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = (
            Path(storage_path) if storage_path is not None else default_session_record_store_path()
        )

    def list_records(self) -> list[SessionRecord]:
        if not self.storage_path.exists():
            return []
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        records = [self._deserialize_record(item) for item in payload.get("records", [])]
        return sorted(records, key=lambda item: item.saved_at, reverse=True)

    def save_record(self, record: SessionRecord) -> None:
        records = [item for item in self.list_records() if item.id != record.id]
        records.append(record)
        records.sort(key=lambda item: item.saved_at, reverse=True)
        self._write_records(records)

    def delete_record(self, record_id: str) -> None:
        records = [item for item in self.list_records() if item.id != record_id]
        self._write_records(records)

    def export_record_json(self, record: SessionRecord) -> str:
        return json.dumps(self._serialize_record(record), indent=2, ensure_ascii=False)

    def parse_record_json(self, payload: str) -> SessionRecord:
        data = json.loads(payload)
        self._validate_record_payload(data)
        return self._deserialize_record(data)

    def _write_records(self, records: list[SessionRecord]) -> None:
        payload = {"records": [self._serialize_record(record) for record in records]}
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _serialize_record(self, record: SessionRecord) -> dict:
        record_payload = asdict(record)
        record_payload["version"] = 1
        record_payload["compare_mode"] = record.compare_mode.value
        record_payload["panes"] = [
            {
                **asdict(pane),
                "source_kind": pane.source_kind.value,
            }
            for pane in sorted(record.panes, key=lambda item: item.pane_index)
        ]
        return record_payload

    def _deserialize_record(self, payload: dict) -> SessionRecord:
        self._validate_record_payload(payload)
        panes = tuple(
            SessionPaneBinding(
                pane_index=int(item["pane_index"]),
                source_kind=SourceKind(item["source_kind"]),
                display_name=item["display_name"],
                root_path=item.get("root_path"),
                server_name=item.get("server_name"),
                remote_path=item.get("remote_path"),
            )
            for item in sorted(payload["panes"], key=lambda item: int(item["pane_index"]))
        )
        return SessionRecord(
            id=payload.get("id") or payload["name"],
            name=payload["name"],
            saved_at=payload["saved_at"],
            layout_mode=payload["layout_mode"],
            compare_mode=CompareMode(payload["compare_mode"]),
            panes=panes,
        )

    def _validate_record_payload(self, payload: dict) -> None:
        required_fields = ("version", "name", "saved_at", "layout_mode", "compare_mode", "panes")
        for field in required_fields:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")
        if payload["version"] != 1:
            raise ValueError(f"Unsupported record version: {payload['version']}")
        if not isinstance(payload["panes"], list):
            raise ValueError("Field panes must be a list")
