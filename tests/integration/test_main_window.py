import time
from pathlib import Path

from PySide6.QtCore import QPoint, QMimeData, QTimer, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QDialog, QGraphicsDropShadowEffect

from remote_image_compare.domain.models import (
    CompareMode,
    SessionPaneBinding,
    ToleranceAlgorithm,
    SftpAuthConfig,
    SftpAuthMode,
    SftpConnectionConfig,
    SessionRecord,
    SftpServerProfile,
    SourceConfig,
    SourceKind,
)
from remote_image_compare.services.server_profile_store import ServerProfileStore
from remote_image_compare.services.session_record_store import SessionRecordStore
from remote_image_compare.services.window_state_store import WindowStateStore
from remote_image_compare.ui.dialogs import (
    ImportRecordDialog,
    RemoteDirectoryDialog,
    SaveRecordDialog,
    SessionRecordBrowserDialog,
    ServerProfileDialog,
    ServerSelectionDialog,
    ToleranceWindow,
)
from remote_image_compare.ui.main_window import MainWindow
from remote_image_compare.ui.pane_widgets import ImagePaneWidget


def _save_image(path: Path, width: int, height: int, color: int) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(color)
    assert image.save(str(path), "PNG")


def _drag_pane_by(pane: ImagePaneWidget, delta: QPoint) -> None:
    center = pane.rect().center()
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        center,
        pane.mapToGlobal(center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        center + delta,
        pane.mapToGlobal(center + delta),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        center + delta,
        pane.mapToGlobal(center + delta),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pane.mousePressEvent(press)
    pane.mouseMoveEvent(move)
    pane.mouseReleaseEvent(release)


def _click_pane_viewport(pane: ImagePaneWidget, pos: QPoint | None = None) -> None:
    click_pos = pos or pane.image_viewport.rect().center()
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        click_pos,
        pane.image_viewport.mapToGlobal(click_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        click_pos,
        pane.image_viewport.mapToGlobal(click_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(pane.image_viewport, press)
    QApplication.sendEvent(pane.image_viewport, release)


def _pane_swap_highlighted(pane: ImagePaneWidget) -> bool:
    return pane.swap_button.text() in {"待交换", "已配对"}


def test_main_window_has_default_layout(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "mulitImgViewer"
    assert window.active_pane_count == 6


def test_main_window_restores_saved_window_size(qtbot, tmp_path: Path) -> None:
    store = WindowStateStore(tmp_path / "window_state.json")
    first = MainWindow(window_state_store=store)
    qtbot.addWidget(first)
    first.move(140, 110)
    first.resize(1234, 777)
    first.close()

    second = MainWindow(window_state_store=store)
    qtbot.addWidget(second)

    assert second.size().width() == 1234
    assert second.size().height() == 777
    assert second.x() == 140
    assert second.y() == 110


def test_tolerance_window_restores_saved_window_size(qtbot, tmp_path: Path) -> None:
    store = WindowStateStore(tmp_path / "window_state.json")
    window = MainWindow(window_state_store=store)
    qtbot.addWidget(window)

    window.open_tolerance_window()
    assert window._tolerance_window is not None
    window._tolerance_window.move(220, 180)
    window._tolerance_window.resize(666, 444)
    window._tolerance_window.close()

    window.open_tolerance_window()

    assert window._tolerance_window.size().width() == 666
    assert window._tolerance_window.size().height() == 444
    assert window._tolerance_window.x() == 220
    assert window._tolerance_window.y() == 180


def test_main_window_exposes_file_mode_options(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.compare_mode_items() == ["共有文件", "主目录基准"]


def test_main_window_exposes_layout_mode_options(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.layout_mode_items() == ["1 x 2", "1 x 3", "2 x 2", "2 x 3"]
    assert window.active_pane_count == 6


def test_main_window_updates_file_list_from_catalog(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_catalog_items(["img1.jpg", "img2.jpg"])

    assert window.file_list_count() == 2
    assert window.current_file_label() == "0 / 2"
    assert window.current_filename_label.text() == ""


def test_pane_widget_shows_status_message(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    pane.set_status("Missing file")

    assert pane.status_text() == "Missing file"


def test_server_profile_dialog_enables_password_input_for_password_auth(qtbot) -> None:
    dialog = ServerProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.auth_mode_combo.currentData() == SftpAuthMode.PASSWORD
    assert dialog.password_edit.isEnabled() is True
    assert dialog.key_path_edit.isEnabled() is False


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


def test_session_record_browser_dialog_exposes_save_and_import_actions(qtbot) -> None:
    dialog = SessionRecordBrowserDialog([])
    qtbot.addWidget(dialog)

    dialog._accept_with_action("save")
    assert dialog.selected_action() == "save"


def test_tolerance_window_exposes_algorithm_choices(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)

    assert len(window.algorithm_buttons) == 3
    assert window.selected_algorithm() == ToleranceAlgorithm.MAX_CHANNEL


def test_tolerance_window_defaults_to_preview_mode(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)

    assert window.preview_mode_button.isChecked() is True
    assert window.sync_mode_button.isChecked() is False
    assert window.view_mode() == "preview"


def test_tolerance_window_limits_selection_to_two_panes(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2", "Pane 3"])

    window.pane_checks[0].setChecked(True)
    window.pane_checks[1].setChecked(True)
    window.pane_checks[2].setChecked(True)

    assert sum(1 for check in window.pane_checks if check.isChecked()) == 2


def test_tolerance_window_highlights_selected_panes_and_allows_deselect(qtbot) -> None:
    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2", "Pane 3"])

    qtbot.mouseClick(window.pane_checks[0], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.pane_checks[1], Qt.MouseButton.LeftButton)

    assert window.pane_checks[0].isChecked() is True
    assert window.pane_checks[1].isChecked() is True
    assert window.pane_checks[0].styleSheet() != window.pane_checks[2].styleSheet()
    assert window.pane_checks[1].styleSheet() != window.pane_checks[2].styleSheet()

    qtbot.mouseClick(window.pane_checks[0], Qt.MouseButton.LeftButton)

    assert window.pane_checks[0].isChecked() is False
    assert window.pane_checks[0].styleSheet() == window.pane_checks[2].styleSheet()


def test_tolerance_window_refreshes_when_algorithm_changes(qtbot) -> None:
    image_a = QImage(4, 4, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(4, 4, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")

    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
    first_map = window.current_tolerance_image()
    qtbot.mouseClick(window.algorithm_buttons[ToleranceAlgorithm.AVERAGE], Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
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
    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
    window.update_hover_position(0.5, 0.5)

    assert "17" in window.left_rgb_label.text()
    assert "34" in window.right_rgb_label.text()


def test_tolerance_window_keeps_large_map_within_preview_area(qtbot) -> None:
    image_a = QImage(3840, 2160, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(3840, 2160, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.resize(600, 500)
    window.show()
    qtbot.waitExposed(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")

    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
    pixmap = window.tolerance_view.current_display_pixmap()

    assert pixmap is not None
    assert pixmap.width() <= window.tolerance_view.width()
    assert pixmap.height() <= window.tolerance_view.height()


def test_tolerance_window_preview_mode_disables_interactive_zoom(qtbot) -> None:
    image_a = QImage(640, 480, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(640, 480, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.resize(700, 520)
    window.show()
    qtbot.waitExposed(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")

    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
    before = window.tolerance_view.zoom_factor()
    center = window.tolerance_view.rect().center()
    event = QWheelEvent(
        center,
        window.tolerance_view.mapToGlobal(center),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(window.tolerance_view, event)

    assert window.tolerance_view.zoom_factor() == before


def test_tolerance_window_sync_mode_uses_full_resolution_map(qtbot) -> None:
    image_a = QImage(1600, 1200, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(1600, 1200, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.resize(700, 520)
    window.show()
    qtbot.waitExposed(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])
    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")

    qtbot.mouseClick(window.sync_mode_button, Qt.MouseButton.LeftButton)

    assert window.view_mode() == "sync"
    qtbot.waitUntil(
        lambda: window.current_tolerance_image() is not None
        and window.current_tolerance_image().width() == 1600,
        timeout=4000,
    )
    assert window.current_tolerance_image().width() == 1600
    assert window.current_tolerance_image().height() == 1200


def test_tolerance_window_sync_mode_shows_preview_before_full_resolution(
    qtbot, monkeypatch
) -> None:
    image_a = QImage(1600, 1200, QImage.Format.Format_RGB32)
    image_a.fill(0xFF000000)
    image_b = QImage(1600, 1200, QImage.Format.Format_RGB32)
    image_b.fill(0xFF101010)

    window = ToleranceWindow()
    qtbot.addWidget(window)
    window.resize(700, 520)
    window.show()
    qtbot.waitExposed(window)
    window.set_available_panes(["Pane 1", "Pane 2"])
    window.set_selected_panes([0, 1])

    original = window._tolerance_service.build_tolerance_map

    def delayed_build(*args, **kwargs):
        if kwargs.get("max_size") is None:
            time.sleep(0.15)
        return original(*args, **kwargs)

    monkeypatch.setattr(window._tolerance_service, "build_tolerance_map", delayed_build)

    window.set_source_images({0: image_a, 1: image_b}, current_filename="img1.png")
    qtbot.mouseClick(window.sync_mode_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_tolerance_image() is not None)
    assert window.current_tolerance_image().width() < 1600
    qtbot.waitUntil(
        lambda: window.current_tolerance_image() is not None
        and window.current_tolerance_image().width() == 1600,
        timeout=4000,
    )


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


def test_server_profile_dialog_uses_chinese_labels(qtbot) -> None:
    dialog = ServerProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "服务器配置"
    assert dialog.auth_mode_combo.itemText(0) == "密码"
    assert dialog.auth_mode_combo.itemText(1) == "密钥"


def test_unbound_pane_exposes_local_and_remote_bind_actions(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    assert pane.is_bound() is False
    assert pane.local_bind_button.text() == "选择本地目录"
    assert pane.remote_bind_button.text() == "选择服务器目录"
    assert pane.status_text() == "未绑定目录"


def test_bound_pane_exposes_clear_action(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    pane.set_image(image, "img")

    assert pane.clear_button.isHidden() is False


def test_bound_pane_exposes_swap_action(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    pane.set_image(image, "img")

    assert pane.swap_button.isHidden() is False


def test_bound_pane_exposes_copy_path_action(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    pane.set_bound_path(r"D:\dataset\HR")
    pane.set_image(image, "img")

    assert pane.copy_path_button.isHidden() is False


def test_pane_title_label_text_is_selectable(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    assert (
        pane.title_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    )


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
        private_key_path=None,
        passphrase="",
        default_root="/srv/photos",
    )
    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()

    assert seen == ["/srv/photos"]


def test_remote_directory_dialog_uses_chinese_labels(qtbot) -> None:
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

    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            del profile, remote_path
            return []

    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "选择服务器目录"
    assert dialog.tree.headerItem().text(0) == "目录"


def test_remote_directory_dialog_shows_loading_then_empty_state(qtbot) -> None:
    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            del profile, remote_path
            return []

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
    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()

    assert dialog.status_label.text() == "空目录"
    assert dialog.error_label.text() == ""
    assert dialog.tree.topLevelItemCount() == 1
    assert dialog.tree.topLevelItem(0).text(0) == "/srv/photos"


def test_remote_directory_dialog_shows_error_state_when_load_fails(qtbot) -> None:
    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            del profile, remote_path
            raise RuntimeError("boom")

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
    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()

    assert dialog.error_label.text() == "目录加载失败"
    assert dialog.status_label.text() == "加载失败"


def test_remote_directory_dialog_path_input_loads_target_directory(qtbot) -> None:
    seen = []

    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            del profile
            seen.append(remote_path)
            return []

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
    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.path_edit.setText("/srv/photos/setA")
    dialog.load_current_path()

    assert seen == ["/srv/photos/setA"]
    assert dialog.selected_path == "/srv/photos/setA"
    assert dialog.path_label.text() == "/srv/photos/setA"


def test_remote_directory_dialog_tree_selection_syncs_path_input(qtbot) -> None:
    class FakeNode:
        def __init__(self, name: str, path: str, has_children: bool = False) -> None:
            self.name = name
            self.path = path
            self.has_children = has_children

    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            del profile
            if remote_path == "/srv/photos":
                return [FakeNode("setA", "/srv/photos/setA")]
            return []

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
    dialog = RemoteDirectoryDialog([profile], FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()
    child = dialog.tree.topLevelItem(0).child(0)
    dialog.tree.setCurrentItem(child)

    assert dialog.selected_path == "/srv/photos/setA"
    assert dialog.path_edit.text() == "/srv/photos/setA"
    assert dialog.path_label.text() == "/srv/photos/setA"


def test_remote_directory_dialog_can_switch_server_and_reload_root(qtbot) -> None:
    seen: list[tuple[str, str]] = []

    class FakeRemoteBrowserService:
        def list_directories(self, profile, remote_path):
            seen.append((profile.name, remote_path))
            return []

    profiles = [
        SftpServerProfile(
            name="wsl",
            host="127.0.0.1",
            port=2222,
            username="tester",
            auth_mode=SftpAuthMode.PASSWORD,
            password="pw",
            private_key_path=None,
            passphrase="",
            default_root="/srv/photos",
        ),
        SftpServerProfile(
            name="nas",
            host="10.0.0.8",
            port=22,
            username="viewer",
            auth_mode=SftpAuthMode.PASSWORD,
            password="pw",
            private_key_path=None,
            passphrase="",
            default_root="/data/images",
        ),
    ]

    dialog = RemoteDirectoryDialog(profiles, FakeRemoteBrowserService())
    qtbot.addWidget(dialog)

    dialog.load_root()
    dialog.profile_combo.setCurrentIndex(1)

    assert seen == [("wsl", "/srv/photos"), ("nas", "/data/images")]
    assert dialog.selected_profile_name() == "nas"
    assert dialog.path_edit.text() == "/data/images"


def test_main_window_exposes_chinese_toolbar_labels(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.toggle_sidebar_button.text() == "文件列表"
    assert window.server_manager_button.text() == "服务器"
    assert window.bind_source_button.text() == "绑定窗口"


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


def test_main_window_save_current_record_persists_snapshot(qtbot, tmp_path: Path, monkeypatch) -> None:
    image_root = tmp_path / "left"
    image_root.mkdir()
    _save_image(image_root / "img1.png", 8, 8, 0xFF224466)

    class FakeSaveRecordDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, parent=None) -> None:
            del parent

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def record_name(self) -> str:
            return "baseline compare"

    monkeypatch.setattr("remote_image_compare.ui.main_window.SaveRecordDialog", FakeSaveRecordDialog)

    window = MainWindow()
    qtbot.addWidget(window)
    window.session_record_store = SessionRecordStore(tmp_path / "session_records.json")
    window.bind_source_path(0, str(image_root))

    window.save_current_record()

    assert [record.name for record in window.session_record_store.list_records()] == [
        "baseline compare"
    ]


def test_main_window_swaps_pane_positions_and_preserves_titles(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)
    _save_image(right / "img1.png", 8, 8, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)

    assert window.grid_layout.itemAtPosition(0, 0).widget().title_text() == "Right"
    assert window.grid_layout.itemAtPosition(0, 1).widget().title_text() == "Left"


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


def test_main_window_remembers_swap_pair_for_fast_toggle(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)
    _save_image(right / "img1.png", 8, 8, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)
    window.handle_swap_requested(1)

    assert window.grid_layout.itemAtPosition(0, 0).widget().title_text() == "Left"
    assert window.grid_layout.itemAtPosition(0, 1).widget().title_text() == "Right"


def test_main_window_keeps_swapped_positions_after_navigation(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for name, color in (("img1.png", 0xFF224466), ("img2.png", 0xFF335577)):
        _save_image(left / name, 8, 8, color)
    for name, color in (("img1.png", 0xFF446688), ("img2.png", 0xFF557799)):
        _save_image(right / name, 8, 8, color)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)
    window.next_image()

    assert window.grid_layout.itemAtPosition(0, 0).widget().title_text() == "Right"
    assert window.grid_layout.itemAtPosition(0, 1).widget().title_text() == "Left"


def test_main_window_can_cancel_swap_selection(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.begin_swap_selection(0)
    window.cancel_swap_selection()

    assert window._pending_swap_index is None


def test_main_window_keeps_locked_swap_pair_highlighted(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)
    _save_image(right / "img1.png", 8, 8, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)

    assert window._locked_swap_pair == (0, 1)
    assert _pane_swap_highlighted(window._panes[0]) is True
    assert _pane_swap_highlighted(window._panes[1]) is True


def test_main_window_clears_locked_swap_pair_highlight_on_cancel(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF224466)
    _save_image(right / "img1.png", 8, 8, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.begin_swap_selection(0)
    window.handle_swap_requested(1)

    window.cancel_swap_selection()

    assert window._locked_swap_pair is None
    assert _pane_swap_highlighted(window._panes[0]) is False
    assert _pane_swap_highlighted(window._panes[1]) is False


def test_main_window_replaces_old_locked_swap_pair_highlight(qtbot, tmp_path: Path) -> None:
    pane_roots = []
    for index, color in enumerate((0xFF224466, 0xFF446688, 0xFF6688AA, 0xFF88AACC), start=1):
        root = tmp_path / f"pane{index}"
        root.mkdir()
        _save_image(root / "img1.png", 8, 8, color)
        pane_roots.append(root)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    for pane_index, root in enumerate(pane_roots):
        window.bind_source(
            pane_index,
            SourceConfig(
                id=f"pane-{pane_index + 1}",
                kind=SourceKind.LOCAL,
                display_name=f"Pane {pane_index + 1}",
                root_path=str(root),
                recursive=False,
            ),
        )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)
    window.handle_swap_requested(2)
    window.handle_swap_requested(3)

    assert window._locked_swap_pair == (2, 3)
    assert _pane_swap_highlighted(window._panes[0]) is False
    assert _pane_swap_highlighted(window._panes[1]) is False
    assert _pane_swap_highlighted(window._panes[2]) is True
    assert _pane_swap_highlighted(window._panes[3]) is True


def test_clicking_other_pane_clears_locked_swap_pair(qtbot, tmp_path: Path) -> None:
    pane_roots = []
    for index, color in enumerate((0xFF224466, 0xFF446688, 0xFF6688AA), start=1):
        root = tmp_path / f"pane{index}"
        root.mkdir()
        _save_image(root / "img1.png", 32, 32, color)
        pane_roots.append(root)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    for pane_index, root in enumerate(pane_roots):
        window.bind_source(
            pane_index,
            SourceConfig(
                id=f"pane-{pane_index + 1}",
                kind=SourceKind.LOCAL,
                display_name=f"Pane {pane_index + 1}",
                root_path=str(root),
                recursive=False,
            ),
        )
    window.layout_mode_combo.setCurrentText("1 x 3")
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.begin_swap_selection(0)
    window.handle_swap_requested(1)

    assert window._locked_swap_pair == (0, 1)
    assert window.grid_layout.itemAtPosition(0, 0).widget().title_text() == "Pane 2"
    assert window.grid_layout.itemAtPosition(0, 1).widget().title_text() == "Pane 1"

    _click_pane_viewport(window._panes[2])
    window.handle_swap_requested(0)

    assert window._locked_swap_pair is None
    assert window._pending_swap_index == 0
    assert window.grid_layout.itemAtPosition(0, 0).widget().title_text() == "Pane 2"
    assert window.grid_layout.itemAtPosition(0, 1).widget().title_text() == "Pane 1"


def test_locked_swap_does_not_reset_current_image_after_navigation(
    qtbot, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for name, color in (("img1.png", 0xFF224466), ("img2.png", 0xFF335577)):
        _save_image(left / name, 8, 8, color)
    for name, color in (("img1.png", 0xFF446688), ("img2.png", 0xFF557799)):
        _save_image(right / name, 8, 8, color)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.layout_mode_combo.setCurrentText("1 x 2")
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.begin_swap_selection(0)
    window.handle_swap_requested(1)

    window.next_image()
    assert window.current_filename() == "img2.png"

    window.handle_swap_requested(0)

    assert window.current_filename() == "img2.png"
    assert window.current_filename_label.text() == "img2.png"


def test_server_selection_dialog_shows_server_details(qtbot) -> None:
    profiles = [
        SftpServerProfile(
            name="WSL",
            host="127.0.0.1",
            port=2222,
            username="kumi",
            auth_mode=SftpAuthMode.PASSWORD,
            password="pw",
            private_key_path=None,
            passphrase="",
            default_root="/srv/photos",
        ),
        SftpServerProfile(
            name="NAS",
            host="10.0.0.8",
            port=22,
            username="viewer",
            auth_mode=SftpAuthMode.KEY,
            password="",
            private_key_path="C:/keys/id_ed25519",
            passphrase="",
            default_root="/data/photos",
        ),
    ]

    chooser = ServerSelectionDialog(profiles)
    qtbot.addWidget(chooser)

    assert chooser.profile_combo.itemText(0) == "WSL  127.0.0.1:2222  kumi"
    assert chooser.profile_combo.itemText(1) == "NAS  10.0.0.8:22  viewer"
    assert chooser.selected_profile_name() == "WSL"


def test_main_window_remote_bind_uses_selected_server(qtbot, monkeypatch) -> None:
    class FakeRemoteDirectoryDialog:
        def __init__(self, profiles, remote_browser_service, parent=None) -> None:
            del remote_browser_service, parent
            self.profiles = profiles
            self.selected_path = "/remote/path"
            self._selected_profile_name = profiles[-1].name

        def load_root(self) -> None:
            return None

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def selected_profile_name(self) -> str:
            return self._selected_profile_name

    created = {}

    def fake_source_factory(config, auth=None, connection=None):
        created["config"] = config
        created["connection"] = connection

        class FakeSource:
            def list_relative_paths(self) -> list[str]:
                return []

            def read_bytes(self, relative_path: str) -> bytes:
                raise FileNotFoundError(relative_path)

        return FakeSource()

    monkeypatch.setattr(
        "remote_image_compare.ui.main_window.RemoteDirectoryDialog",
        FakeRemoteDirectoryDialog,
    )

    store_profile_a = SftpServerProfile(
        name="server-a",
        host="127.0.0.1",
        port=2222,
        username="user-a",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw-a",
        private_key_path=None,
        passphrase="",
        default_root="/a",
    )
    store_profile_b = SftpServerProfile(
        name="server-b",
        host="127.0.0.2",
        port=2223,
        username="user-b",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw-b",
        private_key_path=None,
        passphrase="",
        default_root="/b",
    )
    store = ServerProfileStore(Path("dummy.json"))
    store.list_profiles = lambda: [store_profile_a, store_profile_b]  # type: ignore[method-assign]

    window = MainWindow(profile_store=store, source_factory=fake_source_factory)
    qtbot.addWidget(window)

    window._handle_pane_remote_bind_requested(0)

    assert created["connection"].host == "127.0.0.2"


def test_pane_widget_accepts_loaded_image(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    image = QImage(10, 20, QImage.Format.Format_RGB32)
    pane.set_image(image, "img1.png")

    assert pane.status_text() == "10 x 20"
    assert pane.has_image() is True


def test_pane_widget_drop_event_emits_directory_path(qtbot, tmp_path: Path) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)

    dropped_paths: list[str] = []
    pane.directory_dropped.connect(dropped_paths.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    pos = pane.rect().center()
    drag_event = QDragEnterEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drop_event = QDropEvent(
        pane.mapToGlobal(pos),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    pane.dragEnterEvent(drag_event)
    pane.dropEvent(drop_event)

    assert dropped_paths == [str(tmp_path)]


def test_pane_child_widgets_accept_directory_drag(qtbot, tmp_path: Path) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)

    children = [pane.image_viewport, pane.content_host, pane.empty_state]

    for child in children:
        assert child.acceptDrops() is True


def test_dragging_directory_over_image_viewport_emits_drop_signal(qtbot, tmp_path: Path) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)

    dropped_paths: list[str] = []
    pane.directory_dropped.connect(dropped_paths.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    pos = pane.image_viewport.rect().center()
    drag_event = QDragEnterEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drop_event = QDropEvent(
        pane.image_viewport.mapToGlobal(pos),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    QApplication.sendEvent(pane.image_viewport, drag_event)
    QApplication.sendEvent(pane.image_viewport, drop_event)

    assert dropped_paths == [str(tmp_path)]


def test_pane_drag_move_event_accepts_directory(qtbot, tmp_path: Path) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    pos = pane.rect().center()
    move_event = QDragMoveEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    pane.dragMoveEvent(move_event)

    assert move_event.isAccepted() is True


def test_pane_header_and_status_widgets_accept_directory_drag(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)

    children = [
        pane.title_label,
        pane.status_label,
        pane.clear_button,
        pane.swap_button,
        pane.copy_path_button,
    ]

    for child in children:
        assert child.acceptDrops() is True


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

    assert window.first_pane().status_text() == "6 x 6"


def test_main_window_populates_catalog_from_local_sources(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "img2.jpg").write_bytes(b"two")
    (left / "img10.jpg").write_bytes(b"ten")
    (right / "img10.jpg").write_bytes(b"ten")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )

    window.refresh_catalog()

    assert window.catalog_items() == ["img10.jpg"]


def test_main_window_loads_real_local_image_into_pane(qtbot, tmp_path: Path) -> None:
    image = QImage(12, 7, QImage.Format.Format_RGB32)
    image.fill(0xFF123456)
    image_path = tmp_path / "img1.png"
    assert image.save(str(image_path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )

    window.refresh_catalog()
    window.load_selected_file("img1.png")

    assert window.first_pane().has_image() is True
    assert window.first_pane().status_text() == "12 x 7"
    assert window.current_filename_label.text() == "img1.png"


def test_main_window_bind_source_path_loads_first_image(qtbot, tmp_path: Path) -> None:
    image = QImage(16, 9, QImage.Format.Format_RGB32)
    image.fill(0xFF56789A)
    image_path = tmp_path / "img1.png"
    assert image.save(str(image_path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)

    window.bind_source_path(0, str(tmp_path))

    assert window.first_pane().title_text() == tmp_path.name
    assert window.catalog_items() == ["img1.png"]
    assert window.first_pane().has_image() is True
    assert window.first_pane().status_text() == "16 x 9"
    assert window.current_filename_label.text() == "img1.png"


def test_main_window_copy_path_button_copies_bound_root_path(qtbot, tmp_path: Path) -> None:
    image = QImage(16, 9, QImage.Format.Format_RGB32)
    image.fill(0xFF56789A)
    assert image.save(str(tmp_path / "img1.png"), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)

    window.bind_source_path(0, str(tmp_path))
    qtbot.mouseClick(window.first_pane().copy_path_button, Qt.MouseButton.LeftButton)

    assert QApplication.clipboard().text() == str(tmp_path)


def test_binding_new_source_preserves_current_item_when_still_available(
    qtbot, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for folder, color_offset in ((left, 1), (right, 10)):
        for index in range(1, 3):
            image = QImage(12, 12, QImage.Format.Format_RGB32)
            image.fill(color_offset + index)
            assert image.save(str(folder / f"img{index}.png"), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)

    window.bind_source_path(0, str(left))
    window.set_current_index(1)

    assert window.current_filename() == "img2.png"

    window.bind_source_path(1, str(right))

    assert window.current_filename() == "img2.png"
    assert window.current_file_label() == "2 / 2"


def test_clicking_catalog_item_loads_real_image(qtbot, tmp_path: Path) -> None:
    image = QImage(9, 9, QImage.Format.Format_RGB32)
    image.fill(0xFF998877)
    image_path = tmp_path / "img2.png"
    assert image.save(str(image_path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()

    item = window.file_list.item(0)
    window.jump_to_item(item)

    assert window.first_pane().has_image() is True
    assert window.current_file_label() == "1 / 1"
    assert window.current_filename_label.text() == "img2.png"


def test_compare_mode_switch_refreshes_catalog(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "img1.jpg").write_bytes(b"one")
    (left / "img2.jpg").write_bytes(b"two")
    (right / "img2.jpg").write_bytes(b"two")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )

    window.refresh_catalog()
    assert window.catalog_items() == ["img2.jpg"]

    window.compare_mode_combo.setCurrentText("主目录基准")

    assert window.catalog_items() == ["img1.jpg", "img2.jpg"]


def test_navigation_moves_between_catalog_items(qtbot, tmp_path: Path) -> None:
    for index in range(1, 3):
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(index)
        path = tmp_path / f"img{index}.png"
        assert image.save(str(path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()

    window.set_current_index(0)
    window.next_image()
    assert window.current_file_label() == "2 / 2"

    window.previous_image()
    assert window.current_file_label() == "1 / 2"


def test_main_window_exposes_previous_and_next_buttons(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.previous_button.text() == "上一张"
    assert window.next_button.text() == "下一张"


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


def test_navigation_refreshes_open_tolerance_map_content(qtbot, tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()
    _save_image(left_root / "img1.png", 8, 8, 0xFF000000)
    _save_image(right_root / "img1.png", 8, 8, 0xFF000000)
    _save_image(left_root / "img2.png", 8, 8, 0xFF000000)
    _save_image(right_root / "img2.png", 8, 8, 0xFFFFFFFF)

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local A",
            root_path=str(left_root),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Local B",
            root_path=str(right_root),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.open_tolerance_window()
    window._tolerance_window.tolerance_slider.setValue(0)
    window._tolerance_window.set_selected_panes([0, 1])
    qtbot.waitUntil(lambda: window._tolerance_window.current_tolerance_image() is not None)

    first_map = window._tolerance_window.current_tolerance_image()

    window.next_image()
    qtbot.waitUntil(
        lambda: window._tolerance_window.current_tolerance_image() is not None
        and window._tolerance_window.current_filename_label.text() == "img2.png"
    )

    second_map = window._tolerance_window.current_tolerance_image()

    assert first_map is not None
    assert second_map is not None
    assert window._tolerance_window.current_filename_label.text() == "img2.png"
    assert sum(1 for check in window._tolerance_window.pane_checks if check.isChecked()) == 2
    assert first_map.pixelColor(0, 0).getRgb()[:3] == (0, 0, 0)
    second_color = second_map.pixelColor(0, 0)
    assert second_color.red() > second_color.green()
    assert second_color.red() > second_color.blue()


def test_sync_tolerance_mode_follows_main_pane_view_state(qtbot, tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()
    _save_image(left_root / "img1.png", 1920, 1080, 0xFF000000)
    _save_image(right_root / "img1.png", 1920, 1080, 0xFF101010)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local A",
            root_path=str(left_root),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Local B",
            root_path=str(right_root),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.open_tolerance_window()
    assert window._tolerance_window is not None
    window._tolerance_window.set_selected_panes([0, 1])
    qtbot.mouseClick(window._tolerance_window.sync_mode_button, Qt.MouseButton.LeftButton)

    window.first_pane().apply_zoom_delta(4)
    _drag_pane_by(window.first_pane(), QPoint(30, 18))
    qtbot.waitUntil(
        lambda: window._tolerance_window.current_tolerance_image() is not None
        and window._tolerance_window.current_tolerance_image().width() < 1920,
        timeout=4000,
    )

    assert window._tolerance_window.view_mode() == "sync"
    assert window._tolerance_window.tolerance_view.zoom_factor() == 1.0


def test_sync_tolerance_mode_aligns_different_image_sizes_when_zoomed(
    qtbot, tmp_path: Path
) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()

    left = QImage(200, 100, QImage.Format.Format_RGB32)
    left.fill(QColor(0, 0, 0))
    right = QImage(100, 50, QImage.Format.Format_RGB32)
    right.fill(QColor(0, 0, 0))
    for x in range(50, 150):
        for y in range(25, 75):
            left.setPixelColor(x, y, QColor(255, 255, 255))
    for x in range(25, 75):
        for y in range(12, 37):
            right.setPixelColor(x, y, QColor(255, 255, 255))
    assert left.save(str(left_root / "img1.png"), "PNG")
    assert right.save(str(right_root / "img1.png"), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local A",
            root_path=str(left_root),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Local B",
            root_path=str(right_root),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.open_tolerance_window()
    assert window._tolerance_window is not None
    window._tolerance_window.tolerance_slider.setValue(0)
    window._tolerance_window.set_selected_panes([0, 1])
    qtbot.mouseClick(window._tolerance_window.sync_mode_button, Qt.MouseButton.LeftButton)

    window.first_pane().apply_zoom_delta(2)
    qtbot.waitUntil(
        lambda: window._tolerance_window.current_tolerance_image() is not None
        and window._tolerance_window.current_tolerance_image().width() < 200,
        timeout=4000,
    )

    current_map = window._tolerance_window.current_tolerance_image()
    assert current_map is not None
    center = current_map.pixelColor(current_map.width() // 2, current_map.height() // 2)
    assert center == QColor(255, 255, 255)


def test_hidden_tolerance_window_does_not_refresh_on_navigation(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
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
    assert window._tolerance_window is not None
    window._tolerance_window.hide()

    seen_calls: list[str] = []
    original = window._tolerance_window.set_source_images

    def tracking_set_source_images(images_by_pane, current_filename):
        seen_calls.append(current_filename)
        return original(images_by_pane, current_filename)

    monkeypatch.setattr(window._tolerance_window, "set_source_images", tracking_set_source_images)

    window.next_image()

    assert seen_calls == []


def test_main_window_hover_updates_open_tolerance_window_rgb_readout(qtbot, tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()
    _save_image(left_root / "img1.png", 8, 8, 0xFF112233)
    _save_image(right_root / "img1.png", 8, 8, 0xFF223344)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left_root),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right_root),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.open_tolerance_window()
    window._tolerance_window.set_selected_panes([0, 1])
    qtbot.waitUntil(lambda: window._tolerance_window.current_tolerance_image() is not None)

    pos = QPoint(20, 20)
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        window.first_pane().image_viewport.mapToGlobal(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window.first_pane().image_viewport, event)
    qtbot.waitUntil(lambda: window._tolerance_window.left_rgb_label.text() != "")

    assert "17" in window._tolerance_window.left_rgb_label.text()


def test_navigation_buttons_move_between_catalog_items(qtbot, tmp_path: Path) -> None:
    for index in range(1, 3):
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(index)
        path = tmp_path / f"img{index}.png"
        assert image.save(str(path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.set_current_index(0)

    window.next_button.click()
    assert window.current_file_label() == "2 / 2"

    window.previous_button.click()
    assert window.current_file_label() == "1 / 2"


def test_left_and_right_keys_move_between_catalog_items(qtbot, tmp_path: Path) -> None:
    for index in range(1, 3):
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(index)
        path = tmp_path / f"img{index}.png"
        assert image.save(str(path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.set_current_index(0)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    window.setFocus()

    qtbot.keyClick(window, Qt.Key.Key_Right)
    assert window.current_file_label() == "2 / 2"

    qtbot.keyClick(window, Qt.Key.Key_Left)
    assert window.current_file_label() == "1 / 2"


def test_binding_source_updates_pane_title(qtbot, tmp_path: Path) -> None:
    source_root = tmp_path / "album"
    source_root.mkdir()

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Album",
            root_path=str(source_root),
            recursive=False,
        ),
    )

    assert window.first_pane().title_text() == "Album"


def test_main_window_uses_injected_source_factory(qtbot, tmp_path: Path) -> None:
    class FakeSource:
        def list_relative_paths(self) -> list[str]:
            return ["img1.png"]

        def read_bytes(self, relative_path: str) -> bytes:
            image = QImage(5, 5, QImage.Format.Format_RGB32)
            image.fill(0xFF445566)
            path = tmp_path / relative_path
            image.save(str(path), "PNG")
            return path.read_bytes()

    created = {}

    def fake_source_factory(config, auth=None, connection=None):
        created["config"] = config
        created["auth"] = auth
        created["connection"] = connection
        return FakeSource()

    window = MainWindow(source_factory=fake_source_factory)
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Factory",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()

    assert created["config"].display_name == "Factory"
    assert window.catalog_items() == ["img1.png"]


def test_binding_sftp_source_passes_auth_to_factory(qtbot) -> None:
    created = {}

    def fake_source_factory(config, auth=None, connection=None):
        created["config"] = config
        created["auth"] = auth
        created["connection"] = connection

        class FakeSource:
            def list_relative_paths(self) -> list[str]:
                return ["remote.png"]

            def read_bytes(self, relative_path: str) -> bytes:
                image = QImage(3, 3, QImage.Format.Format_RGB32)
                image.fill(0xFF112233)
                buffer = QImage(image)
                from PySide6.QtCore import QBuffer, QByteArray, QIODevice

                byte_array = QByteArray()
                qbuffer = QBuffer(byte_array)
                qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
                buffer.save(qbuffer, "PNG")
                return bytes(byte_array)

        return FakeSource()

    auth = SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="secret")
    connection = SftpConnectionConfig(host="127.0.0.1", port=22, username="tester")
    window = MainWindow(source_factory=fake_source_factory)
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.SFTP,
            display_name="Remote",
            root_path="/photos",
            recursive=False,
        ),
        auth=auth,
        connection=connection,
    )
    window.refresh_catalog()

    assert created["config"].kind is SourceKind.SFTP
    assert created["auth"] == auth
    assert created["connection"] == connection
    assert window.catalog_items() == ["remote.png"]


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
                image = QImage(3, 3, QImage.Format.Format_RGB32)
                image.fill(0xFF112233)
                buffer = QImage(image)
                from PySide6.QtCore import QBuffer, QByteArray, QIODevice

                byte_array = QByteArray()
                qbuffer = QBuffer(byte_array)
                qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
                buffer.save(qbuffer, "PNG")
                return bytes(byte_array)

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

    assert created["config"].kind is SourceKind.SFTP
    assert created["config"].root_path == "/srv/photos/setA"
    assert created["connection"].host == "127.0.0.1"
    assert created["connection"].port == 2222
    assert created["connection"].username == "tester"
    assert created["auth"].password == "pw"
    assert window.catalog_items() == ["remote.png"]


def test_main_window_persists_profiles_when_manager_closes_after_inner_save(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
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

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, profiles, parent) -> None:
            del profiles, parent

        def exec(self) -> int:
            return QDialog.DialogCode.Rejected

        def deleted_profile_names(self) -> list[str]:
            return []

        def profiles(self) -> list[SftpServerProfile]:
            return [profile]

    monkeypatch.setattr("remote_image_compare.ui.main_window.ServerManagerDialog", FakeDialog)

    window = MainWindow(profile_store=store)
    qtbot.addWidget(window)

    window.open_server_manager()

    assert store.list_profiles() == [profile]
    assert window.saved_server_names() == ["wsl"]


def test_clearing_bound_pane_removes_it_from_catalog(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 8, 8, 0xFF123456)
    _save_image(right / "img1.png", 8, 8, 0xFF123456)

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source_path(0, str(left))
    window.bind_source_path(1, str(right))

    window.clear_pane_binding(1)

    assert "pane-2" not in window._sources_by_pane


def test_primary_mode_promotes_next_bound_pane_after_clear(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "left_only.png", 8, 8, 0xFF101010)
    _save_image(right / "right_only.png", 8, 8, 0xFF202020)

    window = MainWindow()
    qtbot.addWidget(window)
    window.compare_mode_combo.setCurrentText("主目录基准")
    window.bind_source_path(0, str(left))
    window.bind_source_path(1, str(right))

    window.clear_pane_binding(0)

    assert window.catalog_items() == ["right_only.png"]


def test_main_window_exposes_source_binding_controls(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.server_manager_button.text() == "服务器"
    assert window.bind_source_button.text() == "绑定窗口"


def test_main_window_toolbar_keeps_binding_controls_in_top_row(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.top_toolbar_layout.itemAt(1).widget() is window.server_manager_button
    assert window.top_toolbar_layout.itemAt(2).widget() is window.bind_source_button


def test_main_window_loads_first_catalog_item_if_available(qtbot, tmp_path: Path) -> None:
    image = QImage(11, 11, QImage.Format.Format_RGB32)
    image.fill(0xFFAA5500)
    image_path = tmp_path / "img1.png"
    assert image.save(str(image_path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    assert window.current_file_label() == "1 / 1"
    assert window.first_pane().has_image() is True
    assert window.current_filename_label.text() == "img1.png"


def test_bind_source_path_recursively_discovers_nested_images(qtbot, tmp_path: Path) -> None:
    nested = tmp_path / "setA"
    nested.mkdir()
    image = QImage(11, 11, QImage.Format.Format_RGB32)
    image.fill(0xFFAA5500)
    image_path = nested / "img1.png"
    assert image.save(str(image_path), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)

    window.bind_source_path(0, str(tmp_path))

    assert window.catalog_items() == ["setA/img1.png"]
    assert window.current_filename() == "setA/img1.png"
    assert window.current_filename_label.text() == "setA/img1.png"


def test_main_window_can_toggle_sidebar(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.sidebar_is_visible() is True
    assert window.main_splitter.orientation() == Qt.Orientation.Horizontal

    window.toggle_sidebar()
    assert window.sidebar_is_visible() is False

    window.toggle_sidebar()
    assert window.sidebar_is_visible() is True


def test_main_window_uses_fixed_top_toolbar_layout(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.left_panel_layout.itemAt(0).widget() is window.top_toolbar
    assert window.top_toolbar_layout.itemAt(0).widget() is window.toggle_sidebar_button
    assert window.top_toolbar_layout.itemAt(1).widget() is window.server_manager_button
    assert window.top_toolbar_layout.itemAt(2).widget() is window.bind_source_button
    assert window.top_toolbar_layout.itemAt(3).widget() is window.record_button
    assert window.top_toolbar_layout.itemAt(4).widget() is window.previous_button
    assert window.top_toolbar_layout.itemAt(5).widget() is window.next_button
    assert window.top_toolbar_layout.itemAt(6).widget() is window.tolerance_button
    assert window.top_toolbar_layout.itemAt(7).widget() is window.compare_mode_combo
    assert window.top_toolbar_layout.itemAt(8).widget() is window.layout_mode_combo
    assert window.top_toolbar_layout.itemAt(9).widget() is window.current_filename_label
    assert window.top_toolbar_layout.itemAt(11).widget() is window.position_label
    assert window.toggle_sidebar_button.minimumSize() == window.toggle_sidebar_button.maximumSize()
    assert window.server_manager_button.minimumSize() == window.server_manager_button.maximumSize()
    assert window.bind_source_button.minimumSize() == window.bind_source_button.maximumSize()
    assert window.record_button.minimumSize() == window.record_button.maximumSize()
    assert window.previous_button.minimumSize() == window.previous_button.maximumSize()
    assert window.next_button.minimumSize() == window.next_button.maximumSize()
    assert window.tolerance_button.minimumSize() == window.tolerance_button.maximumSize()
    assert window.compare_mode_combo.minimumSize() == window.compare_mode_combo.maximumSize()
    assert window.layout_mode_combo.minimumSize() == window.layout_mode_combo.maximumSize()
    assert window.toggle_sidebar_button.y() == window.server_manager_button.y()
    assert window.server_manager_button.y() == window.bind_source_button.y()
    assert window.bind_source_button.y() == window.record_button.y()
    assert window.record_button.y() == window.previous_button.y()
    assert window.previous_button.y() == window.next_button.y()
    assert window.next_button.y() == window.tolerance_button.y()
    assert window.tolerance_button.y() == window.compare_mode_combo.y()
    assert window.toggle_sidebar_button.x() < window.compare_mode_combo.x()
    assert window.server_manager_button.x() < window.bind_source_button.x()
    assert window.bind_source_button.x() < window.record_button.x()
    assert window.record_button.x() < window.previous_button.x()
    assert window.previous_button.x() < window.next_button.x()
    assert window.next_button.x() < window.tolerance_button.x()
    assert window.compare_mode_combo.x() < window.layout_mode_combo.x()
    assert window.position_label.x() > window.compare_mode_combo.x()


def test_main_window_toolbar_buttons_use_shadow_effect(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    buttons = [
        window.toggle_sidebar_button,
        window.server_manager_button,
        window.bind_source_button,
        window.record_button,
        window.previous_button,
        window.next_button,
        window.tolerance_button,
    ]

    for button in buttons:
        assert isinstance(button.graphicsEffect(), QGraphicsDropShadowEffect)


def test_image_pane_uses_card_shadow_effect(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    assert isinstance(pane.graphicsEffect(), QGraphicsDropShadowEffect)


def test_main_window_uses_split_layout_with_dedicated_sidebar(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    root_layout = window.centralWidget().layout()

    assert root_layout.count() == 1
    assert root_layout.itemAt(0).widget() is window.main_splitter
    assert window.main_splitter.count() == 2
    assert window.main_splitter.widget(0) is window.left_panel
    assert window.main_splitter.widget(1) is window.sidebar
    assert window.left_panel_layout.count() == 2
    assert window.left_panel_layout.itemAt(0).widget() is window.top_toolbar
    assert window.left_panel_layout.itemAt(1).widget() is window.grid_host
    assert window.top_toolbar_layout.itemAt(1).widget() is window.server_manager_button
    assert window.top_toolbar_layout.itemAt(2).widget() is window.bind_source_button
    assert window.top_toolbar_layout.itemAt(3).widget() is window.record_button
    assert window.top_toolbar_layout.itemAt(4).widget() is window.previous_button
    assert window.top_toolbar_layout.itemAt(5).widget() is window.next_button
    assert window.top_toolbar_layout.itemAt(6).widget() is window.tolerance_button
    assert window.top_toolbar_layout.itemAt(8).widget() is window.layout_mode_combo
    assert window.top_toolbar_layout.itemAt(9).widget() is window.current_filename_label
    assert window.top_toolbar_layout.itemAt(11).widget() is window.position_label
    assert window.sidebar.layout().count() == 1
    assert window.sidebar.layout().itemAt(0).widget() is window.file_list


def test_layout_mode_switch_updates_visible_panes(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window.layout_mode_combo.setCurrentText("1 x 2")
    assert window.active_pane_count == 2
    assert sum(1 for pane in window._panes if pane.isVisible()) == 2

    window.layout_mode_combo.setCurrentText("1 x 3")
    assert window.active_pane_count == 3
    assert sum(1 for pane in window._panes if pane.isVisible()) == 3

    window.layout_mode_combo.setCurrentText("2 x 2")
    assert window.active_pane_count == 4
    assert sum(1 for pane in window._panes if pane.isVisible()) == 4

    window.layout_mode_combo.setCurrentText("2 x 3")
    assert window.active_pane_count == 6
    assert sum(1 for pane in window._panes if pane.isVisible()) == 6


def test_pane_widget_fits_large_image_to_view(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(3840, 2160, QImage.Format.Format_RGB32)
    image.fill(0xFF224466)
    pane.set_image(image, "4k")

    rendered_width, rendered_height = pane.rendered_image_size()
    viewport_width, viewport_height = pane.viewport_size()

    assert rendered_width <= viewport_width
    assert rendered_height <= viewport_height


def test_pane_widget_zoom_delta_changes_zoom_factor(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    image.fill(0xFF335577)
    pane.set_image(image, "zoom")

    before = pane.zoom_factor()
    pane.apply_zoom_delta(1)
    after = pane.zoom_factor()

    assert after > before


def test_pane_widget_wheel_event_changes_zoom_factor(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    image.fill(0xFF335577)
    pane.set_image(image, "zoom")

    before = pane.zoom_factor()
    center = pane.rect().center()
    event = QWheelEvent(
        center,
        pane.mapToGlobal(center),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    pane.wheelEvent(event)

    assert pane.zoom_factor() > before


def test_wheel_on_image_viewport_changes_zoom_factor(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    image.fill(0xFF446688)
    pane.set_image(image, "viewport-wheel")

    before = pane.zoom_factor()
    center = pane.image_viewport.rect().center()
    event = QWheelEvent(
        center,
        pane.image_viewport.mapToGlobal(center),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(pane.image_viewport, event)

    assert pane.zoom_factor() > before


def test_wheel_zoom_uses_mouse_position_as_anchor(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(1500, 1000, QImage.Format.Format_RGB32)
    image.fill(0xFF446688)
    pane.set_image(image, "anchor-wheel")

    anchor = QPoint(120, 80)
    event = QWheelEvent(
        anchor,
        pane.image_viewport.mapToGlobal(anchor),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(pane.image_viewport, event)

    assert pane.zoom_factor() > 1.0
    assert pane.pan_offset() != (0, 0)


def test_toggle_compare_pair_switches_between_last_two_images(qtbot, tmp_path: Path) -> None:
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
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.set_current_index(0)
    window.set_current_index(1)

    window.toggle_compare_pair()
    assert window.current_filename() == "img1.png"

    window.toggle_compare_pair()
    assert window.current_filename() == "img2.png"


def test_main_window_synchronizes_zoom_across_loaded_panes(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 1920, 1080, 0xFF224466)
    _save_image(right / "img1.png", 1920, 1080, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    window.first_pane().apply_zoom_delta(3)

    assert window.first_pane().zoom_factor() == window._panes[1].zoom_factor()


def test_main_window_synchronizes_pan_across_loaded_panes(qtbot, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _save_image(left / "img1.png", 1920, 1080, 0xFF224466)
    _save_image(right / "img1.png", 1920, 1080, 0xFF446688)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.first_pane().apply_zoom_delta(4)

    _drag_pane_by(window.first_pane(), QPoint(30, 18))

    assert window.first_pane().pan_offset() == window._panes[1].pan_offset()


def test_main_window_preserves_shared_view_state_when_switching_images(
    qtbot, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for name, color in (("img1.png", 0xFF224466), ("img2.png", 0xFF335577)):
        _save_image(left / name, 1920, 1080, color)
    for name, color in (("img1.png", 0xFF446688), ("img2.png", 0xFF557799)):
        _save_image(right / name, 1920, 1080, color)

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Left",
            root_path=str(left),
            recursive=False,
        ),
    )
    window.bind_source(
        1,
        SourceConfig(
            id="pane-2",
            kind=SourceKind.LOCAL,
            display_name="Right",
            root_path=str(right),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()
    window.first_pane().apply_zoom_delta(4)
    _drag_pane_by(window.first_pane(), QPoint(30, 18))

    expected_zoom = window.first_pane().zoom_factor()
    expected_pan = window.first_pane().pan_offset()
    window.set_current_index(1)

    assert window.first_pane().zoom_factor() == expected_zoom
    assert window.first_pane().pan_offset() == expected_pan
    assert window._panes[1].zoom_factor() == expected_zoom
    assert window._panes[1].pan_offset() == expected_pan


def test_zoom_does_not_increase_main_window_minimum_size(qtbot, tmp_path: Path) -> None:
    image = QImage(3840, 2160, QImage.Format.Format_RGB32)
    image.fill(0xFF335577)
    assert image.save(str(tmp_path / "big.png"), "PNG")

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    window.bind_source(
        0,
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        ),
    )
    window.refresh_catalog()
    window.load_first_catalog_item_if_available()

    before = window.minimumSize()
    window.first_pane().apply_zoom_delta(4)
    after = window.minimumSize()

    assert after.width() <= before.width()
    assert after.height() <= before.height()


def test_main_window_uses_tighter_grid_spacing_for_larger_image_area(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    margins = window.grid_layout.contentsMargins()
    assert window.grid_layout.spacing() <= 8
    assert window.left_panel_layout.spacing() <= 8
    assert margins.left() == 0
    assert margins.top() == 0


def test_image_pane_prioritizes_viewport_area_over_frame_spacing(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)

    layout = pane.layout()
    margins = layout.contentsMargins()

    assert layout.spacing() <= 6
    assert margins.left() <= 8
    assert margins.top() <= 8


def test_pane_widget_drag_updates_pan_offset(qtbot) -> None:
    pane = ImagePaneWidget("Pane 1")
    qtbot.addWidget(pane)
    pane.resize(480, 320)
    pane.show()
    qtbot.waitExposed(pane)

    image = QImage(1920, 1080, QImage.Format.Format_RGB32)
    image.fill(0xFF446688)
    pane.set_image(image, "drag")
    pane.apply_zoom_delta(4)

    before = pane.pan_offset()
    _drag_pane_by(pane, QPoint(20, 10))

    assert pane.pan_offset() != before


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

    pos = QPoint(50, 50)
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        pane.image_viewport.mapToGlobal(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(pane.image_viewport, event)

    assert seen
