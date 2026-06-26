from remote_image_compare.services.cache import LruImageCache
from remote_image_compare.services.image_loader import ImageLoader


class FakeSource:
    def __init__(self) -> None:
        self.calls = 0

    def read_bytes(self, relative_path: str) -> bytes:
        self.calls += 1
        return f"data:{relative_path}".encode()


def test_image_loader_uses_cache_before_source() -> None:
    source = FakeSource()
    cache = LruImageCache(capacity=2)
    cache.put(("pane-1", "img1.jpg"), b"cached")
    loader = ImageLoader(cache=cache)

    assert loader.load_bytes("pane-1", source, "img1.jpg") == b"cached"
    assert source.calls == 0


def test_image_loader_caches_source_result() -> None:
    source = FakeSource()
    cache = LruImageCache(capacity=2)
    loader = ImageLoader(cache=cache)

    assert loader.load_bytes("pane-1", source, "img2.jpg") == b"data:img2.jpg"
    assert cache.get(("pane-1", "img2.jpg")) == b"data:img2.jpg"
