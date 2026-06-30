from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


class ImageViewport(QWidget):
    def __init__(self, pane: "ImagePaneWidget") -> None:
        super().__init__(pane)
        self._pane = pane
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAcceptDrops(True)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101217"))

        pixmap = self._pane._base_pixmap
        if pixmap.isNull():
            return

        viewport_width = max(1, self.width())
        viewport_height = max(1, self.height())
        fit_scale = min(
            viewport_width / pixmap.width(),
            viewport_height / pixmap.height(),
        )
        rendered_width = pixmap.width() * fit_scale * self._pane._zoom_factor
        rendered_height = pixmap.height() * fit_scale * self._pane._zoom_factor
        self._pane._rendered_size = (max(1, int(rendered_width)), max(1, int(rendered_height)))

        offset_x, offset_y = self._pane._clamp_pan(rendered_width, rendered_height)
        target = QRectF(offset_x, offset_y, rendered_width, rendered_height)
        source = QRectF(0, 0, pixmap.width(), pixmap.height())

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(target, pixmap, source)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pane._has_image and event.angleDelta().y() != 0:
            steps = 1 if event.angleDelta().y() > 0 else -1
            self._pane.apply_zoom_delta(steps, event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._pane._has_image
            and event.button() == Qt.MouseButton.LeftButton
            and self._pane._zoom_factor > 1.0
        ):
            self._pane._dragging = True
            self._pane._last_drag_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pane._has_image:
            self._pane._emit_hover_position(event.position())
        if self._pane._dragging and self._pane._last_drag_pos is not None:
            delta = event.position() - self._pane._last_drag_pos
            self._pane._last_drag_pos = event.position()
            self._pane._pan_x += int(delta.x())
            self._pane._pan_y += int(delta.y())
            self._pane._sync_view()
            event.accept()
            return

        if self._pane._zoom_factor > 1.0:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pane._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._pane._dragging = False
            self._pane._last_drag_pos = None
            if self._pane._zoom_factor > 1.0:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:
        self._pane.dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        self._pane.dropEvent(event)


class ImagePaneWidget(QFrame):
    view_state_changed = Signal(float, float, float)
    directory_dropped = Signal(str)
    local_bind_requested = Signal()
    remote_bind_requested = Signal()
    clear_requested = Signal()
    swap_requested = Signal()
    copy_path_requested = Signal()
    hover_position_changed = Signal(float, float)
    activated = Signal()

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("imagePane")
        self.title_label = QLabel(title)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.clear_button = QPushButton("\u6e05\u7a7a")
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.swap_button = QPushButton("\u4ea4\u6362")
        self.swap_button.clicked.connect(self.swap_requested.emit)
        self.copy_path_button = QPushButton("\u590d\u5236\u8def\u5f84")
        self.copy_path_button.clicked.connect(self.copy_path_requested.emit)
        self.image_viewport = ImageViewport(self)
        self.status_label = QLabel("\u672a\u7ed1\u5b9a\u76ee\u5f55")
        self.local_bind_button = QPushButton("\u9009\u62e9\u672c\u5730\u76ee\u5f55")
        self.remote_bind_button = QPushButton("\u9009\u62e9\u670d\u52a1\u5668\u76ee\u5f55")
        self.local_bind_button.clicked.connect(self.local_bind_requested.emit)
        self.remote_bind_button.clicked.connect(self.remote_bind_requested.emit)
        self._bound_path = ""
        self._has_image = False
        self._is_bound = False
        self._base_pixmap = QPixmap()
        self._zoom_factor = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._dragging = False
        self._last_drag_pos: QPointF | None = None
        self._rendered_size = (0, 0)
        self._suppress_view_state_signal = False
        self._swap_pending = False
        self._swap_locked = False
        self.setAcceptDrops(True)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(self.title_label, 1)
        header_layout.addWidget(self.swap_button)
        header_layout.addWidget(self.copy_path_button)
        header_layout.addWidget(self.clear_button)

        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(16, 16, 16, 16)
        empty_layout.setSpacing(8)
        empty_layout.addStretch(1)
        empty_layout.addWidget(self.local_bind_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addWidget(self.remote_bind_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)

        self.content_host = QWidget()
        self.content_host.setAcceptDrops(True)
        self.content_stack = QStackedLayout(self.content_host)
        self.content_stack.setContentsMargins(0, 0, 0, 0)
        self.content_stack.addWidget(self.empty_state)
        self.content_stack.addWidget(self.image_viewport)
        self.empty_state.setAcceptDrops(True)
        self.content_host.dragEnterEvent = self.dragEnterEvent
        self.content_host.dropEvent = self.dropEvent
        self.empty_state.dragEnterEvent = self.dragEnterEvent
        self.empty_state.dropEvent = self.dropEvent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(header)
        layout.addWidget(self.content_host, 1)
        layout.addWidget(self.status_label)

        self._base_stylesheet = """
ImagePaneWidget#imagePane {
    background-color: #f7f9fc;
    border: 1px solid #d8e1ec;
    border-radius: 14px;
}
ImagePaneWidget#imagePane QLabel {
    color: #203040;
}
ImagePaneWidget#imagePane QPushButton {
    background-color: #ffffff;
    border: 1px solid #d6deea;
    border-radius: 10px;
    padding: 6px 12px;
}
ImagePaneWidget#imagePane QPushButton:hover {
    background-color: #f3f7fb;
}
"""
        self._pending_stylesheet = """
ImagePaneWidget#imagePane {
    background-color: #fff8ee;
    border: 2px solid #f5a623;
    border-radius: 14px;
}
ImagePaneWidget#imagePane QLabel {
    color: #203040;
}
ImagePaneWidget#imagePane QPushButton {
    background-color: #ffffff;
    border: 1px solid #e5c88a;
    border-radius: 10px;
    padding: 6px 12px;
}
ImagePaneWidget#imagePane QPushButton:hover {
    background-color: #fff3de;
}
"""
        self._locked_stylesheet = """
ImagePaneWidget#imagePane {
    background-color: #f3f8ff;
    border: 2px solid #4da3ff;
    border-radius: 14px;
}
ImagePaneWidget#imagePane QLabel {
    color: #203040;
}
ImagePaneWidget#imagePane QPushButton {
    background-color: #ffffff;
    border: 1px solid #b9d7fb;
    border-radius: 10px;
    padding: 6px 12px;
}
ImagePaneWidget#imagePane QPushButton:hover {
    background-color: #eaf4ff;
}
"""
        self._apply_card_shadow()
        self._install_drag_forwarding(
            self.image_viewport,
            header,
            self.title_label,
            self.status_label,
            self.clear_button,
            self.swap_button,
            self.copy_path_button,
            self.content_host,
            self.empty_state,
            self.local_bind_button,
            self.remote_bind_button,
        )
        self.clear_binding_state()
        self.set_swap_state()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def status_text(self) -> str:
        return self.status_label.text()

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def title_text(self) -> str:
        return self.title_label.text()

    def set_bound_path(self, path: str) -> None:
        self._bound_path = path

    def bound_path(self) -> str:
        return self._bound_path

    def set_image(self, image: QImage, status: str) -> None:
        self._base_pixmap = QPixmap.fromImage(image)
        self._zoom_factor = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._dragging = False
        self._last_drag_pos = None
        self._has_image = True
        self._is_bound = True
        del status
        self.status_label.setText(f"{image.width()} x {image.height()}")
        self._update_bound_state_ui()
        self.clear_button.show()
        self._sync_view()

    def is_bound(self) -> bool:
        return self._is_bound

    def clear_binding_state(self) -> None:
        self._has_image = False
        self._is_bound = False
        self._bound_path = ""
        self._base_pixmap = QPixmap()
        self._zoom_factor = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._dragging = False
        self._last_drag_pos = None
        self._rendered_size = (0, 0)
        self.status_label.setText("\u672a\u7ed1\u5b9a\u76ee\u5f55")
        self._update_bound_state_ui()
        self.clear_button.hide()
        self.swap_button.hide()
        self.set_swap_state()
        self.image_viewport.update()

    def has_image(self) -> bool:
        return self._has_image

    def rendered_image_size(self) -> tuple[int, int]:
        return self._rendered_size

    def viewport_size(self) -> tuple[int, int]:
        return (self.image_viewport.width(), self.image_viewport.height())

    def zoom_factor(self) -> float:
        return self._zoom_factor

    def pan_offset(self) -> tuple[int, int]:
        return (self._pan_x, self._pan_y)

    def view_state(self) -> tuple[float, float, float]:
        center_x, center_y = self._current_center()
        return (self._zoom_factor, center_x, center_y)

    def set_view_state(self, zoom: float, center_x: float, center_y: float) -> None:
        if not self._has_image:
            return
        self._zoom_factor = max(1.0, min(16.0, zoom))
        if self._zoom_factor <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            rendered_width, rendered_height = self._compute_rendered_size(self._zoom_factor)
            self._pan_x = round(rendered_width * (0.5 - center_x))
            self._pan_y = round(rendered_height * (0.5 - center_y))
        self._sync_view()

    def apply_zoom_delta(self, steps: int, anchor_pos: QPointF | None = None) -> None:
        if not self._has_image:
            return
        if anchor_pos is None:
            anchor_pos = QPointF(
                self.image_viewport.width() / 2,
                self.image_viewport.height() / 2,
            )
        old_zoom = self._zoom_factor
        old_rendered_width, old_rendered_height = self._compute_rendered_size(old_zoom)
        old_offset_x, old_offset_y = self._clamp_pan(
            old_rendered_width,
            old_rendered_height,
        )
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
            viewport_width = max(1, self.image_viewport.width())
            viewport_height = max(1, self.image_viewport.height())
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
        self._sync_view()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.image_viewport.wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._has_image and event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        mapped = self._map_mouse_event_to_viewport(event)
        self.image_viewport.mousePressEvent(mapped)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        mapped = self._map_mouse_event_to_viewport(event)
        self.image_viewport.mouseMoveEvent(mapped)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        mapped = self._map_mouse_event_to_viewport(event)
        self.image_viewport.mouseReleaseEvent(mapped)

    def dragEnterEvent(self, event) -> None:
        path = self._extract_directory_path(event.mimeData())
        if path is not None:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        path = self._extract_directory_path(event.mimeData())
        if path is not None:
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        path = self._extract_directory_path(event.mimeData())
        if path is None:
            event.ignore()
            return
        self.directory_dropped.emit(path)
        event.acceptProposedAction()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._has_image:
            self._sync_view()

    def _update_bound_state_ui(self) -> None:
        self.clear_button.setVisible(self._is_bound)
        self.swap_button.setVisible(self._is_bound)
        self.copy_path_button.setVisible(self._is_bound and bool(self._bound_path))
        self.content_stack.setCurrentWidget(self.image_viewport if self._has_image else self.empty_state)

    def set_swap_state(self, *, pending: bool = False, locked: bool = False) -> None:
        self._swap_pending = pending
        self._swap_locked = locked
        if pending:
            self.setStyleSheet(self._pending_stylesheet)
            self.swap_button.setText("\u5f85\u4ea4\u6362")
            return
        if locked:
            self.setStyleSheet(self._locked_stylesheet)
            self.swap_button.setText("\u5df2\u914d\u5bf9")
            return
        self.setStyleSheet(self._base_stylesheet)
        self.swap_button.setText("\u4ea4\u6362")

    def _apply_card_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(24, 39, 75, 36))
        self.setGraphicsEffect(shadow)

    def _install_drag_forwarding(self, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return event.isAccepted()
        if event.type() == QEvent.Type.DragMove:
            self.dragMoveEvent(event)
            return event.isAccepted()
        if event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return event.isAccepted()
        return super().eventFilter(watched, event)

    def _sync_view(self) -> None:
        if self._base_pixmap.isNull():
            self._rendered_size = (0, 0)
            self.image_viewport.update()
            return
        self._rendered_size = self._compute_rendered_size()
        self._clamp_pan(*self._rendered_size)
        if self._zoom_factor > 1.0:
            self.image_viewport.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.image_viewport.unsetCursor()
        self.image_viewport.update()
        self._emit_view_state_changed()

    def _compute_rendered_size(self, zoom_factor: float | None = None) -> tuple[int, int]:
        viewport_width = max(1, self.image_viewport.width())
        viewport_height = max(1, self.image_viewport.height())
        fit_scale = min(
            viewport_width / self._base_pixmap.width(),
            viewport_height / self._base_pixmap.height(),
        )
        zoom = self._zoom_factor if zoom_factor is None else zoom_factor
        rendered_width = max(1, int(self._base_pixmap.width() * fit_scale * zoom))
        rendered_height = max(1, int(self._base_pixmap.height() * fit_scale * zoom))
        return (rendered_width, rendered_height)

    def _clamp_pan(self, rendered_width: float, rendered_height: float) -> tuple[float, float]:
        viewport_width = max(1, self.image_viewport.width())
        viewport_height = max(1, self.image_viewport.height())
        limit_x = max(0.0, (rendered_width - viewport_width) / 2.0)
        limit_y = max(0.0, (rendered_height - viewport_height) / 2.0)

        self._pan_x = int(max(-limit_x, min(limit_x, self._pan_x)))
        self._pan_y = int(max(-limit_y, min(limit_y, self._pan_y)))

        offset_x = (viewport_width - rendered_width) / 2.0 + self._pan_x
        offset_y = (viewport_height - rendered_height) / 2.0 + self._pan_y
        return (offset_x, offset_y)

    def _current_center(self) -> tuple[float, float]:
        rendered_width, rendered_height = self._rendered_size
        if rendered_width <= 0 or rendered_height <= 0 or self._zoom_factor <= 1.0:
            return (0.5, 0.5)
        center_x = 0.5 - (self._pan_x / rendered_width)
        center_y = 0.5 - (self._pan_y / rendered_height)
        return (
            max(0.0, min(1.0, center_x)),
            max(0.0, min(1.0, center_y)),
        )

    def _emit_view_state_changed(self) -> None:
        if self._suppress_view_state_signal or not self._has_image:
            return
        self.view_state_changed.emit(*self.view_state())

    def _emit_hover_position(self, position: QPointF) -> None:
        if not self._has_image or self._base_pixmap.isNull():
            return
        rendered_width, rendered_height = self._compute_rendered_size()
        offset_x, offset_y = self._clamp_pan(rendered_width, rendered_height)
        normalized_x = (position.x() - offset_x) / max(1.0, rendered_width)
        normalized_y = (position.y() - offset_y) / max(1.0, rendered_height)
        self.hover_position_changed.emit(
            max(0.0, min(1.0, normalized_x)),
            max(0.0, min(1.0, normalized_y)),
        )

    def _map_mouse_event_to_viewport(self, event: QMouseEvent) -> QMouseEvent:
        local = self.image_viewport.mapFrom(self, event.position().toPoint())
        global_pos = event.globalPosition()
        return QMouseEvent(
            event.type(),
            QPointF(local),
            global_pos,
            event.button(),
            event.buttons(),
            event.modifiers(),
        )

    def _extract_directory_path(self, mime_data) -> str | None:
        if not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            candidate = Path(url.toLocalFile())
            if candidate.is_dir():
                return str(candidate)
        return None
