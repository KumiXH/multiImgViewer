from collections.abc import Mapping

from PySide6.QtGui import QImage

from remote_image_compare.services.cache import LruImageCache
from remote_image_compare.services.image_loader import ImageLoader


class RealImageService:
    def __init__(self, sources_by_pane: Mapping[str, object]) -> None:
        self.sources_by_pane = dict(sources_by_pane)
        self.loader = ImageLoader(LruImageCache(capacity=12))

    def replace_sources(self, sources_by_pane: Mapping[str, object]) -> None:
        self.sources_by_pane = dict(sources_by_pane)

    def load_image(self, pane_id: str, relative_path: str) -> QImage | None:
        source = self.sources_by_pane.get(pane_id)
        if source is None:
            return None
        data = self.loader.load_bytes(pane_id, source, relative_path)
        image = QImage.fromData(data)
        if image.isNull():
            return None
        return image

    def load_image_async(self, pane_id: str, relative_path: str, callback) -> None:
        callback(pane_id, relative_path, self.load_image(pane_id, relative_path))
