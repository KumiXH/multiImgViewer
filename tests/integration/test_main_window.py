from PySide6.QtGui import QImage
from PySide6.QtCore import QTimer

from remote_image_compare.ui.main_window import MainWindow
from remote_image_compare.ui.pane_widgets import ImagePaneWidget


def test_main_window_has_default_layout(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Remote Image Compare"
    assert window.active_pane_count == 6


def test_main_window_exposes_file_mode_options(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.compare_mode_items() == ["common", "primary"]


def test_main_window_updates_file_list_from_catalog(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_catalog_items(["img1.jpg", "img2.jpg"])

    assert window.file_list_count() == 2
    assert window.current_file_label() == "0 / 2"


def test_pane_widget_shows_status_message(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    pane.set_status("Missing file")

    assert pane.status_text() == "Missing file"


def test_pane_widget_accepts_loaded_image(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    image = QImage(10, 20, QImage.Format.Format_RGB32)
    pane.set_image(image, "10x20")

    assert pane.status_text() == "10x20"
    assert pane.has_image() is True


def test_main_window_resets_shared_view_state(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_view_state(2.0, 0.2, 0.8)
    window.reset_view_state()

    assert window.view_state() == (1.0, 0.5, 0.5)


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
