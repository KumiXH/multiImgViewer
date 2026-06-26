from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from remote_image_compare.ui.pane_widgets import ImagePaneWidget


class NullImageService:
    def load_image(self, pane_id: str, relative_path: str):
        return None

    def load_image_async(self, pane_id: str, relative_path: str, callback) -> None:
        callback(pane_id, relative_path, None)


class MainWindow(QMainWindow):
    def __init__(self, image_service=None) -> None:
        super().__init__()
        self.setWindowTitle("Remote Image Compare")
        self.image_service = image_service or NullImageService()
        self._active_pane_count = 6
        self._compare_modes = ["common", "primary"]
        self._catalog_items: list[str] = []
        self._zoom = 1.0
        self._center_x = 0.5
        self._center_y = 0.5
        self._panes = [ImagePaneWidget(f"Pane {index + 1}") for index in range(6)]

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
        for index, pane in enumerate(self._panes):
            grid.addWidget(pane, index // 3, index % 3)
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

    def first_pane(self) -> ImagePaneWidget:
        return self._panes[0]

    def set_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        self._zoom = zoom
        self._center_x = center_x
        self._center_y = center_y

    def reset_view_state(self) -> None:
        self.set_view_state(1.0, 0.5, 0.5)

    def view_state(self) -> tuple[float, float, float]:
        return (self._zoom, self._center_x, self._center_y)

    def load_selected_file(self, relative_path: str) -> None:
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            image = self.image_service.load_image(f"pane-{index + 1}", relative_path)
            if image is None:
                pane.set_status("Missing file")
                continue
            pane.set_image(image, relative_path)

    def load_selected_file_async(self, relative_path: str) -> None:
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            pane_id = f"pane-{index + 1}"
            pane.set_status("Loading...")
            self.image_service.load_image_async(pane_id, relative_path, self._handle_loaded_image)

    def _handle_loaded_image(self, pane_id: str, relative_path: str, image) -> None:
        pane_index = int(pane_id.split("-")[-1]) - 1
        pane = self._panes[pane_index]
        if image is None:
            pane.set_status("Missing file")
            return
        pane.set_image(image, relative_path)
