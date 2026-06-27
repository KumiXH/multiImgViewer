from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    SessionRecord,
    SftpServerProfile,
    SourceConfig,
    SourceKind,
)
from remote_image_compare.services.catalog import build_catalog
from remote_image_compare.services.real_image_service import RealImageService
from remote_image_compare.services.remote_browser_service import RemoteBrowserService
from remote_image_compare.services.server_profile_store import ServerProfileStore
from remote_image_compare.services.session_record_store import SessionRecordStore
from remote_image_compare.services.window_state_store import WindowStateStore
from remote_image_compare.sources.factory import create_source
from remote_image_compare.ui.dialogs import (
    ImportRecordDialog,
    PaneBindingDialog,
    RemoteDirectoryDialog,
    SaveRecordDialog,
    ServerManagerDialog,
    SessionRecordBrowserDialog,
    ToleranceWindow,
)
from remote_image_compare.ui.pane_widgets import ImagePaneWidget


class NullImageService:
    def load_image(self, pane_id: str, relative_path: str):
        return None

    def load_image_async(self, pane_id: str, relative_path: str, callback) -> None:
        callback(pane_id, relative_path, None)


class MainWindow(QMainWindow):
    def __init__(
        self,
        image_service=None,
        source_factory=None,
        profile_store: ServerProfileStore | None = None,
        window_state_store: WindowStateStore | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Remote Image Compare")
        self.window_state_store = window_state_store or WindowStateStore()
        self._active_pane_count = 6
        self._compare_modes = [
            ("\u5171\u6709\u6587\u4ef6", CompareMode.COMMON),
            ("\u4e3b\u76ee\u5f55\u57fa\u51c6", CompareMode.PRIMARY),
        ]
        self._catalog_items: list[str] = []
        self._current_index = -1
        self._compare_pair: list[int] = []
        self._visible_pane_order = list(range(6))
        self._pending_swap_index: int | None = None
        self._locked_swap_pair: tuple[int, int] | None = None
        self._zoom = 1.0
        self._center_x = 0.5
        self._center_y = 0.5
        self._layout_modes = [
            ("1 x 2", 1, 2, 2),
            ("1 x 3", 1, 3, 3),
            ("2 x 2", 2, 2, 4),
            ("2 x 3", 2, 3, 6),
        ]
        self._panes = [ImagePaneWidget(f"Pane {index + 1}") for index in range(6)]
        for index, pane in enumerate(self._panes):
            pane.view_state_changed.connect(
                lambda zoom, center_x, center_y, source=pane: self._handle_pane_view_state_changed(
                    source, zoom, center_x, center_y
                )
            )
            pane.hover_position_changed.connect(
                lambda x, y, pane_index=index: self._handle_pane_hover_position_changed(
                    pane_index, x, y
                )
            )
            pane.activated.connect(
                lambda pane_index=index: self._handle_pane_activated(pane_index)
            )
            pane.directory_dropped.connect(
                lambda path, pane_index=index: self.bind_source_path(pane_index, path)
            )
            pane.local_bind_requested.connect(
                lambda pane_index=index: self._handle_pane_local_bind_requested(pane_index)
            )
            pane.remote_bind_requested.connect(
                lambda pane_index=index: self._handle_pane_remote_bind_requested(pane_index)
            )
            pane.clear_requested.connect(
                lambda pane_index=index: self.clear_pane_binding(pane_index)
            )
            pane.swap_requested.connect(
                lambda pane_index=index: self.handle_swap_requested(pane_index)
            )

        self._source_configs: dict[int, object] = {}
        self._remote_server_names_by_pane: dict[int, str] = {}
        self._sources_by_pane: dict[str, object] = {}
        self._source_factory = source_factory or create_source
        self.image_service = image_service or RealImageService(self._sources_by_pane)
        self.profile_store = profile_store or ServerProfileStore()
        self.session_record_store = SessionRecordStore()
        self._server_profiles: dict[str, SftpServerProfile] = {}
        self._remote_browser_service = RemoteBrowserService()
        self._tolerance_window: ToleranceWindow | None = None
        self._reload_server_profiles()

        self.compare_mode_combo = QComboBox()
        for label, mode in self._compare_modes:
            self.compare_mode_combo.addItem(label, mode.value)
        self.compare_mode_combo.currentTextChanged.connect(lambda _text: self.refresh_catalog())
        self.compare_mode_combo.setFixedSize(160, 36)

        self.layout_mode_combo = QComboBox()
        for label, rows, columns, count in self._layout_modes:
            self.layout_mode_combo.addItem(label, (rows, columns, count))
        self.layout_mode_combo.currentTextChanged.connect(lambda _text: self._apply_layout_mode())
        self.layout_mode_combo.setFixedSize(120, 36)

        self.toggle_sidebar_button = QPushButton("\u6587\u4ef6\u5217\u8868")
        self.toggle_sidebar_button.clicked.connect(self.toggle_sidebar)
        self.toggle_sidebar_button.setFixedSize(120, 36)

        self.server_manager_button = QPushButton("\u670d\u52a1\u5668")
        self.server_manager_button.clicked.connect(self.open_server_manager)
        self.server_manager_button.setFixedSize(120, 36)

        self.bind_source_button = QPushButton("\u7ed1\u5b9a\u7a97\u53e3")
        self.bind_source_button.clicked.connect(self.open_pane_binding_dialog)
        self.bind_source_button.setFixedSize(120, 36)

        self.record_button = QPushButton("\u8bb0\u5f55")
        self.record_button.clicked.connect(self.open_record_browser)
        self.record_button.setFixedSize(120, 36)

        self.previous_button = QPushButton("\u4e0a\u4e00\u5f20")
        self.previous_button.clicked.connect(self.previous_image)
        self.previous_button.setFixedSize(120, 36)

        self.next_button = QPushButton("\u4e0b\u4e00\u5f20")
        self.next_button.clicked.connect(self.next_image)
        self.next_button.setFixedSize(120, 36)

        self.tolerance_button = QPushButton("\u5bb9\u5dee\u56fe")
        self.tolerance_button.clicked.connect(self.open_tolerance_window)
        self.tolerance_button.setFixedSize(120, 36)

        self.position_label = QLabel("0 / 0")
        self.position_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.current_filename_label = QLabel("")
        self.current_filename_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.jump_to_item)

        self.top_toolbar = QWidget()
        self.top_toolbar_layout = QHBoxLayout(self.top_toolbar)
        self.top_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_toolbar_layout.setSpacing(12)
        self.top_toolbar_layout.addWidget(self.toggle_sidebar_button)
        self.top_toolbar_layout.addWidget(self.server_manager_button)
        self.top_toolbar_layout.addWidget(self.bind_source_button)
        self.top_toolbar_layout.addWidget(self.record_button)
        self.top_toolbar_layout.addWidget(self.previous_button)
        self.top_toolbar_layout.addWidget(self.next_button)
        self.top_toolbar_layout.addWidget(self.tolerance_button)
        self.top_toolbar_layout.addWidget(self.compare_mode_combo)
        self.top_toolbar_layout.addWidget(self.layout_mode_combo)
        self.top_toolbar_layout.addWidget(self.current_filename_label, 1)
        self.top_toolbar_layout.addStretch(1)
        self.top_toolbar_layout.addWidget(self.position_label)

        self.grid_host = QWidget()
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(12)
        for pane in self._panes:
            self.grid_layout.addWidget(pane)

        self.left_panel = QWidget()
        self.left_panel_layout = QVBoxLayout(self.left_panel)
        self.left_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.left_panel_layout.setSpacing(12)
        self.left_panel_layout.addWidget(self.top_toolbar)
        self.left_panel_layout.addWidget(self.grid_host, 1)

        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.file_list, 1)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.setSizes([1200, 320])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self.main_splitter, 1)
        self.setCentralWidget(central)

        self._restore_window_size()
        self.layout_mode_combo.setCurrentText("2 x 3")
        self._apply_layout_mode()
        self._apply_visual_styles()

    @property
    def active_pane_count(self) -> int:
        return self._active_pane_count

    def compare_mode_items(self) -> list[str]:
        return [self.compare_mode_combo.itemText(i) for i in range(self.compare_mode_combo.count())]

    def layout_mode_items(self) -> list[str]:
        return [self.layout_mode_combo.itemText(i) for i in range(self.layout_mode_combo.count())]

    def saved_server_names(self) -> list[str]:
        return sorted(self._server_profiles, key=str.casefold)

    def set_catalog_items(self, items: list[str]) -> None:
        self._catalog_items = items
        self.file_list.clear()
        self.file_list.addItems(items)
        self._current_index = -1
        self.current_filename_label.setText("")
        self._update_position_label()

    def file_list_count(self) -> int:
        return self.file_list.count()

    def current_file_label(self) -> str:
        return self.position_label.text()

    def first_pane(self) -> ImagePaneWidget:
        return self._panes[0]

    def bind_source(self, pane_index: int, config, auth=None, connection=None) -> None:
        pane_id = f"pane-{pane_index + 1}"
        self._source_configs[pane_index] = config
        if config.kind is not SourceKind.SFTP:
            self._remote_server_names_by_pane.pop(pane_index, None)
        self._sources_by_pane[pane_id] = self._source_factory(
            config,
            auth=auth,
            connection=connection,
        )
        self._panes[pane_index].set_title(config.display_name)
        self._panes[pane_index]._is_bound = True
        if hasattr(self.image_service, "replace_sources"):
            self.image_service.replace_sources(self._sources_by_pane)

    def bind_source_path(self, pane_index: int, path: str) -> None:
        kind = SourceKind.UNC if path.startswith("\\\\") else SourceKind.LOCAL
        display_name = Path(path).name or path
        self.bind_source(
            pane_index,
            SourceConfig(
                id=f"pane-{pane_index + 1}",
                kind=kind,
                display_name=display_name,
                root_path=path,
                recursive=True,
            ),
        )
        self.refresh_catalog()
        self.load_first_catalog_item_if_available()

    def clear_pane_binding(self, pane_index: int) -> None:
        pane_id = f"pane-{pane_index + 1}"
        self._source_configs.pop(pane_index, None)
        self._remote_server_names_by_pane.pop(pane_index, None)
        self._sources_by_pane.pop(pane_id, None)
        if self._locked_swap_pair and pane_index in self._locked_swap_pair:
            self._clear_locked_swap_pair()
        pane = self._panes[pane_index]
        pane.clear_binding_state()
        pane.set_title(f"Pane {pane_index + 1}")
        if self._pending_swap_index == pane_index:
            self.cancel_swap_selection()
        if hasattr(self.image_service, "replace_sources"):
            self.image_service.replace_sources(self._sources_by_pane)
        self.refresh_catalog()
        if self._catalog_items:
            self.set_current_index(0)
        else:
            self._current_index = -1
            self.current_filename_label.setText("")
            self._update_position_label()

    def bind_remote_profile(
        self, pane_index: int, profile: SftpServerProfile, remote_path: str
    ) -> None:
        normalized_remote_path = remote_path.strip() or profile.default_root.strip()
        display_remote_path = normalized_remote_path or profile.default_root or "/"
        self.bind_source(
            pane_index,
            SourceConfig(
                id=f"pane-{pane_index + 1}",
                kind=SourceKind.SFTP,
                display_name=f"{profile.name}:{display_remote_path}",
                root_path=display_remote_path,
                recursive=True,
            ),
            auth=profile.to_auth_config(),
            connection=profile.to_connection_config(),
        )
        self._remote_server_names_by_pane[pane_index] = profile.name
        self.refresh_catalog()
        self.load_first_catalog_item_if_available()

    def set_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        self._zoom = zoom
        self._center_x = center_x
        self._center_y = center_y
        self._apply_shared_view_state()

    def reset_view_state(self) -> None:
        self.set_view_state(1.0, 0.5, 0.5)

    def view_state(self) -> tuple[float, float, float]:
        return (self._zoom, self._center_x, self._center_y)

    def refresh_catalog(self) -> None:
        entries_by_source: dict[str, set[str]] = {}
        for pane_index in range(self._active_pane_count):
            pane_id = f"pane-{pane_index + 1}"
            source = self._sources_by_pane.get(pane_id)
            if source is None:
                continue
            entries_by_source[pane_id] = set(source.list_relative_paths())

        mode = CompareMode(self.compare_mode_combo.currentData())
        self.set_catalog_items(build_catalog(entries_by_source, mode))

    def catalog_items(self) -> list[str]:
        return list(self._catalog_items)

    def jump_to_item(self, item) -> None:
        if item is None:
            return
        name = item.text()
        if name in self._catalog_items:
            self.set_current_index(self._catalog_items.index(name))

    def set_current_index(self, index: int) -> None:
        if not self._catalog_items:
            self._current_index = -1
            self._update_position_label()
            return
        self._current_index = index % len(self._catalog_items)
        if self._current_index not in self._compare_pair:
            self._compare_pair.append(self._current_index)
            self._compare_pair = self._compare_pair[-2:]
        self._update_position_label()
        self.load_selected_file(self._catalog_items[self._current_index])

    def next_image(self) -> None:
        if self._catalog_items:
            self.set_current_index(self._current_index + 1)

    def previous_image(self) -> None:
        if self._catalog_items:
            self.set_current_index(self._current_index - 1)

    def load_first_catalog_item_if_available(self) -> None:
        if self._catalog_items:
            self.set_current_index(0)

    def current_filename(self) -> str | None:
        if 0 <= self._current_index < len(self._catalog_items):
            return self._catalog_items[self._current_index]
        return None

    def toggle_compare_pair(self) -> None:
        if len(self._compare_pair) < 2:
            return
        first, second = self._compare_pair
        if self._current_index == second:
            self.set_current_index(first)
        else:
            self.set_current_index(second)

    def capture_session_record(self, name: str) -> SessionRecord:
        panes: list[SessionPaneBinding] = []
        for pane_index, config in sorted(self._source_configs.items()):
            server_name = self._remote_server_names_by_pane.get(pane_index)
            panes.append(
                SessionPaneBinding(
                    pane_index=pane_index,
                    source_kind=config.kind,
                    display_name=config.display_name,
                    root_path=config.root_path if config.kind is not SourceKind.SFTP else None,
                    server_name=server_name,
                    remote_path=config.root_path if config.kind is SourceKind.SFTP else None,
                )
            )
        return SessionRecord(
            id=str(uuid4()),
            name=name,
            saved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            layout_mode=self.layout_mode_combo.currentText(),
            compare_mode=CompareMode(self.compare_mode_combo.currentData()),
            panes=tuple(panes),
        )

    def apply_session_record(self, record: SessionRecord) -> list[str]:
        self.layout_mode_combo.setCurrentText(record.layout_mode)
        compare_label = next(
            (
                label
                for label, mode in self._compare_modes
                if mode == record.compare_mode
            ),
            None,
        )
        if compare_label is not None:
            self.compare_mode_combo.setCurrentText(compare_label)

        target_panes = {pane.pane_index for pane in record.panes}
        for pane_index in list(self._source_configs):
            if pane_index not in target_panes:
                self.clear_pane_binding(pane_index)

        errors: list[str] = []
        for pane in record.panes:
            if pane.source_kind is SourceKind.SFTP:
                if not pane.server_name or pane.server_name not in self._server_profiles:
                    errors.append(f"缺少服务器配置: {pane.server_name or '未知'}")
                    continue
                profile = self._server_profiles[pane.server_name]
                self.bind_remote_profile(pane.pane_index, profile, pane.remote_path or "")
            else:
                if pane.root_path is None:
                    continue
                self.bind_source(
                    pane.pane_index,
                    SourceConfig(
                        id=f"pane-{pane.pane_index + 1}",
                        kind=pane.source_kind,
                        display_name=pane.display_name,
                        root_path=pane.root_path,
                        recursive=False,
                    ),
                )

        self.refresh_catalog()
        self.load_first_catalog_item_if_available()
        return errors

    def sidebar_is_visible(self) -> bool:
        return self.sidebar.isVisible()

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def open_server_manager(self) -> None:
        dialog = ServerManagerDialog(list(self._server_profiles.values()), self)
        dialog.exec()
        for profile_name in dialog.deleted_profile_names():
            self.profile_store.delete_profile(profile_name)
        for profile in dialog.profiles():
            self.profile_store.save_profile(profile)
        self._reload_server_profiles()

    def open_pane_binding_dialog(self) -> None:
        dialog = PaneBindingDialog(self._active_pane_count, self.saved_server_names(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        binding = dialog.binding()
        pane_index = int(binding["pane_index"])
        if binding["source_type"] == "local":
            self.bind_source_path(pane_index, str(binding["local_path"]))
            return
        profile_name = str(binding["profile_name"])
        profile = self._server_profiles.get(profile_name)
        if profile is None:
            return
        self.bind_remote_profile(pane_index, profile, str(binding["remote_path"]))

    def open_tolerance_window(self) -> None:
        if self._tolerance_window is None:
            self._tolerance_window = ToleranceWindow(
                self,
                window_state_store=self.window_state_store,
            )
        self._tolerance_window.show()
        self._refresh_tolerance_window_state()
        self._tolerance_window.raise_()
        self._tolerance_window.activateWindow()

    def open_record_browser(self) -> None:
        dialog = SessionRecordBrowserDialog(self.session_record_store.list_records(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        action = dialog.selected_action()
        if action == "save":
            self.save_current_record()
            return
        if action == "import":
            self.import_record()
            return

        record_id = dialog.selected_record_id()
        if record_id is None:
            return
        record = next(
            (item for item in self.session_record_store.list_records() if item.id == record_id),
            None,
        )
        if record is None:
            return
        if action == "apply":
            self._apply_record_with_feedback(record)
        elif action == "copy":
            QGuiApplication.clipboard().setText(
                self.session_record_store.export_record_json(record)
            )
        elif action == "export":
            self.export_record_to_file(record)
        elif action == "delete":
            self.session_record_store.delete_record(record.id)

    def save_current_record(self) -> None:
        dialog = SaveRecordDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._source_configs:
            QMessageBox.information(self, "无法保存", "请至少绑定一个窗口后再保存记录。")
            return
        record = self.capture_session_record(dialog.record_name())
        self.session_record_store.save_record(record)

    def import_record(self) -> None:
        dialog = ImportRecordDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            record = self.session_record_store.parse_record_json(dialog.import_text())
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._apply_record_with_feedback(record)

    def export_record_to_file(self, record: SessionRecord) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出记录",
            f"{record.name}.json",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        Path(path).write_text(
            self.session_record_store.export_record_json(record),
            encoding="utf-8",
        )

    def _apply_record_with_feedback(self, record: SessionRecord) -> None:
        errors = self.apply_session_record(record)
        if errors:
            QMessageBox.warning(self, "应用记录提示", "\n".join(errors))

    def _handle_pane_local_bind_requested(self, pane_index: int) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "\u9009\u62e9\u672c\u5730\u76ee\u5f55",
            str(Path.home()),
        )
        if path:
            self.bind_source_path(pane_index, path)

    def _handle_pane_remote_bind_requested(self, pane_index: int) -> None:
        if not self._server_profiles:
            return
        dialog = RemoteDirectoryDialog(
            list(self._server_profiles.values()),
            self._remote_browser_service,
            self,
        )
        dialog.load_root()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile_name = dialog.selected_profile_name()
        profile = self._server_profiles.get(profile_name)
        if profile is None:
            return
        self.bind_remote_profile(pane_index, profile, dialog.selected_path)

    def _apply_layout_mode(self) -> None:
        rows, columns, count = self.layout_mode_combo.currentData()
        del rows, columns
        self._active_pane_count = count
        self._relayout_visible_panes()

        if self._catalog_items:
            self.refresh_catalog()
            current = self.current_filename()
            if current is not None and current in self._catalog_items:
                self.load_selected_file(current)
            elif self._catalog_items:
                self.set_current_index(0)

    def begin_swap_selection(self, pane_index: int) -> None:
        self.cancel_swap_selection()
        self._pending_swap_index = pane_index
        self._panes[pane_index].set_swap_state(pending=True)

    def cancel_swap_selection(self) -> None:
        if self._pending_swap_index is not None:
            self._panes[self._pending_swap_index].set_swap_state()
        self._pending_swap_index = None
        self._clear_locked_swap_pair()

    def handle_swap_requested(self, pane_index: int) -> None:
        if self._locked_swap_pair and pane_index in self._locked_swap_pair:
            left, right = self._locked_swap_pair
            self._swap_pane_positions(left, right)
            return

        if self._pending_swap_index is None:
            self.begin_swap_selection(pane_index)
            return

        if self._pending_swap_index == pane_index:
            self.cancel_swap_selection()
            return

        first = self._pending_swap_index
        second = pane_index
        self._swap_pane_positions(first, second)
        self._panes[first].set_swap_state()
        self._pending_swap_index = None
        self._set_locked_swap_pair(first, second)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_swap_selection()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Left:
            self.previous_image()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.next_image()
            event.accept()
            return
        super().keyPressEvent(event)

    def _swap_pane_positions(self, first: int, second: int) -> None:
        first_visual = self._visible_pane_order.index(first)
        second_visual = self._visible_pane_order.index(second)
        self._visible_pane_order[first_visual], self._visible_pane_order[second_visual] = (
            self._visible_pane_order[second_visual],
            self._visible_pane_order[first_visual],
        )
        self._relayout_visible_panes()

    def _set_locked_swap_pair(self, first: int, second: int) -> None:
        self._clear_locked_swap_pair()
        self._locked_swap_pair = (first, second)
        self._panes[first].set_swap_state(locked=True)
        self._panes[second].set_swap_state(locked=True)

    def _clear_locked_swap_pair(self) -> None:
        if self._locked_swap_pair is None:
            return
        first, second = self._locked_swap_pair
        self._panes[first].set_swap_state()
        self._panes[second].set_swap_state()
        self._locked_swap_pair = None

    def _reload_server_profiles(self) -> None:
        self._server_profiles = {
            profile.name: profile for profile in self.profile_store.list_profiles()
        }

    def _refresh_tolerance_window_state(self) -> None:
        if self._tolerance_window is None or not self._tolerance_window.isVisible():
            return
        available_indices = [
            index for index, pane in enumerate(self._panes[: self._active_pane_count]) if pane.has_image()
        ]
        pane_names = [self._panes[index].title_text() for index in available_indices]
        self._tolerance_window.set_available_panes(pane_names)
        self._tolerance_window.current_filename_label.setText(self.current_filename() or "")
        self._tolerance_window.set_source_images(
            {
                display_index: self._panes[pane_index]._base_pixmap.toImage()
                for display_index, pane_index in enumerate(available_indices)
            },
            current_filename=self.current_filename() or "",
        )

    def _handle_pane_hover_position_changed(
        self,
        pane_index: int,
        normalized_x: float,
        normalized_y: float,
    ) -> None:
        del pane_index
        if self._tolerance_window is None or not self._tolerance_window.isVisible():
            return
        self._tolerance_window.update_hover_position(normalized_x, normalized_y)

    def _handle_pane_activated(self, pane_index: int) -> None:
        if self._pending_swap_index == pane_index:
            return
        if self._locked_swap_pair and pane_index not in self._locked_swap_pair:
            self._clear_locked_swap_pair()

    def _update_position_label(self) -> None:
        if not self._catalog_items or self._current_index < 0:
            self.position_label.setText(f"0 / {len(self._catalog_items)}")
            return
        self.position_label.setText(f"{self._current_index + 1} / {len(self._catalog_items)}")

    def load_selected_file(self, relative_path: str) -> None:
        current_view = self.view_state()
        self.current_filename_label.setText(relative_path)
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            try:
                image = self.image_service.load_image(f"pane-{index + 1}", relative_path)
            except FileNotFoundError:
                image = None
            if image is None:
                pane.set_status("Missing file")
                continue
            pane.set_image(image, relative_path)
        self._zoom, self._center_x, self._center_y = current_view
        self._apply_shared_view_state()
        self._refresh_tolerance_window_state()

    def load_selected_file_async(self, relative_path: str) -> None:
        for index, pane in enumerate(self._panes[: self._active_pane_count]):
            pane_id = f"pane-{index + 1}"
            pane.set_status("Loading...")
            self.image_service.load_image_async(
                pane_id,
                relative_path,
                self._handle_loaded_image,
            )

    def _handle_loaded_image(self, pane_id: str, relative_path: str, image) -> None:
        pane_index = int(pane_id.split("-")[-1]) - 1
        pane = self._panes[pane_index]
        if image is None:
            pane.set_status("Missing file")
            return
        current_view = self.view_state()
        pane.set_image(image, relative_path)
        self._zoom, self._center_x, self._center_y = current_view
        self._apply_shared_view_state()

    def _handle_pane_view_state_changed(
        self,
        source_pane: ImagePaneWidget,
        zoom: float,
        center_x: float,
        center_y: float,
    ) -> None:
        self._zoom = zoom
        self._center_x = center_x
        self._center_y = center_y
        self._apply_shared_view_state(exclude=source_pane)

    def _apply_shared_view_state(self, exclude: ImagePaneWidget | None = None) -> None:
        for pane in self._panes[: self._active_pane_count]:
            if pane is exclude or not pane.has_image():
                continue
            pane._suppress_view_state_signal = True
            try:
                pane.set_view_state(self._zoom, self._center_x, self._center_y)
            finally:
                pane._suppress_view_state_signal = False

    def _apply_visual_styles(self) -> None:
        self.setStyleSheet(
            """
QMainWindow {
    background-color: #eef3f8;
}
QWidget {
    color: #203040;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d6deea;
    border-radius: 10px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #f4f7fb;
}
QPushButton:pressed {
    background-color: #e9eef5;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d6deea;
    border-radius: 10px;
    padding: 6px 12px;
}
QListWidget {
    background-color: #f9fbfd;
    border: 1px solid #d6deea;
    border-radius: 12px;
    padding: 8px;
}
QLabel {
    color: #203040;
}
"""
        )
        for button in (
            self.toggle_sidebar_button,
            self.server_manager_button,
            self.bind_source_button,
            self.record_button,
            self.previous_button,
            self.next_button,
            self.tolerance_button,
        ):
            self._apply_button_shadow(button)

    def _apply_button_shadow(self, button: QPushButton) -> None:
        shadow = QGraphicsDropShadowEffect(button)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QGuiApplication.palette().shadow().color())
        shadow.setColor(shadow.color().darker(100))
        color = shadow.color()
        color.setAlpha(38)
        shadow.setColor(color)
        button.setGraphicsEffect(shadow)

    def closeEvent(self, event) -> None:
        self.window_state_store.save_window_size(
            "main_window",
            self.width(),
            self.height(),
        )
        self.window_state_store.save_window_position(
            "main_window",
            self.x(),
            self.y(),
        )
        super().closeEvent(event)

    def _relayout_visible_panes(self) -> None:
        if len(self._visible_pane_order) != len(self._panes):
            self._visible_pane_order = list(range(len(self._panes)))
        count = self._active_pane_count
        for visual_index, pane_index in enumerate(self._visible_pane_order):
            pane = self._panes[pane_index]
            self.grid_layout.removeWidget(pane)
            if visual_index < count:
                if count in {2, 3}:
                    row, column = (0, visual_index)
                elif count == 4:
                    row, column = divmod(visual_index, 2)
                else:
                    row, column = divmod(visual_index, 3)
                self.grid_layout.addWidget(pane, row, column)
                pane.show()
            else:
                pane.hide()

    def _restore_window_size(self) -> None:
        saved_size = self.window_state_store.load_window_size("main_window")
        if saved_size is not None:
            self.resize(*saved_size)
        else:
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen is None:
                self.resize(1280, 720)
            else:
                available = screen.availableGeometry()
                self.resize(
                    max(960, available.width() // 2),
                    max(640, available.height() // 2),
                )
        saved_position = self.window_state_store.load_window_position("main_window")
        if saved_position is not None:
            self._restore_window_position(saved_position)

    def _restore_window_position(self, position: tuple[int, int]) -> None:
        target = QRect(position[0], position[1], self.width(), self.height())
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(target):
                self.move(*position)
                return
