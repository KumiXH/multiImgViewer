from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QPointF,
    QRect,
    QRectF,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from remote_image_compare.domain.models import CompareMode, SessionRecord, SftpAuthMode, SftpServerProfile
from remote_image_compare.domain.models import ToleranceAlgorithm
from remote_image_compare.services.remote_browser_service import RemoteBrowserService
from remote_image_compare.services.tolerance_map_service import (
    PreparedToleranceComparison,
    ToleranceMapService,
)
from remote_image_compare.services.window_state_store import WindowStateStore


def _server_label(profile: SftpServerProfile) -> str:
    return f"{profile.name}  {profile.host}:{profile.port}  {profile.username}"


class ToleranceComputeSignals(QObject):
    preview_ready = Signal(int, QImage, object)
    final_ready = Signal(int, QImage, object)

class ToleranceComputeTask(QRunnable):
    def __init__(self, service: ToleranceMapService, job: dict[str, object]) -> None:
        super().__init__()
        self._service = service
        self._job = job
        self.signals = ToleranceComputeSignals()

    def _emit_preview(self, job_id: int, image: QImage, prepared: PreparedToleranceComparison) -> None:
        try:
            self.signals.preview_ready.emit(job_id, image, prepared)
        except RuntimeError:
            return

    def _emit_final(self, job_id: int, image: QImage, prepared: PreparedToleranceComparison) -> None:
        try:
            self.signals.final_ready.emit(job_id, image, prepared)
        except RuntimeError:
            return

    @Slot()
    def run(self) -> None:
        job = self._job
        job_id = int(job["job_id"])
        left = job["left"]
        right = job["right"]
        tolerance = int(job["tolerance"])
        algorithm = job["algorithm"]
        preview_size = job["preview_size"]
        roi = job.get("roi")
        sync_mode = bool(job["sync_mode"])

        prepared_preview = self._service.prepare_comparison(
            left,
            right,
            algorithm,
            max_size=preview_size,
            roi=roi,
        )
        preview_map = self._service.build_tolerance_map(
            left,
            right,
            tolerance=tolerance,
            algorithm=algorithm,
            max_size=preview_size,
            roi=roi,
        )
        self._emit_preview(job_id, preview_map, prepared_preview)

        if not sync_mode:
            return

        prepared_final = self._service.prepare_comparison(
            left,
            right,
            algorithm,
            max_size=None,
            roi=roi,
        )
        final_map = self._service.build_tolerance_map(
            left,
            right,
            tolerance=tolerance,
            algorithm=algorithm,
            max_size=None,
            roi=roi,
        )
        self._emit_final(job_id, final_map, prepared_final)


class ToleranceImageView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 180)
        self.setMouseTracking(True)
        self._image = QImage()
        self._zoom_factor = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._dragging = False
        self._last_drag_pos: QPointF | None = None
        self._interactive_enabled = False
        self._display_pixmap: QPixmap | None = None
        self._empty_text = "请选择两个窗口"

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.update()

    def set_image(self, image: QImage | None) -> None:
        self._image = QImage() if image is None else image
        self.reset_view()
        self.repaint()

    def set_interactive_enabled(self, enabled: bool) -> None:
        self._interactive_enabled = enabled
        if not enabled:
            self.reset_view()
        self.update()

    def current_display_pixmap(self) -> QPixmap | None:
        if self._image.isNull():
            return None
        self._display_pixmap = self._build_display_pixmap()
        return self._display_pixmap

    def zoom_factor(self) -> float:
        return self._zoom_factor

    def view_state(self) -> tuple[float, float, float]:
        center_x, center_y = self._current_center()
        return (self._zoom_factor, center_x, center_y)

    def set_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        if self._image.isNull():
            return
        self._zoom_factor = max(1.0, min(16.0, zoom))
        if self._zoom_factor <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            rendered_width, rendered_height = self._compute_rendered_size(self._zoom_factor)
            self._pan_x = round(rendered_width * (0.5 - center_x))
            self._pan_y = round(rendered_height * (0.5 - center_y))
        self.update()

    def reset_view(self) -> None:
        self._zoom_factor = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._dragging = False
        self._last_drag_pos = None
        self._display_pixmap = None

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101217"))
        if self._image.isNull():
            painter.setPen(QColor("#d7e3f4"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            self._display_pixmap = None
            return

        pixmap = QPixmap.fromImage(self._image)
        viewport_width = max(1, self.width())
        viewport_height = max(1, self.height())
        fit_scale = min(viewport_width / pixmap.width(), viewport_height / pixmap.height())
        rendered_width = pixmap.width() * fit_scale * self._zoom_factor
        rendered_height = pixmap.height() * fit_scale * self._zoom_factor
        offset_x, offset_y = self._clamp_pan(rendered_width, rendered_height)

        target = QRectF(offset_x, offset_y, rendered_width, rendered_height)
        source = QRectF(0, 0, pixmap.width(), pixmap.height())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(target, pixmap, source)

        self._display_pixmap = self._build_display_pixmap()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._interactive_enabled or self._image.isNull() or event.angleDelta().y() == 0:
            event.ignore()
            return
        steps = 1 if event.angleDelta().y() > 0 else -1
        self._apply_zoom_delta(steps, event.position())
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._interactive_enabled
            and not self._image.isNull()
            and event.button() == Qt.MouseButton.LeftButton
            and self._zoom_factor > 1.0
        ):
            self._dragging = True
            self._last_drag_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._last_drag_pos is not None:
            delta = event.position() - self._last_drag_pos
            self._last_drag_pos = event.position()
            self._pan_x += int(delta.x())
            self._pan_y += int(delta.y())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._last_drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def _apply_zoom_delta(self, steps: int, anchor_pos: QPointF) -> None:
        old_zoom = self._zoom_factor
        old_rendered_width, old_rendered_height = self._compute_rendered_size(old_zoom)
        old_offset_x, old_offset_y = self._clamp_pan(old_rendered_width, old_rendered_height)
        self._zoom_factor = max(1.0, min(16.0, self._zoom_factor * (1.25 ** steps)))
        if self._zoom_factor <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            if old_rendered_width <= 0 or old_rendered_height <= 0:
                relative_x = 0.5
                relative_y = 0.5
            else:
                relative_x = (anchor_pos.x() - old_offset_x) / old_rendered_width
                relative_y = (anchor_pos.y() - old_offset_y) / old_rendered_height
            relative_x = max(0.0, min(1.0, relative_x))
            relative_y = max(0.0, min(1.0, relative_y))
            new_rendered_width, new_rendered_height = self._compute_rendered_size()
            viewport_width = max(1, self.width())
            viewport_height = max(1, self.height())
            self._pan_x = round(
                anchor_pos.x()
                - relative_x * new_rendered_width
                - (viewport_width - new_rendered_width) / 2.0
            )
            self._pan_y = round(
                anchor_pos.y()
                - relative_y * new_rendered_height
                - (viewport_height - new_rendered_height) / 2.0
            )
        self.update()

    def _compute_rendered_size(self, zoom_factor: float | None = None) -> tuple[int, int]:
        if self._image.isNull():
            return (0, 0)
        viewport_width = max(1, self.width())
        viewport_height = max(1, self.height())
        fit_scale = min(viewport_width / self._image.width(), viewport_height / self._image.height())
        zoom = self._zoom_factor if zoom_factor is None else zoom_factor
        rendered_width = max(1, int(self._image.width() * fit_scale * zoom))
        rendered_height = max(1, int(self._image.height() * fit_scale * zoom))
        return (rendered_width, rendered_height)

    def _build_display_pixmap(self) -> QPixmap:
        pixmap = QPixmap.fromImage(self._image)
        rendered_width, rendered_height = self._compute_rendered_size()
        viewport_width = max(1, self.width())
        viewport_height = max(1, self.height())
        return pixmap.scaled(
            int(min(rendered_width, viewport_width)),
            int(min(rendered_height, viewport_height)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def _current_center(self) -> tuple[float, float]:
        rendered_width, rendered_height = self._compute_rendered_size()
        if rendered_width <= 0 or rendered_height <= 0 or self._zoom_factor <= 1.0:
            return (0.5, 0.5)
        center_x = 0.5 - (self._pan_x / rendered_width)
        center_y = 0.5 - (self._pan_y / rendered_height)
        return (
            max(0.0, min(1.0, center_x)),
            max(0.0, min(1.0, center_y)),
        )

    def _clamp_pan(self, rendered_width: float, rendered_height: float) -> tuple[float, float]:
        viewport_width = max(1, self.width())
        viewport_height = max(1, self.height())
        limit_x = max(0.0, (rendered_width - viewport_width) / 2.0)
        limit_y = max(0.0, (rendered_height - viewport_height) / 2.0)

        self._pan_x = int(max(-limit_x, min(limit_x, self._pan_x)))
        self._pan_y = int(max(-limit_y, min(limit_y, self._pan_y)))

        offset_x = (viewport_width - rendered_width) / 2.0 + self._pan_x
        offset_y = (viewport_height - rendered_height) / 2.0 + self._pan_y
        return (offset_x, offset_y)


class ServerProfileDialog(QDialog):
    def __init__(
        self,
        profile: SftpServerProfile | None = None,
        parent: QWidget | None = None,
        remote_browser_service: RemoteBrowserService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u670d\u52a1\u5668\u914d\u7f6e")
        self._remote_browser_service = remote_browser_service or RemoteBrowserService()

        self.name_edit = QLineEdit(profile.name if profile else "")
        self.host_edit = QLineEdit(profile.host if profile else "")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(profile.port if profile else 22)
        self.username_edit = QLineEdit(profile.username if profile else "")
        self.auth_mode_combo = QComboBox()
        self.auth_mode_combo.addItem("\u5bc6\u7801", SftpAuthMode.PASSWORD)
        self.auth_mode_combo.addItem("\u5bc6\u94a5", SftpAuthMode.KEY)
        self.password_edit = QLineEdit(profile.password if profile else "")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_path_edit = QLineEdit(
            profile.private_key_path if profile and profile.private_key_path else ""
        )
        self.passphrase_edit = QLineEdit(profile.passphrase if profile else "")
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.default_root_edit = QLineEdit(profile.default_root if profile else "")
        self.connection_status_label = QLabel("")
        self.connection_status_label.setWordWrap(True)
        self.connection_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        if profile is not None:
            index = self.auth_mode_combo.findData(profile.auth_mode)
            self.auth_mode_combo.setCurrentIndex(max(0, index))

        key_browse_button = QPushButton("\u9009\u62e9\u5bc6\u94a5")
        key_browse_button.clicked.connect(self._browse_key_path)

        form = QFormLayout()
        form.addRow("\u540d\u79f0", self.name_edit)
        form.addRow("\u4e3b\u673a", self.host_edit)
        form.addRow("\u7aef\u53e3", self.port_spin)
        form.addRow("\u7528\u6237\u540d", self.username_edit)
        form.addRow("\u8ba4\u8bc1\u65b9\u5f0f", self.auth_mode_combo)
        form.addRow("\u5bc6\u7801", self.password_edit)

        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.key_path_edit, 1)
        key_layout.addWidget(key_browse_button)
        form.addRow("\u79c1\u94a5\u8def\u5f84", key_row)
        form.addRow("\u79c1\u94a5\u53e3\u4ee4", self.passphrase_edit)
        form.addRow("\u9ed8\u8ba4\u8fdc\u7aef\u76ee\u5f55", self.default_root_edit)

        self.auth_mode_combo.currentIndexChanged.connect(self._update_auth_mode_fields)
        self._update_auth_mode_fields()

        buttons_row = QWidget()
        buttons = QHBoxLayout(buttons_row)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.connection_status_label, 1)
        buttons.addStretch(1)
        test_button = QPushButton("\u6d4b\u8bd5\u8fde\u63a5")
        save_button = QPushButton("\u4fdd\u5b58")
        cancel_button = QPushButton("\u53d6\u6d88")
        test_button.clicked.connect(self.test_connection)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(test_button)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons_row)

    def profile(self) -> SftpServerProfile:
        return SftpServerProfile(
            name=self.name_edit.text().strip(),
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            username=self.username_edit.text().strip(),
            auth_mode=self.auth_mode_combo.currentData(),
            password=self.password_edit.text(),
            private_key_path=self.key_path_edit.text().strip() or None,
            passphrase=self.passphrase_edit.text(),
            default_root=self.default_root_edit.text().strip(),
        )

    def test_connection(self) -> None:
        ok, message = self._remote_browser_service.test_connection(self.profile())
        self.connection_status_label.setText(message)
        self.connection_status_label.setStyleSheet(
            "color: #22863a;" if ok else "color: #d73a49;"
        )

    def accept(self) -> None:
        profile = self.profile()
        if not profile.name or not profile.host or not profile.username:
            QMessageBox.warning(
                self,
                "\u4fe1\u606f\u4e0d\u5b8c\u6574",
                "\u8bf7\u81f3\u5c11\u586b\u5199\u540d\u79f0\u3001\u4e3b\u673a\u548c\u7528\u6237\u540d\u3002",
            )
            return
        if profile.auth_mode == SftpAuthMode.KEY and not profile.private_key_path:
            QMessageBox.warning(
                self,
                "\u4fe1\u606f\u4e0d\u5b8c\u6574",
                "\u5bc6\u94a5\u8ba4\u8bc1\u9700\u8981\u63d0\u4f9b\u79c1\u94a5\u8def\u5f84\u3002",
            )
            return
        super().accept()

    def _browse_key_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "\u9009\u62e9\u79c1\u94a5\u6587\u4ef6",
            str(Path.home()),
        )
        if path:
            self.key_path_edit.setText(path)

    def _update_auth_mode_fields(self) -> None:
        is_password = self.auth_mode_combo.currentData() == SftpAuthMode.PASSWORD
        self.password_edit.setEnabled(is_password)
        self.key_path_edit.setEnabled(not is_password)
        self.passphrase_edit.setEnabled(not is_password)


class ServerManagerDialog(QDialog):
    def __init__(self, profiles: list[SftpServerProfile], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u670d\u52a1\u5668\u7ba1\u7406")
        self._profiles = {profile.name: profile for profile in profiles}
        self._selected_profile: SftpServerProfile | None = None
        self._deleted_profiles: set[str] = set()

        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._handle_selection_changed)
        self.summary_label = QLabel("\u8bf7\u9009\u62e9\u5de6\u4fa7\u670d\u52a1\u5668\u3002")

        add_button = QPushButton("\u65b0\u589e")
        edit_button = QPushButton("\u7f16\u8f91")
        delete_button = QPushButton("\u5220\u9664")
        save_button = QPushButton("\u5b8c\u6210")
        cancel_button = QPushButton("\u53d6\u6d88")

        add_button.clicked.connect(self._add_profile)
        edit_button.clicked.connect(self._edit_profile)
        delete_button.clicked.connect(self._delete_profile)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.profile_list)
        layout.addWidget(self.summary_label)
        layout.addLayout(buttons)

        self._refresh_profile_list()

    def profiles(self) -> list[SftpServerProfile]:
        return [self._profiles[name] for name in sorted(self._profiles, key=str.casefold)]

    def deleted_profile_names(self) -> list[str]:
        return sorted(self._deleted_profiles, key=str.casefold)

    def _refresh_profile_list(self) -> None:
        current = self.profile_list.currentItem().text() if self.profile_list.currentItem() else None
        self.profile_list.clear()
        self.profile_list.addItems(sorted(self._profiles, key=str.casefold))
        if current and current in self._profiles:
            matches = self.profile_list.findItems(current, Qt.MatchFlag.MatchExactly)
            if matches:
                self.profile_list.setCurrentItem(matches[0])
                return
        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        else:
            self.summary_label.setText(
                "\u8fd8\u6ca1\u6709\u5df2\u4fdd\u5b58\u670d\u52a1\u5668\u3002"
            )

    def _handle_selection_changed(self, name: str) -> None:
        self._selected_profile = self._profiles.get(name)
        if self._selected_profile is None:
            self.summary_label.setText("\u8bf7\u9009\u62e9\u5de6\u4fa7\u670d\u52a1\u5668\u3002")
            return
        auth_label = (
            "\u5bc6\u7801"
            if self._selected_profile.auth_mode == SftpAuthMode.PASSWORD
            else "\u5bc6\u94a5"
        )
        self.summary_label.setText(
            f"{self._selected_profile.host}:{self._selected_profile.port}  "
            f"{self._selected_profile.username}  {auth_label}"
        )

    def _add_profile(self) -> None:
        dialog = ServerProfileDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        self._profiles[profile.name] = profile
        self._deleted_profiles.discard(profile.name)
        self._refresh_profile_list()

    def _edit_profile(self) -> None:
        if self._selected_profile is None:
            QMessageBox.information(
                self,
                "\u6ca1\u6709\u9009\u4e2d",
                "\u8bf7\u5148\u9009\u4e2d\u4e00\u4e2a\u670d\u52a1\u5668\u3002",
            )
            return
        original_name = self._selected_profile.name
        dialog = ServerProfileDialog(self._selected_profile, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        if profile.name != original_name:
            self._profiles.pop(original_name, None)
            self._deleted_profiles.add(original_name)
        self._profiles[profile.name] = profile
        self._deleted_profiles.discard(profile.name)
        self._refresh_profile_list()

    def _delete_profile(self) -> None:
        if self._selected_profile is None:
            QMessageBox.information(
                self,
                "\u6ca1\u6709\u9009\u4e2d",
                "\u8bf7\u5148\u9009\u4e2d\u4e00\u4e2a\u670d\u52a1\u5668\u3002",
            )
            return
        name = self._selected_profile.name
        self._profiles.pop(name, None)
        self._deleted_profiles.add(name)
        self._selected_profile = None
        self._refresh_profile_list()


class ServerSelectionDialog(QDialog):
    def __init__(self, profiles: list[SftpServerProfile], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u9009\u62e9\u670d\u52a1\u5668")
        self.profile_combo = QComboBox()
        for profile in profiles:
            self.profile_combo.addItem(_server_label(profile), profile.name)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        select_button = QPushButton("\u4e0b\u4e00\u6b65")
        cancel_button = QPushButton("\u53d6\u6d88")
        select_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(select_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("\u8bf7\u9009\u62e9\u4e00\u4e2a\u5df2\u4fdd\u5b58\u670d\u52a1\u5668\u3002"))
        layout.addWidget(self.profile_combo)
        layout.addLayout(buttons)

    def selected_profile_name(self) -> str:
        return str(self.profile_combo.currentData())


class RemoteDirectoryDialog(QDialog):
    def __init__(
        self,
        profiles: SftpServerProfile | list[SftpServerProfile],
        remote_browser_service: RemoteBrowserService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u9009\u62e9\u670d\u52a1\u5668\u76ee\u5f55")
        if isinstance(profiles, SftpServerProfile):
            profile_list = [profiles]
        else:
            profile_list = list(profiles)
        if not profile_list:
            raise ValueError("RemoteDirectoryDialog requires at least one server profile.")
        self._profiles = {profile.name: profile for profile in profile_list}
        self.remote_browser_service = remote_browser_service
        self.profile_combo = QComboBox()
        for profile in profile_list:
            self.profile_combo.addItem(_server_label(profile), profile.name)
        self.profile_combo.currentIndexChanged.connect(self._handle_profile_changed)
        self.selected_path: str = self._current_profile().default_root or "/"

        self.path_label = QLabel(self.selected_path)
        self.path_edit = QLineEdit(self.selected_path)
        self.status_label = QLabel("")
        self.error_label = QLabel("")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["\u76ee\u5f55"])
        self.tree.itemExpanded.connect(self._load_children_for_item)
        self.tree.currentItemChanged.connect(self._handle_current_item_changed)

        jump_button = QPushButton("\u8df3\u8f6c")
        refresh_button = QPushButton("\u5237\u65b0")
        bind_button = QPushButton("\u7ed1\u5b9a")
        cancel_button = QPushButton("\u53d6\u6d88")
        jump_button.clicked.connect(self.load_current_path)
        refresh_button.clicked.connect(self.load_root)
        bind_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        path_row = QWidget()
        path_row_layout = QHBoxLayout(path_row)
        path_row_layout.setContentsMargins(0, 0, 0, 0)
        path_row_layout.addWidget(self.path_edit, 1)
        path_row_layout.addWidget(jump_button)

        server_row = QWidget()
        server_row_layout = QHBoxLayout(server_row)
        server_row_layout.setContentsMargins(0, 0, 0, 0)
        server_row_layout.addWidget(QLabel("\u670d\u52a1\u5668"))
        server_row_layout.addWidget(self.profile_combo, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(bind_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(server_row)
        layout.addWidget(self.path_label)
        layout.addWidget(path_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)

    def load_root(self) -> None:
        self._load_path(self._current_profile().default_root or "/")

    def load_current_path(self) -> None:
        self._load_path(self.path_edit.text().strip() or "/")

    def selected_profile_name(self) -> str:
        return str(self.profile_combo.currentData())

    def _load_path(self, path: str) -> None:
        root_path = path or "/"
        self.tree.clear()
        self.error_label.setText("")
        self.status_label.setText("\u6b63\u5728\u52a0\u8f7d...")
        self.selected_path = root_path
        self.path_label.setText(root_path)
        self.path_edit.setText(root_path)
        root_item = QTreeWidgetItem([root_path])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_path)
        self.tree.addTopLevelItem(root_item)
        self._populate_children(root_item, root_path)
        self.tree.setCurrentItem(root_item)

    def _load_children_for_item(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if item.childCount() == 1 and item.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
            item.takeChildren()
            self.status_label.setText("\u6b63\u5728\u52a0\u8f7d...")
            self.error_label.setText("")
            self._populate_children(item, path)

    def _populate_children(self, item: QTreeWidgetItem, path: str) -> None:
        try:
            nodes = self.remote_browser_service.list_directories(self._current_profile(), path)
        except Exception:
            self.error_label.setText("\u76ee\u5f55\u52a0\u8f7d\u5931\u8d25")
            self.status_label.setText("\u52a0\u8f7d\u5931\u8d25")
            return

        if not nodes and item.parent() is None:
            self.status_label.setText("\u7a7a\u76ee\u5f55")
        else:
            self.status_label.setText("")

        for node in nodes:
            child = QTreeWidgetItem([node.name])
            child.setData(0, Qt.ItemDataRole.UserRole, node.path)
            item.addChild(child)
            if node.has_children:
                placeholder = QTreeWidgetItem(["\u6b63\u5728\u52a0\u8f7d..."])
                placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
                child.addChild(placeholder)

    def _handle_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        if current is None:
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.selected_path = path
            self.path_label.setText(path)
            self.path_edit.setText(path)

    def _current_profile(self) -> SftpServerProfile:
        profile_name = self.selected_profile_name()
        return self._profiles[profile_name]

    def _handle_profile_changed(self) -> None:
        self.load_root()


class PaneBindingDialog(QDialog):
    def __init__(
        self,
        pane_count: int,
        profile_names: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u7ed1\u5b9a\u7a97\u53e3")

        self.pane_combo = QComboBox()
        for index in range(pane_count):
            self.pane_combo.addItem(f"\u7a97\u53e3 {index + 1}", index)

        self.source_type_combo = QComboBox()
        self.source_type_combo.addItem("\u672c\u5730\u76ee\u5f55", "local")
        self.source_type_combo.addItem("\u8fdc\u7aef\u76ee\u5f55", "remote")

        self.local_path_edit = QLineEdit("")
        browse_button = QPushButton("\u9009\u62e9\u76ee\u5f55")
        browse_button.clicked.connect(self._browse_local_directory)

        local_row = QWidget()
        local_layout = QHBoxLayout(local_row)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.addWidget(self.local_path_edit, 1)
        local_layout.addWidget(browse_button)

        self.profile_combo = QComboBox()
        for name in profile_names:
            self.profile_combo.addItem(name, name)
        self.remote_path_edit = QLineEdit("")

        form = QFormLayout()
        form.addRow("\u7a97\u53e3", self.pane_combo)
        form.addRow("\u6765\u6e90\u7c7b\u578b", self.source_type_combo)
        form.addRow("\u672c\u5730\u76ee\u5f55", local_row)
        form.addRow("\u670d\u52a1\u5668", self.profile_combo)
        form.addRow("\u8fdc\u7aef\u76ee\u5f55", self.remote_path_edit)

        buttons_row = QWidget()
        buttons = QHBoxLayout(buttons_row)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch(1)
        bind_button = QPushButton("\u7ed1\u5b9a")
        cancel_button = QPushButton("\u53d6\u6d88")
        bind_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(bind_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons_row)

        self.source_type_combo.currentIndexChanged.connect(self._update_mode)
        self._update_mode()

    def binding(self) -> dict[str, object]:
        return {
            "pane_index": self.pane_combo.currentData(),
            "source_type": self.source_type_combo.currentData(),
            "local_path": self.local_path_edit.text().strip(),
            "profile_name": self.profile_combo.currentData(),
            "remote_path": self.remote_path_edit.text().strip(),
        }

    def accept(self) -> None:
        binding = self.binding()
        if binding["source_type"] == "local":
            if not binding["local_path"]:
                QMessageBox.warning(
                    self,
                    "\u4fe1\u606f\u4e0d\u5b8c\u6574",
                    "\u8bf7\u9009\u62e9\u672c\u5730\u76ee\u5f55\u3002",
                )
                return
        else:
            if not binding["profile_name"] or not binding["remote_path"]:
                QMessageBox.warning(
                    self,
                    "\u4fe1\u606f\u4e0d\u5b8c\u6574",
                    "\u8bf7\u9009\u62e9\u670d\u52a1\u5668\u5e76\u586b\u5199\u8fdc\u7aef\u76ee\u5f55\u3002",
                )
                return
        super().accept()

    def _browse_local_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "\u9009\u62e9\u672c\u5730\u76ee\u5f55",
            str(Path.home()),
        )
        if path:
            self.local_path_edit.setText(path)

    def _update_mode(self) -> None:
        is_local = self.source_type_combo.currentData() == "local"
        self.local_path_edit.setEnabled(is_local)
        self.profile_combo.setEnabled(not is_local)
        self.remote_path_edit.setEnabled(not is_local)


class SaveRecordDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("保存记录")
        self.name_edit = QLineEdit("")

        form = QFormLayout()
        form.addRow("记录名称", self.name_edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def record_name(self) -> str:
        return self.name_edit.text().strip()

    def accept(self) -> None:
        if not self.record_name():
            QMessageBox.warning(self, "信息不完整", "请输入记录名称。")
            return
        super().accept()


class ImportRecordDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导入记录")
        self.json_edit = QTextEdit()

        load_button = QPushButton("选择文件")
        import_button = QPushButton("导入")
        cancel_button = QPushButton("取消")
        load_button.clicked.connect(self._load_file)
        import_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(load_button)
        buttons.addStretch(1)
        buttons.addWidget(import_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("粘贴 JSON 或选择文件"))
        layout.addWidget(self.json_edit, 1)
        layout.addLayout(buttons)

    def import_text(self) -> str:
        return self.json_edit.toPlainText().strip()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择记录文件",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if path:
            self.json_edit.setPlainText(Path(path).read_text(encoding="utf-8"))


class SessionRecordBrowserDialog(QDialog):
    def __init__(
        self,
        records: list[SessionRecord],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("查看记录")
        self._records = {record.id: record for record in records}
        self._selected_action: str | None = None
        self.record_list = QListWidget()
        for record in records:
            compare_label = (
                "共有文件" if record.compare_mode == CompareMode.COMMON else "主目录基准"
            )
            item_text = (
                f"{record.name}  {record.saved_at}  {record.layout_mode}  "
                f"{compare_label}  {len(record.panes)} 窗口"
            )
            self.record_list.addItem(item_text)
            self.record_list.item(self.record_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, record.id
            )

        save_current_button = QPushButton("保存当前记录")
        import_button = QPushButton("导入记录")
        apply_button = QPushButton("应用")
        copy_button = QPushButton("复制 JSON")
        export_button = QPushButton("导出文件")
        delete_button = QPushButton("删除")
        close_button = QPushButton("关闭")

        save_current_button.clicked.connect(lambda: self._accept_with_action("save"))
        import_button.clicked.connect(lambda: self._accept_with_action("import"))
        apply_button.clicked.connect(lambda: self._accept_with_action("apply", requires_selection=True))
        copy_button.clicked.connect(lambda: self._accept_with_action("copy", requires_selection=True))
        export_button.clicked.connect(
            lambda: self._accept_with_action("export", requires_selection=True)
        )
        delete_button.clicked.connect(
            lambda: self._accept_with_action("delete", requires_selection=True)
        )
        close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(save_current_button)
        buttons.addWidget(import_button)
        buttons.addWidget(apply_button)
        buttons.addWidget(copy_button)
        buttons.addWidget(export_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.record_list, 1)
        layout.addLayout(buttons)

    def selected_action(self) -> str | None:
        return self._selected_action

    def selected_record_id(self) -> str | None:
        item = self.record_list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _accept_with_action(self, action: str, *, requires_selection: bool = False) -> None:
        if requires_selection and self.selected_record_id() is None:
            QMessageBox.information(self, "没有选中", "请先选择一条记录。")
            return
        self._selected_action = action
        self.accept()


class ToleranceWindow(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        window_state_store: WindowStateStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._window_state_store = window_state_store or WindowStateStore()
        self.setWindowTitle("容差图")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._tolerance_service = ToleranceMapService()
        self._thread_pool = QThreadPool.globalInstance()
        self.pane_checks: list[QPushButton] = []
        self._pane_ids: list[int] = []
        self._source_images: dict[int, QImage] = {}
        self._current_tolerance_image: QImage | None = None
        self._prepared = None
        self._view_mode = "preview"
        self._pending_sync_view_state: tuple[float, float, float] = (1.0, 0.5, 0.5)
        self._compute_job_id = 0
        self._active_job_id = 0
        self._sync_refresh_timer = QTimer(self)
        self._sync_refresh_timer.setSingleShot(True)
        self._sync_refresh_timer.setInterval(120)
        self._sync_refresh_timer.timeout.connect(self._refresh_tolerance_map)
        self._pane_button_base_style = (
            "QPushButton {"
            " background-color: #ffffff;"
            " border: 1px solid #d6deea;"
            " border-radius: 10px;"
            " padding: 8px 12px;"
            " text-align: left;"
            "}"
        )
        self._pane_button_selected_style = (
            "QPushButton {"
            " background-color: #eaf4ff;"
            " border: 2px solid #4da3ff;"
            " border-radius: 10px;"
            " padding: 7px 11px;"
            " text-align: left;"
            " color: #123a66;"
            " font-weight: 600;"
            "}"
        )
        self._tool_button_base_style = (
            "QPushButton {"
            " background-color: #ffffff;"
            " border: 1px solid #d6deea;"
            " border-radius: 10px;"
            " padding: 8px 14px;"
            "}"
        )
        self._tool_button_selected_style = (
            "QPushButton {"
            " background-color: #eaf4ff;"
            " border: 2px solid #4da3ff;"
            " border-radius: 10px;"
            " padding: 7px 13px;"
            " color: #123a66;"
            " font-weight: 600;"
            "}"
        )

        self.algorithm_buttons: dict[ToleranceAlgorithm, QPushButton] = {}
        self.algorithm_group = QButtonGroup(self)
        self.algorithm_group.setExclusive(True)
        algorithm_row = QWidget()
        algorithm_layout = QHBoxLayout(algorithm_row)
        algorithm_layout.setContentsMargins(0, 0, 0, 0)
        algorithm_layout.setSpacing(8)
        for text, algorithm in (
            ("单通道", ToleranceAlgorithm.MAX_CHANNEL),
            ("平均值", ToleranceAlgorithm.AVERAGE),
            ("欧氏距离", ToleranceAlgorithm.EUCLIDEAN),
        ):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setStyleSheet(self._tool_button_base_style)
            button.clicked.connect(self._handle_algorithm_changed)
            self.algorithm_group.addButton(button)
            self.algorithm_buttons[algorithm] = button
            algorithm_layout.addWidget(button)
        self.algorithm_buttons[ToleranceAlgorithm.MAX_CHANNEL].setChecked(True)

        self.tolerance_slider = QSpinBox()
        self.tolerance_slider.setRange(0, 255)
        self.tolerance_slider.setValue(10)
        self.tolerance_slider.valueChanged.connect(self._refresh_tolerance_map)

        self.preview_mode_button = QPushButton("预览")
        self.preview_mode_button.setCheckable(True)
        self.sync_mode_button = QPushButton("同步查看")
        self.sync_mode_button.setCheckable(True)
        self.view_mode_group = QButtonGroup(self)
        self.view_mode_group.setExclusive(True)
        self.view_mode_group.addButton(self.preview_mode_button)
        self.view_mode_group.addButton(self.sync_mode_button)
        self.preview_mode_button.setChecked(True)
        self.preview_mode_button.clicked.connect(lambda: self._set_view_mode("preview"))
        self.sync_mode_button.clicked.connect(lambda: self._set_view_mode("sync"))

        view_mode_row = QWidget()
        view_mode_layout = QHBoxLayout(view_mode_row)
        view_mode_layout.setContentsMargins(0, 0, 0, 0)
        view_mode_layout.setSpacing(8)
        view_mode_layout.addWidget(self.preview_mode_button)
        view_mode_layout.addWidget(self.sync_mode_button)
        view_mode_layout.addStretch(1)

        self.current_filename_label = QLabel("")
        self.status_label = QLabel("请选择两个窗口")
        self.left_rgb_label = QLabel("")
        self.right_rgb_label = QLabel("")
        self.tolerance_view = ToleranceImageView()
        self.tolerance_view.set_empty_text("请选择两个窗口")

        self.pane_host = QWidget()
        self.pane_layout = QVBoxLayout(self.pane_host)
        self.pane_layout.setContentsMargins(0, 0, 0, 0)

        controls = QFormLayout()
        controls.addRow("算法", algorithm_row)
        controls.addRow("查看方式", view_mode_row)
        controls.addRow("容差", self.tolerance_slider)

        layout = QVBoxLayout(self)
        layout.addWidget(self.current_filename_label)
        layout.addWidget(self.pane_host)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tolerance_view, 1)
        layout.addWidget(self.left_rgb_label)
        layout.addWidget(self.right_rgb_label)

        self._refresh_tool_button_styles()
        self.tolerance_view.set_interactive_enabled(False)
        self._restore_window_size()

    def set_available_panes(self, pane_names: list[str]) -> None:
        selected_before = set(self._selected_pane_ids())
        while self.pane_layout.count():
            item = self.pane_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.pane_checks = []
        self._pane_ids = list(range(len(pane_names)))
        for name in pane_names:
            check = QPushButton(name)
            check.setCheckable(True)
            check.toggled.connect(self._enforce_two_selection_limit)
            check.setStyleSheet(self._pane_button_base_style)
            self.pane_checks.append(check)
            self.pane_layout.addWidget(check)
        for pane_id, check in zip(self._pane_ids, self.pane_checks):
            if pane_id in selected_before:
                check.setChecked(True)
        self._refresh_pane_check_styles()

    def set_selected_panes(self, pane_ids: list[int]) -> None:
        allowed = set(pane_ids[:2])
        for pane_id, check in zip(self._pane_ids, self.pane_checks):
            check.setChecked(pane_id in allowed)
        self._refresh_pane_check_styles()
        self._refresh_tolerance_map()

    def _enforce_two_selection_limit(self) -> None:
        checked = [check for check in self.pane_checks if check.isChecked()]
        if len(checked) <= 2:
            self._refresh_pane_check_styles()
            self._refresh_tolerance_map()
            return
        checked[-1].setChecked(False)
        self._refresh_pane_check_styles()
        self._refresh_tolerance_map()

    def set_source_images(self, images_by_pane: dict[int, QImage], current_filename: str) -> None:
        self._source_images = dict(images_by_pane)
        self.current_filename_label.setText(current_filename)
        self._refresh_tolerance_map()

    def current_tolerance_image(self) -> QImage | None:
        return self._current_tolerance_image

    def selected_algorithm(self) -> ToleranceAlgorithm:
        for algorithm, button in self.algorithm_buttons.items():
            if button.isChecked():
                return algorithm
        return ToleranceAlgorithm.MAX_CHANNEL

    def view_mode(self) -> str:
        return self._view_mode

    def set_sync_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        self._pending_sync_view_state = (zoom, center_x, center_y)
        if self._view_mode == "sync":
            self.tolerance_view.set_view_state(1.0, center_x, center_y)
            if self._selected_pane_ids():
                self._sync_refresh_timer.start()

    def update_hover_position(self, normalized_x: float, normalized_y: float) -> None:
        if self._prepared is None:
            return
        sample = self._tolerance_service.sample_at(self._prepared, normalized_x, normalized_y)
        self.left_rgb_label.setText(f"左图 RGB: {sample.left_rgb}")
        self.right_rgb_label.setText(
            f"右图 RGB: {sample.right_rgb}  差值: {sample.difference}"
        )

    def _selected_pane_ids(self) -> list[int]:
        return [
            pane_id
            for pane_id, check in zip(self._pane_ids, self.pane_checks)
            if check.isChecked()
        ]

    def _refresh_pane_check_styles(self) -> None:
        for check in self.pane_checks:
            check.setStyleSheet(
                self._pane_button_selected_style if check.isChecked() else self._pane_button_base_style
            )

    def _refresh_tool_button_styles(self) -> None:
        for button in self.algorithm_buttons.values():
            button.setStyleSheet(
                self._tool_button_selected_style if button.isChecked() else self._tool_button_base_style
            )
        for button in (self.preview_mode_button, self.sync_mode_button):
            button.setStyleSheet(
                self._tool_button_selected_style if button.isChecked() else self._tool_button_base_style
            )

    def _handle_algorithm_changed(self) -> None:
        self._refresh_tool_button_styles()
        self._refresh_tolerance_map()

    def _set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self.preview_mode_button.setChecked(mode == "preview")
        self.sync_mode_button.setChecked(mode == "sync")
        self._refresh_tool_button_styles()
        self.tolerance_view.set_interactive_enabled(mode == "sync")
        self._refresh_tolerance_map()

    def _refresh_tolerance_map(self) -> None:
        selected = self._selected_pane_ids()
        if len(selected) != 2:
            self._prepared = None
            self._current_tolerance_image = None
            self.status_label.setText("请选择两个窗口")
            self.tolerance_view.set_empty_text("请选择两个窗口")
            self.tolerance_view.set_image(None)
            return
        left = self._source_images.get(selected[0])
        right = self._source_images.get(selected[1])
        if left is None or right is None:
            self._prepared = None
            self._current_tolerance_image = None
            self.status_label.setText("当前图片不可用")
            self.tolerance_view.set_empty_text("当前图片不可用")
            self.tolerance_view.set_image(None)
            return
        algorithm = self.selected_algorithm()
        preview_size = self._preview_max_size()
        roi = self._current_roi(left, right)
        self._compute_job_id += 1
        self._active_job_id = self._compute_job_id
        self.status_label.setText("正在生成容差图...")
        self.tolerance_view.set_empty_text("")
        task = ToleranceComputeTask(
            self._tolerance_service,
            {
                "job_id": self._active_job_id,
                "left": left,
                "right": right,
                "tolerance": self.tolerance_slider.value(),
                "algorithm": algorithm,
                "preview_size": preview_size,
                "roi": roi,
                "sync_mode": self._view_mode == "sync",
            },
        )
        task.signals.preview_ready.connect(self._handle_preview_ready)
        task.signals.final_ready.connect(self._handle_final_ready)
        self._thread_pool.start(task)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display_pixmap()

    def closeEvent(self, event) -> None:
        self._active_job_id = -1
        self._sync_refresh_timer.stop()
        self._window_state_store.save_window_size(
            "tolerance_window",
            self.width(),
            self.height(),
        )
        self._window_state_store.save_window_position(
            "tolerance_window",
            self.x(),
            self.y(),
        )
        super().closeEvent(event)

    def _preview_max_size(self) -> tuple[int, int]:
        width = max(320, self.tolerance_view.width() or 640)
        height = max(180, self.tolerance_view.height() or 360)
        return (width, height)

    def _current_roi(self, left: QImage, right: QImage) -> tuple[int, int, int, int] | None:
        if self._view_mode != "sync":
            return None
        zoom, center_x, center_y = self._pending_sync_view_state
        if zoom <= 1.0:
            return None
        comparison_width = max(left.width(), right.width())
        comparison_height = max(left.height(), right.height())
        roi_width = max(1, round(comparison_width / zoom))
        roi_height = max(1, round(comparison_height / zoom))
        center_px = round(center_x * comparison_width)
        center_py = round(center_y * comparison_height)
        x = max(0, min(comparison_width - roi_width, center_px - roi_width // 2))
        y = max(0, min(comparison_height - roi_height, center_py - roi_height // 2))
        return (x, y, roi_width, roi_height)

    def _update_display_pixmap(self) -> None:
        if self._current_tolerance_image is None or self._current_tolerance_image.isNull():
            return
        self.tolerance_view.set_image(self._current_tolerance_image)
        if self._view_mode == "sync":
            _zoom, center_x, center_y = self._pending_sync_view_state
            self.tolerance_view.set_view_state(1.0, center_x, center_y)

    def _handle_preview_ready(
        self, job_id: int, image: QImage, prepared: PreparedToleranceComparison
    ) -> None:
        if job_id != self._active_job_id:
            return
        self._prepared = prepared
        self._current_tolerance_image = image
        self.status_label.setText("容差图预览已更新")
        self._update_display_pixmap()

    def _handle_final_ready(
        self, job_id: int, image: QImage, prepared: PreparedToleranceComparison
    ) -> None:
        if job_id != self._active_job_id:
            return
        self._prepared = prepared
        self._current_tolerance_image = image
        self.status_label.setText("容差图已更新")
        self._update_display_pixmap()

    def _restore_window_size(self) -> None:
        saved_size = self._window_state_store.load_window_size("tolerance_window")
        if saved_size is not None:
            self.resize(*saved_size)
        else:
            self.resize(640, 420)
        saved_position = self._window_state_store.load_window_position("tolerance_window")
        if saved_position is not None:
            self._restore_window_position(saved_position)

    def _restore_window_position(self, position: tuple[int, int]) -> None:
        target = QRect(position[0], position[1], self.width(), self.height())
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(target):
                self.move(*position)
                return
