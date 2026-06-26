from remote_image_compare.services.cache import LruImageCache


def test_cache_returns_recent_value() -> None:
    cache = LruImageCache(capacity=2)
    cache.put(("a", "img1.jpg"), "first")
    assert cache.get(("a", "img1.jpg")) == "first"


def test_cache_evicts_oldest_entry() -> None:
    cache = LruImageCache(capacity=2)
    cache.put(("a", "img1.jpg"), "first")
    cache.put(("a", "img2.jpg"), "second")
    cache.put(("a", "img3.jpg"), "third")
    assert cache.get(("a", "img1.jpg")) is None
    assert cache.get(("a", "img3.jpg")) == "third"
