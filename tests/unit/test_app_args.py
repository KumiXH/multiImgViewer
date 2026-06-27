import remote_image_compare.app as app_module

from remote_image_compare.app import build_source_configs, detect_source_kind, parse_args
from remote_image_compare.domain.models import SourceKind


def test_parse_args_supports_demo_and_sources() -> None:
    args = parse_args(["--demo", "--source", r"C:\images\a", "--source", r"\\server\share\b"])
    assert args.demo is True
    assert args.sources == [r"C:\images\a", r"\\server\share\b"]


def test_detect_source_kind_handles_unc_paths() -> None:
    assert detect_source_kind(r"\\server\share\photos") is SourceKind.UNC
    assert detect_source_kind(r"C:\photos") is SourceKind.LOCAL


def test_build_source_configs_creates_incremental_pane_ids() -> None:
    configs = build_source_configs([r"C:\images\a", r"\\server\share\b"])
    assert [config.id for config in configs] == ["pane-1", "pane-2"]
    assert configs[0].kind is SourceKind.LOCAL
    assert configs[1].kind is SourceKind.UNC
    assert configs[0].recursive is True
    assert configs[1].recursive is True


def test_app_module_bootstraps_before_qt_import() -> None:
    source = app_module.__file__
    text = open(source, encoding="utf-8").read()

    assert text.index("configure_frozen_windows_dll_paths()") < text.index("from PySide6.QtWidgets import QApplication")
