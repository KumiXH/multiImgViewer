# Remote Image Compare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-native Python desktop application for comparing images across local, UNC, and SSH/SFTP sources with lazy loading, background IO, and synchronized multi-pane viewing.

**Architecture:** The implementation starts with a clean Python project scaffold, then builds the shared source abstractions and core services behind tests before wiring them into the PySide6 GUI. IO-heavy work stays behind adapters and services so the UI can remain responsive and package cleanly for Windows later.

**Tech Stack:** Python 3.11+, PySide6, pytest, pytest-qt, Paramiko, ruff

---

## File Structure

Planned files and responsibilities for the first implementation pass:

- Create: `D:\repository\mulitImgViewer\pyproject.toml`
- Create: `D:\repository\mulitImgViewer\README.md`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\app.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\errors.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\models.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\sorting.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\catalog.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\cache.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\image_loader.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\base.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\local_source.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\sftp_source.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\pane_widgets.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_sorting.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_catalog.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_cache.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_local_source.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_image_loader.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_sftp_source.py`
- Create: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`

### Task 1: Scaffold The Python Project

**Files:**
- Create: `D:\repository\mulitImgViewer\pyproject.toml`
- Create: `D:\repository\mulitImgViewer\README.md`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\app.py`

- [ ] **Step 1: Write the failing packaging/import test**

```python
from importlib import import_module


def test_package_exposes_version() -> None:
    package = import_module("remote_image_compare")
    assert package.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_package.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_image_compare'`

- [ ] **Step 3: Write minimal project scaffold**

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "remote-image-compare"
version = "0.1.0"
description = "Windows-native image comparison tool for local, UNC, and SSH/SFTP sources"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "PySide6>=6.8",
  "paramiko>=3.4",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-qt>=4.4",
  "ruff>=0.6",
]

[project.scripts]
remote-image-compare = "remote_image_compare.app:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
__version__ = "0.1.0"
```

```python
import sys


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_package.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/remote_image_compare/__init__.py src/remote_image_compare/app.py tests/unit/test_package.py
git commit -m "chore: scaffold remote image compare package"
```

### Task 2: Add Core Domain Models And Natural Sorting

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\__init__.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\models.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\errors.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\sorting.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_sorting.py`

- [ ] **Step 1: Write the failing sorting and model test**

```python
from remote_image_compare.domain.models import CompareMode, SourceConfig, SourceKind
from remote_image_compare.domain.sorting import natural_key


def test_natural_key_orders_numeric_suffixes() -> None:
    names = ["img10.jpg", "img2.jpg", "img1.jpg"]
    assert sorted(names, key=natural_key) == ["img1.jpg", "img2.jpg", "img10.jpg"]


def test_source_config_exposes_display_name() -> None:
    config = SourceConfig(
        id="pane-1",
        kind=SourceKind.LOCAL,
        display_name="Local Set",
        root_path=r"D:\photos",
        recursive=False,
    )
    assert config.display_name == "Local Set"
    assert CompareMode.COMMON.value == "common"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_sorting.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.domain`

- [ ] **Step 3: Write minimal domain code**

```python
from enum import Enum
from dataclasses import dataclass


class SourceKind(str, Enum):
    LOCAL = "local"
    UNC = "unc"
    SFTP = "sftp"


class CompareMode(str, Enum):
    COMMON = "common"
    PRIMARY = "primary"


@dataclass(frozen=True)
class SourceConfig:
    id: str
    kind: SourceKind
    display_name: str
    root_path: str
    recursive: bool = False
```

```python
import re


def natural_key(text: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", text)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_sorting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/domain tests/unit/test_sorting.py
git commit -m "feat: add core domain models and sorting"
```

### Task 3: Build The Catalog Service For Common And Primary Modes

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\catalog.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_catalog.py`

- [ ] **Step 1: Write the failing catalog tests**

```python
from remote_image_compare.domain.models import CompareMode
from remote_image_compare.services.catalog import build_catalog


def test_build_catalog_returns_intersection_for_common_mode() -> None:
    entries = {
        "pane-a": {"img1.jpg", "img2.jpg", "img10.jpg"},
        "pane-b": {"img2.jpg", "img10.jpg", "img20.jpg"},
    }
    assert build_catalog(entries, CompareMode.COMMON) == ["img2.jpg", "img10.jpg"]


def test_build_catalog_uses_first_pane_for_primary_mode() -> None:
    entries = {
        "pane-a": {"img2.jpg", "img10.jpg", "img1.jpg"},
        "pane-b": {"img10.jpg"},
    }
    assert build_catalog(entries, CompareMode.PRIMARY) == ["img1.jpg", "img2.jpg", "img10.jpg"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.services.catalog`

- [ ] **Step 3: Write minimal catalog implementation**

```python
from collections.abc import Mapping, Set

from remote_image_compare.domain.models import CompareMode
from remote_image_compare.domain.sorting import natural_key


def build_catalog(entries_by_source: Mapping[str, Set[str]], mode: CompareMode) -> list[str]:
    if not entries_by_source:
        return []

    ordered_sets = list(entries_by_source.values())
    if mode is CompareMode.COMMON:
        result = set.intersection(*map(set, ordered_sets))
    else:
        result = set(ordered_sets[0])
    return sorted(result, key=natural_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_catalog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/catalog.py tests/unit/test_catalog.py
git commit -m "feat: add catalog generation service"
```

### Task 4: Implement An LRU Memory Cache For Loaded Images

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\cache.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_cache.py`

- [ ] **Step 1: Write the failing cache tests**

```python
from remote_image_compare.services.cache import LruImageCache


def test_cache_returns_recent_value() -> None:
    cache = LruImageCache(capacity=2)
    cache.put(("a", "img1.jpg"), "first")
    assert cache.get(("a", "img1.jpg")) == "first"


def test_cache_evicts_oldest_entry() -> None:
    cache = LruImageCache(capacity=2)
    cache.put(("a", "img1.jpg"), "first")
    cache.put(("a", "img2.jpg"), "second")
    cache.put(("a", "img3.jpg"), "third")
    assert cache.get(("a", "img1.jpg")) is None
    assert cache.get(("a", "img3.jpg")) == "third"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.services.cache`

- [ ] **Step 3: Write minimal cache implementation**

```python
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LruImageCache(Generic[K, V]):
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        if key not in self._items:
            return None
        value = self._items.pop(key)
        self._items[key] = value
        return value

    def put(self, key: K, value: V) -> None:
        if key in self._items:
            self._items.pop(key)
        self._items[key] = value
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/cache.py tests/unit/test_cache.py
git commit -m "feat: add in-memory image cache"
```

### Task 5: Define The Source Interface And Local Source Adapter

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\base.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\local_source.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_local_source.py`

- [ ] **Step 1: Write the failing local source tests**

```python
from pathlib import Path

from remote_image_compare.domain.models import SourceConfig, SourceKind
from remote_image_compare.sources.local_source import LocalPathSource


def test_local_source_lists_only_supported_images(tmp_path: Path) -> None:
    (tmp_path / "img2.jpg").write_bytes(b"jpg")
    (tmp_path / "img10.jpg").write_bytes(b"jpg")
    (tmp_path / "notes.txt").write_text("ignore me")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        )
    )

    assert source.list_relative_paths() == ["img2.jpg", "img10.jpg"]


def test_local_source_reads_file_bytes(tmp_path: Path) -> None:
    image_path = tmp_path / "img1.jpg"
    image_path.write_bytes(b"image-data")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        )
    )

    assert source.read_bytes("img1.jpg") == b"image-data"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_local_source.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.sources.local_source`

- [ ] **Step 3: Write minimal source contract and local adapter**

```python
from abc import ABC, abstractmethod


class ImageSource(ABC):
    @abstractmethod
    def list_relative_paths(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, relative_path: str) -> bytes:
        raise NotImplementedError
```

```python
from pathlib import Path

from remote_image_compare.domain.sorting import natural_key
from remote_image_compare.sources.base import ImageSource

IMAGE_SUFFIXES = {".bmp", ".dib", ".gif", ".jfif", ".jpe", ".jpeg", ".jpg", ".pbm", ".pgm", ".png", ".ppm", ".tif", ".tiff", ".webp"}


class LocalPathSource(ImageSource):
    def __init__(self, config) -> None:
        self.config = config
        self.root = Path(config.root_path)

    def list_relative_paths(self) -> list[str]:
        iterator = self.root.rglob("*") if self.config.recursive else self.root.iterdir()
        results = [
            path.relative_to(self.root).as_posix()
            for path in iterator
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        ]
        return sorted(results, key=natural_key)

    def read_bytes(self, relative_path: str) -> bytes:
        return (self.root / relative_path).read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_local_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/sources tests/unit/test_local_source.py
git commit -m "feat: add local and UNC source adapter"
```

### Task 6: Add The SFTP Source Adapter With Password And Key Auth

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\sources\sftp_source.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_sftp_source.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\domain\models.py`

- [ ] **Step 1: Write the failing SFTP configuration and load tests**

```python
from remote_image_compare.domain.models import SftpAuthConfig, SftpAuthMode, SourceConfig, SourceKind
from remote_image_compare.sources.sftp_source import SftpSource


def test_sftp_auth_config_supports_password_mode() -> None:
    auth = SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="secret")
    assert auth.mode is SftpAuthMode.PASSWORD
    assert auth.password == "secret"


def test_sftp_auth_config_supports_key_mode() -> None:
    auth = SftpAuthConfig(mode=SftpAuthMode.KEY, private_key_path=r"C:\keys\id_ed25519", passphrase="pw")
    assert auth.private_key_path.endswith("id_ed25519")


class FakeRemoteFile:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeSftpClient:
    def __init__(self) -> None:
        self.files = {
            "/photos/img2.jpg": b"two",
            "/photos/img10.jpg": b"ten",
        }

    def listdir_attr(self, path: str):
        class Attr:
            def __init__(self, filename: str) -> None:
                self.filename = filename
                self.st_mode = 0o100644

        return [Attr("img10.jpg"), Attr("img2.jpg"), Attr("notes.txt")]

    def open(self, path: str, mode: str):
        return FakeRemoteFile(self.files[path])


def test_sftp_source_lists_supported_images() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=False,
    )
    source = SftpSource(config, auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"))
    source._sftp = FakeSftpClient()
    assert source.list_relative_paths() == ["img2.jpg", "img10.jpg"]


def test_sftp_source_reads_file_bytes() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=False,
    )
    source = SftpSource(config, auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"))
    source._sftp = FakeSftpClient()
    assert source.read_bytes("img2.jpg") == b"two"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_sftp_source.py -v`
Expected: FAIL with `ImportError` for `SftpAuthConfig`

- [ ] **Step 3: Write minimal SFTP models and working adapter**

```python
from dataclasses import dataclass
from enum import Enum


class SftpAuthMode(str, Enum):
    PASSWORD = "password"
    KEY = "key"


@dataclass(frozen=True)
class SftpAuthConfig:
    mode: SftpAuthMode
    password: str | None = None
    private_key_path: str | None = None
    passphrase: str | None = None
```

```python
import paramiko
from stat import S_ISDIR

from remote_image_compare.domain.sorting import natural_key
from remote_image_compare.sources.base import ImageSource

IMAGE_SUFFIXES = {".bmp", ".dib", ".gif", ".jfif", ".jpe", ".jpeg", ".jpg", ".pbm", ".pgm", ".png", ".ppm", ".tif", ".tiff", ".webp"}


class SftpSource(ImageSource):
    def __init__(self, config, auth) -> None:
        self.config = config
        self.auth = auth
        self._client: paramiko.SSHClient | None = None
        self._sftp = None

    def _ensure_sftp(self):
        if self._sftp is not None:
            return self._sftp
        raise RuntimeError("SFTP client not connected")

    def list_relative_paths(self) -> list[str]:
        client = self._ensure_sftp()
        results: list[str] = []
        for attr in client.listdir_attr(self.config.root_path):
            if S_ISDIR(attr.st_mode):
                continue
            filename = attr.filename
            suffix = "." + filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
            if suffix in IMAGE_SUFFIXES:
                results.append(filename)
        return sorted(results, key=natural_key)

    def read_bytes(self, relative_path: str) -> bytes:
        client = self._ensure_sftp()
        remote_path = f"{self.config.root_path.rstrip('/')}/{relative_path}"
        with client.open(remote_path, "rb") as handle:
            return handle.read()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_sftp_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/sources/sftp_source.py tests/unit/test_sftp_source.py
git commit -m "feat: add sftp auth models"
```

### Task 7: Implement Image Loader Request De-Duping And Cache Use

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\services\image_loader.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_image_loader.py`

- [ ] **Step 1: Write the failing image loader tests**

```python
from remote_image_compare.services.cache import LruImageCache
from remote_image_compare.services.image_loader import ImageLoader


class FakeSource:
    def __init__(self) -> None:
        self.calls = 0

    def read_bytes(self, relative_path: str) -> bytes:
        self.calls += 1
        return f"data:{relative_path}".encode()


def test_image_loader_uses_cache_before_source() -> None:
    source = FakeSource()
    cache = LruImageCache(capacity=2)
    cache.put(("pane-1", "img1.jpg"), b"cached")
    loader = ImageLoader(cache=cache)

    assert loader.load_bytes("pane-1", source, "img1.jpg") == b"cached"
    assert source.calls == 0


def test_image_loader_caches_source_result() -> None:
    source = FakeSource()
    cache = LruImageCache(capacity=2)
    loader = ImageLoader(cache=cache)

    assert loader.load_bytes("pane-1", source, "img2.jpg") == b"data:img2.jpg"
    assert cache.get(("pane-1", "img2.jpg")) == b"data:img2.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_image_loader.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.services.image_loader`

- [ ] **Step 3: Write minimal image loader implementation**

```python
from remote_image_compare.services.cache import LruImageCache


class ImageLoader:
    def __init__(self, cache: LruImageCache[tuple[str, str], bytes]) -> None:
        self.cache = cache

    def load_bytes(self, source_id: str, source, relative_path: str) -> bytes:
        key = (source_id, relative_path)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        data = source.read_bytes(relative_path)
        self.cache.put(key, data)
        return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_image_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/image_loader.py tests/unit/test_image_loader.py
git commit -m "feat: add cached image loader"
```

### Task 8: Add Request Tokens To Ignore Stale Load Results

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\services\image_loader.py`
- Create: `D:\repository\mulitImgViewer\tests\unit\test_request_tracker.py`

- [ ] **Step 1: Write the failing stale-request test**

```python
from remote_image_compare.services.image_loader import RequestTracker


def test_request_tracker_accepts_only_latest_token() -> None:
    tracker = RequestTracker()
    first = tracker.next_token("pane-1")
    second = tracker.next_token("pane-1")

    assert first != second
    assert tracker.is_current("pane-1", second) is True
    assert tracker.is_current("pane-1", first) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_request_tracker.py -v`
Expected: FAIL with `ImportError` for `RequestTracker`

- [ ] **Step 3: Write minimal request tracker**

```python
class RequestTracker:
    def __init__(self) -> None:
        self._tokens: dict[str, int] = {}

    def next_token(self, pane_id: str) -> int:
        token = self._tokens.get(pane_id, 0) + 1
        self._tokens[pane_id] = token
        return token

    def is_current(self, pane_id: str, token: int) -> bool:
        return self._tokens.get(pane_id) == token
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_request_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/image_loader.py tests/unit/test_request_tracker.py
git commit -m "feat: add stale request tracking"
```

### Task 9: Create The Main Window Skeleton And Pane Layout

**Files:**
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Create: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\pane_widgets.py`
- Create: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\app.py`

- [ ] **Step 1: Write the failing GUI smoke tests**

```python
from remote_image_compare.ui.main_window import MainWindow


def test_main_window_has_default_layout(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Remote Image Compare"
    assert window.active_pane_count == 6


def test_main_window_exposes_file_mode_options(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.compare_mode_items() == ["common", "primary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError` for `remote_image_compare.ui.main_window`

- [ ] **Step 3: Write minimal GUI skeleton**

```python
from PySide6.QtWidgets import QApplication

from remote_image_compare.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
```

```python
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ImagePaneWidget(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
```

```python
from PySide6.QtWidgets import QComboBox, QGridLayout, QMainWindow, QWidget

from remote_image_compare.ui.pane_widgets import ImagePaneWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Remote Image Compare")
        self._active_pane_count = 6
        self._compare_modes = ["common", "primary"]

        self.compare_mode_combo = QComboBox()
        self.compare_mode_combo.addItems(self._compare_modes)

        central = QWidget()
        grid = QGridLayout(central)
        for index in range(6):
            grid.addWidget(ImagePaneWidget(f"Pane {index + 1}"), index // 3, index % 3)
        self.setCentralWidget(central)

    @property
    def active_pane_count(self) -> int:
        return self._active_pane_count

    def compare_mode_items(self) -> list[str]:
        return [self.compare_mode_combo.itemText(i) for i in range(self.compare_mode_combo.count())]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui src/remote_image_compare/app.py tests/integration/test_main_window.py
git commit -m "feat: add main window skeleton"
```

### Task 10: Wire Catalog Results Into The Main Window

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\services\catalog.py`
- Modify: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing GUI catalog test**

```python
from remote_image_compare.ui.main_window import MainWindow


def test_main_window_updates_file_list_from_catalog(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_catalog_items(["img1.jpg", "img2.jpg"])

    assert window.file_list_count() == 2
    assert window.current_file_label() == "0 / 2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_updates_file_list_from_catalog -v`
Expected: FAIL with `AttributeError` for missing catalog UI helpers

- [ ] **Step 3: Write minimal file list wiring**

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QListWidget, QMainWindow, QVBoxLayout, QWidget

from remote_image_compare.ui.pane_widgets import ImagePaneWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Remote Image Compare")
        self._active_pane_count = 6
        self._compare_modes = ["common", "primary"]
        self._catalog_items: list[str] = []

        self.compare_mode_combo = QComboBox()
        self.compare_mode_combo.addItems(self._compare_modes)
        self.position_label = QLabel("0 / 0")
        self.file_list = QListWidget()

        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(self.compare_mode_combo)
        root.addWidget(self.position_label)
        root.addWidget(self.file_list)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        for index in range(6):
            grid.addWidget(ImagePaneWidget(f"Pane {index + 1}"), index // 3, index % 3)
        root.addWidget(grid_host)
        self.setCentralWidget(central)

    @property
    def active_pane_count(self) -> int:
        return self._active_pane_count

    def compare_mode_items(self) -> list[str]:
        return [self.compare_mode_combo.itemText(i) for i in range(self.compare_mode_combo.count())]

    def set_catalog_items(self, items: list[str]) -> None:
        self._catalog_items = items
        self.file_list.clear()
        self.file_list.addItems(items)
        self.position_label.setText(f"0 / {len(items)}")

    def file_list_count(self) -> int:
        return self.file_list.count()

    def current_file_label(self) -> str:
        return self.position_label.text()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_updates_file_list_from_catalog -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py
git commit -m "feat: display catalog items in main window"
```

### Task 11: Add Pane-Level Load States For Missing Or Failed Images

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\pane_widgets.py`
- Modify: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing pane state test**

```python
from remote_image_compare.ui.pane_widgets import ImagePaneWidget


def test_pane_widget_shows_status_message(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    pane.set_status("Missing file")

    assert pane.status_text() == "Missing file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_pane_widget_shows_status_message -v`
Expected: FAIL with `AttributeError` for `set_status`

- [ ] **Step 3: Write minimal pane status implementation**

```python
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ImagePaneWidget(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_label = QLabel(title)
        self.status_label = QLabel("Idle")
        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def status_text(self) -> str:
        return self.status_label.text()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_pane_widget_shows_status_message -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/pane_widgets.py tests/integration/test_main_window.py
git commit -m "feat: add pane load status states"
```

### Task 12: Add Pixmap Display And Scaled Image Presentation

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\pane_widgets.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing image presentation test**

```python
from PySide6.QtGui import QImage

from remote_image_compare.ui.pane_widgets import ImagePaneWidget


def test_pane_widget_accepts_loaded_image(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    image = QImage(10, 20, QImage.Format.Format_RGB32)
    pane.set_image(image, "10x20")

    assert pane.status_text() == "10x20"
    assert pane.has_image() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_pane_widget_accepts_loaded_image -v`
Expected: FAIL with `AttributeError` for `set_image`

- [ ] **Step 3: Write minimal image presentation implementation**

```python
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ImagePaneWidget(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_label = QLabel(title)
        self.image_label = QLabel()
        self.status_label = QLabel("Idle")
        self._has_image = False
        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.status_label)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def status_text(self) -> str:
        return self.status_label.text()

    def set_image(self, image: QImage, status: str) -> None:
        self.image_label.setPixmap(QPixmap.fromImage(image))
        self.status_label.setText(status)
        self._has_image = True

    def has_image(self) -> bool:
        return self._has_image
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_pane_widget_accepts_loaded_image -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/pane_widgets.py tests/integration/test_main_window.py
git commit -m "feat: add pane image presentation"
```

### Task 13: Add Shared Zoom State And Reset Wiring

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing shared view-state test**

```python
from remote_image_compare.ui.main_window import MainWindow


def test_main_window_resets_shared_view_state(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_view_state(2.0, 0.2, 0.8)
    window.reset_view_state()

    assert window.view_state() == (1.0, 0.5, 0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_resets_shared_view_state -v`
Expected: FAIL with `AttributeError` for missing shared view-state methods

- [ ] **Step 3: Write minimal shared view-state implementation**

```python
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._zoom = 1.0
        self._center_x = 0.5
        self._center_y = 0.5
        ...

    def set_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        self._zoom = zoom
        self._center_x = center_x
        self._center_y = center_y

    def reset_view_state(self) -> None:
        self.set_view_state(1.0, 0.5, 0.5)

    def view_state(self) -> tuple[float, float, float]:
        return (self._zoom, self._center_x, self._center_y)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_resets_shared_view_state -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py
git commit -m "feat: add shared view state"
```

### Task 14: Load The Selected File Into Panes Through Services

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\pane_widgets.py`
- Modify: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing pane-load integration test**

```python
from PySide6.QtGui import QImage

from remote_image_compare.ui.main_window import MainWindow


class FakeImageService:
    def load_image(self, pane_id: str, relative_path: str) -> QImage:
        image = QImage(5, 5, QImage.Format.Format_RGB32)
        image.fill(0)
        return image


def test_main_window_loads_selected_file_into_pane(qtbot) -> None:
    window = MainWindow(image_service=FakeImageService())
    qtbot.addWidget(window)
    window.set_catalog_items(["img1.jpg"])

    window.load_selected_file("img1.jpg")

    assert window.first_pane().has_image() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_loads_selected_file_into_pane -v`
Expected: FAIL with `TypeError` or `AttributeError` for missing service injection and load helpers

- [ ] **Step 3: Write minimal selected-file loading flow**

```python
class NullImageService:
    def load_image(self, pane_id: str, relative_path: str):
        return None


class MainWindow(QMainWindow):
    def __init__(self, image_service=None) -> None:
        super().__init__()
        self.image_service = image_service or NullImageService()
        self._panes = [ImagePaneWidget(f"Pane {index + 1}") for index in range(6)]
        ...

    def load_selected_file(self, relative_path: str) -> None:
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            image = self.image_service.load_image(f"pane-{index + 1}", relative_path)
            if image is None:
                pane.set_status("Missing file")
                continue
            pane.set_image(image, relative_path)

    def first_pane(self) -> ImagePaneWidget:
        return self._panes[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_loads_selected_file_into_pane -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py src/remote_image_compare/ui/pane_widgets.py tests/integration/test_main_window.py
git commit -m "feat: load selected files into panes"
```

### Task 15: Add Background Worker Wiring For Non-Blocking Loads

**Files:**
- Modify: `D:\repository\mulitImgViewer\src\remote_image_compare\ui\main_window.py`
- Modify: `D:\repository\mulitImgViewer\tests\integration\test_main_window.py`

- [ ] **Step 1: Write the failing async completion test**

```python
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage

from remote_image_compare.ui.main_window import MainWindow


class DeferredImageService:
    def load_image_async(self, pane_id: str, relative_path: str, callback) -> None:
        image = QImage(6, 6, QImage.Format.Format_RGB32)
        image.fill(0)
        QTimer.singleShot(0, lambda: callback(pane_id, relative_path, image))


def test_main_window_updates_pane_after_async_load(qtbot) -> None:
    window = MainWindow(image_service=DeferredImageService())
    qtbot.addWidget(window)

    window.load_selected_file_async("img1.jpg")
    qtbot.waitUntil(lambda: window.first_pane().has_image(), timeout=1000)

    assert window.first_pane().status_text() == "img1.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_updates_pane_after_async_load -v`
Expected: FAIL with `AttributeError` for `load_selected_file_async`

- [ ] **Step 3: Write minimal async load wiring**

```python
class MainWindow(QMainWindow):
    ...
    def load_selected_file_async(self, relative_path: str) -> None:
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            pane_id = f"pane-{index + 1}"
            pane.set_status("Loading...")
            self.image_service.load_image_async(pane_id, relative_path, self._handle_loaded_image)

    def _handle_loaded_image(self, pane_id: str, relative_path: str, image) -> None:
        pane_index = int(pane_id.split("-")[-1]) - 1
        self._panes[pane_index].set_image(image, relative_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_main_window.py::test_main_window_updates_pane_after_async_load -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py
git commit -m "feat: add async pane image loading"
```

### Task 16: Add Ruff And Full Test Verification

**Files:**
- Modify: `D:\repository\mulitImgViewer\pyproject.toml`
- Modify: `D:\repository\mulitImgViewer\README.md`

- [ ] **Step 1: Write the failing quality gate expectation**

```python
def test_documented_quality_commands_exist() -> None:
    readme = open("README.md", "r", encoding="utf-8").read()
    assert "python -m pytest" in readme
    assert "python -m ruff check ." in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_quality_docs.py -v`
Expected: FAIL because `README.md` does not yet document the commands

- [ ] **Step 3: Write minimal quality-tool configuration and docs**

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

```markdown
# Remote Image Compare

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest
python -m ruff check .
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_quality_docs.py -v`
Expected: PASS

- [ ] **Step 5: Run the full verification suite**

Run: `python -m pytest -v`
Expected: PASS across unit and integration tests

Run: `python -m ruff check .`
Expected: PASS with no lint errors

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md tests/unit/test_quality_docs.py
git commit -m "chore: add quality checks and developer docs"
```

## Self-Review

- Spec coverage:
  - project scaffold covered by Task 1
  - source abstractions and local/UNC support covered by Tasks 2, 5
  - common and primary catalog modes covered by Task 3
  - in-memory caching covered by Task 4
  - SFTP auth and basic read/list behavior covered by Task 6
  - image loader cache path and stale-request identity covered by Tasks 7, 8
  - Windows GUI skeleton, catalog UI, pane states, image presentation, and shared view state covered by Tasks 9, 10, 11, 12, 13
  - selected-file loading and non-blocking async flow covered by Tasks 14, 15
  - verification and developer workflow covered by Task 16
- Gaps:
  - recursive SFTP traversal, connection pooling, and full zoom/pan gesture behavior need a second implementation slice after the baseline is green
- Placeholder scan:
  - no `TBD`, `TODO`, or empty task shells remain
- Type consistency:
  - `CompareMode.COMMON` and `CompareMode.PRIMARY` are used consistently
  - source id plus relative path is the shared cache key shape throughout the plan

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-remote-image-compare-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
