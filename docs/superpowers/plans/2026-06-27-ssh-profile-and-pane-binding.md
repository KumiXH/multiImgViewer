# SSH Profile Persistence And Pane Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add saved SSH server profiles, persist them on disk, and let each image pane bind either a local folder or a saved remote server plus remote path from the running Windows UI.

**Architecture:** Add a small JSON-backed profile store in the service layer, introduce dedicated UI dialogs for managing saved SSH servers and binding a pane to either a local or remote source, and thread the resulting saved connection data through `MainWindow.bind_source()` into the existing source factory. Keep remote selection simple in V1 by using saved server selection plus a typed remote path instead of a full remote directory tree browser.

**Tech Stack:** Python 3.12, PySide6, pytest, pytest-qt, Paramiko

---

### Task 1: Add persisted SSH profile storage

**Files:**
- Create: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\services\server_profile_store.py`
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\domain\models.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\unit\test_server_profile_store.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from remote_image_compare.domain.models import (
    SftpAuthMode,
    SftpServerProfile,
)
from remote_image_compare.services.server_profile_store import ServerProfileStore


def test_server_profile_store_round_trips_profiles(tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    profile = SftpServerProfile(
        name="lab",
        host="192.168.1.9",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.KEY,
        password="",
        private_key_path=r"C:\keys\id_ed25519",
        passphrase="secret",
        default_root="/srv/photos",
    )

    store.save_profile(profile)

    reloaded = ServerProfileStore(tmp_path / "profiles.json").list_profiles()
    assert reloaded == [profile]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_server_profile_store.py::test_server_profile_store_round_trips_profiles -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `SftpServerProfile` or `ServerProfileStore`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import asdict, dataclass
from json import dumps, loads
from pathlib import Path

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile


class ServerProfileStore:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = Path(storage_path)

    def list_profiles(self) -> list[SftpServerProfile]:
        if not self.storage_path.exists():
            return []
        payload = loads(self.storage_path.read_text(encoding="utf-8"))
        return [
            SftpServerProfile(
                name=item["name"],
                host=item["host"],
                port=item["port"],
                username=item["username"],
                auth_mode=SftpAuthMode(item["auth_mode"]),
                password=item.get("password", ""),
                private_key_path=item.get("private_key_path"),
                passphrase=item.get("passphrase"),
                default_root=item.get("default_root", ""),
            )
            for item in payload.get("profiles", [])
        ]

    def save_profile(self, profile: SftpServerProfile) -> None:
        profiles = [item for item in self.list_profiles() if item.name != profile.name]
        profiles.append(profile)
        payload = {"profiles": [{**asdict(item), "auth_mode": item.auth_mode.value} for item in profiles]}
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_server_profile_store.py::test_server_profile_store_round_trips_profiles -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/services/server_profile_store.py tests/unit/test_server_profile_store.py
git commit -m "feat: persist ssh server profiles"
```

### Task 2: Add profile management and pane binding workflows to the UI

**Files:**
- Create: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\dialogs.py`
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\main_window.py`
- Test: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile
from remote_image_compare.services.server_profile_store import ServerProfileStore
from remote_image_compare.ui.main_window import MainWindow


def test_main_window_loads_saved_server_profiles(qtbot, tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    store.save_profile(
        SftpServerProfile(
            name="studio",
            host="10.0.0.8",
            port=22,
            username="kumi",
            auth_mode=SftpAuthMode.PASSWORD,
            password="pw",
            private_key_path=None,
            passphrase="",
            default_root="/data/photos",
        )
    )

    window = MainWindow(profile_store=store)
    qtbot.addWidget(window)

    assert window.saved_server_names() == ["studio"]
```

```python
def test_main_window_bind_remote_profile_uses_selected_server(qtbot) -> None:
    created = {}

    def fake_source_factory(config, auth=None, connection=None):
        created["config"] = config
        created["auth"] = auth
        created["connection"] = connection

        class FakeSource:
            def list_relative_paths(self) -> list[str]:
                return ["remote.png"]

            def read_bytes(self, relative_path: str) -> bytes:
                return b""

        return FakeSource()

    profile = SftpServerProfile(
        name="wsl",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        private_key_path=None,
        passphrase="",
        default_root="/srv/photos",
    )
    window = MainWindow(source_factory=fake_source_factory)
    qtbot.addWidget(window)

    window.bind_remote_profile(0, profile, "/srv/photos/setA")

    assert created["config"].kind.value == "sftp"
    assert created["config"].root_path == "/srv/photos/setA"
    assert created["connection"].host == "127.0.0.1"
    assert created["auth"].password == "pw"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_main_window_loads_saved_server_profiles tests/integration/test_main_window.py::test_main_window_bind_remote_profile_uses_selected_server -v`
Expected: FAIL because `MainWindow` lacks profile loading helpers and remote bind workflow

- [ ] **Step 3: Write minimal implementation**

```python
class MainWindow(QMainWindow):
    def __init__(self, image_service=None, source_factory=None, profile_store=None) -> None:
        ...
        self.profile_store = profile_store or ServerProfileStore(default_profile_store_path())
        self._server_profiles = {profile.name: profile for profile in self.profile_store.list_profiles()}
        ...

    def saved_server_names(self) -> list[str]:
        return sorted(self._server_profiles)

    def bind_remote_profile(self, pane_index: int, profile: SftpServerProfile, remote_path: str) -> None:
        config = SourceConfig(
            id=f"pane-{pane_index + 1}",
            kind=SourceKind.SFTP,
            display_name=f"{profile.name}:{remote_path}",
            root_path=remote_path,
            recursive=False,
        )
        auth = profile.to_auth_config()
        connection = profile.to_connection_config()
        self.bind_source(pane_index, config, auth=auth, connection=connection)
        self.refresh_catalog()
        self.load_first_catalog_item_if_available()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_main_window_loads_saved_server_profiles tests/integration/test_main_window.py::test_main_window_bind_remote_profile_uses_selected_server -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: add saved server and remote pane binding workflows"
```

### Task 3: Wire top-level controls for profile management and pane source selection

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\src\remote_image_compare\ui\main_window.py`
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\tests\integration\test_main_window.py`
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\README.md`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_window_exposes_source_binding_controls(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.server_manager_button.text() == "服务器"
    assert window.bind_source_button.text() == "绑定窗口"
```

```python
def test_main_window_toolbar_keeps_binding_controls_in_top_row(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.top_toolbar_layout.itemAt(1).widget() is window.server_manager_button
    assert window.top_toolbar_layout.itemAt(2).widget() is window.bind_source_button
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_main_window_exposes_source_binding_controls tests/integration/test_main_window.py::test_main_window_toolbar_keeps_binding_controls_in_top_row -v`
Expected: FAIL because toolbar buttons do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
self.server_manager_button = QPushButton("服务器")
self.server_manager_button.setFixedSize(120, 36)
self.bind_source_button = QPushButton("绑定窗口")
self.bind_source_button.setFixedSize(120, 36)

self.top_toolbar_layout.addWidget(self.toggle_sidebar_button)
self.top_toolbar_layout.addWidget(self.server_manager_button)
self.top_toolbar_layout.addWidget(self.bind_source_button)
self.top_toolbar_layout.addWidget(self.compare_mode_combo)
self.top_toolbar_layout.addWidget(self.layout_mode_combo)
```

Update `README.md` with a short section describing:

- launch the app without `--source`
- click `服务器` to save an SSH server profile
- click `绑定窗口` to assign a local folder or saved remote path to a pane

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_main_window.py::test_main_window_exposes_source_binding_controls tests/integration/test_main_window.py::test_main_window_toolbar_keeps_binding_controls_in_top_row -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py README.md
git commit -m "feat: add pane source binding controls"
```

### Task 4: Verify the end-to-end feature set

**Files:**
- Modify: `D:\repository\mulitImgViewer\.worktrees\remote-image-compare-v1\docs\superpowers\plans\2026-06-27-ssh-profile-and-pane-binding.md`

- [ ] **Step 1: Run targeted UI and storage tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_server_profile_store.py tests/integration/test_main_window.py -v`
Expected: PASS

- [ ] **Step 2: Run full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: PASS

- [ ] **Step 3: Run lint**

Run: `.\.venv\Scripts\python.exe -m ruff check .`
Expected: PASS

- [ ] **Step 4: Commit verification-safe documentation updates if needed**

```bash
git add docs/superpowers/plans/2026-06-27-ssh-profile-and-pane-binding.md
git commit -m "docs: record ssh pane binding implementation plan"
```
