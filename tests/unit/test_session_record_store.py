from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    SessionRecord,
    SourceKind,
)
from remote_image_compare.services.session_record_store import SessionRecordStore


def test_session_record_models_capture_remote_and_local_panes() -> None:
    record = SessionRecord(
        id="record-1",
        name="baseline compare",
        saved_at="2026-06-27T12:00:00+08:00",
        layout_mode="2 x 3",
        compare_mode=CompareMode.COMMON,
        panes=(
            SessionPaneBinding(
                pane_index=0,
                source_kind=SourceKind.LOCAL,
                display_name="HR",
                root_path="D:/dataset/HR",
            ),
            SessionPaneBinding(
                pane_index=1,
                source_kind=SourceKind.SFTP,
                display_name="wsl:/srv/photos/LR",
                remote_path="/srv/photos/LR",
                server_name="wsl",
            ),
        ),
    )

    assert record.panes[0].root_path == "D:/dataset/HR"
    assert record.panes[1].server_name == "wsl"
    assert record.panes[1].remote_path == "/srv/photos/LR"


def test_session_record_store_round_trips_records(tmp_path) -> None:
    store = SessionRecordStore(tmp_path / "session_records.json")
    record = SessionRecord(
        id="record-1",
        name="baseline compare",
        saved_at="2026-06-27T12:00:00+08:00",
        layout_mode="2 x 2",
        compare_mode=CompareMode.PRIMARY,
        panes=(
            SessionPaneBinding(
                pane_index=0,
                source_kind=SourceKind.LOCAL,
                display_name="HR",
                root_path="D:/dataset/HR",
            ),
        ),
    )

    store.save_record(record)

    assert store.list_records() == [record]


def test_session_record_store_exports_json_without_credentials(tmp_path) -> None:
    import json

    store = SessionRecordStore(tmp_path / "session_records.json")
    record = SessionRecord(
        id="record-2",
        name="remote compare",
        saved_at="2026-06-27T12:30:00+08:00",
        layout_mode="1 x 2",
        compare_mode=CompareMode.COMMON,
        panes=(
            SessionPaneBinding(
                pane_index=1,
                source_kind=SourceKind.SFTP,
                display_name="wsl:/srv/photos/LR",
                server_name="wsl",
                remote_path="/srv/photos/LR",
            ),
        ),
    )

    payload = json.loads(store.export_record_json(record))

    assert payload["name"] == "remote compare"
    assert payload["panes"][0]["server_name"] == "wsl"
    assert "password" not in json.dumps(payload)


def test_session_record_store_rejects_invalid_import_payload(tmp_path) -> None:
    store = SessionRecordStore(tmp_path / "session_records.json")

    try:
        store.parse_record_json(
            '{"version": 1, "name": "broken", "saved_at": "2026-06-27T12:00:00+08:00", '
            '"layout_mode": "2 x 2", "compare_mode": "common"}'
        )
    except ValueError as exc:
        assert "panes" in str(exc)
    else:
        raise AssertionError("Expected ValueError for incomplete payload")
