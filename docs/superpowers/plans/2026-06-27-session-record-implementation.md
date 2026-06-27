# Session Record Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manual session record save, browse, import, export, and apply workflows for layout mode, compare mode, and pane bindings.

**Architecture:** Introduce explicit session-record domain models plus a dedicated JSON-backed record store, then extend the main window and dialogs to capture and restore session snapshots. Keep persistence, JSON parsing, and validation inside focused services so UI code only coordinates user actions and apply flows.

**Tech Stack:** Python, PySide6, pytest, ruff, project-local JSON storage

---

## File Map

- Create: `src/remote_image_compare/services/session_record_store.py`
  - Persist, serialize, deserialize, import, and export saved records.
- Modify: `src/remote_image_compare/domain/models.py`
  - Add immutable session record and pane snapshot models.
- Modify: `src/remote_image_compare/domain/__init__.py`
  - Export new record-related models if the package already re-exports domain types.
- Modify: `src/remote_image_compare/ui/dialogs.py`
  - Add dialogs for save-record naming, record browser, import JSON, and optional export preview.
- Modify: `src/remote_image_compare/ui/main_window.py`
  - Add toolbar entry point, snapshot capture, record apply, import/export coordination, and missing-server validation.
- Modify: `src/remote_image_compare/app.py`
  - Wire any new top-level dependencies only if startup construction needs them.
- Create: `tests/unit/test_session_record_store.py`
  - Unit coverage for record storage and JSON import/export behavior.
- Modify: `tests/integration/test_main_window.py`
  - Integration coverage for capture/apply/import/export UI behavior.

## Task 1: Add Session Record Domain Models

**Files:**
- Modify: `src/remote_image_compare/domain/models.py`
- Modify: `src/remote_image_compare/domain/__init__.py`
- Test: `tests/unit/test_session_record_store.py`

- [ ] **Step 1: Write the failing test**

```python
from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    SessionRecord,
    SourceKind,
)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_session_record_store.py -k session_record_models_capture_remote_and_local_panes`

Expected: FAIL with import or attribute errors because `SessionRecord` and `SessionPaneBinding` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class SessionPaneBinding:
    pane_index: int
    source_kind: SourceKind
    display_name: str
    root_path: str | None = None
    server_name: str | None = None
    remote_path: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    id: str
    name: str
    saved_at: str
    layout_mode: str
    compare_mode: CompareMode
    panes: tuple[SessionPaneBinding, ...]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_session_record_store.py -k session_record_models_capture_remote_and_local_panes`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/domain/__init__.py tests/unit/test_session_record_store.py
git commit -m "feat: add session record domain models"
```

## Task 2: Add JSON-Backed Session Record Store

**Files:**
- Create: `src/remote_image_compare/services/session_record_store.py`
- Test: `tests/unit/test_session_record_store.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    SessionRecord,
    SourceKind,
)
from remote_image_compare.services.session_record_store import SessionRecordStore


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
        store.parse_record_json('{"version": 1, "name": "broken"}')
    except ValueError as exc:
        assert "panes" in str(exc)
    else:
        raise AssertionError("Expected ValueError for incomplete payload")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_session_record_store.py`

Expected: FAIL because `SessionRecordStore` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class SessionRecordStore:
    def list_records(self) -> list[SessionRecord]:
        ...

    def save_record(self, record: SessionRecord) -> None:
        ...

    def delete_record(self, record_id: str) -> None:
        ...

    def export_record_json(self, record: SessionRecord) -> str:
        ...

    def parse_record_json(self, payload: str) -> SessionRecord:
        ...
```

Implementation requirements:

- use `.remote_image_compare/session_records.json` as the default path
- persist records under `{"records": [...]}` with UTF-8 JSON and `ensure_ascii=False`
- serialize `compare_mode` and `source_kind` by `.value`
- preserve pane order by `pane_index`
- sort saved records newest first
- validate required top-level fields: `version`, `name`, `saved_at`, `layout_mode`, `compare_mode`, `panes`
- raise `ValueError` with readable messages for invalid payloads

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_session_record_store.py`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/session_record_store.py tests/unit/test_session_record_store.py
git commit -m "feat: add session record store"
```

## Task 3: Add Record Management Dialogs

**Files:**
- Modify: `src/remote_image_compare/ui/dialogs.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
from remote_image_compare.domain.models import CompareMode, SessionRecord
from remote_image_compare.ui.dialogs import (
    ImportRecordDialog,
    SaveRecordDialog,
    SessionRecordBrowserDialog,
)


def test_save_record_dialog_returns_trimmed_name(qtbot) -> None:
    dialog = SaveRecordDialog()
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("  baseline compare  ")

    assert dialog.record_name() == "baseline compare"


def test_import_record_dialog_prefers_pasted_text(qtbot) -> None:
    dialog = ImportRecordDialog()
    qtbot.addWidget(dialog)
    dialog.json_edit.setPlainText('{"version": 1}')

    assert dialog.import_text() == '{"version": 1}'


def test_session_record_browser_dialog_lists_saved_records(qtbot) -> None:
    record = SessionRecord(
        id="record-1",
        name="baseline compare",
        saved_at="2026-06-27T12:00:00+08:00",
        layout_mode="2 x 2",
        compare_mode=CompareMode.COMMON,
        panes=(),
    )
    dialog = SessionRecordBrowserDialog([record])
    qtbot.addWidget(dialog)

    assert dialog.record_list.count() == 1
    assert "baseline compare" in dialog.record_list.item(0).text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "save_record_dialog or import_record_dialog or session_record_browser_dialog"`

Expected: FAIL because the dialogs do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class SaveRecordDialog(QDialog):
    ...


class ImportRecordDialog(QDialog):
    ...


class SessionRecordBrowserDialog(QDialog):
    ...
```

Implementation requirements:

- `SaveRecordDialog` exposes `record_name() -> str`
- `ImportRecordDialog` supports pasted text and file load into a text editor widget
- `SessionRecordBrowserDialog` shows saved record summary rows and exposes the selected record/action
- keep labels and buttons in Chinese to match the existing UI

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "save_record_dialog or import_record_dialog or session_record_browser_dialog"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: add session record dialogs"
```

## Task 4: Capture and Apply Records in Main Window

**Files:**
- Modify: `src/remote_image_compare/ui/main_window.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_window_captures_current_session_record(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    left.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)

    window = MainWindow()
    qtbot.addWidget(window)
    window.layout_mode_combo.setCurrentText("1 x 2")
    window.compare_mode_combo.setCurrentText("共有文件")
    window.bind_source_path(0, str(left))

    record = window.capture_session_record("baseline compare")

    assert record.name == "baseline compare"
    assert record.layout_mode == "1 x 2"
    assert record.compare_mode.value == "common"
    assert record.panes[0].root_path == str(left)


def test_main_window_applies_record_and_restores_toolbar_state(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    left.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)

    window = MainWindow()
    qtbot.addWidget(window)
    record = window.capture_session_record("empty")
    restored = record.__class__(
        id="record-2",
        name="restore me",
        saved_at=record.saved_at,
        layout_mode="1 x 2",
        compare_mode=CompareMode.COMMON,
        panes=(
            SessionPaneBinding(
                pane_index=0,
                source_kind=SourceKind.LOCAL,
                display_name="left",
                root_path=str(left),
            ),
        ),
    )

    errors = window.apply_session_record(restored)

    assert errors == []
    assert window.layout_mode_combo.currentText() == "1 x 2"
    assert window.compare_mode_combo.currentData() == CompareMode.COMMON.value
    assert window._source_configs[0].root_path == str(left)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "captures_current_session_record or applies_record_and_restores_toolbar_state"`

Expected: FAIL because the record capture/apply methods do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def capture_session_record(self, name: str) -> SessionRecord:
    ...


def apply_session_record(self, record: SessionRecord) -> list[str]:
    ...
```

Implementation requirements:

- derive `layout_mode` from `layout_mode_combo.currentText()`
- derive `compare_mode` from `CompareMode(self.compare_mode_combo.currentData())`
- capture only currently bound panes
- use current pane index as the persisted binding target
- for SFTP panes, persist `server_name` and `remote_path` from `SourceConfig.display_name` and `root_path` only when the pane was bound through a saved server profile
- apply in the order defined by the spec: layout mode, compare mode, clear missing panes, bind panes, refresh catalog, load first item
- return a list of readable missing-server errors instead of crashing

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "captures_current_session_record or applies_record_and_restores_toolbar_state"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py
git commit -m "feat: add session record capture and apply"
```

## Task 5: Wire Toolbar Actions to Save, Browse, Import, and Export Records

**Files:**
- Modify: `src/remote_image_compare/ui/main_window.py`
- Modify: `src/remote_image_compare/ui/dialogs.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_window_exposes_record_toolbar_button(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.record_button.text() == "记录"


def test_main_window_import_record_reports_missing_server(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    record = SessionRecord(
        id="record-1",
        name="remote compare",
        saved_at="2026-06-27T12:00:00+08:00",
        layout_mode="1 x 2",
        compare_mode=CompareMode.COMMON,
        panes=(
            SessionPaneBinding(
                pane_index=0,
                source_kind=SourceKind.SFTP,
                display_name="wsl:/srv/photos/LR",
                server_name="wsl",
                remote_path="/srv/photos/LR",
            ),
        ),
    )

    errors = window.apply_session_record(record)

    assert errors == ["缺少服务器配置: wsl"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "record_toolbar_button or import_record_reports_missing_server"`

Expected: FAIL because the toolbar button and missing-server handling are incomplete.

- [ ] **Step 3: Write minimal implementation**

```python
self.record_button = QPushButton("记录")
```

Implementation requirements:

- add a `记录` button to the top toolbar with fixed sizing matching existing controls
- add handlers for:
  - save current record
  - browse/apply/delete/export saved record
  - import record from text or file
  - export current record to clipboard or file
- use `SessionRecordStore` as the source of truth
- display readable Chinese errors for missing servers and invalid imports

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "record_toolbar_button or import_record_reports_missing_server"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: add session record toolbar workflows"
```

## Task 6: Run Full Verification

**Files:**
- Modify: any files needed from previous tasks
- Test: `tests/unit/test_session_record_store.py`
- Test: `tests/integration/test_main_window.py`

- [ ] **Step 1: Run targeted tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_session_record_store.py tests\integration\test_main_window.py -k "session_record or record"`

Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS with all tests green

- [ ] **Step 3: Run lint**

Run: `.\.venv\Scripts\python.exe -m ruff check .`

Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/domain/__init__.py src/remote_image_compare/services/session_record_store.py src/remote_image_compare/ui/dialogs.py src/remote_image_compare/ui/main_window.py tests/unit/test_session_record_store.py tests/integration/test_main_window.py
git commit -m "feat: add session record workflows"
```

## Self-Review

- Spec coverage:
  - manual-only save flow is covered by Tasks 3, 4, and 5
  - local record list is covered by Tasks 2 and 3
  - JSON export/import is covered by Tasks 2, 3, and 5
  - restore of layout, compare mode, and pane bindings is covered by Task 4
  - missing-server validation is covered by Tasks 4 and 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “appropriate handling” placeholders remain
  - every testing step contains a concrete command
- Type consistency:
  - `SessionRecord`, `SessionPaneBinding`, `SessionRecordStore`, `capture_session_record`, and `apply_session_record` are used consistently across tasks

Plan complete and saved to `docs/superpowers/plans/2026-06-27-session-record-implementation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints
