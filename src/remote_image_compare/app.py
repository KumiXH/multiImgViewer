from PySide6.QtWidgets import QApplication

from remote_image_compare.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
