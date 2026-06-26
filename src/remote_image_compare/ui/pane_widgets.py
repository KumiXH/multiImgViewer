from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ImagePaneWidget(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_label = QLabel(title)
        self.image_label = QLabel()
        self.status_label = QLabel("Idle")
        self._has_image = False
        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.status_label)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def status_text(self) -> str:
        return self.status_label.text()

    def set_image(self, image: QImage, status: str) -> None:
        self.image_label.setPixmap(QPixmap.fromImage(image))
        self.status_label.setText(status)
        self._has_image = True

    def has_image(self) -> bool:
        return self._has_image
