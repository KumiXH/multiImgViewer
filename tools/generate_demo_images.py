from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter


def main() -> None:
    root = Path("demo_data")
    sets = {
        "set_a": {
            "img1.png": ("#1f77b4", "A-1"),
            "img2.png": ("#ff7f0e", "A-2"),
            "shared.png": ("#2ca02c", "A-S"),
        },
        "set_b": {
            "img1.png": ("#9467bd", "B-1"),
            "img2.png": ("#d62728", "B-2"),
            "shared.png": ("#17becf", "B-S"),
        },
        "set_c": {
            "img1.png": ("#8c564b", "C-1"),
            "img2.png": ("#bcbd22", "C-2"),
            "shared.png": ("#e377c2", "C-S"),
        },
    }

    for folder, files in sets.items():
        target_dir = root / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, (hex_color, label) in files.items():
            image = QImage(800, 520, QImage.Format.Format_RGB32)
            image.fill(QColor(hex_color))

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor("white"))
            font = QFont("Arial", 48)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, label)
            painter.end()

            image.save(str(target_dir / name), "PNG")


if __name__ == "__main__":
    main()
