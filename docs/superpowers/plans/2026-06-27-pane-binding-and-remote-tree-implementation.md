# Pane Binding And Remote Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pane-local local/remote binding actions, SSH connection testing, remote directory tree selection, and per-pane clear actions without regressing current image comparison behavior.

**Architecture:** Add a focused remote browser service for SSH connectivity and remote directory listing, extend the dialog layer with connection-test and remote tree picker workflows, and evolve each pane into a small stateful binding surface that can request local bind, remote bind, or clear while keeping network orchestration inside `MainWindow`.

**Tech Stack:** Python 3.12, PySide6, pytest, pytest-qt, Paramiko

---

### Task 1: Add remote browser service for SSH connection tests and directory listing

**Files:**
- Create: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\services\remote_browser_service.py`
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\sources\sftp_source.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\unit\test_remote_browser_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile
from remote_image_compare.services.remote_browser_service import RemoteBrowserService


def test_remote_browser_service_reports_successful_connection() -> None:
    events = []

    class FakeSftp:
        def listdir_attr(self, path):
            events.append(("listdir", path))
            return []

    class FakeClient:
        def __init__(self):
            self.connected = None

        def set_missing_host_key_policy(self, policy):
            events.append(("policy", type(policy).__name__))

        def connect(self, **kwargs):
            self.connected = kwargs
            events.append(("connect", kwargs["hostname"], kwargs["port"], kwargs["username"]))

        def open_sftp(self):
            return FakeSftp()

        def close(self):
            events.append(("close",))

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    ok, message = service.test_connection(profile)

    assert ok is True
    assert message == "连接成功"
    assert ("connect", "127.0.0.1", 2222, "tester") in events
```

```python
def test_remote_browser_service_lists_only_child_directories() -> None:
    class Attr:
        def __init__(self, filename, mode):
            self.filename = filename
            self.st_mode = mode

    class FakeSftp:
        def listdir_attr(self, path):
            assert path == "/srv/photos"
            return [
                Attr("set_a", 0o040755),
                Attr("notes.txt", 0o100644),
                Attr("set_b", 0o040755),
            ]

    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs

        def open_sftp(self):
            return FakeSftp()

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    nodes = service.list_directories(profile, "/srv/photos")

    assert [node.path for node in nodes] == ["/srv/photos/set_a", "/srv/photos/set_b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_remote_browser_service.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_browser_service`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from stat import S_ISDIR

import paramiko


@dataclass(frozen=True)
class RemoteDirectoryNode:
    name: str
    path: str
    has_children: bool = True


class RemoteBrowserService:
    def __init__(self, ssh_client_factory=None) -> None:
        self._ssh_client_factory = ssh_client_factory or paramiko.SSHClient

    def test_connection(self, profile):
        client = self._build_client(profile)
        try:
            client.close()
            return True, "连接成功"
        except paramiko.AuthenticationException:
            return False, "认证失败"

    def list_directories(self, profile, remote_path):
        client = self._build_client(profile)
        try:
            sftp = client.open_sftp()
            nodes = []
            for attr in sftp.listdir_attr(remote_path):
                if S_ISDIR(attr.st_mode):
                    nodes.append(RemoteDirectoryNode(attr.filename, f"{remote_path.rstrip('/')}/{attr.filename}"))
            return sorted(nodes, key=lambda node: node.name.casefold())
        finally:
            client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_remote_browser_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/remote_browser_service.py src/remote_image_compare/sources/sftp_source.py tests/unit/test_remote_browser_service.py
git commit -m "feat: add remote browser service"
```

### Task 2: Add pane-local empty-state actions and clear support

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\pane_widgets.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_unbound_pane_exposes_local_and_remote_bind_actions(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    assert pane.is_bound() is False
    assert pane.local_bind_button.text() == "选择本地目录"
    assert pane.remote_bind_button.text() == "选择服务器目录"
    assert pane.status_text() == "未绑定目录"
```

```python
def test_bound_pane_exposes_clear_action(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    pane.set_image(image, "img")

    assert pane.clear_button.isVisible() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_unbound_pane_exposes_local_and_remote_bind_actions tests/integration/test_main_window.py::test_bound_pane_exposes_clear_action -v`
Expected: FAIL because pane widget does not yet expose bind buttons or clear action

- [ ] **Step 3: Write minimal implementation**

```python
class ImagePaneWidget(QFrame):
    local_bind_requested = Signal()
    remote_bind_requested = Signal()
    clear_requested = Signal()

    def __init__(self, title: str) -> None:
        ...
        self.local_bind_button = QPushButton("选择本地目录")
        self.remote_bind_button = QPushButton("选择服务器目录")
        self.clear_button = QPushButton("清空")
        self.status_label = QLabel("未绑定目录")
        ...
```

Add helpers:

- `is_bound()`
- `clear_binding_state()`
- show empty-state buttons only when unbound
- show clear button only when bound

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_unbound_pane_exposes_local_and_remote_bind_actions tests/integration/test_main_window.py::test_bound_pane_exposes_clear_action -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/pane_widgets.py tests/integration/test_main_window.py
git commit -m "feat: add pane-local bind and clear actions"
```

### Task 3: Add connection test and remote tree picker dialogs

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\dialogs.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_server_profile_dialog_can_run_connection_test(qtbot) -> None:
    class FakeRemoteBrowserService:
        def test_connection(self, profile):
            assert profile.host == "127.0.0.1"
            return True, "连接成功"

    dialog = ServerProfileDialog(remote_browser_service=FakeRemoteBrowserService())
    qtbot.addWidget(dialog)
    dialog.host_edit.setText("127.0.0.1")
    dialog.username_edit.setText("tester")
    dialog.password_edit.setText("pw")

    dialog.test_connection()

    assert dialog.connection_status_label.text() == "连接成功"
```

```python
def test_remote_directory_dialog_loads_children_lazily(qtbot) -> None:
    seen = []

    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            seen.append(remote_path)
            return []

    profile = SftpServerProfile(
        name="wsl",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    dialog = RemoteDirectoryDialog(profile, FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()

    assert seen == ["/srv/photos"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_server_profile_dialog_can_run_connection_test tests/integration/test_main_window.py::test_remote_directory_dialog_loads_children_lazily -v`
Expected: FAIL because dialog support does not exist yet

- [ ] **Step 3: Write minimal implementation**

Add to `ServerProfileDialog`:

- optional `remote_browser_service`
- `测试连接` button
- inline result label
- `test_connection()` method

Add `RemoteDirectoryDialog`:

- `QTreeWidget`
- `load_root()`
- node expansion callback
- selected path label
- bind/cancel/refresh buttons

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_server_profile_dialog_can_run_connection_test tests/integration/test_main_window.py::test_remote_directory_dialog_loads_children_lazily -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: add ssh test and remote directory picker dialogs"
```

### Task 4: Orchestrate pane-local bind and clear flows in the main window

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\main_window.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_clearing_bound_pane_removes_it_from_catalog(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "img1.png").write_bytes(b"a")
    (right / "img1.png").write_bytes(b"a")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source_path(0, str(left))
    window.bind_source_path(1, str(right))

    window.clear_pane_binding(1)

    assert "pane-2" not in window._sources_by_pane
```

```python
def test_primary_mode_promotes_next_bound_pane_after_clear(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "left_only.png").write_bytes(b"a")
    (right / "right_only.png").write_bytes(b"b")

    window = MainWindow()
    qtbot.addWidget(window)
    window.compare_mode_combo.setCurrentText("主目录基准")
    window.bind_source_path(0, str(left))
    window.bind_source_path(1, str(right))

    window.clear_pane_binding(0)

    assert window.catalog_items() == ["right_only.png"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_clearing_bound_pane_removes_it_from_catalog tests/integration/test_main_window.py::test_primary_mode_promotes_next_bound_pane_after_clear -v`
Expected: FAIL because clear binding flow is not implemented

- [ ] **Step 3: Write minimal implementation**

Add to `MainWindow`:

- pane signal wiring for local bind, remote bind, clear
- `clear_pane_binding(pane_index)`
- local bind chooser handler
- remote bind chooser handler
- active-source catalog rebuild after clear

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_clearing_bound_pane_removes_it_from_catalog tests/integration/test_main_window.py::test_primary_mode_promotes_next_bound_pane_after_clear -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py
git commit -m "feat: support pane-local bind and clear orchestration"
```

### Task 5: Update documentation and verify end-to-end behavior

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\README.md`

- [ ] **Step 1: Document the new workflows**

Add a short section covering:

- server `测试连接`
- pane-local `选择本地目录`
- pane-local `选择服务器目录`
- pane `清空`

- [ ] **Step 2: Run focused integration tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: PASS

- [ ] **Step 4: Run lint**

Run: `.\.venv\Scripts\python.exe -m ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: describe pane-local binding workflow"
```
