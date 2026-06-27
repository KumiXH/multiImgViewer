import argparse
from pathlib import Path
from typing import Sequence

from remote_image_compare.bootstrap import configure_frozen_windows_dll_paths
from remote_image_compare.domain.models import SourceConfig, SourceKind

configure_frozen_windows_dll_paths()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="remote-image-compare")
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        default=[],
        help="Bind a local or UNC folder to the next pane",
    )
    parser.add_argument("--demo", action="store_true", help="Launch with generated demo folders")
    return parser.parse_args(argv)


def detect_source_kind(path: str) -> SourceKind:
    return SourceKind.UNC if path.startswith("\\\\") else SourceKind.LOCAL


def build_source_configs(paths: Sequence[str]) -> list[SourceConfig]:
    configs: list[SourceConfig] = []
    for index, path in enumerate(paths):
        display_name = Path(path).name or path
        configs.append(
            SourceConfig(
                id=f"pane-{index + 1}",
                kind=detect_source_kind(path),
                display_name=display_name,
                root_path=path,
                recursive=True,
            )
        )
    return configs


def demo_source_paths() -> list[str]:
    root = Path(__file__).resolve().parents[2] / "demo_data"
    return [str(root / "set_a"), str(root / "set_b"), str(root / "set_c")]


def create_window_from_args(args: argparse.Namespace):
    from remote_image_compare.ui.main_window import MainWindow

    window = MainWindow()
    paths = list(args.sources)
    if args.demo and not paths:
        paths = demo_source_paths()

    for index, config in enumerate(build_source_configs(paths[: window.active_pane_count])):
        window.bind_source(index, config)

    if paths:
        window.refresh_catalog()
        window.load_first_catalog_item_if_available()
    return window


def main(argv: Sequence[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    args = parse_args(argv)
    app = QApplication.instance() or QApplication([])
    window = create_window_from_args(args)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
