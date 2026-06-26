from remote_image_compare.services.cache import LruImageCache


class ImageLoader:
    def __init__(self, cache: LruImageCache[tuple[str, str], bytes]) -> None:
        self.cache = cache

    def load_bytes(self, source_id: str, source, relative_path: str) -> bytes:
        key = (source_id, relative_path)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        data = source.read_bytes(relative_path)
        self.cache.put(key, data)
        return data


class RequestTracker:
    def __init__(self) -> None:
        self._tokens: dict[str, int] = {}

    def next_token(self, pane_id: str) -> int:
        token = self._tokens.get(pane_id, 0) + 1
        self._tokens[pane_id] = token
        return token

    def is_current(self, pane_id: str, token: int) -> bool:
        return self._tokens.get(pane_id) == token
