# Tolerance Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-on-top floating tolerance map window that compares two selected panes for the current image, supports threshold and algorithm switching, shows RGB/coordinate inspection, and allows zooming/panning inside the tolerance view.

**Architecture:** Introduce a focused tolerance computation service for resize, scalar diff calculation, color mapping, and pixel sampling; then add a dedicated floating tool window and tolerance viewport UI that consume current pane images from the main window. Keep hover mapping and UI orchestration in the window layer, while placing math and image generation in testable services.

**Tech Stack:** Python, PySide6, pytest, ruff, QImage/QPixmap image processing

---

## File Map

- Modify: `src/remote_image_compare/domain/models.py`
  - Add tolerance algorithm enum and any lightweight analysis result models.
- Modify: `src/remote_image_compare/domain/__init__.py`
  - Re-export new tolerance domain types if needed.
- Create: `src/remote_image_compare/services/tolerance_map_service.py`
  - Resize source images, compute scalar differences, colorize tolerance maps, and sample RGB/difference values.
- Modify: `src/remote_image_compare/ui/pane_widgets.py`
  - Expose hover callbacks or signals from loaded image panes with image-relative coordinates.
- Modify: `src/remote_image_compare/ui/dialogs.py`
  - Add floating tolerance window and specialized tolerance viewport widget.
- Modify: `src/remote_image_compare/ui/main_window.py`
  - Add toolbar button, open/reuse floating window, feed it current pane image state, and update it on navigation/load/hover.
- Create: `tests/unit/test_tolerance_map_service.py`
  - Cover algorithms, threshold coloring, resize behavior, and sampling.
- Modify: `tests/integration/test_main_window.py`
  - Cover toolbar button, floating window creation, pane selection, threshold refresh, algorithm refresh, and hover-driven RGB updates.

## Task 1: Add Tolerance Domain Types

**Files:**
- Modify: `src/remote_image_compare/domain/models.py`
- Modify: `src/remote_image_compare/domain/__init__.py`
- Test: `tests/unit/test_tolerance_map_service.py`

- [ ] **Step 1: Write the failing test**

```python
from remote_image_compare.domain.models import ToleranceAlgorithm


def test_tolerance_algorithm_values_are_stable() -> None:
    assert ToleranceAlgorithm.MAX_CHANNEL.value == "max_channel"
    assert ToleranceAlgorithm.AVERAGE.value == "average"
    assert ToleranceAlgorithm.EUCLIDEAN.value == "euclidean"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_tolerance_map_service.py -k tolerance_algorithm_values_are_stable`

Expected: FAIL because `ToleranceAlgorithm` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class ToleranceAlgorithm(str, Enum):
    MAX_CHANNEL = "max_channel"
    AVERAGE = "average"
    EUCLIDEAN = "euclidean"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_tolerance_map_service.py -k tolerance_algorithm_values_are_stable`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/domain/__init__.py tests/unit/test_tolerance_map_service.py
git commit -m "feat: add tolerance algorithm enum"
```

## Task 2: Add Tolerance Map Service

**Files:**
- Create: `src/remote_image_compare/services/tolerance_map_service.py`
- Test: `tests/unit/test_tolerance_map_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from PySide6.QtGui import QImage, QColor

from remote_image_compare.domain.models import ToleranceAlgorithm
from remote_image_compare.services.tolerance_map_service import ToleranceMapService


def _filled_image(width: int, height: int, color: tuple[int, int, int]) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(*color))
    return image


def test_tolerance_service_uses_red_blue_gray_threshold_colors() -> None:
    service = ToleranceMapService()
    left = _filled_image(1, 1, (10, 10, 10))
    right = _filled_image(1, 1, (20, 20, 20))

    blue_map = service.build_tolerance_map(left, right, tolerance=15, algorithm=ToleranceAlgorithm.MAX_CHANNEL)
    equal_map = service.build_tolerance_map(left, right, tolerance=10, algorithm=ToleranceAlgorithm.MAX_CHANNEL)
    red_map = service.build_tolerance_map(left, right, tolerance=5, algorithm=ToleranceAlgorithm.MAX_CHANNEL)

    assert blue_map.pixelColor(0, 0) == QColor(0, 0, 255)
    assert equal_map.pixelColor(0, 0) == QColor(128, 128, 128)
    assert red_map.pixelColor(0, 0) == QColor(255, 0, 0)


def test_tolerance_service_resizes_images_to_common_size() -> None:
    service = ToleranceMapService()
    left = _filled_image(4, 4, (10, 10, 10))
    right = _filled_image(2, 2, (10, 10, 10))

    tolerance_map = service.build_tolerance_map(
        left,
        right,
        tolerance=0,
        algorithm=ToleranceAlgorithm.AVERAGE,
    )

    assert tolerance_map.size() == left.size()


def test_tolerance_service_samples_rgb_and_difference() -> None:
    service = ToleranceMapService()
    left = _filled_image(2, 2, (10, 20, 30))
    right = _filled_image(2, 2, (13, 22, 31))
    result = service.prepare_comparison(
        left,
        right,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
    )

    sample = service.sample_at(result, 0.5, 0.5)

    assert sample.left_rgb == (10, 20, 30)
    assert sample.right_rgb == (13, 22, 31)
    assert sample.difference == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_tolerance_map_service.py`

Expected: FAIL because `ToleranceMapService` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class ToleranceMapService:
    def prepare_comparison(self, left: QImage, right: QImage, algorithm: ToleranceAlgorithm):
        ...

    def build_tolerance_map(self, left: QImage, right: QImage, tolerance: int, algorithm: ToleranceAlgorithm) -> QImage:
        ...

    def sample_at(self, prepared, normalized_x: float, normalized_y: float):
        ...
```

Implementation requirements:

- resize the right image to match the left image size for first-version determinism
- compute scalar differences for all three algorithms
- map threshold result colors exactly to red `(255, 0, 0)`, blue `(0, 0, 255)`, gray `(128, 128, 128)`
- return structured sample data with left RGB, right RGB, and scalar difference
- keep logic free of window-layer dependencies

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_tolerance_map_service.py`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/services/tolerance_map_service.py tests/unit/test_tolerance_map_service.py
git commit -m "feat: add tolerance map service"
```

## Task 3: Add Floating Tolerance Window UI

**Files:**
- Modify: `src/remote_image_compare/ui/dialogs.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
from remote_image_compare.domain.models import ToleranceAlgorithm
from remote_image_compare.ui.dialogs import ToleranceWindow


def test_tolerance_window_exposes_algorithm_choices(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)

    assert window.algorithm_combo.count() == 3
    assert window.algorithm_combo.currentData() == ToleranceAlgorithm.MAX_CHANNEL


def test_tolerance_window_limits_selection_to_two_panes(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2", "Pane 3"])

    window.pane_checks[0].setChecked(True)
    window.pane_checks[1].setChecked(True)
    window.pane_checks[2].setChecked(True)

    assert sum(1 for check in window.pane_checks if check.isChecked()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_window_exposes_algorithm_choices or tolerance_window_limits_selection_to_two_panes"`

Expected: FAIL because `ToleranceWindow` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class ToleranceWindow(QDialog):
    ...
```

Implementation requirements:

- set window modality to non-modal
- set always-on-top window flag
- include pane selection controls, algorithm combo, tolerance slider, image viewport area, and status labels
- expose `set_available_panes(...)`
- enforce at most two checked panes
- keep first version labels in Chinese

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_window_exposes_algorithm_choices or tolerance_window_limits_selection_to_two_panes"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: add floating tolerance window"
```

## Task 4: Add Hover Reporting From Image Panes

**Files:**
- Modify: `src/remote_image_compare/ui/pane_widgets.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pane_widget_emits_hover_signal_for_loaded_image(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(320, 240)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(100, 100, QImage.Format.Format_RGB32)
    image.fill(0xFF224466)
    pane.set_image(image, "hover")

    seen = []
    pane.hover_position_changed.connect(lambda x, y: seen.append((x, y)))

    qtbot.mouseMove(pane.image_viewport, QPoint(50, 50))

    assert seen
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k pane_widget_emits_hover_signal_for_loaded_image`

Expected: FAIL because the hover signal does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
hover_position_changed = Signal(float, float)
```

Implementation requirements:

- emit normalized image-relative coordinates from the pane viewport on mouse move when an image is loaded
- avoid emitting meaningless hover data when no image is loaded
- keep existing drag and zoom behavior intact

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k pane_widget_emits_hover_signal_for_loaded_image`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/pane_widgets.py tests/integration/test_main_window.py
git commit -m "feat: add pane hover reporting"
```

## Task 5: Wire Main Window to the Floating Tolerance Tool

**Files:**
- Modify: `src/remote_image_compare/ui/main_window.py`
- Modify: `src/remote_image_compare/ui/dialogs.py`
- Modify: `tests/integration/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_window_exposes_tolerance_button(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.tolerance_button.text() == "容差图"


def test_tolerance_button_opens_floating_window(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.open_tolerance_window()

    assert window._tolerance_window is not None
    assert window._tolerance_window.isVisible() is True


def test_navigation_updates_open_tolerance_window(qtbot, tmp_path: Path) -> None:
    for index in range(1, 3):
        image = QImage(8, 8, QImage.Format.Format_RGB32)
        image.fill(index)
        assert image.save(str(tmp_path / f"img{index}.png"), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local A",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Local B",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.open_tolerance_window()
    window._tolerance_window.set_selected_panes([0, 1])

    window.next_image()

    assert window._tolerance_window.current_filename_label.text() == "img2.png"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_button or navigation_updates_open_tolerance_window"`

Expected: FAIL because the tolerance button and window wiring do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
self.tolerance_button = QPushButton("容差图")
```

Implementation requirements:

- add a `容差图` toolbar button with fixed sizing
- add `open_tolerance_window()`
- reuse one floating window instance
- keep the window updated when current image changes
- push available pane labels and loaded images into the floating window

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_button or navigation_updates_open_tolerance_window"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/main_window.py src/remote_image_compare/ui/dialogs.py tests/integration/test_main_window.py
git commit -m "feat: wire tolerance floating window"
```

## Task 6: Add Interactive Tolerance Rendering and RGB Inspection

**Files:**
- Modify: `src/remote_image_compare/ui/dialogs.py`
- Modify: `src/remote_image_compare/ui/main_window.py`
- Modify: `tests/integration/test_main_window.py`
- Test: `tests/unit/test_tolerance_map_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_tolerance_window_refreshes_when_algorithm_changes(qtbot, tmp_path: Path) -> None:
    image_a = QImage(4, 4, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(4, 4, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")

    first_map = window.current_tolerance_image()
    window.algorithm_combo.setCurrentIndex(1)
    second_map = window.current_tolerance_image()

    assert first_map is not None
    assert second_map is not None


def test_tolerance_window_updates_rgb_readout_from_hover(qtbot) -> None:
    image_a = QImage(4, 4, QImage.Format.Format_RGB32)
    image_a.fill(0xFF112233)
    image_b = QImage(4, 4, QImage.Format.Format_RGB32)
    image_b.fill(0xFF223344)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")
    window.update_hover_position(0.5, 0.5)

    assert "17" in window.left_rgb_label.text()
    assert "34" in window.right_rgb_label.text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_window_refreshes_when_algorithm_changes or tolerance_window_updates_rgb_readout_from_hover"`

Expected: FAIL because rendering and RGB inspection are incomplete.

- [ ] **Step 3: Write minimal implementation**

```python
def set_source_images(self, images_by_pane: dict[int, QImage], current_filename: str) -> None:
    ...

def update_hover_position(self, normalized_x: float, normalized_y: float) -> None:
    ...
```

Implementation requirements:

- render tolerance maps from current selected panes and current algorithm/tolerance
- refresh on slider and algorithm changes
- update RGB labels from normalized hover coordinates
- expose a tolerance viewport supporting wheel zoom and drag pan
- keep the floating window independent from the main pane zoom state

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_main_window.py -k "tolerance_window_refreshes_when_algorithm_changes or tolerance_window_updates_rgb_readout_from_hover"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote_image_compare/ui/dialogs.py src/remote_image_compare/ui/main_window.py tests/integration/test_main_window.py tests/unit/test_tolerance_map_service.py
git commit -m "feat: add tolerance map rendering and RGB inspection"
```

## Task 7: Run Full Verification

**Files:**
- Modify: any files needed from previous tasks
- Test: `tests/unit/test_tolerance_map_service.py`
- Test: `tests/integration/test_main_window.py`

- [ ] **Step 1: Run targeted tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_tolerance_map_service.py tests\integration\test_main_window.py -k "tolerance"`

Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS with all tests green

- [ ] **Step 3: Run lint**

Run: `.\.venv\Scripts\python.exe -m ruff check .`

Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add src/remote_image_compare/domain/models.py src/remote_image_compare/domain/__init__.py src/remote_image_compare/services/tolerance_map_service.py src/remote_image_compare/ui/pane_widgets.py src/remote_image_compare/ui/dialogs.py src/remote_image_compare/ui/main_window.py tests/unit/test_tolerance_map_service.py tests/integration/test_main_window.py
git commit -m "feat: add floating tolerance map tool"
```

## Self-Review

- Spec coverage:
  - floating always-on-top non-modal window is covered by Tasks 3 and 5
  - algorithm selector, tolerance slider, threshold coloring, and current-image-only scope are covered by Tasks 2, 3, and 6
  - pane hover and tolerance-map hover RGB updates are covered by Tasks 4 and 6
  - tolerance viewport zoom/pan is covered by Task 6
- Placeholder scan:
  - no `TODO`, `TBD`, or vague error-handling placeholders remain
  - every task includes concrete test commands
- Type consistency:
  - `ToleranceAlgorithm`, `ToleranceMapService`, `ToleranceWindow`, `set_source_images`, and `update_hover_position` are used consistently across tasks

Plan complete and saved to `docs/superpowers/plans/2026-06-27-tolerance-map-implementation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints
