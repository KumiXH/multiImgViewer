from pathlib import Path

from remote_image_compare.domain.sorting import natural_key
from remote_image_compare.sources.base import ImageSource

IMAGE_SUFFIXES = {
    ".bmp",
    ".dib",
    ".gif",
    ".jfif",
    ".jpe",
    ".jpeg",
    ".jpg",
    ".pbm",
    ".pgm",
    ".png",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}


class LocalPathSource(ImageSource):
    def __init__(self, config) -> None:
        self.config = config
        self.root = Path(config.root_path)

    def list_relative_paths(self) -> list[str]:
        iterator = self.root.rglob("*") if self.config.recursive else self.root.iterdir()
        results = [
            path.relative_to(self.root).as_posix()
            for path in iterator
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        ]
        return sorted(results, key=natural_key)

    def read_bytes(self, relative_path: str) -> bytes:
        return (self.root / relative_path).read_bytes()
