from pathlib import Path

from PySide6.QtGui import QImage

from remote_image_compare.domain.models import SourceConfig, SourceKind
from remote_image_compare.services.real_image_service import RealImageService
from remote_image_compare.sources.local_source import LocalPathSource


def test_real_image_service_decodes_local_image(tmp_path: Path) -> None:
    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    image_path = tmp_path / "img1.png"
    assert image.save(str(image_path), "PNG")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        )
    )
    service = RealImageService({"pane-1": source})

    decoded = service.load_image("pane-1", "img1.png")

    assert decoded is not None
    assert decoded.size() == image.size()
